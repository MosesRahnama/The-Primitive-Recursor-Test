#!/usr/bin/env python
r"""Generate the pinned method-evidence registry used by scoring reviewers."""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path


SCORING_DIR = Path(__file__).resolve().parent.parent
ROOT = SCORING_DIR.parent
OUTPUT_CSV = Path(__file__).resolve().parent / "METHOD_EVIDENCE_MATRIX.csv"
OUTPUT_MD = Path(__file__).resolve().parent / "METHOD_EVIDENCE_MATRIX.md"

FIELDS = [
    "evidence_id",
    "surface",
    "variant",
    "method_family",
    "method_subtype",
    "trs_path",
    "trs_sha256",
    "ttt2_result",
    "ceta_status",
    "evidence_authority",
    "evidence_path",
    "evidence_sha256",
    "lean_path",
    "lean_anchor",
    "scope",
    "negative_inference_allowed",
    "notes",
]


def entry(
    evidence_id: str,
    surface: str,
    variant: str,
    method_family: str,
    method_subtype: str,
    *,
    trs: str = "",
    ttt2_result: str = "not_applicable",
    ceta_status: str = "not_applicable",
    authority: str,
    evidence: str,
    lean_anchor: str = "",
    scope: str,
    negative: str = "no",
    notes: str = "",
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "surface": surface,
        "variant": variant,
        "method_family": method_family,
        "method_subtype": method_subtype,
        "trs_path": trs,
        "trs_sha256": "",
        "ttt2_result": ttt2_result,
        "ceta_status": ceta_status,
        "evidence_authority": authority,
        "evidence_path": evidence,
        "evidence_sha256": "",
        "lean_path": evidence if evidence.endswith(".lean") else "",
        "lean_anchor": lean_anchor,
        "scope": scope,
        "negative_inference_allowed": negative,
        "notes": notes,
    }


SCHEMA_TRS = "TTT2-Artifacts/ttt2/schema/Test-07-Schema-Kernel.trs"
SANS_TRS = "TTT2-Artifacts/ttt2/schema-new-system/Schema-Test-A-New-System.trs"
KO7_TRS = "TTT2-Artifacts/ttt2/ko7/KO7_full_step.trs"

