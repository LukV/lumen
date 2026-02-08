"""Layered chart builder for trend extrapolation — solid actuals + dashed projections."""

from __future__ import annotations

from typing import Any

from lumen.viz.theme import apply_theme


def build_trend_chart(time_field: str, measure: str) -> dict[str, Any]:
    """Build a layered Vega-Lite spec: solid actuals + dashed projections.

    Layer 1: solid line + points for actuals (period_type === 'actual')
    Layer 2: dashed line + diamond points for projections (period_type === 'projected')
    """
    spec: dict[str, Any] = {
        "layer": [
            # Actuals: solid line + circle points
            {
                "transform": [{"filter": "datum.period_type === 'actual'"}],
                "mark": {"type": "line", "point": {"shape": "circle", "size": 40}, "strokeWidth": 2},
                "encoding": {
                    "x": {"field": time_field, "type": "temporal"},
                    "y": {"field": measure, "type": "quantitative"},
                    "color": {"value": "#3b5998"},
                },
            },
            # Projections: dashed line + diamond points
            {
                "transform": [{"filter": "datum.period_type === 'projected'"}],
                "mark": {
                    "type": "line",
                    "point": {"shape": "diamond", "size": 50},
                    "strokeWidth": 2,
                    "strokeDash": [6, 4],
                },
                "encoding": {
                    "x": {"field": time_field, "type": "temporal"},
                    "y": {"field": measure, "type": "quantitative"},
                    "color": {"value": "#c67a3c"},
                },
            },
        ],
        "width": "container",
        "height": 300,
    }

    return apply_theme(spec)
