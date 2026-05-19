# lumen/server/routes/health.py

from typing import Any

from fastapi import APIRouter

from lumen.server.dependencies import StateDep

router = APIRouter()


@router.get("/health")
async def health(state: StateDep) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True}

    if state.config.active_connection:
        result["connection_name"] = state.config.active_connection

    if state.schema_ctx is None:
        result["ok"] = False
        result["reason"] = "No schema loaded"
        return result

    result["database"] = state.schema_ctx.enriched.database

    if state.datasource is None:
        result["ok"] = False
        result["reason"] = "No data source configured"
        return result

    ping_result = await state.datasource.ping()
    if not ping_result.ok:
        result["ok"] = False
        result["reason"] = (
            ping_result.diagnostics[0].message
            if ping_result.diagnostics
            else "Database unreachable"
        )

    return result