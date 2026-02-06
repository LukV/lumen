"""Schema augmentation: parse external docs and merge into schema context.

Supports three documentation formats:
- dbt schema.yml (models/sources with table and column descriptions)
- Markdown docs (free-form documentation)
- CSV data dictionary (table, column, description rows)
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import NamedTuple

import yaml

from lumen.schema.enricher import EnrichedSchema

logger = logging.getLogger(__name__)

_MARKDOWN_MAX_CHARS = 5000


class TableDoc(NamedTuple):
    description: str
    columns: dict[str, str]  # column_name -> description


def augment_schema(project_dir: Path, enriched: EnrichedSchema) -> str:
    """Discover and parse all doc files in project_dir, return merged text.

    Returns empty string if no documentation files are found.
    """
    if not project_dir.is_dir():
        return ""

    dbt_docs: dict[str, TableDoc] = {}
    markdown = ""
    csv_docs: dict[str, dict[str, str]] = {}

    # Parse dbt schema.yml
    yml_path = project_dir / "schema.yml"
    if yml_path.exists():
        dbt_docs = _parse_dbt_yml(yml_path)

    # Parse markdown docs
    md_path = project_dir / "docs.md"
    if md_path.exists():
        markdown = _parse_markdown(md_path)

    # Parse CSV data dictionary
    csv_path = project_dir / "dictionary.csv"
    if csv_path.exists():
        csv_docs = _parse_csv_dictionary(csv_path)

    if not dbt_docs and not markdown and not csv_docs:
        return ""

    return _format_augmented_docs(dbt_docs, markdown, csv_docs, enriched)


def _parse_dbt_yml(path: Path) -> dict[str, TableDoc]:
    """Parse a dbt schema.yml file into table documentation."""
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        logger.warning("Failed to parse dbt schema YAML: %s", path)
        return {}

    if not isinstance(data, dict):
        return {}

    result: dict[str, TableDoc] = {}

    # Parse models[] format
    for model in data.get("models", []):
        if not isinstance(model, dict):
            continue
        name = model.get("name", "")
        if not name:
            continue
        desc = model.get("description", "")
        columns = _extract_columns(model)
        result[name] = TableDoc(description=desc, columns=columns)

    # Parse sources[].tables[] format
    for source in data.get("sources", []):
        if not isinstance(source, dict):
            continue
        for table in source.get("tables", []):
            if not isinstance(table, dict):
                continue
            name = table.get("name", "")
            if not name:
                continue
            desc = table.get("description", "")
            columns = _extract_columns(table)
            result[name] = TableDoc(description=desc, columns=columns)

    return result


def _extract_columns(model: dict[str, object]) -> dict[str, str]:
    """Extract column name -> description from a dbt model/table entry."""
    columns: dict[str, str] = {}
    raw_cols = model.get("columns", [])
    if not isinstance(raw_cols, list):
        return columns
    for col in raw_cols:
        if not isinstance(col, dict):
            continue
        col_name = col.get("name", "")
        col_desc = col.get("description", "")
        if col_name and col_desc:
            columns[str(col_name)] = str(col_desc)
    return columns


def _parse_markdown(path: Path) -> str:
    """Read markdown docs, truncating at the character limit."""
    text = path.read_text()
    if len(text) > _MARKDOWN_MAX_CHARS:
        return text[:_MARKDOWN_MAX_CHARS] + "\n... (truncated)"
    return text


def _parse_csv_dictionary(path: Path) -> dict[str, dict[str, str]]:
    """Parse a CSV data dictionary with table, column, description columns.

    Returns {table_name: {column_name: description}}.
    """
    result: dict[str, dict[str, str]] = {}
    try:
        text = path.read_text()
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            table = row.get("table", "").strip()
            column = row.get("column", "").strip()
            description = row.get("description", "").strip()
            if not table or not column or not description:
                continue
            if table not in result:
                result[table] = {}
            result[table][column] = description
    except (csv.Error, KeyError):
        logger.warning("Failed to parse CSV dictionary: %s", path)
        return {}

    return result


def _format_augmented_docs(
    dbt_docs: dict[str, TableDoc],
    markdown: str,
    csv_docs: dict[str, dict[str, str]],
    enriched: EnrichedSchema,
) -> str:
    """Merge all documentation sources into a structured text block."""
    lines: list[str] = []

    # Collect all table names from enriched schema
    table_names = [t.name for t in enriched.tables]

    # Build per-table documentation
    for table_name in table_names:
        table_desc = ""
        col_descs: dict[str, str] = {}

        # dbt docs
        if table_name in dbt_docs:
            doc = dbt_docs[table_name]
            table_desc = doc.description
            col_descs.update(doc.columns)

        # CSV dictionary overrides/supplements
        if table_name in csv_docs:
            col_descs.update(csv_docs[table_name])

        if not table_desc and not col_descs:
            continue

        lines.append(f"## Table: {table_name}")
        if table_desc:
            lines.append(table_desc)
        for col_name, col_desc in col_descs.items():
            lines.append(f"- {col_name}: {col_desc}")
        lines.append("")

    # Also include dbt docs for tables not in the enriched schema
    for table_name, doc in dbt_docs.items():
        if table_name in table_names:
            continue
        lines.append(f"## Table: {table_name}")
        if doc.description:
            lines.append(doc.description)
        for col_name, col_desc in doc.columns.items():
            lines.append(f"- {col_name}: {col_desc}")
        lines.append("")

    # Append markdown documentation
    if markdown:
        lines.append("## Additional Documentation")
        lines.append(markdown)
        lines.append("")

    return "\n".join(lines).strip()
