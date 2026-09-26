#!/usr/bin/env python3
"""
Private On-Chain Wallet Analyzer Bot
Tracks funding sources and token minting activity recursively.
"""

from __future__ import annotations
import sys
from typing import List, Optional
import typer
from rich.console import Console

from .analyzer import WalletAnalyzer
from .reporter import print_console_report, save_json_report, generate_html_graph
from .config import settings

app = typer.Typer(
    name="onchain-analyzer",
    help="Private Solana wallet funding + minting analysis bot",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    wallets: List[str] = typer.Argument(..., help="One or more wallet addresses to analyze"),
    depth: Optional[int] = typer.Option(None, "--depth", "-d", help="Max recursion depth"),
    min_sol: Optional[float] = typer.Option(None, "--min-sol", help="Minimum SOL amount to consider funding"),
    lookback: Optional[int] = typer.Option(None, "--lookback", help="Days to look back for transactions"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Disable cache"),
    html: bool = typer.Option(True, "--html/--no-html", help="Generate interactive HTML graph"),
):
    """
    Analyze wallet(s): find funders → main funder → downstream minting activity.
    """
    if depth is not None:
        settings.max_recursion_depth = depth
    if min_sol is not None:
        settings.min_funding_sol = min_sol
    if lookback is not None:
        settings.lookback_days = lookback
    if no_cache:
        settings.cache_enabled = False

    # Basic validation
    clean = []
    for w in wallets:
        w = w.strip()
        if len(w) < 32 or len(w) > 44:
            console.print(f"[red]Skipping invalid address:[/] {w}")
            continue
        clean.append(w)

    if not clean:
        console.print("[red]No valid wallets provided.[/]")
        raise typer.Exit(1)

    analyzer = WalletAnalyzer()
    try:
        result = analyzer.run(clean)
        print_console_report(result)
        json_path = save_json_report(result)
        result.report_path = str(json_path)

        if html:
            html_path = generate_html_graph(result)
            result.html_graph_path = str(html_path) if html_path else None

        console.print("\n[bold green]✓ Analysis complete[/]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/]")
    except Exception as e:
        console.print(f"[red]Error:[/] {e}")
        raise
    finally:
        analyzer.close()


@app.command()
def version():
    """Show version"""
    console.print("onchain-wallet-analyzer v1.0.0 (private)")


if __name__ == "__main__":
    app()
