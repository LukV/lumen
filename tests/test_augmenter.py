"""Tests for schema augmentation: dbt YAML, markdown, CSV dictionary parsing."""

from pathlib import Path

from lumen.schema.augmenter import (
    _format_augmented_docs,
    _parse_csv_dictionary,
    _parse_dbt_yml,
    _parse_markdown,
    augment_schema,
)
from lumen.schema.enricher import EnrichedColumn, EnrichedSchema, EnrichedTable


def _make_enriched() -> EnrichedSchema:
    return EnrichedSchema(
        database="analytics",
        schema_name="public",
        tables=[
            EnrichedTable(
                name="orders",
                row_count=10000,
                columns=[
                    EnrichedColumn(name="id", data_type="integer", role="key", is_primary_key=True),
                    EnrichedColumn(name="amount", data_type="numeric", role="measure_candidate"),
                    EnrichedColumn(name="status", data_type="varchar", role="categorical"),
                ],
            ),
            EnrichedTable(
                name="customers",
                row_count=500,
                columns=[
                    EnrichedColumn(name="id", data_type="integer", role="key", is_primary_key=True),
                    EnrichedColumn(name="name", data_type="varchar", role="other"),
                ],
            ),
        ],
    )


# --- dbt YAML parsing ---


def test_parse_dbt_yml_models(tmp_path: Path) -> None:
    yml = tmp_path / "schema.yml"
    yml.write_text("""
models:
  - name: orders
    description: Sales orders in the pipeline.
    columns:
      - name: amount
        description: Deal value in USD
      - name: status
        description: Current deal stage
""")
    result = _parse_dbt_yml(yml)
    assert "orders" in result
    assert result["orders"].description == "Sales orders in the pipeline."
    assert result["orders"].columns["amount"] == "Deal value in USD"
    assert result["orders"].columns["status"] == "Current deal stage"


def test_parse_dbt_yml_sources(tmp_path: Path) -> None:
    yml = tmp_path / "schema.yml"
    yml.write_text("""
sources:
  - name: raw
    tables:
      - name: customers
        description: Customer master data.
        columns:
          - name: name
            description: Full customer name
""")
    result = _parse_dbt_yml(yml)
    assert "customers" in result
    assert result["customers"].description == "Customer master data."
    assert result["customers"].columns["name"] == "Full customer name"


def test_parse_dbt_yml_malformed(tmp_path: Path) -> None:
    yml = tmp_path / "schema.yml"
    yml.write_text("{{invalid yaml: [")
    result = _parse_dbt_yml(yml)
    assert result == {}


def test_parse_dbt_yml_not_dict(tmp_path: Path) -> None:
    yml = tmp_path / "schema.yml"
    yml.write_text("- just\n- a\n- list\n")
    result = _parse_dbt_yml(yml)
    assert result == {}


def test_parse_dbt_yml_empty_models(tmp_path: Path) -> None:
    yml = tmp_path / "schema.yml"
    yml.write_text("models: []\n")
    result = _parse_dbt_yml(yml)
    assert result == {}


# --- Markdown parsing ---


def test_parse_markdown(tmp_path: Path) -> None:
    md = tmp_path / "docs.md"
    md.write_text("# Orders\nThis table tracks all sales orders.\n")
    result = _parse_markdown(md)
    assert "Orders" in result
    assert "sales orders" in result


def test_parse_markdown_truncation(tmp_path: Path) -> None:
    md = tmp_path / "docs.md"
    md.write_text("x" * 6000)
    result = _parse_markdown(md)
    assert len(result) < 6000
    assert result.endswith("... (truncated)")


def test_parse_markdown_within_limit(tmp_path: Path) -> None:
    md = tmp_path / "docs.md"
    content = "Short doc"
    md.write_text(content)
    result = _parse_markdown(md)
    assert result == content


# --- CSV dictionary parsing ---


def test_parse_csv_dictionary(tmp_path: Path) -> None:
    csv_file = tmp_path / "dictionary.csv"
    csv_file.write_text("table,column,description\norders,amount,Deal value in USD\norders,status,Deal stage\n")
    result = _parse_csv_dictionary(csv_file)
    assert "orders" in result
    assert result["orders"]["amount"] == "Deal value in USD"
    assert result["orders"]["status"] == "Deal stage"


