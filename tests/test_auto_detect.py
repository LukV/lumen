"""Tests for auto-detect chart type."""

from lumen.schema.enricher import EnrichedColumn, EnrichedSchema, EnrichedTable
from lumen.viz.auto_detect import auto_detect_chart


def _make_schema(columns: list[tuple[str, str, str]]) -> EnrichedSchema:
    """Helper to build an EnrichedSchema from (name, data_type, role) tuples."""
    enriched_cols = [EnrichedColumn(name=n, data_type=dt, role=r) for n, dt, r in columns]
    return EnrichedSchema(tables=[EnrichedTable(name="test", columns=enriched_cols)])


def test_time_plus_measure_gives_line() -> None:
    schema = _make_schema([("order_date", "date", "time_dimension"), ("revenue", "numeric", "measure_candidate")])
    spec = auto_detect_chart(["order_date", "revenue"], ["date", "float"], schema)
    assert spec["mark"]["type"] == "line"
    assert spec["encoding"]["x"]["field"] == "order_date"
    assert spec["encoding"]["y"]["field"] == "revenue"


def test_categorical_plus_measure_gives_bar() -> None:
    schema = _make_schema([("country", "varchar", "categorical"), ("sales", "numeric", "measure_candidate")])
    spec = auto_detect_chart(["country", "sales"], ["str", "float"], schema)
    assert spec["mark"]["type"] == "bar"
    assert spec["encoding"]["x"]["field"] == "country"
    assert spec["encoding"]["y"]["field"] == "sales"


def test_single_measure_gives_kpi() -> None:
    schema = _make_schema([("total", "numeric", "measure_candidate")])
    spec = auto_detect_chart(["total"], ["float"], schema)
    assert "mark" in spec
    assert "encoding" in spec


def test_two_numerics_gives_scatter() -> None:
    schema = _make_schema([("height", "numeric", "measure_candidate"), ("weight", "numeric", "measure_candidate")])
    spec = auto_detect_chart(["height", "weight"], ["float", "float"], schema)
    assert spec["mark"]["type"] == "point"


def test_fallback_gives_bar() -> None:
    schema = _make_schema([("name", "varchar", "other"), ("value", "numeric", "other")])
    spec = auto_detect_chart(["name", "value"], ["str", "int"], schema)
    assert "mark" in spec
    assert "encoding" in spec


def test_spec_has_theme_applied() -> None:
    schema = _make_schema([("x", "varchar", "categorical"), ("y", "numeric", "measure_candidate")])
    spec = auto_detect_chart(["x", "y"], ["str", "float"], schema)
    assert "$schema" in spec
    assert "config" in spec


def test_time_plus_two_measures_gives_stacked_area() -> None:
    schema = _make_schema([
        ("month", "date", "time_dimension"),
        ("revenue", "numeric", "measure_candidate"),
        ("cost", "numeric", "measure_candidate"),
    ])
    spec = auto_detect_chart(["month", "revenue", "cost"], ["date", "float", "float"], schema)
    assert spec["mark"]["type"] == "area"
    assert spec["encoding"]["x"]["field"] == "month"
    assert spec["encoding"]["color"]["field"] == "metric"
    assert "transform" in spec


def test_kpi_uses_text_mark() -> None:
    schema = _make_schema([("total", "numeric", "measure_candidate")])
    spec = auto_detect_chart(["total"], ["float"], schema)
    assert spec["mark"]["type"] == "text"
    assert spec["mark"]["fontSize"] == 48


def test_empty_schema_fallback() -> None:
    schema = EnrichedSchema()
    spec = auto_detect_chart(["a", "b"], ["str", "int"], schema)
    assert "mark" in spec
