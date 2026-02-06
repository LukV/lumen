"""SQL validation using pglast AST analysis.

Only SELECT statements are allowed. Any DML, DDL, or DCL is rejected,
including within CTEs.
"""

from __future__ import annotations

import pglast
from pglast import visitors

from lumen.core import Result

_FORBIDDEN_NODE_TAGS = frozenset(
    {
        "InsertStmt",
        "UpdateStmt",
        "DeleteStmt",
        "CreateStmt",
        "DropStmt",
        "AlterTableStmt",
        "TruncateStmt",
        "GrantStmt",
        "RevokeStmt",
        "CreateFunctionStmt",
        "CreateRoleStmt",
        "CopyStmt",
        "CreateSchemaStmt",
        "CreateTableAsStmt",
    }
)


class _ForbiddenNodeChecker(visitors.Visitor):  # type: ignore[misc]
    """Walks the AST looking for forbidden statement types."""

    def __init__(self) -> None:
        self.forbidden: list[str] = []

    def visit(self, ancestors: object, node: object) -> None:
        tag = type(node).__name__
        if tag in _FORBIDDEN_NODE_TAGS:
            self.forbidden.append(tag)


def validate_sql(sql: str) -> Result[str]:
    """Validate that SQL is a single, safe SELECT statement.

    Returns Result with the cleaned SQL on success, or error diagnostics.
    """
    result: Result[str] = Result()

    # Parse
    try:
        stmts = pglast.parse_sql(sql)
    except pglast.parser.ParseError as e:
        result.error("SQL_PARSE_ERROR", f"SQL parse error: {e}")
        return result

    # Must be exactly one statement
    if len(stmts) != 1:
        result.error("VALIDATION_ERROR", f"Expected 1 statement, got {len(stmts)}")
        return result

    # Top-level must be a SELECT
    top_stmt = stmts[0].stmt
    if type(top_stmt).__name__ != "SelectStmt":
        result.error("VALIDATION_ERROR", f"Only SELECT statements allowed, got {type(top_stmt).__name__}")
        return result

    # Walk entire AST for forbidden nodes (catches DML in CTEs, subqueries, etc.)
    checker = _ForbiddenNodeChecker()
    checker(stmts)
    for tag in checker.forbidden:
        result.error("VALIDATION_ERROR", f"Forbidden statement type: {tag}")

    if result.ok:
        result.data = sql.strip()

    return result
