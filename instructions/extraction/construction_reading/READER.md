# Construction reading round r7 reader

Read your batch brief, this file, FORMAT.md, and the bound responses named in the brief. Copy quotations and choose menu values. Write zero grades.

| Setting | Rule |
|---|---|
| Workspace | `<workspace>` |
| Assignment | One record per session in the sessions table of your batch brief. |
| Raw outputs | Edit only the JSON paths listed in the brief. Keep extraction CSVs, scored data, normalized data and every other reader's records unchanged. |
| Input boundaries | Read the bound response named in the brief. Exclude policies, ledgers, answer keys, scores, prior extraction rounds, and the sessions of other readers. |
| Exposure | Set `exposure` to `none`, `prior_source` or `prior_grades`; describe each earlier sight of the response. |
| Slots | Record every construction offered, rejected, hypothesized or mentioned, in order of first appearance, in at most six slots. Put further constructions in `constructions_overflow_json`; they carry the ids `c7`, `c8`, ... in list order, and every field that names a slot may name them. |
| Quotes | Copy each quotation as a contiguous substring of the response. Keep formulas, symbol definitions, precedences and rule names as written. A menu value other than `absent`, `none` or `unstated` needs its paired quotation. |
| Session fields | Fill every field of `session` for your test from FORMAT.md. |
| Premises | Give every catalog item a status and a quotation where the status asserts or denies it. |
| Coverage | Give every paragraph block a role and the slot or premise ids it supports. A mathematical or mixed block needs at least one id. |
| Completion | Set `read_complete` true and `record_status` `complete` after the entire response and every construction appear in the record. |
| Tools | Use the commands below. Work alone. |
| Command boundary | Leave preparation, export, publication, scoring, Lean, Lake, Git commits, Git pushes and deletion unchanged. |

| Action from the repository root | Command |
|---|---|
| Validate one record | `python scripts/construction_reading.py validate --test TEST --record "PATH"` |
| Validate every record of the test | `python scripts/construction_reading.py validate --test TEST` |
| Progress | `python scripts/construction_reading.py status --test TEST` |

Report the batch number, completed records, validation result, exposure, and source or format problems in at most six lines. Omit mathematical opinions.
