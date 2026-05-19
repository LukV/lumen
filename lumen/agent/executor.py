"""SQL execution via asyncpg with timeout and row limits."""

from __future__ import annotations

import logging
import time

import asyncpg

from lumen.cell import CellResult, compute_data_hash
from lumen.core import Diag, Result, Severity

logger = logging.getLogger("lumen.executor")

_PG_OID_TYPE_NAMES: dict[int, str] = {
    16: "boolean",
    20: "bigint",
    21: "smallint",
    23: "integer",
    25: "text",
    700: "real",
    701: "double precision",
    1043: "character varying",
    1082: "date",
    1114: "timestamp without time zone",
    1184: "timestamp with time zone",
    1700: "numeric",
    2950: "uuid",
}


def pg_type_from_oid(oid: int) -> str:
    """Map a Postgres OID to a canonical type name, falling back to 'text'."""
    return _PG_OID_TYPE_NAMES.get(oid, "text")


async def execute_query(
    conn_source: str | asyncpg.Pool,
    sql: str,
    *,
    timeout_seconds: int = 30,
    max_rows: int = 1000,
) -> Result[CellResult]:
    """Execute a validated SQL query and return structured results.

    conn_source can be a DSN string (creates a one-off connection) or an
    asyncpg.Pool (acquires and releases a connection from the pool).
    """
    result: Result[CellResult] = Result()

    # Acquire connection from pool or create a new one
    pool_mode = isinstance(conn_source, asyncpg.Pool)
    conn: asyncpg.Connection | None = None
    try:
        if pool_mode:
            conn = await conn_source.acquire()  # type: ignore[union-attr]
        else:
            conn = await asyncpg.connect(conn_source)
    except Exception as e:  # noqa: BLE001
        result.error("SQL_ERROR", f"Connection failed: {e}")
        return result

    try:
        await conn.execute(f"SET statement_timeout = '{timeout_seconds * 1000}'")

        start = time.monotonic()
        wrapped_sql = f"SELECT * FROM ({sql}) AS _lumen_q LIMIT {max_rows + 1}"
        stmt = await conn.prepare(wrapped_sql)
        # No positional args: PreparedStatement.fetch(*args) treats them as
        # query parameters ($1, $2, ...), not a row limit. The cap is in LIMIT.
        rows = await stmt.fetch()
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

        # Build column info from prepared statement attributes
        attrs = stmt.get_attributes()
        columns = [a.name for a in attrs]
        column_types = [pg_type_from_oid(a.type.oid) for a in attrs]

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
    except asyncpg.exceptions.InterfaceError as e:
        logger.exception("asyncpg InterfaceError during execute_query")
        result.error(
            "SQL_INTERNAL",
            f"Database driver misuse: {e}",
            hint="This is a Lumen bug, not a query issue. See server log for traceback.",
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Unexpected error during execute_query")
        result.error("SQL_ERROR", f"Unexpected error: {e}")
    finally:
        if conn is not None:
            if pool_mode:
                await conn_source.release(conn)  # type: ignore[union-attr]
            else:
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
