# Lumen — Technical Documentation

**Release Tufte** — v0.1.0 (shipped) | **Release Proef** — v0.2.0 (planned)

This document describes the architecture, data flow, and implementation details of Lumen as built. It serves as the definitive technical reference for the codebase.

---

## System overview

Lumen is a local-first, single-user conversational analytics tool. The user connects to a PostgreSQL database, asks questions in natural language, and receives SQL-backed Vega-Lite visualizations with written narratives. The system uses a two-call LLM orchestration loop that produces deterministic, replayable artifacts.

```
┌───────────────────────────────────────────────────────┐
│                   Frontend (React + TS)                │
│  InputBar → SSE consumer → CellView (Chart+Narrative) │
│                + CodeView (SQL editor)                 │
└──────────────────────┬────────────────────────────────┘
                       │ SSE
┌──────────────────────┼────────────────────────────────┐
│                Backend (FastAPI)                       │
│                      │                                │
│  ┌───────────────────▼──────────────────────────┐     │
│  │           Agent (two-call orchestrator)       │     │
│  │                                              │     │
│  │  1. Build context (schema XML + history)     │     │
│  │  2. Call 1: LLM → SQL + chart spec           │     │
│  │  3. Validate SQL (pglast AST)                │     │
│  │  4. Execute SQL (asyncpg)                    │     │
│  │  5. On error → feed back to LLM → retry (3x) │     │
│  │  6. Validate chart spec; fallback to auto    │     │
│  │  7. Call 2: LLM narrates actual results      │     │
│  │  8. Build canonical cell → stream to client  │     │
│  └──┬──────────┬──────────┬──────────┬──────────┘     │
│     │          │          │          │                 │
│     ▼          ▼          ▼          ▼                 │
│  Schema     Anthropic    SQL       Notebook            │
│  Layer      SDK          Executor  Store               │
│     │                      │                          │
│     ▼                      ▼                          │
│  Cached                 PostgreSQL                    │
│  Schema                 (user's DB)                   │
└───────────────────────────────────────────────────────┘
```

---

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | Python 3.13+ | `type` statement syntax, strict mypy |
| Backend | FastAPI | Async-native, SSE via `sse-starlette` |
| LLM | Anthropic SDK | Claude API with structured tool calling |
| Database driver | asyncpg | Async Postgres, statement timeout enforcement |
| SQL validation | pglast | Postgres parser — AST walk catches DML in CTEs |
| Chart spec | Vega-Lite v5 JSON | Declarative, deterministic rendering |
| Frontend | React 19 + TypeScript + Vite | `react-vega` for chart rendering |
| Streaming | Server-Sent Events | Unidirectional, sufficient for v1 |
| Storage | JSON files on disk | `~/.lumen/notebooks/` — no metadata DB needed |
| Schema docs | YAML / Markdown / CSV parsers | dbt `schema.yml`, freeform docs, data dictionaries |
| CLI | Typer + Rich | `lumen connect`, `lumen start` |
| Package manager | uv | Fast, lockfile-based |
| Lint / format | Ruff | Line length 120, py313 target |
| Type checking | mypy strict + Pydantic plugin | All 29 source files pass |

---

## Project structure

