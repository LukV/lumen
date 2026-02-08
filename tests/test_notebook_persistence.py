"""Tests for notebook persistence."""

from __future__ import annotations

from pathlib import Path

from lumen.agent.cell import Cell, CellNarrative, CellResult, CellSQL
from lumen.notebook.notebook import Notebook
from lumen.notebook.store import NotebookStore


def _make_cell(question: str = "Test?") -> Cell:
    return Cell(
        question=question,
        sql=CellSQL(query="SELECT 1"),
        result=CellResult(columns=["a"], column_types=["int"], row_count=1, data=[{"a": 1}]),
        narrative=CellNarrative(text="One row."),
    )


def test_save_and_load(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    store.notebook.connection_name = "myconn"
    cell = _make_cell()
    store.add_cell(cell)

    nb_id = store.notebook.id
    result = store.load(nb_id)
    assert result.ok
    loaded = result.data
    assert loaded is not None
    assert len(loaded.cells) == 1
    assert loaded.cells[0].question == "Test?"
    assert loaded.cells[0].sql is not None
    assert loaded.cells[0].sql.query == "SELECT 1"
    assert loaded.connection_name == "myconn"


def test_conversation_position_auto_set(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    c1 = _make_cell("Q1")
    c2 = _make_cell("Q2")
    store.add_cell(c1)
    store.add_cell(c2)
    assert c1.context.conversation_position == 1
    assert c2.context.conversation_position == 2


def test_update_cell(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    cell = _make_cell("Original")
    store.add_cell(cell)

    updated = cell.model_copy(update={"question": "Updated"})
    store.update_cell(cell.id, updated)

    assert store.get_cell(cell.id) is not None
    assert store.get_cell(cell.id).question == "Updated"  # type: ignore[union-attr]

    # Persisted
    result = store.load(store.notebook.id)
    assert result.ok
    assert result.data is not None
    assert result.data.cells[0].question == "Updated"


def test_load_not_found(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    result = store.load("nb_nonexistent")
    assert result.has_errors
    assert "not found" in result.diagnostics[0].message.lower()


def test_load_latest(tmp_path: Path) -> None:
    # Create two notebooks for different connections
    store1 = NotebookStore(tmp_path)
    nb1 = Notebook(connection_name="conn_a")
    store1.set_notebook(nb1)
    store1.add_cell(_make_cell("Q from A"))

    store2 = NotebookStore(tmp_path)
    nb2 = Notebook(connection_name="conn_b")
    store2.set_notebook(nb2)
    store2.add_cell(_make_cell("Q from B"))

    # Load latest for conn_a
    fresh_store = NotebookStore(tmp_path)
    latest = fresh_store.load_latest("conn_a")
    assert latest is not None
    assert latest.connection_name == "conn_a"
    assert len(latest.cells) == 1
    assert latest.cells[0].question == "Q from A"


def test_load_latest_no_match(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    assert store.load_latest("nonexistent") is None


def test_atomic_write_no_tmp_leftover(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    store.add_cell(_make_cell())
    # No .tmp files should remain
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_multiple_cells_persist(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    for i in range(5):
        store.add_cell(_make_cell(f"Q{i}"))

    result = store.load(store.notebook.id)
    assert result.ok
    assert result.data is not None
    assert len(result.data.cells) == 5
    assert result.data.cells[3].question == "Q3"


def test_delete_cell(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    cell = _make_cell("To delete")
    store.add_cell(cell)
    assert len(store.get_cells()) == 1

    found = store.delete_cell(cell.id)
    assert found is True
    assert len(store.get_cells()) == 0

    # Verify persisted
    result = store.load(store.notebook.id)
    assert result.ok
    assert result.data is not None
    assert len(result.data.cells) == 0


def test_delete_cell_not_found(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    assert store.delete_cell("cell_nonexistent") is False


def test_update_cell_title(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    cell = _make_cell("Original question")
    store.add_cell(cell)

    found = store.update_cell_title(cell.id, "Custom Title")
    assert found is True
    assert store.get_cell(cell.id) is not None
    assert store.get_cell(cell.id).title == "Custom Title"  # type: ignore[union-attr]

    # Verify persisted
    result = store.load(store.notebook.id)
    assert result.ok
    assert result.data is not None
    assert result.data.cells[0].title == "Custom Title"


def test_update_cell_title_not_found(tmp_path: Path) -> None:
    store = NotebookStore(tmp_path)
    assert store.update_cell_title("cell_nonexistent", "Title") is False
