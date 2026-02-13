"""Tests for LLM-generated suggestion questions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from lumen.agent.suggestions import (
    SuggestionsCache,
    generate_suggestions,
    load_cached_suggestions,
    save_suggestions_cache,
)

from .conftest import make_config, make_schema_ctx


def _mock_response(text: str) -> MagicMock:
    """Create a mock Anthropic response with text content."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


def test_generate_suggestions_happy_path() -> None:
    """Test that generate_suggestions returns up to 10 questions."""
    schema_ctx = make_schema_ctx()
    config = make_config()

    questions = [f"Question {i}?" for i in range(10)]
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=_mock_response(json.dumps(questions)))

    with (
        patch("lumen.agent.suggestions.anthropic.Anthropic", return_value=mock_client),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        result = generate_suggestions(schema_ctx, config)

    assert result.ok
    assert result.data is not None
    assert len(result.data) == 10
    assert result.data[0] == "Question 0?"


def test_generate_suggestions_strips_markdown_fences() -> None:
    """Test that markdown code fences around JSON are stripped."""
    schema_ctx = make_schema_ctx()
    config = make_config()

    questions = ["What are top sales?", "Show revenue trend"]
    text = f"```json\n{json.dumps(questions)}\n```"
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=_mock_response(text))

    with (
        patch("lumen.agent.suggestions.anthropic.Anthropic", return_value=mock_client),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        result = generate_suggestions(schema_ctx, config)

    assert result.ok
    assert result.data == ["What are top sales?", "Show revenue trend"]


def test_generate_suggestions_missing_api_key() -> None:
    """Test that missing API key returns CONFIG_ERROR."""
    schema_ctx = make_schema_ctx()
    config = make_config()

    with patch.dict("os.environ", {}, clear=True):
        result = generate_suggestions(schema_ctx, config)

    assert result.has_errors
    assert result.diagnostics[0].code == "CONFIG_ERROR"


def test_generate_suggestions_invalid_json() -> None:
    """Test that invalid JSON response returns PARSE_ERROR."""
    schema_ctx = make_schema_ctx()
    config = make_config()

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=_mock_response("not valid json"))

    with (
        patch("lumen.agent.suggestions.anthropic.Anthropic", return_value=mock_client),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        result = generate_suggestions(schema_ctx, config)

    assert result.has_errors
    assert result.diagnostics[0].code == "PARSE_ERROR"


def test_generate_suggestions_non_array_json() -> None:
    """Test that JSON object (not array) returns PARSE_ERROR."""
    schema_ctx = make_schema_ctx()
    config = make_config()

    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=_mock_response('{"questions": []}'))

    with (
        patch("lumen.agent.suggestions.anthropic.Anthropic", return_value=mock_client),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        result = generate_suggestions(schema_ctx, config)

    assert result.has_errors
    assert result.diagnostics[0].code == "PARSE_ERROR"


def test_cache_save_and_load(tmp_path: pytest.TempPathFactory) -> None:
    """Test saving and loading suggestions cache."""
    cache = SuggestionsCache(schema_hash="sha256:abc123", suggestions=["Q1?", "Q2?"])

    with patch("lumen.agent.suggestions.project_dir", return_value=tmp_path):
        save_suggestions_cache("test_conn", cache)
        loaded = load_cached_suggestions("test_conn")

    assert loaded is not None
    assert loaded.schema_hash == "sha256:abc123"
    assert loaded.suggestions == ["Q1?", "Q2?"]


def test_cache_staleness(tmp_path: pytest.TempPathFactory) -> None:
    """Test that stale cache (different hash) is detected."""
    cache = SuggestionsCache(schema_hash="sha256:old", suggestions=["Old question?"])

    with patch("lumen.agent.suggestions.project_dir", return_value=tmp_path):
        save_suggestions_cache("test_conn", cache)
        loaded = load_cached_suggestions("test_conn")

    assert loaded is not None
    assert loaded.schema_hash != "sha256:new"  # Different hash = stale


def test_cache_missing_returns_none(tmp_path: pytest.TempPathFactory) -> None:
    """Test that missing cache file returns None."""
    empty = tmp_path / "empty"  # type: ignore[operator]
    with patch("lumen.agent.suggestions.project_dir", return_value=empty):
        loaded = load_cached_suggestions("test_conn")

    assert loaded is None


def test_generate_suggestions_truncates_to_10() -> None:
    """Test that more than 10 suggestions are truncated."""
    schema_ctx = make_schema_ctx()
    config = make_config()

    questions = [f"Question {i}?" for i in range(15)]
    mock_client = MagicMock()
    mock_client.messages.create = MagicMock(return_value=_mock_response(json.dumps(questions)))

    with (
        patch("lumen.agent.suggestions.anthropic.Anthropic", return_value=mock_client),
        patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
    ):
        result = generate_suggestions(schema_ctx, config)

    assert result.ok
    assert result.data is not None
    assert len(result.data) == 10
