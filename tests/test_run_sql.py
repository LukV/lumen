"""Tests for run_edited_sql flow."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lumen.agent.agent import run_edited_sql
from lumen.agent.cell import CellResult
from lumen.core import Result

from .conftest import make_config, make_original_cell, make_schema_ctx, mock_narrate_response


@pytest.mark.asyncio
async def test_run_edited_sql_happy_path() -> None:
    """Edited SQL: validate → execute → narrate (no Call 1)."""
    schema_ctx = make_schema_ctx()
    config = make_config()
    original = make_original_cell()

    # Use a 3-row result for the edited query
    edited_result: Result[CellResult] = Result(
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

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=mock_narrate_response("Updated narrative with 3 rows."))

    with (
        patch("lumen.agent.agent.anthropic.Anthropic", return_value=mock_client),
        patch("lumen.agent.agent.execute_query", new_callable=AsyncMock, return_value=edited_result),
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
    schema_ctx = make_schema_ctx()
    config = make_config()
    original = make_original_cell()

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
    schema_ctx = make_schema_ctx()
    config = make_config()
    original = make_original_cell()

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
