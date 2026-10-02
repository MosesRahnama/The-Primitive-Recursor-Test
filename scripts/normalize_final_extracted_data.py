#!/usr/bin/env python
"""Launch the canonical normalization driver from the scripts directory."""

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "results" / "normalized_data" / "normalize_final_extracted_data.py"

if not TARGET.exists():
    raise SystemExit(f"Missing canonical normalizer: {TARGET}")

runpy.run_path(str(TARGET), run_name="__main__")
