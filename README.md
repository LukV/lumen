# Lumen

**From question to insight in one conversation.**

Lumen is a conversational analytics notebook. Connect it to a PostgreSQL database, ask a question in plain English, and get back a SQL query, a visualization, and a narrative — all in one step. Refine with follow-ups, edit the SQL directly, or drill down further. Each exchange becomes a cell in a notebook that is reproducible, auditable, and entirely local.

Lumen is not a dashboard builder or a chatbot bolted onto a chart library. It is the analyst's thinking partner: a tool for the exploration and sensemaking that happens *before* the dashboard.

## How it works

1. **Connect** — Lumen introspects your PostgreSQL schema: tables, columns, types, foreign keys, sample values. It builds a semantic map that makes the LLM effective.
2. **Ask** — Type a question. Lumen generates SQL, executes it, picks the right chart type, renders a Vega-Lite visualization, and writes a concise narrative.
3. **Refine** — Ask follow-ups, adjust scope, or edit the generated SQL directly. Lumen threads the conversation and respects your edits.
4. **Augment** — Drop a dbt `schema.yml`, a markdown file, or a CSV data dictionary into your project folder. Lumen reads these alongside the introspected schema for better SQL generation.

Everything runs on your machine. Data never leaves localhost — the only external call is to the Claude API for language understanding.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- A running PostgreSQL database
- An [Anthropic API key](https://console.anthropic.com/)

## Installation

```bash
git clone https://github.com/LukV/lumen.git
cd lumen
uv sync --all-extras
```

Set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Getting started

### 1. Connect to your database

```bash
uv run lumen connect "postgresql://user:pass@localhost:5432/mydb"
```

Lumen introspects the schema, enriches columns with role detection (keys, time dimensions, categoricals, measures), and caches the result. You'll see a summary of every table and column.

Use `--name` to manage multiple connections:

```bash
uv run lumen connect "postgresql://..." --name staging
```

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

Re-run `lumen connect` to pick up documentation changes. Lumen detects schema staleness automatically.

### 3. Launch the UI

```bash
uv run lumen start
```

This opens Lumen in your browser at `http://localhost:8000`. Start asking questions.

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

MIT
