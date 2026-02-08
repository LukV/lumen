"""Persistent notebook store. Saves to ~/.lumen/notebooks/{id}.json."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from lumen.agent.cell import Cell
from lumen.core import Result
from lumen.notebook.notebook import Notebook

logger = logging.getLogger("lumen.notebook")


class NotebookStore:
    """Stores cells with automatic disk persistence."""

    def __init__(self, notebooks_dir: Path) -> None:
        self._notebooks_dir = notebooks_dir
        self._notebooks_dir.mkdir(parents=True, exist_ok=True)
        self._notebook: Notebook | None = None

    @property
    def notebook(self) -> Notebook:
        if self._notebook is None:
            self._notebook = Notebook()
        return self._notebook

    def set_notebook(self, notebook: Notebook) -> None:
        """Set the active notebook (e.g. after loading from disk)."""
        self._notebook = notebook

    def add_cell(self, cell: Cell) -> None:
        """Append a cell, set its conversation_position, and persist."""
        cell.context.conversation_position = len(self.notebook.cells) + 1
        self.notebook.cells.append(cell)
        self.notebook.updated_at = datetime.now(UTC).isoformat()
        self.save()

    def update_cell(self, cell_id: str, cell: Cell) -> None:
        """Replace a cell in-place by ID and persist."""
        for i, existing in enumerate(self.notebook.cells):
            if existing.id == cell_id:
                self.notebook.cells[i] = cell
                self.notebook.updated_at = datetime.now(UTC).isoformat()
                self.save()
                return

    def delete_cell(self, cell_id: str) -> bool:
        """Remove a cell by ID, persist, return True if found."""
        for i, cell in enumerate(self.notebook.cells):
            if cell.id == cell_id:
                self.notebook.cells.pop(i)
                self.notebook.updated_at = datetime.now(UTC).isoformat()
                self.save()
                return True
        return False

    def update_cell_title(self, cell_id: str, title: str) -> bool:
        """Set title on a cell, persist, return True if found."""
        for cell in self.notebook.cells:
            if cell.id == cell_id:
                cell.title = title
                self.notebook.updated_at = datetime.now(UTC).isoformat()
                self.save()
                return True
        return False

    def get_cells(self) -> list[Cell]:
        return list(self.notebook.cells)

    def get_cell(self, cell_id: str) -> Cell | None:
        for cell in self.notebook.cells:
            if cell.id == cell_id:
                return cell
        return None

    def save(self) -> None:
        """Atomic write: write to .tmp, then rename."""
        nb = self.notebook
        path = self._notebooks_dir / f"{nb.id}.json"
        tmp_path = path.with_suffix(".json.tmp")
        data = nb.model_dump(exclude_none=True)
        tmp_path.write_text(json.dumps(data, indent=2, default=str) + "\n")
        tmp_path.rename(path)
        logger.info("Saved notebook %s (%d cells)", nb.id, len(nb.cells))

    def load(self, notebook_id: str) -> Result[Notebook]:
        """Load a notebook from disk by ID."""
        result: Result[Notebook] = Result()
        path = self._notebooks_dir / f"{notebook_id}.json"
        if not path.exists():
            result.error("NOT_FOUND", f"Notebook {notebook_id} not found")
            return result
        try:
            data = json.loads(path.read_text())
            nb = Notebook.model_validate(data)
            result.data = nb
        except Exception as e:  # noqa: BLE001
            result.error("LOAD_ERROR", f"Failed to load notebook: {e}")
        return result

    def load_latest(self, connection_name: str) -> Notebook | None:
        """Find the most recently updated notebook for a connection."""
        best: Notebook | None = None
        best_time = ""
        for path in self._notebooks_dir.glob("nb_*.json"):
            try:
                data = json.loads(path.read_text())
                nb = Notebook.model_validate(data)
                if nb.connection_name == connection_name and nb.updated_at > best_time:
                    best = nb
                    best_time = nb.updated_at
            except Exception:  # noqa: BLE001
                logger.warning("Skipping corrupt notebook: %s", path)
                continue
        return best


_store: NotebookStore | None = None


def get_store(notebooks_dir: Path | None = None) -> NotebookStore:
    """Get the module-level singleton store."""
    global _store  # noqa: PLW0603
    if _store is None:
        if notebooks_dir is None:
            notebooks_dir = Path.home() / ".lumen" / "notebooks"
        _store = NotebookStore(notebooks_dir)
    return _store


def reset_store() -> None:
    """Reset the singleton (for testing)."""
    global _store  # noqa: PLW0603
    _store = None
