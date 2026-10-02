from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import canonical_sha256, read_json, sha256_file


def roster_entry_core(session_slug: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "session_slug": session_slug,
        "sources": [
            {
                "source_id": item["source_id"],
                "path": str(Path(item["path"]).resolve()),
                "sha256": item["sha256"],
                "characters": item["characters"],
            }
            for item in sorted(sources, key=lambda value: value["source_id"])
        ],
    }


def bind_roster_entry(session_slug: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    core = roster_entry_core(session_slug, sources)
    return {**core, "roster_entry_sha256": canonical_sha256(core)}


def run_contract_core(
    *,
    run_id: str,
    instance_key: str,
    contract: dict[str, Any],
    sessions_root: str,
    selection: dict[str, Any],
    passes: list[dict[str, Any]],
    roster: list[dict[str, Any]],
    extraction_mode: str | None = None,
) -> dict[str, Any]:
    core = {
        "run_id": run_id,
        "instance_key": instance_key,
        "contract": contract,
        "sessions_root": str(Path(sessions_root).resolve()),
        "selection": selection,
        "passes": [
            {
                "pass_number": int(item["pass_number"]),
                "pass_id": str(item["pass_id"]),
            }
            for item in sorted(passes, key=lambda item: int(item["pass_number"]))
        ],
        "roster": sorted(roster, key=lambda item: item["session_slug"]),
    }
    if extraction_mode is not None:
        core["extraction_mode"] = extraction_mode
    return core


def finalize_run_manifest(manifest_core: dict[str, Any], operational: dict[str, Any]) -> dict[str, Any]:
    run_contract_sha256 = canonical_sha256(manifest_core)
    body = {
        "run_manifest_version": "tgc-run-manifest/3.0.0",
        **manifest_core,
        "run_contract_sha256": run_contract_sha256,
        "operational": operational,
    }
    return {**body, "run_manifest_sha256": canonical_sha256(body)}


def verify_run_manifest(value: dict[str, Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if value.get("run_manifest_version") != "tgc-run-manifest/3.0.0":
        issues.append(
            {
                "code": "RUN_MANIFEST_VERSION",
                "path": "$",
                "message": str(value.get("run_manifest_version")),
            }
        )
        return issues
    body = dict(value)
    declared_self = body.pop("run_manifest_sha256", None)
    observed_self = canonical_sha256(body)
    if declared_self != observed_self:
        issues.append(
            {
                "code": "RUN_MANIFEST_SELF_HASH",
                "path": "$.run_manifest_sha256",
                "message": f"declared {declared_self}, observed {observed_self}",
            }
        )
    core = run_contract_core(
        run_id=value.get("run_id", ""),
        instance_key=value.get("instance_key", ""),
        contract=value.get("contract", {}),
        sessions_root=value.get("sessions_root", ""),
        selection=value.get("selection", {}),
        passes=value.get("passes", []),
        roster=value.get("roster", []),
        extraction_mode=value.get("extraction_mode"),
    )
    observed_contract = canonical_sha256(core)
    if value.get("run_contract_sha256") != observed_contract:
        issues.append(
            {
                "code": "RUN_CONTRACT_HASH",
                "path": "$.run_contract_sha256",
                "message": f"declared {value.get('run_contract_sha256')}, observed {observed_contract}",
            }
        )
    seen_slugs: set[str] = set()
    for index, entry in enumerate(value.get("roster", [])):
        slug = entry.get("session_slug")
        if slug in seen_slugs:
            issues.append(
                {
                    "code": "RUN_ROSTER_DUPLICATE",
                    "path": f"$.roster[{index}].session_slug",
                    "message": str(slug),
                }
            )
        seen_slugs.add(str(slug))
        core_entry = roster_entry_core(str(slug), entry.get("sources", []))
        observed = canonical_sha256(core_entry)
        if entry.get("roster_entry_sha256") != observed:
            issues.append(
                {
                    "code": "RUN_ROSTER_ENTRY_HASH",
                    "path": f"$.roster[{index}].roster_entry_sha256",
                    "message": f"declared {entry.get('roster_entry_sha256')}, observed {observed}",
                }
            )
    seen_passes: set[int] = set()
    seen_ids: set[str] = set()
    for index, item in enumerate(value.get("passes", [])):
        number = item.get("pass_number")
        pass_id = item.get("pass_id")
        if not isinstance(number, int) or isinstance(number, bool) or number not in {1, 2, 3}:
            issues.append(
                {
                    "code": "RUN_PASS_NUMBER",
                    "path": f"$.passes[{index}].pass_number",
                    "message": str(number),
                }
            )
        elif number in seen_passes:
            issues.append(
                {
                    "code": "RUN_PASS_DUPLICATE",
                    "path": f"$.passes[{index}].pass_number",
                    "message": str(number),
                }
            )
        seen_passes.add(number)
        if not isinstance(pass_id, str) or not pass_id or pass_id in seen_ids:
            issues.append(
                {
                    "code": "RUN_PASS_ID",
                    "path": f"$.passes[{index}].pass_id",
                    "message": str(pass_id),
                }
            )
        seen_ids.add(str(pass_id))
    mode = value.get("extraction_mode")
    if mode not in {None, "single"} or (mode == "single" and seen_passes != {1}):
        issues.append({"code": "RUN_EXTRACTION_MODE", "path": "$.extraction_mode",
                       "message": "single extraction requires exactly pass 1"})
    return issues


def load_and_verify_run_manifest(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    try:
        value = read_json(path)
    except Exception as error:
        return None, [{"code": "RUN_MANIFEST_JSON", "path": "$", "message": str(error)}]
    return value, verify_run_manifest(value)


def find_roster_entry(manifest: dict[str, Any], session_slug: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in manifest.get("roster", [])
            if item.get("session_slug") == session_slug
        ),
        None,
    )


def find_pass(manifest: dict[str, Any], pass_number: int) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in manifest.get("passes", [])
            if item.get("pass_number") == pass_number
        ),
        None,
    )


def file_binding(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }
