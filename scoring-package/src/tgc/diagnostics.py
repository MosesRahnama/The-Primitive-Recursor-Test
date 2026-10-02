from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .checkers import checker_from_contract
from .common import canonical_sha256, read_json, sha256_file
from .config import InstanceContract
from .deploy_v3 import verify_deployed_run
from .lineage import verify_run_manifest
from .validation import validate_record_file


def audit_pass_directory(
    input_dir: Path,
    contract: InstanceContract,
    *,
    run_manifest: dict[str, Any] | None = None,
    require_independence: bool = True,
    official_mode: bool = True,
) -> dict[str, Any]:
    input_dir = input_dir.resolve()
    rows: list[dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    claims = 0
    anchors = 0
    dispositions = 0
    # Tiebreak passes (engine 3.1.4, live tiebreak round 2026-07-27): e03 is
    # registered post-gate by the hash-bound TIEBREAK_MANIFEST, not by the
    # run manifest. Resolve it exactly like the compiler does, then audit
    # against the augmented pass registry and the tiebreak slug subset so
    # RUN_PASS_MISSING / PASS_FILE_SET reflect the real contract.
    tiebreak_slugs: list[str] | None = None
    extra_pass_entry: dict[str, Any] | None = None
    if run_manifest is not None:
        from .collection_v3 import _pass_for_input_dir

        try:
            pass_entry = _pass_for_input_dir(run_manifest, input_dir)
        except ValueError:
            pass_entry = None
        if pass_entry is not None and pass_entry.get("tiebreak_slugs"):
            tiebreak_slugs = list(pass_entry["tiebreak_slugs"])
            extra_pass_entry = {
                key: value
                for key, value in pass_entry.items()
                if key != "tiebreak_slugs"
            }
    # Designated-folder discipline surfaces at AUDIT time, not first at
    # compile: the pass directory must contain exactly one <slug>.json per
    # roster entry (live-round finding 2026-07-27: an agent drafting files
    # under other names elsewhere is invisible to the engine, and an extra
    # or missing file here must be an explicit, named defect).
    file_set = None
    if run_manifest is not None:
        expected = (
            {f"{slug}.json" for slug in tiebreak_slugs}
            if tiebreak_slugs is not None
            else {
                f"{item['session_slug']}.json"
                for item in run_manifest.get("roster", [])
            }
        )
        observed = {path.name for path in input_dir.glob("*.json")}
        file_set = {
            "expected_count": len(expected),
            "observed_count": len(observed),
            "missing": sorted(expected - observed),
            "extra": sorted(observed - expected),
            "matches_roster": observed == expected,
        }
        if not file_set["matches_roster"]:
            issue_counts["PASS_FILE_SET"] += 1
    for path in sorted(input_dir.glob("*.json")):
        record, issues = validate_record_file(
            path,
            contract,
            require_independence=require_independence,
            run_manifest=run_manifest,
            official_mode=official_mode,
            extra_pass_entry=extra_pass_entry,
        )
        for issue in issues:
            issue_counts[issue.code] += 1
        if record is not None:
            status_counts[str(record.get("record_status"))] += 1
            claims += len(record.get("claims", [])) if isinstance(record.get("claims"), list) else 0
            anchors += len(record.get("anchors", {})) if isinstance(record.get("anchors"), dict) else 0
            coverage = record.get("coverage", {})
            if isinstance(coverage, dict) and isinstance(coverage.get("mention_dispositions"), list):
                dispositions += len(coverage["mention_dispositions"])
        rows.append(
            {
                "input_file": str(path),
                "input_sha256": sha256_file(path),
                "session_slug": (
                    record.get("session", {}).get("session_slug")
                    if isinstance(record, dict)
                    else path.stem
                ),
                "valid": not issues,
                "issue_count": len(issues),
                "issues": [issue.as_dict() for issue in issues],
            }
        )
    report = {
        "pass_audit_version": "tgc-pass-audit/3.0.0",
        "file_set": file_set,
        "contract": contract.binding(),
        "run_contract_sha256": (
            run_manifest.get("run_contract_sha256")
            if isinstance(run_manifest, dict)
            else None
        ),
        "input_dir": str(input_dir),
        "record_count": len(rows),
        "valid_count": sum(row["valid"] for row in rows),
        "invalid_count": sum(not row["valid"] for row in rows),
        "record_status_counts": dict(sorted(status_counts.items())),
        "claim_count": claims,
        "anchor_count": anchors,
        "mention_disposition_count": dispositions,
        "issue_counts": dict(sorted(issue_counts.items())),
        "rows": rows,
    }
    report["pass_audit_sha256"] = canonical_sha256(report)
    return report


def doctor(
    contract_dir: Path,
    *,
    run_dir: Path | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        contract = InstanceContract.load(contract_dir)
    except Exception as error:
        return {
            "doctor_version": "tgc-doctor/3.0.0",
            "valid": False,
            "checks": [
                {
                    "name": "contract",
                    "status": "FAIL",
                    "detail": str(error),
                }
            ],
        }
    checks.append(
        {
            "name": "contract",
            "status": "PASS",
            "detail": {
                "config_version": contract.config_version,
                "instance_key": contract.instance_key,
                "manifest_sha256": contract.manifest_sha256,
                "modular_registry_sha256": contract.modular_registry_sha256,
            },
        }
    )
    try:
        checker = checker_from_contract(contract, artifact_root=artifact_root)
        binding = getattr(checker, "__tgc_binding__", contract.checker_binding)
    except Exception as error:
        checks.append(
            {
                "name": "checker",
                "status": "FAIL",
                "detail": str(error),
            }
        )
    else:
        checks.append(
            {
                "name": "checker",
                "status": "PASS",
                "detail": {
                    "binding": binding,
                    "binding_sha256": canonical_sha256(binding),
                },
            }
        )
    if run_dir is not None:
        verification = verify_deployed_run(run_dir)
        checks.append(
            {
                "name": "deployed_run",
                "status": "PASS" if verification["valid"] else "FAIL",
                "detail": verification,
            }
        )
        manifest_path = run_dir / "RUN_MANIFEST.json"
        if manifest_path.is_file():
            manifest = read_json(manifest_path)
            issues = verify_run_manifest(manifest)
            checks.append(
                {
                    "name": "run_manifest",
                    "status": "PASS" if not issues else "FAIL",
                    "detail": {
                        "path": str(manifest_path.resolve()),
                        "sha256": sha256_file(manifest_path),
                        "issues": issues,
                    },
                }
            )
    result = {
        "doctor_version": "tgc-doctor/3.0.0",
        "valid": all(check["status"] == "PASS" for check in checks),
        "checks": checks,
    }
    result["doctor_report_sha256"] = canonical_sha256(result)
    return result


def pass_status(run_dir: Path, pass_number: int) -> dict[str, Any]:
    """Lightweight mid-flight fill status for one pass of a deployed run.

    Reads ONLY the run manifest and the pass directory (no validation, no
    checker): file-set conformance plus per-file parse / placeholder /
    record_status progress, so the operator can see exactly where a live
    extraction stands without touching agent work.
    """
    from .common import read_json as _read_json

    run_dir = run_dir.resolve()
    manifest = _read_json(run_dir / "RUN_MANIFEST.json")
    roster_slugs = sorted(
        item["session_slug"] for item in manifest.get("roster", [])
    )
    directory = run_dir / "extraction" / f"e{pass_number:02d}"
    expected = {f"{slug}.json" for slug in roster_slugs}
    observed = {path.name for path in directory.glob("*.json")}
    rows = []
    filled = placeholders = unparseable = 0
    for slug in roster_slugs:
        path = directory / f"{slug}.json"
        state = "missing"
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
                json.loads(text)
            except Exception:
                state = "unparseable"
                unparseable += 1
            else:
                if "<FILL:" in text or "<OPTIONAL:" in text:
                    state = "placeholders"
                    placeholders += 1
                else:
                    state = "filled"
                    filled += 1
        rows.append({"session_slug": slug, "state": state})
    return {
        "pass_status_version": "tgc-pass-status/1.0.0",
        "run_id": manifest.get("run_id"),
        "pass_number": pass_number,
        "directory": str(directory),
        "file_set": {
            "matches_roster": observed == expected,
            "missing": sorted(expected - observed),
            "extra": sorted(observed - expected),
        },
        "roster_count": len(roster_slugs),
        "filled": filled,
        "placeholders_remaining": placeholders,
        "unparseable": unparseable,
        "rows": rows,
    }


def repair_brief(audit_report: dict[str, Any]) -> str:
    """Generate the per-pass repair dispatch box from an audit report (F5).

    The box contains ONLY this pass's validator output — never another
    pass's content — so blindness survives the repair loop. Format-repair
    only: agents fix listed issues, never re-extract or reinterpret.
    """
    rows = [row for row in audit_report.get("rows", []) if not row.get("valid")]
    directory = audit_report.get("input_dir", "<your fill directory>")
    lines = [
        "=== START REPAIR BOX (copy from here) ===",
        "",
        "You previously filled the extraction records in:",
        f"  {directory}",
        f"The mechanical validator rejected {len(rows)} of "
        f"{audit_report.get('record_count')} records for FORMAT issues.",
        "Fix ONLY what is listed below, editing each file IN PLACE. Do not "
        "re-read responses (except to re-copy an exact span flagged as "
        "non-exact), do not change transcription content, do not add or "
        "remove claims, do not touch any bound field.",
        "After each file: re-parse it as ONE valid JSON document.",
        "",
    ]
    for row in rows:
        name = Path(str(row.get("input_file"))).name
        lines.append(f"### {name}")
        for issue in row.get("issues", []):
            lines.append(
                f"- {issue.get('code')} at {issue.get('path')} : "
                f"{str(issue.get('message'))[:160]}"
            )
        lines.append("")
    lines += [
        "WHEN DONE, reply with EXACTLY: DONE repair: <n> files fixed.",
        "",
        "=== END REPAIR BOX ===",
        "",
    ]
    return "\n".join(lines)
