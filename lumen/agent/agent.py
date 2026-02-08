"""Two-call orchestrator: question → SQL + chart → narrative, streamed as SSE events."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

import anthropic

from lumen.agent.cell import (
    Cell,
    CellChart,
    CellContext,
    CellMetadata,
    CellNarrative,
    CellResult,
    CellSQL,
    DataReference,
    WhatIfMetadata,
)
from lumen.agent.executor import execute_query
from lumen.agent.prompts import (
    NARRATE_TOOL,
    PLAN_TOOL,
    build_narrate_prompt,
    build_system_prompt,
)
from lumen.agent.sql_validator import validate_sql
from lumen.config import LumenConfig
from lumen.schema.context import SchemaContext
from lumen.viz.auto_detect import auto_detect_chart
from lumen.viz.theme import apply_theme
from lumen.viz.validator import validate_chart_spec
from lumen.whatif.chart import build_trend_chart
from lumen.whatif.explain import generate_caveats
from lumen.whatif.trend import TrendParams, build_trend_sql

logger = logging.getLogger("lumen.agent")

MAX_RETRIES = 3


class SSEEvent:
    """Base class for SSE events."""

    def __init__(self, event: str, data: dict[str, Any]) -> None:
        self.event = event
        self.data = data

    def to_dict(self) -> dict[str, Any]:
        return {"event": self.event, "data": self.data}


def stage_event(stage: str) -> SSEEvent:
    return SSEEvent("stage", {"stage": stage})


def cell_event(cell: Cell) -> SSEEvent:
    return SSEEvent("cell", cell.model_dump())


def error_event(message: str, code: str = "AGENT_ERROR") -> SSEEvent:
    return SSEEvent("error", {"code": code, "message": message})


async def ask_question(
    question: str,
    schema_ctx: SchemaContext,
    config: LumenConfig,
    cells: list[Cell] | None = None,
    parent_cell_id: str | None = None,
) -> AsyncGenerator[SSEEvent]:
    """Run the two-call agent flow, yielding SSE events at each stage.

    Flow:
    1. Call 1: LLM generates SQL + chart spec via plan_query tool
    2. Validate SQL with pglast
    3. Execute query via asyncpg
    4. On error: retry up to 3x, feeding error back to LLM
    5. Validate chart spec; fallback to auto_detect if invalid
    6. Call 2: LLM generates narrative via narrate_results tool
    7. Build and yield complete Cell
    """
    api_key = os.environ.get(config.llm.api_key_env, "")
    if not api_key:
        logger.error("Missing API key: %s", config.llm.api_key_env)
        yield error_event(f"Missing API key: set {config.llm.api_key_env} environment variable", "CONFIG_ERROR")
        return

    client = anthropic.Anthropic(api_key=api_key)
    model = config.llm.model

    # Resolve parent cell for refinement
    parent_cell: Cell | None = None
    if parent_cell_id and cells:
        for c in cells:
            if c.id == parent_cell_id:
                parent_cell = c
                break

    logger.info("ask_question: model=%s question=%r parent=%s", model, question, parent_cell_id)

    # --- Call 1: Plan query ---
    yield stage_event("thinking")

    system_prompt = build_system_prompt(schema_ctx, cells, parent_cell)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

    reasoning = ""
    sql = ""
    chart_spec: dict[str, Any] = {}
    retry_count = 0
    agent_steps: list[str] = ["thinking"]

    for attempt in range(MAX_RETRIES + 1):
        response = client.messages.create(  # type: ignore[call-overload]
            model=model,
            max_tokens=4096,
            temperature=0,
            system=system_prompt,
            messages=messages,
            tools=[PLAN_TOOL],
            tool_choice={"type": "tool", "name": "plan_query"},
        )

        # Extract tool_use block
        tool_input = _extract_tool_input(response, "plan_query")
        if tool_input is None:
            logger.error("LLM did not return plan_query tool call. Content: %s", response.content)
            yield error_event("LLM did not return a plan_query tool call")
            return

        reasoning = tool_input.get("reasoning", "")
        sql = tool_input.get("sql", "")
        chart_spec = tool_input.get("chart_spec", {})
        whatif_input: dict[str, Any] | None = tool_input.get("whatif")
        logger.info("Call 1 result: sql=%r (len=%d)", sql[:80], len(sql))

        # Validate SQL
        validation = validate_sql(sql)
        if not validation.ok:
            error_msgs = "; ".join(d.message for d in validation.diagnostics)
            if attempt < MAX_RETRIES:
                yield stage_event("correcting")
                agent_steps.append("correcting")
                retry_count += 1
                # Feed error back to LLM
                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "id": f"retry_{attempt}", "name": "plan_query", "input": tool_input},
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": f"retry_{attempt}",
                                "content": f"SQL validation failed: {error_msgs}. Please fix and try again.",
                            },
                        ],
                    }
                )
                continue
            yield error_event(f"SQL validation failed after {MAX_RETRIES} retries: {error_msgs}")
            return

        # --- Execute SQL ---
        yield stage_event("executing")
        agent_steps.append("executing")

        dsn = _get_dsn(config)
        exec_result = await execute_query(
            dsn,
            sql,
            timeout_seconds=config.settings.statement_timeout_seconds,
            max_rows=config.settings.max_result_rows,
        )

        rd = exec_result.data
        logger.info("Query executed: rows=%d time=%dms", rd.row_count if rd else 0, rd.execution_time_ms if rd else 0)

        if exec_result.has_errors:
            error_msgs = "; ".join(d.message for d in exec_result.diagnostics if d.severity == "error")
            logger.warning("SQL error (attempt %d): %s", attempt, error_msgs)
            hints = "; ".join(d.hint for d in exec_result.diagnostics if d.hint)
            if attempt < MAX_RETRIES:
                yield stage_event("correcting")
                agent_steps.append("correcting")
                retry_count += 1
                feedback = f"SQL execution error: {error_msgs}"
                if hints:
                    feedback += f"\nHints: {hints}"
                messages.append(
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "id": f"retry_{attempt}", "name": "plan_query", "input": tool_input},
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {"type": "tool_result", "tool_use_id": f"retry_{attempt}", "content": feedback},
                        ],
                    }
                )
                continue
            yield error_event(f"SQL execution failed after {MAX_RETRIES} retries: {error_msgs}")
            return

        # Success — break retry loop
        break

    cell_result = exec_result.data
    if cell_result is None:
        yield error_event("No result data from execution")
        return

    # --- What-if trend extrapolation ---
    is_whatif = False
    whatif_caveats: list[str] = []
    whatif_meta: WhatIfMetadata | None = None

    if whatif_input and whatif_input.get("technique") == "trend_extrapolation":
        yield stage_event("projecting")
        agent_steps.append("projecting")

        trend_params = TrendParams(
            time_field=whatif_input.get("time_field", ""),
            measure=whatif_input.get("measure", ""),
            periods_ahead=whatif_input.get("periods_ahead", 3),
            period_interval=whatif_input.get("period_interval", "month"),
        )
        trend_result = build_trend_sql(sql, params=trend_params)

        if trend_result.ok and trend_result.data is not None:
            # Re-execute with wrapped SQL
            trend_sql = trend_result.data.sql
            logger.info("Trend SQL built, re-executing wrapped query")

            trend_exec = await execute_query(
                dsn,
                trend_sql,
                timeout_seconds=config.settings.statement_timeout_seconds,
                max_rows=config.settings.max_result_rows,
            )

            if trend_exec.ok and trend_exec.data is not None:
                sql = trend_sql
                cell_result = trend_exec.data
                is_whatif = True
                whatif_caveats = generate_caveats(
                    "trend_extrapolation",
                    {
                        "periods_ahead": trend_params.periods_ahead,
                        "period_interval": trend_params.period_interval,
                    },
                )
                whatif_meta = WhatIfMetadata(
                    technique="trend_extrapolation",
                    parameters={
                        "time_field": trend_params.time_field,
                        "measure": trend_params.measure,
                        "periods_ahead": trend_params.periods_ahead,
                        "period_interval": trend_params.period_interval,
                    },
                    caveats=whatif_caveats,
                )
            else:
                logger.warning("Trend SQL execution failed, falling back to baseline")
        else:
            logger.warning("Trend SQL build failed: %s", trend_result.diagnostics)

    # --- Validate chart spec ---
    auto_detected = False
    if is_whatif and whatif_input:
        # Override chart with layered trend chart
        chart_spec = build_trend_chart(
            whatif_input.get("time_field", ""),
            whatif_input.get("measure", ""),
        )
        auto_detected = True
    else:
        spec_validation = validate_chart_spec(chart_spec, cell_result.columns)
        if not spec_validation.ok:
            chart_spec = auto_detect_chart(
                cell_result.columns,
                cell_result.column_types,
                schema_ctx.enriched,
            )
            auto_detected = True
        else:
            chart_spec = apply_theme(chart_spec)

    # --- Call 2: Narrate results ---
    yield stage_event("narrating")
    agent_steps.append("narrating")

    narrative_text, data_references = await _narrate(
        client,
        model,
        question,
        sql,
        cell_result,
        caveats=whatif_caveats if is_whatif else None,
    )

    # --- Build Cell ---
    cell = Cell(
        question=question,
        context=CellContext(
            parent_cell_id=parent_cell_id,
            refinement_of=parent_cell_id,
        ),
        sql=CellSQL(query=sql),
        result=cell_result,
        chart=CellChart(spec=chart_spec, auto_detected=auto_detected),
        narrative=CellNarrative(text=narrative_text, data_references=data_references),
        metadata=CellMetadata(
            model=model,
            agent_steps=agent_steps,
            retry_count=retry_count,
            reasoning=reasoning,
            whatif=whatif_meta,
        ),
    )

    logger.info("Cell built: id=%s rows=%d", cell.id, cell.result.row_count if cell.result else 0)
    yield cell_event(cell)


async def run_edited_sql(
    sql: str,
    original_cell: Cell,
    schema_ctx: SchemaContext,
    config: LumenConfig,
) -> AsyncGenerator[SSEEvent]:
    """Execute user-edited SQL: validate → execute → narrate (Call 2 only).

    Skips Call 1 (plan_query) since the user provided the SQL directly.
    """
    api_key = os.environ.get(config.llm.api_key_env, "")
    if not api_key:
        yield error_event(f"Missing API key: set {config.llm.api_key_env} environment variable", "CONFIG_ERROR")
        return

    # Validate SQL
    yield stage_event("thinking")
    validation = validate_sql(sql)
    if not validation.ok:
        error_msgs = "; ".join(d.message for d in validation.diagnostics)
        yield error_event(f"SQL validation failed: {error_msgs}", "SQL_VALIDATION_ERROR")
        return

    # Execute
    yield stage_event("executing")
    dsn = _get_dsn(config)
    exec_result = await execute_query(
        dsn,
        sql,
        timeout_seconds=config.settings.statement_timeout_seconds,
        max_rows=config.settings.max_result_rows,
    )

    if exec_result.has_errors:
        error_msgs = "; ".join(d.message for d in exec_result.diagnostics if d.severity == "error")
        yield error_event(f"SQL execution error: {error_msgs}", "SQL_ERROR")
        return

    cell_result = exec_result.data
    if cell_result is None:
        yield error_event("No result data from execution")
        return

    # Auto-detect chart for edited SQL
    chart_spec = auto_detect_chart(
        cell_result.columns,
        cell_result.column_types,
        schema_ctx.enriched,
    )

    # Call 2: Narrate
    yield stage_event("narrating")
    client = anthropic.Anthropic(api_key=api_key)
    model = config.llm.model
    narrative_text, data_references = await _narrate(client, model, original_cell.question, sql, cell_result)

    # Build updated cell
    cell = Cell(
        id=original_cell.id,
        created_at=original_cell.created_at,
        question=original_cell.question,
        context=original_cell.context,
        sql=CellSQL(query=sql, edited_by_user=True),
        result=cell_result,
        chart=CellChart(spec=chart_spec, auto_detected=True),
        narrative=CellNarrative(text=narrative_text, data_references=data_references),
        metadata=CellMetadata(
            model=model,
            agent_steps=["executing", "narrating"],
            reasoning=original_cell.metadata.reasoning,
        ),
    )

    yield cell_event(cell)


async def _narrate(
    client: anthropic.Anthropic,
    model: str,
    question: str,
    sql: str,
    cell_result: CellResult,
    caveats: list[str] | None = None,
) -> tuple[str, list[DataReference]]:
    """Run Call 2 (narrate_results) and return (text, references)."""
    narrate_prompt = build_narrate_prompt(question, sql, cell_result, caveats=caveats)
    narrate_response = client.messages.create(  # type: ignore[call-overload]
        model=model,
        max_tokens=1024,
        temperature=0,
        system=narrate_prompt,
        messages=[{"role": "user", "content": "Generate the narrative insight."}],
        tools=[NARRATE_TOOL],
        tool_choice={"type": "tool", "name": "narrate_results"},
    )

    narrate_input = _extract_tool_input(narrate_response, "narrate_results")
    logger.info("Call 2 complete: has_narrative=%s", narrate_input is not None)

    narrative_text = ""
    data_references: list[DataReference] = []
    if narrate_input:
        narrative_text = narrate_input.get("narrative", "")
        for ref in narrate_input.get("data_references", []):
            data_references.append(
                DataReference(
                    ref_id=ref.get("ref_id", ""),
                    text=ref.get("text", ""),
                    source=ref.get("source", ""),
                )
            )

    return narrative_text, data_references


def _extract_tool_input(response: Any, tool_name: str) -> dict[str, Any] | None:
    """Extract the input dict from a tool_use content block."""
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input  # type: ignore[no-any-return]
    return None


def _get_dsn(config: LumenConfig) -> str:
    """Get the DSN for the active connection."""
    if config.active_connection and config.active_connection in config.connections:
        return config.connections[config.active_connection].dsn
    # Fallback to first connection
    for conn in config.connections.values():
        return conn.dsn
    return ""
