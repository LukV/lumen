"""Structural Vega-Lite spec validation."""

from __future__ import annotations

from typing import Any

from lumen.core import Result

_VALID_MARK_TYPES = frozenset({"bar", "line", "point", "area", "rect", "text", "arc", "circle", "square", "tick"})
_VALID_ENCODING_TYPES = frozenset({"nominal", "ordinal", "quantitative", "temporal"})


def validate_chart_spec(spec: dict[str, Any], columns: list[str]) -> Result[dict[str, Any]]:
    """Validate a Vega-Lite spec structurally against result columns.

    Checks mark type, encoding presence, field name validity, and encoding types.
    Returns the spec on success, diagnostics on failure.
    """
    result: Result[dict[str, Any]] = Result()

    if not spec:
        result.error("CHART_EMPTY", "Chart spec is empty")
        return result

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

    # Validate encoded fields and types
    col_set = set(columns)
    for channel, enc_def in encoding.items():
        if not isinstance(enc_def, dict):
            continue
        field = enc_def.get("field")
        if field and col_set and field not in col_set:
            result.error("CHART_UNKNOWN_FIELD", f"Field '{field}' in {channel} not in result columns: {columns}")
        enc_type = enc_def.get("type")
        if enc_type and enc_type not in _VALID_ENCODING_TYPES:
            result.error("CHART_INVALID_TYPE", f"Invalid encoding type '{enc_type}' in {channel}")

    if result.ok:
        result.data = spec

    return result
