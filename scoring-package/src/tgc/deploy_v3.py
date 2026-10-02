from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .common import (
    canonical_sha256,
    read_json,
    read_text,
    resolve_profile_path,
    sha256_file,
    sha256_text,
    write_json_atomic,
    write_text_atomic,
)
from .config import InstanceContract
from .lineage import (
    bind_roster_entry,
    finalize_run_manifest,
    run_contract_core,
    verify_run_manifest,
)
from .source_coverage import seed_paragraph_coverage


def _source_binding(
    contract: InstanceContract, session_dir: Path
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for source_id in contract.response_files:
        path = (session_dir / source_id).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        text = read_text(path)
        sources.append(
            {
                "source_id": source_id,
                "path": str(path),
                "sha256": sha256_file(path),
                "characters": len(text),
            }
        )
    return sources


def _copy_contract(source: Path, destination: Path) -> InstanceContract:
    source_contract = InstanceContract.load(source)
    if not source_contract.is_v3:
        raise ValueError("v3 deployment profile requires a v3 generated contract")
    shutil.copytree(source, destination)
    return InstanceContract.load(destination)


def _pass_entries(run_id: str, values: list[Any], extraction_mode: str | None = None) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for value in values:
        if isinstance(value, int) and not isinstance(value, bool):
            number = value
            pass_id = f"{run_id}:pass:{number:02d}"
        elif isinstance(value, dict):
            number = value.get("pass_number")
            pass_id = value.get("pass_id")
        else:
            raise ValueError(f"invalid pass entry {value!r}")
        if not isinstance(number, int) or isinstance(number, bool) or number not in {1, 2, 3}:
            raise ValueError(f"invalid pass number {number!r}")
        if not isinstance(pass_id, str) or not pass_id:
            raise ValueError(f"invalid pass ID {pass_id!r}")
        entries.append({"pass_number": number, "pass_id": pass_id})
    numbers = [item["pass_number"] for item in entries]
    ids = [item["pass_id"] for item in entries]
    if len(set(numbers)) != len(numbers) or len(set(ids)) != len(ids):
        raise ValueError("pass numbers and pass IDs must be unique")
    if extraction_mode not in {None, "single"}:
        raise ValueError("extraction_mode must be single or omitted for independent readers")
    if extraction_mode == "single":
        if numbers != [1]:
            raise ValueError("single extraction requires passes=[1]")
    elif sorted(numbers) not in ([1, 2], [1, 2, 3]):
        raise ValueError("official deployment pass set must be [1,2] or [1,2,3]")
    return sorted(entries, key=lambda item: item["pass_number"])


def _seed_binding(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": record["schema_version"],
        "contract": record["contract"],
        "run_binding": record["run_binding"],
        "session": record["session"],
        "pass_number": record["extractor"]["pass_number"],
    }


def _seed_record(
    contract: InstanceContract,
    *,
    run_id: str,
    run_contract_sha256: str,
    roster_entry: dict[str, Any],
    pass_entry: dict[str, Any],
) -> dict[str, Any]:
    template = read_json(contract.contract_dir / "record.template.json")
    template["contract"] = contract.binding()
    template["run_binding"] = {
        "run_id": run_id,
        "run_contract_sha256": run_contract_sha256,
        "roster_entry_sha256": roster_entry["roster_entry_sha256"],
        "pass_id": pass_entry["pass_id"],
    }
    template["session"] = {
        "session_slug": roster_entry["session_slug"],
        "sources": roster_entry["sources"],
    }
    template["extractor"]["pass_number"] = pass_entry["pass_number"]
    return template


def _dispatch_text(
    contract: InstanceContract,
    *,
    deployed_contract_dir: Path,
    assigned_dir: Path,
    pass_entry: dict[str, Any],
    run_id: str,
) -> str:
    prompt = read_text(contract.contract_dir / "EXTRACTOR_PROMPT_V3.md")
    return (
        prompt.replace("<CONTRACT_DIR>", str(deployed_contract_dir.resolve()))
        .replace("<ASSIGNED_DIR>", str(assigned_dir))
        .replace("<PASS_NUMBER>", str(pass_entry["pass_number"]))
        .replace("<PASS_ID>", pass_entry["pass_id"])
        .replace("<RUN_ID>", run_id)
    )


def _operational_manifest(
    *,
    profile_path: Path,
    run_dir: Path,
    pass_entries: list[dict[str, Any]],
    dispatch_texts: dict[int, str],
    seed_bindings: dict[str, dict[str, str]],
) -> dict[str, Any]:
    return {
        "profile": {
            "path": str(profile_path.resolve()),
            "sha256": sha256_file(profile_path),
        },
        "run_dir": str(run_dir.resolve()),
        "contract_dir": str((run_dir / "contract").resolve()),
        "extraction_directories": {
            str(item["pass_number"]): str(
                (run_dir / "extraction" / f"e{item['pass_number']:02d}").resolve()
            )
            for item in pass_entries
        },
        "dispatch_files": {
            str(item["pass_number"]): {
                "path": str(
                    (run_dir / "dispatch" / f"EXTRACTOR_{item['pass_number']:02d}.md").resolve()
                ),
                "sha256": sha256_text(dispatch_texts[item["pass_number"]]),
            }
            for item in pass_entries
        },
        "seed_bindings": seed_bindings,
    }


def _write_stage(
    *,
    stage: Path,
    source_contract_dir: Path,
    sessions_root: Path,
    slugs: list[str],
    profile: dict[str, Any],
    profile_path: Path,
    final_run_dir: Path,
) -> dict[str, Any]:
    contract = _copy_contract(source_contract_dir, stage / "contract")
    if contract.instance_key != profile["instance_key"]:
        raise ValueError("profile instance_key does not match contract")
    extraction_mode = profile.get("extraction_mode")
    pass_entries = _pass_entries(profile["run_id"], list(profile.get("passes", [1, 2])), extraction_mode)
    roster = [
        bind_roster_entry(
            slug,
            _source_binding(contract, sessions_root / slug),
        )
        for slug in slugs
    ]
    contract_core = run_contract_core(
        run_id=profile["run_id"],
        instance_key=contract.instance_key,
        contract=contract.binding(),
        sessions_root=str(sessions_root),
        selection=profile["selection"],
        passes=pass_entries,
        roster=roster,
        extraction_mode=extraction_mode,
    )
    run_contract_sha256 = canonical_sha256(contract_core)

    dispatch_texts: dict[int, str] = {}
    seed_bindings: dict[str, dict[str, str]] = {}
    for pass_entry in pass_entries:
        pass_number = pass_entry["pass_number"]
        extraction_dir = stage / "extraction" / f"e{pass_number:02d}"
        extraction_dir.mkdir(parents=True)
        # Designated-folder breadcrumb (live-round finding 2026-07-27): any
        # agent or operator LISTING this directory sees the law immediately.
        # Not a .json file, so it never enters the pass file-set.
        (extraction_dir / "_DIRECTORY_CONTRACT.txt").write_text(
            "OUTPUT LOCATION CONTRACT (mechanically enforced)\n"
            f"Run: {profile['run_id']}  Pass: {pass_number}\n\n"
            "This directory contains exactly one seeded <session_slug>.json "
            "per roster session. EDIT THOSE FILES IN PLACE.\n"
            "- Never create a new filename; never rename a file.\n"
            "- Never draft session JSON in a scratch/temp directory to copy "
            "later; save into the seeded file before moving on.\n"
            "- Enforcement: a wrong filename fails RECORD_FILENAME; an "
            "extra/missing .json fails PASS_FILE_SET; the compiler accepts "
            "only this run's registered pass directories, so files anywhere "
            "else are mechanically invisible.\n",
            encoding="utf-8",
            newline="\n",
        )
        for roster_entry in roster:
            record = _seed_record(
                contract,
                run_id=profile["run_id"],
                run_contract_sha256=run_contract_sha256,
                roster_entry=roster_entry,
                pass_entry=pass_entry,
            )
            if extraction_mode == "single":
                seed_paragraph_coverage(
                    record,
                    {item["source_id"]: read_text(Path(item["path"])) for item in roster_entry["sources"]},
                    int(contract.evidence_policy.get("max_anchor_characters", 4000)),
                )
            write_json_atomic(
                extraction_dir / f"{roster_entry['session_slug']}.json", record
            )
            seed_bindings.setdefault(str(pass_number), {})[
                roster_entry["session_slug"]
            ] = canonical_sha256(_seed_binding(record))
        text = _dispatch_text(
            contract,
            deployed_contract_dir=final_run_dir / "contract",
            assigned_dir=final_run_dir / "extraction" / f"e{pass_number:02d}",
            pass_entry=pass_entry,
            run_id=profile["run_id"],
        )
        if extraction_mode == "single":
            text = (
                "# Single extractor assignment\n\n"
                "Complete this pass alone. The engine checks the stated constructions after extraction. "
                "There is no second-reader agreement.\n\n"
                "The seeded p-prefixed anchors contain every source paragraph. Preserve their text and "
                "occurrence; fill every paragraph's mention disposition and link every construction "
                "in it. Add shorter exact anchors for individual fields and assertions. Reuse a "
                "paragraph anchor when it already is the exact required quote. Unresolved passages "
                "require uncertain coverage and an explanation. The independence attestation means "
                "that you did not consult other extractions, historical labels or scoring feedback.\n\n"
                + text
            )
        dispatch_texts[pass_number] = text
        write_text_atomic(
            stage / "dispatch" / f"EXTRACTOR_{pass_number:02d}.md", text
        )

    operational = _operational_manifest(
        profile_path=profile_path,
        run_dir=final_run_dir,
        pass_entries=pass_entries,
        dispatch_texts=dispatch_texts,
        seed_bindings=seed_bindings,
    )
    manifest = finalize_run_manifest(contract_core, operational)
    write_json_atomic(stage / "RUN_MANIFEST.json", manifest)
    return manifest


def verify_deployed_run(
    run_dir: Path,
    *,
    expected_profile: dict[str, Any] | None = None,
    expected_profile_path: Path | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest_path = run_dir / "RUN_MANIFEST.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)
    manifest = read_json(manifest_path)
    manifest_issues = verify_run_manifest(manifest)
    issues: list[dict[str, str]] = list(manifest_issues)
    try:
        contract = InstanceContract.load(run_dir / "contract")
    except Exception as error:
        contract = None
        issues.append(
            {"code": "DEPLOYED_CONTRACT", "path": "contract", "message": str(error)}
        )
    if contract is not None and manifest.get("contract") != contract.binding():
        issues.append(
            {
                "code": "DEPLOYED_CONTRACT_BINDING",
                "path": "RUN_MANIFEST.json",
                "message": "manifest and deployed contract differ",
            }
        )
    operational = manifest.get("operational", {})
    for pass_number, item in operational.get("dispatch_files", {}).items():
        path = Path(item["path"])
        if not path.is_file():
            issues.append(
                {"code": "DISPATCH_MISSING", "path": str(path), "message": pass_number}
            )
        elif sha256_file(path) != item.get("sha256"):
            issues.append(
                {"code": "DISPATCH_HASH", "path": str(path), "message": pass_number}
            )
    roster = {item["session_slug"]: item for item in manifest.get("roster", [])}
    for pass_entry in manifest.get("passes", []):
        number = pass_entry["pass_number"]
        directory = run_dir / "extraction" / f"e{number:02d}"
        expected_files = {f"{slug}.json" for slug in roster}
        observed_files = {path.name for path in directory.glob("*.json")}
        if observed_files != expected_files:
            issues.append(
                {
                    "code": "SEED_FILE_SET",
                    "path": str(directory),
                    "message": f"missing={sorted(expected_files-observed_files)} extra={sorted(observed_files-expected_files)}",
                }
            )
        for slug in sorted(roster):
            path = directory / f"{slug}.json"
            if not path.is_file():
                continue
            try:
                record = read_json(path)
                observed = canonical_sha256(_seed_binding(record))
            except Exception as error:
                issues.append(
                    {"code": "SEED_JSON", "path": str(path), "message": str(error)}
                )
                continue
            wanted = operational.get("seed_bindings", {}).get(str(number), {}).get(slug)
            if observed != wanted:
                issues.append(
                    {
                        "code": "SEED_BINDING_DRIFT",
                        "path": str(path),
                        "message": f"expected {wanted}, observed {observed}",
                    }
                )
    if expected_profile is not None:
        if expected_profile.get("run_id") != manifest.get("run_id"):
            issues.append(
                {
                    "code": "PROFILE_RUN_ID",
                    "path": "profile.run_id",
                    "message": str(expected_profile.get("run_id")),
                }
            )
        if expected_profile.get("instance_key") != manifest.get("instance_key"):
            issues.append(
                {
                    "code": "PROFILE_INSTANCE",
                    "path": "profile.instance_key",
                    "message": str(expected_profile.get("instance_key")),
                }
            )
    if expected_profile_path is not None:
        profile_binding = operational.get("profile", {})
        if profile_binding.get("sha256") != sha256_file(expected_profile_path):
            issues.append(
                {
                    "code": "PROFILE_HASH",
                    "path": str(expected_profile_path),
                    "message": "profile differs from deployed profile hash",
                }
            )
    return {
        "run_dir": str(run_dir),
        "valid": not issues,
        "run_contract_sha256": manifest.get("run_contract_sha256"),
        "run_manifest_sha256": manifest.get("run_manifest_sha256"),
        "session_count": len(roster),
        "pass_count": len(manifest.get("passes", [])),
        "issues": issues,
    }


def deploy_profile_v3(
    profile_path: Path,
    *,
    select_sessions: Any,
) -> dict[str, Any]:
    profile_path = profile_path.resolve()
    profile = read_json(profile_path)
    if profile.get("profile_version") != "tgc-deployment-profile/3.0.0":
        raise ValueError("unsupported v3 deployment profile version")
    base_dir = profile_path.parent
    source_contract_dir = resolve_profile_path(base_dir, profile["contract_dir"])
    sessions_root = resolve_profile_path(base_dir, profile["sessions_root"])
    run_dir = resolve_profile_path(base_dir, profile["run_dir"])
    slugs = select_sessions(
        sessions_root, profile["selection"], base_dir=base_dir
    )
    if not slugs:
        raise ValueError("deployment selected zero sessions")

    if run_dir.exists():
        verification = verify_deployed_run(
            run_dir,
            expected_profile=profile,
            expected_profile_path=profile_path,
        )
        if not verification["valid"]:
            raise ValueError(
                "existing run is not an idempotent match: "
                + json.dumps(verification["issues"], ensure_ascii=False)
            )
        return {**verification, "deployment_status": "preserved"}

    run_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=f".{run_dir.name}.staging-", dir=run_dir.parent)
    )
    try:
        manifest = _write_stage(
            stage=stage,
            source_contract_dir=source_contract_dir,
            sessions_root=sessions_root,
            slugs=slugs,
            profile=profile,
            profile_path=profile_path,
            final_run_dir=run_dir,
        )
        os.replace(stage, run_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    verification = verify_deployed_run(
        run_dir,
        expected_profile=profile,
        expected_profile_path=profile_path,
    )
    if not verification["valid"]:
        raise ValueError(
            "fresh deployment failed verification: "
            + json.dumps(verification["issues"], ensure_ascii=False)
        )
    return {
        **verification,
        "deployment_status": "created",
        "run_manifest": manifest,
    }


def seed_tiebreak(
    run_dir: Path,
    gate_report_path: Path,
) -> dict[str, Any]:
    """Seed a blind pass-3 tiebreak bound to the deployed run (friction F4).

    Reads the run manifest and a completed 2-pass gate report, takes the
    gate's `tiebreak_session_slugs`, seeds `extraction/e03/<slug>.json` with
    the SAME hash-bound seed records deploy uses (no-clobber), writes a
    create-once `TIEBREAK_MANIFEST.json` binding run manifest + gate report +
    slug subset + seed bindings, and emits `dispatch/EXTRACTOR_03.md`.
    Compilation of e03 resolves its pass entry and roster subset from this
    manifest.
    """
    run_dir = run_dir.resolve()
    manifest = read_json(run_dir / "RUN_MANIFEST.json")
    if manifest.get("extraction_mode") == "single":
        raise ValueError("a single-extractor run has no reader tiebreak")
    gate_report = read_json(gate_report_path)
    declared = gate_report.get("gate_report_sha256")
    core = dict(gate_report)
    core.pop("gate_report_sha256", None)
    if canonical_sha256(core) != declared:
        raise ValueError("gate report hash mismatch; refusing to seed tiebreak")
    if gate_report.get("run_contract_sha256") != manifest.get(
        "contract", {}
    ).get("run_contract_sha256") and gate_report.get(
        "run_contract_sha256"
    ) != manifest.get("run_contract_sha256"):
        # tolerate either manifest layout; at least one must match
        run_contract = (
            manifest.get("contract", {}).get("run_contract_sha256")
            or manifest.get("run_contract_sha256")
        )
        if gate_report.get("run_contract_sha256") != run_contract:
            raise ValueError(
                "gate report was not produced from this run's contract"
            )
    slugs = sorted(gate_report.get("tiebreak_session_slugs") or [])
    if not slugs:
        raise ValueError("gate report lists no tiebreak candidates")
    tiebreak_path = run_dir / "TIEBREAK_MANIFEST.json"
    contract = InstanceContract.load(run_dir / "contract")
    run_id = manifest["run_id"]
    pass_entry = {"pass_number": 3, "pass_id": f"{run_id}:pass:03"}
    roster = {
        item["session_slug"]: item for item in manifest.get("roster", [])
    }
    unknown = [slug for slug in slugs if slug not in roster]
    if unknown:
        raise ValueError(f"tiebreak slugs outside the roster: {unknown[:5]}")
    run_contract_sha256 = (
        manifest.get("contract", {}).get("run_contract_sha256")
        or manifest.get("run_contract_sha256")
    )
    extraction_dir = run_dir / "extraction" / "e03"
    dispatch_dir = run_dir / "dispatch"
    dispatch_path = dispatch_dir / "EXTRACTOR_03.md"
    seed_bindings: dict[str, str] = {}
    records = {}
    for slug in slugs:
        record = _seed_record(
            contract,
            run_id=run_id,
            run_contract_sha256=run_contract_sha256,
            roster_entry=roster[slug],
            pass_entry=pass_entry,
        )
        seed_bindings[slug] = canonical_sha256(_seed_binding(record))
        records[slug] = record
    tiebreak_manifest_core = {
        "tiebreak_manifest_version": "tgc-tiebreak-manifest/1.0.0",
        "run_id": run_id,
        "run_manifest_sha256": manifest.get("run_manifest_sha256"),
        "gate_report_sha256": declared,
        "pass_entry": pass_entry,
        "session_slugs": slugs,
        "seed_bindings": seed_bindings,
        "extraction_directory": str(extraction_dir),
        "dispatch_file": str(dispatch_path),
    }
    tiebreak_manifest = {
        **tiebreak_manifest_core,
        "tiebreak_manifest_sha256": canonical_sha256(tiebreak_manifest_core),
    }
    if tiebreak_path.exists() and read_json(tiebreak_path) != tiebreak_manifest:
        raise ValueError("TIEBREAK_MANIFEST.json exists with different content; refusing to overwrite")
    unexpected = {p.name for p in extraction_dir.glob("*.json")} - {f"{s}.json" for s in slugs}
    if unexpected:
        raise ValueError("unexpected files in tiebreak directory")
    for slug in slugs:
        target = extraction_dir / f"{slug}.json"
        if target.exists() and canonical_sha256(_seed_binding(read_json(target))) != seed_bindings[slug]:
            raise ValueError("changed tiebreak seed binding: " + slug)
    extraction_dir.mkdir(parents=True, exist_ok=True)
    created = preserved = 0
    for slug, record in records.items():
        target = extraction_dir / f"{slug}.json"
        if target.exists():
            preserved += 1
            continue
        write_json_atomic(target, record)
        created += 1
    directory_contract = extraction_dir / "_DIRECTORY_CONTRACT.txt"
    if not directory_contract.exists():
        directory_contract.write_text(
            "OUTPUT LOCATION CONTRACT (mechanically enforced)\n"
            f"Run: {run_id}  Pass: 3 (TIEBREAK)\n\n"
            "This directory contains exactly one seeded <session_slug>.json per "
            "tiebreak session. EDIT THOSE FILES IN PLACE.\n"
            "- Never create a new filename; never rename a file.\n"
            "- Never draft session JSON elsewhere; save into the seeded file "
            "before moving on.\n",
            encoding="utf-8",
            newline="\n",
        )
    dispatch_dir.mkdir(exist_ok=True)
    dispatch_text = _dispatch_text(
        contract,
        deployed_contract_dir=run_dir / "contract",
        assigned_dir=extraction_dir,
        pass_entry=pass_entry,
        run_id=run_id,
    )
    if not dispatch_path.exists():
        dispatch_path.write_text(dispatch_text, encoding="utf-8", newline="\n")
    if not tiebreak_path.exists():
        write_json_atomic(tiebreak_path, tiebreak_manifest)
    return {
        **tiebreak_manifest,
        "created": created,
        "preserved": preserved,
    }
