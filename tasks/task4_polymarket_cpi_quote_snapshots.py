from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

from cpi_mom.config import load_settings
from cpi_mom.polymarket import GammaClient, event_matches_cpi_mom, normalize_event_contracts


FIELDNAMES = [
    "scrape_time_utc",
    "exchange",
    "event_id",
    "event_slug",
    "event_title",
    "market_id",
    "market_slug",
    "question",
    "outcome_bucket",
    "threshold_value",
    "outcome",
    "token_id",
    "outcome_price_dollars",
    "best_bid_dollars",
    "best_ask_dollars",
    "last_trade_price_dollars",
    "volume",
    "volume_24hr",
    "liquidity",
    "open_interest",
    "active",
    "closed",
    "end_time_utc",
    "source_url",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append Polymarket CPI/Core CPI MoM quote snapshots when matching markets exist."
    )
    parser.add_argument(
        "--output",
        default="data/polymarket_cpi_quote_snapshots.csv",
        help="Append-only CSV output path.",
    )
    parser.add_argument("--once", action="store_true", help="Collect once and exit.")
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
    parser.add_argument("--limit", type=int, default=100, help="Gamma API events per page.")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="Maximum event pages to scan per scrape.",
    )
    parser.add_argument(
        "--event-slug",
        action="append",
        help="Known Polymarket event slug to scrape. Can be passed multiple times.",
    )
    return parser.parse_args()


def collect_once(args: argparse.Namespace) -> tuple[int, int]:
    scrape_time = datetime.now(timezone.utc).isoformat()
    settings = load_settings()
    client = GammaClient()

    matched_events = []
    rows = []
    seen_event_ids = set()

    known_slugs = list(settings.polymarket_event_slugs)
    if args.event_slug:
        known_slugs.extend(args.event_slug)

    for slug in dict.fromkeys(known_slugs):
        event = client.get_event_by_slug(slug)
        if not event:
            continue
        event_id = str(event.get("id") or event.get("slug") or slug)
        seen_event_ids.add(event_id)
        if event.get("closed") is True:
            continue
        matched_events.append(event)
        for contract in normalize_event_contracts(event):
            rows.append(contract_to_row(contract, scrape_time_utc=scrape_time))

    for event in client.iter_active_events(limit=args.limit, max_pages=args.max_pages):
        event_id = str(event.get("id") or event.get("slug") or "")
        if event_id in seen_event_ids:
            continue
        if not event_matches_cpi_mom(event):
            continue
        seen_event_ids.add(event_id)
        matched_events.append(event)
        for contract in normalize_event_contracts(event):
            rows.append(contract_to_row(contract, scrape_time_utc=scrape_time))

    rows.sort(
        key=lambda row: (
            str(row["end_time_utc"] or ""),
            str(row["event_slug"] or ""),
            str(row["market_slug"] or ""),
            str(row["outcome"] or ""),
        )
    )
    append_rows(Path(args.output), rows)
    return len(rows), len(matched_events)


def contract_to_row(contract, *, scrape_time_utc: str) -> dict[str, object]:
    return {
        "scrape_time_utc": scrape_time_utc,
        "exchange": "polymarket",
        "event_id": contract.event_id,
        "event_slug": contract.event_slug,
        "event_title": contract.event_title,
        "market_id": contract.market_id,
        "market_slug": contract.market_slug,
        "question": contract.question,
        "outcome_bucket": parse_outcome_bucket(contract.question),
        "threshold_value": parse_threshold_value(contract.question),
        "outcome": contract.outcome,
        "token_id": contract.token_id,
        "outcome_price_dollars": contract.outcome_price,
        "best_bid_dollars": contract.best_bid,
        "best_ask_dollars": contract.best_ask,
        "last_trade_price_dollars": contract.last_trade_price,
        "volume": contract.volume,
        "volume_24hr": contract.volume_24hr,
        "liquidity": contract.liquidity,
        "open_interest": contract.open_interest,
        "active": contract.active,
        "closed": contract.closed,
        "end_time_utc": contract.end_time_utc,
        "source_url": contract.source_url,
    }


def parse_outcome_bucket(question: str | None) -> str | None:
    if not question:
        return None
    text = question.lower()
    if "or less" in text:
        return "less_than_or_equal"
    if "or more" in text:
        return "greater_than_or_equal"
    if re.search(r"\bbe\s+-?\d", text):
        return "equals"
    return None


def parse_threshold_value(question: str | None) -> float | None:
    if not question:
        return None
    match = re.search(r"(-?\d+(?:\.\d+)?)%", question)
    if match:
        return float(match.group(1))
    match = re.search(r"(-?\d+)pt(\d+)", question)
    if match:
        sign = -1 if match.group(1).startswith("-") else 1
        whole = abs(int(match.group(1)))
        decimal = int(match.group(2)) / (10 ** len(match.group(2)))
        return sign * (whole + decimal)
    return None


def append_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists() and path.stat().st_size > 0

    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def seconds_until_next_minute() -> float:
    now = datetime.now(timezone.utc)
    return 60.05 - now.second - (now.microsecond / 1_000_000)


def main() -> None:
    args = parse_args()

    while True:
        if args.align_to_minute and not args.once:
            sleep_seconds = seconds_until_next_minute()
            if sleep_seconds > 0:
                sleep(sleep_seconds)

        row_count, event_count = collect_once(args)
        print(
            f"{datetime.now(timezone.utc).isoformat()} appended {row_count} rows "
            f"from {event_count} matching Polymarket events"
        )

        if args.once:
            return
        if args.align_to_minute:
            continue
        sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
