# Method Evidence Registry

Pinned external evidence backing the method-axis scoring policy.

| File | Role |
|------|------|
| `build_method_evidence_matrix.py` | Generator: validates every pinned file exists, hashes it, and checks each Lean anchor is declared in its file |
| `METHOD_EVIDENCE_MATRIX.csv` | The registry: evidence id, surface, method family, TTT2/CeTA status, authority class, repo-relative paths, SHA-256 pins, Lean anchors, scope, and whether negative inference is allowed |
| `METHOD_EVIDENCE_MATRIX.md` | Human-readable rendering of the registry |
| `LEAN_EVIDENCE_AXIOM_AUDIT.txt` | Exported statements of the Lean witness declarations cited by the registry |

Override auditors cite registry `evidence_id` values in their `evidence_anchor` column. Regenerate after any evidence change:

```powershell
python scoring\evidence\build_method_evidence_matrix.py
```

CeTA `MAYBE` rows are search-inconclusive and never support negative inference.
