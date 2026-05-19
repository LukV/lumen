"""Application state for dependency injection."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lumen.config import LumenConfig
from lumen.datasource.protocol import DataSource
from lumen.notebook.store import NotebookStore
from lumen.schema.context import SchemaContext

if TYPE_CHECKING:
    import asyncpg


@dataclass(slots=True)
class AppState:
    """Mutable application state shared by FastAPI endpoints."""

    config: LumenConfig
    store: NotebookStore

    schema_ctx: SchemaContext | None = None
    datasource: DataSource | None = None
    pool: asyncpg.Pool | None = None

    suggestions: list[str] = field(default_factory=list)
    suggestions_generating: bool = False

    table_descriptions: dict[str, str] = field(default_factory=dict)
    descriptions_generating: bool = False

    schema_lock: asyncio.Lock = field(default_factory=asyncio.Lock)