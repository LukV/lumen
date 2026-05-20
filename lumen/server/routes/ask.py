# lumen/server/routes/ask.py

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from lumen.agent.agent import ask_question, run_edited_sql
from lumen.cell import Cell
from lumen.server.dependencies import StateDep
from lumen.server.schema_context import get_schema_ctx
from lumen.server.sse import sse_error

logger = logging.getLogger("lumen.server.routes.ask")

router = APIRouter()


class AskRequest(BaseModel):
    question: str
    parent_cell_id: str | None = None


class RunSQLRequest(BaseModel):
    cell_id: str
    sql: str


@router.post("/ask")
async def ask(request: AskRequest, state: StateDep) -> EventSourceResponse:
    logger.info(
        "POST /api/ask question=%r parent=%s",
        request.question,
        request.parent_cell_id,
    )

    ctx = await get_schema_ctx(state)
    if ctx is None:
        logger.warning("No schema loaded")
        return sse_error("NO_SCHEMA", "No schema loaded. Run `lumen connect` first.")

    ds = state.datasource
    if ds is None:
        return sse_error("NO_CONNECTION", "No active connection configured.")

    store = state.store
    cells = store.get_cells()

    async def event_stream() -> AsyncGenerator[dict[str, str]]:
        try:
            async for sse_event in ask_question(
                request.question,
                ctx,
                state.config,
                ds,
                cells,
                request.parent_cell_id,
            ):
                event_dict = sse_event.to_dict()
                evt_type = event_dict["event"]

                logger.info("SSE >> %s", evt_type)

                if evt_type == "cell":
                    cell = Cell.model_validate(event_dict["data"])
                    store.add_cell(cell)

                yield {
                    "event": evt_type,
                    "data": json.dumps(event_dict["data"], default=str),
                }

            logger.info("SSE stream complete")

        except Exception:
            logger.exception("Error in SSE stream")
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "code": "STREAM_ERROR",
                        "message": "Internal server error",
                    }
                ),
            }

    return EventSourceResponse(event_stream())


@router.post("/run-sql")
async def run_sql(request: RunSQLRequest, state: StateDep) -> EventSourceResponse:
    logger.info("POST /api/run-sql cell_id=%s", request.cell_id)

    ctx = await get_schema_ctx(state)
    if ctx is None:
        return sse_error("NO_SCHEMA", "No schema loaded.")

    ds = state.datasource
    if ds is None:
        return sse_error("NO_CONNECTION", "No active connection configured.")

    store = state.store
    original_cell = store.get_cell(request.cell_id)

    if original_cell is None:
        return sse_error("NOT_FOUND", f"Cell {request.cell_id} not found")

    async def event_stream() -> AsyncGenerator[dict[str, str]]:
        try:
            async for sse_event in run_edited_sql(
                request.sql,
                original_cell,
                ctx,
                state.config,
                ds,
            ):
                event_dict = sse_event.to_dict()
                evt_type = event_dict["event"]

                logger.info("SSE >> %s", evt_type)

                if evt_type == "cell":
                    cell = Cell.model_validate(event_dict["data"])
                    store.update_cell(request.cell_id, cell)

                yield {
                    "event": evt_type,
                    "data": json.dumps(event_dict["data"], default=str),
                }

            logger.info("run-sql SSE stream complete")

        except Exception:
            logger.exception("Error in run-sql SSE stream")
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "code": "STREAM_ERROR",
                        "message": "Internal server error",
                    }
                ),
            }

    return EventSourceResponse(event_stream())