"""Tests for conversation context builder."""

from __future__ import annotations

from lumen.agent.cell import Cell, CellNarrative, CellResult, CellSQL
from lumen.agent.history import build_conversation_context, build_refinement_context


def _make_cell(question: str, sql: str = "SELECT 1", narrative: str = "Insight.", row_count: int = 5) -> Cell:
    return Cell(
        question=question,
        sql=CellSQL(query=sql),
        result=CellResult(columns=["a", "b"], column_types=["int", "str"], row_count=row_count),
        narrative=CellNarrative(text=narrative),
    )


def test_empty_cells() -> None:
    assert build_conversation_context([]) == ""


def test_single_cell() -> None:
    ctx = build_conversation_context([_make_cell("What is revenue?")])
    assert "<conversation_so_far>" in ctx
    assert '<turn number="1">' in ctx
    assert "<question>What is revenue?</question>" in ctx
    assert "<sql>SELECT 1</sql>" in ctx
    assert "<insight>Insight.</insight>" in ctx
    assert "</conversation_so_far>" in ctx


def test_respects_max_turns() -> None:
    cells = [_make_cell(f"Q{i}") for i in range(10)]
    ctx = build_conversation_context(cells, max_turns=3)
    # Should only have turns 1-3 (from the last 3 cells)
    assert '<turn number="1">' in ctx
    assert '<turn number="3">' in ctx
    assert '<turn number="4">' not in ctx
    # Content should be from the last 3 cells (Q7, Q8, Q9)
    assert "Q7" in ctx
    assert "Q8" in ctx
    assert "Q9" in ctx
    assert "Q6" not in ctx


def test_escapes_xml_special_chars() -> None:
    cell = _make_cell("Revenue > $100 & < $200")
    ctx = build_conversation_context([cell])
    assert "&gt;" in ctx
    assert "&amp;" in ctx
    assert "&lt;" in ctx


def test_cell_without_sql() -> None:
    cell = Cell(question="test?")
    ctx = build_conversation_context([cell])
    assert "<question>test?</question>" in ctx
    assert "<sql>" not in ctx


def test_cell_without_narrative() -> None:
    cell = Cell(question="test?", sql=CellSQL(query="SELECT 1"))
    ctx = build_conversation_context([cell])
    assert "<sql>SELECT 1</sql>" in ctx
    assert "<insight>" not in ctx


def test_row_count_included() -> None:
    ctx = build_conversation_context([_make_cell("test?", row_count=42)])
    assert "<row_count>42</row_count>" in ctx


def test_build_refinement_context() -> None:
    cell = _make_cell("Top customers?", sql="SELECT name FROM customers", narrative="Acme leads.", row_count=10)
    ctx = build_refinement_context(cell)
    assert "<parent_cell>" in ctx
    assert "<question>Top customers?</question>" in ctx
    assert "<sql>SELECT name FROM customers</sql>" in ctx
    assert "<columns>a, b</columns>" in ctx
    assert "<row_count>10</row_count>" in ctx
    assert "<insight>Acme leads.</insight>" in ctx
    assert "</parent_cell>" in ctx


def test_refinement_context_minimal_cell() -> None:
    cell = Cell(question="test?")
    ctx = build_refinement_context(cell)
    assert "<parent_cell>" in ctx
    assert "<question>test?</question>" in ctx
    assert "<sql>" not in ctx
    assert "</parent_cell>" in ctx
