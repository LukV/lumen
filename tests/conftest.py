"""Shared test fixtures for lumen tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from lumen.agent.cell import Cell, CellChart, CellMetadata, CellNarrative, CellResult, CellSQL
from lumen.config import ConnectionConfig, LumenConfig
from lumen.core import Result
from lumen.schema.context import SchemaContext
from lumen.schema.enricher import EnrichedColumn, EnrichedSchema, EnrichedTable


def make_schema_ctx() -> SchemaContext:
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


def make_config() -> LumenConfig:
    return LumenConfig(
        connections={"test": ConnectionConfig(dsn="postgresql://localhost/test")},
        active_connection="test",
    )


def make_cell_result() -> Result[CellResult]:
    return Result(
        data=CellResult(
            columns=["name", "revenue"],
            column_types=["str", "float"],
            row_count=2,
            data=[{"name": "Acme", "revenue": 1000}, {"name": "Beta", "revenue": 500}],
            execution_time_ms=10,
        )
    )


def make_original_cell() -> Cell:
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


def mock_plan_response(
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


def mock_narrate_response(narrative: str = "Test narrative with $1000 value.") -> MagicMock:
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
