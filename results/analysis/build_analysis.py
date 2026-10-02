"""Run every per-test analysis and collect their finding rows into FINDINGS.csv.

    python results/analysis/build_analysis.py

Each folder's analysis.py reads results/final_scored_data, writes analysis.md and
analysis.csv beside itself, and returns its rows. This driver concatenates them.
"""
import csv
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _lib import FINDINGS_COLUMNS  # noqa: E402
from _analysis_runtime import SURFACE_FOLDERS  # noqa: E402

FOLDERS = [*SURFACE_FOLDERS, "cross-test"]


def main() -> None:
    all_rows = []
    for folder in FOLDERS:
        path = HERE / folder / "analysis.py"
        spec = importlib.util.spec_from_file_location(f"analysis_{folder.replace('-', '_')}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        rows = mod.run()
        all_rows.extend(rows)
        print(f"{folder:45s} rows={len(rows)}")
    out = HERE / "FINDINGS.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FINDINGS_COLUMNS)
        w.writeheader()
        for r in all_rows:
            w.writerow({c: r.get(c, "") for c in FINDINGS_COLUMNS})
    print(f"FINDINGS.csv rows={len(all_rows)}")


if __name__ == "__main__":
    main()
