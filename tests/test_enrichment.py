"""Tests for schema enrichment / column role classification."""

from lumen.schema.enricher import enrich
from lumen.schema.introspector import ColumnSnapshot, SchemaSnapshot, TableSnapshot


def _col(
    name: str,
    data_type: str = "integer",
    *,
    is_primary_key: bool = False,
    foreign_key: str | None = None,
    distinct_estimate: int | None = None,
    sample_values: list[str] | None = None,
    min_value: str | None = None,
    max_value: str | None = None,
) -> ColumnSnapshot:
    return ColumnSnapshot(
        name=name,
        data_type=data_type,
        is_primary_key=is_primary_key,
        foreign_key=foreign_key,
        distinct_estimate=distinct_estimate,
        sample_values=sample_values or [],
        min_value=min_value,
        max_value=max_value,
    )


def _snapshot(tables: list[TableSnapshot]) -> SchemaSnapshot:
    return SchemaSnapshot(database="test", schema_name="public", tables=tables)


def test_primary_key_detection() -> None:
    table = TableSnapshot(
        name="users",
        row_count=1000,
        columns=[_col("id", "integer", is_primary_key=True)],
    )
    enriched = enrich(_snapshot([table]))
    assert enriched.tables[0].columns[0].role == "key"


def test_foreign_key_detection() -> None:
    table = TableSnapshot(
        name="orders",
        row_count=5000,
        columns=[_col("user_id", "integer", foreign_key="users.id")],
    )
    enriched = enrich(_snapshot([table]))
    assert enriched.tables[0].columns[0].role == "key"


def test_heuristic_key_detection() -> None:
    table = TableSnapshot(
        name="orders",
        row_count=1000,
        columns=[_col("order_id", "integer", distinct_estimate=990)],
    )
    enriched = enrich(_snapshot([table]))
    assert enriched.tables[0].columns[0].role == "key"


def test_time_dimension_date() -> None:
    table = TableSnapshot(
        name="events",
        row_count=100,
        columns=[_col("event_date", "date", min_value="2024-01-01", max_value="2025-12-31")],
    )
    enriched = enrich(_snapshot([table]))
    assert enriched.tables[0].columns[0].role == "time_dimension"


def test_time_dimension_timestamp() -> None:
    table = TableSnapshot(
        name="events",
        row_count=100,
        columns=[_col("created_at", "timestamp without time zone")],
    )
    enriched = enrich(_snapshot([table]))
    assert enriched.tables[0].columns[0].role == "time_dimension"


def test_categorical_boolean() -> None:
    table = TableSnapshot(
        name="users",
        row_count=100,
        columns=[_col("is_active", "boolean")],
    )
    enriched = enrich(_snapshot([table]))
    assert enriched.tables[0].columns[0].role == "categorical"


def test_categorical_low_cardinality_string() -> None:
    table = TableSnapshot(
        name="orders",
        row_count=5000,
        columns=[
            _col("status", "character varying", distinct_estimate=5, sample_values=["pending", "shipped", "delivered"]),
        ],
    )
    enriched = enrich(_snapshot([table]))
    assert enriched.tables[0].columns[0].role == "categorical"


def test_categorical_by_name_pattern() -> None:
    table = TableSnapshot(
        name="products",
        row_count=1000,
        columns=[_col("product_category", "text", distinct_estimate=300)],
    )
    enriched = enrich(_snapshot([table]))
    # _category matches _DIMENSION_PATTERNS
    assert enriched.tables[0].columns[0].role == "categorical"


def test_measure_candidate() -> None:
    table = TableSnapshot(
        name="orders",
        row_count=5000,
        columns=[_col("amount", "numeric", distinct_estimate=4500)],
    )
    enriched = enrich(_snapshot([table]))
    col = enriched.tables[0].columns[0]
    assert col.role == "measure_candidate"
    assert col.suggested_agg == "sum"


def test_measure_avg_suggestion() -> None:
    table = TableSnapshot(
        name="reviews",
        row_count=1000,
        columns=[_col("rating", "numeric", distinct_estimate=5)],
    )
    enriched = enrich(_snapshot([table]))
    col = enriched.tables[0].columns[0]
    assert col.role == "measure_candidate"
    assert col.suggested_agg == "avg"


def test_numeric_id_is_key() -> None:
    """Numeric columns ending in _id should be classified as keys, not measures."""
    table = TableSnapshot(
        name="orders",
        row_count=5000,
        columns=[_col("customer_id", "integer", distinct_estimate=100)],
    )
    enriched = enrich(_snapshot([table]))
    assert enriched.tables[0].columns[0].role == "key"


def test_full_table_enrichment() -> None:
    table = TableSnapshot(
        name="orders",
        row_count=10000,
        columns=[
            _col("id", "integer", is_primary_key=True),
            _col("created_at", "timestamp with time zone"),
            _col("customer_id", "integer", foreign_key="customers.id"),
            _col(
                "status",
                "character varying",
                distinct_estimate=4,
                sample_values=["pending", "active", "closed", "cancelled"],
            ),
            _col("amount", "numeric", distinct_estimate=8000),
            _col("is_refunded", "boolean"),
        ],
    )
    enriched = enrich(_snapshot([table]))
    roles = {c.name: c.role for c in enriched.tables[0].columns}

    assert roles["id"] == "key"
    assert roles["created_at"] == "time_dimension"
    assert roles["customer_id"] == "key"
    assert roles["status"] == "categorical"
    assert roles["amount"] == "measure_candidate"
    assert roles["is_refunded"] == "categorical"


def test_enrich_preserves_metadata() -> None:
    snapshot = SchemaSnapshot(
        database="mydb",
        schema_name="analytics",
        introspected_at="2026-01-01T00:00:00Z",
        tables=[],
    )
    enriched = enrich(snapshot)
    assert enriched.database == "mydb"
    assert enriched.schema_name == "analytics"
    assert enriched.introspected_at == "2026-01-01T00:00:00Z"
