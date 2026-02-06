"""Tests for the agent orchestrator with mocked LLM and executor."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumen.agent.agent import ask_question
from lumen.agent.cell import CellResult
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


def _mock_plan_response(
    sql: str = "SELECT name, revenue FROM customers",
    chart_spec: dict[str, Any] | None = None,
) -> MagicMock:
    """Create a mock Anthropic response with a plan_query tool use."""
    if chart_spec is None:
        chart_spec = {
            "mark": {"type": "bar"},
            "encoding": {
                "x": {"field": "name", "type": "nominal"},
                "y": {"field": "revenue", "type": "quantitative"},
            },
            "width": "container",
        }
    block = MagicMock()
    block.type = "tool_use"
    block.name = "plan_query"
    block.input = {"reasoning": "Test reasoning", "sql": sql, "chart_spec": chart_spec}
    response = MagicMock()
    response.content = [block]
    return response


def _mock_narrate_response(narrative: str = "Test narrative with $1000 value.") -> MagicMock:
    """Create a mock Anthropic response with a narrate_results tool use."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = "narrate_results"
    block.input = {
        "narrative": narrative,
        "data_references": [{"ref_id": "r1", "text": "$1000", "source": "revenue column"}],
    }
    response = MagicMock()
    response.content = [block]
    return response


def _mock_cell_result() -> Result[CellResult]:
    r: Result[CellResult] = Result(
        data=CellResult(
            columns=["name", "revenue"],
            column_types=["str", "float"],
            row_count=2,
            data=[{"name": "Acme", "revenue": 1000}, {"name": "Beta", "revenue": 500}],
            execution_time_ms=10,
        )
    )
    return r


@pytest.mark.asyncio
async def test_full_flow() -> None:
    """Test the happy path: question → SQL → execute → narrate → cell."""
    schema_ctx = _make_schema_ctx()
    config = _make_config()

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(side_effect=[_mock_plan_response(), _mock_narrate_response()])

    with (
        patch("lumen.agent.agent.anthropic.Anthropic", return_value=mock_client),
        patch("lumen.agent.agent.execute_query", new_callable=AsyncMock, return_value=_mock_cell_result()),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        events = []
        async for event in ask_question("top customers?", schema_ctx, config):
            events.append(event)

    # Check stages
    stages = [e.data["stage"] for e in events if e.event == "stage"]
    assert "thinking" in stages
    assert "executing" in stages
    assert "narrating" in stages

    # Check cell
    cell_events = [e for e in events if e.event == "cell"]
    assert len(cell_events) == 1
    cell_data = cell_events[0].data
    assert cell_data["question"] == "top customers?"
    assert cell_data["sql"]["query"] == "SELECT name, revenue FROM customers"
    assert cell_data["narrative"]["text"] == "Test narrative with $1000 value."


@pytest.mark.asyncio
async def test_retry_on_sql_error() -> None:
    """Test that SQL execution errors trigger retry with correcting stage."""
    schema_ctx = _make_schema_ctx()
    config = _make_config()

    # First call returns bad SQL result, second returns good
    error_result: Result[CellResult] = Result()
    error_result.error("SQL_ERROR", "column 'revnue' does not exist")

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(
        side_effect=[_mock_plan_response(), _mock_plan_response(), _mock_narrate_response()]
    )

    with (
        patch("lumen.agent.agent.anthropic.Anthropic", return_value=mock_client),
        patch(
            "lumen.agent.agent.execute_query",
            new_callable=AsyncMock,
            side_effect=[error_result, _mock_cell_result()],
        ),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        events = []
        async for event in ask_question("revenue?", schema_ctx, config):
            events.append(event)

    stages = [e.data["stage"] for e in events if e.event == "stage"]
    assert "correcting" in stages

    cell_events = [e for e in events if e.event == "cell"]
    assert len(cell_events) == 1
    assert cell_events[0].data["metadata"]["retry_count"] == 1


@pytest.mark.asyncio
async def test_chart_fallback_to_auto_detect() -> None:
    """Test that invalid chart spec triggers auto_detect fallback."""
    schema_ctx = _make_schema_ctx()
    config = _make_config()

    # Return an invalid chart spec (missing mark)
    bad_spec = {"encoding": {"x": {"field": "nonexistent"}}}

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(
        side_effect=[_mock_plan_response(chart_spec=bad_spec), _mock_narrate_response()]
    )

    with (
        patch("lumen.agent.agent.anthropic.Anthropic", return_value=mock_client),
        patch("lumen.agent.agent.execute_query", new_callable=AsyncMock, return_value=_mock_cell_result()),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        events = []
        async for event in ask_question("test?", schema_ctx, config):
            events.append(event)

    cell_events = [e for e in events if e.event == "cell"]
    assert len(cell_events) == 1
    assert cell_events[0].data["chart"]["auto_detected"] is True


@pytest.mark.asyncio
async def test_missing_api_key() -> None:
    """Test that missing API key produces an error event."""
    schema_ctx = _make_schema_ctx()
    config = _make_config()

    with patch.dict("os.environ", {}, clear=True):
        events = []
        async for event in ask_question("test?", schema_ctx, config):
            events.append(event)

    assert len(events) == 1
    assert events[0].event == "error"
    assert "API key" in events[0].data["message"]
