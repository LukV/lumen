"""Tests for caveat generation."""

from __future__ import annotations

from lumen.whatif.explain import generate_caveats


def test_trend_extrapolation_caveats() -> None:
    caveats = generate_caveats("trend_extrapolation", {"periods_ahead": 6, "period_interval": "month"})
    assert len(caveats) == 4
    assert any("6 month" in c for c in caveats)
    assert any("linear regression" in c for c in caveats)
    assert any("R-squared" in c or "R\u00b2" in c for c in caveats)
    assert any("uncertainty" in c for c in caveats)


def test_trend_caveats_defaults() -> None:
    caveats = generate_caveats("trend_extrapolation", {})
    assert len(caveats) == 4
    assert any("3 month" in c for c in caveats)


def test_unknown_technique_caveats() -> None:
    caveats = generate_caveats("nonexistent_technique", {})
    assert len(caveats) == 1
    assert "Unknown technique" in caveats[0]
