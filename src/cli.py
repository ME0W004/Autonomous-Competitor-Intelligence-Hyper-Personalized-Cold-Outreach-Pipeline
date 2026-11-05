import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# Ensure UTF-8 standard streams on Windows
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from config.settings import settings
from src.pipeline.batch_processor import BatchPipelineRunner
from src.crawler.engine import ResilientCrawlerEngine
from src.agents.crew_pipeline import IntelligenceOutreachCrew, load_our_portfolio

app = typer.Typer(
    help="Autonomous B2B Competitor Intelligence & Hyper-Personalized Cold Outreach Pipeline",
    add_completion=False
)
console = Console(legacy_windows=False)

@app.command()
def run(
    input_csv: str = typer.Option(
        str(settings.INPUT_DIR / "sample_domains.csv"),
        "--input", "-i",
        help="Path to input CSV containing domain targets"
    ),
    output_name: str = typer.Option(
        "b2b_outreach_campaign",
        "--output-name", "-o",
        help="Base name for exported campaign files"
    ),
    concurrency: int = typer.Option(
        settings.CRAWLER_CONCURRENCY,
        "--concurrency", "-c",
        help="Number of concurrent domains to process"
    ),
    delay: float = typer.Option(
        settings.RATE_LIMIT_DELAY_SECONDS,
        "--delay", "-d",
        help="Rate-limiting delay between domain requests (seconds)"
    ),
    language: str = typer.Option(
        settings.DEFAULT_OUTREACH_LANGUAGE,
        "--lang", "-l",
        help="Language for email drafts ('en' or 'fa')"
    )
):
    """
    Execute batch processing across a CSV list of company domains.
    """
    console.print(Panel.fit(
        "[bold cyan]>> Autonomous Competitor Intelligence & Outreach Pipeline <<[/bold cyan]\n"
        "[dim]Batch Processor for High-Conversion B2B Prospecting[/dim]",
        border_style="cyan"
    ))

    csv_path = Path(input_csv)
    if not csv_path.exists():
        console.print(f"[bold red]Error:[/bold red] Input CSV not found: {csv_path}")
        raise typer.Exit(code=1)

    runner = BatchPipelineRunner(
        concurrency=concurrency,
        rate_limit_delay=delay,
        language=language
    )

    domains = runner.load_domains_from_csv(csv_path)
    total_domains = len(domains)
    console.print(f"[bold green]Loaded {total_domains} unique target domains from:[/bold green] {csv_path}\n")

    if total_domains == 0:
        console.print("[yellow]No domains found in CSV.[/yellow]")
        raise typer.Exit(code=0)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task_id = progress.add_task("[cyan]Processing domains...", total=total_domains)

        def on_progress(completed: int, total: int, record: dict):
            progress.update(task_id, advance=1)
            status_color = "green" if record["Status"] == "SUCCESS" else "red"
            progress.console.print(
                f"[{status_color}]* [/{status_color}] {record['Domain']:<28} "
                f"Status: [{status_color}]{record['Status']}[/{status_color}] | "
                f"Company: [bold]{record['Company_Name'] or 'N/A'}[/bold]"
            )

        summary = asyncio.run(runner.run_batch(
            domains=domains,
            output_name=output_name,
            progress_callback=on_progress
        ))

    # Print Summary Table
    table = Table(title="Batch Processing Execution Summary", border_style="green")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold white")

    table.add_row("Total Processed", str(summary["total"]))
    table.add_row("Successfully Generated", f"[green]{summary['success']}[/green]")
    table.add_row("Failed / Offline", f"[red]{summary['failed']}[/red]")
    
    for fmt, p in summary["exported_files"].items():
        table.add_row(f"Exported {fmt.upper()}", str(p))

    console.print("\n", table)
    console.print("\n[bold green][+] Pipeline batch execution completed successfully![/bold green]")

