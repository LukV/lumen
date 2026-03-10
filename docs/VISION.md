# Lumen

_From question to insight in one conversation._

## THE PROBLEM

Data analysts spend most of their time wrangling queries and formatting charts — not thinking about what the data means. The typical workflow looks like this: a stakeholder asks a question, the analyst opens a SQL editor, writes queries, pivots results in a spreadsheet, copies charts into slides, and presents findings. The insight takes minutes. The plumbing takes hours.

Every major BI vendor now markets "talk to your data" features. Most of them disappoint. Users try them, ask a moderately complex question, get a wrong answer or a strange chart, lose trust, and never come back. Trust recovery in analytics is brutally hard. This is both the biggest risk in this space and the biggest opportunity.

## WHAT LUMEN IS

Lumen is a conversational analytics notebook. It connects to a data source and lets analysts explore their data through natural language. Ask a question, get a visualization and a narrative. Refine, drill down, change direction — all in conversation. Each question-and-answer pair becomes a cell in a notebook that is reproducible, auditable, and shareable.

Lumen is not a dashboard builder, not a BI platform, and not a chatbot bolted onto a chart library. It is **the analyst's thinking partner**: a tool for the exploration and sensemaking that happens before the dashboard. It sits at the crossroads of conversational interfaces and Jupyter Notebooks. Jupyter became hugely successful because it preserved the analyst's sense of control and reproducibility while making exploration fluid. Lumen aims for the same balance — with natural language as the primary interface.

_"Lumen is a Jupyter Notebook you can talk to."_

## WHO IT IS FOR

The early user is not a casual business user looking for self-serve analytics — that is the graveyard of failed products. Lumen's user is a data-literate analyst who is tired of the grunt work. Someone who knows what they would write in SQL but wants to move faster, and wants the narrative and the visualization generated for free. They care about correctness, reproducibility, and aesthetics. They are skeptical of AI hype. They need to be won over with substance, not sizzle.

As Lumen matures, it expands its circle: first the analyst, then the analyst's colleagues who receive curated dashboards, and eventually the domain expert who asks questions directly. But the analyst remains the gatekeeper — the one who validates, curates, and trusts.

## THREE DESIGN PILLARS

### 1. Explainability

Every visualization can be expanded to reveal the query and logic underneath it. The generated SQL is visible with a single click, collapsed by default as progressive disclosure. Analysts will not trust a black box. The conversation itself is the reproducible artifact — this is what makes Lumen a notebook, not a chatbot.

### 2. Conversational correction

When the chart uses the wrong date field or aggregation, the user says "break that down by quarter instead" or clicks to adjust — they do not start over. The analyst can also edit the generated SQL directly and re-run it, and Lumen respects those edits in the ongoing conversation. This is where most conversational analytics tools fail, and where Lumen must excel.

### 3. Reproducibility

Given the same question against the same data and schema, Lumen produces the same query, the same chart, the same narrative. The system resolves the user's intent into a canonical intermediate representation — a SQL query, a declarative chart specification, a data-bound narrative template — that is deterministic and replayable independently of the LLM. Every insight is auditable and version-controllable. Switching models does not break past work.

## WHAT MAKES LUMEN DIFFERENT

### Narrative as a first-class output

The response is a story, not just a chart. "Pipeline is down 12% YoY, driven primarily by a drop in enterprise deals in Q3. Mid-market has actually grown 8%." That synthesis is what analysts spend hours producing manually. Lumen's narrative voice should read like a sharp analyst wrote it — concise, specific, opinionated where the data supports it.

### Chart and narrative are linked

Hovering over a data point in the chart highlights the relevant part of the narrative. Clicking a number in the narrative highlights it in the chart. The conversation and the visualization are not parallel streams — they are interconnected.

### Beautiful defaults

The first chart a user sees sets the tone. Default colors, typography, and proportions must be beautiful out of the box — inspired by Observable Plot and the Financial Times chart style. Muted, purposeful palettes. No chartjunk. If the first chart looks like a default Excel chart, the spell is broken.

### Quiet analytical power

Beyond showing what happened, Lumen can hint at what could happen. A simple trend extrapolation with confidence intervals, a linear regression with clearly stated assumptions and R2 values. This is not a headline feature — it is a surprise-and-delight moment. Every what-if output states its assumptions plainly, because that is what an analyst expects and what builds trust.

## WHAT WE BELIEVE

We believe the "talk to your data" space is large and mostly fails because products optimize for breadth over trust. Lumen bets on depth: one data source, one interaction loop, done exceptionally well. We would rather support one database flawlessly than ten databases poorly.

We believe the analyst is the right early adopter. Analysts are harder to impress but more forgiving of a narrow scope, because they understand the underlying complexity. Win them, and they become the distribution channel to their organizations.

We believe reproducibility is a moat. Most conversational tools treat LLM output as the final artifact. Lumen treats it as a translation step. The artifact is a structured, deterministic object. This is harder to build but fundamentally more trustworthy — and it is what separates a notebook from a chatbot.

