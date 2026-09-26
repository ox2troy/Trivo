from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class TxType(str, Enum):
    FUNDING = "funding"
    MINT = "mint"
    TRANSFER = "transfer"
    UNKNOWN = "unknown"


class FundingEdge(BaseModel):
    from_wallet: str
    to_wallet: str
    amount_sol: float
    signature: str
    timestamp: Optional[datetime] = None
    slot: Optional[int] = None


class MintEvent(BaseModel):
    mint_address: str
    signature: str
    timestamp: Optional[datetime] = None
    token_name: Optional[str] = None
    token_symbol: Optional[str] = None
    amount: Optional[float] = None


class WalletProfile(BaseModel):
    address: str
    mint_count: int = 0
    mints: List[MintEvent] = Field(default_factory=list)
    direct_funders: List[FundingEdge] = Field(default_factory=list)
    funded_wallets: List[FundingEdge] = Field(default_factory=list)
    is_main_funder: bool = False
    depth: int = 0
    labels: List[str] = Field(default_factory=list)  # e.g. ["cex", "known_bot", "high_mint"]


class AnalysisGraph(BaseModel):
    target_wallets: List[str]
    main_funders: List[str] = Field(default_factory=list)
    wallets: Dict[str, WalletProfile] = Field(default_factory=dict)
    funding_edges: List[FundingEdge] = Field(default_factory=list)
    mint_events: List[MintEvent] = Field(default_factory=list)
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    notes: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    graph: AnalysisGraph
    summary: Dict[str, Any] = Field(default_factory=dict)
    report_path: Optional[str] = None
    html_graph_path: Optional[str] = None