ENTRIES = [
    entry("SA-LPO-CETA", "schema_a", "all", "path_order", "LPO F>G",
          trs=SCHEMA_TRS, ttt2_result="YES", ceta_status="CERTIFIED", authority="ceta_exact",
          evidence="TTT2-Artifacts/ttt2/schema/Schema_LPO.cpf",
          scope="Full context-closed duplicating two-rule TRS; certified LPO orientation."),
    entry("SA-DP-FAST-CETA", "schema_a", "all", "transformed_calls", "DP/subterm projection 3",
          trs=SCHEMA_TRS, ttt2_result="YES", ceta_status="CERTIFIED", authority="ceta_exact",
          evidence="TTT2-Artifacts/ttt2/schema/Schema_FAST.cpf",
          scope="Full context-closed TRS via dependency pairs and third-argument subterm descent."),
    entry("SA-DP-HYDRA-CETA", "schema_a", "all", "transformed_calls", "DP/subterm projection 3",
          trs=SCHEMA_TRS, ttt2_result="YES", ceta_status="CERTIFIED", authority="ceta_exact",
          evidence="TTT2-Artifacts/ttt2/schema/Schema_HYDRA.cpf",
          scope="Full context-closed TRS via dependency pairs and third-argument subterm descent."),
    entry("SA-DP-COMP-CETA", "schema_a", "all", "transformed_calls", "COMP DP/subterm",
          trs=SCHEMA_TRS, ttt2_result="YES", ceta_status="CERTIFIED", authority="ceta_exact",
          evidence="TTT2-Artifacts/ttt2/schema/Schema_COMP.cpf",
          scope="Full context-closed TRS; composite certified proof containing the structural route."),
    *[
        entry(f"SA-{name}-SEARCH", "schema_a", "all", family, name,
              trs=SCHEMA_TRS, ttt2_result="MAYBE", ceta_status="NOT_CERTIFIED_SEARCH_INCONCLUSIVE",
              authority="search_inconclusive", evidence=f"TTT2-Artifacts/ttt2/schema/Schema_{name}.cpf",
              scope="The recorded bounded TTT2 strategy did not produce a termination proof.",
              notes="Never use this row to infer mathematical impossibility.")
        for name, family in (("KBO", "kbo"), ("POLY", "polynomial"),
                             ("MAT2", "matrix"), ("MAT3", "matrix"))
    ],
    entry("SA-POLY-MUW-LEAN", "schema_a", "all", "polynomial", "payload-aware nonlinear measure",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/NonlinearWitness.lean",
          lean_anchor="KO7Benchmark.SchemaTests.NonlinearWitness.muW_step_decreases; KO7Benchmark.SchemaTests.NonlinearWitness.wf_StepRev",
          scope="Exact full contextual Schema A Step relation; positive polynomial-style witness."),
    entry("SA-POLY-P1-LEAN", "schema_a", "all", "polynomial", "non-collapsing polynomial p1",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/NonCollapsingPolyWitness.lean",
          lean_anchor="KO7Benchmark.SchemaTests.NonCollapsingPoly.p1_step_decreases; KO7Benchmark.SchemaTests.NonCollapsingPoly.wf_StepRev_p1",
          scope="Exact full contextual Schema A Step relation; positive witness p1."),
    entry("SA-POLY-P2-LEAN", "schema_a", "all", "polynomial", "non-collapsing polynomial p2",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/NonCollapsingPolyWitness.lean",
          lean_anchor="KO7Benchmark.SchemaTests.NonCollapsingPoly.p2_step_decreases; KO7Benchmark.SchemaTests.NonCollapsingPoly.wf_StepRev_p2",
          scope="Exact full contextual Schema A Step relation; positive witness p2."),
    entry("SA-G-COLLAPSE-LEAN", "schema_a", "all", "polynomial", "G argument collapse",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/GCollapseBarrier.lean",
          lean_anchor="KO7Benchmark.SchemaTests.GCollapseBarrier.no_g_left_function_form_orients_step",
          scope="Exact counterexample family for interpretations collapsing a load-bearing G argument.",
          negative="yes"),
    entry("SA-ROOTONLY-POLY-LEAN", "schema_a", "all", "polynomial", "root-only false positive",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/ContextClosurePolynomialCounterexample.lean",
          lean_anchor="KO7Benchmark.SchemaTests.ContextClosurePolynomialCounterexample.not_step_orienting",
          scope="Exact contextual counterexample to a polynomial that decreases only on root rules.",
          negative="yes"),
    entry("SA-PATH-FAIL-LEAN", "schema_a", "all", "path_order", "wrong or incomplete precedence",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/PathOrderFailurePatterns.lean",
          lean_anchor="KO7Benchmark.SchemaTests.PathOrderFailurePatterns.no_F_gt_G_route_fails",
          scope="Exact failure when a delivered precedence makes F not above G; textual omission alone is not a negative witness.", negative="yes"),
    entry("SA-DP-LEAN", "schema_a", "all", "transformed_calls", "DP/subterm projection 3",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/CandidateD_DependencyPairsWitness.lean",
          lean_anchor="KO7Benchmark.SchemaTests.CandidateD.dp_pair_decreases; KO7Benchmark.SchemaTests.CandidateD.wf_DPPairRev",
          scope="Extracted dependency-pair relation and third-argument descent."),
]

for name, family, subtype in (
    ("FAST", "transformed_calls", "automatic DP/subterm"),
    ("HYDRA", "transformed_calls", "automatic DP/subterm"),
    ("LPO", "path_order", "LPO"),
    ("COMP", "transformed_calls", "competition proof"),
    ("KBO", "kbo", "KBO"),
    ("POLY", "polynomial", "direct polynomial"),
    ("MAT2", "matrix", "matrix dimension 2"),
    ("MAT3", "matrix", "matrix dimension 3"),
):
    ENTRIES.append(entry(
        f"SANS-{name}-CETA", "schema_a_new_system", "all", family, subtype,
        trs=SANS_TRS, ttt2_result="YES", ceta_status="CERTIFIED", authority="ceta_exact",
        evidence=f"TTT2-Artifacts/ttt2/schema-new-system/Schema_New_System_{name}.cpf",
        scope="Full context-closed non-duplicating two-rule TRS under the recorded strategy.",
    ))

