# Test 04 (Measure Verification) Round 1 - Coded core

## Mandatory Bad-Session Protocol

This section binds the extractor and every sub-agent in this file and supersedes any shorter bad-session sentence below.

- A session is bad only when the assigned raw response is mechanically unusable: the required response file is missing; empty or whitespace-only; an `[ERROR]` or provider-failure placeholder; clearly cut off or truncated mid-sentence, mid-code, mid-list, or before completion; garbled, corrupt, or unreadable; or a flat refusal/tool-spill with no task-relevant analytical content.
- Do not log a session merely because the answer is wrong, weak, terse, non-itemized, poorly reasoned, or omits some requested points while still containing an extractable answer. Code what it says under the round schema. Silence is not mechanical corruption.
- Diagnose using only the raw response file permitted for the current round. Never open a prohibited response, thinking file, prompt, or metadata file to decide whether the session is bad.
- If the session is bad, do not invent values. Apply the round's existing `extraction_notes` vocabulary, leave unavailable response-derived fields blank, and log the session immediately before continuing.
- Ledger: `results\test-04-measure-verification-tests\extraction\bad_sessions.md`
- Check the ledger first. It must contain exactly one data row per `session_slug`; if the slug is already present, do not append a duplicate.
- Append one Markdown table row with exactly four cells and leading/trailing pipes:
  `| <session_slug> | <absolute path to the assigned response file> | <specific mechanical reason, without pipe characters> | <your role and round> |`
- If the response file is missing, the path must still name its expected absolute location. State exactly what failed and, for truncation, where the response cuts off. Use a specific `logged_by` value such as `Extractor R1`.
- Save the ledger in place. Do not delete the session; purging is a separate downstream step.

Single response. Read `response.txt` and nothing else. Transcribe the response's verdicts and citations; never judge whether they are right. Paste the fenced extractor block below.

EXTRACTOR
```
You are the Extractor for Test 04 (Measure Verification) Round 1 (coded core).

HARD CONDITIONS (these bind you AND every sub-agent you dispatch):
(1) NO Python, NO scripts, NO mechanical extraction. You, the AI, READ each assigned session's response.txt IN FULL and extract every value by reading and understanding the text yourself. Never write or run a script, regex, parser, notebook, or program to read, parse, transform, count, or auto-fill any response. Scripted or mechanical extraction is an automatic failure.
(2) You MAY dispatch sub-agents to split the sessions, but ONLY at the SAME power as you: Claude = Opus 4.8 at maximum reasoning effort with the 1,000,000-token context; Codex = GPT-5.6 Sol at Max reasoning (or Ultra reasoning if available); any other model = its maximum reasoning effort and maximum context window. Give every sub-agent the FULL text of these instructions so it knows exactly what to extract and how. Never hand work to a weaker, smaller-context, or under-instructed sub-agent.

Transcribe what the model said; do not judge correctness, do not apply any answer key, no web, no scripts. Read each assigned session's response.txt IN FULL, top to bottom, yourself; never sample, skim, regex, or copy one row into another. Every session gets a fully populated row, every determinable field filled. Mechanical or partial extraction is a failed extraction.

Sessions: every slug in results\test-04-measure-verification-tests\extraction\TEST04_LEDGER.csv. For each, read ONLY response.txt in results\test-04-measure-verification-tests\test-sessions\<slug>\. Never read prompt.txt, thinking.txt, or session.json.
Write only blank cells (keep row order) in: results\test-04-measure-verification-tests\extraction\TEST04_r1.csv
Header: session_slug,measure_sound_yes_no,r_rec_succ_cited,phase_exposure_cited,self_correction_flag,self_contradiction_flag,review_notes,extraction_notes

Fields:
- measure_sound_yes_no: yes | no | unclear — the response's FINAL verdict on whether the proposed (phase, cost) measure is sound. If it revises mid-response, code the final committed position.
- r_rec_succ_cited: yes | no — does the response explicitly cite or analyze the R_rec_succ rule (recDelta b s (delta n) -> app s (recDelta b s n))?
- phase_exposure_cited: yes | no — does the response explicitly identify the wrapper-removal / exposure problem: a step can strip an outer wrapper and EXPOSE a redex so that phase INCREASES at the root (for example a merge/integrate step uncovering recDelta _ _ (delta _))? Generic "phase can go up" without the exposure mechanism = no.
- self_correction_flag: yes | no — the response visibly revises or retracts an earlier claim.
- self_contradiction_flag: yes | no — incompatible claims remain in the final text with no clean resolved reading.
- review_notes: free text, short; ambiguity or follow-up notes; blank if none.
- extraction_notes: "" | refused | truncated | file_missing.

Rules:
- Code the response's own final committed position; a mid-response revision is coded at its final state.
- File-not-read or flat refusal with no analytical content: extraction_notes=refused, leave coded fields blank. Missing/empty response.txt: extraction_notes=file_missing.
- Defective session (response missing, empty, truncated, garbled, or a flat refusal with no analytical content): append it to the bad-sessions ledger results\test-04-measure-verification-tests\extraction\bad_sessions.md (`session_slug | session_path | bad_data_reason | logged_by`); log only mechanically unusable data, never a wrong answer or weak reasoning. Save in place.
```
