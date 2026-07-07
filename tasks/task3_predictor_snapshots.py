from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

from cpi_mom.predictors import (
    PredictorObservation,
    fetch_cleveland_fed_nowcast,
    fetch_fred_market_context,
    observation_to_row,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Append predictor observations only when values change."
    )
    parser.add_argument(
        "--output",
        default="data/predictor_snapshots.csv",
        help="Append-only CSV output path.",
    )
    parser.add_argument(
        "--state",
        default="data/predictor_latest_hashes.json",
        help="JSON state file used for change detection.",
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
    return parser.parse_args()


def load_state(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def append_rows(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def collect_once(args: argparse.Namespace) -> int:
    scrape_time = datetime.now(timezone.utc).isoformat()
    output_path = Path(args.output)
    state_path = Path(args.state)

    state = load_state(state_path)
    observations = []
    observations.extend(fetch_cleveland_fed_nowcast())
    observations.extend(fetch_fred_market_context())

    changed_rows: list[dict[str, object]] = []
    for group_key, group_observations in group_observations_for_change_detection(observations).items():
        group_hash = hash_observation_group(group_observations)
        previous_hash = state.get(group_key)
        if previous_hash == group_hash:
            continue

        for observation in group_observations:
            changed_rows.append(observation_to_row(observation, scrape_time_utc=scrape_time))
        state[group_key] = group_hash

    changed_rows.sort(
        key=lambda row: (
            str(row["source"]),
            str(row["frequency"]),
            str(row["period"]),
            str(row["measure"]),
        )
    )

    append_rows(output_path, changed_rows)
    save_state(state_path, state)
    return len(changed_rows)


def group_observations_for_change_detection(
    observations: list[PredictorObservation],
) -> dict[str, list[PredictorObservation]]:
    groups: dict[str, list[PredictorObservation]] = {}
    for observation in observations:
        group_key = change_detection_group_key(observation)
        groups.setdefault(group_key, []).append(observation)
    return groups


def change_detection_group_key(observation: PredictorObservation) -> str:
    if observation.source == "cleveland_fed" and observation.frequency == "monthly_mom":
        return "|".join(
            [
                observation.source,
                observation.predictor_family,
                observation.frequency,
                observation.period,
            ]
        )

    return observation.observation_key


def hash_observation_group(observations: list[PredictorObservation]) -> str:
    payload_parts = []
    for observation in sorted(observations, key=lambda item: item.measure):
        payload_parts.append(
            "|".join(
                [
                    observation.measure,
                    "" if observation.value is None else f"{observation.value:.12g}",
                    observation.source_updated,
                ]
            )
        )
    payload = "\n".join(payload_parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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

        row_count = collect_once(args)
        print(f"{datetime.now(timezone.utc).isoformat()} appended {row_count} changed rows")

        if args.once:
            return

        if args.align_to_minute:
            continue

        sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
