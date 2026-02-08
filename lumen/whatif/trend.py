"""Trend extrapolation — wraps baseline SQL with Postgres linear regression + future periods."""

from __future__ import annotations

from pydantic import BaseModel, Field

from lumen.core import Result

_VALID_INTERVALS = frozenset({"day", "week", "month", "quarter", "year"})
_MAX_PERIODS = 24


class TrendParams(BaseModel):
    time_field: str
    measure: str
    periods_ahead: int = Field(default=3, ge=1, le=_MAX_PERIODS)
    period_interval: str = "month"


class TrendSQL(BaseModel):
    sql: str
    baseline_sql: str
    time_field: str
    measure: str
    periods_ahead: int
    period_interval: str


def build_trend_sql(baseline_sql: str, *, params: TrendParams) -> Result[TrendSQL]:
    """Wrap baseline SQL with linear regression and future period projection.

    Uses Postgres regr_slope()/regr_intercept()/regr_r2() with EXTRACT(EPOCH FROM ...)
    for numeric time axis. Produces UNION ALL of actuals + bridge + future_periods.
    """
    result: Result[TrendSQL] = Result()

    interval = params.period_interval
    if interval not in _VALID_INTERVALS:
        result.error(
            "TREND_INVALID_INTERVAL",
            f"Invalid period_interval '{interval}'",
            hint=f"Must be one of: {', '.join(sorted(_VALID_INTERVALS))}",
        )
        return result

    periods = params.periods_ahead
    if periods < 1 or periods > _MAX_PERIODS:
        result.error(
            "TREND_INVALID_PERIODS",
            f"periods_ahead must be 1-{_MAX_PERIODS}, got {periods}",
        )
        return result

    time_col = params.time_field
    measure_col = params.measure

    # Epoch expression for Postgres (seconds → days for numeric stability)
    epoch_expr = f'EXTRACT(EPOCH FROM "{time_col}"::timestamp) / 86400.0'
    m_cast = f'"{measure_col}"::double precision'

    future_ts = f"lp.max_time + (gs.n * INTERVAL '1 {interval}')"
    future_epoch = f"EXTRACT(EPOCH FROM ({future_ts})::timestamp) / 86400.0"
    bridge_epoch = "EXTRACT(EPOCH FROM lp.max_time::timestamp) / 86400.0"

    sql = (
        f"WITH baseline AS (SELECT * FROM ({baseline_sql}) AS _b),\n"
        f"regression AS (\n"
        f"  SELECT\n"
        f"    regr_slope({m_cast}, {epoch_expr}) AS slope,\n"
        f"    regr_intercept({m_cast}, {epoch_expr}) AS intercept,\n"
        f"    regr_r2({m_cast}, {epoch_expr}) AS r_squared,\n"
        f"    COUNT(*) AS n_points\n"
        f"  FROM baseline\n"
        f'  WHERE "{measure_col}" IS NOT NULL AND "{time_col}" IS NOT NULL\n'
        f"),\n"
        f"actuals AS (\n"
        f"  SELECT\n"
        f'    "{time_col}",\n'
        f'    "{measure_col}",\n'
        f"    'actual' AS period_type\n"
        f"  FROM baseline\n"
        f"),\n"
        f"last_period AS (\n"
        f'  SELECT MAX("{time_col}"::timestamp) AS max_time FROM baseline\n'
        f"),\n"
        f"bridge AS (\n"
        f"  SELECT\n"
        f'    lp.max_time AS "{time_col}",\n'
        f'    r.slope * ({bridge_epoch}) + r.intercept AS "{measure_col}",\n'
        f"    'projected' AS period_type\n"
        f"  FROM last_period lp\n"
        f"  CROSS JOIN regression r\n"
        f"  WHERE lp.max_time IS NOT NULL\n"
        f"),\n"
        f"future_periods AS (\n"
        f"  SELECT\n"
        f'    ({future_ts})::timestamp AS "{time_col}",\n'
        f'    r.slope * ({future_epoch}) + r.intercept AS "{measure_col}",\n'
        f"    'projected' AS period_type\n"
        f"  FROM generate_series(1, {periods}) AS gs(n)\n"
        f"  CROSS JOIN regression r\n"
        f"  CROSS JOIN last_period lp\n"
        f")\n"
        f"SELECT * FROM actuals\n"
        f"UNION ALL\n"
        f"SELECT * FROM bridge\n"
        f"UNION ALL\n"
        f"SELECT * FROM future_periods\n"
        f'ORDER BY "{time_col}"'
    )

    result.data = TrendSQL(
        sql=sql,
        baseline_sql=baseline_sql,
        time_field=time_col,
        measure=measure_col,
        periods_ahead=periods,
        period_interval=interval,
    )
    return result
