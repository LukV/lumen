"""SQL execution via asyncpg with timeout and row limits."""

from __future__ import annotations

import time

import asyncpg

from lumen.agent.cell import CellResult, compute_data_hash
from lumen.core import Diag, Result, Severity


async def execute_query(
    dsn: str,
    sql: str,
    *,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
) -> Result[CellResult]:
    """Execute a validated SQL query and return structured results.

    Connects to Postgres, sets statement_timeout, fetches up to max_rows+1
    to detect truncation, and builds a CellResult.
    """
    result: Result[CellResult] = Result()

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:  # noqa: BLE001
        result.error("SQL_ERROR", f"Connection failed: {e}")
        return result

    try:
        await conn.execute(f"SET statement_timeout = '{timeout_seconds * 1000}'")

        start = time.monotonic()
        rows = await conn.fetch(sql)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if len(rows) == 0:
            cell_result = CellResult(execution_time_ms=elapsed_ms)
            result.data = cell_result
            result.warning("EMPTY_RESULT", "Query returned no rows")
            return result

        # Detect truncation
        truncated = len(rows) > max_rows
        if truncated:
            rows = rows[:max_rows]

        # Build column info from first row
        columns = list(rows[0].keys())
        # Get types from the Record values
        column_types = [type(rows[0][col]).__name__ for col in columns]

        # Convert to list of dicts
        data: list[dict[str, object]] = [dict(r) for r in rows]

        cell_result = CellResult(
            columns=columns,
            column_types=column_types,
            row_count=len(data),
            data_hash=compute_data_hash(data),
            data=data,
            truncated=truncated,
            execution_time_ms=elapsed_ms,
        )

        if truncated:
            cell_result.diagnostics.append(
                Diag(
                    severity=Severity.WARNING,
                    code="RESULT_TRUNCATED",
                    message=f"Results truncated to {max_rows} rows",
                    hint="Add a LIMIT clause to your query",
                )
            )

        result.data = cell_result

    except asyncpg.exceptions.QueryCanceledError:
        result.error(
            "SQL_TIMEOUT",
            f"Query exceeded {timeout_seconds}s timeout",
            hint="Simplify the query or add filters",
        )
    except asyncpg.exceptions.PostgresError as e:
        hint = _suggest_fix(str(e))
        result.error("SQL_ERROR", f"SQL execution error: {e}", hint=hint)
    except Exception as e:  # noqa: BLE001
        result.error("SQL_ERROR", f"Unexpected error: {e}")
    finally:
        await conn.close()

    return result


def _suggest_fix(error_msg: str) -> str | None:
    """Generate a hint from common Postgres error messages."""
    lower = error_msg.lower()
    if "column" in lower and "does not exist" in lower:
        return "Check column names against the schema"
    if "relation" in lower and "does not exist" in lower:
        return "Check table names against the schema"
    if "syntax error" in lower:
        return "Check SQL syntax"
    if "permission denied" in lower:
        return "The database user lacks permissions for this operation"
    return None