```
lumen/
├── pyproject.toml
├── uv.lock
├── CLAUDE.md                        # Dev instructions
├── TECHNICAL.md                     # This document
├── README.md
│
├── lumen/
│   ├── __init__.py
│   ├── core.py                      # Severity, Diag, Result[T]
│   ├── config.py                    # ConnectionConfig, LumenConfig, path helpers
│   ├── cli.py                       # lumen connect / lumen start (Typer)
│   ├── server.py                    # FastAPI app, SSE endpoints, static serving
│   ├── py.typed                     # PEP 561 marker
│   │
│   ├── schema/
│   │   ├── introspector.py          # Postgres introspection via asyncpg
│   │   ├── enricher.py              # Column role inference (key, time, categorical, measure)
│   │   ├── augmenter.py             # dbt YAML, markdown, CSV dictionary parsers
│   │   ├── context.py               # SchemaContext, XML serialization, SHA-256 hashing
│   │   └── cache.py                 # Disk caching, staleness detection via hash
│   │
│   ├── agent/
│   │   ├── agent.py                 # Two-call orchestrator (ask_question, run_edited_sql)
│   │   ├── prompts.py               # System prompts, PLAN_TOOL, NARRATE_TOOL definitions
│   │   ├── cell.py                  # Cell model and all sub-models (Pydantic)
│   │   ├── executor.py              # SQL execution via asyncpg → Result[CellResult]
│   │   ├── sql_validator.py         # pglast AST validation (read-only enforcement)
│   │   └── history.py               # XML conversation context + refinement context builders
│   │
│   ├── viz/
│   │   ├── auto_detect.py           # Query shape → chart type heuristic fallback
│   │   ├── validator.py             # Structural Vega-Lite spec validation
│   │   └── theme.py                 # Lumen Vega-Lite theme (muted palette, FT-inspired)
│   │
│   ├── whatif/
│   │   ├── trend.py                 # Trend extrapolation SQL (regr_slope/intercept/r2)
│   │   ├── explain.py               # Deterministic caveat generation
│   │   └── chart.py                 # Layered Vega-Lite (solid actuals + dashed projections)
│   │
│   └── notebook/
│       ├── notebook.py              # Notebook model
│       └── store.py                 # JSON file persistence with atomic writes
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                   # Shell, routing, state, SSE consumption
│       ├── config.ts                 # API_BASE
│       ├── styles.css                # Design tokens, all component styles
│       ├── vite-env.d.ts
│       ├── components/
│       │   ├── CellView.tsx          # Cell card: chart + narrative + code drawer
│       │   ├── ChartRenderer.tsx     # Vega-Lite rendering with theme + signal listeners
│       │   ├── NarrativeView.tsx     # Narrative with highlighted data references
│       │   ├── CodeView.tsx          # Tabbed SQL editor (SQL / Chart Spec / Reasoning)
│       │   ├── InputBar.tsx          # Question input (hero + compact variants)
│       │   └── StageIndicator.tsx    # Animated processing stage display
│       ├── types/
│       │   ├── cell.ts              # Cell, WhatIfMetadata, DataReference types
│       │   └── schema.ts            # SchemaData, SchemaTable, SchemaColumn types
│       └── utils/
│           └── sse.ts               # SSE stream consumer
│
├── tests/                           # 144 tests, all passing
│   ├── conftest.py
│   ├── test_core.py
│   ├── test_context.py
│   ├── test_enrichment.py
│   ├── test_cell.py
│   ├── test_sql_validator.py
│   ├── test_history.py
│   ├── test_schema_staleness.py
│   ├── test_augmenter.py
│   ├── test_trend.py
│   ├── test_explain.py
│   ├── test_auto_detect.py
│   ├── test_agent.py
│   ├── test_run_sql.py
│   ├── test_notebook_persistence.py
│   ├── test_server_cells.py
│   ├── test_trend_chart.py
│   └── test_viz_validator.py
│
├── reference/                       # DuckBook code adapted during build
└── docs/
    ├── VISION.md                    # Product vision and Release Tufte scope
    ├── TECH_ANALYSES.md             # Original technical analysis (pre-implementation)
    ├── mockup.html                  # UI design mockup
    ├── moodboard.html               # Visual design reference
    └── TEST_QUESTIONS.md            # Sample questions for testing
```

---

## Core types

### `Result[T]` — `lumen/core.py`

Every public function returns `Result[T]`, never raises for validation or business logic failures. This is the foundational pattern across the entire codebase.

```python
class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class Diag(BaseModel):
    severity: Severity
    code: str        # Machine-readable: SQL_ERROR, EMPTY_RESULT, SCHEMA_STALE, etc.
    message: str     # Human-readable description
    hint: str | None # Actionable fix suggestion

class Result(BaseModel, Generic[T]):
    data: T | None = None
    diagnostics: list[Diag]

    @property
    def ok(self) -> bool: ...
    def error(self, code, message, *, hint=None): ...
    def warning(self, code, message, *, hint=None): ...
```

`Result[T]` uses `Generic[T]` (not PEP 695 type params) because Pydantic requires the `BaseModel, Generic[T]` inheritance form. The `# noqa: UP046` suppresses Ruff's suggestion to use the newer syntax.

### Diagnostic codes

| Code | Trigger | Example hint |
|------|---------|--------------|
| `SQL_ERROR` | Generated SQL fails execution | *"Column 'revnue' not found. Available: revenue, region, date."* |
| `SQL_PARSE_ERROR` | pglast cannot parse the SQL | *"Check the query for syntax errors."* |
| `SQL_TIMEOUT` | Query exceeds 30s statement timeout | *"Try adding a date filter."* |
| `EMPTY_RESULT` | Query returns 0 rows | *"No data matches. Try broadening the date range."* |
| `RESULT_TRUNCATED` | Result exceeds 1000 rows | *"Showing first 1000 rows."* |
| `VALIDATION_ERROR` | DML detected in SQL AST | *"Write operations are not permitted."* |
| `VIZ_FALLBACK` | LLM chart spec failed validation | *"Using auto-detected chart type."* |
| `VIZ_FIELD_MISMATCH` | Chart references non-existent column | *"Available columns: revenue, region."* |

---

## The canonical cell

Every interaction produces a `Cell`. The cell is the unit of reproducibility.

