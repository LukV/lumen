"""Tests for cell models."""

from lumen.agent.cell import (
    Cell,
    CellChart,
    CellNarrative,
    CellResult,
    CellSQL,
    DataReference,
    compute_data_hash,
    generate_cell_id,
)


def test_generate_cell_id_format() -> None:
    cid = generate_cell_id()
    assert cid.startswith("cell_")
    assert len(cid) == 13  # "cell_" + 8 hex


def test_generate_cell_id_unique() -> None:
    ids = {generate_cell_id() for _ in range(100)}
    assert len(ids) == 100


def test_compute_data_hash_deterministic() -> None:
    rows = [{"a": 1, "b": "hello"}, {"a": 2, "b": "world"}]
    h1 = compute_data_hash(rows)
    h2 = compute_data_hash(rows)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_data_hash_order_sensitive() -> None:
    rows_a = [{"a": 1}, {"a": 2}]
    rows_b = [{"a": 2}, {"a": 1}]
    assert compute_data_hash(rows_a) != compute_data_hash(rows_b)


def test_compute_data_hash_key_order_insensitive() -> None:
    """Keys within a dict are sorted by json.dumps(sort_keys=True)."""
    rows_a = [{"b": 2, "a": 1}]
    rows_b = [{"a": 1, "b": 2}]
    assert compute_data_hash(rows_a) == compute_data_hash(rows_b)


def test_cell_defaults() -> None:
    cell = Cell(question="test?")
    assert cell.id.startswith("cell_")
    assert cell.question == "test?"
    assert cell.sql is None
    assert cell.result is None
    assert cell.chart is None
    assert cell.narrative is None


def test_cell_full_construction() -> None:
    cell = Cell(
        question="top 10 customers?",
        sql=CellSQL(query="SELECT * FROM customers LIMIT 10"),
        result=CellResult(
            columns=["name", "revenue"],
            column_types=["text", "numeric"],
            row_count=10,
            data=[{"name": "Acme", "revenue": 1000}],
            execution_time_ms=42,
        ),
        chart=CellChart(spec={"mark": "bar"}, auto_detected=True),
        narrative=CellNarrative(
            text="Acme leads with $1000 in revenue.",
            data_references=[DataReference(ref_id="r1", text="$1000", source="revenue column")],
        ),
    )
    assert cell.sql is not None
    assert cell.sql.query == "SELECT * FROM customers LIMIT 10"
    assert cell.result is not None
    assert cell.result.row_count == 10
    assert cell.chart is not None
    assert cell.chart.auto_detected is True
    assert cell.narrative is not None
    assert len(cell.narrative.data_references) == 1


def test_cell_serialization_roundtrip() -> None:
    cell = Cell(
        question="test?",
        sql=CellSQL(query="SELECT 1"),
        result=CellResult(columns=["x"], column_types=["int"], row_count=1, data=[{"x": 1}]),
    )
    dumped = cell.model_dump()
    restored = Cell.model_validate(dumped)
    assert restored.question == cell.question
    assert restored.sql is not None
    assert restored.sql.query == "SELECT 1"
    assert restored.result is not None
    assert restored.result.data == [{"x": 1}]


def test_cell_json_roundtrip() -> None:
    cell = Cell(question="json test?")
    json_str = cell.model_dump_json()
    restored = Cell.model_validate_json(json_str)
    assert restored.id == cell.id
    assert restored.question == cell.question
