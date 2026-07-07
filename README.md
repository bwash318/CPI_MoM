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

Run continuously every 60 seconds:

```powershell
python -m tasks.task2_kalshi_quote_snapshots --interval-seconds 60
```

Output:

```text
data/kalshi_core_cpi_quote_snapshots.csv
```

Register and start the local Windows scheduled collector:

```powershell
.\scripts\register_kalshi_quote_collector_task.ps1
```

The scheduled task starts the collector at logon. The collector itself runs continuously and appends a fresh snapshot every 60 seconds.

If Task Scheduler is unavailable, start the collector as a background process for the current Windows session:

```powershell
.\scripts\start_kalshi_quote_collector_background.ps1
```

Stop the background collector:

```powershell
.\scripts\stop_kalshi_quote_collector_background.ps1
```

Start Kalshi, predictor, and Polymarket collectors in parallel:

```powershell
.\scripts\start_all_collectors_background.ps1
```

Stop all collectors:

```powershell
.\scripts\stop_all_collectors_background.ps1
```

### Task 3: Cross-Exchange Mesh

### Task 3: Predictor Collection

Collect official/public predictor snapshots and append only rows whose value changed since the last scrape.

Current source:

```text
Cleveland Fed Inflation Nowcasting
FRED daily market context series
```

For Cleveland Fed nowcasts, we collect only:

```text
Inflation, month-over-month percent change
```

The year-over-year and quarterly annualized Cleveland Fed tables are intentionally ignored for Phase 1 because the traded Kalshi market is Core CPI month-over-month.

Current FRED series:

```text
DGS2: 2-year Treasury yield
DGS10: 10-year Treasury yield
T5YIE: 5-year breakeven inflation
T10YIE: 10-year breakeven inflation
T5YIFR: 5-year, 5-year forward inflation expectation rate
DCOILWTICO: WTI crude oil
DTWEXBGS: broad US dollar index
SP500: S&P 500 index
ICSA: initial jobless claims
PAYEMS: nonfarm payrolls
UNRATE: unemployment rate
CES0500000003: average hourly earnings, total private
PPIACO: producer price index, all commodities
WPSFD4131: producer price index, final demand less foods and energy
RSAFS: advance retail and food services sales
```

Run one scrape:

```powershell
python -m tasks.task3_predictor_snapshots --once
```

Run continuously every 60 seconds, aligned to the top of each minute:

```powershell
python -m tasks.task3_predictor_snapshots --interval-seconds 60
```

Output:

```text
data/predictor_snapshots.csv
```

Change-detection state:

```text
data/predictor_latest_hashes.json
```

Predictor output fields:

```text
scrape_time_utc
source
predictor_family
frequency
period
measure
value
source_updated
source_url
```

For Cleveland Fed monthly MoM nowcasts, change detection is performed at the full report-row level. If any of `cpi`, `core_cpi`, `pce`, `core_pce`, or `source_updated` changes for a period, all four measures for that period are appended with the earliest scrape time at which the new report row was observed.

Start in the background:

```powershell
.\scripts\start_predictor_collector_background.ps1
```

Stop the background collector:

```powershell
.\scripts\stop_predictor_collector_background.ps1
```

### Task 4: Cross-Exchange Mesh

### Task 4: Polymarket CPI Quote Collection

Discover active Polymarket CPI/Core CPI month-over-month markets and append quote snapshots when matching markets exist.

Run one snapshot:

```powershell
python -m tasks.task4_polymarket_cpi_quote_snapshots --once
```

Output:

```text
data/polymarket_cpi_quote_snapshots.csv
```

Current note: the strict CPI MoM filter found no active Polymarket matches on the first test run, so the output file may contain only headers until a matching market appears.

### Task 5: Cross-Exchange Mesh

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
