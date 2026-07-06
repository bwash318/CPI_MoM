from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterator
from time import sleep
from typing import Any

import requests


CORE_CPI_TERMS = ("core cpi", "core consumer price index", "cpi")


@dataclass(frozen=True)
class KalshiMarket:
    market_ticker: str
    event_ticker: str | None
    series_ticker: str | None
    title: str | None
    subtitle: str | None
    status: str | None
    raw_payload: dict[str, Any]


class KalshiClient:
    def __init__(self, api_base: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()

    def iter_markets(
        self,
        *,
        status: str = "open",
        series_ticker: str | None = None,
        limit: int = 100,
        max_pages: int | None = None,
        sleep_seconds: float = 0.25,
    ) -> Iterator[dict[str, Any]]:
        cursor: str | None = None
        page_count = 0
        while True:
            params: dict[str, Any] = {"status": status, "limit": limit}
            if series_ticker:
                params["series_ticker"] = series_ticker
            if cursor:
                params["cursor"] = cursor

            response = self.session.get(f"{self.api_base}/markets", params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()

            for market in payload.get("markets", []):
                yield market

            page_count += 1
            cursor = payload.get("cursor")
            if not cursor or (max_pages is not None and page_count >= max_pages):
                break
            sleep(sleep_seconds)


def is_core_cpi_candidate(market: dict[str, Any]) -> bool:
    searchable = " ".join(
        str(market.get(field) or "")
        for field in (
            "ticker",
            "event_ticker",
            "series_ticker",
            "title",
            "subtitle",
            "yes_sub_title",
            "no_sub_title",
            "rules_primary",
            "rules_secondary",
        )
    ).lower()
    return any(term in searchable for term in CORE_CPI_TERMS)


def normalize_market(market: dict[str, Any], *, series_ticker: str | None = None) -> KalshiMarket:
    return KalshiMarket(
        market_ticker=str(market.get("ticker") or ""),
        event_ticker=market.get("event_ticker"),
        series_ticker=market.get("series_ticker") or series_ticker,
        title=market.get("title"),
        subtitle=market.get("subtitle"),
        status=market.get("status"),
        raw_payload=market,
    )
