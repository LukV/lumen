# Lumen — Technical Documentation

**Release Tufte** — v0.1.0

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
| Frontend | React 18 + TypeScript + Vite | `react-vega` for chart rendering |
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
