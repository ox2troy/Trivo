from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from .config import settings
from .models import (
    WalletProfile,
    FundingEdge,
    MintEvent,
    AnalysisGraph,
    AnalysisResult,
)
from .solana_client import SolanaClient

console = Console()


class WalletAnalyzer:
    def __init__(self):
        self.client = SolanaClient()
        self.visited: Set[str] = set()
        self.graph = AnalysisGraph(target_wallets=[])

    def _cache_path(self, address: str) -> Path:
        return settings.cache_dir / f"{address}.json"

    def _load_cache(self, address: str) -> Optional[Dict]:
        if not settings.cache_enabled:
            return None
        path = self._cache_path(address)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                return None
        return None

    def _save_cache(self, address: str, data: Dict):
        if not settings.cache_enabled:
            return
        path = self._cache_path(address)
        path.write_text(json.dumps(data, default=str, indent=2))

    def analyze_wallet(self, address: str, depth: int = 0) -> WalletProfile:
        """Analyze a single wallet: mints + direct funders."""
        if address in self.graph.wallets:
            return self.graph.wallets[address]

        cached = self._load_cache(address)
        if cached:
            profile = WalletProfile(**cached)
            self.graph.wallets[address] = profile
            return profile

        console.print(f"[cyan]→ Analyzing[/] {address[:8]}...{address[-6:]} (depth {depth})")

        sigs = self.client.fetch_recent_signatures(
            address,
            lookback_days=settings.lookback_days,
            max_sigs=1500,
        )
        funders_raw, mints_raw = self.client.parse_funding_and_mints(
            address,
            sigs,
            min_sol=settings.min_funding_sol,
        )

        funders = [FundingEdge(**f) for f in funders_raw]
        mints = [MintEvent(**m) for m in mints_raw]

        profile = WalletProfile(
            address=address,
            mint_count=len(mints),
            mints=mints,
            direct_funders=funders,
            depth=depth,
        )

        # Also record outgoing funding later when we process downstream
        self.graph.wallets[address] = profile
        self.graph.funding_edges.extend(funders)
        self.graph.mint_events.extend(mints)

        self._save_cache(address, profile.model_dump())
        return profile

    def trace_upstream(self, start_wallets: List[str]) -> List[str]:
        """
        Recursively walk funders until we reach wallets with no further significant funders
        or hit max depth. Returns list of main funders.
        """
        self.graph.target_wallets = start_wallets
        queue: List[tuple[str, int]] = [(w, 0) for w in start_wallets]
        main_funders: Set[str] = set()
        processed: Set[str] = set()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Tracing funders upstream...", total=None)

            while queue:
                address, depth = queue.pop(0)
                if address in processed or depth > settings.max_recursion_depth:
                    if depth > settings.max_recursion_depth:
                        main_funders.add(address)
                    continue
                processed.add(address)

                profile = self.analyze_wallet(address, depth=depth)

                if not profile.direct_funders or depth == settings.max_recursion_depth:
                    main_funders.add(address)
                    profile.is_main_funder = True
                else:
                    for edge in profile.direct_funders:
                        funder = edge.from_wallet
                        if funder not in processed:
                            queue.append((funder, depth + 1))

                progress.update(task, description=f"Traced {len(processed)} wallets | depth {depth}")

        self.graph.main_funders = list(main_funders)
        return list(main_funders)

    def analyze_downstream(self, main_funders: List[str]):
        """
        From each main funder, discover wallets they funded and check
        whether those wallets mint or fund further minters.
        """
        console.print("\n[bold magenta]Analyzing downstream activity from main funders...[/]")

        for mf in main_funders:
            # We already have the profile; now we need outgoing funding.
            # For simplicity we re-scan the main funder looking for outgoing SOL transfers.
            profile = self.graph.wallets.get(mf) or self.analyze_wallet(mf)

            sigs = self.client.fetch_recent_signatures(mf, lookback_days=settings.lookback_days)
            # Re-use parser but invert: look for negative balance changes on main funder
            # and positive on others.
            outgoing: List[FundingEdge] = []
            seen = set()

            for sig_info in sigs[:800]:  # limit for speed
                sig = sig_info["signature"]
                try:
                    tx = self.client.get_transaction(sig)
                except Exception:
                    continue
                if not tx or not tx.get("meta") or tx["meta"].get("err"):
                    continue

                meta = tx["meta"]
                pre = meta.get("preBalances", [])
                post = meta.get("postBalances", [])
                keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]

                if mf not in keys:
                    continue
                idx = keys.index(mf)
                if idx >= len(pre) or idx >= len(post):
                    continue

                delta = (post[idx] - pre[idx]) / 1e9
                if delta > -settings.min_funding_sol:
                    continue  # not a significant outgoing

                # Find receivers
                for i, (p, po) in enumerate(zip(pre, post)):
                    if i == idx:
                        continue
                    recv_delta = (po - p) / 1e9
                    if recv_delta >= settings.min_funding_sol:
                        receiver = keys[i]
                        key = (mf, receiver, sig)
                        if key not in seen:
                            seen.add(key)
                            edge = FundingEdge(
                                from_wallet=mf,
                                to_wallet=receiver,
                                amount_sol=recv_delta,
                                signature=sig,
                                timestamp=datetime.fromtimestamp(sig_info["blockTime"]) if sig_info.get("blockTime") else None,
                                slot=sig_info.get("slot"),
                            )
                            outgoing.append(edge)
                            self.graph.funding_edges.append(edge)

            profile.funded_wallets = outgoing
            self.graph.wallets[mf] = profile

            # Now analyze each funded wallet for minting
            for edge in outgoing:
                recv = edge.to_wallet
                if recv not in self.graph.wallets:
                    self.analyze_wallet(recv, depth=1)

    def build_summary(self) -> Dict:
        total_mints = sum(p.mint_count for p in self.graph.wallets.values())
        high_mint_wallets = [
            {"address": a, "mints": p.mint_count}
            for a, p in self.graph.wallets.items()
            if p.mint_count > 0
        ]
        high_mint_wallets.sort(key=lambda x: x["mints"], reverse=True)

        return {
            "targets": self.graph.target_wallets,
            "main_funders": self.graph.main_funders,
            "total_wallets_analyzed": len(self.graph.wallets),
            "total_funding_edges": len(self.graph.funding_edges),
            "total_mint_events": total_mints,
            "wallets_that_minted": high_mint_wallets[:20],
            "analysis_time": datetime.utcnow().isoformat(),
        }

    def run(self, target_wallets: List[str]) -> AnalysisResult:
        console.print(Panel.fit(
            f"[bold green]On-Chain Wallet Analyzer[/]\n"
            f"Targets: {', '.join(w[:8]+'...'+w[-4:] for w in target_wallets)}\n"
            f"Max depth: {settings.max_recursion_depth} | Min SOL: {settings.min_funding_sol}",
            title="Starting Analysis",
        ))

        main_funders = self.trace_upstream(target_wallets)
        self.analyze_downstream(main_funders)
        summary = self.build_summary()

        result = AnalysisResult(graph=self.graph, summary=summary)
        return result

    def close(self):
        self.client.close()
