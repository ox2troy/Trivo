from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    solana_rpc_url: str = Field(default="https://api.mainnet-beta.solana.com", alias="SOLANA_RPC_URL")
    helius_api_key: str | None = Field(default=None, alias="HELIUS_API_KEY")
    
    max_recursion_depth: int = Field(default=6, alias="MAX_RECURSION_DEPTH")
    min_funding_sol: float = Field(default=0.01, alias="MIN_FUNDING_SOL")
    lookback_days: int = Field(default=90, alias="LOOKBACK_DAYS")
    cache_enabled: bool = Field(default=True, alias="CACHE_ENABLED")
    
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    cache_dir: Path = base_dir / "cache"
    reports_dir: Path = base_dir / "reports"
    data_dir: Path = base_dir / "data"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

# Ensure dirs exist
settings.cache_dir.mkdir(parents=True, exist_ok=True)
settings.reports_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)
