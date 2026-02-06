# Lumen — Technical Analysis

**Purpose:** This document defines the architecture, tech stack, data structures, and implementation plan for Lumen v1 (Release Tufte). It is written to be precise enough to serve as input for Claude Code implementation.

**Lineage:** Lumen descends from DuckBook, a prototype conversational analytics notebook built around a semantic layer and DuckDB. DuckBook was nuked because it was too bloated — it tried to be a full BI platform. Lumen strips that back to the core: connect to a database, ask a question, get a chart and a story. Specific DuckBook components are recuperated where noted.

---

## 1. System overview

Lumen is a local-first, single-user conversational analytics tool. The user connects to a PostgreSQL database, asks questions in natural language, and receives SQL-backed visualizations with written narratives. The system uses an agentic LLM orchestration loop but produces deterministic, replayable artifacts.

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (React)                    │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Chat    │  │  Chart   │  │ Narrative│  │  Code    │ │
│  │  Input   │  │  Render  │  │  Panel   │  │  View    │ │
│  └────┬─────┘  └────▲─────┘  └────▲─────┘  └────▲─────┘ │
│       │              │             │              │       │
│       ▼              │             │              │       │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              Server-Sent Events (SSE)               │ │
│  └──────────────────────┬──────────────────────────────┘ │
└──────────────────────────┼───────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────┐
│                   Backend (Python / FastAPI)              │
│                          │                               │
│  ┌───────────────────────▼───────────────────────────┐   │
│  │              Orchestrator (Agent Loop)             │   │
│  │                                                   │   │
│  │  1. Build context (schema + history + question)   │   │
│  │  2. Call 1: LLM plans query (SQL + chart spec)    │   │
│  │  3. Validate SQL via AST (pglast)                 │   │
│  │  4. Execute SQL against Postgres                  │   │
│  │  5. On error → feed error back to LLM → retry     │   │
│  │  6. Validate chart spec structurally              │   │
│  │  7. Call 2: LLM narrates actual results           │   │
│  │  8. Store canonical cell                          │   │
│  │  9. Stream stages + final result to frontend      │   │
│  └──┬──────────┬──────────┬──────────┬───────────────┘   │
│     │          │          │          │                    │
│     ▼          ▼          ▼          ▼                    │
│  ┌──────┐ ┌────────┐ ┌────────┐ ┌───────────┐           │
│  │Schema│ │  LLM   │ │  SQL   │ │  Notebook  │           │
│  │Layer │ │Client  │ │Executor│ │  Store     │           │
│  └──┬───┘ └────────┘ └───┬────┘ └───────────┘           │
│     │                    │                               │
│     ▼                    ▼                               │
│  ┌──────┐          ┌──────────┐                          │
│  │Cached│          │PostgreSQL│                          │
│  │Schema│          │(user's)  │                          │
│  └──────┘          └──────────┘                          │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Tech stack

| Layer | Choice | Rationale |
|---|---|---|
| **Language** | Python 3.13+ | Developer expertise, Claude Code fluency, rich ecosystem, `type` statement syntax |
| **Backend framework** | FastAPI | Async-native, SSE support, lightweight, auto-generates OpenAPI |
| **LLM client** | `anthropic` Python SDK | Direct Claude API with tool use (structured outputs) |
| **Database driver** | `asyncpg` | Async Postgres driver, fast, well-maintained |
| **Schema introspection** | Raw SQL against `information_schema` + `pg_catalog` | Full control, no ORM overhead |
| **SQL validation** | `pglast` (Postgres parser in Python) | AST-based validation catches DML in CTEs/subqueries; prefix checks don't |
| **Chart specification** | Vega-Lite JSON | Declarative, deterministic, renders identically every time, excellent Python/JS ecosystem |
| **Frontend** | React + TypeScript | Standard, fast, good Vega-Lite integration via `react-vega` |
| **Frontend build** | Vite | Fast dev server, simple config |
| **Chart rendering** | `react-vega` (Vega-Lite) | Direct rendering of the spec the LLM produces |
| **Streaming** | Server-Sent Events (SSE) | Simpler than WebSocket for unidirectional streaming, sufficient for v1 |
| **Notebook storage** | JSON files on disk | One `.json` file per notebook in a `~/.lumen/notebooks/` directory. No database needed for metadata in v1 |
| **Schema docs** | YAML/Markdown/CSV parser | Read dbt `schema.yml`, markdown docs, CSV data dictionaries from a project folder |
| **CLI** | `typer` and optionally `rich` | For `lumen connect`, `lumen start` commands |
| **Dependency management** | `uv` | Fast installs, lockfile support, reproducible environments |
| **Linting/formatting** | `ruff` | Very fast linter + formatter, replaces multiple tools, consistent style |
| **Type checking** | `mypy` (strict mode, Pydantic plugin) | Static typing safety net for refactors and LLM-adjacent code paths |
| **Package/install** | `uv pip install` from git (later: PyPI) | Single install with entry point |

### What we are NOT using and why

- **No ORM** (SQLAlchemy, etc.) — we introspect schemas and execute generated SQL; an ORM adds indirection with no benefit
- **No LangChain / LlamaIndex** — the agent loop is simple enough to implement directly; these frameworks add complexity and make debugging harder
- **No semantic layer** (DuckBook's entities/explores/compiler) — Lumen is LLM-first; the LLM generates SQL directly from schema context. A rigid intermediate layer fights with the conversational nature. The DuckBook prototype proved that the semantic layer, while elegant, was too much abstraction for the use case.
- **No Docker in v1** — local-first means `uv pip install` and go
- **No database for Lumen's own state** — JSON files are sufficient for single-user local notebooks

---

## 3. Recuperated from DuckBook

Five components from the DuckBook prototype are worth adapting. The rest is architecturally incompatible with Lumen's LLM-first approach.

### 3.1 `core.py` — Result[T] + Diag pattern

**Recuperation: direct port, minimal adaptation.**

DuckBook's error handling pattern is excellent and directly applicable. Functions never throw exceptions for validation or compilation failures — they return `Result[T]` containing both output and diagnostics.

```python
from enum import Enum
from pydantic import BaseModel

class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class Diag(BaseModel):
    severity: Severity
    code: str           # Machine-readable: "SQL_ERROR", "EMPTY_RESULT", "SCHEMA_STALE"
    message: str        # Human-readable description
    hint: str | None    # Actionable fix suggestion

class Result[T](BaseModel):
    data: T | None      # None only if errors make output impossible
    diagnostics: list[Diag]

    @property
    def ok(self) -> bool:
        return not any(d.severity == Severity.ERROR for d in self.diagnostics)
```

**Why this matters for Lumen:**
- The agent retry loop feeds `Diag.message` + `Diag.hint` back to Claude on SQL errors — structured error codes are more useful than raw exception messages
- The frontend renders inline error messages with fix suggestions (e.g., "Column 'revnue' not found. Did you mean 'revenue'?")
- Partial results: a cell can have warnings alongside valid data (e.g., "Results truncated to 1000 rows")

**Diagnostic codes for Lumen:**

| Code | When | Example hint |
|------|------|-------------|
| `SQL_ERROR` | Generated SQL fails to execute | *"Column 'revnue' not found in table 'orders'. Available columns: revenue, region, date."* |
| `SQL_PARSE_ERROR` | Generated SQL is syntactically invalid (pglast) | *"Check the query for syntax errors."* |
| `SQL_TIMEOUT` | Query exceeds 30s statement timeout | *"Try adding a date filter or reducing the scope."* |
| `EMPTY_RESULT` | Query returns 0 rows | *"No data matches these filters. Try broadening the date range."* |
| `RESULT_TRUNCATED` | Result exceeds 1000 rows | *"Showing first 1000 rows. Add filters or aggregations to reduce the result set."* |
| `SCHEMA_STALE` | Schema hash changed since cell was created | *"The database schema has changed. Re-run this cell to update."* |
| `VIZ_FALLBACK` | LLM chart spec failed structural validation; auto-detection used | *"Using auto-detected chart type."* |
| `VIZ_FIELD_MISMATCH` | Chart spec references column not in query results | *"Available columns: revenue, region, date."* |
| `LLM_ERROR` | Claude API call failed | *"LLM service unavailable. Try again."* |
| `VALIDATION_ERROR` | Generated SQL contains forbidden operations (pglast AST) | *"Write operations are not permitted."* |

### 3.2 Viz auto-detection heuristics

**Recuperation: port rules as a validation/fallback layer.**

DuckBook's query-shape → chart-type mapping is sound. In Lumen, the LLM picks the chart type via the Vega-Lite spec, but these heuristics serve two purposes:

1. **Validation** — if the LLM suggests a bar chart for a time series, the system can flag this or override it
2. **Fallback** — if the LLM returns a malformed chart spec, auto-detection provides a sensible default

```python
def auto_detect_chart_type(columns: list[ColumnInfo], has_aggregation: bool) -> str:
    """
    Returns: "kpi", "line", "bar", "scatter", "table"

    Rules (from DuckBook viz/auto.py, adapted):
    - 1 aggregate, no grouping          → kpi
    - 2+ aggregates, no grouping        → kpi (multiple)
    - time column + 1+ measures         → line
    - 1 categorical + 1 measure         → bar
    - 2 numeric columns (no time)       → scatter
    - 2+ dimensions + measures          → table
    - fallback                          → table
    """
```

This module also produces a Vega-Lite spec from the detected type, acting as the fallback renderer when the LLM's spec fails validation.

### 3.3 What-if SQL patterns

**Recuperation: adapt SQL patterns from DuckDB dialect to PostgreSQL.**

DuckBook's five what-if techniques are pure SQL transformations. The logic ports to Postgres with minor dialect changes. For Lumen v1, only `trend_extrapolation` ships as a quiet capability; the others are staged for later.

| Technique | DuckBook SQL | Postgres adaptation | Lumen v1? |
|-----------|-------------|-------------------|-----------|
| `trend_extrapolation` | `regr_slope()` + `regr_intercept()` | Same functions exist in Postgres | **Yes** |
| `linear_scaling` | `measure * factor` | Identical | Later |
| `correlation` | `regr_r2()`, `corr()` | Same functions exist in Postgres | Later |
| `seasonal_forecast` | Window functions | Same syntax | Later |
| `monte_carlo` | `generate_series()` + `random()` | `generate_series()` exists; `random()` needs `setseed()` for reproducibility | Later |

**Also recuperated:** The deterministic caveat/assumption generation from `whatif/explain.py`. Every what-if result states its assumptions plainly — this is central to Lumen's explainability pillar.

### 3.4 Bootstrap heuristics for schema enrichment

**Recuperation: adapt heuristics to enrich schema context XML.**

DuckBook's bootstrap module infers column roles from introspection data:

```python
# Adapted from DuckBook bootstrap/generator.py
def enrich_schema(snapshot: SchemaSnapshot) -> EnrichedSchema:
    """
    For each column:
    - _is_time_column(): date/timestamp types → tag as time dimension
    - _is_categorical(): string/bool with distinct_count < threshold → tag with sample values
    - _is_measure_candidate(): numeric, not a key → tag as potential measure with suggested agg
    - _is_primary_key(): *_id naming + high distinct count → tag as key
    """
```

Lumen doesn't build a formal semantic model from this. Instead, the enriched tags are included in the schema context XML sent to Claude, dramatically improving SQL generation:

```xml
<column name="status" type="varchar"
        role="categorical"
        distinct_count="5"
        values="['prospecting','qualification','proposal','closed_won','closed_lost']"/>
<column name="created_at" type="timestamp"
        role="time_dimension"
        range="2023-01-15 to 2025-12-28"/>
<column name="amount" type="numeric"
        role="measure_candidate"
        suggested_agg="sum"/>
```

### 3.5 Deterministic serialization principles

**Recuperation: apply principles from `spec/canonical.py` to cell serialization.**

DuckBook's canonical YAML serializer guaranteed identical bytes for identical semantics (deterministic key order, sorted arrays, no None values). The same principles apply to Lumen's JSON cell serialization:

- Deterministic key order (follow Pydantic field order via `model_dump()`)
- `exclude_none=True` — don't serialize absent fields
- Sorted arrays where order is semantically meaningless
- Consistent float formatting

This enables reliable hashing for the reproducibility pillar (`result.data_hash`, `metadata.schema_version`).

---

## 4. The canonical cell (core data structure)

Every interaction produces a cell. The cell is the unit of reproducibility.

```json
{
  "id": "cell_a1b2c3d4",
  "created_at": "2026-02-06T14:30:00Z",
  "question": "How is our sales pipeline compared to last year?",
  "context": {
    "parent_cell_id": null,
    "refinement_of": null,
    "conversation_position": 0
  },
  "sql": {
    "query": "SELECT DATE_TRUNC('quarter', created_at) AS quarter, SUM(amount) AS pipeline_value, EXTRACT(YEAR FROM created_at) AS year FROM opportunities WHERE created_at >= '2024-01-01' GROUP BY quarter, year ORDER BY quarter",
    "generated_by": "claude-sonnet-4-20250514",
    "edited_by_user": false,
    "user_sql_override": null
  },
  "result": {
    "columns": ["quarter", "pipeline_value", "year"],
    "column_types": ["timestamp", "numeric", "integer"],
    "row_count": 8,
    "data_hash": "sha256:e3b0c44298fc...",
    "data": [],
    "truncated": false,
    "execution_time_ms": 142,
    "diagnostics": []
  },
  "chart": {
    "spec": {
      "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
      "mark": "line",
      "encoding": {
        "x": {"field": "quarter", "type": "temporal", "title": "Quarter"},
        "y": {"field": "pipeline_value", "type": "quantitative", "title": "Pipeline Value ($)"},
        "color": {"field": "year", "type": "nominal"}
      }
    },
    "auto_detected": false,
    "theme": "lumen-default"
  },
  "narrative": {
    "text": "Pipeline is down 12% YoY overall, driven primarily by a drop in enterprise deals in Q3. Mid-market has actually grown 8%.",
    "data_references": [
      {"ref_id": "ref1", "text": "down 12%", "source": "computed from pipeline_value for 2025 vs 2024"},
      {"ref_id": "ref2", "text": "grown 8%", "source": "computed from mid-market segment rows"}
    ]
  },
  "metadata": {
    "model": "claude-sonnet-4-20250514",
    "schema_version": "sha256:abc123...",
    "agent_steps": 2,
    "retry_count": 0,
    "reasoning": "Comparing pipeline by quarter, splitting by year to enable YoY comparison."
  }
}
```

### Key design decisions in the cell format

- **`sql.edited_by_user`** — tracks whether the user modified the SQL. If true, `user_sql_override` contains their version. Essential for the conversational correction pillar.
- **`result.data_hash`** — SHA-256 of the result set. Allows verifying reproducibility without storing full result data.
- **`result.data`** — stores up to 1000 rows. Beyond that, only the hash is stored (re-execute to reproduce). This keeps notebooks self-contained for most cases without getting huge.
- **`result.diagnostics`** — array of `Diag` objects (from `core.py`). Warnings and info messages live alongside valid results.
- **`chart.spec`** — a complete Vega-Lite spec. The frontend renders this directly. The LLM generates it; once stored, the LLM is not needed to re-render.
- **`chart.auto_detected`** — true when the LLM's spec was invalid and auto-detection was used as fallback.
- **`narrative.data_references`** — maps claims in the narrative to data using named markers (`ref_id` + `text` substring), not character offsets. The frontend finds each `text` substring in the narrative via string matching and wraps it in a `<span data-ref="ref1">`. This is robust against whitespace differences and encoding issues — asking an LLM to count character offsets is unreliable.
- **`metadata.schema_version`** — hash of the schema context at time of generation. If the schema changes, the cell can be flagged as stale (`SCHEMA_STALE` diagnostic).
- **`metadata.reasoning`** — the LLM's brief explanation of its analytical approach (from Call 1). Visible in an expanded view for explainability.

### Notebook format

```json
{
  "id": "notebook_x1y2z3",
  "name": "Q1 Pipeline Review",
  "created_at": "2026-02-06T14:00:00Z",
  "updated_at": "2026-02-06T15:30:00Z",
  "connection": {
    "type": "postgresql",
    "database": "analytics",
    "schema_hash": "sha256:abc123..."
  },
  "cells": [
    { "...cell..." }
  ]
}
```

---

## 5. Schema layer

### Introspection

On `lumen connect <connection_string>`, the system runs introspection queries and builds an enriched schema context:

```python
# Core introspection queries (asyncpg)

# 1. Tables and columns
SELECT table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

# 2. Primary keys and foreign keys
SELECT tc.table_name, kcu.column_name, tc.constraint_type,
       ccu.table_name AS foreign_table, ccu.column_name AS foreign_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu USING (constraint_name, table_schema)
LEFT JOIN information_schema.constraint_column_usage ccu USING (constraint_name, table_schema)
WHERE tc.table_schema = 'public';

# 3. Sample values for categoricals (low cardinality columns)
# For each column with data_type in ('character varying', 'text') or few distinct values:
SELECT DISTINCT {column} FROM {table} LIMIT 20;

# 4. Row counts (approximate, fast)
SELECT relname, reltuples::bigint
FROM pg_class
WHERE relnamespace = 'public'::regnamespace;

# 5. Table/column comments (if available)
SELECT obj_description(oid) FROM pg_class WHERE relname = '{table}';
SELECT col_description('{table}'::regclass, ordinal_position)
FROM information_schema.columns WHERE table_name = '{table}';

# 6. Distinct count estimates (for role inference)
# For each non-key column:
SELECT COUNT(DISTINCT {column}) FROM {table};
# (Use approximate methods for large tables)

# 7. Value ranges for time and numeric columns
SELECT MIN({column}), MAX({column}) FROM {table};
```

### Schema enrichment (recuperated from DuckBook)

After introspection, the bootstrap heuristics from DuckBook enrich each column with role tags:

```python
def enrich_columns(snapshot: SchemaSnapshot) -> EnrichedSchema:
    """
    Adapted from DuckBook bootstrap/generator.py.

    For each column, infer:
    - role: "key", "time_dimension", "categorical", "measure_candidate", or "other"
    - For categoricals: sample values, distinct count
    - For time dimensions: value range
    - For measure candidates: suggested aggregation (sum, avg, count)
    - For keys: flagged as primary/foreign

    These tags go into the schema context XML. They don't build a formal
    semantic model — they're hints for the LLM.
    """
```

### Schema augmentation from files

The system reads additional documentation from a project directory (`~/.lumen/projects/<name>/`):

| File | Format | What it provides |
|---|---|---|
| `schema.yml` | dbt schema YAML | Table/column descriptions, tests, relationships |
| `docs.md` | Markdown | Free-form documentation about the data model |
| `dictionary.csv` | CSV | Column-level descriptions: `table,column,description,example_values` |
| `*.sql` | SQL files | Common query patterns (used as few-shot examples in the prompt) |

These are parsed once on startup and merged with the introspected + enriched schema into a single `SchemaContext` object.

### Schema context format (what the LLM sees)

```xml
<schema database="analytics" introspected_at="2026-02-06T14:00:00Z">
  <table name="opportunities" rows="~145000" description="Sales pipeline opportunities">
    <column name="id" type="uuid" role="key" pk="true"/>
    <column name="created_at" type="timestamp" role="time_dimension" range="2023-01-15 to 2025-12-28"/>
    <column name="amount" type="numeric" role="measure_candidate" suggested_agg="sum" description="Deal value in USD"/>
    <column name="stage" type="varchar" role="categorical" distinct_count="5"
            values="['prospecting','qualification','proposal','closed_won','closed_lost']"/>
    <column name="owner_id" type="uuid" role="key" fk="users.id"/>
    <column name="account_id" type="uuid" role="key" fk="accounts.id"/>
  </table>
  <table name="users" rows="~200" description="Sales team members">
    ...
  </table>
  <augmented_docs>
    {content from dbt schema.yml, docs.md, etc. if available}
  </augmented_docs>
</schema>
```

The schema context is cached and hashed. The hash is stored in each cell for reproducibility tracking. On `lumen start`, the system checks if the schema has changed since last cached and re-introspects if needed.

### Handling large schemas (100+ tables)

When the full schema exceeds the context window, use a two-pass approach:

1. **Table selection pass:** Send the user's question + a compact table list (name + description + row count only) to Claude. Ask which tables are relevant.
2. **Full context pass:** Send the question + full schema for only the selected tables.

This adds one LLM round-trip but keeps the system working on production databases. Implement if needed; for most analytical databases under ~50 tables, the full schema fits in context.

---

## 6. LLM orchestration (the agent loop)

### Two-step LLM calls

The orchestration uses **two LLM calls per question**, not one. This is a deliberate design decision:

- **Call 1 (Plan):** Given the schema context and user question, generate `reasoning` + `sql` + `chart_spec`. The LLM knows the column names from the SQL it writes, so the chart spec (which references columns, not data values) can be generated before execution.
- **Execute SQL** on our side.
- **Call 2 (Narrate):** Given the actual query results + chart spec, generate the `narrative` + `data_references`. The narrative contains specific numbers ("Pipeline is down 12% YoY") — these **must** come from real data, never from LLM inference about what the data might contain.

A single compound tool that generates SQL + chart + narrative before seeing data would produce hallucinated numbers in the narrative. For a product whose #1 value proposition is trust, this is non-negotiable.

#### Tool: `plan_query` (Call 1)

```python
plan_tool = {
    "name": "plan_query",
    "description": "Generate a SQL query and chart specification to answer the user's question.",
    "input_schema": {
        "type": "object",
        "required": ["reasoning", "sql", "chart_spec"],
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of your analytical approach: what tables/joins you're using and why, what the chart should show."
            },
            "sql": {
                "type": "string",
                "description": "PostgreSQL query. Use explicit column names, proper GROUP BY, and meaningful aliases. Never use SELECT *."
            },
            "chart_spec": {
                "type": "object",
                "description": "A Vega-Lite v5 specification object. Reference column aliases from the SQL. Use appropriate mark types (line for trends, bar for comparisons, point for correlations). Include proper axis titles."
            }
        }
    }
}
```

#### Tool: `narrate_results` (Call 2)

```python
narrate_tool = {
    "name": "narrate_results",
    "description": "Given query results, generate a narrative insight with data references.",
    "input_schema": {
        "type": "object",
        "required": ["narrative", "data_references"],
        "properties": {
            "narrative": {
                "type": "string",
                "description": "2-3 sentence insight grounded in the actual data provided. Be specific with real numbers from the results. Lead with the most important finding. Note anomalies or caveats. Write like a sharp analyst, not like an AI summary."
            },
            "data_references": {
                "type": "array",
                "description": "Array mapping specific claims to data. Each has a ref_id (short unique tag), the text substring in the narrative, and a source description.",
                "items": {
                    "type": "object",
                    "required": ["ref_id", "text", "source"],
                    "properties": {
                        "ref_id": {"type": "string", "description": "Short unique tag, e.g. 'ref1', 'ref2'"},
                        "text": {"type": "string", "description": "Exact substring from the narrative to highlight"},
                        "source": {"type": "string", "description": "Which rows/columns support this claim"}
                    }
                }
            }
        }
    }
}
```

### Why two calls, not one or three

| Approach | Pros | Cons |
|----------|------|------|
| **One call** (SQL + chart + narrative) | Fast, coherent | Narrative is hallucinated — numbers are guessed, not computed from real data. Fundamentally broken for a trust-first product. |
| **Two calls** (plan → execute → narrate) | Narrative grounded in real data. Chart spec still coherent with SQL. | One extra round-trip (~1-2s). Acceptable. |
| **Three calls** (SQL → execute → chart → narrate) | Maximum accuracy | Too slow. Chart spec doesn't need to see data — it references column names. |

The two-call split is the right tradeoff: the chart spec is generated alongside the SQL (they reference the same columns), while the narrative is generated after seeing actual results (it references specific values).

### The orchestration loop

```python
async def handle_question(question: str, notebook: Notebook, schema: SchemaContext) -> AsyncGenerator[Event, None]:
    """Core agent loop. Two LLM calls: plan (SQL + chart) → execute → narrate."""

    # 1. Build conversation context
    history = build_conversation_history(notebook.cells[-5:])
    system_prompt = build_system_prompt(schema)

    max_retries = 3
    messages = history + [{"role": "user", "content": question}]

    # === CALL 1: Plan (SQL + chart spec) ===
    for attempt in range(max_retries):
        yield StageEvent("thinking", "Analyzing your question...")

        plan_response = await claude.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=[plan_tool],
            temperature=0,
        )

        plan = extract_tool_use(plan_response)

        # Validate SQL via AST (pglast)
        validation = validate_sql(plan["sql"])
        if not validation.ok:
            yield ErrorEvent(validation.diagnostics[0].message)
            return

        # Execute SQL
        yield StageEvent("executing", "Running query...")
        execution = await execute_query(plan["sql"])

        if not execution.ok:
            if attempt < max_retries - 1:
                yield StageEvent("correcting", "Query error, adjusting...")
                error_diag = execution.diagnostics[0]
                messages.append({"role": "assistant", "content": plan_response.content})
                messages.append({"role": "user", "content":
                    f"SQL error: {error_diag.message}\nHint: {error_diag.hint}\nPlease fix the query."
                })
                continue
            else:
                yield ErrorEvent(
                    f"Could not generate a valid query after {max_retries} attempts.",
                    diagnostics=execution.diagnostics,
                )
                return

        # SQL succeeded — break retry loop
        break

    # Validate chart spec structurally, fall back to auto-detection if needed
    chart_spec = plan["chart_spec"]
    auto_detected = False
    chart_validation = validate_chart_spec(chart_spec, execution.data.columns)
    if not chart_validation.ok:
        chart_spec = auto_detect_chart(execution.data)
        auto_detected = True

    # === CALL 2: Narrate (given actual results) ===
    yield StageEvent("narrating", "Writing insight...")

    narrate_response = await claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system="You are Lumen. Given query results, write a concise analytical narrative grounded in the actual data.",
        messages=[{
            "role": "user",
            "content": f"""The user asked: "{question}"

This SQL was executed:
```sql
{plan['sql']}
```

Results ({execution.data.row_count} rows):
{format_results_for_llm(execution.data)}

Chart type: {chart_spec.get('mark', 'unknown')}

Write a 2-3 sentence narrative insight. Be specific with real numbers from the results.
Also provide data_references mapping your claims to the data."""
        }],
        tools=[narrate_tool],
        temperature=0,
    )

    narration = extract_tool_use(narrate_response)

    # Build canonical cell
    yield StageEvent("rendering", "Building visualization...")
    cell = build_cell(
        question=question,
        sql=plan["sql"],
        result=execution.data,
        chart_spec=chart_spec,
        auto_detected=auto_detected,
        narrative=narration["narrative"],
        data_references=narration.get("data_references", []),
        reasoning=plan["reasoning"],
        model=plan_response.model,
        schema_hash=schema.hash,
        diagnostics=execution.data.diagnostics,
    )
    yield CellEvent(cell)
```

**Latency budget:** Call 1 (plan) ~2-3s + SQL execution ~0.1-1s + Call 2 (narrate) ~1-2s = **~3-6s total**. The streaming stages make this feel responsive. The narrate call is lighter (smaller context, shorter output) so it's fast.
```

### System prompt (Call 1: plan)

```
You are Lumen, an analytical assistant. You answer questions about data
by generating SQL queries and chart specifications.

<schema>
{schema_context_xml}
</schema>

<schema_documentation>
{merged docs from dbt/markdown/csv if available}
</schema_documentation>

<rules>
- Generate PostgreSQL-compatible SQL only.
- Never use SELECT *. Always specify columns explicitly.
- Use meaningful column aliases.
- For time series, default to DATE_TRUNC appropriate to the data range.
- The chart_spec must be a valid Vega-Lite v5 specification.
  Reference column aliases from your SQL in the encoding fields.
- Chart type guidelines:
  - Comparisons across categories: bar chart
  - Trends over time: line chart
  - Distributions: histogram
  - Correlations between two measures: scatter plot
  - Single aggregate value: return a simple bar or value
- Do NOT include specific data values in the chart spec — only column
  references and formatting. The data will be bound after execution.
- If the user's question is ambiguous, make a reasonable assumption
  and state it in the reasoning field.
- If the question cannot be answered with the available schema,
  explain what's missing and suggest what you can answer instead.
</rules>

<conversation_so_far>
{previous cells as condensed context: question + SQL + narrative for each}
</conversation_so_far>
```

The Call 2 (narrate) prompt is simpler — just the question, SQL, actual results, and chart type. No schema context needed. See the orchestrator code above.

### Handling user SQL edits

When the user edits SQL in the code view and re-runs:

1. Execute the user's SQL directly (no Call 1 needed — the user *is* the planner)
2. Run Call 2 (narrate) with the user's SQL and actual results to generate narrative + data_references
3. Auto-detect chart spec from result shape (or keep the existing spec if columns match)
4. Store the cell with `sql.edited_by_user = true` and `sql.user_sql_override`
5. In subsequent conversation turns, include the user's edit in context so the LLM understands the adjusted scope ("I see you changed the date filter to Q3")

### Handling refinements

When the user says "break that down by quarter instead":

1. Include the previous cell in context (full SQL, chart spec, narrative)
2. The LLM sees what was generated and generates a modified version
3. New cell is created with `context.refinement_of` pointing to the parent cell
4. The conversation thread is replayable

### Model choice

Start with Claude Sonnet (fast, cheap, good at structured tool use). The model is configurable. Test Haiku for simple queries where speed matters most. Opus for complex multi-table joins if needed. Log model + latency in cell metadata to guide future optimization.

---

## 7. SQL safety and validation

### AST-based validation with `pglast`

Naive prefix checks (`if sql.startswith('INSERT')`) are trivially bypassed — a CTE like `WITH x AS (DELETE FROM ...) SELECT ...` would pass. We use `pglast`, a Python wrapper around PostgreSQL's own parser, to inspect the SQL AST.

```python
import pglast
from pglast.enums import ObjectType

# Statement types that are safe (read-only)
ALLOWED_STMT_TYPES = {"SelectStmt"}

# Node types that indicate write operations (even inside CTEs or subqueries)
FORBIDDEN_NODE_TYPES = {
    "InsertStmt", "UpdateStmt", "DeleteStmt",
    "CreateStmt", "DropStmt", "AlterTableStmt",
    "TruncateStmt", "GrantStmt", "RevokeStmt",
    "CreateFunctionStmt", "CreateRoleStmt",
}

def validate_sql(sql: str) -> Result[str]:
    """
    Parse SQL into AST using Postgres's own parser.
    Reject anything that isn't a pure read-only SELECT.
    Returns Result with the SQL string on success.
    """
    # 1. Parse
    try:
        stmts = pglast.parse_sql(sql)
    except pglast.parser.ParseError as e:
        return Result(data=None, diagnostics=[
            Diag(severity=Severity.ERROR, code="SQL_PARSE_ERROR",
                 message=f"Invalid SQL syntax: {e}",
                 hint="Check the query for syntax errors.")
        ])

    # 2. Reject multiple statements
    if len(stmts) != 1:
        return Result(data=None, diagnostics=[
            Diag(severity=Severity.ERROR, code="VALIDATION_ERROR",
                 message="Multiple statements are not permitted.",
                 hint="Please use a single SELECT statement.")
        ])

    # 3. Check top-level statement type
    stmt = stmts[0].stmt
    stmt_type = type(stmt).__name__
    if stmt_type not in ALLOWED_STMT_TYPES:
        return Result(data=None, diagnostics=[
            Diag(severity=Severity.ERROR, code="VALIDATION_ERROR",
                 message=f"Only SELECT statements are permitted (got {stmt_type}).",
                 hint="Lumen only executes read-only queries.")
        ])

    # 4. Walk entire AST to catch DML hidden in CTEs or subqueries
    root = pglast.Node(stmts[0])
    for node in root.traverse():
        node_type = type(node.node).__name__ if hasattr(node, 'node') else ""
        if node_type in FORBIDDEN_NODE_TYPES:
            return Result(data=None, diagnostics=[
                Diag(severity=Severity.ERROR, code="VALIDATION_ERROR",
                     message=f"Write operation ({node_type}) detected inside query.",
                     hint="Lumen only executes read-only queries. Remove any INSERT, UPDATE, DELETE, or DDL.")
            ])

    return Result(data=sql, diagnostics=[])
```

### Defense in depth

AST validation is the first line. Additional layers:

- **Read-only database user (hard requirement).** The setup instructions must create a Postgres user with only `SELECT` privileges. Lumen should verify this on connection by attempting a harmless write and confirming it's rejected. This is the real safety net — even if AST validation has a gap, the database won't execute writes.
- **`SET statement_timeout = '30s'`** at connection level, non-overridable.
- **asyncpg exceptions → Diag objects:** Wrap execution in try/except, converting Postgres error codes to structured diagnostics with column-level hints where available (e.g., "Column 'revnue' not found" → `hint: "Did you mean 'revenue'?"`).

---

## 8. Chart theming — Lumen default

A custom Vega-Lite theme applied to every chart:

```json
{
  "config": {
    "font": "Inter, system-ui, sans-serif",
    "title": {
      "fontSize": 14,
      "fontWeight": 600,
      "color": "#1a1a1a",
      "anchor": "start",
      "offset": 12
    },
    "axis": {
      "labelFont": "Inter, system-ui, sans-serif",
      "labelFontSize": 11,
      "labelColor": "#666666",
      "titleFont": "Inter, system-ui, sans-serif",
      "titleFontSize": 12,
      "titleColor": "#444444",
      "gridColor": "#e8e8e8",
      "gridDash": [2, 4],
      "domainColor": "#cccccc",
      "tickColor": "#cccccc"
    },
    "range": {
      "category": [
        "#3b5998", "#c67a3c", "#5a9e6f", "#8b6caf",
        "#c75a5a", "#4a9cc2", "#d4a843", "#7d7d7d"
      ]
    },
    "bar": { "cornerRadiusTopLeft": 2, "cornerRadiusTopRight": 2 },
    "line": { "strokeWidth": 2.5 },
    "point": { "size": 60, "filled": true },
    "view": { "strokeWidth": 0 },
    "background": "#ffffff"
  }
}
```

Design references: Financial Times chart style, Observable Plot defaults. Muted palette with enough contrast for accessibility (WCAG AA). No chartjunk, no 3D, no gratuitous gradients.

### Chart spec validation

Full Vega-Lite JSON schema validation in Python is impractical — the schema is complex and there's no well-maintained Python validator. Instead, do **structural validation** on the Python side and let the frontend's Vega-Lite renderer be the real validator.

```python
def validate_chart_spec(spec: dict, result_columns: list[str]) -> Result[dict]:
    """
    Structural validation — check the bones, not every detail.
    The frontend Vega-Lite renderer will catch the rest.
    """
    diagnostics = []

    # 1. Required keys
    if "mark" not in spec:
        diagnostics.append(Diag(
            severity=Severity.ERROR, code="VIZ_INVALID",
            message="Chart spec missing 'mark' field.",
            hint=None,
        ))

    # 2. Mark type is valid
    valid_marks = {"bar", "line", "point", "area", "rect", "tick", "arc", "boxplot", "circle", "square"}
    mark = spec.get("mark")
    mark_type = mark if isinstance(mark, str) else mark.get("type") if isinstance(mark, dict) else None
    if mark_type and mark_type not in valid_marks:
        diagnostics.append(Diag(
            severity=Severity.WARNING, code="VIZ_UNKNOWN_MARK",
            message=f"Unknown mark type: {mark_type}",
            hint=None,
        ))

    # 3. Encoding field references match result columns
    encoding = spec.get("encoding", {})
    for channel, enc in encoding.items():
        if isinstance(enc, dict) and "field" in enc:
            if enc["field"] not in result_columns:
                diagnostics.append(Diag(
                    severity=Severity.ERROR, code="VIZ_FIELD_MISMATCH",
                    message=f"Chart references column '{enc['field']}' but query returned: {result_columns}",
                    hint=f"Available columns: {', '.join(result_columns)}",
                ))

    if any(d.severity == Severity.ERROR for d in diagnostics):
        return Result(data=None, diagnostics=diagnostics)
    return Result(data=spec, diagnostics=diagnostics)
```

When validation fails, the auto-detection fallback generates a safe spec from the result shape. The cell is tagged with `chart.auto_detected = true` and a `VIZ_FALLBACK` diagnostic so the user knows what happened.

---

## 9. Frontend architecture

### Stack
- React 18+ with TypeScript
- Vite for bundling
- `react-vega` for chart rendering
- Tailwind CSS for utility styling (restrained — mostly custom CSS for the notebook aesthetic)
- `shiki` for SQL syntax highlighting in the code view
- Inter font (loaded locally, not from CDN)

### Layout

```
┌─────────────────────────────────────────────────┐
│  Lumen                          [Connection: ●] │  ← minimal header
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ User: How is pipeline vs last year?       │  │  ← user message
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ ┌─────────────────────────────────────┐   │  │
│  │ │         [Vega-Lite chart]            │   │  │  ← chart (primary)
│  │ └─────────────────────────────────────┘   │  │
│  │                                           │  │
│  │ Pipeline is down 12% YoY, driven          │  │  ← narrative (interactive spans)
│  │ primarily by a drop in enterprise deals   │  │
│  │ in Q3. Mid-market has actually grown 8%.  │  │
│  │                                           │  │
│  │ ▸ View SQL  ▸ View chart spec  ▸ Reasoning│  │  ← progressive disclosure
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │ User: Break that down by quarter          │  │  ← refinement
│  └───────────────────────────────────────────┘  │
│                                                 │
│  ┌───────────────────────────────────────────┐  │
│  │         [Updated chart]                   │  │
│  │         [Updated narrative]               │  │
│  │         ▸ View SQL  ▸ View chart spec     │  │
│  └───────────────────────────────────────────┘  │
│                                                 │
├─────────────────────────────────────────────────┤
│  Ask a question about your data...    [Enter ⏎] │  ← input (always visible)
└─────────────────────────────────────────────────┘
```

### Streaming UX

SSE events from the backend drive a stage indicator:

```typescript
type StageEvent =
  | { type: "stage"; stage: "thinking"; message: string }      // Call 1: planning
  | { type: "stage"; stage: "executing"; message: string }     // SQL execution
  | { type: "stage"; stage: "correcting"; message: string }    // agent retry
  | { type: "stage"; stage: "narrating"; message: string }     // Call 2: narrative
  | { type: "stage"; stage: "rendering"; message: string }     // final assembly
  | { type: "cell"; cell: Cell }                               // final result
  | { type: "error"; message: string; diagnostics?: Diag[] };  // failure
```

Each stage shows inline in the cell area with a subtle animation (a pulsing dot, not a spinner). Stages make the system feel alive and transparent.

### Chart ↔ Narrative linking

1. The `narrative.data_references` in the cell map claims to data via named markers (`ref_id` + `text` substring)
2. The frontend finds each `text` substring in the narrative via string matching and wraps it in a `<span data-ref="ref1" class="data-ref">` element
3. On hover over a chart element → highlight the corresponding narrative span (CSS class toggle)
4. On hover/click on a narrative reference → highlight the chart element (Vega-Lite signal injection)

Using substring matching instead of character offsets is more robust — LLMs are unreliable at counting characters, and whitespace/encoding differences would break offset-based linking constantly.

Implementation order: chart → narrative highlighting first (easier via Vega-Lite tooltip/signal events), then narrative → chart (requires Vega-Lite signal injection via the View API).

### Code view

Collapsible panel below each cell, containing:
1. **SQL tab** — syntax-highlighted, editable. "Run" button re-executes with the edited SQL.
2. **Chart spec tab** — read-only JSON view of the Vega-Lite spec. For power users.
3. **Reasoning tab** — the LLM's `reasoning` field, showing its analytical approach.

The SQL editor doesn't need to be a full IDE — a `<textarea>` with `shiki` highlighting and basic keyboard shortcuts (Cmd+Enter to run) is sufficient for v1.

---

## 10. Project structure

```
lumen/
├── pyproject.toml                  # Package config, entry points, uv/ruff/mypy config
├── uv.lock                         # Lockfile for reproducible installs
├── README.md
├── TECHNICAL.md                    # This document
│
├── lumen/
│   ├── __init__.py                 # Version
│   ├── core.py                     # Severity, Diag, Result[T] (from DuckBook)
│   ├── cli.py                      # `lumen connect`, `lumen start` (typer)
│   ├── server.py                   # FastAPI app, SSE endpoints
│   ├── config.py                   # Connection config, project paths
│   │
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── introspector.py         # Postgres schema introspection (asyncpg)
│   │   ├── enricher.py             # Column role inference (from DuckBook bootstrap)
│   │   ├── augmenter.py            # Parse dbt yml, markdown, csv docs
│   │   ├── context.py              # SchemaContext object, XML serialization, hashing
│   │   └── cache.py                # Schema caching on disk
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── orchestrator.py         # Core agent loop (handle_question)
│   │   ├── prompts.py              # System prompt templates
│   │   ├── tools.py                # Tool definitions for Claude API
│   │   └── history.py              # Conversation history management
│   │
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── runner.py               # SQL execution via asyncpg, Result[QueryResult]
│   │   └── validator.py            # SQL safety via pglast AST inspection
│   │
│   ├── viz/
│   │   ├── __init__.py
│   │   ├── auto_detect.py          # Query shape → chart type fallback (from DuckBook)
│   │   ├── validator.py            # Structural chart spec validation (not full JSON schema)
│   │   └── theme.py                # Lumen Vega-Lite theme
│   │
│   ├── whatif/
│   │   ├── __init__.py
│   │   ├── trend.py                # Trend extrapolation (from DuckBook, adapted to Postgres)
│   │   └── explain.py              # Deterministic assumption/caveat generation
│   │
│   ├── notebook/
│   │   ├── __init__.py
│   │   ├── cell.py                 # Cell dataclass / builder
│   │   ├── notebook.py             # Notebook dataclass, serialization
│   │   └── store.py                # JSON file persistence (~/.lumen/notebooks/)
│   │
│   └── py.typed                    # PEP 561 marker for mypy
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── App.tsx                 # Main app shell
│   │   ├── main.tsx
│   │   ├── components/
│   │   │   ├── NotebookView.tsx    # Cell list / conversation
│   │   │   ├── CellView.tsx        # Single cell: chart + narrative + code
│   │   │   ├── ChartRenderer.tsx   # Vega-Lite rendering with Lumen theme
│   │   │   ├── NarrativeView.tsx   # Narrative with interactive data references
│   │   │   ├── CodeView.tsx        # SQL viewer/editor with syntax highlighting
│   │   │   ├── InputBar.tsx        # Question input
│   │   │   ├── StageIndicator.tsx  # Streaming stage display
│   │   │   └── ConnectionStatus.tsx
│   │   ├── hooks/
│   │   │   ├── useSSE.ts           # SSE connection management
│   │   │   └── useNotebook.ts      # Notebook state management
│   │   ├── types/
│   │   │   ├── cell.ts             # TypeScript types matching Python models
│   │   │   └── events.ts           # SSE event types
│   │   └── styles/
│   │       ├── theme.css           # Design tokens, typography
│   │       └── notebook.css        # Notebook-specific styles
│   └── public/
│       └── fonts/                  # Inter font files (self-hosted)
│
└── tests/
    ├── conftest.py                 # Shared fixtures (test Postgres, sample schemas)
    ├── test_core.py                # Result/Diag types
    ├── test_introspection.py       # Schema introspection
    ├── test_enrichment.py          # Column role inference
    ├── test_augmentation.py        # dbt/md/csv parsing
    ├── test_sql_validation.py      # Safety checks
    ├── test_orchestrator.py        # Agent loop (mocked LLM)
    ├── test_viz_auto_detect.py     # Chart type heuristics
    ├── test_cell_serialization.py  # Cell round-trip
    ├── test_trend.py               # Trend extrapolation
    └── fixtures/
        ├── sample_schema.json      # Test schema fixtures
        ├── sample_dbt_schema.yml   # Test dbt augmentation
        └── sample_results.json     # Test query results
```

---

## 11. Configuration

### `~/.lumen/config.json`

```json
{
  "connections": {
    "analytics": {
      "type": "postgresql",
      "dsn": "postgresql://analyst:***@localhost:5432/analytics",
      "schema": "public"
    }
  },
  "active_connection": "analytics",
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

The API key is read from an environment variable (never stored in the config file). The config file stores only the env var name.

### `~/.lumen/projects/<name>/`

```
my-analytics/
├── schema.yml              # dbt schema (optional)
├── docs.md                 # Data model documentation (optional)
├── dictionary.csv          # Column descriptions (optional)
└── examples/               # Example SQL queries (optional)
    ├── revenue_by_region.sql
    └── pipeline_trend.sql
```

---

## 12. Implementation sequence

Build in this order. Each phase produces a working (if incomplete) system. Never go more than a day without something you can run and see.

### Phase 1: Foundation (days 1-3)
**Goal:** Connect to Postgres, introspect schema, display it. Core types in place.

- [ ] Project scaffold: `pyproject.toml` with uv, ruff, mypy config
- [ ] `core.py` — port `Severity`, `Diag`, `Result[T]` from DuckBook
- [ ] `cli.py` — `lumen connect <dsn>`, `lumen start` (typer)
- [ ] `config.py` — store connection in `~/.lumen/config.json`
- [ ] `introspector.py` — run introspection queries via asyncpg
- [ ] `enricher.py` — column role inference (adapted from DuckBook bootstrap)
- [ ] `context.py` — build `SchemaContext`, serialize to XML, compute hash
- [ ] Basic FastAPI server: `GET /api/schema` returns schema info
- [ ] Minimal React app (Vite + TypeScript) that shows connected schema
- [ ] ruff + mypy passing from day 1

**Checkpoint:** `lumen connect postgres://...` → `lumen start` → browser shows your tables, columns, and inferred roles.

### Phase 2: The core loop (days 4-7)
**Goal:** Ask a question, get a chart and narrative.

- [ ] `tools.py` — define the `analyze_data` tool for Claude API
- [ ] `prompts.py` — build the system prompt with schema context XML
- [ ] `orchestrator.py` — single-turn agent: question → LLM → SQL → execute → cell
- [ ] `runner.py` — execute SQL via asyncpg, return `Result[QueryResult]`
- [ ] `validator.py` — SQL safety checks returning `Result`
- [ ] `cell.py` — Cell Pydantic model, builder function
- [ ] `theme.py` — Lumen Vega-Lite theme JSON
- [ ] SSE endpoint: `POST /api/ask` streams stage events, ends with cell
- [ ] Frontend: `InputBar` → send question → receive SSE events → render `CellView`
- [ ] `ChartRenderer.tsx` — render Vega-Lite spec with Lumen theme
- [ ] `NarrativeView.tsx` — render narrative text
- [ ] `StageIndicator.tsx` — show streaming stages with animation

**Checkpoint:** Ask "what are my top 10 customers by revenue?" and see a styled bar chart with a narrative.

### Phase 3: Conversation and correction (days 8-10)
**Goal:** Multi-turn conversation, refinements, SQL editing, error recovery.

- [ ] `history.py` — build conversation context from previous cells
- [ ] `notebook.py` / `store.py` — persist notebook as JSON, load on startup
- [ ] `NotebookView.tsx` — render multiple cells as a scrollable conversation
- [ ] Refinement: "break that down by quarter" uses previous cell as context
- [ ] `CodeView.tsx` — collapsible SQL view with shiki highlighting
- [ ] SQL editing: user edits SQL → re-execute → call LLM for chart/narrative only
- [ ] Error retry loop: SQL errors fed back to LLM with `Diag` (max 3 attempts)
- [ ] Graceful failure UI: error messages with hints rendered in the cell
- [ ] `auto_detect.py` — viz fallback when LLM chart spec is invalid
- [ ] `viz/validator.py` — basic Vega-Lite spec validation

**Checkpoint:** Have a 5-turn conversation with refinements. Edit SQL mid-conversation. See the agent self-correct on a bad query.

### Phase 4: Schema augmentation (days 11-12)
**Goal:** dbt docs, markdown, CSV improve SQL generation.

- [ ] `augmenter.py` — parse `schema.yml` (dbt), `docs.md`, `dictionary.csv`
- [ ] Merge augmented info into SchemaContext XML
- [ ] `cache.py` — cache schema to disk, detect changes on restart
- [ ] Test: compare SQL quality with and without augmentation on a messy schema
- [ ] Schema refresh: detect column/table changes via hash comparison

**Checkpoint:** Add a dbt schema file, ask the same question, observe measurably better SQL.

### Phase 5: Polish (days 13-16)
**Goal:** Make it feel like a finished product.

- [ ] Vega-Lite theme tuning — test across chart types (line, bar, scatter, histogram, grouped bar, stacked area)
- [ ] Typography and layout polish — Inter font, spacing, colors
- [ ] Narrative ↔ chart linking (start with chart → narrative hover)
- [ ] Input affordances: placeholder text that suggests questions based on schema
- [ ] Empty state: first-launch experience that guides the user
- [ ] Connection status indicator
- [ ] README with clear setup instructions and a GIF/screenshot
- [ ] Handle edge cases: empty results, very large result sets, timeout, disconnection
- [ ] Full ruff + mypy clean across codebase
- [ ] Test suite: core, introspection, enrichment, validation, orchestrator (mocked LLM), viz, cell serialization

**Checkpoint:** Show it to another analyst. Watch them use it without help. Note where they stumble.

### Phase 6: Quiet capabilities (days 17-18)
**Goal:** Trend extrapolation as a surprise feature.

- [ ] `whatif/trend.py` — adapt DuckBook's `trend_extrapolation` SQL to Postgres
- [ ] `whatif/explain.py` — deterministic assumption/caveat generation
- [ ] Extend system prompt: when the user asks about future trends, the LLM can generate a trend query using `regr_slope()` / `regr_intercept()`
- [ ] Render extrapolation as a dashed line with confidence interval band on the chart (Vega-Lite layered spec)
- [ ] Narrative states assumptions clearly: method, R², data range, caveats

**Checkpoint:** Ask "what's the trend for next quarter?" and get a chart with a dashed extrapolation line and clear explanation of assumptions.

---

## 13. API endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/schema` | Return current schema context | `SchemaContext` JSON |
| POST | `/api/ask` | Ask a question (SSE stream) | Stream of `StageEvent` → `CellEvent` |
| POST | `/api/run-sql` | Execute user-edited SQL, get new chart/narrative | `CellEvent` |
| GET | `/api/notebook` | Get current notebook | `Notebook` JSON |
| GET | `/api/notebook/{cell_id}` | Get a specific cell | `Cell` JSON |
| DELETE | `/api/notebook/{cell_id}` | Delete a cell | 204 |
| POST | `/api/notebook/refresh` | Re-execute a cell against current data | `CellEvent` |
| GET | `/api/config` | Get current connection status | Config JSON |
| GET | `/api/health` | Health check | `{"ok": true}` |

---

## 14. Dependencies

### `pyproject.toml`

```toml
[project]
name = "lumen"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "asyncpg>=0.30",
    "anthropic>=0.42",
    "pydantic>=2.10",
    "pyyaml>=6.0",
    "typer>=0.15",
    "rich>=13.9",
    "sse-starlette>=2.2",
    "pglast>=7",
    "numpy>=2.2",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.9",
    "mypy>=1.14",
    "pytest>=8.3",
    "pytest-asyncio>=0.25",
    "httpx>=0.28",
]

[project.scripts]
lumen = "lumen.cli:main"

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "SIM"]

[tool.mypy]
python_version = "3.13"
strict = true
plugins = ["pydantic.mypy"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 15. Later releases (informing architecture, not v1 scope)

These are out of scope for Release Tufte but should not be *prevented* by v1 architecture decisions:

- **Support multiple projects** — Support connections to mutiple databases and their respective configurations. Allow the user to switch between them, resulting in a new session.
- **Additional data sources** — MotherDuck, DuckDB with local Parquet/CSV. The `SchemaContext` and `runner.py` are the abstraction boundary; adding a source type means implementing a new introspector and executor behind the same interface.
- **What-if as a headline feature** — all five techniques from DuckBook, with full explainability.
- **Local model support** — Ollama integration. The `anthropic` client is isolated in `agent/`; swapping to an Ollama client means implementing the same tool-use interface.
- **Collaboration and sharing** — notebook export (HTML, PDF), team sharing.
- **Dashboard publishing** — curated cells become a live, refreshable dashboard. Fundamentally different product surface.
- **DuckDB performance layer** — cache Postgres data locally in DuckDB for faster iteration.
- **MCP server** — expose Lumen as an MCP tool for use in Claude Code or other MCP hosts (as DuckBook did).

---

*This document is the input for implementation. It should be treated as a living reference — update it as decisions are made during development.*