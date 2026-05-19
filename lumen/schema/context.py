"""Schema context: enriched schema + optional docs, XML serialization, hashing."""

from __future__ import annotations

import hashlib
import json
from xml.sax.saxutils import escape

from pydantic import BaseModel, Field

from lumen.schema.enricher import EnrichedColumn, EnrichedSchema, EnrichedTable


class SchemaContext(BaseModel):
    enriched: EnrichedSchema = Field(alias="schema")
    augmented_docs: str | None = None
    hash: str = ""

    model_config = {"populate_by_name": True}


def to_xml(ctx: SchemaContext) -> str:
    """Serialize a SchemaContext to XML format for the LLM system prompt."""
    s = ctx.enriched
    lines: list[str] = []
    lines.append(f'<schema database="{escape(s.database)}" introspected_at="{escape(s.introspected_at)}">')

    for table in s.tables:
        lines.append(_table_xml(table))

    if ctx.augmented_docs:
        lines.append("  <augmented_docs>")
        lines.append(f"    {escape(ctx.augmented_docs)}")
        lines.append("  </augmented_docs>")

    lines.append("</schema>")
    return "\n".join(lines)


def _table_xml(table: EnrichedTable) -> str:
    """Serialize a single table to XML."""
    attrs = [f'name="{escape(table.name)}"']
    attrs.append(f'rows="~{table.row_count}"')
    if table.comment:
        attrs.append(f'description="{escape(table.comment)}"')

    lines: list[str] = []
    lines.append(f"  <table {' '.join(attrs)}>")

    for col in table.columns:
        lines.append(f"    {_column_xml(col)}")

    lines.append("  </table>")
    return "\n".join(lines)


def _column_xml(col: EnrichedColumn) -> str:
    """Serialize a single column to XML."""
    attrs = [f'name="{escape(col.name)}"', f'type="{escape(col.data_type)}"']

    if col.role != "other":
        attrs.append(f'role="{escape(col.role)}"')

    if col.is_primary_key:
        attrs.append('pk="true"')

    if col.foreign_key:
        attrs.append(f'fk="{escape(col.foreign_key)}"')

    if col.distinct_estimate is not None and col.role == "categorical":
        attrs.append(f'distinct_count="{col.distinct_estimate}"')

    if col.sample_values and col.role == "categorical":
        values_str = str(col.sample_values)
        attrs.append(f'values="{escape(values_str)}"')

    if col.min_value is not None and col.max_value is not None and col.role == "time_dimension":
        attrs.append(f'range="{escape(col.min_value)} to {escape(col.max_value)}"')

    if col.suggested_agg:
        attrs.append(f'suggested_agg="{escape(col.suggested_agg)}"')

    if col.comment:
        attrs.append(f'description="{escape(col.comment)}"')

    return f"<column {' '.join(attrs)}/>"


def compute_hash(ctx: SchemaContext) -> str:
    """Compute a deterministic SHA-256 hash of the schema context."""
    # Use deterministic JSON serialization (sorted keys, no None)
    data = ctx.enriched.model_dump(exclude_none=True)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    h = hashlib.sha256(canonical.encode()).hexdigest()
    return f"sha256:{h}"