We believe aesthetics are not superficial. A tool that looks and feels crafted earns trust faster. The experience of using Lumen should feel like opening a Moleskine, not a legal pad. Typographic care, restrained color, generous whitespace, calm confidence.

---

## VERSION 1 — RELEASE TUFTE (shipped)

Named for Edward Tufte, the pioneer of data visualization who insisted that every element on a chart must earn its place. This release embodies that principle: nothing ships that is not essential, and everything that ships is polished.

### Scope

A single-page application where the analyst connects to a PostgreSQL database, the system reads the schema, and they begin a conversation that generates visualizations and narratives. No authentication, no sharing, no multi-user features, no dashboard publishing. Just the core loop, done beautifully.

### What shipped

- Two-call LLM orchestration: plan (SQL + chart) then narrate (with actual data)
- Schema introspection, enrichment (role inference), and augmentation (dbt YAML, markdown, CSV)
- SQL validation via pglast AST walking, retry loop with error feedback
- Vega-Lite rendering with FT-inspired theme, auto-detection fallback
- Chart-narrative bidirectional linking
- Code view with SQL editing and re-execution
- Trend extrapolation as a quiet what-if capability
- Notebook persistence with atomic writes
- CLI: `lumen connect`, `lumen start`

---

## VERSION 2 — RELEASE PROEF

### Context

Release Proef is shaped by a first engagement and stakeholder input.

### Design principles for Proef

**Do little, do it right.** The client workshops generated a rich wishlist. We filter aggressively. Every feature must pass the test: "Does this make the analyst's first session magical?" If not, it waits.

**Analyst first, business user second.** The client's instinct is to put business users in the driver's seat. We resist this gently. The analyst validates the data, curates the experience, builds trust. Business users benefit downstream — through dashboards, storyboards, and sharing — but the analyst is the quality gate.

**Brand without a brand platform.** The client needs their visual identity. We deliver it through configuration, not through building a white-label admin panel.

### 2.1 — Theming and identity

Lumen instances should feel like they belong to the organization that deploys them. Release Proef introduces a theme configuration that controls the visual identity without touching code.

**What ships:**
- A `theme.json` configuration file per project: app name, logo path, primary/secondary/accent colors, font family
- Vega-Lite chart theme derived from the brand colors — charts feel native to the organization's visual language
- Light and dark mode variants generated from the base palette
- Locale support

**What does not ship:**
- No brand builder UI — the theme file is edited by hand or by the deployment team
- No runtime theme switching — one theme per instance
- No custom logo upload flow — a file path in the config

### 2.2 — Geographic visualization

The stakeholder is missing the geographic dimension municipality. Without maps, users are forced to ask "show me a table of the top 10 municipalities by library visits" when what they mean is "show me where the library visits are." Maps turn a lookup into a pattern.

