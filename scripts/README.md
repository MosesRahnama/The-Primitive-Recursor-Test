# Scripts

This directory contains the benchmark session runners, extraction infrastructure,
consolidation and publishing tools, and a small set of specialized legacy utilities.
Run all commands below from the repo root.

## Recommended Workflow

```text
roster/models.json
  -> build_roster.py
  -> run_battery.py or corpus_run.py
  -> sync_extraction_sessions.py --apply
  -> manual extractor work (one extractor per round, one output)
  -> express_extraction.py finalize
  -> combine_consolidations.py
  -> publish_final_extracted_data.py
  -> results/normalized_data/normalize_final_extracted_data.py
  -> scoring pipeline
```

Important operating rules:

- `run_battery.py`, `corpus_run.py`, `run_corpus.py`, and `runners/*.py` make paid
  model API calls. `corpus_run.py` also deletes failed or incomplete session folders
  after its bounded retry loop.
- `sync_extraction_sessions.py` is the current intake command for all ten tests.
  Its default mode is read-only; use `--apply` to append rows.
- Response-derived extraction cells are never filled mechanically. The sync and
  express tools only create slug rows, metadata, backups, manifests, and audits.
- The older pipeline `intake` subcommands are disabled after express runs exist, to
  prevent duplicate rows. Their `verify`, `publish`, `status`, `report`, and `render`
  commands remain available where defined.
- Current automatic extraction intake targets eight usable sessions per live model
  per required variant. Several older corpus launchers still default to four; pass
  `--runs 8` to `run_battery.py` or `corpus_run.py` when generating an eight-run set.

## Session Generation

### `build_roster.py`

Builds the runtime roster from the ordered source file `roster/models.json`.

- Writes `roster/roster.json`, consumed by runners, audits, and extraction tools.
- Writes the human-readable `roster/roster.md` table.
- Direct-provider models are marked live by construction. If any model routes through
  OpenRouter, the script checks OpenRouter's `/models` endpoint before marking it live.
- Reads API credentials from environment variables first, then the local key fallback.
- Makes no benchmark test calls.

```powershell
python scripts\build_roster.py
```

### `run_battery.py`

The core raw-session generator. It sends prompt files verbatim to each selected live
model, assigns no grades, and writes one immutable folder per call under
`results\<test>\test-sessions\<session_slug>\`.

- Supports all ten tests and the Schema B control and Test 01 fruit variants.
- Writes two-turn files for Schema A and Schema A New System; all other tests are
  single-turn.
- Routes each model through its roster-defined direct provider or OpenRouter route.
- Supports repeated `--test`, selected `--models`, `--runs`, `--workers`, `--resume`,
  `--skip`, and a small `--validate` run.
- Retries only transient HTTP failures once. Timeouts, empty answers, and other
  potentially billed failures are not immediately rebilled.
- Uses an attempt cap in resume mode and writes failures as `[ERROR]` responses.

```powershell
python scripts\run_battery.py --test test-05 --runs 8 --resume
python scripts\run_battery.py --test schema-a --models claude-opus-4.8
```

### `corpus_run.py`

A bounded, resumable wrapper around `run_battery.py` for one test key.

- Repeats child-process passes until the target is reached or the pass/deadline limit
  is exhausted.
- Applies a hard wall-clock timeout to each child process, then resumes missing work.
- Counts usable sessions by variant and removes failed/incomplete session directories
  at the end. This deletion is intentional and is the principal safety distinction
  from running `run_battery.py` directly.
- Defaults to four sessions per model and skips `claude-fable-5`; both are configurable.

```powershell
python scripts\corpus_run.py --list
python scripts\corpus_run.py test-04 --runs 8 --workers 8
```

### `run_corpus.py`

Generated master launcher that runs all 13 test/variant keys sequentially through
`corpus_run.run`. It currently requests four sessions per model for each key and prints
one final coverage summary. Re-running it tops up incomplete keys.

```powershell
python scripts\run_corpus.py
```

### `gen_runners.py`

Regenerates `run_corpus.py` and every wrapper under `scripts\runners\` from its
internal test table. It overwrites those generated files. Update the generator first
when changing their fixed run count or test order.

```powershell
python scripts\gen_runners.py
```

## Extraction Intake and Express Runs

### `sync_extraction_sessions.py`

The current all-tests incremental intake driver.

- Scans all ten `test-sessions` directories against the live roster.
- Selects completed, non-bad sessions until each model/variant reaches the target
  count, eight by default.
- Excludes out-of-roster, unsupported-variant, known-bad, missing, empty, unreadable,
  malformed-metadata, and `[ERROR]` sessions. It does not judge answer correctness or
  automatically diagnose semantic truncation.
- Treats a slug found in any active extraction CSV as already initialized. If it is
  missing from other CSVs for that test, `--apply` appends a blank row to each missing
  extractor/consolidation file and mechanical identity fields to a missing ledger row.
- Preserves all existing rows and cells, rejects duplicate slugs, enforces target caps,
  and records automatic run IDs.
- Uses `express_extraction.py prepare` for wholly new sessions. Partial-row repairs get
  independent backups, manifests, and audits under `batches\sync_repairs\<run-id>\`.

```powershell
# Read-only plan for all tests
python scripts\sync_extraction_sessions.py

