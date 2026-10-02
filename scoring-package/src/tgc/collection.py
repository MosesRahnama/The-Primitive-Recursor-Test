from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .common import read_json, write_json_atomic
from .compiler import compile_record
from .config import InstanceContract

V2_COMPILE_REPORT = "tgc-compile-report/2.0.0"
V3_COMPILE_REPORT = "tgc-compile-report/3.0.0"


def compile_pass_directory(
    input_dir: Path,
    output_dir: Path,
    contract: InstanceContract,
    *,
    require_independence: bool = True,
    run_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if contract.is_v3:
        if run_manifest is None:
            raise ValueError("v3 pass compilation requires RUN_MANIFEST.json")
        from .collection_v3 import compile_pass_directory_v3

        return compile_pass_directory_v3(
            input_dir,
            output_dir,
            contract,
            run_manifest=run_manifest,
            require_independence=require_independence,
        )
    if output_dir.exists():
        raise FileExistsError(f"immutable compiled output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    valid = 0
    invalid = 0
    for path in sorted(input_dir.glob("*.json")):
        try:
            record = read_json(path)
            compiled, issues = compile_record(
                record,
                contract,
                require_independence=require_independence,
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
                    "session_slug": path.stem,
                    "valid": False,
                    "issues": [issue.as_dict() for issue in issues]
                    or [{"code": "COMPILE_EXCEPTION", "path": "$", "message": error_message}],
                }
            )
            continue
        valid += 1
        output_path = output_dir / path.name
        write_json_atomic(output_path, compiled)
        rows.append(
            {
                "input_file": str(path),
                "output_file": str(output_path),
                "session_slug": compiled["session"]["session_slug"],
                "pass_number": compiled["extractor"]["pass_number"],
                "valid": True,
                "compiled_record_id": compiled["compiled_record_id"],
                "claim_count": len(compiled["claims"]),
                "issues": [],
            }
        )
    report = {
        "compile_report_version": V2_COMPILE_REPORT,
        "input_dir": str(input_dir.resolve()),
        "output_dir": str(output_dir.resolve()),
        "record_count": len(rows),
        "valid_count": valid,
        "invalid_count": invalid,
        "rows": rows,
    }
    write_json_atomic(output_dir / "COMPILE_REPORT.json", report)
    return report


def load_compiled_directories(directories: list[Path]) -> list[dict[str, Any]]:
    if not directories:
        return []
    reports = [
        read_json(directory / "COMPILE_REPORT.json")
        for directory in directories
    ]
    versions = {report.get("compile_report_version") for report in reports}
    if versions == {V3_COMPILE_REPORT}:
        from .collection_v3 import load_compiled_directories_v3

        return load_compiled_directories_v3(directories)
    if versions != {V2_COMPILE_REPORT}:
        rendered = sorted(repr(version) for version in versions)
        if versions <= {V2_COMPILE_REPORT, V3_COMPILE_REPORT}:
            raise ValueError("cannot mix v2 and v3 compiled pass directories")
        raise ValueError(
            "unsupported or mixed compile report versions: "
            f"{rendered}"
        )
    records: list[dict[str, Any]] = []
    for directory in directories:
        for path in sorted(directory.glob("*.json")):
            if path.name == "COMPILE_REPORT.json":
                continue
            record = read_json(path)
            if record.get("compiled_schema_version") != "tgc-compiled-record/2.0.0":
                raise ValueError(f"{path} is not a compiled TGC v2 record")
            records.append(record)
    return records


def write_gate_csv(report: dict[str, Any], path: Path) -> None:
    """Compatibility/reporting view only; JSON remains authoritative."""
    fields = [
        "session_slug",
        "gate_status",
        "pass_numbers_json",
        "n_agreed",
        "n_unresolved",
        "agreed_claims_json",
        "unresolved_claims_json",
        "primary_json",
        "provenance_json",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in report.get("rows", []):
            writer.writerow(
                {
                    "session_slug": row["session"]["session_slug"],
                    "gate_status": row["gate_status"],
                    "pass_numbers_json": json.dumps(row.get("pass_numbers", []), separators=(",", ":")),
                    "n_agreed": len(row.get("agreed_claims", [])),
                    "n_unresolved": row.get("unresolved_count", 0),
                    "agreed_claims_json": json.dumps(row.get("agreed_claims", []), ensure_ascii=False, separators=(",", ":")),
                    "unresolved_claims_json": json.dumps(row.get("unresolved_claims", []), ensure_ascii=False, separators=(",", ":")),
                    "primary_json": json.dumps(row.get("primary", {}), ensure_ascii=False, separators=(",", ":")),
                    "provenance_json": json.dumps(row.get("pass_provenance", []), ensure_ascii=False, separators=(",", ":")),
                }
            )
