"""Tests for schema context XML serialization and hashing."""

from lumen.schema.context import SchemaContext, compute_hash, to_xml
from lumen.schema.enricher import EnrichedColumn, EnrichedSchema, EnrichedTable


def _make_ctx() -> SchemaContext:
    schema = EnrichedSchema(
        database="analytics",
        schema_name="public",
        introspected_at="2026-02-06T14:00:00Z",
        tables=[
            EnrichedTable(
                name="orders",
                row_count=10000,
                comment="Sales orders",
                columns=[
                    EnrichedColumn(
                        name="id",
                        data_type="integer",
                        role="key",
                        is_primary_key=True,
                    ),
                    EnrichedColumn(
                        name="created_at",
                        data_type="timestamp with time zone",
                        role="time_dimension",
                        min_value="2024-01-01",
                        max_value="2026-01-31",
                    ),
                    EnrichedColumn(
                        name="status",
                        data_type="varchar",
                        role="categorical",
                        distinct_estimate=4,
                        sample_values=["pending", "active", "closed", "cancelled"],
                    ),
                    EnrichedColumn(
                        name="amount",
                        data_type="numeric",
                        role="measure_candidate",
                        suggested_agg="sum",
                        comment="Order total in USD",
                    ),
                    EnrichedColumn(
                        name="customer_id",
                        data_type="integer",
                        role="key",
                        foreign_key="customers.id",
                    ),
                ],
            ),
        ],
    )
    return SchemaContext(schema=schema)


def test_to_xml_structure() -> None:
    ctx = _make_ctx()
    xml = to_xml(ctx)

    assert xml.startswith('<schema database="analytics"')
    assert "</schema>" in xml
    assert '<table name="orders"' in xml
    assert 'rows="~10000"' in xml
    assert 'description="Sales orders"' in xml


def test_to_xml_column_attributes() -> None:
    ctx = _make_ctx()
    xml = to_xml(ctx)

    # PK column
    assert 'name="id"' in xml
    assert 'pk="true"' in xml

    # Time dimension with range
    assert 'role="time_dimension"' in xml
    assert 'range="2024-01-01 to 2026-01-31"' in xml

    # Categorical with sample values
    assert 'role="categorical"' in xml
    assert 'distinct_count="4"' in xml
    assert "values=" in xml

    # Measure candidate
    assert 'suggested_agg="sum"' in xml
    assert 'description="Order total in USD"' in xml

    # FK
    assert 'fk="customers.id"' in xml


def test_to_xml_no_role_for_other() -> None:
    """Columns with role='other' should not have a role attribute."""
    schema = EnrichedSchema(
        database="test",
        tables=[
            EnrichedTable(
                name="misc",
                columns=[EnrichedColumn(name="notes", data_type="text", role="other")],
            ),
        ],
    )
    ctx = SchemaContext(schema=schema)
    xml = to_xml(ctx)
    assert "role=" not in xml


def test_to_xml_augmented_docs() -> None:
    ctx = _make_ctx()
    ctx.augmented_docs = "Orders represent completed sales transactions."
    xml = to_xml(ctx)
    assert "<augmented_docs>" in xml
    assert "Orders represent completed sales transactions." in xml


def test_compute_hash_deterministic() -> None:
    ctx1 = _make_ctx()
    ctx2 = _make_ctx()

    h1 = compute_hash(ctx1)
    h2 = compute_hash(ctx2)

    assert h1 == h2
    assert h1.startswith("sha256:")
    assert len(h1) == 71  # "sha256:" + 64 hex chars


def test_compute_hash_changes_on_data_change() -> None:
    ctx1 = _make_ctx()
    ctx2 = _make_ctx()
    ctx2.enriched.tables[0].row_count = 99999

    assert compute_hash(ctx1) != compute_hash(ctx2)


def test_xml_escapes_special_chars() -> None:
    schema = EnrichedSchema(
        database="test&db",
        tables=[
            EnrichedTable(
                name="t&able",
                columns=[
                    EnrichedColumn(
                        name='col"name',
                        data_type="text",
                        comment="has <special> & chars",
                    ),
                ],
            ),
        ],
    )
    ctx = SchemaContext(schema=schema)
    xml = to_xml(ctx)
    assert "&amp;" in xml
    assert "&lt;special&gt;" in xml
