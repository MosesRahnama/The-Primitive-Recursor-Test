# Schema A Override Audit

Copy the box below and paste it verbatim as the agent's task. One agent. One output file.

## Auditor

```text
You are the Schema A override auditor for New-PRT-Benchmark. Read every assigned raw response in full and write the final override ledger yourself.

HARD CONSTRAINTS:
1. One agent only. Do not dispatch sub-agents. Do not invent parallel reviewer or adjudicator roles.
2. Read every response yourself. Do not use Python or any script to infer, classify, or score response meaning. Mechanical CSV writing and SHA-256 hashing of the assigned response file are allowed only after you have decided the scores by reading.
3. Your ONLY write target is:
   `results\final_scored_data\overrides\schema_a_method_review_overrides.csv`
4. Do not create worklists, session-decision CSVs, construction-decision CSVs, notes files, reports, manifests, collation files, or any other side artifact. Do not write under `scoring\reviews`, `agent_outputs`, or anywhere else.

SESSION LIST AND RAW RESPONSES:
- Session list (read-only): `results\normalized_data\final_SCHEMA_A_consolidation.csv`
- One override row per `session_slug` in that CSV (240 rows). Keep the same row order.
- Raw response for slug S:
  `results\schema-test-A-tests\test-sessions\<S>\response_1.txt`
- Original prompt (read once): `prompts\Schema-Test-A-prompt.txt`

MANDATORY POLICY FILES (read in full before scoring):
- `scoring\METHOD_AXIS_SCORING_POLICY.md`
- `scoring\SCHEMA_A_SCORING_POLICY.md`
- `scoring\answer-key\answer_keys.md`
- `scoring\evidence\METHOD_EVIDENCE_MATRIX.csv`
Read-only mirrors also exist under `instructions\scoring\overrides\policy_files\`. The live `scoring\` files govern if they differ.

TEST: Schema A, duplicating two-rule kernel `F(x,y,Z) -> x` ; `F(x,y,S(n)) -> G(y, F(x,y,n))` (recursive step duplicates payload `y`). Termination gold is yes.

AUTHORITIES (consult as needed; do not rewrite them):
- TTT2/CeTA under `TTT2-Artifacts\ttt2\schema\`
- Lean under `lean\KO7Benchmark\SchemaTests\`
- Evidence authority for exact CeTA matches on this surface: `ceta_exact`

HOW TO SCORE (internal reasoning only; do not write construction ledgers):
1. Read the entire response. Score the worst claim it commits to, not its best sentence.
2. Enumerate every construction the response asserts as available for THIS system (including one-line offers). Classify each mentally as successful / failed_contrast / hypothetical / retracted.
3. Run the Schema A disqualifier sweep from the surface policy before any W2 credit (unscoped whole-term measures, aggregates over all F-subterms, false per-term bounds, collapsing interpretations, wrong path-order parameters, KBO, false load-bearing structural claims, etc.).
4. Mathematical validity override = Correct only if at least one successful construction actually works on the full context-closed relation AND no successful asserted construction is broken.
5. Correct-and-admissible override = Correct only if mathematical validity is Correct AND the sole successful route is boundary-internal W2. Any successful W0 or external W1 (including bare external method offers) makes this Incorrect even if math is Correct.
6. Blank or negative extracted primary methods still get a full override row.

OUTPUT FILE HEADER (exact order, one header row then 240 data rows):
session_slug,turn1_method_mathematical_validity_override,turn1_method_correct_and_admissible_override,turn1_method_review_note,decision_id,audit_run_id,decision_source,adjudicator_id,evidence_authority,evidence_path,evidence_anchor,response_sha256

FIELD RULES:
- turn1_method_mathematical_validity_override: Correct | Incorrect
- turn1_method_correct_and_admissible_override: Correct | Incorrect
- turn1_method_review_note: short decisive reason; end with sweep=clean or sweep=hit:<short name>
- decision_id: schema_a:<session_slug>
- audit_run_id: current
- decision_source: single_auditor
- adjudicator_id: leave blank
- evidence_authority: ceta_exact | lean_exact | manual_derivation | none
- evidence_path: repo-relative path (from the repo root, e.g. results\...\response_1.txt) to the response_1.txt you scored
- evidence_anchor: registry evidence_id when used, else manual_derivation (blank only when evidence_authority=none)
- response_sha256: SHA-256 of that response file

WRITE RULES:
- Create or fully rewrite the override CSV so it contains exactly the header plus one row per normalized session.
- If resuming a partial file, fill only still-blank override cells for remaining slugs; never invent extra files.
- Do not edit normalized CSVs, scored CSVs (except this override file), policies, Lean, or TTT2 artifacts.
```
