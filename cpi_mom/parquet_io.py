from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def append_partitioned_parquet(rows: list[dict[str, Any]], *, output_dir: str) -> Path | None:
    if not rows:
        return None

    partition_date = scrape_date(rows)
    path = Path(output_dir) / f"scrape_date={partition_date}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)

    new_df = pd.DataFrame(rows)
    if path.exists() and path.stat().st_size > 0:
        existing_df = pd.read_parquet(path)
        new_df = pd.concat([existing_df, new_df], ignore_index=True)

    new_df = normalize_for_parquet(new_df)
    new_df.to_parquet(path, index=False)
    return path


def scrape_date(rows: list[dict[str, Any]]) -> str:
    value = rows[0].get("scrape_time_utc")
    if not value:
        return datetime.now(timezone.utc).date().isoformat()

    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.now(timezone.utc).date().isoformat()

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


def normalize_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    for column in normalized.columns:
        if normalized[column].dtype == "object":
            normalized[column] = normalized[column].astype("string")
    return normalized
