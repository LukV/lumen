"""Core types used across all modules."""

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Diag(BaseModel):
    """A structured diagnostic message."""

    severity: Severity
    code: str
    message: str
    hint: str | None = None


class Result(BaseModel, Generic[T]):  # noqa: UP046 — Pydantic requires Generic[T] subclass
    """Result container that pairs output with diagnostics.

    Functions never throw for validation/compilation failures.
    They return Result with diagnostics instead.
    """

    data: T | None = None
    diagnostics: list[Diag] = Field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == Severity.ERROR for d in self.diagnostics)

    @property
    def ok(self) -> bool:
        return not self.has_errors

    def error(self, code: str, message: str, *, hint: str | None = None) -> None:
        self.diagnostics.append(Diag(severity=Severity.ERROR, code=code, message=message, hint=hint))

    def warning(self, code: str, message: str, *, hint: str | None = None) -> None:
        self.diagnostics.append(Diag(severity=Severity.WARNING, code=code, message=message, hint=hint))

    def info(self, code: str, message: str, *, hint: str | None = None) -> None:
        self.diagnostics.append(Diag(severity=Severity.INFO, code=code, message=message, hint=hint))
