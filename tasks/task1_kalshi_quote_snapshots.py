from __future__ import annotations

import argparse
import traceback
from datetime import datetime, timezone
from time import sleep

from cpi_mom.config import load_settings
from cpi_mom.kalshi import KalshiClient, is_core_cpi_candidate, normalize_market
from cpi_mom.kalshi_rows import market_to_row
from cpi_mom.parquet_io import append_partitioned_parquet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append Kalshi Core CPI quote snapshots for the next event markets to close."
    )
    parser.add_argument("--series-ticker", default="KXCPICORE", help="Kalshi Core CPI series ticker.")
    parser.add_argument("--status", default="open", help="Kalshi market status to query.")
    parser.add_argument("--limit", type=int, default=100, help="Markets to request per API page.")
    parser.add_argument("--event-count", type=int, default=2, help="Number of upcoming event tickers.")
    parser.add_argument(
        "--output",
        default="data/kalshi_core_cpi_quote_snapshots",
        help="Directory for daily partitioned Parquet output.",
    )
    parser.add_argument("--once", action="store_true", help="Collect one snapshot and exit.")
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60,
        help="Seconds between snapshots when running continuously.",
    )
    parser.add_argument(
        "--align-to-minute",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Align continuous collection to the top of each minute.",
    )
    return parser.parse_args()


def parse_utc(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def select_next_event_markets(matches, *, now_utc: datetime, event_count: int):
    event_close_times: dict[str, datetime] = {}
    for match in matches:
        if not match.event_ticker:
            continue
        close_time = parse_utc(match.raw_payload.get("close_time"))
        if close_time is None or close_time < now_utc:
            continue
        current_close = event_close_times.get(match.event_ticker)
        if current_close is None or close_time < current_close:
            event_close_times[match.event_ticker] = close_time

    selected_events = {
        event_ticker
        for event_ticker, _ in sorted(event_close_times.items(), key=lambda item: item[1])[
            :event_count
        ]
    }
    return [match for match in matches if match.event_ticker in selected_events]


def collect_once(args: argparse.Namespace) -> tuple[int, list[str]]:
    settings = load_settings()
    scrape_time = datetime.now(timezone.utc)
    client = KalshiClient(settings.kalshi_api_base)

    matches = [
        normalize_market(market, series_ticker=args.series_ticker)
        for market in client.iter_markets(
            status=args.status,
            series_ticker=args.series_ticker,
            limit=args.limit,
        )
        if is_core_cpi_candidate(market)
    ]
    selected = select_next_event_markets(
        matches,
        now_utc=scrape_time,
        event_count=args.event_count,
    )

    rows = [market_to_row(match, scrape_time_utc=scrape_time) for match in selected]
    rows.sort(
        key=lambda row: (
            str(row.get("scrape_time_utc") or ""),
            str(row.get("close_time_utc") or ""),
            str(row.get("event_ticker") or ""),
            float(row.get("floor_strike") or 0),
        )
    )
    append_partitioned_parquet(rows, output_dir=args.output)

    event_tickers = sorted({str(row["event_ticker"]) for row in rows})
    return len(rows), event_tickers


def main() -> None:
    args = parse_args()

    while True:
        if args.align_to_minute and not args.once:
            sleep_seconds = seconds_until_next_minute()
            if sleep_seconds > 0:
                sleep(sleep_seconds)

        try:
            row_count, event_tickers = collect_once(args)
            print(
                f"{datetime.now(timezone.utc).isoformat()} appended {row_count} rows "
                f"for {', '.join(event_tickers)}",
                flush=True,
            )
        except Exception:
            print(
                f"{datetime.now(timezone.utc).isoformat()} collection failed; "
                "retrying on the next cycle",
                flush=True,
            )
            traceback.print_exc()
            if args.once:
                raise
            continue
        if args.once:
            return

        if args.align_to_minute:
            continue

        sleep(args.interval_seconds)


def seconds_until_next_minute() -> float:
    now = datetime.now(timezone.utc)
    return 60.05 - now.second - (now.microsecond / 1_000_000)


if __name__ == "__main__":
    main()
