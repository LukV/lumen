"""DataSource protocol — the abstraction boundary for database backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from lumen.cell import CellResult
from lumen.core import Result
from lumen.schema.introspector import SchemaSnapshot


@runtime_checkable
class DataSource(Protocol):
    """Interface for database backends (Postgres, DuckDB, etc.)."""

    @property
    def dialect(self) -> str:
        """SQL dialect identifier: 'postgresql', 'duckdb', etc."""
        ...

    async def introspect(self) -> Result[SchemaSnapshot]:
        """Return table/column metadata for the configured schema."""
        ...

    async def execute(self, sql: str, *, timeout_seconds: int = 30, max_rows: int = 1000) -> Result[CellResult]:
        """Execute a SELECT query and return structured results."""
        ...

    def validate_sql(self, sql: str) -> Result[str]:
        """Validate SQL syntax and safety (read-only enforcement)."""
        ...

    async def ping(self) -> Result[bool]:
        """Verify the data source is reachable. Returns Result with True on success."""
        ...

    async def close(self) -> None:
        """Release resources."""
        ...
