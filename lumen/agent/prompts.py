"""System prompt templates and Anthropic tool definitions for the agent."""

from __future__ import annotations

from typing import Any

from lumen.agent.cell import Cell, CellResult
from lumen.agent.history import build_conversation_context, build_refinement_context
from lumen.schema.context import SchemaContext, to_xml

PLAN_TOOL: dict[str, Any] = {
    "name": "plan_query",
    "description": (
        "Plan and generate a SQL query to answer the user's question, "
        "along with a Vega-Lite chart specification for visualizing the results."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Step-by-step reasoning about how to answer the question using the available schema.",
            },
            "sql": {
                "type": "string",
                "description": (
                    "A single Postgres SELECT statement. Must be read-only. "
                    "Use CTEs for clarity. Include ORDER BY and LIMIT where appropriate."
                ),
            },
            "chart_spec": {
                "type": "object",
                "description": (
                    "A Vega-Lite v5 specification object. Must include 'mark' and 'encoding'. "
                    "Use field names that match the SQL SELECT column aliases. "
                    "Set width to 'container'."
                ),
            },
        },
        "required": ["reasoning", "sql", "chart_spec"],
    },
}

NARRATE_TOOL: dict[str, Any] = {
    "name": "narrate_results",
    "description": "Generate a concise narrative insight from the query results, with data references.",
    "input_schema": {
        "type": "object",
        "properties": {
            "narrative": {
                "type": "string",
                "description": (
                    "A 2-4 sentence insight about the data. Reference specific values. "
                    "Be direct and analytical, not generic."
                ),
            },
            "data_references": {
                "type": "array",
                "description": "Specific data points referenced in the narrative.",
                "items": {
                    "type": "object",
                    "properties": {
                        "ref_id": {"type": "string", "description": "Unique ID like 'r1', 'r2'"},
                        "text": {
                            "type": "string",
                            "description": (
                                "The exact text substring from the narrative that references this data point."
                            ),
                        },
                        "source": {
                            "type": "string",
                            "description": "Where this value comes from (e.g., 'row 1, revenue column').",
                        },
                    },
                    "required": ["ref_id", "text", "source"],
                },
            },
        },
        "required": ["narrative", "data_references"],
    },
}


def build_system_prompt(
    schema_ctx: SchemaContext,
    cells: list[Cell] | None = None,
    parent_cell: Cell | None = None,
) -> str:
    """Build the system prompt for Call 1 (plan_query).

    Includes schema XML, rules, conversation context from previous cells,
    and optional refinement context from a parent cell.
    """
    schema_xml = to_xml(schema_ctx)

    parts = [
        "You are Lumen, an expert data analyst. You answer questions about data by writing SQL queries "
        "and creating visualizations.",
        "",
        "## Database Schema",
        schema_xml,
        "",
        "## Rules",
        "1. Write a single Postgres SELECT statement. Never write INSERT, UPDATE, DELETE, DROP, or any DDL/DML.",
        "2. Use CTEs (WITH clauses) for complex queries to improve readability.",
        "3. Always include ORDER BY for meaningful ordering.",
        "4. Include LIMIT when returning individual records (default LIMIT 100).",
        "5. Use aggregate functions (SUM, AVG, COUNT, etc.) when the question implies aggregation.",
        "6. Alias columns with clear, readable names using AS.",
        "7. For the chart_spec: use Vega-Lite v5. Field names must exactly match SQL column aliases.",
        "8. Set chart width to 'container'. Choose appropriate mark types (bar, line, point, etc.).",
        "9. For bar charts with categorical data, sort by the measure descending (sort: '-y').",
    ]

    # Conversation context from previous cells
    if cells:
        conv_ctx = build_conversation_context(cells)
        if conv_ctx:
            parts.append("")
            parts.append("## Conversation So Far")
            parts.append(conv_ctx)

    # Refinement context
    if parent_cell:
        ref_ctx = build_refinement_context(parent_cell)
        parts.append("")
        parts.append("## Refinement Context")
        parts.append(
            "The user is refining a previous question. Use the parent cell context below "
            "to understand what was previously asked and build upon it."
        )
        parts.append(ref_ctx)

    return "\n".join(parts)


def build_narrate_prompt(question: str, sql: str, result: CellResult) -> str:
    """Build the system prompt for Call 2 (narrate_results)."""
    data_text = format_result_for_llm(result)

    return "\n".join(
        [
            "You are Lumen, an expert data analyst. Based on the query results below, "
            "write a concise narrative insight.",
            "",
            f"## Question: {question}",
            "",
            f"## SQL Query\n```sql\n{sql}\n```",
            "",
            f"## Results ({result.row_count} rows)\n{data_text}",
            "",
            "## Instructions",
            "1. Write 2-4 sentences highlighting the key findings.",
            "2. Reference specific data values (numbers, names) from the results.",
            "3. Be analytical and direct — state what the data shows, not generic observations.",
            "4. Include data_references for each specific value you mention.",
        ]
    )


def format_result_for_llm(result: CellResult) -> str:
    """Format query results as a text table for the LLM context.

    Truncates to first 50 rows for context efficiency.
    """
    if not result.data:
        return "(no data)"

    display_rows = result.data[:50]
    columns = result.columns

    if not columns:
        return "(no columns)"

    # Simple text table
    lines: list[str] = []
    lines.append(" | ".join(columns))
    lines.append(" | ".join("---" for _ in columns))

    for row in display_rows:
        values = [str(row.get(col, "")) for col in columns]
        lines.append(" | ".join(values))

    if result.row_count > 50:
        lines.append(f"... ({result.row_count - 50} more rows)")

    return "\n".join(lines)
