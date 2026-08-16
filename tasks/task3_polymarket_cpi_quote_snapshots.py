from __future__ import annotations

import argparse
import re
import traceback
from datetime import datetime, timezone
from time import sleep

from cpi_mom.config import load_settings
from cpi_mom.parquet_io import append_partitioned_parquet
from cpi_mom.polymarket import GammaClient, event_matches_cpi_mom, normalize_event_contracts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append Polymarket CPI/Core CPI MoM quote snapshots when matching markets exist."
    )
    parser.add_argument(
        "--output",
        default="data/polymarket_cpi_quote_snapshots",
        help="Directory for daily partitioned Parquet output.",
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
    parser.add_argument(
        "--event-count",
        type=int,
        default=2,
        help="Number of upcoming CPI MoM events to keep after discovery.",
    )
    return parser.parse_args()


def collect_once(args: argparse.Namespace) -> tuple[int, int]:
    scrape_time = datetime.now(timezone.utc).isoformat()
    settings = load_settings()
    client = GammaClient()

    matched_events = []
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

    for event in client.iter_active_events(limit=args.limit, max_pages=args.max_pages):
        event_id = str(event.get("id") or event.get("slug") or "")
        if event_id in seen_event_ids:
            continue
        if not event_matches_cpi_mom(event):
            continue
        seen_event_ids.add(event_id)
        matched_events.append(event)

    selected_events = select_next_events(matched_events, event_count=args.event_count)
    rows = []
    for event in selected_events:
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
    append_partitioned_parquet(rows, output_dir=args.output)
    return len(rows), len(selected_events)


def select_next_events(events: list[dict], *, event_count: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    open_events = []
    for event in events:
        if event.get("closed") is True:
            continue
        end_time = parse_utc(event.get("endDate"))
        if end_time is None:
            event_end_times = [
                parse_utc(market.get("endDate"))
                for market in event.get("markets") or []
                if market.get("closed") is not True
            ]
            event_end_times = [value for value in event_end_times if value is not None]
            end_time = min(event_end_times) if event_end_times else None
        if end_time is None or end_time < now:
            continue
        open_events.append((end_time, event))

    return [event for _, event in sorted(open_events, key=lambda item: item[0])[:event_count]]


def parse_utc(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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

        try:
            row_count, event_count = collect_once(args)
            print(
                f"{datetime.now(timezone.utc).isoformat()} appended {row_count} rows "
                f"from {event_count} matching Polymarket events",
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


if __name__ == "__main__":
    main()