**What ships:**
- Bubble maps as a first-class Vega-Lite visualization type: each municipality rendered as a circle at its geographic centroid, sized and colored by the measure value
- A geographic lookup file for Vlaamse gemeenten (178 municipalities with lat/lon coordinates, derived from the client's municipalities dataset), keyed by NIS code
- The LLM learns when to choose a map: geographic dimension + a single measure = bubble map
- Auto-detection fallback: if the result contains a recognized geographic key column and a numeric measure, suggest a map
- Background layer of all municipalities for geographic context, even when the query filters to a subset
- Color and size scale derived from the brand palette

**What does not ship:**
- No choropleth (polygon) maps — we have point coordinates, not boundary files. Bubble maps are cleaner for this data.
- No interactive map drilling (click a municipality to filter) — that is a Release 3+ feature
- No custom geographic datasets — the lookup file is bundled per deployment

### 2.3 — Live reasoning stream

When a user asks a complex question and stares at a spinner for 8 seconds, trust erodes. The LLM is doing useful work during that time — reading the schema, reasoning about joins, considering chart types. Showing that reasoning live transforms dead time into a trust-building moment.

**What ships:**
- The reasoning trace streams to the frontend in real time during Call 1 (plan), displayed in a collapsible panel below the stage indicator
- Reasoning text appears as a calm, monospaced stream — not a chat bubble, not a dramatic reveal. Think: a craftsperson's workbench visible through a glass wall
- When the cell completes, the reasoning collapses into the existing code view tab
- The stage indicator gains richer labels: "Reading schema..." → "Reasoning about joins..." → "Writing SQL..." → "Executing query..." → "Composing narrative..."

**What does not ship:**
- No editable reasoning — this is a window, not an input
- No reasoning for Call 2 (narrate) — that call is fast enough that streaming adds noise

### 2.4 — Data dictionary

With 60+ indicators, the most common first question is not analytical — it is navigational. "What data do you have about migration numbers?" The data dictionary turns the schema from a hidden context into a browsable, inviting surface.

**What ships:**
- A slide-out panel (triggered from the top bar) showing all tables, expandable to columns with descriptions and roles
- Each column shows: name, type, role badge (measure, dimension, time, key), and the description from the dbt YAML or augmented docs
- A search/filter within the panel — type "biblio" and see all library-related columns across tables
- "Ask about this" action on the datamodel

**What does not ship:**
- No data dictionary editing via UI — descriptions come from the YAML/docs files
- No "suggest a new indicator" workflow — the graceful refusal message points users to the right contact
- No column-level lineage or data quality indicators

---

## ROADMAP

The items below are organized by theme, not by release. They represent the full product vision — what Lumen becomes if it succeeds. Ordering reflects our current best judgment of impact and dependency, not a commitment to sequence.

### Near horizon — foundations for multi-user deployment

**Connection management via UI.** Replace CLI-only `lumen connect` with a settings panel for adding, editing, and switching database connections. Essential before any multi-user deployment. The analyst should be able to connect to a new data source without touching the terminal.

**Conversation memory and personalization.** The system remembers what the user has asked before, learns their preferred dimensions and measures, and suggests relevant follow-ups. When the system cannot answer, it logs the gap and revisits it: "You asked about X last week — we still don't have that data, but here's who to contact about adding it."

**Extended notebook cells.** The notebook currently supports only LLM-generated SQL+chart cells. Extend to support hand-written SQL cells, Python cells (for custom transformations), and text/markdown cells (for annotations and section headers). This turns the notebook from a conversation transcript into a curated analytical document.

### Mid horizon — analytical depth

**What-if modeling as a headline feature.** Release Tufte shipped trend extrapolation as a quiet capability. This promotes what-if to a first-class interaction: "What happens to library visits if we cut the budget by 15%?" Complex scenario models — financial impact of cuts/investments, geographic spread of infrastructure changes, stress testing — with clear assumptions, sensitivity parameters, and confidence indicators. Not just linear regression: configurable models with explicit trade-offs.

**Predictive analytics with agentic ML.** The agent selects an appropriate algorithm, trains a model on the connected data, applies it, and presents results — all conversationally. Output includes model performance metrics (accuracy, R2, confusion matrix), a summary of the most important features, and a results table. The analyst can adjust parameters and re-train. This is not AutoML-as-a-black-box — it is guided, explainable model building.

**Dashboard publishing.** Gather cells from the notebook and publish them as a standalone dashboard — a React application with live SQL queries, editable layout, and shareable URL. The dashboard is a different product surface than the notebook: it is read-optimized, designed for the business user who consumes insights rather than produces them. The generated React code is inspectable and editable.

### Far horizon — platform capabilities

**Sharing and collaboration.** Multiple users working on the same notebook. Comments, annotations, version history. This requires authentication, which opens the door to access management.

**Access management (data).** Role-based access to datasets, driven by an external IdP. A user with a "cultuur" role sees culture tables; a user with a "jeugd" role sees youth tables. Row-level security where the connected database supports it.

**Access management (models).** Role-based access to LLM models. Sensitive queries route to local models; complex queries route to hosted models (Claude, GPT). The routing can be automatic (based on data classification) or manual (user chooses).

**Pseudonymization.** Sensitive data is anonymized before being sent to hosted LLMs. Column-level classification (PII, financial, health) drives automatic masking. The LLM sees anonymized values; the narrative references real values from the local result set. Essential for government and healthcare deployments.

**Model flexibility.** Switch between LLM providers: local models via Ollama for air-gapped or cost-sensitive deployments, hosted models for maximum quality. The system recommends a model based on query complexity: simple lookups use a fast local model, complex analytical questions use a frontier model.

**Performance layer.** An optimized local storage layer using DuckDB for caching query results and enabling fast re-aggregation without hitting the source database on every interaction. Particularly valuable for large datasets or slow source connections.

**Multiple data source types.** Beyond PostgreSQL: DuckDB reading local Parquet/CSV files ("point it at your data files and start talking"), Snowflake, BigQuery. Each source type implements the same schema introspection and execution interface. Start with DuckDB for the compelling local-first story.

**Agentic data ingestion.** Point Lumen at an API endpoint or a file, and an agent creates a dimensional schema, generates dbt models, and ingests the data. This collapses the "get data into a queryable shape" step that currently happens outside Lumen.

**Schema change detection.** The agent monitors the connected database for schema changes and notifies the user: "The table `stg_uitpas` gained 3 new columns since your last session. Would you like to explore them?" Paired with the data dictionary, this makes new data sources discoverable without manual communication.

**Personalized storyboards.** Based on conversation memory and user roles, Lumen generates and pushes periodic storyboards — curated narratives with key metrics, trends, and anomalies. A weekly email or in-app briefing: "Here's what changed in your data this week." The storyboard is a notebook published on a schedule, not a separate product.

---

_Lumen exists because we believe analysts deserve better tools — tools that respect their intelligence, protect their data, show their work, and look as good as the insights they produce. Release Tufte proved the core loop. Release Proef proves it works in the real world._
