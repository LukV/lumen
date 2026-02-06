# CLAUDE.md

## Project
Lumen — conversational analytics notebook. See TECHNICAL.md for full spec.

## Reference code
The `reference/` directory contains files extracted from DuckBook (predecessor
project). These are for adaptation, not direct import. Specifically:

- `reference/core.py` → Adapt into `lumen/core.py` (Result[T] + Diag pattern)
- `reference/auto.py` → Adapt into `lumen/viz/auto_detect.py` (chart heuristics)
- `reference/techniques.py` → Adapt into `lumen/whatif/trend.py` (Postgres SQL, not DuckDB)
- `reference/explain.py` → Adapt into `lumen/whatif/explain.py`
- `reference/generator.py` → Adapt into `lumen/schema/enricher.py` (column role inference only, not full entity generation)
- `reference/canonical.py` → Apply serialization principles to cell hashing, don't port the module

Key differences from DuckBook:
- No semantic layer (entities, explores, compiler) — LLM generates SQL directly
- Postgres via asyncpg, not DuckDB
- Vega-Lite, not Chart.js
- All functions return Result[T], never raise for validation/compilation

## Stack
- Python 3.13+, uv, ruff, mypy strict, FastAPI, asyncpg, anthropic SDK
- React + TypeScript + Vite frontend
- See pyproject.toml for full dependencies

## Commands
- `ruff check .` — lint
- `ruff format .` — format
- `mypy lumen/` — type check
- `pytest tests/` — test
- `uv run lumen start` — run dev server

## Style
- ruff: line-length 120, py313
- mypy: strict mode, pydantic plugin
- All public functions return Result[T] from core.py
- No exceptions for validation/business logic failures
- Type hints everywhere, use Python 3.13 type syntax
- Apply semantic versioning
