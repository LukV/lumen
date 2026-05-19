"""Two-call orchestrator: question → SQL + chart → narrative, streamed as SSE events."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from typing import Any

import anthropic
from pydantic import ValidationError

from lumen.agent.models import NarrateOutput, PlanQueryOutput
from lumen.agent.prompts import (
    EXPLAIN_TOOL,
    NARRATE_TOOL,
    PLAN_TOOL,
    build_explain_prompt,
    build_narrate_prompt,
    build_system_prompt,
)
from lumen.cell import (
    Cell,
    CellChart,
    CellContext,
    CellMetadata,
    CellNarrative,
    CellResult,
    CellSQL,
    DataReference,
)
from lumen.config import LumenConfig
from lumen.datasource.protocol import DataSource
from lumen.schema.context import SchemaContext
from lumen.theme import load_theme
from lumen.viz.auto_detect import auto_detect_chart
from lumen.viz.theme import apply_theme
from lumen.viz.validator import validate_chart_spec

logger = logging.getLogger("lumen.agent")

MAX_RETRIES = 3

# Prefix markers for extracting reasoning from streamed partial JSON.
_REASONING_PREFIXES = ('"reasoning":"', '"reasoning": "')
_REASONING_END_MARKERS = ('","sql"', '", "sql"')


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


def reasoning_event(text: str) -> SSEEvent:
    return SSEEvent("reasoning", {"text": text})


class _StreamResult:
    """Mutable holder for the final message from a streaming call."""

    message: Any = None


def _extract_new_reasoning(json_buffer: str, already_emitted: int) -> str:
    """Extract new reasoning text from accumulated partial JSON fragments."""
    # Find where reasoning value starts
    content_start = -1
    for prefix in _REASONING_PREFIXES:
        idx = json_buffer.find(prefix)
        if idx >= 0:
            content_start = idx + len(prefix)
            break
    if content_start < 0:
        return ""

    content = json_buffer[content_start:]

    # Find where reasoning value ends (next field starts)
    for marker in _REASONING_END_MARKERS:
        end = content.find(marker)
        if end >= 0:
            content = content[:end]
            break

    # Return only new content, decoding JSON escape sequences
    if len(content) > already_emitted:
        chunk = content[already_emitted:]
        return chunk.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    return ""


async def _stream_plan_call(
    client: anthropic.AsyncAnthropic,
    model: str,
    system_prompt: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    tool_choice: dict[str, str],
    result: _StreamResult,
) -> AsyncGenerator[SSEEvent]:
    """Stream a plan call, yielding reasoning SSE events. Stores final message in result."""
    json_buffer = ""
    emitted = 0

    async with client.messages.stream(
        model=model,
        max_tokens=4096,
        temperature=0,
        system=system_prompt,
        messages=messages,  # type: ignore[arg-type]
        tools=tools,  # type: ignore[arg-type]
        tool_choice=tool_choice,  # type: ignore[arg-type]
    ) as stream:
        async for event in stream:
            if hasattr(event, "delta") and hasattr(event.delta, "partial_json"):
                json_buffer += event.delta.partial_json
                chunk = _extract_new_reasoning(json_buffer, emitted)
                if chunk:
                    emitted += len(chunk)
                    yield reasoning_event(chunk)

        result.message = await stream.get_final_message()


async def ask_question(
    question: str,
    schema_ctx: SchemaContext,
    config: LumenConfig,
    datasource: DataSource,
    cells: list[Cell] | None = None,
    parent_cell_id: str | None = None,
) -> AsyncGenerator[SSEEvent]:
    """Run the two-call agent flow, yielding SSE events at each stage.

    Flow:
    1. Call 1: LLM generates SQL + chart spec via plan_query tool (streamed)
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

    client = anthropic.AsyncAnthropic(api_key=api_key)
    model = config.llm.model

    # Resolve parent cell for refinement
    parent_cell: Cell | None = None
    if parent_cell_id and cells:
        for c in cells:
            if c.id == parent_cell_id:
                parent_cell = c
                break

    theme = load_theme(config.active_connection)
    logger.info("ask_question: model=%s question=%r parent=%s", model, question, parent_cell_id)

    # --- Call 1: Plan or explain (streamed) ---
    yield stage_event("thinking")

    system_prompt = build_system_prompt(schema_ctx, cells, parent_cell, dialect=datasource.dialect)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

    # First call: let LLM choose between plan_query and explain_schema
    holder = _StreamResult()
    async for event in _stream_plan_call(
        client, model, system_prompt, messages, [PLAN_TOOL, EXPLAIN_TOOL], {"type": "any"}, holder
    ):
        yield event
    first_response = holder.message

    # Check if LLM chose explain_schema
    explain_input = _extract_tool_input(first_response, "explain_schema")
    if explain_input is not None:
        async for event in _handle_explanation(
            client, model, question, explain_input, schema_ctx, cells, parent_cell_id, theme.locale
        ):
            yield event
        return

    reasoning = ""
    sql = ""
    chart_spec: dict[str, Any] = {}
    retry_count = 0
    agent_steps: list[str] = ["thinking"]

    # Extract plan_query from first response
    tool_input = _extract_tool_input(first_response, "plan_query")

    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            holder = _StreamResult()
            async for event in _stream_plan_call(
                client,
                model,
                system_prompt,
                messages,
                [PLAN_TOOL],
                {"type": "tool", "name": "plan_query"},
                holder,
            ):
                yield event
            tool_input = _extract_tool_input(holder.message, "plan_query")

        if tool_input is None:
            logger.error("LLM did not return plan_query tool call")
            yield error_event("LLM did not return a plan_query tool call")
            return

        try:
            plan = PlanQueryOutput.model_validate(tool_input)
        except ValidationError as exc:
            logger.warning("plan_query output validation failed: %s", exc)
            if attempt < MAX_RETRIES:
                yield stage_event("correcting")
                agent_steps.append("correcting")
                retry_count += 1
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
                                "content": f"Tool output validation failed: {exc}. Please provide all required fields.",
                            },
                        ],
                    }
                )
                continue
            yield error_event(f"plan_query output validation failed after {MAX_RETRIES} retries: {exc}")
            return

        reasoning = plan.reasoning
        sql = plan.sql
        chart_spec = plan.chart_spec
        logger.info("Call 1 result: sql=%r (len=%d)", sql[:80], len(sql))

        # Validate SQL
        validation = datasource.validate_sql(sql)
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

        exec_result = await datasource.execute(
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

    # --- Validate chart spec ---
    auto_detected = False
    spec_validation = validate_chart_spec(chart_spec, cell_result.columns)
    if not spec_validation.ok:
        chart_spec = auto_detect_chart(
            cell_result.columns,
            cell_result.column_types,
            schema_ctx.enriched,
            theme=theme,
        )
        auto_detected = True
    else:
        chart_spec = apply_theme(chart_spec, theme=theme)

    # --- Call 2: Narrate results (async, non-streaming) ---
    yield stage_event("narrating")
    agent_steps.append("narrating")

    narrative_text, data_references = await _narrate(
        client,
        model,
        question,
        sql,
        cell_result,
        locale=theme.locale,
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
        ),
    )

    logger.info("Cell built: id=%s rows=%d", cell.id, cell.result.row_count if cell.result else 0)
    yield cell_event(cell)


