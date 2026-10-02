"""Validate and score one source-bound PRT extraction without a consensus vote."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import __version__
from .checkers import checker_from_contract
from .common import canonical_sha256, read_json, sha256_file
from .compiler import compile_record
from .config import InstanceContract
from .deploy_v3 import verify_deployed_run
from .prt_policy import POLICY_VERSION, _fruit_refutation_applies
from .prt_readings import AXES, _check_reading
from .prt_source_refutations import source_refutations

PRT_INSTANCES = {"schema-a", "schema-a-new", "test01-ko7"}


def _undecided(reason: str) -> dict[str, Any]:
    return {"policy_version": POLICY_VERSION, **dict.fromkeys(AXES, "Unknown"), "reasons": [reason]}


def score_single_run(run_dir: Path, *, artifact_root: Path) -> dict[str, Any]:
    """Require a single-mode deployment, exact source coverage and one extractor identity."""
    verified = verify_deployed_run(run_dir)
    if not verified["valid"]:
        raise ValueError(f"invalid single-extractor deployment: {verified['issues']}")
    manifest = read_json(run_dir / "RUN_MANIFEST.json")
    if (manifest.get("extraction_mode") != "single"
            or [entry["pass_number"] for entry in manifest["passes"]] != [1]):
        raise ValueError("score-single requires extraction_mode=single and passes=[1]; do not reuse a paired run")
    if (run_dir / "TIEBREAK_MANIFEST.json").exists():
        raise ValueError("single extraction cannot contain a tiebreak manifest")
    extraction = run_dir / "extraction"
    if any(path.is_dir() and path.name != "e01" for path in extraction.iterdir()):
        raise ValueError("single extraction must contain only the registered e01 directory")
    contract = InstanceContract.load(run_dir / "contract")
    if contract.instance_key not in PRT_INSTANCES:
        raise ValueError("the single-extractor score command currently implements the PRT method policy")
    checker = checker_from_contract(contract, artifact_root=artifact_root)
    rows, hashes, identities = [], {}, set()
    for roster_entry in manifest["roster"]:
        slug = roster_entry["session_slug"]
        path = extraction / "e01" / f"{slug}.json"
        raw_hash = sha256_file(path)
        hashes[path.name] = raw_hash
        row = {"session_slug": slug, "source_sha256": {s["source_id"]: s["sha256"] for s in roster_entry["sources"]},
               "input_sha256": raw_hash, "extraction_mode": "single", "extractor_count": 1,
               "validation_issues": [], "checks": [], "source_refutations": []}
        compiled = None
        try:
            raw = read_json(path)
            if not isinstance(raw, dict):
                raise ValueError("record must be an object")
            extractor = raw.get("extractor")
            extractor_id = extractor.get("extractor_id") if isinstance(extractor, dict) else None
            if isinstance(extractor_id, str) and not extractor_id.startswith("<FILL:"):
                identities.add(extractor_id)
            compiled, issues = compile_record(raw, contract, run_manifest=manifest,
                                              raw_record_sha256=raw_hash)
            row["validation_issues"] = [issue.as_dict() for issue in issues]
        except (ValueError, KeyError, TypeError) as error:
            row["validation_issues"] = [{"code": "INVALID_RECORD", "message": str(error)}]
        if compiled is None or row["validation_issues"]:
            row.update(status="invalid_extraction", **_undecided("invalid_or_unfilled_record"))
        elif (compiled["record_status"] != "complete"
              or compiled["coverage"]["completeness_status"] != "complete"
              or compiled["coverage"]["completeness_attestation"] is not True):
            row.update(status="incomplete_extraction", **_undecided("source_coverage_not_complete"))
        else:
            checked = _check_reading(compiled, contract, checker,
                                     contract.instance_key == "test01-ko7" and "fruit" in slug)
            row.update(checked["projection"], checks=checked["checks"],
                       compiled_record_sha256=checked["compiled_record_sha256"],
                       extractor_id=checked["extractor_id"])
            refutations = source_refutations([raw], contract, single_extractor=True)
            row["source_refutations"] = refutations
            applicable = [item for item in refutations if contract.instance_key != "test01-ko7"
                          or "fruit" not in slug or _fruit_refutation_applies({"certificate": item})]
            if applicable:
                row.update(dict.fromkeys(AXES, "Incorrect"))
                row["reasons"] = ["source_assertion_refuted:" + item["certificate_sha256"] for item in applicable]
            row["status"] = "checker_unresolved" if any(row[axis] == "Unknown" for axis in AXES) else "decided"
        rows.append(row)
    if len(identities) > 1:
        raise ValueError("single extraction contains multiple extractor identities")
    for entry in manifest["roster"]:
        filename = entry["session_slug"] + ".json"
        if sha256_file(extraction / "e01" / filename) != hashes[filename]:
            raise ValueError("an extraction changed during scoring; rerun after its writer finishes")
    report = {
        "version": "prt-single-extractor-score/1", "engine_version": __version__,
        "extraction_mode": "single", "extractor_count": 1,
        "independent_reader_agreement": "not_performed",
        "source_fidelity_basis": "one_reader_transcription_with_exact_anchors_and_paragraph_accounting",
        "contract": contract.binding(), "checker_binding": contract.checker_binding,
        "run_contract_sha256": manifest["run_contract_sha256"],
        "run_manifest_sha256": manifest["run_manifest_sha256"],
        "engine_source_sha256": {p.name: sha256_file(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "raw_record_hashes": hashes, "session_count": len(rows), "rows": rows,
        "invalid_count": sum(r["status"] == "invalid_extraction" for r in rows),
        "unknown_count": sum(any(r[a] == "Unknown" for a in AXES) for r in rows),
        "published_scores_modified": False,
    }
    report["report_sha256"] = canonical_sha256(report)
    return report
