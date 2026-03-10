"""Structural Vega-Lite spec validation."""

from __future__ import annotations

from typing import Any

from lumen.core import Result

_VALID_MARK_TYPES = frozenset(
    {"bar", "line", "point", "area", "rect", "text", "arc", "circle", "square", "tick", "geoshape"}
)
_VALID_ENCODING_TYPES = frozenset({"nominal", "ordinal", "quantitative", "temporal"})


def validate_chart_spec(spec: dict[str, Any], columns: list[str]) -> Result[dict[str, Any]]:
    """Validate a Vega-Lite spec structurally against result columns.

    Checks mark type, encoding presence, field name validity, and encoding types.
    Supports layered specs: if spec has 'layer', validates each layer independently.
    Returns the spec on success, diagnostics on failure.
    """
    result: Result[dict[str, Any]] = Result()

    if not spec:
        result.error("CHART_EMPTY", "Chart spec is empty")
        return result

    # Layered spec: validate each layer independently
    layers = spec.get("layer")
    if isinstance(layers, list):
        for i, layer in enumerate(layers):
            if not isinstance(layer, dict):
                result.error("CHART_INVALID_LAYER", f"Layer {i} must be an object")
                continue
            layer_result = _validate_single_spec(layer, columns)
            for diag in layer_result.diagnostics:
                result.diagnostics.append(diag)
        if result.ok:
            result.data = spec
        return result

    # Single spec
    single_result = _validate_single_spec(spec, columns)
    result.diagnostics = single_result.diagnostics
    if result.ok:
        result.data = spec
    return result


def _validate_single_spec(spec: dict[str, Any], columns: list[str]) -> Result[dict[str, Any]]:
    """Validate a single (non-layered) Vega-Lite spec."""
    result: Result[dict[str, Any]] = Result()

    # Check mark
    mark = spec.get("mark")
    if mark is None:
        result.error("CHART_NO_MARK", "Chart spec missing 'mark'")
    else:
        mark_type = mark if isinstance(mark, str) else mark.get("type") if isinstance(mark, dict) else None
        if mark_type and mark_type not in _VALID_MARK_TYPES:
            result.error("CHART_INVALID_MARK", f"Invalid mark type: {mark_type}")

    # Check encoding
    encoding = spec.get("encoding")
    if encoding is None:
        result.error("CHART_NO_ENCODING", "Chart spec missing 'encoding'")
        return result

    if not isinstance(encoding, dict):
        result.error("CHART_INVALID_ENCODING", "Encoding must be an object")
        return result

    # Check for lookup transform (map specs join external geo data)
    has_geo_lookup = _has_geo_lookup(spec)

    # Validate encoded fields and types
    col_set = set(columns)
    for channel, enc_def in encoding.items():
        if not isinstance(enc_def, dict):
            continue
        field = enc_def.get("field")
        if field and col_set and field not in col_set:
            # Skip field validation for geo lookup fields (lat, lon, gemeente come from external data)
            if has_geo_lookup and field in ("lat", "lon", "gemeente", "properties.naam", "properties.nis"):
                continue
            result.error("CHART_UNKNOWN_FIELD", f"Field '{field}' in {channel} not in result columns: {columns}")
        enc_type = enc_def.get("type")
        if enc_type and enc_type not in _VALID_ENCODING_TYPES:
            result.error("CHART_INVALID_TYPE", f"Invalid encoding type '{enc_type}' in {channel}")

    return result


def _has_geo_lookup(spec: dict[str, Any]) -> bool:
    """Check if a spec uses a geographic lookup transform."""
    transforms = spec.get("transform", [])
    if isinstance(transforms, list):
        for tr in transforms:
            if isinstance(tr, dict) and "lookup" in tr:
                from_data = tr.get("from", {})
                if isinstance(from_data, dict):
                    data = from_data.get("data", {})
                    if isinstance(data, dict) and isinstance(data.get("url"), str) and "/geo/" in data["url"]:
                        return True
    return False
