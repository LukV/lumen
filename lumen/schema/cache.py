"""Schema cache: persist and reload SchemaContext from disk."""

from __future__ import annotations

import json
from pathlib import Path

from lumen.config import _config_dir
from lumen.schema.context import SchemaContext


def _cache_path(project: str) -> Path:
    return _config_dir() / "projects" / project / "schema_cache.json"


async def load_cached(project: str) -> SchemaContext | None:
    """Load a cached SchemaContext, or None if not found."""
    path = _cache_path(project)
    if not path.exists():
        return None
    text = path.read_text()
    return SchemaContext.model_validate_json(text)


async def save_cache(project: str, ctx: SchemaContext) -> None:
    """Save a SchemaContext to disk."""
    path = _cache_path(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ctx.model_dump(by_alias=True), indent=2, default=str) + "\n")


def is_stale(project: str, current_hash: str) -> bool:
    """Check if the cached schema is stale by comparing hashes.

    Returns True if hashes differ or cache doesn't exist.
    """
    path = _cache_path(project)
    if not path.exists():
        return True
    try:
        text = path.read_text()
        cached = SchemaContext.model_validate_json(text)
        return cached.hash != current_hash
    except (json.JSONDecodeError, ValueError):
        return True
