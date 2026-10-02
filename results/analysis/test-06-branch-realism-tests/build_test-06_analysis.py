#!/usr/bin/env python
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import runpy
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _analysis_runtime import cfg_reports, gen_folder_summary, gen_index, gen_test


def main():
    runpy.run_path(str(Path(__file__).with_name('analysis.py')), run_name='__main__')
    for report in cfg_reports('test-06'):
        gen_test('test-06', report)
    gen_folder_summary('test-06')
    gen_index('test-06')


if __name__ == '__main__':
    main()
