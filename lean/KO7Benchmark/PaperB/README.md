# PaperB

This folder contains the public theory-lane Lean modules used to back the
paper's theorem-level claims.

The answer-key lane remains rooted at `../../KO7Benchmark.lean` and is locked
separately by `../../../scoring/answer-key/answer_key.json` plus the source
lock manifest. This `PaperB/` tree is part of the separate theory lane rooted
at `../../KO7BenchmarkTheory.lean`.

Use this folder when auditing the theorem bridge cited by the manuscript.
These modules are not imported from the locked public `KO7Benchmark` root; they
are imported through the separate `KO7BenchmarkTheory` build target.