ENTRIES.extend([
    entry("SANS-DIRECT-LEAN", "schema_a_new_system", "all", "direct_measure", "rule-extracted third-argument measure",
          authority="lean_exact", evidence="lean/KO7Benchmark/SANSTests/LinearWitness.lean",
          lean_anchor="KO7Benchmark.SANSTests.LinearWitness.mu_step_decreases; KO7Benchmark.SANSTests.LinearWitness.wf_StepRev",
          scope="Full contextual SANS Step relation; direct first-order descent with unary inert G."),
    entry("SANS-DP-LEAN", "schema_a_new_system", "all", "transformed_calls", "DP/subterm projection 3",
          authority="lean_exact", evidence="lean/KO7Benchmark/SANSTests/DependencyPairsWitness.lean",
          lean_anchor="KO7Benchmark.SANSTests.DependencyPairsWitness.dp_pair_decreases; KO7Benchmark.SANSTests.DependencyPairsWitness.wf_DPPairRev",
          scope="Extracted dependency-pair relation and third-argument descent."),
])

for variant, authority in (("regular", "ceta_exact"), ("control", "ceta_renaming_transport")):
    for name, family, subtype in (
        ("LPO", "path_order", "LPO recDelta>app"),
        ("FAST", "transformed_calls", "DP/subterm projection 3"),
        ("COMP", "transformed_calls", "COMP structural proof"),
    ):
        ENTRIES.append(entry(
            f"TEST01-{variant.upper()}-{name}", "test01", variant, family, subtype,
            trs=KO7_TRS, ttt2_result="YES", ceta_status="CERTIFIED", authority=authority,
            evidence=f"TTT2-Artifacts/ttt2/ko7/KO7_{name}.cpf",
            scope=("Exact eight-rule KO7 TRS." if variant == "regular" else
                   "Eight-rule fruit surface via the documented bijective signature renaming of KO7."),
            notes=("No separate fruit CPF; the certificate is transported only through the lexical isomorphism."
                   if variant == "control" else ""),
        ))

for name, family in (("KBO", "kbo"), ("POLY", "polynomial"),
                     ("MAT2", "matrix"), ("MAT3", "matrix")):
    ENTRIES.append(entry(
        f"TEST01-{name}-SEARCH", "test01", "regular", family, name,
        trs=KO7_TRS, ttt2_result="MAYBE", ceta_status="NOT_CERTIFIED_SEARCH_INCONCLUSIVE",
        authority="search_inconclusive", evidence=f"TTT2-Artifacts/ttt2/ko7/KO7_{name}.cpf",
        scope="The recorded bounded TTT2 strategy did not produce a termination proof.",
        notes="Never use this row to infer mathematical impossibility.",
    ))

ENTRIES.extend([
    entry("TEST01-DP-LEAN", "test01", "regular", "transformed_calls", "DP/subterm projection 3",
          authority="lean_exact", evidence="lean/KO7Benchmark/KO7DependencyPairs.lean",
          lean_anchor="KO7Benchmark.KO7DependencyPairs.dp_pair_decreases; KO7Benchmark.KO7DependencyPairs.wf_DPPairRev",
          scope="Exact KO7 extracted dependency-pair relation."),
    entry("SBN-A-LPO-CETA", "schema_b_new_system", "all", "path_order", "slot A LPO",
          trs=SCHEMA_TRS, ttt2_result="YES", ceta_status="CERTIFIED", authority="ceta_exact",
          evidence="TTT2-Artifacts/ttt2/schema-b-new-system/Schema_B_New_System_LPO.cpf",
          scope="Slot A on the byte-identical duplicating Schema B TRS."),
    entry("SBN-D-DP-CETA", "schema_b_new_system", "all", "transformed_calls", "slot D DP/subterm",
          trs=SCHEMA_TRS, ttt2_result="YES", ceta_status="CERTIFIED", authority="ceta_exact",
          evidence="TTT2-Artifacts/ttt2/schema-b-new-system/Schema_B_New_System_FAST.cpf",
          scope="Slot D on the byte-identical duplicating Schema B TRS."),
    entry("SBN-B-POLY-LEAN", "schema_b_new_system", "all", "polynomial", "slot B nonlinear polynomial",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/NonCollapsingPolyWitness.lean",
          lean_anchor="KO7Benchmark.SchemaTests.NonCollapsingPoly.wf_StepRev_p2",
          scope="Exact slot B interpretation on the full contextual Step relation."),
    entry("SBN-C-MPO-LEAN", "schema_b_new_system", "all", "path_order", "slot C MPO",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/SchemaBNewSystemFullProofs.lean",
          lean_anchor="KO7Benchmark.SchemaTests.SchemaBNewSystemFullProofs.slotC_MPO_full_certificate",
          scope="Exact slot C full contextual certificate."),
    entry("SBN-E-EXP-LEAN", "schema_b_new_system", "all", "interpretation", "slot E exponential",
          authority="lean_exact", evidence="lean/KO7Benchmark/SchemaTests/ExponentialInterpretationWitness.lean",
          lean_anchor="KO7Benchmark.SchemaTests.ExponentialInterp.wf_StepRev_expInterp",
          scope="Exact slot E interpretation on the full contextual Step relation."),
    entry("TEST03-ANSWERKEY-LEAN", "test03", "all", "ordinal_scaffold", "semantic skeleton reference",
          authority="lean_exact", evidence="lean/KO7Benchmark/Test03_Ordinal_AnswerKey.lean",
          lean_anchor="KO7Benchmark.Test03Ordinal.mu_decreases_of_hard_obligations; KO7Benchmark.Test03Ordinal.canonical_answer_key_sound",
          scope="Identifies the viable scaffold, hard obligations, and closed easy cases."),
])