```python
class Cell(BaseModel):
    id: str                          # "cell_" + 8 hex chars
    created_at: str                  # ISO 8601 UTC
    question: str                    # Original user question
    title: str                       # Editable display title (defaults to question)
    context: CellContext             # parent_cell_id, refinement_of, position
    sql: CellSQL | None              # query, edited_by_user, user_sql_override
    result: CellResult | None        # columns, data, row_count, data_hash, execution_time_ms
    chart: CellChart | None          # Vega-Lite spec, auto_detected flag
    narrative: CellNarrative | None  # text, data_references[]
    metadata: CellMetadata           # model, agent_steps, retry_count, reasoning, whatif
```

Key design decisions:
- **`result.data_hash`** — SHA-256 of result rows for reproducibility verification
- **`result.data`** — stores up to 1000 rows; beyond that, truncated with diagnostic
- **`chart.spec`** — complete Vega-Lite spec; renders without LLM once stored
- **`narrative.data_references`** — maps claims to data via substring matching (not character offsets, which LLMs get wrong)
- **`metadata.whatif`** — present when trend extrapolation was applied; includes technique, parameters, and caveats

---

## Schema layer

### Introspection — `schema/introspector.py`

On `lumen connect <dsn>`, the system runs these queries against `information_schema` and `pg_catalog`:

1. **Tables and columns** — names, data types, nullability
2. **Primary and foreign keys** — constraint types and references
3. **Sample values** — `SELECT DISTINCT` for low-cardinality string columns
4. **Approximate row counts** — `pg_class.reltuples` (fast, no sequential scan)
5. **Table/column comments** — `obj_description()`, `col_description()`
6. **Distinct count estimates** — for role inference
7. **Value ranges** — `MIN`/`MAX` for time and numeric columns

### Enrichment — `schema/enricher.py`

Heuristics adapted from DuckBook's bootstrap module infer column roles:

| Role | Detection | LLM hint |
|------|-----------|----------|
| `key` | `*_id` naming + high distinct count, or PK/FK | Excluded from aggregation |
| `time_dimension` | date/timestamp types | Suggested for time axes |
| `categorical` | String/bool with distinct_count < threshold | Sample values included |
| `measure_candidate` | Numeric, not a key | Suggested aggregation (sum/avg/count) |
| `other` | Default | No special treatment |

### Augmentation — `schema/augmenter.py`

Three parsers merge external documentation into the schema context:

| Source | Format | What it provides |
|--------|--------|------------------|
| `schema.yml` | dbt YAML | Table/column descriptions |
| `docs.md` | Markdown | Free-form data model documentation |
| `dictionary.csv` | CSV | `table,column,description` mappings |

Files are read from `~/.lumen/projects/<connection-name>/` on connect.

### Schema context — `schema/context.py`

The enriched schema serializes to XML for the LLM prompt:

```xml
<schema database="analytics" introspected_at="2026-02-06T14:00:00Z">
  <table name="orders" rows="~145000" description="Sales pipeline">
    <column name="id" type="uuid" role="key" pk="true"/>
    <column name="created_at" type="timestamp" role="time_dimension"
            range="2023-01-15 to 2025-12-28"/>
    <column name="amount" type="numeric" role="measure_candidate"
            suggested_agg="sum" description="Deal value in USD"/>
    <column name="status" type="varchar" role="categorical" distinct_count="5"
            values="['prospecting','qualification','proposal','closed_won','closed_lost']"/>
  </table>
  <augmented_docs>
    {content from dbt/markdown/csv if available}
  </augmented_docs>
</schema>
```

The context is cached to disk and hashed (SHA-256). The hash is compared on subsequent connects to detect schema changes.

### Caching — `schema/cache.py`

- `save_cached(name, ctx)` — writes schema JSON to `~/.lumen/projects/<name>/schema_cache.json`
- `load_cached(name)` — reads and deserializes
- `is_stale(name, current_hash)` — compares stored hash against live schema hash

---

## LLM orchestration — `agent/agent.py`

### Two-call architecture

The orchestration uses **two LLM calls per question**. This is a deliberate design decision to prevent hallucinated numbers in the narrative:

1. **Call 1 (Plan):** Schema context + question → `reasoning` + `sql` + `chart_spec` (+ optional `whatif`)
2. **Execute SQL** against Postgres
3. **Call 2 (Narrate):** Actual query results → `narrative` + `data_references`

A single call that generates SQL + chart + narrative before seeing data would produce hallucinated numbers. For a trust-first product, this is non-negotiable.

### Tool definitions — `agent/prompts.py`

**`plan_query` (Call 1):**
- `reasoning` (string) — analytical approach explanation
- `sql` (string) — Postgres SELECT statement
- `chart_spec` (object) — Vega-Lite v5 specification
- `whatif` (object, optional) — trend extrapolation parameters

**`narrate_results` (Call 2):**
- `narrative` (string) — 2-4 sentence insight with specific numbers
- `data_references` (array) — `{ref_id, text, source}` mappings

### Retry loop

When SQL validation or execution fails, the error is fed back to the LLM as a tool result:

```
attempt 0: plan_query → SQL error → feed error back
attempt 1: plan_query → fixed SQL → success
```