@app.command()
def test_domain(
    domain: str = typer.Argument(..., help="Domain to analyze (e.g. stripe.com or linear.app)"),
    language: str = typer.Option("en", "--lang", "-l", help="Language for email draft ('en' or 'fa')")
):
    """
    Test the crawler & multi-agent pipeline on a single domain with live terminal preview.
    """
    console.print(f"\n[cyan][*] Running single-target intelligence audit for:[/cyan] [bold]{domain}[/bold]...\n")

    runner = BatchPipelineRunner(concurrency=1, rate_limit_delay=0.0, language=language)
    
    with console.status("[bold green]Crawling website and running Multi-Agent Crew..."):
        record = asyncio.run(runner.process_single_domain(domain))

    if record["Status"] == "FAILED":
        console.print(Panel(
            f"[bold red]Execution Failed for {domain}:[/bold red]\n{record['Error_Message']}",
            title="Domain Failure",
            border_style="red"
        ))
        raise typer.Exit(code=1)

    # Display Extracted Intelligence
    intel_table = Table(title=f"Extracted Intelligence: {record['Company_Name']}", border_style="blue")
    intel_table.add_column("Property", style="cyan")
    intel_table.add_column("Extracted Details", style="white")

    intel_table.add_row("Company Name", record["Company_Name"])
    intel_table.add_row("Domain", record["Domain"])
    intel_table.add_row("Business Model", record["Business_Model"])
    intel_table.add_row("Target Audience", record["Target_Audience"])
    intel_table.add_row("Identified Pain Point", f"[yellow]{record['Identified_Pain_Point']}[/yellow]")
    intel_table.add_row("Evidence Snippet", f"[dim]{record['Evidence_Snippet']}[/dim]")
    intel_table.add_row("Matched Offering", f"[green]{record['Matched_Service']}[/green]")
    intel_table.add_row("Confidence Score", f"{record['Confidence_Score'] * 100:.0f}%")
    console.print(intel_table)

    # Display Email Copy
    email_panel = Panel(
        f"[bold cyan]Subject Option 1:[/bold cyan] {record['Personalized_Subject_1']}\n"
        f"[bold cyan]Subject Option 2:[/bold cyan] {record['Personalized_Subject_2']}\n\n"
        f"[bold green]-- Email Body Draft --[/bold green]\n\n"
        f"[italic]{record['Email_Body_Draft']}[/italic]",
        title=f"Personalized Outreach Draft ({record['Company_Name']})",
        border_style="green"
    )
    console.print(email_panel)

@app.command()
def portfolio():
    """
    Display our agency value proposition, service offerings, and proof metrics.
    """
    data = load_our_portfolio()
    console.print(Panel(
        f"[bold cyan]{data.get('agency_name', 'Agency')}[/bold cyan]\n"
        f"[white]{data.get('core_value_proposition', '')}[/white]",
        title="Our Value Proposition",
        border_style="cyan"
    ))

    table = Table(title="Active Offerings & Matching Matrix", border_style="magenta")
    table.add_column("Service ID", style="cyan")
    table.add_column("Title", style="bold white")
    table.add_column("Case Study Metric", style="green")

    for off in data.get("offerings", []):
        table.add_row(
            off.get("service_id", ""),
            off.get("title", ""),
            off.get("proof_and_case_study", "")
        )

    console.print(table)

@app.command()
def diagnostics():
    """
    Check system health, dependencies, and configuration.
    """
    console.print("[bold cyan]System Diagnostics & Health Check:[/bold cyan]\n")
    
    # Check API keys
    keys = {
        "OPENAI_API_KEY": settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"),
        "GEMINI_API_KEY": settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY"),
        "GROQ_API_KEY": settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY"),
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY or os.getenv("ANTHROPIC_API_KEY"),
    }

    key_table = Table(title="Configured LLM Providers", border_style="yellow")
    key_table.add_column("Key Name", style="cyan")
    key_table.add_column("Status", style="white")

    for k, v in keys.items():
        status = "[green]Configured[/green]" if v else "[dim]Not Set (Heuristic Fallback Active)[/dim]"
        key_table.add_row(k, status)
    console.print(key_table)

    # Check Directories
    dirs = [settings.INPUT_DIR, settings.OUTPUT_DIR, settings.LOGS_DIR, settings.CONFIG_DIR]
    dir_table = Table(title="Storage & Workspace Directories", border_style="blue")
    dir_table.add_column("Directory", style="cyan")
    dir_table.add_column("Exists", style="white")

    for d in dirs:
        dir_table.add_row(str(d), "[green]YES[/green]" if d.exists() else "[red]NO[/red]")
    console.print("\n", dir_table)

if __name__ == "__main__":
    app()
