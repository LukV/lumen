"""Pydantic models for LLM tool output validation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from lumen.cell import DataReference


class PlanQueryOutput(BaseModel):
    """Validated output from the plan_query tool."""

    reasoning: str
    sql: str
    chart_spec: dict[str, Any]


class NarrateOutput(BaseModel):
    """Validated output from the narrate_results tool."""

    narrative: str
    data_references: list[DataReference] = Field(default_factory=list)
