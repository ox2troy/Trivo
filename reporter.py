from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box

from .models import AnalysisResult, AnalysisGraph
from .config import settings

console = Console()


def print_console_report(result: AnalysisResult):
    g = result.graph
    s = result.summary

    console.print("\n")
    console.rule("[bold green]ANALYSIS SUMMARY[/]")
    console.print(f"Targets analyzed      : {len(s['targets'])}")
    console.print(f"Main funders found    : {len(s['main_funders'])}")
    console.print(f"Total wallets scanned : {s['total_wallets_analyzed']}")
    console.print(f"Funding edges         : {s['total_funding_edges']}")
    console.print(f"Total mint events     : {s['total_mint_events']}")

    # Main funders table
    if s["main_funders"]:
        table = Table(title="Main Funders", box=box.ROUNDED)
        table.add_column("Address", style="cyan")
        table.add_column("Mints", justify="right")
        table.add_column("Funded Wallets", justify="right")
        for mf in s["main_funders"]:
            p = g.wallets.get(mf)
            mints = p.mint_count if p else 0
            funded = len(p.funded_wallets) if p else 0
            table.add_row(mf, str(mints), str(funded))
        console.print(table)

    # Top minters
    if s["wallets_that_minted"]:
        table2 = Table(title="Wallets that Minted Tokens", box=box.ROUNDED)
        table2.add_column("Address", style="magenta")
        table2.add_column("Mint Count", justify="right", style="green")
        for item in s["wallets_that_minted"][:15]:
            table2.add_row(item["address"], str(item["mints"]))
        console.print(table2)

    # Simple funding tree for first target
    if g.target_wallets:
        tree = Tree(f"[bold]Funding chain for {g.target_wallets[0][:12]}...[/]")
        _build_tree(tree, g.target_wallets[0], g, set())
        console.print(tree)


def _build_tree(node, address: str, graph: AnalysisGraph, visited: set, max_depth: int = 4):
    if address in visited or max_depth <= 0:
        return
    visited.add(address)
    profile = graph.wallets.get(address)
    if not profile:
        return
    label = f"{address[:8]}...{address[-4:]}"
    if profile.mint_count:
        label += f" [green](minted {profile.mint_count})[/]"
    if profile.is_main_funder:
        label += " [bold yellow]★ MAIN FUNDER[/]"
    child = node.add(label)
    for edge in profile.direct_funders[:5]:  # limit branching
        _build_tree(child, edge.from_wallet, graph, visited, max_depth - 1)


def save_json_report(result: AnalysisResult) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = settings.reports_dir / f"analysis_{ts}.json"
    data = {
        "summary": result.summary,
        "graph": result.graph.model_dump(mode="json"),
    }
    path.write_text(json.dumps(data, indent=2, default=str))
    console.print(f"\n[green]JSON report saved →[/] {path}")
    return path


def generate_html_graph(result: AnalysisResult) -> Optional[Path]:
    try:
        import networkx as nx
        from pyvis.network import Network
    except ImportError:
        console.print("[yellow]pyvis/networkx not available – skipping HTML graph[/]")
        return None

    g = result.graph
    net = Network(height="900px", width="100%", bgcolor="#0d1117", font_color="white", directed=True)
    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=150)

    # Nodes
    for addr, profile in g.wallets.items():
        color = "#58a6ff"
        size = 15
        title = f"{addr}\nMints: {profile.mint_count}"
        if profile.is_main_funder:
            color = "#f0883e"
            size = 35
            title += "\n★ MAIN FUNDER"
        elif addr in g.target_wallets:
            color = "#3fb950"
            size = 28
            title += "\nTARGET"
        elif profile.mint_count > 0:
            color = "#f85149"
            size = 20 + min(profile.mint_count * 3, 25)
            title += f"\nMinted {profile.mint_count} tokens"

        net.add_node(addr, label=addr[:6] + "…" + addr[-4:], title=title, color=color, size=size)

    # Edges
    for edge in g.funding_edges:
        net.add_edge(
            edge.from_wallet,
            edge.to_wallet,
            title=f"{edge.amount_sol:.4f} SOL\n{edge.signature[:16]}…",
            value=min(edge.amount_sol * 2, 10),
            color="#8b949e",
        )

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = settings.reports_dir / f"graph_{ts}.html"
    net.write_html(str(path))
    console.print(f"[green]Interactive HTML graph →[/] {path}")
    return path
