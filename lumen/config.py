"""Configuration management for Lumen."""

import json
from pathlib import Path

from pydantic import BaseModel


class ConnectionConfig(BaseModel):
    type: str = "postgresql"
    dsn: str = ""
    schema_name: str = "public"


class LLMConfig(BaseModel):
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-20250514"
    api_key_env: str = "ANTHROPIC_API_KEY"


class SettingsConfig(BaseModel):
    max_result_rows: int = 1000
    statement_timeout_seconds: int = 30
    theme: str = "lumen-default"


class LumenConfig(BaseModel):
    connections: dict[str, ConnectionConfig] = {}
    active_connection: str | None = None
    llm: LLMConfig = LLMConfig()
    settings: SettingsConfig = SettingsConfig()


def _config_dir() -> Path:
    return Path.home() / ".lumen"


def _config_path() -> Path:
    return _config_dir() / "config.json"


def notebooks_dir() -> Path:
    """Return the notebooks directory path."""
    return _config_dir() / "notebooks"


def projects_dir() -> Path:
    """Return the projects directory path."""
    return _config_dir() / "projects"


def project_dir(name: str) -> Path:
    """Return the directory for a specific project."""
    return projects_dir() / name


def ensure_dirs() -> None:
    """Create required Lumen directories."""
    base = _config_dir()
    base.mkdir(exist_ok=True)
    notebooks_dir().mkdir(exist_ok=True)
    (base / "projects").mkdir(exist_ok=True)


def load_config() -> LumenConfig:
    """Load config from ~/.lumen/config.json, returning defaults if missing."""
    path = _config_path()
    if not path.exists():
        return LumenConfig()
    text = path.read_text()
    return LumenConfig.model_validate_json(text)


def save_config(config: LumenConfig) -> None:
    """Save config to ~/.lumen/config.json."""
    ensure_dirs()
    path = _config_path()
    path.write_text(json.dumps(config.model_dump(), indent=2) + "\n")
