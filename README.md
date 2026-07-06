# CPI MoM Prediction Market Research

Phase 1 tests whether Core CPI Month-over-Month prediction markets show repeatable short-term pricing inefficiencies after scheduled macro releases.

The project starts intentionally narrow:

1. Build one clean Kalshi ingestion pipeline.
2. Add Polymarket as a second native pipeline.
3. Build a mesh layer that maps comparable contracts across venues for event studies.

The goal is research discipline, not an immediate trading bot.

## Initial Tasks

### Task 1: Kalshi Market Discovery

Find active Kalshi markets/contracts related to Core CPI MoM and persist their native identifiers, titles, settlement text, and contract metadata.

Run:

```powershell
python -m tasks.task1_kalshi_market_discovery
```

Use `--dry-run` to print matches without writing to PostgreSQL:

```powershell
python -m tasks.task1_kalshi_market_discovery --dry-run
```

### Task 2: Kalshi Quote Collection

Collect Kalshi top-of-book quotes/trades for discovered contracts at the highest feasible resolution.

The initial collector appends top-of-book snapshots for the next two Core CPI event markets by close time. With the current calendar, that means June and July; after the June market closes, it automatically rolls to July and August.

Run one snapshot:

```powershell
python -m tasks.task2_kalshi_quote_snapshots --once
```

Run continuously every 30 seconds:

```powershell
python -m tasks.task2_kalshi_quote_snapshots --interval-seconds 30
```

Output:

```text
data/kalshi_core_cpi_quote_snapshots.csv
```

Register and start the local Windows scheduled collector:

```powershell
.\scripts\register_kalshi_quote_collector_task.ps1
```

The scheduled task starts the collector at logon. The collector itself runs continuously and appends a fresh snapshot every 30 seconds.

If Task Scheduler is unavailable, start the collector as a background process for the current Windows session:

```powershell
.\scripts\start_kalshi_quote_collector_background.ps1
```

Stop the background collector:

```powershell
.\scripts\stop_kalshi_quote_collector_background.ps1
```

### Task 3: Cross-Exchange Mesh

After Polymarket exists as its own native pipeline, create a mesh dataframe/table that maps economically equivalent or overlapping contracts across exchanges.

Do not force the two venues into one schema too early. Store raw venue-native data first, then normalize for analysis.

## Database

Schema lives in:

```text
sql/schema.sql
```

The schema is designed to preserve raw venue data and timestamp provenance. Feature engineering belongs in analysis scripts, not ingestion.

## Kalshi Core CPI Market Rules

The discovery CSV omits Kalshi's repeated rules text to keep the dataset readable by eye.

Primary rule template:

```text
If the seasonally adjusted Consumer Price Index for All Urban Consumers: All Items less Food and Energy for {month} {year}, as published by the Bureau of Labor Statistics, increases by above {threshold}%, then the market resolves to Yes.
```

Secondary rule:

```text
Please note that the value of the Underlying is the single-decimal value reported by the BLS.

In the case of a delay in data caused by a federal government shutdown impacting the reliability of the Source Agency, the market's latest Expiration Date will be extended to the sooner of the release of the Underlying or six months after the end of the government shutdown.
```

`settlement_timer_seconds` is Kalshi's post-release settlement window. For the current Core CPI contracts it is `3600`, meaning Kalshi allows up to one hour after the underlying release before settlement.

## Discovery CSV Fields

`scrape_time_utc`: when this local discovery task collected the row.

`exchange`: source venue, currently `kalshi`.

`event_ticker`: Kalshi event/month identifier, such as `KXCPICORE-26JUN`.

`market_ticker`: Kalshi contract/threshold identifier, such as `KXCPICORE-26JUN-T0.2`.

`title`: human-readable contract question.

`subtitle`: displayed threshold label.

`status`: Kalshi market status.

`strike_type`: threshold direction, currently `greater`.

`floor_strike`: numeric threshold used by the contract.

`cap_strike`: upper strike field from Kalshi; for these threshold contracts it matches `floor_strike`.

`yes_bid_dollars`, `yes_ask_dollars`: current best bid and ask for Yes, in dollars.

`yes_bid_size_fp`, `yes_ask_size_fp`: size available at the Yes bid and ask.

`no_bid_dollars`, `no_ask_dollars`: current best bid and ask for No, in dollars.

`last_price_dollars`: most recent trade price.

`previous_price_dollars`: prior reference price from Kalshi.

`volume_fp`: cumulative contract volume.

`volume_24h_fp`: contract volume over the prior 24 hours.

`open_interest_fp`: open interest.

`open_time_utc`: when Kalshi opened trading for the contract.

`close_time_utc`: when Kalshi closes trading before release.

`expiration_time_utc`: latest contract expiration timestamp.

## Environment

Copy `.env.example` to `.env` and set values as needed.

```text
DATABASE_URL=postgresql://user:password@localhost:5432/cpi_mom
KALSHI_API_BASE=https://api.elections.kalshi.com/trade-api/v2
```
