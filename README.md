# On-Chain Wallet Analyzer (Private Bot)

Private Python bot that performs deep recursive analysis of Solana wallet funding sources and token minting activity.

## What it does

1. Takes one or more target wallet addresses.
2. Detects how many tokens each wallet has minted.
3. Finds every significant SOL funder of the target.
4. Recursively walks upstream until it reaches the **main funder(s)**.
5. From each main funder, discovers all wallets it has funded.
6. Checks whether those wallets are minting tokens or funding further minters.
7. Outputs:
   - Rich console report + funding tree
   - Full JSON report
   - Interactive HTML network graph

No login, no signup, fully local / private.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. (Optional) copy env and set better RPC
cp .env.example .env
# Edit .env → put a Helius / QuickNode URL for better rate limits

# 3. Run analysis
python run.py analyze <WALLET1> [WALLET2 ...]

# Examples
python run.py analyze 7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU
python run.py analyze WALLET1 WALLET2 --depth 5 --min-sol 0.05 --lookback 60
python run.py analyze WALLET --no-cache --no-html
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--depth / -d` | Max upstream recursion depth | 6 |
| `--min-sol` | Minimum SOL transfer to count as funding | 0.01 |
| `--lookback` | Days of history to scan | 90 |
| `--no-cache` | Disable disk cache | false |
| `--no-html` | Skip interactive graph generation | false |

## Output

- Console summary + funding tree
- `reports/analysis_YYYYMMDD_HHMMSS.json`
- `reports/graph_YYYYMMDD_HHMMSS.html` (open in browser)

## Architecture

```
src/
├── main.py          # CLI (Typer)
├── analyzer.py      # Core recursive logic
├── solana_client.py # RPC + tx parsing
├── models.py        # Pydantic models
├── reporter.py      # Console / JSON / HTML
└── config.py        # Settings
```

## Notes

- Public RPC (`api.mainnet-beta.solana.com`) works but is rate-limited. For serious use put a Helius or QuickNode endpoint in `.env`.
- Cache lives in `cache/` – delete folder to force re-fetch.
- Mint detection looks for `initializeMint` / `mintTo` instructions. It is heuristic and can be extended.
- The bot is intentionally private – no telemetry, no accounts, no external services beyond the RPC you configure.

## Extending

- Add Ethereum support by creating an `EVMClient` with the same interface.
- Add Telegram alerts by watching new mint events from the main funder cluster.
- Improve mint detection with Helius enhanced transactions or DAS API.
