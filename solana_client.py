from __future__ import annotations
import httpx
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from tenacity import retry, stop_after_attempt, wait_exponential
from rich.console import Console
from .config import settings

console = Console()


class SolanaClient:
    def __init__(self, rpc_url: Optional[str] = None, helius_key: Optional[str] = None):
        self.rpc_url = rpc_url or settings.solana_rpc_url
        self.helius_key = helius_key or settings.helius_api_key
        self.session = httpx.Client(timeout=30.0)
        self._cache: Dict[str, Any] = {}

    def _rpc(self, method: str, params: list) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        resp = self.session.post(self.rpc_url, json=payload, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data.get("result")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get_signatures_for_address(
        self,
        address: str,
        limit: int = 1000,
        before: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: List[Any] = [address, {"limit": limit}]
        if before:
            params[1]["before"] = before
        if until:
            params[1]["until"] = until
        return self._rpc("getSignaturesForAddress", params) or []

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
    def get_transaction(self, signature: str) -> Optional[Dict[str, Any]]:
        return self._rpc(
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}],
        )

    def get_balance(self, address: str) -> float:
        result = self._rpc("getBalance", [address])
        return (result.get("value", 0) or 0) / 1e9

    def get_token_accounts(self, owner: str) -> List[Dict[str, Any]]:
        result = self._rpc(
            "getTokenAccountsByOwner",
            [owner, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}, {"encoding": "jsonParsed"}],
        )
        return result.get("value", []) if result else []

    # ---------- Higher-level helpers ----------

    def fetch_recent_signatures(
        self,
        address: str,
        lookback_days: int = 90,
        max_sigs: int = 2000,
    ) -> List[Dict[str, Any]]:
        """Fetch signatures within lookback window (newest first)."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        all_sigs: List[Dict[str, Any]] = []
        before = None

        while len(all_sigs) < max_sigs:
            batch = self.get_signatures_for_address(address, limit=1000, before=before)
            if not batch:
                break
            for sig in batch:
                block_time = sig.get("blockTime")
                if block_time and datetime.fromtimestamp(block_time, tz=timezone.utc) < cutoff:
                    return all_sigs
                all_sigs.append(sig)
            before = batch[-1]["signature"]
            if len(batch) < 1000:
                break
        return all_sigs[:max_sigs]

    def parse_funding_and_mints(
        self,
        address: str,
        signatures: List[Dict[str, Any]],
        min_sol: float = 0.01,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Returns:
          funders: list of {from, amount_sol, signature, timestamp, slot}
          mints: list of {mint, signature, timestamp, ...}
        """
        funders: List[Dict[str, Any]] = []
        mints: List[Dict[str, Any]] = []
        seen_funders = set()

        for sig_info in signatures:
            sig = sig_info["signature"]
            try:
                tx = self.get_transaction(sig)
            except Exception:
                continue
            if not tx or not tx.get("meta") or tx["meta"].get("err"):
                continue

            block_time = sig_info.get("blockTime")
            ts = datetime.fromtimestamp(block_time, tz=timezone.utc) if block_time else None
            slot = sig_info.get("slot")

            # ---- Detect SOL funding (native transfers) ----
            meta = tx["meta"]
            pre = meta.get("preBalances", [])
            post = meta.get("postBalances", [])
            account_keys = [k["pubkey"] if isinstance(k, dict) else k for k in tx["transaction"]["message"]["accountKeys"]]

            if address in account_keys:
                idx = account_keys.index(address)
                if idx < len(pre) and idx < len(post):
                    delta = (post[idx] - pre[idx]) / 1e9
                    if delta >= min_sol:
                        # Find who sent the SOL (look for negative deltas)
                        for i, (p, po) in enumerate(zip(pre, post)):
                            if i == idx:
                                continue
                            sender_delta = (po - p) / 1e9
                            if sender_delta < -min_sol * 0.5:  # approximate
                                sender = account_keys[i]
                                key = (sender, sig)
                                if key not in seen_funders:
                                    seen_funders.add(key)
                                    funders.append(
                                        {
                                            "from_wallet": sender,
                                            "to_wallet": address,
                                            "amount_sol": delta,
                                            "signature": sig,
                                            "timestamp": ts,
                                            "slot": slot,
                                        }
                                    )
                                break

            # ---- Detect mint activity (simplified) ----
            # Look for InitializeMint / MintTo instructions or new token accounts created by this wallet
            instructions = tx["transaction"]["message"].get("instructions", [])
            inner = meta.get("innerInstructions", [])

            for ix in instructions + [i for group in inner for i in group.get("instructions", [])]:
                parsed = ix.get("parsed") if isinstance(ix, dict) else None
                if not parsed:
                    continue
                typ = parsed.get("type")
                info = parsed.get("info", {})

                if typ in ("initializeMint", "initializeMint2"):
                    mint_addr = info.get("mint")
                    if mint_addr:
                        mints.append(
                            {
                                "mint_address": mint_addr,
                                "signature": sig,
                                "timestamp": ts,
                                "token_name": None,
                                "token_symbol": None,
                            }
                        )
                elif typ == "mintTo":
                    # Only count if the mint authority is our address
                    mint_auth = info.get("mintAuthority") or info.get("authority")
                    if mint_auth == address:
                        mints.append(
                            {
                                "mint_address": info.get("mint"),
                                "signature": sig,
                                "timestamp": ts,
                                "amount": float(info.get("amount", 0)) / 10 ** int(info.get("decimals", 0) or 0),
                            }
                        )

        return funders, mints

    def close(self):
        self.session.close()
