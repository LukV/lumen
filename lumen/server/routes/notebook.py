# lumen/server/routes/notebook.py

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from lumen.server.dependencies import StateDep

router = APIRouter()


class UpdateCellRequest(BaseModel):
    title: str


@router.patch("/cells/{cell_id}")
async def update_cell(
    cell_id: str,
    request: UpdateCellRequest,
    state: StateDep,
) -> Any:
    if state.store.update_cell_title(cell_id, request.title):
        return {"ok": True}

    return JSONResponse(
        status_code=404,
        content={"error": f"Cell {cell_id} not found"},
    )


@router.delete("/cells/{cell_id}")
async def delete_cell(cell_id: str, state: StateDep) -> Any:
    if state.store.delete_cell(cell_id):
        return {"ok": True}

    return JSONResponse(
        status_code=404,
        content={"error": f"Cell {cell_id} not found"},
    )


@router.get("/notebook")
async def get_notebook(state: StateDep) -> list[dict[str, Any]]:
    return [cell.model_dump() for cell in state.store.get_cells()]