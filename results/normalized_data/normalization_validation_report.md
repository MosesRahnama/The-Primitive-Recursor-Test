# Normalization Validation Report

> Source snapshot: 2026-07-16 16:36 UTC.

Status: **PASS**. Checks: 90. Failures: 0.

| Test | Check | Status | Detail |
|---|---|---|---|
| GLOBAL | method dictionary schema | pass | ['primary_method', 'standardized_method_name', 'method_class'] |
| GLOBAL | method labels unique | pass | rows=1205 unique=1205 |
| GLOBAL | method labels complete | pass | rows=1205 |
| SCHEMA_A | row count and order | pass | input=240 output=240 |
| SCHEMA_A | unique session slugs | pass | rows=240 unique=240 |
| SCHEMA_A | identity complete | pass | models=30 |
| SCHEMA_A | score-free schema | pass | forbidden=[] |
| SCHEMA_A | prefix cleanup | pass | residual=[] |
| SCHEMA_A | pass-through fidelity | pass | mismatched_cells=0 |
| SCHEMA_A | method mapping | pass | mismatched_rows=0 |
| SCHEMA_A | run-report hash | pass | sha256=dde162fc563ff179304c4152af008b9f195937605259795ac51f508585fd0cba |
| SCHEMA_A_NEW_SYSTEM | row count and order | pass | input=240 output=240 |
| SCHEMA_A_NEW_SYSTEM | unique session slugs | pass | rows=240 unique=240 |
| SCHEMA_A_NEW_SYSTEM | identity complete | pass | models=30 |
| SCHEMA_A_NEW_SYSTEM | score-free schema | pass | forbidden=[] |
| SCHEMA_A_NEW_SYSTEM | prefix cleanup | pass | residual=[] |
| SCHEMA_A_NEW_SYSTEM | pass-through fidelity | pass | mismatched_cells=0 |
| SCHEMA_A_NEW_SYSTEM | method mapping | pass | mismatched_rows=0 |
| SCHEMA_A_NEW_SYSTEM | run-report hash | pass | sha256=043ac1b9eb56573233772165edc25867da34000698ff9f92354ee2ba891ad838 |
| SCHEMA_B | row count and order | pass | input=480 output=480 |
| SCHEMA_B | unique session slugs | pass | rows=480 unique=480 |
| SCHEMA_B | identity complete | pass | models=30 |
| SCHEMA_B | score-free schema | pass | forbidden=[] |
| SCHEMA_B | prefix cleanup | pass | residual=[] |
| SCHEMA_B | pass-through fidelity | pass | mismatched_cells=0 |
| SCHEMA_B | method mapping | pass | mismatched_rows=0 |
| SCHEMA_B | paired variant balance | pass | {'control': 240, 'regular': 240} |
| SCHEMA_B | run-report hash | pass | sha256=c3348fa6d632a92f3d2c474b63ca24a1784382e4fec489b4fc8ccd345718fdab |
| SCHEMA_B_NEW_SYSTEM | row count and order | pass | input=480 output=480 |
| SCHEMA_B_NEW_SYSTEM | unique session slugs | pass | rows=480 unique=480 |
| SCHEMA_B_NEW_SYSTEM | identity complete | pass | models=30 |
| SCHEMA_B_NEW_SYSTEM | score-free schema | pass | forbidden=[] |
| SCHEMA_B_NEW_SYSTEM | prefix cleanup | pass | residual=[] |
| SCHEMA_B_NEW_SYSTEM | pass-through fidelity | pass | mismatched_cells=0 |
| SCHEMA_B_NEW_SYSTEM | method mapping | pass | mismatched_rows=0 |
| SCHEMA_B_NEW_SYSTEM | paired variant balance | pass | {'control': 240, 'regular': 240} |
| SCHEMA_B_NEW_SYSTEM | run-report hash | pass | sha256=2d028ac771ff8bcce28ae887b77bd9bc17ae9f313d6dff964c8629dce4c689ba |
| TEST01 | row count and order | pass | input=480 output=480 |
| TEST01 | unique session slugs | pass | rows=480 unique=480 |
| TEST01 | identity complete | pass | models=30 |
| TEST01 | score-free schema | pass | forbidden=[] |
| TEST01 | prefix cleanup | pass | residual=[] |
| TEST01 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST01 | method mapping | pass | mismatched_rows=0 |
| TEST01 | paired variant balance | pass | {'control': 240, 'regular': 240} |
| TEST01 | run-report hash | pass | sha256=827b83ee852854338ecee641d638269a9dc8fa065c0bf899bee2a0a38c69915b |
| TEST02 | row count and order | pass | input=240 output=240 |
| TEST02 | unique session slugs | pass | rows=240 unique=240 |
| TEST02 | identity complete | pass | models=30 |
| TEST02 | score-free schema | pass | forbidden=[] |
| TEST02 | prefix cleanup | pass | residual=[] |
| TEST02 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST02 | method mapping | pass | mismatched_rows=0 |
| TEST02 | run-report hash | pass | sha256=582ec03ffbc7e0d47ab22e1428577e3c1cf2ba60cb5c4b5756aca3bb6d54d75a |
| TEST03 | row count and order | pass | input=240 output=240 |
| TEST03 | unique session slugs | pass | rows=240 unique=240 |
| TEST03 | identity complete | pass | models=30 |
| TEST03 | score-free schema | pass | forbidden=[] |
| TEST03 | prefix cleanup | pass | residual=[] |
| TEST03 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST03 | method mapping | pass | mismatched_rows=0 |
| TEST03 | run-report hash | pass | sha256=408ff71c50d31fb0d86f76d335a21b8340f8c46858280f404f51660f4eab4c03 |
| TEST04 | row count and order | pass | input=240 output=240 |
| TEST04 | unique session slugs | pass | rows=240 unique=240 |
| TEST04 | identity complete | pass | models=30 |
| TEST04 | score-free schema | pass | forbidden=[] |
| TEST04 | prefix cleanup | pass | residual=[] |
| TEST04 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST04 | method mapping | pass | mismatched_rows=0 |
| TEST04 | run-report hash | pass | sha256=802f375f724e6f1768228a55ab78d740c66a7d734ac87e6bdf9827b315a7e094 |
| TEST05 | row count and order | pass | input=240 output=240 |
| TEST05 | unique session slugs | pass | rows=240 unique=240 |
| TEST05 | identity complete | pass | models=30 |
| TEST05 | score-free schema | pass | forbidden=[] |
| TEST05 | prefix cleanup | pass | residual=[] |
| TEST05 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST05 | method mapping | pass | mismatched_rows=0 |
| TEST05 | run-report hash | pass | sha256=a6a906521cbac66701c86ff0acea13319002381017bd0cbc508970fb1b100913 |
| TEST06 | row count and order | pass | input=240 output=240 |
| TEST06 | unique session slugs | pass | rows=240 unique=240 |
| TEST06 | identity complete | pass | models=30 |
| TEST06 | score-free schema | pass | forbidden=[] |
| TEST06 | prefix cleanup | pass | residual=[] |
| TEST06 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST06 | method mapping | pass | mismatched_rows=0 |
| TEST06 | run-report hash | pass | sha256=bf97a99bdc3d5b3881c48e31e97cafd2e91164e5256ff0fbf3e98bf92b4ccc7f |
| GLOBAL | total row preservation | pass | input=3120 output=3120 |
| GLOBAL | normalization-only run state | pass | status=pass stage=normalization_only |
| GLOBAL | single dictionary authority | pass | canonical=results/normalized_data/normalization_methods |
| GLOBAL | no override artifacts | pass | files=[] |

This validator checks normalization only. It never reads scoring overrides and never writes to `results/final_scored_data`.
