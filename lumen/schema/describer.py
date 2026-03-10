"""LLM-generated table descriptions, cached per schema hash."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import anthropic

from lumen.config import LumenConfig, project_dir
from lumen.core import Result
from lumen.schema.context import SchemaContext, to_xml
from lumen.theme import load_theme

logger = logging.getLogger("lumen.describer")


class DescriptionsCache:
    """In-memory representation of cached table descriptions."""

    def __init__(self, schema_hash: str, descriptions: dict[str, str]) -> None:
        self.schema_hash = schema_hash
        self.descriptions = descriptions


def _cache_path(connection_name: str) -> Path:
    return project_dir(connection_name) / "descriptions_cache.json"


def load_cached_descriptions(connection_name: str) -> DescriptionsCache | None:
    """Load cached descriptions from disk, or None if not found."""
    path = _cache_path(connection_name)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return DescriptionsCache(
            schema_hash=data["schema_hash"],
            descriptions=data["descriptions"],
        )
    except (json.JSONDecodeError, KeyError):
        return None


def save_descriptions_cache(connection_name: str, cache: DescriptionsCache) -> None:
    """Persist descriptions cache to disk."""
    path = _cache_path(connection_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema_hash": cache.schema_hash, "descriptions": cache.descriptions}, indent=2) + "\n"
    )


_SYSTEM_PROMPT = """\
You are a data analyst assistant. Given the database schema below, generate a short description \
for each table that a non-technical user would understand.

{schema_xml}

## Rules
1. For each table, write ONE sentence (under 80 characters) describing what data it contains.
2. Use plain language, not technical jargon. Focus on the business meaning.
3. Return a JSON object mapping table names to descriptions, nothing else.
{language_rule}"""


def generate_descriptions(schema_ctx: SchemaContext, config: LumenConfig) -> Result[dict[str, str]]:
    """Generate table descriptions via LLM."""
    result: Result[dict[str, str]] = Result()

    api_key = os.environ.get(config.llm.api_key_env, "")
    if not api_key:
        result.error("CONFIG_ERROR", f"Missing API key: {config.llm.api_key_env}")
        return result

    schema_xml = to_xml(schema_ctx)
    theme = load_theme(config.active_connection)
    lang_map = {"nl": "Dutch", "fr": "French", "de": "German"}
    lang = lang_map.get(theme.locale)
    language_rule = f"4. Write all descriptions in {lang}." if lang else ""
    system = _SYSTEM_PROMPT.format(schema_xml=schema_xml, language_rule=language_rule)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=config.llm.model,
            max_tokens=2048,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": "Generate table descriptions."}],
        )

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

        descriptions: Any = json.loads(text)
        if not isinstance(descriptions, dict):
            result.error("PARSE_ERROR", "LLM response is not a JSON object")
            return result

        result.data = {str(k): str(v) for k, v in descriptions.items()}
    except json.JSONDecodeError as e:
        result.error("PARSE_ERROR", f"Failed to parse LLM response as JSON: {e}")
    except anthropic.APIError as e:
        result.error("API_ERROR", f"Anthropic API error: {e}")

    return result
