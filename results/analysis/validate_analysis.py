#!/usr/bin/env python
import sys
sys.dont_write_bytecode = True
from _analysis_runtime import main
if __name__ == '__main__': raise SystemExit(main(['validate']))
