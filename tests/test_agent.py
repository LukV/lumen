"""Tests for the agent orchestrator with mocked LLM and executor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumen.agent.agent import ask_question

from .conftest import make_cell_result, make_config, make_schema_ctx, mock_narrate_response, mock_plan_response


@pytest.mark.asyncio
async def test_full_flow() -> None:
    """Test the happy path: question → SQL → execute → narrate → cell."""
    schema_ctx = make_schema_ctx()
    config = make_config()

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(side_effect=[mock_plan_response(), mock_narrate_response()])

    with (
        patch("lumen.agent.agent.anthropic.Anthropic", return_value=mock_client),
        patch("lumen.agent.agent.execute_query", new_callable=AsyncMock, return_value=make_cell_result()),
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
    schema_ctx = make_schema_ctx()
    config = make_config()

    # First call returns bad SQL result, second returns good
    error_result = make_cell_result()
    error_result.data = None
    error_result.error("SQL_ERROR", "column 'revnue' does not exist")

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(
        side_effect=[mock_plan_response(), mock_plan_response(), mock_narrate_response()]
    )

    with (
        patch("lumen.agent.agent.anthropic.Anthropic", return_value=mock_client),
        patch(
            "lumen.agent.agent.execute_query",
            new_callable=AsyncMock,
            side_effect=[error_result, make_cell_result()],
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
    schema_ctx = make_schema_ctx()
    config = make_config()

    # Return an invalid chart spec (missing mark)
    bad_spec = {"encoding": {"x": {"field": "nonexistent"}}}

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(
        side_effect=[mock_plan_response(chart_spec=bad_spec), mock_narrate_response()]
    )

    with (
        patch("lumen.agent.agent.anthropic.Anthropic", return_value=mock_client),
        patch("lumen.agent.agent.execute_query", new_callable=AsyncMock, return_value=make_cell_result()),
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
    schema_ctx = make_schema_ctx()
    config = make_config()

    with patch.dict("os.environ", {}, clear=True):
        events = []
        async for event in ask_question("test?", schema_ctx, config):
            events.append(event)

    assert len(events) == 1
    assert events[0].event == "error"
    assert "API key" in events[0].data["message"]
