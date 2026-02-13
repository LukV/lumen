"""LLM-generated suggestion questions, cached per schema hash."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

import anthropic

from lumen.config import LumenConfig, project_dir
from lumen.core import Result
from lumen.schema.context import SchemaContext, to_xml

logger = logging.getLogger("lumen.suggestions")


class SuggestionsCache:
    """In-memory representation of cached suggestions."""

    def __init__(self, schema_hash: str, suggestions: list[str]) -> None:
        self.schema_hash = schema_hash
        self.suggestions = suggestions


def _cache_path(connection_name: str) -> Path:
    return project_dir(connection_name) / "suggestions_cache.json"


def load_cached_suggestions(connection_name: str) -> SuggestionsCache | None:
    """Load cached suggestions from disk, or None if not found."""
    path = _cache_path(connection_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return SuggestionsCache(
            schema_hash=data["schema_hash"],
            suggestions=data["suggestions"],
        )
    except (json.JSONDecodeError, KeyError):
        return None


def save_suggestions_cache(connection_name: str, cache: SuggestionsCache) -> None:
    """Persist suggestions cache to disk."""
    path = _cache_path(connection_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_hash": cache.schema_hash, "suggestions": cache.suggestions}, indent=2) + "\n")


_SYSTEM_PROMPT = """\
You are a data analyst assistant. Given the database schema below, generate 10 diverse, \
natural-language questions that a business user might ask about this data.

{schema_xml}

## Rules
1. Each question must be specific to the schema — reference real tables and concepts.
2. Vary question types: trends, comparisons, top-N, aggregations, distributions, outliers.
3. Use natural language a non-technical person would use. No SQL syntax or column names.
4. Keep each question under 60 characters.
5. Return a JSON array of 10 strings, nothing else."""


def generate_suggestions(schema_ctx: SchemaContext, config: LumenConfig) -> Result[list[str]]:
    """Generate suggestion questions via LLM, returning up to 10 questions."""
    result: Result[list[str]] = Result()

    api_key = os.environ.get(config.llm.api_key_env, "")
    if not api_key:
        result.error("CONFIG_ERROR", f"Missing API key: {config.llm.api_key_env}")
        return result

    schema_xml = to_xml(schema_ctx)
    system = _SYSTEM_PROMPT.format(schema_xml=schema_xml)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=config.llm.model,
            max_tokens=1024,
            temperature=0.7,
            system=system,
            messages=[{"role": "user", "content": "Generate 10 suggestion questions."}],
        )

        # Extract text from response
        text = ""
        for block in response.content:
            if block.type == "text":
                text = block.text
                break

        if not text:
            result.error("PARSE_ERROR", "LLM returned no text content")
            return result

        # Strip markdown fences if present
        text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
        text = re.sub(r"\n?```\s*$", "", text.strip())

        suggestions = json.loads(text)
        if not isinstance(suggestions, list):
            result.error("PARSE_ERROR", "LLM response is not a JSON array")
            return result

        result.data = [str(s) for s in suggestions[:10]]
    except json.JSONDecodeError as e:
        result.error("PARSE_ERROR", f"Failed to parse LLM response as JSON: {e}")
    except anthropic.APIError as e:
        result.error("API_ERROR", f"Anthropic API error: {e}")

    return result