# Apply all newly eligible rows and partial-row repairs
python scripts\sync_extraction_sessions.py --apply

# Limit to one test or inspect exact slugs
python scripts\sync_extraction_sessions.py --test test-05-candidate-class-reasoning-tests --show-slugs
```

### `express_extraction.py`

Transactional infrastructure for small manual extraction runs.

- `build-dispatch` derives the 30 role documents, three roles for each of ten tests,
  from the live round contracts. `--check` reports stale generated documents.
- `prepare` takes an explicit slug list, validates the test contract and metadata,
  snapshots every target CSV, appends blank rows, hashes raw responses, and creates an
  immutable run manifest under `batches\express_runs\<run-id>\`.
- `finalize` verifies preserved baseline rows, source hashes, literal quote/span
  evidence, completed consolidation fields, and master-output growth. It then invokes
  the existing combine scripts.
- It never chooses or fills a response-derived extraction value.

```powershell
python scripts\express_extraction.py build-dispatch --check
python scripts\express_extraction.py prepare --test test-04-measure-verification-tests --run-id run_001 --session-slugs slugs.csv --dry-run
python scripts\express_extraction.py finalize --test test-04-measure-verification-tests --run-id run_001
```

See `express_extraction.md` for the generated operator guide.

### `test_sync_extraction_sessions.py`

Unit tests for the automatic synchronizer. The tests use temporary fixtures and cover
target-capped live-roster selection, bad/invalid/out-of-roster filtering, partial-CSV
repair, historical row-order differences, and Schema A response-file completeness.

```powershell
python -m unittest -v scripts.test_sync_extraction_sessions
```

## Extraction Pipelines

These four modules define the authoritative round schemas and mechanical validation
rules consumed by the combiner. Their legacy `intake` commands must not be used after
express runs exist; use `sync_extraction_sessions.py` instead.

### `schema_a_pipeline.py`

Shared four-round engine for Schema A and Schema A New System. It defines Turn 1/Turn 2
core and peripheral schemas, quote-source restrictions, controlled vocabularies,
agreement gates, method normalization, QA sampling, publication reshaping, and status
reports. The two tests differ in their Round 3 structural flag and publish-time method
classes.

```powershell
python scripts\schema_a_pipeline.py --test schema-test-A-tests verify --batch latest
python scripts\schema_a_pipeline.py --test schema-test-A-new-system-tests status
python scripts\schema_a_pipeline.py --test schema-test-A-tests publish
python scripts\schema_a_pipeline.py --test schema-test-A-tests report
```

### `schema_b_pipeline.py`

Shared two-round engine for Schema B and Schema B New System. Round 1 carries coded
method verdicts, rationales, accepted sets, and confidence; Round 2 carries literal
evidence spans. It validates formatting and agreement mechanically, then applies each
test's fixed answer key only during publication. It handles regular/control variants.

```powershell
python scripts\schema_b_pipeline.py --test schema-test-B-tests verify --batch latest
python scripts\schema_b_pipeline.py --test schema-test-B-new-system-tests status
python scripts\schema_b_pipeline.py --test schema-test-B-tests publish
python scripts\schema_b_pipeline.py --test schema-test-B-tests report
```

### `test01_pipeline.py`

Three-round single-response engine for Test 01, covering both KO7 and fruit variants.
It validates core verdict/method fields, boundary/W2 fields, peripheral/objection fields,
literal evidence, agreement, and method normalization. `render` regenerates a batch's
dispatch documents from current templates.

```powershell
python scripts\test01_pipeline.py verify --batch latest
python scripts\test01_pipeline.py render --batch latest
python scripts\test01_pipeline.py status
python scripts\test01_pipeline.py publish
```

### `test0x_pipeline.py`

Shared two-round engine for Tests 02-06. Round 1 contains each test's coded core and
Round 2 contains literal evidence. The selected `--test` configures its schema,
controlled vocabulary, QA checks, publish-time mechanical answer-key derivations,
status board, and audit report.

```powershell
python scripts\test0x_pipeline.py --test test-04-measure-verification-tests verify --batch latest
python scripts\test0x_pipeline.py --test test-05-candidate-class-reasoning-tests status
python scripts\test0x_pipeline.py --test test-06-branch-realism-tests publish
python scripts\test0x_pipeline.py --test test-02-completion-tests-nat-lex report
```

## Consolidation, Publication, and Normalization

### `combine_consolidations.py`

Generic mechanical combiner for all ten tests. It loads each test's round schema from
the relevant pipeline module, validates headers, controlled vocabularies, duplicate
slugs, and cross-round slug order, then writes one wide round-prefixed final
consolidation plus an audit file. It refuses blank consolidation payloads. A dynamic
program repairs only malformed CSV tokenization caused by unquoted embedded commas;
it does not make semantic decisions.

```powershell
python scripts\combine_consolidations.py --list
python scripts\combine_consolidations.py --test test-04-measure-verification-tests --batch all
```

### `publish_final_extracted_data.py`

Copies each test's `<PREFIX>_master_output.csv` from its extraction batch into
`results\final_extracted_data\`. Before copying, it rejects stale masters and malformed
CSV rows; afterward it verifies byte-identical hashes. It writes
`_publish_manifest.md` with row, column, hash, source, and timestamp provenance.

```powershell
python scripts\publish_final_extracted_data.py
```

### `normalize_final_extracted_data.py`

A thin launcher for the single active driver at
`results\normalized_data\normalize_final_extracted_data.py`. The canonical driver reads
published master outputs, keeps consolidated round fields, removes extractor-specific
columns, cleans round and legacy `final_` prefixes, joins identity fields from master
identity from roster/roster.json via session slug,
adds method-normalization fields, and writes ten scoring-ready CSVs plus a column ledger,
run report, and Markdown contract. Both commands invoke the same implementation.
The outputs contain method identity normalization only. They contain no correctness
scores, answer-key comparisons, or manual scoring overrides.

```powershell
python results\normalized_data\normalize_final_extracted_data.py
```

## Specialized Schema B Single-Round Utilities

These three scripts operate only on
`results\schema-test-B-tests\extraction\single-round\`. They are a specialized older
workflow, separate from the active two-round Schema B pipeline and Schema B New System.

### `schema_b_make_worklist.py`

Scans usable Schema B session folders, writes `single-round\worklist.csv`, and creates
plain-text extractor slices under `single-round\extraction\_slices\`. The optional
positional argument controls maximum slice size, default 16.

```powershell
python scripts\schema_b_make_worklist.py 16
```

### `schema_b_merge.py`

Merges single-round extraction CSVs with validation and optional adjudication. Clean
rows pass through; disputed rows use adjudication when available; unresolved rows are
marked pending. It rechecks every stored quote against `response.txt` and writes
`final_SCHEMA_B_grid.csv` plus `merge_report.md`.

```powershell
python scripts\schema_b_merge.py
```

### `schema_b_score.py`

Scores the merged specialized Schema B grid against its fixed A-E gold table. It
reports per-session cell accuracy, exact winner-set recognition, D recognition, A
over-acceptance, and regular/control aggregates. Optional positional arguments replace
the input grid and output prefix.

```powershell
python scripts\schema_b_score.py
```

## Generated Per-Test Runners

Every file below is a thin generated wrapper around `corpus_run.run(<key>, runs=4)`.
They make paid API calls and inherit `corpus_run.py` retry, timeout, resume, cleanup,
and default model-exclusion behavior.

| File | Test key | Surface |
|---|---|---|
| `runners/run_schema-a.py` | `schema-a` | Schema A |
| `runners/run_schema-a-new-system.py` | `schema-a-new-system` | Schema A New System |
| `runners/run_schema-b.py` | `schema-b` | Schema B regular |
| `runners/run_schema-b-control.py` | `schema-b-control` | Schema B clarified control |
| `runners/run_schema-b-new-system.py` | `schema-b-new-system` | Schema B New System regular |
| `runners/run_schema-b-new-system-control.py` | `schema-b-new-system-control` | Schema B New System control |
| `runners/run_test-01-kernel.py` | `test-01-kernel` | Test 01 KO7 |
| `runners/run_test-01-fruit.py` | `test-01-fruit` | Test 01 fruit control |
| `runners/run_test-02.py` | `test-02` | Completion, Nat-Lex |
| `runners/run_test-03.py` | `test-03` | Completion, ordinal |
| `runners/run_test-04.py` | `test-04` | Measure verification |
| `runners/run_test-05.py` | `test-05` | Candidate-class reasoning |
| `runners/run_test-06.py` | `test-06` | Branch realism |

Do not hand-edit generated runners. Change `gen_runners.py`, then regenerate them.