Maximum 3 retries. Each retry emits a `correcting` SSE stage event.

### SQL editing flow — `run_edited_sql()`

When the user edits SQL in the code view:

1. Validate the user's SQL via pglast (no Call 1 needed — the user is the planner)
2. Execute against Postgres
3. Auto-detect chart spec from result shape
4. Run Call 2 (narrate) with the user's SQL and actual results
5. Build updated cell with `sql.edited_by_user = true`

### Conversation context — `agent/history.py`

Previous cells are serialized as XML context in the system prompt:

```xml
<conversation>
  <cell position="1">
    <question>Top customers by revenue</question>
    <sql>SELECT ... FROM ... ORDER BY revenue DESC LIMIT 10</sql>
    <narrative>Karl Seal leads with $221.55...</narrative>
  </cell>
</conversation>
```

For refinements, the parent cell gets a dedicated `<refinement_context>` block with full SQL, chart spec, and narrative.

---

## SQL safety — `agent/sql_validator.py`

### AST-based validation with pglast

Naive prefix checks (`if sql.startswith('INSERT')`) are trivially bypassed. Lumen uses `pglast`, a Python wrapper around PostgreSQL's own parser, to walk the AST:

1. **Parse** — reject syntactically invalid SQL
2. **Single statement** — reject multiple statements (`;`-separated)
3. **Top-level type** — only `SelectStmt` allowed
4. **AST walk** — catch DML hidden in CTEs or subqueries (`InsertStmt`, `UpdateStmt`, `DeleteStmt`, `DropStmt`, etc.)

### Defense in depth

- AST validation is the first line
- The connected Postgres user should have only `SELECT` privileges (documented in README)
- `SET statement_timeout = '30s'` at connection level

---

## Visualization — `viz/`

### Theme — `viz/theme.py`

Custom Vega-Lite config applied to every chart:

- **Palette:** Muted 8-color category range inspired by the Financial Times chart style
- **Typography:** DM Sans for labels and titles
- **Axes:** Dashed grid lines, subtle domain lines
- **Marks:** Bar corner radius, 2.5px line stroke, filled points
- **Dark mode:** Separate config with inverted colors, applied based on frontend theme

### Auto-detection — `viz/auto_detect.py`

When the LLM's chart spec fails validation, heuristics select a chart type from the result shape:

| Pattern | Chart type |
|---------|-----------|
| 1 row, 1 numeric column | KPI (text mark) |
| Time column + 1+ measures | Line chart |
| Time column + 2+ measures | Stacked area chart |
| 1 categorical + 1 measure | Horizontal bar chart |
| 2 numeric columns | Scatter plot |
| Fallback | Table (no chart) |

### Validation — `viz/validator.py`

