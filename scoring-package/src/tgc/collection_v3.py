from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from .common import (
    canonical_sha256,
    read_json,
    sha256_file,
    write_json_atomic,
)
from .compiler import compile_record
from .compiler_v3 import compiler_build_receipt
from .config import InstanceContract
from .lineage import find_pass, verify_run_manifest

V3_COMPILE_REPORT = "tgc-compile-report/3.0.0"
V3_COMPILED_RECORD = "tgc-compiled-record/3.0.0"


def _pass_for_input_dir(
    manifest: dict[str, Any], input_dir: Path
) -> dict[str, Any]:
    resolved = str(input_dir.resolve())
    directories = manifest.get("operational", {}).get(
        "extraction_directories", {}
    )
    matches = [
        int(pass_number)
        for pass_number, path in directories.items()
        if str(Path(path).resolve()) == resolved
    ]
    if not matches:
        # Tiebreak pass (friction F4): e03 is registered post-gate by
        # TIEBREAK_MANIFEST.json in the run directory, hash-bound to the run
        # manifest and the gate report that selected its slug subset.
        tiebreak_path = input_dir.resolve().parents[1] / "TIEBREAK_MANIFEST.json"
        if tiebreak_path.is_file():
            tiebreak = read_json(tiebreak_path)
            core = dict(tiebreak)
            declared = core.pop("tiebreak_manifest_sha256", None)
            from .common import canonical_sha256 as _csha

            if declared != _csha(core):
                raise ValueError("TIEBREAK_MANIFEST hash mismatch")
            if tiebreak.get("run_manifest_sha256") != manifest.get(
                "run_manifest_sha256"
            ):
                raise ValueError(
                    "TIEBREAK_MANIFEST is not bound to this run manifest"
                )
            if str(Path(tiebreak["extraction_directory"]).resolve()) == resolved:
                entry = dict(tiebreak["pass_entry"])
                entry["tiebreak_slugs"] = list(tiebreak["session_slugs"])
                return entry
    if len(matches) != 1:
        raise ValueError(
            f"input directory {resolved} is not exactly one deployed pass directory"
        )
    entry = find_pass(manifest, matches[0])
    if entry is None:
        raise ValueError(f"run manifest has no pass entry {matches[0]}")
    return entry


def _report_hash(report: dict[str, Any]) -> str:
    core = dict(report)
    core.pop("compile_report_sha256", None)
    return canonical_sha256(core)


