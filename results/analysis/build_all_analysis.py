#!/usr/bin/env python
r"""Build per-surface findings and the core statistical reports."""

import sys

sys.dont_write_bytecode = True

from _analysis_runtime import gen_all
from build_analysis import main as build_findings


if __name__ == "__main__":
    build_findings()
    gen_all()
