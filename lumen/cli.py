"""CLI entry points: `lumen connect` and `lumen start`."""

from __future__ import annotations

import asyncio
import webbrowser

import typer
from rich.console import Console
from rich.table import Table

from lumen.config import ConnectionConfig, ensure_dirs, load_config, project_dir, save_config
from lumen.datasource.protocol import DataSource
from lumen.schema.augmenter import augment_schema
from lumen.schema.cache import is_stale, save_cache
from lumen.schema.context import SchemaContext, compute_hash
from lumen.schema.enricher import enrich

app = typer.Typer(name="lumen", help="Conversational analytics notebook.")
console = Console()


@app.command()
def connect(
    dsn: str = typer.Argument(None, help="PostgreSQL connection string"),
    parquet: str = typer.Option(None, "--parquet", help="Path to directory of Parquet files"),
    name: str = typer.Option("default", "--name", "-n", help="Connection name"),
    schema_name: str = typer.Option("public", "--schema", "-s", help="Schema to introspect"),
) -> None:
    """Connect to a data source and introspect its schema."""
    ensure_dirs()

    if parquet and dsn:
        console.print("[red]Provide either a DSN or --parquet, not both.[/red]")
        raise typer.Exit(1)
    if not parquet and not dsn:
        console.print("[red]Provide a PostgreSQL DSN or --parquet path.[/red]")
        raise typer.Exit(1)

    if parquet:
        from pathlib import Path

        parquet_path = Path(parquet).resolve()
        if not parquet_path.is_dir():
            console.print(f"[red]Directory not found: {parquet_path}[/red]")
            raise typer.Exit(1)
        parquet_files = list(parquet_path.glob("*.parquet"))
        if not parquet_files:
            console.print(f"[red]No .parquet files found in {parquet_path}[/red]")
            raise typer.Exit(1)

        from lumen.datasource.duckdb_source import DuckDBSource

        ds: DataSource = DuckDBSource(str(parquet_path))
        conn_config = ConnectionConfig(type="duckdb", parquet_path=str(parquet_path))
    else:
        from lumen.datasource.postgres import PostgresSource

        ds = PostgresSource(dsn, schema_name)
        conn_config = ConnectionConfig(type="postgresql", dsn=dsn, schema_name=schema_name)

    asyncio.run(_connect(ds, name, conn_config))


async def _connect(ds: DataSource, name: str, conn_config: ConnectionConfig) -> None:
    console.print("[bold]Connecting to data source...[/bold]")

    result = await ds.introspect()

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
    augment_result = augment_schema(proj_dir, enriched)
    ctx = SchemaContext(enriched=enriched, augmented_docs=augment_result.data or None)
    ctx.hash = compute_hash(ctx)

    # Check staleness against cached version
    stale = is_stale(name, ctx.hash)

    # Save config
    config = load_config()
    config.connections[name] = conn_config
    config.active_connection = name
    save_config(config)

    # Cache schema
    await save_cache(name, ctx)

    # Print summary
    console.print(f"\n[green]Connected to [bold]{enriched.database}[/bold][/green]")
    status_label = "[yellow]schema changed[/yellow]" if stale else "[dim]unchanged[/dim]"
    console.print(f"Schema: {enriched.schema_name} | Hash: {ctx.hash[:20]}... | {status_label}")

    if augment_result.data:
        # Count augmented tables/columns
        doc_lines = augment_result.data.split("\n")
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
    console.print(f"[dim]Connection:[/dim] {config.active_connection}")

    if not no_browser:
        webbrowser.open(f"http://localhost:{port}")

    uvicorn.run("lumen.server.app:app", host="0.0.0.0", port=port, reload=False)


@app.command()
def status() -> None:
    """Show the current connection and project status."""
    config = load_config()
    if not config.active_connection:
        console.print("[yellow]No active connection.[/yellow] Run [bold]lumen connect[/bold] first.")
        raise typer.Exit(0)

    conn_name = config.active_connection
    conn = config.connections.get(conn_name)
    console.print(f"[bold]Connection:[/bold] {conn_name}")
    if conn:
        # Mask password in DSN for display
        import re

        display_dsn = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", conn.dsn)
        console.print(f"[dim]DSN:[/dim] {display_dsn}")
        console.print(f"[dim]Schema:[/dim] {conn.schema_name}")

    from lumen.theme import load_theme

    proj = project_dir(conn_name)
    theme = load_theme(conn_name)
    theme_file = proj / "theme.json"
    if theme_file.exists():
        console.print(f"[dim]Theme:[/dim] {theme_file}")
    else:
        console.print("[dim]Theme:[/dim] default")
    console.print(f"[dim]Locale:[/dim] {theme.locale}")
    console.print(f"[dim]Project dir:[/dim] {proj}")


def main() -> None:
    app()
