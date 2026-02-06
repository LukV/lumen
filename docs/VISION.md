Lumen

From question to insight in one conversation.

## THE PROBLEM

Data analysts spend most of their time wrangling queries and formatting charts — not thinking about what the data means. The typical workflow looks like this: a stakeholder asks a question, the analyst opens a SQL editor, writes queries, pivots results in a spreadsheet, copies charts into slides, and presents findings. The insight takes minutes. The plumbing takes hours.

Every major BI vendor now markets “talk to your data” features. Most of them disappoint. Users try them, ask a moderately complex question, get a wrong answer or a strange chart, lose trust, and never come back. Trust recovery in analytics is brutally hard. This is both the biggest risk in this space and the biggest opportunity.

## WHAT LUMEN IS

Lumen is a conversational analytics notebook. It connects to a data source and lets analysts explore their data through natural language. Ask a question, get a visualization and a narrative. Refine, drill down, change direction — all in conversation. Each question-and-answer pair becomes a cell in a notebook that is reproducible, auditable, and shareable.

Lumen is not a dashboard builder, not a BI platform, and not a chatbot bolted onto a chart library. It is the analyst’s thinking partner: a tool for the exploration and sensemaking that happens before the dashboard. It sits at the crossroads of conversational interfaces and Jupyter Notebooks. Jupyter became hugely successful because it preserved the analyst’s sense of control and reproducibility while making exploration fluid. Lumen aims for the same balance — with natural language as the primary interface.

“Lumen is a Jupyter Notebook you can talk to.”

## WHO IT IS FOR

The early user is not a casual business user looking for self-serve analytics — that is the graveyard of failed products. Lumen’s user is a data-literate analyst who is tired of the grunt work. Someone who knows what they would write in SQL but wants to move faster, and wants the narrative and the visualization generated for free. They care about correctness, reproducibility, and aesthetics. They are skeptical of AI hype. They need to be won over with substance, not sizzle.

## THREE DESIGN PILLARS

1. Explainability

Every visualization can be expanded to reveal the query and logic underneath it. The generated SQL is visible with a single click, collapsed by default as progressive disclosure. Analysts will not trust a black box. The conversation itself is the reproducible artifact — this is what makes Lumen a notebook, not a chatbot.

2. Conversational correction

When the chart uses the wrong date field or aggregation, the user says “break that down by quarter instead” or clicks to adjust — they do not start over. The analyst can also edit the generated SQL directly and re-run it, and Lumen respects those edits in the ongoing conversation. This is where most conversational analytics tools fail, and where Lumen must excel.

3. Reproducibility

Given the same question against the same data and schema, Lumen produces the same query, the same chart, the same narrative. The system resolves the user’s intent into a canonical intermediate representation — a SQL query, a declarative chart specification, a data-bound narrative template — that is deterministic and replayable independently of the LLM. Every insight is auditable and version-controllable. Switching models does not break past work.



## WHAT MAKES LUMEN DIFFERENT

Narrative as a first-class output

The response is a story, not just a chart. “Pipeline is down 12% YoY, driven primarily by a drop in enterprise deals in Q3. Mid-market has actually grown 8%.” That synthesis is what analysts spend hours producing manually. Lumen’s narrative voice should read like a sharp analyst wrote it — concise, specific, opinionated where the data supports it.

Chart and narrative are linked

Hovering over a data point in the chart highlights the relevant part of the narrative. Clicking a number in the narrative highlights it in the chart. The conversation and the visualization are not parallel streams — they are interconnected.

Beautiful defaults

The first chart a user sees sets the tone. Default colors, typography, and proportions must be beautiful out of the box — inspired by Observable Plot and the Financial Times chart style. Muted, purposeful palettes. No chartjunk. If the first chart looks like a default Excel chart, the spell is broken.

Quiet analytical power

Beyond showing what happened, Lumen can hint at what could happen. A simple trend extrapolation with confidence intervals, a linear regression with clearly stated assumptions and R² values. This is not a headline feature — it is a surprise-and-delight moment. Every what-if output states its assumptions plainly, because that is what an analyst expects and what builds trust.

Local-first, transparent

Lumen runs on the analyst’s laptop. No accounts, no cloud, no telemetry. Data never leaves the machine — which sidesteps one of the biggest trust barriers in enterprise analytics. The only exception is the LLM API call, and Lumen is fully transparent about exactly what is sent.

## WHAT WE BELIEVE

We believe the “talk to your data” space is large and mostly fails because products optimize for breadth over trust. Lumen bets on depth: one data source, one interaction loop, done exceptionally well. We would rather support one database flawlessly than ten databases poorly.

