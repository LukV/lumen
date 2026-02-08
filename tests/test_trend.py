"""Tests for trend extrapolation SQL builder."""

from __future__ import annotations

from lumen.whatif.trend import TrendParams, build_trend_sql


def test_basic_trend_sql() -> None:
    params = TrendParams(time_field="order_month", measure="revenue")
    result = build_trend_sql("SELECT order_month, revenue FROM orders GROUP BY 1", params=params)
    assert result.ok
    assert result.data is not None
    sql = result.data.sql
    assert "regr_slope" in sql
    assert "regr_intercept" in sql
    assert "regr_r2" in sql
    assert "EXTRACT(EPOCH FROM" in sql
    assert "'actual'" in sql
    assert "'projected'" in sql
    assert "UNION ALL" in sql
    assert "generate_series(1, 3)" in sql


def test_trend_sql_fields() -> None:
    params = TrendParams(time_field="month", measure="sales", periods_ahead=6, period_interval="week")
    result = build_trend_sql("SELECT month, sales FROM t", params=params)
    assert result.ok
    data = result.data
    assert data is not None
    assert data.time_field == "month"
    assert data.measure == "sales"
    assert data.periods_ahead == 6
    assert data.period_interval == "week"
    assert data.baseline_sql == "SELECT month, sales FROM t"


def test_trend_sql_wraps_baseline_as_subquery() -> None:
    """Baseline with CTEs should be wrapped as subquery to avoid CTE conflicts."""
    baseline = "WITH cte AS (SELECT 1) SELECT * FROM cte"
    params = TrendParams(time_field="dt", measure="val")
    result = build_trend_sql(baseline, params=params)
    assert result.ok
    assert result.data is not None
    # baseline is wrapped in: SELECT * FROM (...) AS _b
    assert "AS _b" in result.data.sql


def test_trend_sql_invalid_interval() -> None:
    params = TrendParams(time_field="dt", measure="val", period_interval="decade")
    result = build_trend_sql("SELECT dt, val FROM t", params=params)
    assert result.has_errors
    assert any("decade" in d.message for d in result.diagnostics)


def test_trend_sql_all_valid_intervals() -> None:
    for interval in ("day", "week", "month", "quarter", "year"):
        params = TrendParams(time_field="dt", measure="val", period_interval=interval)
        result = build_trend_sql("SELECT dt, val FROM t", params=params)
        assert result.ok, f"Interval '{interval}' should be valid"
        assert f"INTERVAL '1 {interval}'" in result.data.sql  # type: ignore[union-attr]


def test_trend_sql_custom_periods() -> None:
    params = TrendParams(time_field="dt", measure="val", periods_ahead=12)
    result = build_trend_sql("SELECT dt, val FROM t", params=params)
    assert result.ok
    assert result.data is not None
    assert "generate_series(1, 12)" in result.data.sql


def test_trend_sql_bridge_cte() -> None:
    """Bridge CTE should connect actuals to projections for visual continuity."""
    params = TrendParams(time_field="dt", measure="val")
    result = build_trend_sql("SELECT dt, val FROM t", params=params)
    assert result.ok
    assert result.data is not None
    assert "bridge AS" in result.data.sql


def test_trend_sql_includes_order_by() -> None:
    params = TrendParams(time_field="month", measure="revenue")
    result = build_trend_sql("SELECT month, revenue FROM t", params=params)
    assert result.ok
    assert result.data is not None
    assert 'ORDER BY "month"' in result.data.sql
