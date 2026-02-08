"""Tests for Vega-Lite spec validation."""

from __future__ import annotations

from lumen.viz.validator import validate_chart_spec


def _good_spec() -> dict:
    return {
        "mark": {"type": "bar"},
        "encoding": {
            "x": {"field": "name", "type": "nominal"},
            "y": {"field": "revenue", "type": "quantitative"},
        },
        "width": "container",
    }


def test_valid_spec() -> None:
    result = validate_chart_spec(_good_spec(), ["name", "revenue"])
    assert result.ok
    assert result.data is not None
    assert result.data["mark"]["type"] == "bar"


def test_empty_spec() -> None:
    result = validate_chart_spec({}, ["a"])
    assert result.has_errors
    assert any("empty" in d.message.lower() for d in result.diagnostics)


def test_missing_mark() -> None:
    spec = {"encoding": {"x": {"field": "a", "type": "nominal"}}}
    result = validate_chart_spec(spec, ["a"])
    assert result.has_errors
    assert any("mark" in d.message.lower() for d in result.diagnostics)


def test_invalid_mark_type() -> None:
    spec = {"mark": {"type": "invalid_mark"}, "encoding": {"x": {"field": "a", "type": "nominal"}}}
    result = validate_chart_spec(spec, ["a"])
    assert result.has_errors
    assert any("invalid mark" in d.message.lower() for d in result.diagnostics)


def test_missing_encoding() -> None:
    spec = {"mark": "bar"}
    result = validate_chart_spec(spec, ["a"])
    assert result.has_errors
    assert any("encoding" in d.message.lower() for d in result.diagnostics)


def test_unknown_field() -> None:
    spec = {
        "mark": "bar",
        "encoding": {
            "x": {"field": "nonexistent", "type": "nominal"},
        },
    }
    result = validate_chart_spec(spec, ["name", "revenue"])
    assert result.has_errors
    assert any("nonexistent" in d.message for d in result.diagnostics)


def test_invalid_encoding_type() -> None:
    spec = {
        "mark": "bar",
        "encoding": {
            "x": {"field": "name", "type": "categorical"},  # wrong, should be nominal
        },
    }
    result = validate_chart_spec(spec, ["name"])
    assert result.has_errors
    assert any("categorical" in d.message for d in result.diagnostics)


def test_string_mark_accepted() -> None:
    spec = {
        "mark": "line",
        "encoding": {
            "x": {"field": "date", "type": "temporal"},
            "y": {"field": "value", "type": "quantitative"},
        },
    }
    result = validate_chart_spec(spec, ["date", "value"])
    assert result.ok


def test_empty_columns_skips_field_check() -> None:
    """When columns list is empty, field name check is skipped."""
    spec = {
        "mark": "bar",
        "encoding": {
            "x": {"field": "anything", "type": "nominal"},
        },
    }
    result = validate_chart_spec(spec, [])
    assert result.ok


def test_color_value_encoding_no_field() -> None:
    """Encoding with value instead of field should pass."""
    spec = {
        "mark": "bar",
        "encoding": {
            "x": {"field": "name", "type": "nominal"},
            "color": {"value": "#4A2D4F"},
        },
    }
    result = validate_chart_spec(spec, ["name"])
    assert result.ok
