from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    kalshi_api_base: str
    polymarket_event_slugs: tuple[str, ...]


def load_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv()

    return Settings(
        database_url=os.getenv("DATABASE_URL"),
        kalshi_api_base=os.getenv(
            "KALSHI_API_BASE",
            "https://api.elections.kalshi.com/trade-api/v2",
        ).rstrip("/"),
        polymarket_event_slugs=tuple(
            slug.strip()
            for slug in os.getenv(
                "POLYMARKET_EVENT_SLUGS",
                "core-cpi-mom-july-2026-20260705181328287",
            ).split(",")
            if slug.strip()
        ),
    )
