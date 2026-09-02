# Test 07 propagation/fac TTT2 artifacts

This directory is the canonical artifact mirror for the Test 07 verification matrix.

- `run_ttt2_matrix.ps1`: reproducible 19-run TTT2/CeTA matrix against the four frozen TRSs.
- `trs/`: exact S1-S4 inputs.
- `runs/`: decoded run records and raw integrated-host HTML.
- `cpf/`: one CPF per run. A CPF from a `MAYBE` row contains a termination assumption and is not a proof.
- `exploratory_dp_sc/`: retained narrow `dp;sc` experiment showing why S1 requires more DP processors than the subterm criterion alone.
- `matrix_results.json`: machine-readable latest new-run results.
- `TTT2_RESULTS.csv`: full result ledger, including the reused S4 FAST certificate.

The human report is mirrored from `results/test-07-propagation-fac-tests/verification/TTT2_REPORT.md` after each audited run.
