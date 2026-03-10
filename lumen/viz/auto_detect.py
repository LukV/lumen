"""Auto-detect the best Vega-Lite visualization from query result shape.

Adapted from DuckBook's auto.py. Instead of a semantic model, we use
EnrichedSchema to classify columns by role.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lumen.schema.enricher import EnrichedSchema
from lumen.viz.theme import LUMEN_PALETTE, apply_theme

if TYPE_CHECKING:
    from lumen.theme import ThemeConfig

_PRIMARY = LUMEN_PALETTE[0]


def auto_detect_chart(
    columns: list[str],
    column_types: list[str],
    enriched: EnrichedSchema,
    theme: ThemeConfig | None = None,
) -> dict[str, Any]:
    """Detect the best chart type and return a complete Vega-Lite spec.

    Rules (priority):
    1. No dims + measures → text/KPI (simple bar with single value)
    2. Time + measures → line
    3. 1 categorical + measures → bar
    4. 2 numerics → scatter
    5. Fallback → bar (first string-like col as x, first numeric as y)
    """
    # Build a role lookup from enriched schema
    role_map = _build_role_map(enriched)

    # Classify result columns
    time_cols: list[str] = []
    cat_cols: list[str] = []
    measure_cols: list[str] = []
    numeric_cols: list[str] = []

    for col, col_type in zip(columns, column_types, strict=True):
        role = role_map.get(col, _infer_role_from_type(col_type))

        if role == "time_dimension":
            time_cols.append(col)
        elif role == "categorical":
            cat_cols.append(col)
        elif role in ("measure_candidate", "numeric"):
            measure_cols.append(col)
            numeric_cols.append(col)
        elif role == "key":
            # Keys can act as categorical for display
            cat_cols.append(col)
        else:
            # Try to classify by Python type name
            if col_type in ("int", "float", "Decimal", "int64", "float64", "numeric"):
                numeric_cols.append(col)
                measure_cols.append(col)
            else:
                cat_cols.append(col)

    # Rule 0: Geographic key + measure → bubble map
    geo_col = _find_geo_column(columns, role_map)
    if geo_col and measure_cols:
        spec = _bubble_map_spec(geo_col, measure_cols[0])
        return apply_theme(spec, theme)

    # Rule 1: No dims + single measure → KPI
    if not time_cols and not cat_cols and len(measure_cols) == 1:
        spec = _kpi_spec(measure_cols[0])
        return apply_theme(spec, theme)

    # Rule 2a: Time + 2+ measures → stacked area (fold transform)
    if time_cols and len(measure_cols) >= 2:
        spec = _stacked_area_spec(time_cols[0], measure_cols)
        return apply_theme(spec, theme)

    # Rule 2b: Time + 1 measure → line
    if time_cols and measure_cols:
        spec = _line_spec(time_cols[0], measure_cols[0])
        return apply_theme(spec, theme)

    # Rule 3: 1 categorical + measures → bar
    if cat_cols and measure_cols:
        spec = _bar_spec(cat_cols[0], measure_cols[0])
        return apply_theme(spec, theme)

    # Rule 4: 2+ numerics (no dims) → scatter
    if len(numeric_cols) >= 2:
        spec = _scatter_spec(numeric_cols[0], numeric_cols[1])
        return apply_theme(spec, theme)

    # Fallback → bar with first two columns
    if len(columns) >= 2:
        spec = _bar_spec(columns[0], columns[1])
        return apply_theme(spec, theme)

    # Single column fallback
    if columns:
        spec = _kpi_spec(columns[0])
        return apply_theme(spec, theme)

    return apply_theme({"mark": "text", "encoding": {}})


def _build_role_map(enriched: EnrichedSchema) -> dict[str, str]:
    """Build a flat column_name → role mapping from all tables in the schema."""
    role_map: dict[str, str] = {}
    for table in enriched.tables:
        for col in table.columns:
            # Don't overwrite if we already have a role (ambiguous column names)
            if col.name not in role_map:
                role_map[col.name] = col.role
    return role_map


def _infer_role_from_type(col_type: str) -> str:
    """Infer a role from a Python type name when schema lookup fails."""
    lower = col_type.lower()
    if lower in ("date", "datetime", "timestamp"):
        return "time_dimension"
    if lower in ("int", "float", "decimal", "numeric", "int64", "float64"):
        return "numeric"
    if lower in ("str", "string", "text", "varchar"):
        return "categorical"
    if lower in ("bool", "boolean"):
        return "categorical"
    return "other"


def _bar_spec(x: str, y: str) -> dict[str, Any]:
    return {
        "mark": {"type": "bar", "cornerRadiusEnd": 3},
        "encoding": {
            "x": {"field": x, "type": "nominal", "sort": "-y"},
            "y": {"field": y, "type": "quantitative"},
            "color": {"value": _PRIMARY},
        },
        "width": "container",
        "height": 300,
    }


def _line_spec(x: str, y: str) -> dict[str, Any]:
    return {
        "mark": {"type": "line", "point": True},
        "encoding": {
            "x": {"field": x, "type": "temporal"},
            "y": {"field": y, "type": "quantitative"},
            "color": {"value": _PRIMARY},
        },
        "width": "container",
        "height": 300,
    }


def _scatter_spec(x: str, y: str) -> dict[str, Any]:
    return {
        "mark": {"type": "point", "filled": True},
        "encoding": {
            "x": {"field": x, "type": "quantitative"},
            "y": {"field": y, "type": "quantitative"},
            "color": {"value": _PRIMARY},
        },
        "width": "container",
        "height": 300,
    }


def _stacked_area_spec(time_col: str, measure_cols: list[str]) -> dict[str, Any]:
    return {
        "transform": [{"fold": measure_cols, "as": ["metric", "value"]}],
        "mark": {"type": "area", "opacity": 0.7, "line": True},
        "encoding": {
            "x": {"field": time_col, "type": "temporal"},
            "y": {"field": "value", "type": "quantitative", "stack": "zero"},
            "color": {"field": "metric", "type": "nominal"},
        },
        "width": "container",
        "height": 300,
    }


_GEO_COLUMN_NAMES = frozenset({"nis", "nis_code", "gemeente_code", "geo_code"})


def _find_geo_column(columns: list[str], role_map: dict[str, str]) -> str | None:
    """Detect a geographic key column by name or role."""
    for col in columns:
        if role_map.get(col) == "geographic_key":
            return col
        if col.lower() in _GEO_COLUMN_NAMES:
            return col
    return None


def _bubble_map_spec(geo_col: str, measure_col: str) -> dict[str, Any]:
    return {
        "width": "container",
        "height": 450,
        "projection": {"type": "mercator"},
        "layer": [
            {
                "data": {"url": "/geo/vlaanderen-gemeenten.json"},
                "mark": {"type": "circle", "color": "#ddd", "size": 8, "opacity": 0.4},
                "encoding": {
                    "latitude": {"field": "lat", "type": "quantitative"},
                    "longitude": {"field": "lon", "type": "quantitative"},
                },
            },
            {
                "mark": {"type": "circle", "opacity": 0.75},
                "transform": [
                    {
                        "lookup": geo_col,
                        "from": {
                            "data": {"url": "/geo/vlaanderen-gemeenten.json"},
                            "key": "nis",
                            "fields": ["lat", "lon", "gemeente"],
                        },
                    },
                ],
                "encoding": {
                    "latitude": {"field": "lat", "type": "quantitative"},
                    "longitude": {"field": "lon", "type": "quantitative"},
                    "size": {
                        "field": measure_col,
                        "type": "quantitative",
                        "scale": {"range": [20, 800]},
                        "legend": {"title": measure_col},
                    },
                    "color": {
                        "field": measure_col,
                        "type": "quantitative",
                        "scale": {"scheme": "teals"},
                    },
                    "tooltip": [
                        {"field": "gemeente", "title": "Gemeente"},
                        {"field": measure_col, "type": "quantitative", "format": ","},
                    ],
                },
            },
        ],
    }


def _kpi_spec(field: str) -> dict[str, Any]:
    return {
        "mark": {
            "type": "text",
            "fontSize": 48,
            "fontWeight": 700,
            "color": _PRIMARY,
        },
        "encoding": {
            "text": {"field": field, "type": "quantitative", "format": ",.2~f"},
        },
        "width": "container",
        "height": 80,
    }
