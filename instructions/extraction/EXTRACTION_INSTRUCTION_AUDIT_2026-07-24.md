# Extraction-Instruction Audit — seven surfaces, 33 files, full read (2026-07-24)

**Scope read in full:** every file in `schema-test-A-tests`, `schema-test-A-new-system-tests`, `schema-a-nonce-arm-tests`, `test-01-kernel-tests`, `test-01-context-arm-tests`, `test-01-tools-arm-tests`, `test-03-completion-tests-ordinal` (7 READMEs + 26 round files).
**Cross-checked against:** the session trees on disk, `scripts\r5_construction_gate.py` SURFACES registry, `scripts\nonce_normalize.py`, and `WINDOW_EXPERIMENTS_DESIGN_2026-07-24.md`.

## State line

```
PARENT SURFACES (SA / SANS / T01 / T03):  sound; one cosmetic round-4 inconsistency, no data impact
ARM-B context arm:                        CLEAN — byte-identical to parent T01 R4 + one banner line
ARM-A tools arm:                          RUNNABLE but missing the one rule the arm's own question depends on
ARM-C nonce arm:                          ** CANNOT RUN AS WRITTEN ** — hard blocker + vocabulary contradiction
```

The three arms have **0 extraction CSVs** so far (40 / 40 / 80 session dirs exist). Every defect below is still cheap to fix; none has contaminated data.

---

## BLOCKER — ARM-C nonce arm reads a file that does not exist

