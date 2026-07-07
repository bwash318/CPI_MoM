from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests


GAMMA_API_BASE = "https://gamma-api.polymarket.com"


@dataclass(frozen=True)
class PolymarketContract:
    event_id: str | None
    event_slug: str | None
    event_title: str | None
    market_id: str | None
    market_slug: str | None
    question: str | None
    outcome: str
    token_id: str | None
    outcome_price: float | None
    best_bid: float | None
    best_ask: float | None
    last_trade_price: float | None
    volume: float | None
    volume_24hr: float | None
    liquidity: float | None
    open_interest: float | None
    active: bool | None
    closed: bool | None
    end_time_utc: str | None
    source_url: str


class GammaClient:
    def __init__(self, api_base: str = GAMMA_API_BASE) -> None:
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()

    def iter_active_events(self, *, limit: int = 100, max_pages: int | None = None):
        offset = 0
        page_count = 0
        while True:
            response = self.session.get(
                f"{self.api_base}/events",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit,
                    "offset": offset,
                },
                timeout=30,
            )
            response.raise_for_status()
            events = response.json()
            if not events:
                break

            yield from events

            page_count += 1
            if max_pages is not None and page_count >= max_pages:
                break
            offset += limit

    def get_event_by_slug(self, slug: str) -> dict[str, Any] | None:
        response = self.session.get(f"{self.api_base}/events/slug/{slug}", timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        event = response.json()
        return event if isinstance(event, dict) else None


def event_matches_cpi_mom(event: dict[str, Any]) -> bool:
    text = searchable_event_title_text(event)
    if re.search(r"\bannual\b", text, re.I):
        return False

    has_cpi = re.search(r"\b(core\s+cpi|cpi|consumer price index)\b", text, re.I) is not None
    has_monthly = re.search(r"\b(mom|m/m|month[- ]over[- ]month|monthly)\b", text, re.I) is not None
    return has_cpi and has_monthly


def searchable_event_title_text(event: dict[str, Any]) -> str:
    pieces = [
        event.get("slug"),
        event.get("title"),
    ]
    for market in event.get("markets") or []:
        pieces.extend(
            [
                market.get("slug"),
                market.get("question"),
            ]
        )
    return " ".join(str(piece or "") for piece in pieces)


def searchable_event_text(event: dict[str, Any]) -> str:
    pieces = [
        event.get("slug"),
        event.get("title"),
        event.get("description"),
        event.get("resolutionSource"),
    ]
    for market in event.get("markets") or []:
        pieces.extend(
            [
                market.get("slug"),
                market.get("question"),
                market.get("description"),
                market.get("resolutionSource"),
            ]
        )
    return " ".join(str(piece or "") for piece in pieces)


def normalize_event_contracts(event: dict[str, Any]) -> list[PolymarketContract]:
    contracts: list[PolymarketContract] = []
    event_slug = event.get("slug")
    source_url = f"https://polymarket.com/event/{event_slug}" if event_slug else "https://polymarket.com"

    for market in event.get("markets") or []:
        if market.get("closed") is True:
            continue

        outcomes = parse_json_list(market.get("outcomes"))
        token_ids = parse_json_list(market.get("clobTokenIds"))
        outcome_prices = parse_json_list(market.get("outcomePrices"))

        for index, outcome in enumerate(outcomes):
            contracts.append(
                PolymarketContract(
                    event_id=as_string(event.get("id")),
                    event_slug=event_slug,
                    event_title=event.get("title"),
                    market_id=as_string(market.get("id")),
                    market_slug=market.get("slug"),
                    question=market.get("question"),
                    outcome=str(outcome),
                    token_id=value_at(token_ids, index),
                    outcome_price=parse_float(value_at(outcome_prices, index)),
                    best_bid=parse_float(market.get("bestBid")) if index == 0 else None,
                    best_ask=parse_float(market.get("bestAsk")) if index == 0 else None,
                    last_trade_price=parse_float(market.get("lastTradePrice")) if index == 0 else None,
                    volume=parse_float(market.get("volume")),
                    volume_24hr=parse_float(market.get("volume24hr")),
                    liquidity=parse_float(market.get("liquidity")),
                    open_interest=parse_float(market.get("openInterest")),
                    active=market.get("active"),
                    closed=market.get("closed"),
                    end_time_utc=market.get("endDate"),
                    source_url=source_url,
                )
            )
    return contracts


def parse_json_list(value: object) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def value_at(values: list[Any], index: int) -> Any:
    if index >= len(values):
        return None
    return values[index]


def parse_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
