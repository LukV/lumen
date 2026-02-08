"""Tests for trend chart builder."""

from __future__ import annotations

from lumen.whatif.chart import build_trend_chart


def test_trend_chart_has_two_layers() -> None:
    spec = build_trend_chart("month", "revenue")
    assert "layer" in spec
    assert len(spec["layer"]) == 2


def test_trend_chart_actuals_layer() -> None:
    spec = build_trend_chart("dt", "val")
    actuals = spec["layer"][0]
    assert actuals["mark"]["type"] == "line"
    assert actuals["encoding"]["x"]["field"] == "dt"
    assert actuals["encoding"]["y"]["field"] == "val"
    assert actuals["encoding"]["color"]["value"] == "#3b5998"
    # Actuals filter
    assert any("actual" in str(t.get("filter", "")) for t in actuals.get("transform", []))


def test_trend_chart_projections_layer() -> None:
    spec = build_trend_chart("dt", "val")
    proj = spec["layer"][1]
    assert proj["mark"]["type"] == "line"
    assert proj["mark"]["strokeDash"] == [6, 4]
    assert proj["encoding"]["color"]["value"] == "#c67a3c"
    # Projections filter
    assert any("projected" in str(t.get("filter", "")) for t in proj.get("transform", []))


def test_trend_chart_has_theme() -> None:
    spec = build_trend_chart("month", "revenue")
    assert "$schema" in spec
    assert "config" in spec


def test_trend_chart_dimensions() -> None:
    spec = build_trend_chart("month", "revenue")
    assert spec["width"] == "container"
    assert spec["height"] == 300
