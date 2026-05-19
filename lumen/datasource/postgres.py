"""PostgreSQL data source — wraps introspector, executor, and SQL validator."""

from __future__ import annotations

import asyncpg

from lumen.agent.executor import execute_query
from lumen.agent.sql_validator import validate_sql as _validate_sql
from lumen.cell import CellResult
from lumen.core import Result
from lumen.schema.introspector import SchemaSnapshot, introspect


class PostgresSource:
    """DataSource implementation for PostgreSQL via asyncpg + pglast."""

    def __init__(self, dsn: str, schema_name: str = "public", pool: asyncpg.Pool | None = None) -> None:
        self._dsn = dsn
        self._schema_name = schema_name
        self._pool = pool

    @property
    def dialect(self) -> str:
        return "postgresql"

    async def introspect(self) -> Result[SchemaSnapshot]:
        return await introspect(self._dsn, self._schema_name)

    async def execute(self, sql: str, *, timeout_seconds: int = 30, max_rows: int = 1000) -> Result[CellResult]:
        conn_source: str | asyncpg.Pool = self._pool if self._pool is not None else self._dsn
        return await execute_query(conn_source, sql, timeout_seconds=timeout_seconds, max_rows=max_rows)

    def validate_sql(self, sql: str) -> Result[str]:
        return _validate_sql(sql)

    async def ping(self) -> Result[bool]:
        result: Result[bool] = Result()
        try:
            if self._pool is not None:
                async with self._pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
            else:
                conn = await asyncpg.connect(self._dsn, timeout=2)
                try:
                    await conn.fetchval("SELECT 1")
                finally:
                    await conn.close()
            result.data = True
        except Exception as e:  # noqa: BLE001
            result.error("PING_FAILED", f"Database unreachable: {e}")
        return result

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
