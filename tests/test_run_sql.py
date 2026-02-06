"""Tests for run_edited_sql flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumen.agent.agent import run_edited_sql
from lumen.agent.cell import Cell, CellChart, CellMetadata, CellNarrative, CellResult, CellSQL
from lumen.config import ConnectionConfig, LumenConfig
from lumen.core import Result
from lumen.schema.context import SchemaContext
from lumen.schema.enricher import EnrichedColumn, EnrichedSchema, EnrichedTable


def _make_schema_ctx() -> SchemaContext:
    return SchemaContext(
        enriched=EnrichedSchema(
            database="testdb",
            tables=[
                EnrichedTable(
                    name="customers",
                    row_count=100,
                    columns=[
                        EnrichedColumn(name="name", data_type="varchar", role="categorical"),
                        EnrichedColumn(name="revenue", data_type="numeric", role="measure_candidate"),
                    ],
                )
            ],
        ),
    )


def _make_config() -> LumenConfig:
    return LumenConfig(
        connections={"test": ConnectionConfig(dsn="postgresql://localhost/test")},
        active_connection="test",
    )


def _make_original_cell() -> Cell:
    return Cell(
        question="Top customers?",
        sql=CellSQL(query="SELECT name, revenue FROM customers ORDER BY revenue DESC LIMIT 10"),
        result=CellResult(
            columns=["name", "revenue"],
            column_types=["str", "float"],
            row_count=2,
            data=[{"name": "Acme", "revenue": 1000}],
        ),
        chart=CellChart(spec={"mark": "bar", "encoding": {}}),
        narrative=CellNarrative(text="Acme leads."),
        metadata=CellMetadata(model="test-model", reasoning="Original reasoning"),
    )


def _mock_cell_result() -> Result[CellResult]:
    return Result(
        data=CellResult(
            columns=["name", "revenue"],
            column_types=["str", "float"],
            row_count=3,
            data=[
                {"name": "Acme", "revenue": 1000},
                {"name": "Beta", "revenue": 500},
                {"name": "Gamma", "revenue": 300},
            ],
            execution_time_ms=15,
        )
    )


def _mock_narrate_response() -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = "narrate_results"
    block.input = {
        "narrative": "Updated narrative with 3 rows.",
        "data_references": [{"ref_id": "r1", "text": "3 rows", "source": "row count"}],
    }
    response = MagicMock()
    response.content = [block]
    return response


@pytest.mark.asyncio
async def test_run_edited_sql_happy_path() -> None:
    """Edited SQL: validate → execute → narrate (no Call 1)."""
    schema_ctx = _make_schema_ctx()
    config = _make_config()
    original = _make_original_cell()

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=_mock_narrate_response())

    with (
        patch("lumen.agent.agent.anthropic.Anthropic", return_value=mock_client),
        patch("lumen.agent.agent.execute_query", new_callable=AsyncMock, return_value=_mock_cell_result()),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        events: list[Any] = []
        async for event in run_edited_sql("SELECT name, revenue FROM customers LIMIT 20", original, schema_ctx, config):
            events.append(event)

    # Should have stages + cell
    stages = [e.data["stage"] for e in events if e.event == "stage"]
    assert "thinking" in stages
    assert "executing" in stages
    assert "narrating" in stages

    cell_events = [e for e in events if e.event == "cell"]
    assert len(cell_events) == 1
    cell_data = cell_events[0].data
    assert cell_data["sql"]["edited_by_user"] is True
    assert cell_data["id"] == original.id
    assert cell_data["question"] == "Top customers?"

    # Only 1 LLM call (narrate), not 2
    assert mock_client.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_run_edited_sql_invalid_sql() -> None:
    """Invalid SQL should produce error event without execution."""
    schema_ctx = _make_schema_ctx()
    config = _make_config()
    original = _make_original_cell()

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
        events: list[Any] = []
        async for event in run_edited_sql("DROP TABLE customers", original, schema_ctx, config):
            events.append(event)

    error_events = [e for e in events if e.event == "error"]
    assert len(error_events) == 1
    assert "validation failed" in error_events[0].data["message"].lower()


@pytest.mark.asyncio
async def test_run_edited_sql_execution_error() -> None:
    """SQL execution error should produce error event."""
    schema_ctx = _make_schema_ctx()
    config = _make_config()
    original = _make_original_cell()

    error_result: Result[CellResult] = Result()
    error_result.error("SQL_ERROR", "column 'bad' does not exist")

    with (
        patch("lumen.agent.agent.execute_query", new_callable=AsyncMock, return_value=error_result),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        events: list[Any] = []
        async for event in run_edited_sql("SELECT bad FROM customers", original, schema_ctx, config):
            events.append(event)

    error_events = [e for e in events if e.event == "error"]
    assert len(error_events) == 1
    assert "execution error" in error_events[0].data["message"].lower()
