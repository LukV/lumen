# lumen/server/routes/schema.py

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from lumen.server.dependencies import StateDep
from lumen.server.schema_context import get_schema_ctx

router = APIRouter()


@router.get("/schema")
async def get_schema(state: StateDep) -> Any:
    ctx = await get_schema_ctx(state)

    if ctx is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No schema loaded. Run `lumen connect` first."},
        )

    return ctx.model_dump(by_alias=True)