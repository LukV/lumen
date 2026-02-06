"""Postgres schema introspection via asyncpg."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

import asyncpg
from pydantic import BaseModel, Field

from lumen.core import Result

logger = logging.getLogger(__name__)


class ColumnSnapshot(BaseModel):
    name: str
    data_type: str
    is_nullable: bool = True
    column_default: str | None = None
    comment: str | None = None
    is_primary_key: bool = False
    foreign_key: str | None = None  # "table.column" if FK
    distinct_estimate: int | None = None
    sample_values: list[str] = Field(default_factory=list)
    min_value: str | None = None
    max_value: str | None = None


class TableSnapshot(BaseModel):
    name: str
    row_count: int = 0
    comment: str | None = None
    columns: list[ColumnSnapshot] = Field(default_factory=list)


class SchemaSnapshot(BaseModel):
    database: str = ""
    schema_name: str = "public"
    introspected_at: str = ""
    tables: list[TableSnapshot] = Field(default_factory=list)


_LOW_CARDINALITY_TYPES = frozenset({"character varying", "text", "char", "bpchar", "USER-DEFINED"})
_TIME_TYPES = frozenset({"date", "timestamp without time zone", "timestamp with time zone", "timestamptz"})
_NUMERIC_TYPES = frozenset(
    {
        "integer",
        "bigint",
        "smallint",
        "numeric",
        "real",
        "double precision",
        "decimal",
    }
)


async def introspect(dsn: str, schema_name: str = "public") -> Result[SchemaSnapshot]:
    """Introspect a Postgres database and return a SchemaSnapshot."""
    result: Result[SchemaSnapshot] = Result()
    conn: asyncpg.Connection[object] | None = None

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        result.error("CONN_ERROR", f"Failed to connect: {e}", hint="Check your connection string.")
        return result

    try:
        snapshot = SchemaSnapshot(schema_name=schema_name)

        row = await conn.fetchrow("SELECT current_database()")
        snapshot.database = str(row["current_database"]) if row else ""

        snapshot.introspected_at = datetime.now(UTC).isoformat()

        # 1. Tables and columns
        columns_rows = await conn.fetch(
            """
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = $1
            ORDER BY table_name, ordinal_position
            """,
            schema_name,
        )

        tables_dict: dict[str, TableSnapshot] = {}
        for row in columns_rows:
            tname = str(row["table_name"])
            if tname not in tables_dict:
                tables_dict[tname] = TableSnapshot(name=tname)
            tables_dict[tname].columns.append(
                ColumnSnapshot(
                    name=str(row["column_name"]),
                    data_type=str(row["data_type"]),
                    is_nullable=str(row["is_nullable"]) == "YES",
                    column_default=str(row["column_default"]) if row["column_default"] is not None else None,
                )
            )

        # 2. PK/FK constraints
        constraint_rows = await conn.fetch(
            """
            SELECT tc.table_name, kcu.column_name, tc.constraint_type,
                   ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu USING (constraint_name, table_schema)
            LEFT JOIN information_schema.constraint_column_usage ccu USING (constraint_name, table_schema)
            WHERE tc.table_schema = $1
            """,
            schema_name,
        )

        for row in constraint_rows:
            tname = str(row["table_name"])
            cname = str(row["column_name"])
            ctype = str(row["constraint_type"])
            if tname in tables_dict:
                for col in tables_dict[tname].columns:
                    if col.name == cname:
                        if ctype == "PRIMARY KEY":
                            col.is_primary_key = True
                        elif ctype == "FOREIGN KEY" and row["foreign_table"] and row["foreign_column"]:
                            col.foreign_key = f"{row['foreign_table']}.{row['foreign_column']}"

        # 4. Approximate row counts
        count_rows = await conn.fetch(
            """
            SELECT relname, reltuples::bigint AS row_count
            FROM pg_class
            WHERE relnamespace = $1::regnamespace
            """,
            schema_name,
        )
        for row in count_rows:
            tname = str(row["relname"])
            if tname in tables_dict:
                tables_dict[tname].row_count = max(0, int(row["row_count"]))

        # 5. Table comments
        for tname, table in tables_dict.items():
            comment_row = await conn.fetchrow(
                """
                SELECT obj_description(c.oid)
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE c.relname = $1 AND n.nspname = $2
                """,
                tname,
                schema_name,
            )
            if comment_row and comment_row[0]:
                table.comment = str(comment_row[0])

        # 5b. Column comments
        for tname, table in tables_dict.items():
            qualified = f"{schema_name}.{tname}"
            col_comment_rows = await conn.fetch(
                """
                SELECT column_name, col_description($1::regclass, ordinal_position)
                FROM information_schema.columns
                WHERE table_name = $2 AND table_schema = $3
                ORDER BY ordinal_position
                """,
                qualified,
                tname,
                schema_name,
            )
            for row in col_comment_rows:
                cname = str(row["column_name"])
                desc = row["col_description"]
                if desc:
                    for col in table.columns:
                        if col.name == cname:
                            col.comment = str(desc)

        # Per-column introspection (distinct counts, sample values, ranges)
        for tname, table in tables_dict.items():
            for col in table.columns:
                # 6. Distinct count estimates
                try:
                    dist_row = await conn.fetchrow(
                        f'SELECT COUNT(DISTINCT "{col.name}") AS dc FROM "{tname}"'  # noqa: S608
                    )
                    if dist_row:
                        col.distinct_estimate = int(dist_row["dc"])
                except Exception:
                    logger.debug("Could not get distinct count for %s.%s", tname, col.name)

                # 3. Sample values for low-cardinality string columns
                if (
                    col.data_type in _LOW_CARDINALITY_TYPES
                    and col.distinct_estimate is not None
                    and col.distinct_estimate <= 50
                ):
                    try:
                        sample_rows = await conn.fetch(
                            f'SELECT DISTINCT "{col.name}" FROM "{tname}" WHERE "{col.name}" IS NOT NULL LIMIT 20'  # noqa: S608
                        )
                        col.sample_values = [str(r[0]) for r in sample_rows if r[0] is not None]
                    except Exception:
                        logger.debug("Could not get sample values for %s.%s", tname, col.name)

                # 7. Value ranges for time and numeric columns
                if col.data_type in _TIME_TYPES or col.data_type in _NUMERIC_TYPES:
                    try:
                        range_row = await conn.fetchrow(
                            f'SELECT MIN("{col.name}") AS mn, MAX("{col.name}") AS mx FROM "{tname}"'  # noqa: S608
                        )
                        if range_row:
                            mn = range_row["mn"]
                            mx = range_row["mx"]
                            if mn is not None:
                                col.min_value = _format_value(mn)
                            if mx is not None:
                                col.max_value = _format_value(mx)
                    except Exception:
                        logger.debug("Could not get range for %s.%s", tname, col.name)

        snapshot.tables = list(tables_dict.values())
        result.data = snapshot
        result.info("INTROSPECTION_OK", f"Introspected {len(snapshot.tables)} tables")

    except Exception as e:
        result.error("INTROSPECTION_ERROR", f"Introspection failed: {e}")
    finally:
        if conn:
            await conn.close()

    return result


def _format_value(val: object) -> str:
    """Format a value for display in schema context."""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    return str(val)