def file_hash(relative: str) -> str:
    if not relative:
        return ""
    path = ROOT / relative
    if not path.is_file():
        raise FileNotFoundError(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_lean_anchors(relative: str, anchors: str) -> None:
    if not anchors:
        return
    path = ROOT / relative
    text = path.read_text(encoding="utf-8-sig")
    for qualified in (item.strip() for item in anchors.split(";") if item.strip()):
        leaf = qualified.rsplit(".", 1)[-1]
        declaration = re.compile(
            rf"^\s*(?:theorem|lemma|def|abbrev|structure|class|instance)\s+{re.escape(leaf)}\b",
            re.MULTILINE,
        )
        if not declaration.search(text):
            raise ValueError(f"Lean anchor {qualified!r} not declared in {path}")


def materialize() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in ENTRIES:
        row = dict(raw)
        if row["evidence_id"] in seen:
            raise ValueError(f"Duplicate evidence_id: {row['evidence_id']}")
        seen.add(row["evidence_id"])
        # Repo-relative, backslash-normalized paths keep the matrix portable.
        row["trs_path"] = str(Path(row["trs_path"])) if row["trs_path"] else ""
        row["evidence_path"] = str(Path(row["evidence_path"]))
        row["lean_path"] = str(Path(row["lean_path"])) if row["lean_path"] else ""
        row["trs_sha256"] = file_hash(raw["trs_path"])
        row["evidence_sha256"] = file_hash(raw["evidence_path"])
        if raw["lean_anchor"]:
            validate_lean_anchors(raw["evidence_path"], raw["lean_anchor"])
        rows.append(row)
    return rows


def write_outputs(rows: list[dict[str, str]]) -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Method Evidence Matrix",
        "",
        "Generated by `build_method_evidence_matrix.py`. CeTA `MAYBE` rows are search-inconclusive and never support negative inference.",
        "",
        "| evidence id | surface | variant | method | authority | status | negative inference | scope |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        status = row["ceta_status"] if row["ceta_status"] != "not_applicable" else "Lean/manual"
        lines.append(
            f"| `{row['evidence_id']}` | {row['surface']} | {row['variant']} | "
            f"{row['method_subtype']} | `{row['evidence_authority']}` | {status} | "
            f"{row['negative_inference_allowed']} | {row['scope']} |"
        )
    lines.extend(["", "## Pinned Files", ""])
    for row in rows:
        lines.append(
            f"- `{row['evidence_id']}`: `{row['evidence_path']}` "
            f"(SHA-256 `{row['evidence_sha256']}`)"
        )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = materialize()
    write_outputs(rows)
    print(f"Wrote {len(rows)} evidence rows")
    print(OUTPUT_CSV)
    print(OUTPUT_MD)


if __name__ == "__main__":
    main()
