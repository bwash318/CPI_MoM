from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from cpi_mom.config import load_settings
from cpi_mom.kalshi import KalshiClient, is_core_cpi_candidate, normalize_market


UPSERT_SQL = """
insert into markets (
    exchange,
    native_market_id,
    native_event_id,
    native_series_id,
    market_name,
    market_status,
    raw_payload,
    discovered_at_utc,
    updated_at_utc
)
values (
    'kalshi',
    %(native_market_id)s,
    %(native_event_id)s,
    %(native_series_id)s,
    %(market_name)s,
    %(market_status)s,
    %(raw_payload)s,
    %(discovered_at_utc)s,
    %(updated_at_utc)s
)
on conflict (exchange, native_market_id)
do update set
    native_event_id = excluded.native_event_id,
    native_series_id = excluded.native_series_id,
    market_name = excluded.market_name,
    market_status = excluded.market_status,
    raw_payload = excluded.raw_payload,
    updated_at_utc = excluded.updated_at_utc;
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Discover Kalshi Core CPI MoM candidate markets.")
    parser.add_argument("--dry-run", action="store_true", help="Print matches without DB writes.")
    parser.add_argument("--status", default="open", help="Kalshi market status to query.")
    parser.add_argument(
        "--series-ticker",
        help="Optional Kalshi series ticker filter, such as KXCPI.",
    )
    parser.add_argument("--limit", type=int, default=100, help="Markets to request per API page.")
    parser.add_argument("--max-pages", type=int, help="Maximum API pages to scan.")
    parser.add_argument("--sleep-seconds", type=float, default=0.25, help="Pause between API pages.")
    parser.add_argument("--output", help="Optional CSV output path for discovered markets.")
    return parser.parse_args()


def market_to_row(match, *, discovered_at_utc: datetime) -> dict[str, object]:
    raw = match.raw_payload
    yes_bid = parse_float(raw.get("yes_bid_dollars"))
    yes_ask = parse_float(raw.get("yes_ask_dollars"))
    yes_bid_size = parse_float(raw.get("yes_bid_size_fp"))
    yes_ask_size = parse_float(raw.get("yes_ask_size_fp"))

    return {
        "scrape_time_utc": discovered_at_utc.isoformat(),
        "exchange": "kalshi",
        "event_ticker": match.event_ticker,
        "market_ticker": match.market_ticker,
        "title": match.title,
        "subtitle": match.subtitle,
        "status": match.status,
        "strike_type": raw.get("strike_type"),
        "floor_strike": raw.get("floor_strike"),
        "cap_strike": raw.get("cap_strike"),
        "yes_bid_dollars": raw.get("yes_bid_dollars"),
        "yes_ask_dollars": raw.get("yes_ask_dollars"),
        "yes_bid_size_fp": raw.get("yes_bid_size_fp"),
        "yes_ask_size_fp": raw.get("yes_ask_size_fp"),
        "no_bid_dollars": raw.get("no_bid_dollars"),
        "no_ask_dollars": raw.get("no_ask_dollars"),
        "fair_yes_topbook_dollars": weighted_topbook_fair(
            bid=yes_bid,
            ask=yes_ask,
            bid_size=yes_bid_size,
            ask_size=yes_ask_size,
        ),
        "fair_no_from_yes_dollars": complement(
            weighted_topbook_fair(
                bid=yes_bid,
                ask=yes_ask,
                bid_size=yes_bid_size,
                ask_size=yes_ask_size,
            )
        ),
        "last_price_dollars": raw.get("last_price_dollars"),
        "previous_price_dollars": raw.get("previous_price_dollars"),
        "volume_fp": raw.get("volume_fp"),
        "volume_24h_fp": raw.get("volume_24h_fp"),
        "open_interest_fp": raw.get("open_interest_fp"),
        "open_time_utc": raw.get("open_time"),
        "close_time_utc": raw.get("close_time"),
        "expiration_time_utc": raw.get("expiration_time"),
    }


def parse_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def weighted_topbook_fair(
    *,
    bid: float | None,
    ask: float | None,
    bid_size: float | None,
    ask_size: float | None,
) -> float | None:
    if bid is None or ask is None or bid_size is None or ask_size is None:
        return None

    total_size = bid_size + ask_size
    if total_size <= 0:
        return None

    return ((bid * ask_size) + (ask * bid_size)) / total_size


def complement(value: float | None) -> float | None:
    if value is None:
        return None
    return 1 - value


def write_csv(matches, *, output_path: str, discovered_at_utc: datetime) -> None:
    rows = [market_to_row(match, discovered_at_utc=discovered_at_utc) for match in matches]
    rows.sort(
        key=lambda row: (
            str(row.get("scrape_time_utc") or ""),
            str(row.get("close_time_utc") or ""),
            str(row.get("event_ticker") or ""),
            float(row.get("floor_strike") or 0),
        )
    )
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


def main() -> None:
    args = parse_args()
    settings = load_settings()
    now = datetime.now(timezone.utc)

    client = KalshiClient(settings.kalshi_api_base)
    matches = [
        normalize_market(market, series_ticker=args.series_ticker)
        for market in client.iter_markets(
            status=args.status,
            series_ticker=args.series_ticker,
            limit=args.limit,
            max_pages=args.max_pages,
            sleep_seconds=args.sleep_seconds,
        )
        if is_core_cpi_candidate(market)
    ]

    if args.output:
        write_csv(matches, output_path=args.output, discovered_at_utc=now)

    if args.dry_run:
        print(json.dumps([match.__dict__ for match in matches], indent=2, default=str))
        return

    if not settings.database_url:
        print("DATABASE_URL is not set, so no database rows were written.")
        return

    from cpi_mom.db import connect
    from psycopg.types.json import Jsonb

    with connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            for match in matches:
                cur.execute(
                    UPSERT_SQL,
                    {
                        "native_market_id": match.market_ticker,
                        "native_event_id": match.event_ticker,
                        "native_series_id": match.series_ticker,
                        "market_name": match.title or match.subtitle or match.market_ticker,
                        "market_status": match.status,
                        "raw_payload": Jsonb(match.raw_payload),
                        "discovered_at_utc": now,
                        "updated_at_utc": now,
                    },
                )

    print(f"Wrote {len(matches)} Kalshi candidate markets.")


if __name__ == "__main__":
    main()
