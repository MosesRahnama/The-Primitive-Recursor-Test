#!/usr/bin/env python
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import runpy
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _analysis_runtime import cfg_reports, gen_folder_summary, gen_index, gen_test


def main():
    runpy.run_path(str(Path(__file__).with_name('analysis.py')), run_name='__main__')
    for report in cfg_reports('schema-a'):
        gen_test('schema-a', report)
    gen_folder_summary('schema-a')
    gen_index('schema-a')


if __name__ == '__main__':
    main()
