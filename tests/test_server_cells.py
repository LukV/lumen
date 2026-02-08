"""Tests for cell PATCH and DELETE endpoints."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from lumen.agent.cell import Cell, CellNarrative, CellResult, CellSQL
from lumen.notebook.store import NotebookStore, reset_store
from lumen.server import app


def _make_cell(question: str = "Test?") -> Cell:
    return Cell(
        question=question,
        sql=CellSQL(query="SELECT 1"),
        result=CellResult(columns=["a"], column_types=["int"], row_count=1, data=[{"a": 1}]),
        narrative=CellNarrative(text="One row."),
    )


@pytest.fixture
def _store(tmp_path: Path) -> Generator[NotebookStore]:
    """Provide a fresh NotebookStore and patch get_store to return it."""
    store = NotebookStore(tmp_path)
    with patch("lumen.server.get_store", return_value=store):
        yield store
    reset_store()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_patch_cell_title(client: AsyncClient, _store: NotebookStore) -> None:
    cell = _make_cell("Original")
    _store.add_cell(cell)

    resp = await client.patch(f"/api/cells/{cell.id}", json={"title": "My Custom Title"})
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    updated = _store.get_cell(cell.id)
    assert updated is not None
    assert updated.title == "My Custom Title"


async def test_patch_cell_not_found(client: AsyncClient, _store: NotebookStore) -> None:
    resp = await client.patch("/api/cells/cell_nonexistent", json={"title": "Title"})
    assert resp.status_code == 404


async def test_delete_cell_endpoint(client: AsyncClient, _store: NotebookStore) -> None:
    cell = _make_cell("To delete")
    _store.add_cell(cell)
    assert len(_store.get_cells()) == 1

    resp = await client.delete(f"/api/cells/{cell.id}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert len(_store.get_cells()) == 0


async def test_delete_cell_not_found(client: AsyncClient, _store: NotebookStore) -> None:
    resp = await client.delete("/api/cells/cell_nonexistent")
    assert resp.status_code == 404
