"""Notebook model for persistent cell storage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from lumen.agent.cell import Cell


def generate_notebook_id() -> str:
    """Generate a notebook ID: 'nb_' + 12 hex chars from uuid4."""
    return "nb_" + uuid.uuid4().hex[:12]


class Notebook(BaseModel):
    id: str = Field(default_factory=generate_notebook_id)
    name: str = "Untitled"
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    connection_name: str = ""
    cells: list[Cell] = Field(default_factory=list)
