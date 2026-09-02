#!/usr/bin/env python
"""Launch the canonical normalized-data validator."""

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "results" / "normalized_data" / "validate_normalized_data.py"

if not TARGET.exists():
    raise SystemExit(f"Missing canonical validator: {TARGET}")

runpy.run_path(str(TARGET), run_name="__main__")
