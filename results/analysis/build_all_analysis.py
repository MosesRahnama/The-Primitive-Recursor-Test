#!/usr/bin/env python
r"""Regenerate the complete PRT-New analysis layer."""

import sys

sys.dont_write_bytecode = True

from _analysis_runtime import gen_all


if __name__ == "__main__":
    gen_all()