async def run_edited_sql(
    sql: str,
    original_cell: Cell,
    schema_ctx: SchemaContext,
    config: LumenConfig,
    datasource: DataSource,
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
    validation = datasource.validate_sql(sql)
    if not validation.ok:
        error_msgs = "; ".join(d.message for d in validation.diagnostics)
        yield error_event(f"SQL validation failed: {error_msgs}", "SQL_VALIDATION_ERROR")
        return

    # Execute
    yield stage_event("executing")
    exec_result = await datasource.execute(
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
    theme = load_theme(config.active_connection)
    chart_spec = auto_detect_chart(
        cell_result.columns,
        cell_result.column_types,
        schema_ctx.enriched,
        theme=theme,
    )

    # Call 2: Narrate (async, non-streaming)
    yield stage_event("narrating")
    client = anthropic.AsyncAnthropic(api_key=api_key)
    model = config.llm.model
    narrative_text, data_references = await _narrate(
        client, model, original_cell.question, sql, cell_result, locale=theme.locale
    )

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
    client: anthropic.AsyncAnthropic,
    model: str,
    question: str,
    sql: str,
    cell_result: CellResult,
    locale: str = "en",
) -> tuple[str, list[DataReference]]:
    """Run Call 2 (narrate_results) and return (text, references)."""
    narrate_prompt = build_narrate_prompt(question, sql, cell_result, locale=locale)
    narrate_response = await client.messages.create(  # type: ignore[call-overload]
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
        try:
            narrate = NarrateOutput.model_validate(narrate_input)
            narrative_text = narrate.narrative
            data_references = narrate.data_references
        except ValidationError as exc:
            logger.warning("narrate_results output validation failed: %s", exc)
            # Graceful fallback: use raw narrative if available
            narrative_text = narrate_input.get("narrative", "")

    return narrative_text, data_references


async def _handle_explanation(
    client: anthropic.AsyncAnthropic,
    model: str,
    question: str,
    explain_input: dict[str, Any],
    schema_ctx: SchemaContext,
    cells: list[Cell] | None,
    parent_cell_id: str | None,
    locale: str,
) -> AsyncGenerator[SSEEvent]:
    """Handle an explanation question — no SQL, no chart, just narrative."""
    reasoning = explain_input.get("reasoning", "")
    narrative_text = explain_input.get("narrative", "")

    # If the first call didn't include a narrative (shouldn't happen, but be safe), do a second call
    if not narrative_text:
        explain_prompt = build_explain_prompt(question, schema_ctx, locale=locale, cells=cells)
        explain_response = await client.messages.create(  # type: ignore[call-overload]
            model=model,
            max_tokens=2048,
            temperature=0,
            system=explain_prompt,
            messages=[{"role": "user", "content": question}],
            tools=[EXPLAIN_TOOL],
            tool_choice={"type": "tool", "name": "explain_schema"},
        )
        fallback_input = _extract_tool_input(explain_response, "explain_schema")
        if fallback_input:
            reasoning = fallback_input.get("reasoning", reasoning)
            narrative_text = fallback_input.get("narrative", "")

    cell = Cell(
        cell_type="explanation",
        question=question,
        context=CellContext(parent_cell_id=parent_cell_id, refinement_of=parent_cell_id),
        narrative=CellNarrative(text=narrative_text),
        metadata=CellMetadata(model=model, agent_steps=["thinking"], reasoning=reasoning),
    )

    logger.info("Explanation cell built: id=%s", cell.id)
    yield cell_event(cell)


def _extract_tool_input(response: Any, tool_name: str) -> dict[str, Any] | None:
    """Extract the input dict from a tool_use content block."""
    for block in response.content:
        if block.type == "tool_use" and block.name == tool_name:
            return block.input  # type: ignore[no-any-return]
    return None
