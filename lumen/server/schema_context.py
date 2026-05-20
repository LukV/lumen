# lumen/server/schema_context.py

from lumen.schema.cache import load_cached
from lumen.schema.context import SchemaContext
from lumen.server.state import AppState


async def get_schema_ctx(state: AppState) -> SchemaContext | None:
    """Return cached schema context, loading from disk if needed."""
    if state.schema_ctx is not None:
        return state.schema_ctx

    async with state.schema_lock:
        if state.schema_ctx is not None:
            return state.schema_ctx

        if state.config.active_connection:
            state.schema_ctx = await load_cached(state.config.active_connection)

    return state.schema_ctx