We believe the analyst, not the business user, is the right early adopter. Analysts are harder to impress but more forgiving of a narrow scope, because they understand the underlying complexity. Win them, and they become the distribution channel to their organizations.

We believe reproducibility is a moat. Most conversational tools treat LLM output as the final artifact. Lumen treats it as a translation step. The artifact is a structured, deterministic object. This is harder to build but fundamentally more trustworthy — and it is what separates a notebook from a chatbot.

We believe aesthetics are not superficial. A tool that looks and feels crafted earns trust faster. The experience of using Lumen should feel like opening a Moleskine, not a legal pad. Typographic care, restrained color, generous whitespace, calm confidence.



## VERSION 1 — RELEASE TUFTE

Named for Edward Tufte, the pioneer of data visualization who insisted that every element on a chart must earn its place. This release embodies that principle: nothing ships that is not essential, and everything that ships is polished.

Scope

A single-page application where the analyst connects to a PostgreSQL database, the system reads the schema, and they begin a conversation that generates visualizations and narratives. No authentication, no sharing, no multi-user features, no dashboard publishing. Just the core loop, done beautifully.

The test is simple: if an analyst sits down with Lumen and the interaction feels magical, we have something. If it does not, no amount of features will save it.

Setup

Clone the repository, install, connect, start. Four steps, under a minute. Lumen opens in the browser on localhost. To enrich SQL generation quality, the analyst can drop schema documentation into the project folder — a dbt schema.yml, a markdown file with table descriptions, a CSV with sample data. Lumen reads these alongside the introspected schema. Schema changes in the source database are detected on refresh.

The interaction loop

The user asks a question in natural language. Lumen generates SQL, executes it against the database, selects an appropriate chart type, renders the visualization, and writes a concise narrative. The user can refine: ask a follow-up, adjust the scope, or edit the SQL directly. Each exchange is a cell in the notebook. The full conversation is the artifact.

The code view

Always available, one click to expand. The analyst can see the generated SQL, edit it, and re-run. Power users can also inspect the chart specification. Edits are respected in the conversation context. This is progressive disclosure: the default experience is conversational, the code is there when you need it.

Streaming and trust

When a question is processing, Lumen shows the stages transparently: reading schema, generating query, executing, building visualization. Each stage has a subtle animation. No blank spinners. This is not just UX polish — it makes the process legible and builds trust. It also directly supports the explainability pillar.

LLM integration

Version 1 uses Claude’s API for natural language understanding, SQL generation, chart specification, and narrative writing via structured tool calling. The user can see exactly what is sent to the API at any time. Support for local models via Ollama is planned for a later release, but the quality gap currently makes it incompatible with Lumen’s core value proposition.

## ARCHITECTURE SKETCH

Schema layer

On connection, Lumen introspects the database and builds a semantic map: table names, column names and types, foreign key relationships, sample values for categorical columns. This context, augmented by any user-provided documentation, is what makes the LLM effective. It is cached and refreshed when the source changes.

LLM orchestration

The user’s question plus schema context is sent to Claude via structured tool calling. The model returns a SQL query, a chart specification (type, axes, grouping, formatting), and a narrative. Corrections and follow-ups include the conversation history to maintain context.

Execution engine

The generated SQL is validated, then executed against the connected database. Results are returned as structured data. Errors are surfaced clearly, with suggestions for how to rephrase or what the schema does support.

Rendering layer

A declarative chart specification (aligned with Vega-Lite or Observable Plot) is rendered with defaults inspired by the Financial Times style: muted palettes, clean typography, no chartjunk. The narrative is rendered alongside with bidirectional linking to the chart.

Frontend

A clean, minimal React application. Each conversation cell contains the question, the visualization, the narrative, and the collapsible code view. The interface prioritizes whitespace, typographic care, and responsiveness.

## LATER RELEASES

These are deliberately out of scope for Release Tufte, but inform architectural decisions from day one:

Additional data sources — Snowflake, BigQuery, DuckDB with local Parquet and CSV files (“point it at your data files and start talking”).

What-if as a headline feature — regressions, Monte Carlo simulations, sensitivity analysis, all with the same explainability standards as the core product.

Local model support — Ollama integration for fully air-gapped environments, once model quality supports it.

Collaboration and sharing — notebook export, team sharing, commenting.

Dashboard publishing — turning a curated set of cells into a live, refreshable dashboard. This is a fundamentally different product surface and should not be rushed.

Performance layer — an optimized local storage layer using DuckDB for faster iteration on large datasets.



—

Lumen exists because we believe analysts deserve better tools — tools that respect their intelligence, protect their data, show their work, and look as good as the insights they produce. Release Tufte is the first step: small in scope, uncompromising in quality.