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
source ./.venv/bin/activate
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

Check the active connection at any time:

```bash
lumen status
```

```
Connection: default
DSN: postgresql://user:***@localhost:5432/mydb
Schema: public
Theme: default
Project dir: /Users/lukv/.lumen/projects/default
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

MIT
