# Lumen

**From question to insight in one conversation.**

The wider story — category, positioning, who pays — lives at [lumen-analytics.com](https://lumen-analytics.com). This README is the technical entry point.

## Where we stand

Lumen today is a conversational analytics notebook. Connect it to a PostgreSQL database or a directory of Parquet files, ask a question in plain language, and get back a SQL query, a visualization, and a narrative in one cycle. Refine with follow-ups, edit the SQL directly, or drill down further. Each exchange becomes a cell in a notebook that is reproducible, auditable, and entirely local.

Underneath the notebook, a "substrate" is taking shape: Domain (curated definitions, entities, metrics), Policy (access, masking, disclosure), and Runtime (governed SQL, audit on every answer, refusal as a typed output when the data cannot support a claim). Today this substrate is embedded as the schema precursor inside Lumen's Python backend; a standalone service is the next phase. Lumen does not trust the LLM; it trusts the substrate around it.

## Where we're going

The notebook is the first of three product forms that share one kernel — schema introspection, deterministic queries, narrative beside numbers, sources, version history — and differ in who initiates and what comes out the other end:

- **Notebook** — the analyst asks, refines, drills down. The artifact is the conversation itself. 
- **Brief** — a published, narrative-led document handed from the analyst to the organization once the exploration has earned the right to be shared. *Design in progress.*
- **Lead** — the agent initiates. Lumen pushes back with something worth a look, drawing on a memory of past work. *Design in progress.*

The three forms feed each other: **lead → notebook → brief → memory → next lead**. That loop is what turns one-off conversations into a shared knowledge base.

Two other directions matter alongside the form axis. Lumen will climb a **depth ladder** from descriptive (the notebook today) into diagnostic and scenario questions — without ever silently promoting one kind of question into another. And the kernel is being written under a permissive license, in open formats, deployable from a laptop to a private cloud to a hosted multi-tenant runtime, all running the same code.

The category we sell into is **Governed AI Analytics** — AI-ready BI and data governance, built for autonomous analysis. The argument behind that framing, the buyer it's shaped for, and the partner conversations testing the thesis are all on [lumen-analytics.com](https://lumen-analytics.com).

## How it works

1. **Connect** — Lumen introspects your data source (PostgreSQL or Parquet files via DuckDB): tables, columns, types, foreign keys, sample values. It builds a semantic map that makes the LLM effective.
2. **Ask** — Type a question. Lumen generates SQL, executes it, picks the right chart type, renders a Vega-Lite visualization, and writes a concise narrative.
3. **Refine** — Ask follow-ups, adjust scope, or edit the generated SQL directly. Lumen threads the conversation and respects your edits.
4. **Augment** — Drop a dbt `schema.yml`, a markdown file, or a CSV data dictionary into your project folder. Lumen reads these alongside the introspected schema for better SQL generation.

Everything runs on your machine. Data never leaves localhost — the only external call is to the Claude API for language understanding.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- A data source: PostgreSQL database **or** a directory of Parquet files
- An [Anthropic API key](https://console.anthropic.com/)

## Installation

```bash
git clone https://github.com/LukV/lumen.git
cd lumen
uv sync --all-extras
source ./.venv/bin/activate
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Getting started

### 1. Connect to a data source

Lumen supports two data source types: PostgreSQL databases and local Parquet files.

#### Option A: PostgreSQL

Connect to a running PostgreSQL database by passing a connection string:

```bash
lumen connect "postgresql://user:pass@localhost:5432/mydb --name mydb"
```

Lumen introspects the schema via `information_schema` and `pg_stats`: tables, columns, types, primary/foreign keys, distinct counts, sample values, min/max ranges. It enriches columns with role detection (keys, time dimensions, categoricals, measures) and caches the result.

Common options:

```bash
# Connect to a specific schema
uv run lumen connect "postgresql://user:pass@localhost:5432/mydb" --schema analytics
```

The database user only needs `SELECT` privileges. Lumen never writes to your database.

#### Option B: Parquet files

Point Lumen at a directory containing `.parquet` files:

```bash
uv run lumen connect --parquet ./my-data/
```

Lumen uses an embedded DuckDB engine to:
1. Scan the directory for all `.parquet` files
2. Create a DuckDB view for each file (filename becomes the table name: `orders.parquet` → `orders`)
3. Introspect column metadata, types, row counts, and statistics
4. Cache the schema for fast startup

This means no database server is needed — DuckDB runs in-process. The Parquet files are read directly from disk.

```bash
# Example: connect to an open data export
uv run lumen connect --parquet ~/Downloads/open-data/ --name nyc-cab-drives

# Files are mapped to tables by filename:
#   customers.parquet  →  customers
#   fact_orders.parquet  →  fact_orders
#   2024-revenue.parquet  →  2024_revenue  (hyphens become underscores)
```

#### Managing connections

Check the active connection:

```bash
uv run lumen status
```

```
Connection: default
DSN: postgresql://user:***@localhost:5432/mydb
Schema: public
Theme: default
Project dir: /Users/lukv/.lumen/projects/default
```

Switch between named connections by re-running `lumen connect` with the same `--name`. The last connected source becomes the active connection.

### 2. Add documentation (optional)

Place any of these files in `~/.lumen/projects/<connection-name>/` to improve SQL generation quality:

**dbt schema.yml** — table and column descriptions:
```yaml
# ~/.lumen/projects/default/schema.yml
models:
  - name: orders
    description: Sales orders in the pipeline.
    columns:
      - name: amount
        description: Deal value in USD
      - name: status
        description: "Current stage: prospecting, qualification, closed_won, closed_lost"
```

**Markdown docs** — free-form context:
```markdown
# ~/.lumen/projects/default/docs.md
The fiscal year starts in April. Q1 = Apr-Jun, Q2 = Jul-Sep, etc.
"Active" customers are those with at least one order in the last 12 months.
```

**CSV data dictionary** — column-level descriptions:
```csv
table,column,description
orders,amount,Deal value in USD
orders,status,Current deal stage
customers,tier,Account tier based on annual spend
```
~
Re-run `lumen connect` to pick up documentation changes. Lumen detects schema staleness automatically.

### 3. Configure theming and locale (optional)

Create a `theme.json` in your project folder to customize branding, colors, fonts, and language:

```json
// ~/.lumen/projects/<connection-name>/theme.json
{
  "app_name": "My Analytics",
  "locale": "nl",
  "colors": {
    "primary": "#2B979D",
    "secondary": "#CC5621",
    "accent": "#5D6009"
  },
  "fonts": {
    "body": "Inter",
    "editorial": "Source Serif 4"
  }
}
```

All fields are optional — omitted values fall back to defaults.

| Field | Default | Description |
|-------|---------|-------------|
| `app_name` | `"Lumen"` | Displayed in the topbar |
| `locale` | `"en"` | UI language (`en`, `nl`). Also controls the language of generated narratives |
| `logo_path` | `null` | Path to a logo image (served as a static asset) |
| `colors.primary` | `"#4A2D4F"` | Primary accent color (buttons, highlights, charts) |
| `colors.secondary` | `"#C2876E"` | Secondary chart color |
| `colors.accent` | `"#6B8F8A"` | Third chart color |
| `colors.palette` | derived | Full chart color palette (list of 3-6 hex strings). When omitted, derived from primary/secondary/accent |
| `fonts.body` | `"DM Sans"` | UI and chart label font |
| `fonts.editorial` | `"Source Serif 4"` | Narrative and heading font |
| `fonts.mono` | `"JetBrains Mono"` | Code font |
| `fonts.custom_css` | `null` | URL to a CSS file with `@font-face` declarations for custom fonts |

The theme is loaded on server start and served to the frontend via `GET /api/theme`. Colors propagate to CSS custom properties and Vega-Lite chart configs automatically — no frontend rebuild needed.

A global fallback theme can be placed at `~/.lumen/theme.json`. The resolution order is: project theme → global theme → built-in defaults.

#### Supported locales

| Code | Language |
|------|----------|
| `en` | English (default) |
| `nl` | Dutch |

The locale setting affects two things:
1. **UI chrome** — all labels, buttons, placeholders, and stage indicators are translated.
2. **Narratives** — the LLM writes its data insights in the configured language.

### 4. Launch the UI

```bash
uv run lumen start
```

This opens Lumen in your browser at `http://localhost:8000` and prints the active connection. Start asking questions.

Use `--no-browser` to suppress the automatic browser launch, or `--port` to change the port:

```bash
uv run lumen start --port 3000 --no-browser
```

## Development

Install dev dependencies:

```bash
uv sync --all-extras
```

Run the checks:

```bash
uv run ruff check lumen/ tests/     # lint
uv run ruff format lumen/ tests/    # format
uv run mypy lumen/                  # type check (strict)
uv run pytest tests/                # test
```

### Frontend

The frontend is a React + TypeScript + Vite application:

```bash
cd frontend
npm install
npm run dev
```

This starts the Vite dev server at `http://localhost:5173`, proxying API calls to the backend on port 8000.

## License

All rights reserved.

Copyright 2026 Departement Cultuur, Jeugd en Media - Vlaamse overheid

This repository contains proprietary code. No permission is granted
to use, copy, modify, or distribute this software without explicit consent.