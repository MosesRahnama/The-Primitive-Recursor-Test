#!/usr/bin/env python
import sys
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _analysis_runtime import gen_test
if __name__ == '__main__': gen_test('schema-b', 'control_or_pair_profile')
