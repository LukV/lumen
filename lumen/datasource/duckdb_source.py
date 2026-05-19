"""DuckDB data source for Parquet files."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from lumen.cell import CellResult, compute_data_hash
from lumen.core import Diag, Result, Severity
from lumen.schema.introspector import ColumnSnapshot, SchemaSnapshot, TableSnapshot

logger = logging.getLogger(__name__)

_LOW_CARDINALITY_MAX = 50
_SAMPLE_VALUES_LIMIT = 20


class DuckDBSource:
    """DataSource implementation for Parquet files via in-process DuckDB."""

    def __init__(self, parquet_path: str) -> None:
        self._path = Path(parquet_path).resolve()
        self._conn = duckdb.connect(database=":memory:")
        self._views = self._register_views()
        logger.info("DuckDB source: %d views from %s", len(self._views), self._path)

    @property
    def dialect(self) -> str:
        return "duckdb"

    def _register_views(self) -> list[str]:
        """Scan parquet_path for .parquet files and create DuckDB views."""
        views: list[str] = []
        if not self._path.is_dir():
            logger.warning("Parquet path does not exist or is not a directory: %s", self._path)
            return views

        for pf in sorted(self._path.glob("*.parquet")):
            table_name = pf.stem.lower().replace("-", "_").replace(" ", "_")
            escaped_path = str(pf).replace("'", "''")
            self._conn.execute(f"CREATE OR REPLACE VIEW {table_name} AS SELECT * FROM read_parquet('{escaped_path}')")
            views.append(table_name)

        return views

    async def introspect(self) -> Result[SchemaSnapshot]:
        """Introspect DuckDB views and return schema metadata."""
        return await asyncio.to_thread(self._introspect_sync)

    def _introspect_sync(self) -> Result[SchemaSnapshot]:
        result: Result[SchemaSnapshot] = Result()
        try:
            tables: list[TableSnapshot] = []
            for view_name in self._views:
                table = self._introspect_table(view_name)
                tables.append(table)

            snapshot = SchemaSnapshot(
                database=self._path.name,
                schema_name="main",
                introspected_at=datetime.now(UTC).isoformat(),
                tables=tables,
            )
            result.data = snapshot
        except duckdb.Error as e:
            result.error("INTROSPECTION_ERROR", f"DuckDB introspection failed: {e}")
        return result

    def _introspect_table(self, table_name: str) -> TableSnapshot:
        # Column metadata from information_schema
        cols_raw = self._conn.execute(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position",
            [table_name],
        ).fetchall()

        # Row count (fast — reads Parquet metadata)
        row_count = self._conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]  # type: ignore[index]

        columns: list[ColumnSnapshot] = []
        for col_name, data_type, is_nullable in cols_raw:
            col = ColumnSnapshot(
                name=col_name,
                data_type=data_type.lower(),
                is_nullable=is_nullable == "YES",
            )

            # Distinct estimate
            try:
                dc = self._conn.execute(f'SELECT APPROX_COUNT_DISTINCT("{col_name}") FROM {table_name}').fetchone()
                if dc:
                    col.distinct_estimate = int(dc[0])
            except duckdb.Error:
                pass

            # Sample values for low-cardinality string columns
            if col.distinct_estimate is not None and col.distinct_estimate <= _LOW_CARDINALITY_MAX:
                lower_type = data_type.lower()
                if "varchar" in lower_type or "text" in lower_type or "char" in lower_type:
                    try:
                        samples = self._conn.execute(
                            f'SELECT DISTINCT "{col_name}" FROM {table_name} '
                            f'WHERE "{col_name}" IS NOT NULL LIMIT {_SAMPLE_VALUES_LIMIT}'
                        ).fetchall()
                        col.sample_values = [str(r[0]) for r in samples]
                    except duckdb.Error:
                        pass

            # Min/max for numeric and date columns
            lower_type = data_type.lower()
            is_numeric = any(t in lower_type for t in ("int", "float", "double", "numeric", "decimal", "real"))
            is_temporal = any(t in lower_type for t in ("date", "timestamp", "time"))
            if is_numeric or is_temporal:
                try:
                    minmax = self._conn.execute(
                        f'SELECT MIN("{col_name}"), MAX("{col_name}") FROM {table_name}'
                    ).fetchone()
                    if minmax and minmax[0] is not None:
                        col.min_value = str(minmax[0])
                        col.max_value = str(minmax[1])
                except duckdb.Error:
                    pass

            columns.append(col)

        return TableSnapshot(name=table_name, row_count=row_count, columns=columns)

    async def execute(self, sql: str, *, timeout_seconds: int = 30, max_rows: int = 1000) -> Result[CellResult]:
        """Execute SQL against DuckDB views."""
        return await asyncio.to_thread(self._execute_sync, sql, timeout_seconds, max_rows)

    def _execute_sync(self, sql: str, timeout_seconds: int, max_rows: int) -> Result[CellResult]:
        result: Result[CellResult] = Result()
        try:
            start = time.monotonic()
            wrapped = f"SELECT * FROM ({sql}) AS _lumen_q LIMIT {max_rows + 1}"
            rel = self._conn.execute(wrapped)
            columns = [desc[0] for desc in rel.description]
            rows_raw = rel.fetchall()
            elapsed_ms = int((time.monotonic() - start) * 1000)

            if len(rows_raw) == 0:
                cell_result = CellResult(execution_time_ms=elapsed_ms)
                result.data = cell_result
                result.warning("EMPTY_RESULT", "Query returned no rows")
                return result

            truncated = len(rows_raw) > max_rows
            if truncated:
                rows_raw = rows_raw[:max_rows]

            # Get column types from description
            column_types = [str(desc[1]).lower() if len(desc) > 1 and desc[1] else "text" for desc in rel.description]

            # Convert to list of dicts
            data: list[dict[str, object]] = [dict(zip(columns, row, strict=True)) for row in rows_raw]

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

        except duckdb.Error as e:
            result.error("SQL_ERROR", f"DuckDB execution error: {e}", hint=_suggest_fix(str(e)))

        return result

    def validate_sql(self, sql: str) -> Result[str]:
        """Validate SQL via prefix check + DuckDB EXPLAIN."""
        result: Result[str] = Result(data=sql)

        stripped = sql.strip()
        upper = stripped.upper()
        if not upper.startswith(("SELECT", "WITH")):
            result.error("VALIDATION_ERROR", "Only SELECT statements are permitted.")
            return result

        try:
            self._conn.execute(f"EXPLAIN {stripped}")
        except duckdb.Error as e:
            result.error("SQL_PARSE_ERROR", f"SQL validation failed: {e}", hint="Check the query for syntax errors.")

        return result

    async def ping(self) -> Result[bool]:
        result: Result[bool] = Result()
        try:
            self._conn.execute("SELECT 1").fetchone()
            result.data = True
        except duckdb.Error as e:
            result.error("PING_FAILED", f"DuckDB unreachable: {e}")
        return result

    async def close(self) -> None:
        """Close the DuckDB connection."""
        with contextlib.suppress(duckdb.Error):
            self._conn.close()


def _suggest_fix(error_msg: str) -> str | None:
    lower = error_msg.lower()
    if "column" in lower and "not found" in lower:
        return "Check column names against the schema"
    if "table" in lower and "not found" in lower:
        return "Check table names against the schema"
    if "syntax error" in lower:
        return "Check SQL syntax"
    return None
