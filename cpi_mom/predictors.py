from __future__ import annotations

import hashlib
import html
import csv
import re
import io
from dataclasses import dataclass
from datetime import date, datetime, timezone
from calendar import monthrange
from typing import Any

import requests


CLEVELAND_NOWCAST_URL = "https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
MONTH_PATTERN = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
FRED_SERIES = {
    "DGS2": "two_year_treasury_yield",
    "DGS10": "ten_year_treasury_yield",
    "T5YIE": "five_year_breakeven_inflation",
    "T10YIE": "ten_year_breakeven_inflation",
    "T5YIFR": "five_year_five_year_forward_inflation_expectation",
    "DCOILWTICO": "wti_crude_oil",
    "DTWEXBGS": "broad_us_dollar_index",
    "SP500": "sp500_index",
    "ICSA": "initial_jobless_claims",
    "PAYEMS": "nonfarm_payrolls",
    "UNRATE": "unemployment_rate",
    "CES0500000003": "average_hourly_earnings_total_private",
    "PPIACO": "producer_price_index_all_commodities",
    "WPSFD4131": "producer_price_index_final_demand_less_foods_energy",
    "RSAFS": "retail_and_food_services_sales",
}


@dataclass(frozen=True)
class PredictorObservation:
    source: str
    source_url: str
    predictor_family: str
    frequency: str
    period: str
    measure: str
    value: float | None
    source_updated: str
    raw_text: str

    @property
    def observation_key(self) -> str:
        return "|".join(
            [
                self.source,
                self.predictor_family,
                self.frequency,
                self.period,
                self.measure,
            ]
        )

    @property
    def content_hash(self) -> str:
        payload = "|".join(
            [
                self.observation_key,
                "" if self.value is None else f"{self.value:.12g}",
                self.source_updated,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fetch_cleveland_fed_nowcast() -> list[PredictorObservation]:
    response = requests.get(CLEVELAND_NOWCAST_URL, timeout=30)
    response.raise_for_status()
    text = html_to_text(response.text)

    observations: list[PredictorObservation] = []
    observations.extend(
        parse_cleveland_monthly_table(
            text,
            heading="Inflation, month-over-month percent change",
            frequency="monthly_mom",
        )
    )
    return observations


def fetch_fred_market_context() -> list[PredictorObservation]:
    observations: list[PredictorObservation] = []
    for series_id, measure in FRED_SERIES.items():
        response = requests.get(FRED_CSV_URL, params={"id": series_id}, timeout=30)
        response.raise_for_status()
        latest = latest_fred_observation(response.text, series_id)
        if latest is None:
            continue

        observation_date, value = latest
        observations.append(
            PredictorObservation(
                source="fred",
                source_url=f"{FRED_CSV_URL}?id={series_id}",
                predictor_family="market_context",
                frequency="daily",
                period=observation_date,
                measure=measure,
                value=value,
                source_updated=observation_date,
                raw_text=f"{series_id},{observation_date},{value}",
            )
        )
    return observations


def latest_fred_observation(csv_text: str, series_id: str) -> tuple[str, float] | None:
    reader = csv.DictReader(io.StringIO(csv_text))
    latest: tuple[str, float] | None = None
    for row in reader:
        value_text = row.get(series_id)
        if not value_text or value_text == ".":
            continue
        latest = (str(row["observation_date"]), float(value_text))
    return latest


def html_to_text(markup: str) -> str:
    no_tags = re.sub(r"<[^>]+>", " ", markup)
    unescaped = html.unescape(no_tags)
    return re.sub(r"\s+", " ", unescaped).strip()


def parse_cleveland_monthly_table(
    text: str,
    *,
    heading: str,
    frequency: str,
) -> list[PredictorObservation]:
    section = extract_section(text, heading)
    row_pattern = re.compile(
        rf"(?P<period>(?:{MONTH_PATTERN}) \d{{4}})\s+"
        rf"(?P<cpi>-?\d+(?:\.\d+)?)\s+"
        rf"(?P<core_cpi>-?\d+(?:\.\d+)?)\s+"
        rf"(?P<pce>-?\d+(?:\.\d+)?)\s+"
        rf"(?P<core_pce>-?\d+(?:\.\d+)?)\s+"
        rf"(?P<updated>\d{{2}}/\d{{2}})"
    )

    observations: list[PredictorObservation] = []
    for match in row_pattern.finditer(section):
        groups = match.groupdict()
        for field_name, measure in (
            ("cpi", "cpi"),
            ("core_cpi", "core_cpi"),
            ("pce", "pce"),
            ("core_pce", "core_pce"),
        ):
            observations.append(
                PredictorObservation(
                    source="cleveland_fed",
                    source_url=CLEVELAND_NOWCAST_URL,
                    predictor_family="inflation_nowcast",
                    frequency=frequency,
                    period=groups["period"],
                    measure=measure,
                    value=parse_float(groups[field_name]),
                    source_updated=normalize_month_day(groups["updated"]),
                    raw_text=match.group(0),
                )
            )
    return observations


def parse_cleveland_quarterly_table(text: str) -> list[PredictorObservation]:
    section = extract_section(text, "Quarterly annualized percent change")
    row_pattern = re.compile(
        r"(?P<period>\d{4}:Q[1-4])\s+"
        r"(?P<cpi>-?\d+(?:\.\d+)?)\s+"
        r"(?P<core_cpi>-?\d+(?:\.\d+)?)\s+"
        r"(?P<pce>-?\d+(?:\.\d+)?)\s+"
        r"(?P<core_pce>-?\d+(?:\.\d+)?)\s+"
        r"(?P<updated>\d{2}/\d{2})"
    )

    observations: list[PredictorObservation] = []
    for match in row_pattern.finditer(section):
        groups = match.groupdict()
        for field_name, measure in (
            ("cpi", "cpi"),
            ("core_cpi", "core_cpi"),
            ("pce", "pce"),
            ("core_pce", "core_pce"),
        ):
            observations.append(
                PredictorObservation(
                    source="cleveland_fed",
                    source_url=CLEVELAND_NOWCAST_URL,
                    predictor_family="inflation_nowcast",
                    frequency="quarterly_annualized",
                    period=groups["period"],
                    measure=measure,
                    value=parse_float(groups[field_name]),
                    source_updated=normalize_month_day(groups["updated"]),
                    raw_text=match.group(0),
                )
            )
    return observations


def extract_section(text: str, heading: str) -> str:
    start = text.find(heading)
    if start == -1:
        raise ValueError(f"Could not find section heading: {heading}")

    next_note = text.find("Note:", start)
    if next_note == -1:
        return text[start:]
    return text[start:next_note]


def parse_float(value: str) -> float | None:
    if value == "":
        return None
    return float(value)


def normalize_month_day(value: str) -> str:
    month_text, day_text = value.split("/")
    now = datetime.now(timezone.utc).date()
    year = now.year
    month = int(month_text)
    day = int(day_text)
    day = min(day, monthrange(year, month)[1])
    parsed = date(year, month, day)

    # Handles rare New Year cases where the page still shows a December update.
    if (parsed - now).days > 30:
        parsed = date(year - 1, month, day)

    return parsed.isoformat()


def observation_to_row(observation: PredictorObservation, *, scrape_time_utc: str) -> dict[str, Any]:
    return {
        "scrape_time_utc": scrape_time_utc,
        "source": observation.source,
        "predictor_family": observation.predictor_family,
        "frequency": observation.frequency,
        "period": observation.period,
        "measure": observation.measure,
        "value": observation.value,
        "source_updated": observation.source_updated,
        "source_url": observation.source_url,
    }