def test_parse_csv_dictionary_missing_columns(tmp_path: Path) -> None:
    csv_file = tmp_path / "dictionary.csv"
    csv_file.write_text("table,column,description\norders,,Deal value\n,amount,Deal value\n")
    result = _parse_csv_dictionary(csv_file)
    # Both rows should be skipped — empty table or column
    assert result == {}


def test_parse_csv_dictionary_extra_columns(tmp_path: Path) -> None:
    csv_file = tmp_path / "dictionary.csv"
    csv_file.write_text("table,column,description,example_values\norders,amount,Deal value in USD,100;200;300\n")
    result = _parse_csv_dictionary(csv_file)
    assert result["orders"]["amount"] == "Deal value in USD"


# --- Merge logic ---


def test_format_augmented_docs_all_sources() -> None:
    from lumen.schema.augmenter import TableDoc

    dbt_docs = {
        "orders": TableDoc(description="Sales orders in the pipeline.", columns={"amount": "Deal value in USD"}),
    }
    markdown = "# Business Context\nOrders represent completed sales."
    csv_docs = {"orders": {"status": "Current deal stage"}}
    enriched = _make_enriched()

    result = _format_augmented_docs(dbt_docs, markdown, csv_docs, enriched)
    assert "## Table: orders" in result
    assert "Sales orders in the pipeline." in result
    assert "- amount: Deal value in USD" in result
    assert "- status: Current deal stage" in result
    assert "## Additional Documentation" in result
    assert "Business Context" in result


def test_format_augmented_docs_dbt_only() -> None:
    from lumen.schema.augmenter import TableDoc

    dbt_docs = {
        "orders": TableDoc(description="Sales orders.", columns={}),
    }
    enriched = _make_enriched()
    result = _format_augmented_docs(dbt_docs, "", {}, enriched)
    assert "## Table: orders" in result
    assert "Sales orders." in result
    assert "## Additional Documentation" not in result


def test_format_augmented_docs_csv_overrides_dbt() -> None:
    from lumen.schema.augmenter import TableDoc

    dbt_docs = {
        "orders": TableDoc(description="From dbt.", columns={"amount": "dbt description"}),
    }
    csv_docs = {"orders": {"amount": "csv description"}}
    enriched = _make_enriched()

    result = _format_augmented_docs(dbt_docs, "", csv_docs, enriched)
    assert "- amount: csv description" in result
    assert "dbt description" not in result


def test_format_augmented_docs_extra_dbt_table() -> None:
    """Tables in dbt docs but not in enriched schema are still included."""
    from lumen.schema.augmenter import TableDoc

    dbt_docs = {
        "unknown_table": TableDoc(description="Not in schema.", columns={"col1": "Some column"}),
    }
    enriched = _make_enriched()
    result = _format_augmented_docs(dbt_docs, "", {}, enriched)
    assert "## Table: unknown_table" in result
    assert "Not in schema." in result


# --- Integration: augment_schema ---


def test_augment_schema_missing_dir(tmp_path: Path) -> None:
    result = augment_schema(tmp_path / "nonexistent", _make_enriched())
    assert result == ""


def test_augment_schema_empty_dir(tmp_path: Path) -> None:
    result = augment_schema(tmp_path, _make_enriched())
    assert result == ""


def test_augment_schema_full_integration(tmp_path: Path) -> None:
    # Create all three doc files
    (tmp_path / "schema.yml").write_text("""
models:
  - name: orders
    description: Sales orders.
    columns:
      - name: amount
        description: Deal value in USD
""")
    (tmp_path / "docs.md").write_text("# Extra docs\nSome context.\n")
    (tmp_path / "dictionary.csv").write_text("table,column,description\ncustomers,name,Full customer name\n")

    enriched = _make_enriched()
    result = augment_schema(tmp_path, enriched)

    assert "## Table: orders" in result
    assert "Deal value in USD" in result
    assert "## Table: customers" in result
    assert "Full customer name" in result
    assert "## Additional Documentation" in result
    assert "Extra docs" in result


def test_augment_schema_in_to_xml(tmp_path: Path) -> None:
    """Augmented docs appear in SchemaContext XML output."""
    from lumen.schema.context import SchemaContext, to_xml

    (tmp_path / "schema.yml").write_text("""
models:
  - name: orders
    description: Sales orders.
""")
    enriched = _make_enriched()
    docs = augment_schema(tmp_path, enriched)
    ctx = SchemaContext(enriched=enriched, augmented_docs=docs)
    xml = to_xml(ctx)
    assert "<augmented_docs>" in xml
    assert "Sales orders." in xml
