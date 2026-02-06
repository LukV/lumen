"""Build conversation context from previous cells for multi-turn agent prompts."""

from __future__ import annotations

from lumen.agent.cell import Cell


def build_conversation_context(cells: list[Cell], *, max_turns: int = 5) -> str:
    """Build an XML block summarizing recent conversation turns.

    Includes question, SQL, and narrative (omits raw data to save tokens).
    Returns empty string if no cells.
    """
    if not cells:
        return ""

    recent = cells[-max_turns:]
    lines: list[str] = ["<conversation_so_far>"]

    for i, cell in enumerate(recent, start=1):
        lines.append(f'<turn number="{i}">')
        lines.append(f"  <question>{_escape_xml(cell.question)}</question>")
        if cell.sql:
            lines.append(f"  <sql>{_escape_xml(cell.sql.query)}</sql>")
        if cell.result:
            lines.append(f"  <row_count>{cell.result.row_count}</row_count>")
        if cell.narrative:
            lines.append(f"  <insight>{_escape_xml(cell.narrative.text)}</insight>")
        lines.append("</turn>")

    lines.append("</conversation_so_far>")
    return "\n".join(lines)


def build_refinement_context(parent_cell: Cell) -> str:
    """Build rich context from a parent cell for refinement prompts.

    Includes question, full SQL, column names, row count, and narrative.
    """
    lines: list[str] = ["<parent_cell>"]
    lines.append(f"  <question>{_escape_xml(parent_cell.question)}</question>")

    if parent_cell.sql:
        lines.append(f"  <sql>{_escape_xml(parent_cell.sql.query)}</sql>")

    if parent_cell.result:
        lines.append(f"  <columns>{', '.join(parent_cell.result.columns)}</columns>")
        lines.append(f"  <row_count>{parent_cell.result.row_count}</row_count>")

    if parent_cell.narrative:
        lines.append(f"  <insight>{_escape_xml(parent_cell.narrative.text)}</insight>")

    lines.append("</parent_cell>")
    return "\n".join(lines)


def _escape_xml(text: str) -> str:
    """Escape XML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
