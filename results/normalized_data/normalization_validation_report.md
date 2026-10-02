# Normalization Validation Report

> Source snapshot: 2026-09-03 22:07 UTC.

Status: **PASS**. Checks: 154. Failures: 0.

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
| SCHEMA_A | run-report hash | pass | sha256=16eeda8fa86b0dd4115538501c0c7557bb50048e73caa35672bc29bf9b37c4b5 |
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
| TEST07 | row count and order | pass | input=360 output=360 |
| TEST07 | unique session slugs | pass | rows=360 unique=360 |
| TEST07 | identity complete | pass | models=10 |
| TEST07 | score-free schema | pass | forbidden=[] |
| TEST07 | prefix cleanup | pass | residual=[] |
| TEST07 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST07 | method mapping | pass | mismatched_rows=0 |
| TEST07 | run-report hash | pass | sha256=3c5e933a4a9582adc1ca4395245801f9304f8ceb428de2f1a87797401024824c |
| TEST08 | row count and order | pass | input=140 output=140 |
| TEST08 | unique session slugs | pass | rows=140 unique=140 |
| TEST08 | identity complete | pass | models=5 |
| TEST08 | score-free schema | pass | forbidden=[] |
| TEST08 | prefix cleanup | pass | residual=[] |
| TEST08 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST08 | method mapping | pass | mismatched_rows=0 |
| TEST08 | run-report hash | pass | sha256=9d1f5c467c97a5570ef7b700c6cce32a230330ae315151a3ba06db8ebc823deb |
| TEST09 | row count and order | pass | input=80 output=80 |
| TEST09 | unique session slugs | pass | rows=80 unique=80 |
| TEST09 | identity complete | pass | models=5 |
| TEST09 | score-free schema | pass | forbidden=[] |
| TEST09 | prefix cleanup | pass | residual=[] |
| TEST09 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST09 | method mapping | pass | mismatched_rows=0 |
| TEST09 | run-report hash | pass | sha256=f857af88fc1c22650bc9aed772c20af3bc4751392e6b83b3d51851c4acca995f |
| TEST10 | row count and order | pass | input=100 output=100 |
| TEST10 | unique session slugs | pass | rows=100 unique=100 |
| TEST10 | identity complete | pass | models=10 |
| TEST10 | score-free schema | pass | forbidden=[] |
| TEST10 | prefix cleanup | pass | residual=[] |
| TEST10 | pass-through fidelity | pass | mismatched_cells=0 |
| TEST10 | method mapping | pass | mismatched_rows=0 |
| TEST10 | run-report hash | pass | sha256=f1b78f599a59590feee563b3c9216172577c61bb15c05b4fa49d5e6aa924da43 |
| PAYLOAD | row count and order | pass | input=120 output=120 |
| PAYLOAD | unique session slugs | pass | rows=120 unique=120 |
| PAYLOAD | identity complete | pass | models=10 |
| PAYLOAD | score-free schema | pass | forbidden=[] |
| PAYLOAD | prefix cleanup | pass | residual=[] |
| PAYLOAD | pass-through fidelity | pass | mismatched_cells=0 |
| PAYLOAD | method mapping | pass | mismatched_rows=0 |
| PAYLOAD | run-report hash | pass | sha256=901a2ef71ebe4a4bd666fbdede99e041fb1fbfe2546f3d1923fdddaff0f30302 |
| TEST01_CONTEXT | row count and order | pass | input=40 output=40 |
| TEST01_CONTEXT | unique session slugs | pass | rows=40 unique=40 |
| TEST01_CONTEXT | identity complete | pass | models=5 |
| TEST01_CONTEXT | score-free schema | pass | forbidden=[] |
| TEST01_CONTEXT | prefix cleanup | pass | residual=[] |
| TEST01_CONTEXT | pass-through fidelity | pass | mismatched_cells=0 |
| TEST01_CONTEXT | method mapping | pass | mismatched_rows=0 |
| TEST01_CONTEXT | run-report hash | pass | sha256=79fbd2fc111f70123033cebcf2ded0a1761bc1cfe5245cf09b0e0189297d4809 |
| TEST01_TOOLS | row count and order | pass | input=160 output=160 |
| TEST01_TOOLS | unique session slugs | pass | rows=160 unique=160 |
| TEST01_TOOLS | identity complete | pass | models=10 |
| TEST01_TOOLS | score-free schema | pass | forbidden=[] |
| TEST01_TOOLS | prefix cleanup | pass | residual=[] |
| TEST01_TOOLS | pass-through fidelity | pass | mismatched_cells=0 |
| TEST01_TOOLS | method mapping | pass | mismatched_rows=0 |
| TEST01_TOOLS | run-report hash | pass | sha256=da20217f87edb52e3b366b8717a51c682b7b772868844f367f0a9f9c8c8dbe36 |
| SCHEMA_A_NONCE | row count and order | pass | input=40 output=40 |
| SCHEMA_A_NONCE | unique session slugs | pass | rows=40 unique=40 |
| SCHEMA_A_NONCE | identity complete | pass | models=5 |
| SCHEMA_A_NONCE | score-free schema | pass | forbidden=[] |
| SCHEMA_A_NONCE | prefix cleanup | pass | residual=[] |
| SCHEMA_A_NONCE | pass-through fidelity | pass | mismatched_cells=0 |
| SCHEMA_A_NONCE | method mapping | pass | mismatched_rows=0 |
| SCHEMA_A_NONCE | run-report hash | pass | sha256=02af032df583432e227a0bdeec23c6a10c11f9eb12c46d34b60c166edfa2baea |
| GLOBAL | total row preservation | pass | input=4160 output=4160 |
| GLOBAL | normalization-only run state | pass | status=pass stage=normalization_only |
| GLOBAL | single dictionary authority | pass | canonical=results/normalized_data/normalization_methods |
| GLOBAL | no override artifacts | pass | files=[] |

This validator checks normalization only. It never reads scoring overrides and never writes to `results/final_scored_data`.
