# Generated Per-Test Runners

Thin generated wrappers, one per test/variant key, each calling `corpus_run.run(<key>)`. They make paid model API calls and inherit `corpus_run.py` retry, timeout, resume, cleanup, and default model-exclusion behavior.

Do not hand-edit these files. Change `scripts\gen_runners.py`, then regenerate. The key-to-surface table is in `scripts\README.md`.
