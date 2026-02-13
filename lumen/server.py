"""FastAPI server for Lumen."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from lumen.agent.agent import ask_question, run_edited_sql
from lumen.agent.cell import Cell
from lumen.agent.suggestions import (
    SuggestionsCache,
    generate_suggestions,
    load_cached_suggestions,
    save_suggestions_cache,
)
from lumen.config import LumenConfig, load_config, notebooks_dir
from lumen.notebook.notebook import Notebook
from lumen.notebook.store import get_store
from lumen.schema.cache import load_cached
from lumen.schema.context import SchemaContext

logger = logging.getLogger("lumen.server")

app = FastAPI(title="Lumen", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cached schema context loaded on first request
_schema_ctx: SchemaContext | None = None

# Suggestion questions
_suggestions: list[str] = []
_suggestions_generating: bool = False


async def _get_schema_ctx() -> SchemaContext | None:
    global _schema_ctx  # noqa: PLW0603
    if _schema_ctx is not None:
        return _schema_ctx

    config = load_config()
    if config.active_connection:
        _schema_ctx = await load_cached(config.active_connection)
    return _schema_ctx


def _sse_error(code: str, message: str) -> EventSourceResponse:
    """Return an SSE response with a single error event."""

    async def _stream() -> AsyncGenerator[dict[str, str]]:
        yield {"event": "error", "data": json.dumps({"code": code, "message": message})}

    return EventSourceResponse(_stream())


async def _generate_suggestions_bg(schema_ctx: SchemaContext, config: LumenConfig) -> None:
    """Generate suggestions in background thread and cache on success."""
    global _suggestions, _suggestions_generating  # noqa: PLW0603
    _suggestions_generating = True
    try:
        result = await asyncio.to_thread(generate_suggestions, schema_ctx, config)
        if result.ok and result.data:
            _suggestions = result.data
            if config.active_connection:
                cache = SuggestionsCache(schema_hash=schema_ctx.hash, suggestions=result.data)
                save_suggestions_cache(config.active_connection, cache)
                logger.info("Generated and cached %d suggestions", len(result.data))
        else:
            logger.warning("Suggestion generation failed: %s", result.diagnostics)
    except Exception:
        logger.exception("Error generating suggestions")
    finally:
        _suggestions_generating = False


@app.on_event("startup")
async def _startup() -> None:
    """Load the most recent notebook for the active connection on startup."""
    global _suggestions  # noqa: PLW0603
    config = load_config()
    if not config.active_connection:
        return

    store = get_store(notebooks_dir())
    latest = store.load_latest(config.active_connection)
    if latest:
        store.set_notebook(latest)
        logger.info("Loaded notebook %s (%d cells)", latest.id, len(latest.cells))
    else:
        # Create a fresh notebook for this connection
        nb = Notebook(connection_name=config.active_connection)
        store.set_notebook(nb)
        logger.info("Created new notebook %s for connection %s", nb.id, config.active_connection)

    # Load or generate suggestions
    schema_ctx = await load_cached(config.active_connection)
    if schema_ctx:
        cached = load_cached_suggestions(config.active_connection)
        if cached and cached.schema_hash == schema_ctx.hash:
            _suggestions = cached.suggestions
            logger.info("Loaded %d cached suggestions", len(_suggestions))
        else:
            asyncio.create_task(_generate_suggestions_bg(schema_ctx, config))


@app.get("/api/health")
async def health() -> dict[str, Any]:
    config = load_config()
    result: dict[str, Any] = {"ok": True}
    if config.active_connection:
        result["connection_name"] = config.active_connection
    if _schema_ctx is not None:
        result["database"] = _schema_ctx.enriched.database
    return result


@app.get("/api/suggestions")
async def get_suggestions() -> dict[str, Any]:
    return {"suggestions": _suggestions, "generating": _suggestions_generating}


@app.get("/api/schema")
async def get_schema() -> Any:
    ctx = await _get_schema_ctx()
    if ctx is None:
        return JSONResponse(status_code=404, content={"error": "No schema loaded. Run `lumen connect` first."})
    return ctx.model_dump(by_alias=True)


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    config = load_config()
    return {
        "active_connection": config.active_connection,
        "has_connection": config.active_connection is not None,
        "connections": list(config.connections.keys()),
    }


class AskRequest(BaseModel):
    question: str
    parent_cell_id: str | None = None


@app.post("/api/ask")
async def ask(request: AskRequest) -> EventSourceResponse:
    logger.info("POST /api/ask question=%r parent=%s", request.question, request.parent_cell_id)
    ctx = await _get_schema_ctx()
    if ctx is None:
        logger.warning("No schema loaded")
        return _sse_error("NO_SCHEMA", "No schema loaded. Run `lumen connect` first.")

    config = load_config()
    store = get_store(notebooks_dir())
    cells = store.get_cells()

    async def _event_stream() -> AsyncGenerator[dict[str, str]]:
        try:
            async for sse_event in ask_question(request.question, ctx, config, cells, request.parent_cell_id):
                event_dict = sse_event.to_dict()
                evt_type = event_dict["event"]
                logger.info("SSE >> %s", evt_type)
                if evt_type == "cell":
                    cell = Cell.model_validate(event_dict["data"])
                    store.add_cell(cell)
                yield {"event": evt_type, "data": json.dumps(event_dict["data"], default=str)}
            logger.info("SSE stream complete")
        except Exception:
            logger.exception("Error in SSE stream")
            yield {"event": "error", "data": json.dumps({"code": "STREAM_ERROR", "message": "Internal server error"})}

    return EventSourceResponse(_event_stream())


class RunSQLRequest(BaseModel):
    cell_id: str
    sql: str


@app.post("/api/run-sql")
async def run_sql(request: RunSQLRequest) -> EventSourceResponse:
    logger.info("POST /api/run-sql cell_id=%s", request.cell_id)
    ctx = await _get_schema_ctx()
    if ctx is None:
        return _sse_error("NO_SCHEMA", "No schema loaded.")

    config = load_config()
    store = get_store(notebooks_dir())
    original_cell = store.get_cell(request.cell_id)

    if original_cell is None:
        return _sse_error("NOT_FOUND", f"Cell {request.cell_id} not found")

    async def _event_stream() -> AsyncGenerator[dict[str, str]]:
        try:
            async for sse_event in run_edited_sql(request.sql, original_cell, ctx, config):
                event_dict = sse_event.to_dict()
                evt_type = event_dict["event"]
                logger.info("SSE >> %s", evt_type)
                if evt_type == "cell":
                    cell = Cell.model_validate(event_dict["data"])
                    store.update_cell(request.cell_id, cell)
                yield {"event": evt_type, "data": json.dumps(event_dict["data"], default=str)}
            logger.info("run-sql SSE stream complete")
        except Exception:
            logger.exception("Error in run-sql SSE stream")
            yield {"event": "error", "data": json.dumps({"code": "STREAM_ERROR", "message": "Internal server error"})}

    return EventSourceResponse(_event_stream())


class UpdateCellRequest(BaseModel):
    title: str


@app.patch("/api/cells/{cell_id}")
async def update_cell(cell_id: str, request: UpdateCellRequest) -> Any:
    store = get_store(notebooks_dir())
    if store.update_cell_title(cell_id, request.title):
        return {"ok": True}
    return JSONResponse(status_code=404, content={"error": f"Cell {cell_id} not found"})


@app.delete("/api/cells/{cell_id}")
async def delete_cell(cell_id: str) -> Any:
    store = get_store(notebooks_dir())
    if store.delete_cell(cell_id):
        return {"ok": True}
    return JSONResponse(status_code=404, content={"error": f"Cell {cell_id} not found"})


@app.get("/api/notebook")
async def get_notebook() -> list[dict[str, Any]]:
    store = get_store(notebooks_dir())
    return [cell.model_dump() for cell in store.get_cells()]


# Serve frontend static files if built
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
