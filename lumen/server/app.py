# lumen/server/app.py

import asyncio
import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import asyncpg
from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from lumen.agent.suggestions import (
    SuggestionsCache,
    generate_suggestions,
    load_cached_suggestions,
    save_suggestions_cache,
)
from lumen.config import LumenConfig, load_config, notebooks_dir
from lumen.datasource.protocol import DataSource
from lumen.notebook.notebook import Notebook
from lumen.notebook.store import NotebookStore
from lumen.schema.cache import load_cached
from lumen.schema.context import SchemaContext
from lumen.schema.describer import (
    DescriptionsCache,
    generate_descriptions,
    load_cached_descriptions,
    save_descriptions_cache,
)
from lumen.server.routes.health import router as health_router
from lumen.server.state import AppState

logger = logging.getLogger("lumen.server")


def _create_datasource(config: LumenConfig, pool: asyncpg.Pool | None = None) -> DataSource | None:
    """Create the appropriate DataSource from the active connection config."""
    if not config.active_connection:
        return None
    conn = config.connections.get(config.active_connection)
    if conn is None:
        return None
    if conn.type == "duckdb":
        from lumen.datasource.duckdb_source import DuckDBSource

        return DuckDBSource(conn.parquet_path)

    from lumen.datasource.postgres import PostgresSource

    return PostgresSource(conn.dsn, conn.schema_name, pool=pool)

async def _generate_suggestions_bg(state: AppState, schema_ctx: SchemaContext) -> None:
    """Generate suggestions in background thread and cache on success."""
    state.suggestions_generating = True
    try:
        result = await asyncio.to_thread(generate_suggestions, schema_ctx, state.config)
        if result.ok and result.data:
            state.suggestions = result.data
            if state.config.active_connection:
                cache = SuggestionsCache(schema_hash=schema_ctx.hash, suggestions=result.data)
                save_suggestions_cache(state.config.active_connection, cache)
                logger.info("Generated and cached %d suggestions", len(result.data))
        else:
            logger.warning("Suggestion generation failed: %s", result.diagnostics)
    except Exception:
        logger.exception("Error generating suggestions")
    finally:
        state.suggestions_generating = False


async def _generate_descriptions_bg(state: AppState, schema_ctx: SchemaContext) -> None:
    """Generate table descriptions in background thread and cache on success."""
    state.descriptions_generating = True
    try:
        result = await asyncio.to_thread(generate_descriptions, schema_ctx, state.config)
        if result.ok and result.data:
            state.table_descriptions = result.data
            if state.config.active_connection:
                cache = DescriptionsCache(schema_hash=schema_ctx.hash, descriptions=result.data)
                save_descriptions_cache(state.config.active_connection, cache)
                logger.info("Generated and cached %d table descriptions", len(result.data))
        else:
            logger.warning("Description generation failed: %s", result.diagnostics)
    except Exception:
        logger.exception("Error generating descriptions")
    finally:
        state.descriptions_generating = False


async def _startup_logic(state: AppState) -> None:
    """Load the most recent notebook for the active connection on startup."""
    if not state.config.active_connection:
        return

    latest = state.store.load_latest(state.config.active_connection)
    if latest:
        state.store.set_notebook(latest)
        logger.info("Loaded notebook %s (%d cells)", latest.id, len(latest.cells))
    else:
        nb = Notebook(connection_name=state.config.active_connection)
        state.store.set_notebook(nb)
        logger.info("Created new notebook %s for connection %s", nb.id, state.config.active_connection)

    # Load schema and create datasource
    schema_ctx = await load_cached(state.config.active_connection)
    if schema_ctx:
        state.schema_ctx = schema_ctx
        state.datasource = _create_datasource(state.config, pool=state.pool)

        cached = load_cached_suggestions(state.config.active_connection)
        if cached and cached.schema_hash == schema_ctx.hash:
            state.suggestions = cached.suggestions
            logger.info("Loaded %d cached suggestions", len(state.suggestions))
        else:
            asyncio.create_task(_generate_suggestions_bg(state, schema_ctx))

        desc_cached = load_cached_descriptions(state.config.active_connection)
        if desc_cached and desc_cached.schema_hash == schema_ctx.hash:
            state.table_descriptions = desc_cached.descriptions
            logger.info("Loaded %d cached table descriptions", len(state.table_descriptions))
        else:
            asyncio.create_task(_generate_descriptions_bg(state, schema_ctx))


async def _create_pool(config: LumenConfig) -> asyncpg.Pool | None:
    """Create a connection pool for Postgres connections."""
    if not config.active_connection:
        return None
    conn = config.connections.get(config.active_connection)
    if conn is None or conn.type != "postgresql":
        return None
    try:
        pool = await asyncpg.create_pool(conn.dsn, min_size=2, max_size=10)
        logger.info("Created asyncpg connection pool (min=2, max=10)")
        return pool
    except Exception:
        logger.exception("Failed to create connection pool — falling back to per-query connections")
        return None


@asynccontextmanager
async def lifespan(_app_instance: FastAPI) -> AsyncGenerator[None]:
    config = load_config()
    pool = await _create_pool(config)
    state = AppState(
        config=config,
        store=NotebookStore(notebooks_dir()),
        pool=pool,
    )
    _app_instance.state.app_state = state
    await _startup_logic(state)
    yield
    if state.pool is not None:
        await state.pool.close()
        logger.info("Connection pool closed")

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Lumen", version="0.3.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")

    frontend_dist = Path(__file__).parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()