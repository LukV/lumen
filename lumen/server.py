"""FastAPI server for Lumen."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from lumen.config import load_config
from lumen.schema.cache import load_cached
from lumen.schema.context import SchemaContext

app = FastAPI(title="Lumen", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cached schema context loaded on first request
_schema_ctx: SchemaContext | None = None


async def _get_schema_ctx() -> SchemaContext | None:
    global _schema_ctx  # noqa: PLW0603
    if _schema_ctx is not None:
        return _schema_ctx

    config = load_config()
    if config.active_connection:
        _schema_ctx = await load_cached(config.active_connection)
    return _schema_ctx


@app.get("/api/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


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


# Serve frontend static files if built
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
