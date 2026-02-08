"""Canonical cell models for the notebook.

A Cell captures every stage of the ask flow: question → SQL → result → chart → narrative.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from lumen.core import Diag


def generate_cell_id() -> str:
    """Generate a cell ID: 'cell_' + 8 hex chars from uuid4."""
    return "cell_" + uuid.uuid4().hex[:8]


def compute_data_hash(rows: list[dict[str, object]]) -> str:
    """Compute a deterministic SHA-256 hash of result rows."""
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class CellContext(BaseModel):
    parent_cell_id: str | None = None
    refinement_of: str | None = None
    conversation_position: int = 0


class CellSQL(BaseModel):
    query: str
    generated_by: str = "llm"
    edited_by_user: bool = False
    user_sql_override: str | None = None


class CellResult(BaseModel):
    columns: list[str] = Field(default_factory=list)
    column_types: list[str] = Field(default_factory=list)
    row_count: int = 0
    data_hash: str = ""
    data: list[dict[str, object]] = Field(default_factory=list)
    truncated: bool = False
    execution_time_ms: int = 0
    diagnostics: list[Diag] = Field(default_factory=list)


class CellChart(BaseModel):
    spec: dict[str, object] = Field(default_factory=dict)
    auto_detected: bool = False
    theme: str = "lumen-default"


class DataReference(BaseModel):
    ref_id: str
    text: str
    source: str


class CellNarrative(BaseModel):
    text: str = ""
    data_references: list[DataReference] = Field(default_factory=list)


class WhatIfMetadata(BaseModel):
    technique: str
    parameters: dict[str, object] = Field(default_factory=dict)
    caveats: list[str] = Field(default_factory=list)


class CellMetadata(BaseModel):
    model: str = ""
    schema_version: str = ""
    agent_steps: list[str] = Field(default_factory=list)
    retry_count: int = 0
    reasoning: str = ""
    whatif: WhatIfMetadata | None = None


class Cell(BaseModel):
    id: str = Field(default_factory=generate_cell_id)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    question: str = ""
    context: CellContext = Field(default_factory=CellContext)
    sql: CellSQL | None = None
    result: CellResult | None = None
    chart: CellChart | None = None
    narrative: CellNarrative | None = None
    metadata: CellMetadata = Field(default_factory=CellMetadata)
