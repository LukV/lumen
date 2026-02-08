"""Lumen Vega-Lite theme."""

from __future__ import annotations

from typing import Any

LUMEN_PALETTE = [
    "#4A2D4F",
    "#C2876E",
    "#6B8F8A",
    "#B8A44C",
    "#8C7B6B",
    "#A3667E",
]

LUMEN_THEME: dict[str, Any] = {
    "config": {
        "font": "DM Sans, system-ui, sans-serif",
        "axis": {
            "labelFont": "DM Sans, system-ui, sans-serif",
            "titleFont": "DM Sans, system-ui, sans-serif",
            "labelFontSize": 11,
            "titleFontSize": 12,
            "titleFontWeight": 600,
            "gridDash": [3, 3],
            "gridColor": "#E8E5DF",
            "domainColor": "#CCCAC5",
            "tickColor": "#CCCAC5",
            "labelLimit": 150,
            "titlePadding": 12,
        },
        "legend": {
            "labelFont": "DM Sans, system-ui, sans-serif",
            "titleFont": "DM Sans, system-ui, sans-serif",
            "labelFontSize": 11,
            "titleFontSize": 12,
        },
        "title": {
            "font": "DM Sans, system-ui, sans-serif",
            "fontSize": 14,
            "fontWeight": 600,
        },
        "bar": {
            "cornerRadiusEnd": 3,
        },
        "line": {
            "strokeWidth": 2,
            "point": {"size": 40},
        },
        "point": {
            "size": 60,
            "opacity": 0.7,
        },
        "area": {
            "opacity": 0.7,
            "line": True,
        },
        "range": {
            "category": LUMEN_PALETTE,
        },
        "view": {
            "strokeWidth": 0,
        },
        "padding": {"row": 10, "column": 10},
        "background": "transparent",
    },
}


def apply_theme(spec: dict[str, Any]) -> dict[str, Any]:
    """Merge the Lumen theme config into a Vega-Lite spec."""
    themed: dict[str, Any] = dict(spec)
    # Merge config
    existing_config: dict[str, Any] = dict(themed.get("config", {}))
    for key, value in LUMEN_THEME["config"].items():
        if key not in existing_config:
            existing_config[key] = value
        elif isinstance(value, dict) and isinstance(existing_config[key], dict):
            merged: dict[str, Any] = dict(value)
            merged.update(existing_config[key])
            existing_config[key] = merged
    themed["config"] = existing_config

    # Set $schema if not present
    if "$schema" not in themed:
        themed["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"

    return themed