Structural validation (not full JSON schema — that's impractical in Python):

1. `mark` field must exist and be a known type
2. Encoding field references must match query result columns
3. Layered specs: each layer validated independently

---

## What-if — `whatif/`

Trend extrapolation ships as a quiet capability in Release Tufte. The LLM can trigger it by including a `whatif` parameter in `plan_query`.

### Trend SQL — `whatif/trend.py`

Wraps the user's baseline query with Postgres regression functions:

```sql
WITH baseline AS (<original query>),
regression AS (
    SELECT
        regr_slope(measure, EXTRACT(EPOCH FROM time_col)) AS slope,
        regr_intercept(measure, EXTRACT(EPOCH FROM time_col)) AS intercept,
        regr_r2(measure, EXTRACT(EPOCH FROM time_col)) AS r2
    FROM baseline
),
future_periods AS (
    SELECT generate_series(...) AS time_col
),
projections AS (
    SELECT time_col, slope * EXTRACT(EPOCH FROM time_col) + intercept AS measure,
           'projected' AS _series
    FROM future_periods, regression
)
SELECT * FROM baseline UNION ALL SELECT * FROM projections
```

`TrendParams`: `time_field`, `measure`, `periods_ahead` (default 3), `period_interval` (day/week/month/quarter/year).

### Caveats — `whatif/explain.py`

Deterministic caveat generation based on technique and parameters. No LLM call — caveats are formulaic by design:

- "Based on linear regression of historical data"
- "Projecting N periods ahead; accuracy decreases with distance"
- "R² value indicates strength of the linear relationship"
- "Does not account for seasonality, external factors, or regime changes"

### Chart overlay — `whatif/chart.py`

Builds a layered Vega-Lite spec:
- **Layer 1:** Solid line + points for actual data (filtered by `_series != 'projected'`)
- **Layer 2:** Dashed line + open points for projected data (filtered by `_series == 'projected'`)

---

## Notebook persistence — `notebook/`

### Notebook model — `notebook/notebook.py`

```python
class Notebook(BaseModel):
    id: str                    # "nb_" + 8 hex chars
    connection_name: str
    created_at: str            # ISO 8601
    updated_at: str
    cells: list[Cell]
```

### Store — `notebook/store.py`

- Atomic writes via `tempfile` + `os.replace` (no partial writes on crash)
- One JSON file per notebook: `~/.lumen/notebooks/{id}.json`
- `load_latest(connection_name)` — finds the most recent notebook for a connection
- `add_cell()`, `update_cell()`, `delete_cell()`, `update_cell_title()` — in-memory + persist
- Singleton store instance per `notebooks_dir` path

---

## API endpoints — `server.py`

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/api/health` | Health check + connection info | `{ok, connection_name, database}` |
| `GET` | `/api/schema` | Current schema context | `SchemaContext` JSON |
| `GET` | `/api/config` | Connection status | `{active_connection, connections[]}` |
| `POST` | `/api/ask` | Ask a question (SSE stream) | `stage` → `cell` or `error` events |
| `POST` | `/api/run-sql` | Execute user-edited SQL | SSE stream (same event format) |
| `GET` | `/api/notebook` | Get all cells | `Cell[]` JSON |
| `PATCH` | `/api/cells/{id}` | Update cell title | `{ok: true}` |
| `DELETE` | `/api/cells/{id}` | Delete a cell | `{ok: true}` |

### SSE event types

```
stage   → {"stage": "thinking"|"executing"|"correcting"|"narrating"|"projecting"}
cell    → {full Cell JSON}
error   → {"code": "...", "message": "..."}
```

---

## Frontend architecture

### State management

All state lives in `App.tsx` — no external state library. Key state:

- `cells: Cell[]` — the notebook
- `currentStage: string | null` — SSE processing stage
- `isProcessing: boolean` — disables input during agent flow
- `schema: SchemaData | null` — fetched on mount for suggestion generation
- `health: HealthData | null` — polled every 30s for connection status
- `theme: "light" | "dark"` — persisted to localStorage

### Component tree

```
App
├── Topbar (logo, wordmark, connection indicator, theme toggle)
├── View: Empty (hero)
│   ├── Hero title + subtitle
│   ├── InputBar (hero variant)
│   └── Sample chips (schema-aware suggestions)
└── View: Results
    ├── CellView[] (scrollable)
    │   ├── ChartRenderer (Vega-Lite via react-vega)
    │   ├── NarrativeView (data reference highlighting)
    │   ├── Cell footer (row count, execution time, model)
    │   └── CodeView (tabbed: SQL editor / Chart Spec / Reasoning)
    ├── StageIndicator (animated dots + stage label)
    └── InputBar (compact variant, bottom-anchored)
```

### Chart ↔ narrative linking

1. **Chart → narrative:** Vega-Lite `signalListeners` on `hover` emit the hovered datum to `ChartRenderer`, which passes it to `NarrativeView` as `highlightedDatum`
2. **NarrativeView** matches the datum's values against `data_references[].text` and applies a highlight CSS class

### Design system — `styles.css`

- **Design tokens:** CSS custom properties for colors, typography, spacing, radii
- **Dual theme:** `[data-theme="light"]` and `[data-theme="dark"]` token sets
- **Fonts:** Source Serif 4 (editorial/headings), DM Sans (body/UI), JetBrains Mono (code)
- **Palette:** Muted warm tones — accent `#4A2D4F` (light) / `#9B7BA0` (dark)

---

## Configuration

### `~/.lumen/config.json`

```json
{
  "connections": {
    "default": {
      "type": "postgresql",
      "dsn": "postgresql://analyst@localhost:5432/analytics",
      "schema_name": "public"
    }
  },
  "active_connection": "default",
  "llm": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "api_key_env": "ANTHROPIC_API_KEY"
  },
  "settings": {
    "max_result_rows": 1000,
    "statement_timeout_seconds": 30,
    "theme": "lumen-default"
  }
}
```

API key is read from an environment variable (name stored in config, not the key itself).

### `~/.lumen/projects/<name>/`

```
my-analytics/
├── schema_cache.json          # Cached enriched schema
├── schema.yml                 # dbt schema (optional)
├── docs.md                    # Data model docs (optional)
└── dictionary.csv             # Column descriptions (optional)
```

---

## Quality gates

All gates pass as of Release Tufte:

| Gate | Command | Status |
|------|---------|--------|
| Lint | `uv run ruff check lumen/ tests/` | Clean |
| Format | `uv run ruff format --check lumen/ tests/` | Clean |
| Type check (Python) | `uv run mypy lumen/` | 29 files, strict, no errors |
| Type check (TypeScript) | `cd frontend && npx tsc --noEmit` | Clean |
| Tests | `uv run pytest tests/` | 144 passed, 0 failed |

---

## Dependencies

### Python (`pyproject.toml`)

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.115 | Web framework |
| uvicorn | >=0.34 | ASGI server |
| asyncpg | >=0.30 | Postgres async driver |
| anthropic | >=0.42 | Claude SDK |
| pydantic | >=2.10 | Data models, serialization |
| pyyaml | >=6.0 | dbt schema.yml parsing |
| typer | >=0.15 | CLI framework |
| rich | >=13.9 | CLI formatting |
| sse-starlette | >=2.2 | SSE response support |
| pglast | >=7 | Postgres SQL parser (AST) |
| numpy | >=2.2 | Numeric operations |

### Dev dependencies

ruff, mypy, pytest, pytest-asyncio, httpx

### Frontend (`package.json`)

react, react-dom, react-vega, vega, vega-lite, vega-embed, typescript, vite, @vitejs/plugin-react

---

## Known limitations (Release Tufte)

1. **Single database type** — PostgreSQL only. The schema layer and executor are the abstraction boundary for future sources.
2. **No authentication** — local-only, single-user. No login, no sharing.
3. **No narrative → chart linking** — chart hover highlights narrative spans, but clicking a narrative reference does not yet highlight chart elements via Vega-Lite signal injection.
4. **No cell re-execution** — there is no endpoint to re-run a cell against current data with its stored SQL. The user can copy-paste SQL into the editor to re-run.
5. **No SQL syntax highlighting** — the code view uses a plain textarea, not a syntax-highlighted editor.
6. **Single-threaded LLM calls** — the Anthropic client is synchronous (called from async context). This is fine for single-user but would need async wrapping for concurrent users.

---

## Technical improvement opportunities

Identified during code review ahead of Release Proef. Organized by priority and effort. These should be addressed alongside or before Proef feature work, as several are prerequisites for a client deployment.

### P0 — Fix before client deployment

#### Introspector N+1 query pattern (performance)

**File:** `lumen/schema/introspector.py:142-220`

The per-column metadata loop issues individual queries for distinct counts, sample values, and min/max ranges. For the LVTM dataset (~30 tables, ~200 columns), this generates ~600 sequential queries with network latency per query.

**Current:**
```python
for tname, table in tables_dict.items():
    for col in table.columns:
        dist_row = await conn.fetchrow(
            f'SELECT COUNT(DISTINCT "{col.name}") AS dc FROM "{tname}"'
        )
```

**Fix:** Batch queries per table or use `pg_stats` for pre-computed statistics:
```python
# Use pg_stats for distinct counts (no table scan needed)
SELECT tablename, attname, n_distinct
FROM pg_stats WHERE schemaname = $1

# Batch sample values per table
SELECT column_name, array_agg(DISTINCT value) ...
```

Table comments (line 142-155) and column comments (line 157-177) also use per-table queries. These can be batched into single `obj_description()`/`col_description()` queries.

**Impact:** Reduces introspection time from O(tables × columns) queries to O(tables) or O(1). Critical for schemas with 100+ columns.

#### SQL field name injection in trend SQL (security)

**File:** `lumen/whatif/trend.py:54-109`

`TrendParams.time_field` and `TrendParams.measure` come from LLM output (user-influenced) and are interpolated into SQL via f-strings with double-quoting:

```python
epoch_expr = f'EXTRACT(EPOCH FROM "{time_col}"::timestamp) / 86400.0'
```

Double-quoted identifiers prevent most injection, but do not handle embedded quotes. A field name containing `"` breaks out of the identifier.

**Fix:** Validate field names against the schema's known columns before constructing SQL:
```python
valid_cols = {col.name for table in schema.tables for col in table.columns}
if params.time_field not in valid_cols:
    result.error("TREND_INVALID_FIELD", f"Unknown column: {params.time_field}")
```

The same pattern exists in `introspector.py:185,200,210` (column/table names in f-string SQL). These are sourced from `information_schema` (trusted), so lower risk, but should use the same validation pattern for consistency.

#### Executor fetches all rows before truncating (memory)

**File:** `lumen/agent/executor.py:37,47-49`

```python
rows = await conn.fetch(sql)           # Loads ALL rows into RAM
if len(rows) > max_rows:
    rows = rows[:max_rows]             # Truncates after the fact
```

A query returning 1M rows loads everything into memory before truncating to 1000. For the LVTM dataset this is unlikely to be a problem (small tables), but it is a correctness issue.

**Fix:** Wrap the user's SQL with a LIMIT to prevent runaway fetches:
```python
wrapped = f"SELECT * FROM ({sql}) AS _q LIMIT {max_rows + 1}"
rows = await conn.fetch(wrapped)
```

The `+1` detects truncation without fetching more than needed.

#### Deprecated FastAPI startup event

**File:** `lumen/server.py:93`

```python
@app.on_event("startup")  # Deprecated in FastAPI >=0.109
```

FastAPI warns about this in test output. Replace with lifespan context manager:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    await _startup()
    yield

app = FastAPI(title="Lumen", version="0.2.0", lifespan=lifespan)
```

### P1 — Address during Proef development

#### Global mutable state in server

**Files:** `lumen/server.py:46-50`, `lumen/notebook/store.py:122-138`

Three pieces of global state without synchronization:

```python
_schema_ctx: SchemaContext | None = None       # server.py:46
_suggestions: list[str] = []                    # server.py:49
_suggestions_generating: bool = False           # server.py:50
_store: NotebookStore | None = None            # store.py:122
```

**Problems:**
- No `asyncio.Lock` — concurrent requests can race on `_suggestions_generating`
- `_schema_ctx` is loaded once at startup, never refreshed
- `get_store()` accepts `notebooks_dir` on first call only; ignored on subsequent calls
- `reset_store()` exists solely for testing — indicates the singleton is hard to test

**Fix for Proef:** Replace with FastAPI dependency injection:
```python
async def get_schema_ctx(config: LumenConfig = Depends(get_config)) -> SchemaContext:
    ...

@app.post("/api/ask")
async def ask(request: AskRequest, ctx: SchemaContext = Depends(get_schema_ctx)):
    ...
```

This is a prerequisite for connection management via UI (the schema context must be reloadable).

#### Synchronous LLM calls in async context

**Files:** `lumen/agent/agent.py:118,427`, `lumen/agent/suggestions.py:82`

The Anthropic SDK client is synchronous. `agent.py` calls `client.messages.create()` directly in async generator functions, blocking the event loop:

```python
response = client.messages.create(...)  # Blocks entire server
```

`suggestions.py` correctly uses `asyncio.to_thread()` (server.py:78), but `agent.py` does not.

**Fix:** Use the async Anthropic client:
```python
client = anthropic.AsyncAnthropic(api_key=api_key)
response = await client.messages.create(...)
```

This is a prerequisite for streaming reasoning (Proef 2.3) — streaming requires the async client's `client.messages.stream()`.

#### Column type inference from Python types

**File:** `lumen/agent/executor.py:54`

```python
column_types = [type(rows[0][col]).__name__ for col in columns]
```

Returns Python type names (`int`, `Decimal`, `datetime`) instead of Postgres type names (`integer`, `numeric`, `timestamp`). Auto-detect heuristics in `auto_detect.py` compare against these types, creating a fragile coupling.

**Problems:**
- `datetime` maps to `datetime` not `timestamp` — time dimension detection works by accident
- `NoneType` appears when first row has NULL — breaks type inference entirely
- `Decimal` vs `float` behavior differs between Postgres numeric types

**Fix:** Use asyncpg's `PreparedStatement.get_attributes()` to get Postgres column types:
```python
stmt = await conn.prepare(sql)
column_types = [attr.type.name for attr in stmt.get_attributes()]
rows = await stmt.fetch(max_rows + 1)
```

#### Unvalidated LLM tool output

**File:** `lumen/agent/agent.py:135-138`

```python
reasoning = tool_input.get("reasoning", "")
sql = tool_input.get("sql", "")
chart_spec = tool_input.get("chart_spec", {})
whatif_input: dict[str, Any] | None = tool_input.get("whatif")
```

Tool output is extracted as `dict[str, Any]` with no Pydantic validation. If the LLM returns unexpected types (e.g., `sql` as a list), errors surface downstream with confusing messages.

**Fix:** Define a Pydantic model for tool input:
```python
class PlanToolOutput(BaseModel):
    reasoning: str
    sql: str
    chart_spec: dict[str, Any]
    whatif: WhatIfInput | None = None

parsed = PlanToolOutput.model_validate(tool_input)
```

### P2 — Quality improvements

#### SSE client has no error recovery

**File:** `frontend/src/utils/sse.ts:8-55`

The SSE consumer reads the stream once with no reconnection, no timeout, and no abort support. If the server drops the connection mid-stream, the client hangs silently.

**Problems:**
- No `AbortController` integration — component unmount during streaming leaks the reader
- No timeout — a stalled server blocks indefinitely
- No reconnection logic — network blips kill the interaction

**Fix:** Accept an `AbortSignal` and propagate it:
```typescript
export async function consumeSSE(
  response: Response,
  handlers: SSEHandlers,
  signal?: AbortSignal
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No response body");

  signal?.addEventListener("abort", () => reader.cancel());
  ...
}
```

#### No responsive design

**File:** `frontend/src/styles.css`

929 lines of CSS with zero media queries. The UI is designed for desktop only:
- `.hero-title` is 34px — unreadable on mobile
- `.results-inner` max-width 820px — fine, but padding (32px) is excessive on small screens
- `.topbar` padding 28px — wastes space on mobile
- `.sample-chip` has `white-space: nowrap` — overflows on narrow screens

**Fix:** Add breakpoints for mobile (< 640px) and tablet (640-1024px). Start with padding/font adjustments, not layout changes.

#### Missing keyboard accessibility

**Files:** `frontend/src/components/CellView.tsx`, `frontend/src/styles.css`

- Cell title editing requires double-click — no keyboard alternative (`CellView.tsx:100`)
- Delete button is hidden until hover (`styles.css:502`) — invisible to keyboard users
- Theme toggle has no visible focus state (`styles.css:200-216`)
- No focus management after cell creation — user must tab through all cells

#### Silent error swallowing in frontend

**File:** `frontend/src/App.tsx:57,75,79,117`

Multiple `.catch(() => {})` blocks silently discard errors:

```javascript
fetch(`${API_BASE}/api/notebook`)
  .then((res) => res.json())
  .then((data: Cell[]) => setCells(data))
  .catch(() => {});                          // User sees empty page
```

If the backend is down on initial load, the user sees an empty page with no indication of failure.

#### Health endpoint always returns ok

**File:** `lumen/server.py:123-131`

```python
@app.get("/api/health")
async def health() -> dict[str, Any]:
    config = load_config()
    result: dict[str, Any] = {"ok": True}    # Always true
```

Should verify Postgres connectivity, schema cache existence, or at minimum that an active connection is configured.

#### Numpy dependency appears unused

**File:** `pyproject.toml:22`

```toml
"numpy>=2.2",
```

No `import numpy` found in the codebase. If unused, this adds ~50MB to the installation. Verify and remove if not needed.

### Test coverage gaps

#### Missing test files

| Module | Status | Risk |
|--------|--------|------|
| `lumen/agent/executor.py` | No dedicated tests | All agent tests mock it — real asyncpg behavior untested |
| `lumen/schema/introspector.py` | No tests | Core functionality, all database interaction untested |
| `lumen/cli.py` | No tests | Config loading, connect flow untested |
| `lumen/agent/prompts.py` | No direct tests | XML prompt construction only tested indirectly via mocked LLM responses |
| `lumen/server.py` (endpoints) | Partial | Only PATCH/DELETE tested; POST /api/ask, POST /api/run-sql, GET /api/schema untested |
| Frontend | No tests | No React component tests |

#### Missing edge case tests

- Empty schema (zero tables) — untested path through enricher and context
- NULL values in first row — breaks `executor.py:54` type inference
- `distinct_estimate=0` — untested path through `enricher.py`
- Schema with reserved SQL keywords as column/table names
- Concurrent cell creation — no test for race conditions in `NotebookStore`
- Corrupt notebook JSON recovery — `load_latest()` logs warning but behavior untested
- SSE stream interruption — no test for partial stream delivery

#### Test quality observations

**Strengths:**
- 153 tests, all passing, covering core Result[T], SQL validation, cell models, history, augmentation, auto-detect, trend SQL, chart building, and notebook persistence
- Error paths tested alongside happy paths in most modules
- Deterministic hashing and XML escaping well-tested

**Weaknesses:**
- `test_agent.py` uses hardcoded mock responses — doesn't verify actual tool schemas match LLM expectations
- `test_augmenter.py:84` malformed YAML test uses `{{invalid yaml: [` which is actually valid YAML
- `test_notebook_persistence.py:100-105` atomic write test only checks for `.tmp` file absence, doesn't verify atomicity under failure
- Index-based keys in frontend (`key={i}`) — anti-pattern for dynamic lists

### Architecture notes for Proef

These aren't bugs — they're architectural decisions from Release Tufte that need revisiting for Proef's scope.

**Connection lifecycle.** Currently, the DSN is resolved per-request via `_get_dsn(config)` → `config.connections[name].dsn`, and a new `asyncpg.connect()` is created per query execution. This works for single-user but creates unnecessary connection overhead. For Proef, consider a connection pool (`asyncpg.create_pool()`) initialized at startup with the active connection.

**Theme as code vs config.** The current theme (`viz/theme.py`) is hardcoded Python returning a Vega-Lite config dict. For Proef's branding feature, the theme must be driven by the `theme.json` configuration. The Vega-Lite palette, the CSS custom properties, and the chart colors must all derive from the same source of truth.

**Locale architecture.** Release Proef adds Dutch UI chrome. The simplest approach: a `locales/` directory with `nl.json` and `en.json`, loaded at build time, with the locale set in `theme.json`. No runtime switching. The LLM system prompt's language directive should read from the same config.

**Streaming architecture for reasoning.** The current SSE flow emits discrete `stage` events. Streaming reasoning requires a new SSE event type (`reasoning` with incremental text chunks). This requires the async Anthropic client (`client.messages.stream()`) to receive token-by-token output. The frontend needs a new UI component for the reasoning stream — not a chat bubble, but a collapsible monospaced panel below the stage indicator.

**Geographic visualization.** Vega-Lite supports choropleth maps natively via `mark: "geoshape"` with TopoJSON/GeoJSON projections. The key decision is where the GeoJSON lives: bundled as a static asset in the frontend (simplest), or served from the backend (more flexible for future boundary sets). For Proef, bundle it — the Vlaamse gemeenten GeoJSON is ~1MB and changes rarely.
