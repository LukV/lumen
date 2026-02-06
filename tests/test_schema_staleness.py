"""Tests for schema cache staleness detection."""

import json
from pathlib import Path

from lumen.schema.cache import is_stale
from lumen.schema.context import SchemaContext, compute_hash
from lumen.schema.enricher import EnrichedColumn, EnrichedSchema, EnrichedTable


def _make_ctx(row_count: int = 10000) -> SchemaContext:
    schema = EnrichedSchema(
        database="analytics",
        tables=[
            EnrichedTable(
                name="orders",
                row_count=row_count,
                columns=[
                    EnrichedColumn(name="id", data_type="integer", role="key", is_primary_key=True),
                ],
            ),
        ],
    )
    ctx = SchemaContext(enriched=schema)
    ctx.hash = compute_hash(ctx)
    return ctx


def test_fresh_cache_not_stale(tmp_path: Path) -> None:
    """Same hash → not stale."""
    ctx = _make_ctx()

    # Write cache file manually
    cache_path = tmp_path / "projects" / "test" / "schema_cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps(ctx.model_dump(by_alias=True), indent=2, default=str))

    # Monkeypatch _cache_path
    import lumen.schema.cache as cache_mod

    original = cache_mod._cache_path
    cache_mod._cache_path = lambda project: cache_path  # type: ignore[assignment]
    try:
        assert not is_stale("test", ctx.hash)
    finally:
        cache_mod._cache_path = original


def test_stale_cache_different_hash(tmp_path: Path) -> None:
    """Different hash → stale."""
    ctx = _make_ctx()

    cache_path = tmp_path / "projects" / "test" / "schema_cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text(json.dumps(ctx.model_dump(by_alias=True), indent=2, default=str))

    import lumen.schema.cache as cache_mod

    original = cache_mod._cache_path
    cache_mod._cache_path = lambda project: cache_path  # type: ignore[assignment]
    try:
        assert is_stale("test", "sha256:different_hash")
    finally:
        cache_mod._cache_path = original


def test_missing_cache_is_stale(tmp_path: Path) -> None:
    """No cache file → stale."""
    cache_path = tmp_path / "projects" / "test" / "schema_cache.json"

    import lumen.schema.cache as cache_mod

    original = cache_mod._cache_path
    cache_mod._cache_path = lambda project: cache_path  # type: ignore[assignment]
    try:
        assert is_stale("test", "sha256:any_hash")
    finally:
        cache_mod._cache_path = original


def test_corrupt_cache_is_stale(tmp_path: Path) -> None:
    """Corrupted cache file → stale."""
    cache_path = tmp_path / "projects" / "test" / "schema_cache.json"
    cache_path.parent.mkdir(parents=True)
    cache_path.write_text("not valid json {{{")

    import lumen.schema.cache as cache_mod

    original = cache_mod._cache_path
    cache_mod._cache_path = lambda project: cache_path  # type: ignore[assignment]
    try:
        assert is_stale("test", "sha256:any_hash")
    finally:
        cache_mod._cache_path = original
