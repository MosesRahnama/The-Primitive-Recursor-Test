"""Post-freeze fixed-opportunity robustness check for MATM online signals.

At each landmark, only episodes still active for that many recorded steps are
compared, and every episode is scored on exactly the same prefix length. This
addresses the extra signal opportunity available in longer failed episodes.
The analysis is explicitly post-freeze and exploratory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from matm_boundary_probe import ALLOWED_COLUMNS, analyze_episode, safe_steps
from score_matm_predictions import holm_adjust, signal_stat


HORIZONS = (3, 5, 10)
SIGNALS = {
    "webarena": (
        "hard_local_claim_counterwitness",
        "blocked_family_persistence",
        "null_progress_loop",
    ),
    "alfworld": ("null_progress_loop",),
}


def prefix_records(source: Path, relative: str, horizon: int) -> list[dict[str, str]]:
    columns = list(ALLOWED_COLUMNS) + ["success"]
    source_rows = pq.read_table(source, columns=columns).to_pylist()
    output: list[dict[str, str]] = []
    for source_row, row in enumerate(source_rows):
        steps = safe_steps(str(row["trajectory"]))
        if len(steps) < horizon:
            continue
        projected: dict[str, Any] = {column: row[column] for column in ALLOWED_COLUMNS}
        projected["trajectory"] = json.dumps(steps[:horizon], ensure_ascii=False)
        projected["num_steps"] = horizon
        prediction = analyze_episode(projected, relative, source_row)
        prediction["success"] = str(bool(row["success"])).lower()
        prediction["failure"] = str(not bool(row["success"])).lower()
        output.append(prediction)
    return output


def run(data_root: Path) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    pools: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        for environment in ("alfworld", "webarena"):
            relative = f"{environment}/population_runs.parquet"
            rows = prefix_records(data_root / relative, relative, horizon)
            failures = sum(row["failure"] == "true" for row in rows)
            pools.append(
                {
                    "environment": environment,
                    "horizon_steps": horizon,
                    "active_episode_n": len(rows),
                    "eventual_failures": failures,
                    "eventual_failure_rate": failures / len(rows) if rows else None,
                }
            )
            for signal in SIGNALS[environment]:
                result = signal_stat(rows, environment, signal)
                result["horizon_steps"] = horizon
                results.append(result)
    fisher_holm = holm_adjust([result["fisher_p"] for result in results])
    for result, adjusted in zip(results, fisher_holm):
        result["exploratory_fisher_p_holm12"] = adjusted
    return {
        "status": "post_freeze_exploratory_fixed_opportunity_landmark",
        "horizons": HORIZONS,
        "active_pools": pools,
        "signal_statistics": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(run(arguments.data_root), indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