| | |
|---|---|
| **Instruction** | `SCHEMA_A_NONCE_ROUND5_PROMPTS.md`, all three boxes: *"read ONLY **response_1.txt**"* |
| **On disk** | `results\schema-a-nonce-arm-tests\test-sessions\<slug>\` contains only `prompt.txt`, **`response.txt`**, `session.json` |
| **Gate registry** | `SCHEMA_A_NONCE` → `resp_file="response.txt"` — **the gate is correct** |
| **Design doc** | contradicts itself: line 80 registers the nonce gate as `response_1.txt`; line 96 says `response.txt` (single-turn convention) |

**Consequence if dispatched as written:** both extractors hit a missing file, and the box's own rule fires — *"Missing/empty response_1.txt: leave fields blank, extraction_notes=file_missing; bad sessions go to the ledger."* Outcome: 40/40 blank rows, 40 spurious bad-session ledger entries, zero data. This is the arm that answers a reviewer W3/Q3 (contamination), one of the AC's four experimental issues.

**Root cause:** the arm was copied from Schema A (a two-turn surface, hence `response_1.txt`) rather than from Test 01 (single-response, already fixed under rollout-log Entry 3, calibration action 1). The tools and context arms were copied from T01 and are correct.

**Fix:** replace `response_1.txt` → `response.txt` in all three boxes of `SCHEMA_A_NONCE_ROUND5_PROMPTS.md` (3 occurrences in the Sessions lines, plus the payload/rules mentions: quote-substring rule and the missing-file rule). Same substitution in `ROUND1` and `ROUND3`. Reconcile design-doc line 80 to line 96.

---

## HIGH — ARM-C vocabulary contradiction (would corrupt the arm even after the blocker is fixed)

The nonce bijection appears **exactly once in the file, on line 1, in the operator-facing ARM NOTE that is explicitly not pasted to agents**:

> FROZEN BIJECTION: F→Velk, G→Tarn, S→Oru, Z→Mek … **Transcribe constructions in the SESSION'S OWN vocabulary (Velk/Tarn/Oru/Mek); do NOT translate.** … **no agent applies the map by hand.**

Every one of the three agent boxes says the opposite:

> SIGNATURE (Schema A; **use EXACTLY these canonical symbol and argument names in payloads**): F(x, y, n) ternary; G(a, b) binary; S(n) unary; Z constant.

and the payload grammar's keys are literally `{"map": {"F": …, "G": …, "S": …, "Z": …}}`. **Verified: zero occurrences of Velk/Tarn/Oru/Mek inside any agent box.**

Contrast Test 01, which handles the identical problem correctly: its `FRUIT CANONICALIZATION` table sits **inside** each agent box (lines 42–44, within the fence at 26–113) together with a `vocabulary_used` column recording which vocabulary the session used.

**Two failure modes, both live:**

1. *Agents obey their box* → they hand-translate Velk→F etc., which is precisely what the ARM NOTE forbids and what `nonce_normalize.py` exists to do mechanically. The design guarantee "no agent applies the map by hand" becomes false. Tell-tale: `nonce_normalize.py` reports **0 cells normalized**.
2. *The operator pastes the ARM NOTE alongside the box* → E01 and E02 may split (one nonce, one canonical), and since the gate compares canonicalized payloads for **exact equality**, every construction-bearing row mismatches → gate agreement near 0%.

**Aggravating:** the nonce arm is registered with `HDR_CONSTR` (no `vocabulary_used` column), unlike tools/context which use `HDR_CONSTR_VOCAB`. So there is **no per-row record of which vocabulary was written** — the one mechanical way to detect either failure mode is absent.

**Fix (choose the T01 pattern, it is already proven):** put the bijection table **inside** all three boxes, state the direction explicitly ("transcribe payload symbols in the session's own nonce vocabulary; do not translate"), and add `vocabulary_used` to the header + the gate's header constant. Then `nonce_normalize.py` does the inversion, as designed.

---

## HIGH — ARM-A tools arm has no tool-attribution rule inside any agent box

All 17 occurrences of "tool" in `TEST01_TOOLS_ROUND4_PROMPTS.md` are either the line-1 ARM NOTE or the literal string `TEST01_TOOLS` in paths. **Nothing inside any agent box mentions tools at all.**

The ARM NOTE (operator-only) says: *"Responses may contain tool-call traces and quoted tool output; they are part of the response text and all quote rules apply to them unchanged."* Read literally, that permits an extractor to transcribe a construction that appears **only in tool output** as the model's own asserted construction.

That is the single rule this arm's question turns on. ARM-A exists to measure whether tool access changes **the model's** witness construction; a reviewer's score-change criterion (≥10× the isolation rule-derived rate) is computed from exactly this number. If a model invokes a termination tool and the tool emits "dependency pairs, subterm criterion, project argument 3," and the extractor records that as the model's asserted `dp_projection{argument:3}`, the arm measures the tool and the reported lift is an artifact.

**Fix:** add one paragraph to all three boxes, e.g. — *a construction is transcribed as `asserted` only when the response's own prose commits to it; content appearing solely inside a tool-call block or quoted tool output is transcribed with stance `mentioned` and a `"source":"tool_output"` marker in the payload.* Also add a `tool_invoked` telemetry column so the pre-registered "which tools were actually invoked and how often" sentence (design doc line 31) is derivable.

---

## MEDIUM — ARM-C vestigial and misfiring rounds

| Round | Problem |
|---|---|
| `ROUND2` | Turn-2 round on a **turn-1-only** surface (ARM NOTE: "Turn-2 fields do not exist on this surface"); reads `response_2.txt`, which does not exist. |
| `ROUND4` | Same: turn-2 peripheral round, inapplicable. |
| `ROUND1` | Refusal test is *"File-not-read (**no mention of F, G, Z, S**, or the two rules): extraction_notes=refused."* On the nonce arm a correct response mentions **Velk/Tarn/Oru/Mek** — so genuine analytical responses would be marked `refused` by construction. |

**Fix:** mark ROUND2/ROUND4 NOT APPLICABLE at the top of each file (do not delete — the parent-surface lineage is the provenance record); update ROUND1's refusal token list to the nonce symbols.

---

## LOW — pre-existing round-4 filename inconsistency (SA / SANS / nonce)

`*_ROUND4_PROMPTS.md` says *"read ONLY **response.txt**"* in its Sessions line, but its Rules say *"literal substring of **response_2.txt**"* and *"Missing/empty **response_2.txt**"*. R4 is the turn-2 peripheral round, so `response_2.txt` is the intended file.

**Impact: none observed.** On 25 sampled Schema A sessions `response.txt` and `response_2.txt` are byte-identical, and `SCHEMA_A_r4.csv` shows 240/240 rows filled with zero `extraction_notes`. Fix for reproducibility, not for data integrity.

---

## Clean

- **`test-01-context-arm-tests`** — diffs against parent T01 R4 to exactly one added line (the ARM NOTE). Correct `response.txt`, correct `HDR_CONSTR_VOCAB`, gate registered. Nothing to do.
- **Parent surfaces SA / SANS / T01 / T03** — rounds 1–3 are coherent single-extractor legacy rounds; R5/R4/R3 carry the v4.1 contract (precision rules, worked examples, self-check) uniformly across all three boxes; T01's fruit canonicalization and T03's stance enums are correctly placed inside the boxes.

---

## Fix order (all are minutes of work; the arms have not run)

1. **ARM-C `response_1.txt` → `response.txt`** in ROUND5 (×3 boxes), ROUND1, ROUND3. *Blocker.*
2. **ARM-C bijection into the boxes + `vocabulary_used` column** (copy the T01 fruit pattern verbatim; add the column to `HDR_CONSTR` for this surface or reuse `HDR_CONSTR_VOCAB`).
3. **ARM-A tool-attribution paragraph + `tool_invoked` column** in all three boxes.
4. **ARM-C ROUND2/ROUND4 marked NOT APPLICABLE; ROUND1 refusal tokens** updated to nonce symbols.
5. **Round-4 `response.txt`/`response_2.txt`** reconciled on SA/SANS/nonce.
6. Reconcile `WINDOW_EXPERIMENTS_DESIGN_2026-07-24.md` line 80 against line 96.
