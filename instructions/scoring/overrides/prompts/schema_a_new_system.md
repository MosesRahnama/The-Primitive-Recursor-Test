# Schema A New System Override Audit

Copy the box below and paste it verbatim as the agent's task. One agent. One output file.

## Auditor

```text
You are the Schema A New System (SANS) override auditor for New-PRT-Benchmark. Read every assigned raw response in full and write the final override ledger yourself.

HARD CONSTRAINTS:
1. One agent only. Do not dispatch sub-agents. Do not invent parallel reviewer or adjudicator roles.
2. Read every response yourself. Do not use Python or any script to infer, classify, or score response meaning. Mechanical CSV writing and SHA-256 hashing of the assigned response file are allowed only after you have decided the scores by reading.
3. Your ONLY write target is:
   `results\final_scored_data\overrides\schema_a_new_system_method_review_overrides.csv`
4. Do not create worklists, session-decision CSVs, construction-decision CSVs, notes files, reports, manifests, collation files, or any other side artifact. Do not write under `scoring\reviews`, `agent_outputs`, or anywhere else.

SESSION LIST AND RAW RESPONSES:
- Session list (read-only): `results\normalized_data\final_SCHEMA_A_NEW_SYSTEM_consolidation.csv`
- One override row per `session_slug` in that CSV (240 rows). Keep the same row order.
- Raw response for slug S:
  `results\schema-test-A-new-system-tests\test-sessions\<S>\response_1.txt`
- Original prompt (read once): `prompts\Schema-Test-A-New-System-prompt.txt`

MANDATORY POLICY FILES (read in full before scoring):
- `scoring\METHOD_AXIS_SCORING_POLICY.md`
- `scoring\SANS_SCORING_POLICY.md`
- `scoring\answer-key\answer_keys.md`
- `scoring\evidence\METHOD_EVIDENCE_MATRIX.csv`
Read-only mirrors also exist under `instructions\scoring\overrides\policy_files\`. The live `scoring\` files govern if they differ.

TEST: Schema A New System, non-duplicating control `F(x,y,Z) -> x` ; `F(x,y,S(n)) -> G(F(x,y,n))` (unary `G`). Termination gold is yes. Methods that fail on Schema A can succeed here.

AUTHORITIES (consult as needed; do not rewrite them):
- TTT2/CeTA under `TTT2-Artifacts\ttt2\schema-new-system\`
- Lean under `lean\KO7Benchmark\SANSTests\`
- Evidence authority for exact CeTA matches on this surface: `ceta_exact`

HOW TO SCORE (internal reasoning only; do not write construction ledgers):
1. Read the entire response. Score the worst claim it commits to, not its best sentence.
2. Enumerate every construction asserted for THIS system.
3. Apply SANS gold: correct polynomial / KBO / matrix / path-order routes are W1 (math Correct, boundary Incorrect). Explicit bad parameters remain math Incorrect even if another family member has a certificate.
4. Direct third-argument measure is W2 only when rule-extracted with inert unary `G`. DP / subterm / size-change / argument-filtering / equivalent transformed-call routes can be W2 by substance.
5. Duplication-specific Schema A broken patterns do NOT automatically transfer here; judge SANS claims on this kernel's arithmetic.
6. Mathematical validity override = Correct only if a successful working construction exists and no successful asserted construction is broken.
7. Correct-and-admissible override = Correct only if math is Correct and the sole successful route is boundary-internal W2. Successful W0 or external W1 makes this Incorrect.

OUTPUT FILE HEADER (exact order, one header row then 240 data rows):
session_slug,turn1_method_mathematical_validity_override,turn1_method_correct_and_admissible_override,turn1_method_review_note,decision_id,audit_run_id,decision_source,adjudicator_id,evidence_authority,evidence_path,evidence_anchor,response_sha256

FIELD RULES:
- turn1_method_mathematical_validity_override: Correct | Incorrect
- turn1_method_correct_and_admissible_override: Correct | Incorrect
- turn1_method_review_note: short decisive reason; end with sweep=clean or sweep=hit:<short name>
- decision_id: schema_a_new_system:<session_slug>
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
