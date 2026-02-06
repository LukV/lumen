"""Tests for core types: Result[T] and Diag."""

from lumen.core import Diag, Result, Severity


def test_severity_values() -> None:
    assert Severity.ERROR == "error"
    assert Severity.WARNING == "warning"
    assert Severity.INFO == "info"


def test_diag_creation() -> None:
    d = Diag(severity=Severity.ERROR, code="SQL_ERROR", message="bad query")
    assert d.severity == Severity.ERROR
    assert d.code == "SQL_ERROR"
    assert d.message == "bad query"
    assert d.hint is None


def test_diag_with_hint() -> None:
    d = Diag(severity=Severity.WARNING, code="TRUNCATED", message="too many rows", hint="Add a LIMIT clause")
    assert d.hint == "Add a LIMIT clause"


def test_result_empty_is_ok() -> None:
    r: Result[str] = Result()
    assert r.ok is True
    assert r.has_errors is False
    assert r.data is None
    assert r.diagnostics == []


def test_result_with_data() -> None:
    r: Result[int] = Result(data=42)
    assert r.ok is True
    assert r.data == 42


def test_result_error_helper() -> None:
    r: Result[str] = Result(data="hello")
    r.error("FAIL", "something broke")
    assert r.ok is False
    assert r.has_errors is True
    assert len(r.diagnostics) == 1
    assert r.diagnostics[0].severity == Severity.ERROR
    assert r.diagnostics[0].code == "FAIL"


def test_result_warning_helper() -> None:
    r: Result[str] = Result(data="hello")
    r.warning("WARN", "heads up", hint="do something")
    assert r.ok is True
    assert r.has_errors is False
    assert len(r.diagnostics) == 1
    assert r.diagnostics[0].severity == Severity.WARNING
    assert r.diagnostics[0].hint == "do something"


def test_result_info_helper() -> None:
    r: Result[str] = Result(data="hello")
    r.info("NOTE", "fyi")
    assert r.ok is True
    assert len(r.diagnostics) == 1
    assert r.diagnostics[0].severity == Severity.INFO


def test_result_mixed_diagnostics() -> None:
    r: Result[str] = Result(data="partial")
    r.info("LOADED", "schema loaded")
    r.warning("STALE", "cache is old")
    assert r.ok is True
    assert len(r.diagnostics) == 2

    r.error("CONN_FAIL", "connection lost")
    assert r.ok is False
    assert r.has_errors is True
    assert len(r.diagnostics) == 3


def test_result_serialization() -> None:
    r: Result[str] = Result(data="test")
    r.warning("W", "warn")
    d = r.model_dump()
    assert d["data"] == "test"
    assert len(d["diagnostics"]) == 1
    assert d["diagnostics"][0]["severity"] == "warning"


def test_result_no_path_field() -> None:
    """Verify that Diag does not have a path field (dropped from DuckBook)."""
    d = Diag(severity=Severity.ERROR, code="X", message="y")
    dumped = d.model_dump()
    assert "path" not in dumped
