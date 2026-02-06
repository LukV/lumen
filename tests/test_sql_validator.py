"""Tests for SQL validator."""

from lumen.agent.sql_validator import validate_sql


def test_valid_simple_select() -> None:
    r = validate_sql("SELECT 1")
    assert r.ok
    assert r.data == "SELECT 1"


def test_valid_select_with_from() -> None:
    r = validate_sql("SELECT name, age FROM users WHERE age > 21")
    assert r.ok


def test_valid_select_with_cte() -> None:
    r = validate_sql("WITH top AS (SELECT * FROM users LIMIT 10) SELECT * FROM top")
    assert r.ok


def test_valid_select_with_subquery() -> None:
    r = validate_sql("SELECT * FROM (SELECT 1 AS x) sub")
    assert r.ok


def test_reject_insert() -> None:
    r = validate_sql("INSERT INTO users VALUES (1, 'test')")
    assert not r.ok
    assert any("INSERT" in d.message or d.code == "VALIDATION_ERROR" for d in r.diagnostics)


def test_reject_update() -> None:
    r = validate_sql("UPDATE users SET name = 'x'")
    assert not r.ok


def test_reject_delete() -> None:
    r = validate_sql("DELETE FROM users")
    assert not r.ok


def test_reject_drop() -> None:
    r = validate_sql("DROP TABLE users")
    assert not r.ok


def test_reject_create() -> None:
    r = validate_sql("CREATE TABLE foo (id int)")
    assert not r.ok


def test_reject_truncate() -> None:
    r = validate_sql("TRUNCATE users")
    assert not r.ok


def test_reject_dml_in_cte() -> None:
    r = validate_sql("WITH x AS (DELETE FROM users RETURNING *) SELECT * FROM x")
    assert not r.ok
    assert any("DeleteStmt" in d.message for d in r.diagnostics)


def test_reject_multiple_statements() -> None:
    r = validate_sql("SELECT 1; SELECT 2")
    assert not r.ok
    assert any("Expected 1 statement" in d.message for d in r.diagnostics)


def test_reject_syntax_error() -> None:
    r = validate_sql("SELECTTTT 1")
    assert not r.ok
    assert any(d.code == "SQL_PARSE_ERROR" for d in r.diagnostics)


def test_strips_whitespace() -> None:
    r = validate_sql("  SELECT 1  ")
    assert r.ok
    assert r.data == "SELECT 1"
