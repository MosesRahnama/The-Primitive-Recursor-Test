# Schema A Round 3 — Turn 1 Peripheral (per-flag quotes) — batch (126 sessions)

## Mandatory Bad-Session Protocol

This section binds the extractor and every sub-agent in this file and supersedes any shorter bad-session sentence below.

- A session is bad only when the assigned raw response is mechanically unusable: the required response file is missing; empty or whitespace-only; an `[ERROR]` or provider-failure placeholder; clearly cut off or truncated mid-sentence, mid-code, mid-list, or before completion; garbled, corrupt, or unreadable; or a flat refusal/tool-spill with no task-relevant analytical content.
- Do not log a session merely because the answer is wrong, weak, terse, non-itemized, poorly reasoned, or omits some requested points while still containing an extractable answer. Code what it says under the round schema. Silence is not mechanical corruption.
- Diagnose using only the raw response file permitted for the current round. Never open a prohibited response, thinking file, prompt, or metadata file to decide whether the session is bad.
- If the session is bad, do not invent values. Apply the round's existing `extraction_notes` vocabulary, leave unavailable response-derived fields blank, and log the session immediately before continuing.
- Ledger: `results\schema-test-A-tests\extraction\bad_sessions.md`
- Check the ledger first. It must contain exactly one data row per `session_slug`; if the slug is already present, do not append a duplicate.
- Append one Markdown table row with exactly four cells and leading/trailing pipes:
  `| <session_slug> | <absolute path to the assigned response file> | <specific mechanical reason, without pipe characters> | <your role and round> |`
- If the response file is missing, the path must still name its expected absolute location. State exactly what failed and, for truncation, where the response cuts off. Use a specific `logged_by` value such as `Extractor R3`.
- Save the ledger in place. Do not delete the session; purging is a separate downstream step.

Paste one fenced block per agent box. Single extractor only. Each evidence quote is filled ONLY when its paired flag fires, else blank. No inference from silence: a flag is no unless the response explicitly states it.

EXTRACTOR
```
You are the Extractor for Schema A Round 3 (Turn 1 peripheral). 

HARD CONDITIONS (these bind you AND every sub-agent you dispatch):
(1) NO Python, NO scripts, NO mechanical extraction. You, the AI, READ each assigned session's response file(s) IN FULL and extract every value by reading and understanding the text yourself. Never write or run a script, regex, parser, notebook, or program to read, parse, transform, count, or auto-fill any response. Scripted or mechanical extraction is an automatic failure.
(2) You MAY dispatch sub-agents to split the sessions, but ONLY at the SAME power as you: Claude = Opus 4.8 at maximum reasoning effort with the 1,000,000-token context; Codex = GPT-5.6 Sol at Max reasoning (or Ultra reasoning if available); any other model = its maximum reasoning effort and maximum context window. Give every sub-agent the FULL text of these instructions so it knows exactly what to extract and how. Never hand work to a weaker, smaller-context, or under-instructed sub-agent.

Transcribe what the model said; no judging, no web, no scripts. Read each assigned session's response file IN FULL, top to bottom, yourself; never sample, skim, regex, or copy one row into another. Every session gets a fully populated row, every determinable field filled. Mechanical or partial extraction is a failed extraction.

Sessions: every slug in results\schema-test-A-tests\extraction\SCHEMA_A_LEDGER.csv. For each, read ONLY response_1.txt in results\schema-test-A-tests\test-sessions\<slug>\. Never read thinking.txt or session.json.
Write only blank cells (keep row order) in: results\schema-test-A-tests\extraction\SCHEMA_A_r3.csv
Header: session_slug,turn1_flag_w2_method_named,turn1_w2_quote,turn1_flag_duplication_noted,turn1_duplication_quote,turn1_flag_subterm_descent_noted,turn1_subterm_quote,turn1_negative_verdict_subtype,turn1_negative_subtype_quote,extraction_notes

Flags (yes | no; no unless explicit; when yes, put the supporting sentence in the paired quote):
- turn1_flag_w2_method_named: response explicitly names dependency pairs / subterm criterion / argument filtering / size-change / counter-projection / transformed calls / DP method. ("structural recursion/induction" alone is NOT this.) -> turn1_w2_quote
- turn1_flag_duplication_noted: response explicitly notes the step payload y is duplicated / copied / on both sides of the recursive step. -> turn1_duplication_quote
- turn1_flag_subterm_descent_noted: response explicitly says the third argument strictly decreases / n is a proper subterm of S(n) / one S is stripped each step. -> turn1_subterm_quote
- turn1_negative_verdict_subtype: cannot_establish (SN not provable from the rules alone / needs extra assumptions, not asserting non-termination) | claims_nontermination (explicitly non-terminating or a concrete loop) | none (verdict positive or unclear) | unclear (negative but can't tell). When not none -> turn1_negative_subtype_quote.
- extraction_notes: "" | refused | truncated | file_missing.

Rules:
- Every non-blank quote is a literal substring of response_1.txt, <=300 chars, one span. Fill a quote only when its flag fires (and the subtype quote only when subtype is not none). Never quote a trailing agent postamble.
- Missing/empty response_1.txt: leave fields blank, extraction_notes=file_missing. Defective session (response missing, empty, truncated, garbled, or a flat refusal with no analytical content): append it to the bad-sessions ledger results\schema-test-A-tests\extraction\bad_sessions.md (`session_slug | session_path | bad_data_reason | logged_by`); log only mechanically unusable data, never a wrong answer or weak reasoning. Save in place.
```
