# lumen/server/routes/suggestions.py

from typing import Any

from fastapi import APIRouter

from lumen.server.dependencies import StateDep

router = APIRouter()


@router.get("/suggestions")
async def get_suggestions(state: StateDep) -> dict[str, Any]:
    return {
        "suggestions": state.suggestions,
        "generating": state.suggestions_generating,
    }


@router.get("/descriptions")
async def get_descriptions(state: StateDep) -> dict[str, Any]:
    return {
        "descriptions": state.table_descriptions,
        "generating": state.descriptions_generating,
    }