def compile_pass_directory_v3(
    input_dir: Path,
    output_dir: Path,
    contract: InstanceContract,
    *,
    run_manifest: dict[str, Any],
    require_independence: bool = True,
) -> dict[str, Any]:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(
            f"immutable compiled output already exists: {output_dir}"
        )
    manifest_issues = verify_run_manifest(run_manifest)
    if manifest_issues:
        raise ValueError(f"invalid run manifest: {manifest_issues}")
    if run_manifest.get("contract") != contract.binding():
        raise ValueError("run manifest and loaded contract differ")
    pass_entry = _pass_for_input_dir(run_manifest, input_dir)
    pass_number = pass_entry["pass_number"]
    # Tiebreak passes are registered by the TIEBREAK_MANIFEST, not the run
    # manifest; record validation receives the resolved entry explicitly so
    # the immutable manifest is never mutated (its self-hash must hold).
    extra_pass_entry = (
        {k: v for k, v in pass_entry.items() if k != "tiebreak_slugs"}
        if pass_entry.get("tiebreak_slugs")
        else None
    )
    roster_slugs = sorted(
        pass_entry.get("tiebreak_slugs")
        or [item["session_slug"] for item in run_manifest.get("roster", [])]
    )
    expected_files = {f"{slug}.json" for slug in roster_slugs}
    observed_files = {path.name for path in input_dir.glob("*.json")}
    file_set_issue = None
    if observed_files != expected_files:
        file_set_issue = {
            "code": "PASS_FILE_SET",
            "path": str(input_dir),
            "message": (
                f"missing={sorted(expected_files-observed_files)} "
                f"extra={sorted(observed_files-expected_files)}"
            ),
        }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=f".{output_dir.name}.staging-", dir=output_dir.parent
        )
    )
    rows: list[dict[str, Any]] = []
    valid = 0
    invalid = 0
    seen_slugs: set[str] = set()
    build = compiler_build_receipt()
    try:
        if file_set_issue is not None:
            invalid += 1
            rows.append(
                {
                    "input_file": None,
                    "session_slug": None,
                    "valid": False,
                    "issues": [file_set_issue],
                }
            )
        for slug in roster_slugs:
            path = input_dir / f"{slug}.json"
            if not path.is_file():
                continue
            input_sha256 = sha256_file(path)
            try:
                record = read_json(path)
                compiled, issues = compile_record(
                    record,
                    contract,
                    require_independence=require_independence,
                    run_manifest=run_manifest,
                    official_mode=True,
                    raw_record_sha256=input_sha256,
                    extra_pass_entry=extra_pass_entry,
                )
            except Exception as error:
                compiled = None
                issues = []
                error_message = str(error)
            else:
                error_message = ""
            if compiled is None:
                invalid += 1
                rows.append(
                    {
                        "input_file": str(path),
                        "input_sha256": input_sha256,
                        "session_slug": slug,
                        "pass_number": pass_number,
                        "valid": False,
                        "issues": [issue.as_dict() for issue in issues]
                        or [
                            {
                                "code": "COMPILE_EXCEPTION",
                                "path": "$",
                                "message": error_message,
                            }
                        ],
                    }
                )
                continue
            compiled_slug = compiled["session"]["session_slug"]
            compiled_pass = compiled["extractor"]["pass_number"]
            if compiled_slug != slug or compiled_pass != pass_number:
                invalid += 1
                rows.append(
                    {
                        "input_file": str(path),
                        "input_sha256": input_sha256,
                        "session_slug": slug,
                        "pass_number": pass_number,
                        "valid": False,
                        "issues": [
                            {
                                "code": "PASS_RECORD_BINDING",
                                "path": "$",
                                "message": (
                                    f"record slug/pass={compiled_slug!r}/{compiled_pass!r}; "
                                    f"expected {slug!r}/{pass_number!r}"
                                ),
                            }
                        ],
                    }
                )
                continue
            if compiled_slug in seen_slugs:
                invalid += 1
                rows.append(
                    {
                        "input_file": str(path),
                        "input_sha256": input_sha256,
                        "session_slug": slug,
                        "pass_number": pass_number,
                        "valid": False,
                        "issues": [
                            {
                                "code": "COMPILED_SLUG_DUPLICATE",
                                "path": "$.session.session_slug",
                                "message": compiled_slug,
                            }
                        ],
                    }
                )
                continue
            seen_slugs.add(compiled_slug)
            valid += 1
            output_path = stage / path.name
            write_json_atomic(output_path, compiled)
            rows.append(
                {
                    "input_file": str(path),
                    "input_sha256": input_sha256,
                    "output_file": str(output_dir / path.name),
                    "output_sha256": sha256_file(output_path),
                    "session_slug": compiled_slug,
                    "pass_number": compiled_pass,
                    "valid": True,
                    "compiled_record_id": compiled["compiled_record_id"],
                    "claim_count": len(compiled["claims"]),
                    "issues": [],
                }
            )

        report = {
            "compile_report_version": V3_COMPILE_REPORT,
            "lineage": {
                "contract_manifest_sha256": contract.manifest_sha256,
                "modular_registry_sha256": contract.modular_registry_sha256,
                "run_contract_sha256": run_manifest[
                    "run_contract_sha256"
                ],
                "run_manifest_sha256": run_manifest[
                    "run_manifest_sha256"
                ],
                "pass_id": pass_entry["pass_id"],
                "compiler": build,
            },
            "input_dir": str(input_dir),
            "output_dir": str(output_dir),
            "pass_number": pass_number,
            "expected_record_count": len(roster_slugs),
            "record_count": len(rows),
            "valid_count": valid,
            "invalid_count": invalid,
            "published": invalid == 0 and valid == len(roster_slugs),
            "rows": rows,
        }
        report["compile_report_sha256"] = _report_hash(report)
        if report["published"]:
            write_json_atomic(stage / "COMPILE_REPORT.json", report)
            os.replace(stage, output_dir)
        else:
            shutil.rmtree(stage, ignore_errors=True)
        return report
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def verify_compiled_directory_v3(
    directory: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    directory = directory.resolve()
    report_path = directory / "COMPILE_REPORT.json"
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    report = read_json(report_path)
    if report.get("compile_report_version") != V3_COMPILE_REPORT:
        raise ValueError(f"{report_path} is not a v3 compile report")
    declared = report.get("compile_report_sha256")
    observed = _report_hash(report)
    if declared != observed:
        raise ValueError(
            f"compile report hash mismatch: declared {declared}, observed {observed}"
        )
    if report.get("published") is not True or report.get("invalid_count") != 0:
        raise ValueError("compiled directory report is not a closed successful pass")
    records: list[dict[str, Any]] = []
    expected_files = {
        Path(row["output_file"]).name
        for row in report.get("rows", [])
        if row.get("valid") is True
    }
    observed_files = {
        path.name
        for path in directory.glob("*.json")
        if path.name != "COMPILE_REPORT.json"
    }
    if expected_files != observed_files:
        raise ValueError(
            f"compiled file set mismatch: missing={sorted(expected_files-observed_files)} extra={sorted(observed_files-expected_files)}"
        )
    for row in report.get("rows", []):
        if row.get("valid") is not True:
            continue
        path = directory / Path(row["output_file"]).name
        observed_hash = sha256_file(path)
        if observed_hash != row.get("output_sha256"):
            raise ValueError(
                f"compiled record hash mismatch for {path}: expected {row.get('output_sha256')}, observed {observed_hash}"
            )
        record = read_json(path)
        if record.get("compiled_schema_version") != V3_COMPILED_RECORD:
            raise ValueError(f"{path} is not a v3 compiled record")
        if record.get("compiled_record_id") != row.get("compiled_record_id"):
            raise ValueError(
                f"compiled record ID mismatch for {path}"
            )
        records.append(record)
    if len(records) != report.get("valid_count"):
        raise ValueError("compile report valid_count differs from loaded records")
    return records, report


def load_compiled_directories_v3(
    directories: list[Path],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    run_hashes: set[str] = set()
    contract_hashes: set[str] = set()
    pass_numbers: set[int] = set()
    for directory in directories:
        batch, report = verify_compiled_directory_v3(directory)
        run_hashes.add(report["lineage"]["run_contract_sha256"])
        contract_hashes.add(report["lineage"]["contract_manifest_sha256"])
        number = int(report["pass_number"])
        if number in pass_numbers:
            raise ValueError(f"duplicate compiled pass directory for pass {number}")
        pass_numbers.add(number)
        records.extend(batch)
    if len(run_hashes) != 1 or len(contract_hashes) != 1:
        raise ValueError("compiled directories do not share one run and contract")
    return records
