from __future__ import annotations

from datetime import datetime


def market_to_row(match, *, scrape_time_utc: datetime) -> dict[str, object]:
    raw = match.raw_payload
    yes_bid = parse_float(raw.get("yes_bid_dollars"))
    yes_ask = parse_float(raw.get("yes_ask_dollars"))
    yes_bid_size = parse_float(raw.get("yes_bid_size_fp"))
    yes_ask_size = parse_float(raw.get("yes_ask_size_fp"))
    fair_yes = weighted_topbook_fair(
        bid=yes_bid,
        ask=yes_ask,
        bid_size=yes_bid_size,
        ask_size=yes_ask_size,
    )

    return {
        "scrape_time_utc": scrape_time_utc.isoformat(),
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
        "fair_yes_topbook_dollars": fair_yes,
        "fair_no_from_yes_dollars": complement(fair_yes),
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

