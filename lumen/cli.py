"""CLI entry points: `lumen connect` and `lumen start`."""

from __future__ import annotations

import asyncio
import webbrowser

import typer
from rich.console import Console
from rich.table import Table

from lumen.config import ConnectionConfig, ensure_dirs, load_config, project_dir, save_config
from lumen.schema.augmenter import augment_schema
from lumen.schema.cache import is_stale, save_cache
from lumen.schema.context import SchemaContext, compute_hash
from lumen.schema.enricher import enrich
from lumen.schema.introspector import introspect

app = typer.Typer(name="lumen", help="Conversational analytics notebook.")
console = Console()


@app.command()
def connect(
    dsn: str = typer.Argument(help="PostgreSQL connection string"),
    name: str = typer.Option("default", "--name", "-n", help="Connection name"),
    schema_name: str = typer.Option("public", "--schema", "-s", help="Schema to introspect"),
) -> None:
    """Connect to a PostgreSQL database and introspect its schema."""
    ensure_dirs()
    asyncio.run(_connect(dsn, name, schema_name))


async def _connect(dsn: str, name: str, schema_name: str) -> None:
    console.print("[bold]Connecting to database...[/bold]")

    result = await introspect(dsn, schema_name)

    if not result.ok or result.data is None:
        for d in result.diagnostics:
            console.print(f"[red]Error:[/red] {d.message}")
            if d.hint:
                console.print(f"  Hint: {d.hint}")
        raise typer.Exit(1)

    snapshot = result.data
    enriched = enrich(snapshot)

    # Augment with external documentation
    proj_dir = project_dir(name)
    augmented_docs = augment_schema(proj_dir, enriched)
    ctx = SchemaContext(enriched=enriched, augmented_docs=augmented_docs or None)
    ctx.hash = compute_hash(ctx)

    # Check staleness against cached version
    stale = is_stale(name, ctx.hash)

    # Save config
    config = load_config()
    config.connections[name] = ConnectionConfig(dsn=dsn, schema_name=schema_name)
    config.active_connection = name
    save_config(config)

    # Cache schema
    await save_cache(name, ctx)

    # Print summary
    console.print(f"\n[green]Connected to [bold]{enriched.database}[/bold][/green]")
    status_label = "[yellow]schema changed[/yellow]" if stale else "[dim]unchanged[/dim]"
    console.print(f"Schema: {enriched.schema_name} | Hash: {ctx.hash[:20]}... | {status_label}")

    if augmented_docs:
        # Count augmented tables/columns
        doc_lines = augmented_docs.split("\n")
        table_count = sum(1 for line in doc_lines if line.startswith("## Table:"))
        col_count = sum(1 for line in doc_lines if line.startswith("- "))
        console.print(f"[cyan]Augmented docs:[/cyan] {table_count} tables, {col_count} columns documented")

    for table in enriched.tables:
        t = Table(title=f"{table.name} (~{table.row_count} rows)", show_lines=False)
        t.add_column("Column", style="cyan")
        t.add_column("Type")
        t.add_column("Role", style="green")
        t.add_column("Details")

        for col in table.columns:
            details = []
            if col.is_primary_key:
                details.append("PK")
            if col.foreign_key:
                details.append(f"FK→{col.foreign_key}")
            if col.suggested_agg:
                details.append(f"agg:{col.suggested_agg}")
            if col.sample_values:
                details.append(f"values:{col.sample_values[:3]}")
            if col.min_value and col.max_value:
                details.append(f"range:{col.min_value}..{col.max_value}")

            t.add_row(col.name, col.data_type, col.role, ", ".join(details))

        console.print(t)
        console.print()

    console.print("[green]Schema cached. Run [bold]lumen start[/bold] to launch the UI.[/green]")


@app.command()
def start(
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve on"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser"),
) -> None:
    """Start the Lumen server."""
    import logging

    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    config = load_config()
    if not config.active_connection:
        console.print("[red]No active connection. Run [bold]lumen connect[/bold] first.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]Starting Lumen on port {port}...[/bold]")

    if not no_browser:
        webbrowser.open(f"http://localhost:{port}")

    uvicorn.run("lumen.server:app", host="0.0.0.0", port=port, reload=False)


def main() -> None:
    app()
