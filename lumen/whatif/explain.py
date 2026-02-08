"""Caveat generation — deterministic, technique-specific assumption statements."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def generate_caveats(technique: str, parameters: dict[str, Any]) -> list[str]:
    """Generate caveats for a what-if scenario. Pure function, no LLM."""
    generator = _CAVEAT_GENERATORS.get(technique, _unknown_caveats)
    return generator(parameters)


def _trend_extrapolation_caveats(parameters: dict[str, Any]) -> list[str]:
    periods = parameters.get("periods_ahead", 3)
    interval = parameters.get("period_interval", "month")
    return [
        f"Projects {periods} {interval}(s) ahead using linear regression on historical data.",
        "Assumes the historical trend continues unchanged — external shocks are not modeled.",
        "R-squared (R\u00b2) indicates fit quality: values below 0.5 suggest weak predictive power.",
        "Extrapolation beyond observed data ranges carries increasing uncertainty.",
    ]


def _unknown_caveats(parameters: dict[str, Any]) -> list[str]:
    return ["Unknown technique — no specific caveats available."]


_CAVEAT_GENERATORS: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "trend_extrapolation": _trend_extrapolation_caveats,
}
