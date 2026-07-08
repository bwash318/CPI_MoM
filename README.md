# CPI MoM Prediction Market Research

Phase 1 tests whether Core CPI Month-over-Month prediction markets show repeatable short-term pricing inefficiencies after scheduled macro releases.

The live pipeline has three concurrent collectors. Each runs every 60 seconds, aligned just after the top of the minute.

```mermaid
flowchart LR
    A["Task 1<br/>Kalshi quote snapshots<br/>tasks.task1_kalshi_quote_snapshots"]
    B["Task 2<br/>Predictor snapshots<br/>tasks.task2_predictor_snapshots"]
    C["Task 3<br/>Polymarket quote snapshots<br/>tasks.task3_polymarket_cpi_quote_snapshots"]

    A --- B
    B --- C
```

## Task 1: Kalshi Quote Snapshots

Collects top-of-book snapshots for the next two Kalshi Core CPI MoM event markets by close time.

```powershell
python -m tasks.task1_kalshi_quote_snapshots --once
```

Output:

```text
data/kalshi_core_cpi_quote_snapshots/scrape_date=YYYY-MM-DD.parquet
```

## Task 2: Predictor Snapshots

Collects Cleveland Fed and FRED predictor/context rows. It appends only changed rows.

For Cleveland Fed monthly MoM nowcasts, change detection is grouped by period: if any of `cpi`, `core_cpi`, `pce`, `core_pce`, or `source_updated` changes, all four rows for that period are appended.

```powershell
python -m tasks.task2_predictor_snapshots --once
```

Outputs:

```text
data/predictor_snapshots.csv
data/predictor_latest_hashes.json
data/predictor_measure_definitions.csv
```

## Task 3: Polymarket Quote Snapshots

Collects Polymarket Core CPI MoM snapshots using configured known slugs plus discovery, then keeps the next two open CPI MoM events by end time.

```powershell
python -m tasks.task3_polymarket_cpi_quote_snapshots --once
```

Output:

```text
data/polymarket_cpi_quote_snapshots/scrape_date=YYYY-MM-DD.parquet
```

Known Polymarket event slugs can be configured with `POLYMARKET_EVENT_SLUGS`. The default includes:

```text
core-cpi-mom-july-2026-20260705181328287
```

## Running Collectors

Start all collectors in parallel:

```powershell
.\scripts\start_all_collectors_background.ps1
```

Stop all collectors:

```powershell
.\scripts\stop_all_collectors_background.ps1
```

Individual starts:

```powershell
.\scripts\start_kalshi_quote_collector_background.ps1
.\scripts\start_predictor_collector_background.ps1
.\scripts\start_polymarket_quote_collector_background.ps1
```

Individual stops:

```powershell
.\scripts\stop_kalshi_quote_collector_background.ps1
.\scripts\stop_predictor_collector_background.ps1
.\scripts\stop_polymarket_quote_collector_background.ps1
```

## Environment

Copy `.env.example` to `.env` and set values as needed.

```text
DATABASE_URL=postgresql://user:password@localhost:5432/cpi_mom
KALSHI_API_BASE=https://api.elections.kalshi.com/trade-api/v2
POLYMARKET_EVENT_SLUGS=core-cpi-mom-july-2026-20260705181328287
```
