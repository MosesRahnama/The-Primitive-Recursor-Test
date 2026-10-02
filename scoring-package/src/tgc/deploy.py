from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .common import (
    canonical_sha256,
    read_json,
    read_text,
    resolve_profile_path,
    sha256_file,
    write_json_atomic,
    write_text_atomic,
)
from .config import InstanceContract

CLAIMS_PLACEHOLDER = (
    "<FILL: replace this entire array with zero or more complete claim objects "
    "copied from contract/templates/<kind>.json; use [] when no construction claim is present>"
)


def select_sessions(
    sessions_root: Path,
    selection: dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> list[str]:
    slugs = sorted(path.name for path in sessions_root.iterdir() if path.is_dir())
    excluded_markers = selection.get("exclude_slug_contains", [])
    slugs = [
        slug
        for slug in slugs
        if not any(marker in slug for marker in excluded_markers)
    ]
    # Successive-round support (2026-07-27): exclude explicit slugs and/or the
    # rosters of prior run manifests, so iterated randomized rounds sample
    # fresh sessions deterministically.
    excluded_slugs = set(selection.get("exclude_slugs", []))
    for manifest_path in selection.get("exclude_rosters_from_manifests", []):
        path = (
            resolve_profile_path(base_dir, manifest_path)
            if base_dir is not None
            else Path(manifest_path).expanduser().resolve()
        )
        manifest = read_json(path)
        excluded_slugs.update(
            item["session_slug"] for item in manifest.get("roster", [])
        )
    if excluded_slugs:
        slugs = [slug for slug in slugs if slug not in excluded_slugs]
    strategy = selection.get("strategy", "all")
    size = selection.get("size")
    if strategy == "random_seeded":
        # Deterministic randomized subset: same seed + same eligible pool =>
        # same selection, reproducible in the run manifest forever.
        import random as _random

        seed = selection.get("seed")
        if not isinstance(seed, int):
            raise ValueError(
                "random_seeded selection requires an integer 'seed'"
            )
        rng = _random.Random(seed)
        count = int(size) if size is not None else len(slugs)
        if count > len(slugs):
            raise ValueError(
                f"random_seeded size {count} exceeds eligible pool {len(slugs)}"
            )
        return sorted(rng.sample(slugs, count))
    if strategy == "explicit":
        # Paired A/B rounds: re-deploy an EXACT prior roster under a changed contract, so the
        # comparison isolates the contract change instead of confounding it with a fresh
        # sample. This matters because a 30-session round is a blunt instrument — its 95%
        # interval spans roughly +/-17 points, so an unpaired round-to-round difference of a
        # few sessions is indistinguishable from noise, while a paired design makes each
        # session its own control. Fail closed on any slug missing from the eligible pool so a
        # typo, an exclusion marker, or a purged session can never silently shrink the round
        # and turn a paired comparison into an unpaired one.
        wanted = list(selection.get("slugs") or [])
        if not wanted:
            raise ValueError("explicit selection requires a non-empty 'slugs' list")
        missing = sorted(set(wanted) - set(slugs))
        if missing:
            raise ValueError(
                f"explicit selection: {len(missing)} slug(s) not in the eligible pool "
                f"(first: {missing[:3]})"
            )
        return sorted(set(wanted))
    if strategy == "all":
        picked = slugs
    elif strategy == "model_round_robin":
        delimiter = selection.get("model_delimiter", "__")
        by_model: dict[str, list[str]] = {}
        for slug in slugs:
            by_model.setdefault(slug.split(delimiter)[0], []).append(slug)
        picked: list[str] = []
        depth = 0
        while True:
            added = False
            for model in sorted(by_model):
                runs = by_model[model]
                if depth < len(runs):
                    picked.append(runs[depth])
                    added = True
                    if size is not None and len(picked) >= int(size):
                        return sorted(picked)
            if not added:
                break
            depth += 1
    else:
        raise ValueError(f"unknown selection strategy {strategy!r}")
    if size is not None:
        picked = picked[: int(size)]
    return sorted(picked)


def source_binding(contract: InstanceContract, session_dir: Path) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for source_id in contract.response_files:
        path = session_dir / source_id
        if not path.exists():
            raise FileNotFoundError(path)
        text = read_text(path)
        sources.append(
            {
                "source_id": source_id,
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
                "characters": len(text),
            }
        )
    return sources


def seed_record(
    contract: InstanceContract,
    *,
    session_slug: str,
    session_dir: Path,
    pass_number: int,
) -> dict[str, Any]:
    return {
        "schema_version": contract.schema_version,
        "contract": contract.binding(),
        "session": {
            "session_slug": session_slug,
            "sources": source_binding(contract, session_dir),
        },
        "extractor": {
            "pass_number": pass_number,
            "extractor_id": "<FILL: stable extractor/agent identifier>",
            "run_id": "<FILL: unique run identifier for this dispatched pass>",
            "independence_attestation": "<FILL: true after confirming no access to other passes, gates, scores, or prior extraction outputs>",
        },
        "record_status": "<FILL: complete | refused | truncated | file_missing | garbled>",
        "claims": [CLAIMS_PLACEHOLDER],
        "primary": {
            "status": "<FILL: single | coequal | none | unclear>",
            "claim_ids": ["<FILL: local_id values; [] for none or unclear>"],
        },
        "notes": "",
    }


def write_seed_dir(
    contract: InstanceContract,
    *,
    destination: Path,
    sessions_root: Path,
    slugs: list[str],
    pass_number: int,
) -> tuple[int, int]:
    destination.mkdir(parents=True, exist_ok=True)
    created = 0
    preserved = 0
    for slug in slugs:
        path = destination / f"{slug}.json"
        if path.exists():
            preserved += 1
            continue
        write_json_atomic(
            path,
            seed_record(
                contract,
                session_slug=slug,
                session_dir=sessions_root / slug,
                pass_number=pass_number,
            ),
        )
        created += 1
    return created, preserved


def _copy_contract(source: Path, destination: Path) -> InstanceContract:
    source_contract = InstanceContract.load(source)
    if destination.exists():
        existing = InstanceContract.load(destination)
        if existing.manifest_sha256 != source_contract.manifest_sha256:
            raise ValueError(
                f"refusing to replace a different deployed contract at {destination}"
            )
        return existing
    shutil.copytree(source, destination)
    return InstanceContract.load(destination)


def _write_generated_text(path: Path, text: str) -> None:
    if path.exists():
        observed = read_text(path)
        if observed != text:
            raise ValueError(f"refusing to replace drifted generated file: {path}")
        return
    write_text_atomic(path, text)


def _dispatch_text(
    contract: InstanceContract,
    *,
    extraction_dir: Path,
    pass_number: int,
    run_id: str,
) -> str:
    prompt_path = contract.contract_dir / "EXTRACTOR_PROMPT_V2.md"
    prompt = read_text(prompt_path)
    return (
        prompt.replace("<CONTRACT_DIR>", str(contract.contract_dir))
        .replace("<ASSIGNED_DIR>", str(extraction_dir))
        .replace("<PASS_NUMBER>", str(pass_number))
        .replace("<RUN_ID>", run_id)
    )


def deploy_profile(profile_path: Path) -> dict[str, Any]:
    profile_path = profile_path.resolve()
    profile = read_json(profile_path)
    if profile.get("profile_version") == "tgc-deployment-profile/3.0.0":
        from .deploy_v3 import deploy_profile_v3

        return deploy_profile_v3(
            profile_path, select_sessions=select_sessions
        )
    if profile.get("profile_version") != "tgc-deployment-profile/2.0.0":
        raise ValueError("unsupported deployment profile version")
    base_dir = profile_path.parent
    source_contract_dir = resolve_profile_path(base_dir, profile["contract_dir"])
    sessions_root = resolve_profile_path(base_dir, profile["sessions_root"])
    run_dir = resolve_profile_path(base_dir, profile["run_dir"])
    run_dir.mkdir(parents=True, exist_ok=True)
    contract = _copy_contract(source_contract_dir, run_dir / "contract")
    if contract.instance_key != profile["instance_key"]:
        raise ValueError("profile instance_key does not match contract")
    slugs = select_sessions(
        sessions_root, profile["selection"], base_dir=base_dir
    )
    if not slugs:
        raise ValueError("deployment selected zero sessions")

    passes = [int(value) for value in profile.get("passes", [1, 2])]
    seed_results: dict[str, Any] = {}
    dispatch_files: dict[str, str] = {}
    for pass_number in passes:
        extraction_dir = run_dir / "extraction" / f"e{pass_number:02d}"
        created, preserved = write_seed_dir(
            contract,
            destination=extraction_dir,
            sessions_root=sessions_root,
            slugs=slugs,
            pass_number=pass_number,
        )
        seed_results[str(pass_number)] = {
            "directory": str(extraction_dir),
            "created": created,
            "preserved": preserved,
        }
        dispatch_path = run_dir / "dispatch" / f"EXTRACTOR_{pass_number:02d}.md"
        _write_generated_text(
            dispatch_path,
            _dispatch_text(
                contract,
                extraction_dir=extraction_dir,
                pass_number=pass_number,
                run_id=profile["run_id"],
            ),
        )
        dispatch_files[str(pass_number)] = str(dispatch_path)

    roster = [
        {
            "session_slug": slug,
            "sources": source_binding(contract, sessions_root / slug),
        }
        for slug in slugs
    ]
    manifest_core = {
        "run_manifest_version": "tgc-run-manifest/2.0.0",
        "run_id": profile["run_id"],
        "instance_key": contract.instance_key,
        "contract": contract.binding(),
        "profile_sha256": sha256_file(profile_path),
        "sessions_root": str(sessions_root),
        "selection": profile["selection"],
        "passes": passes,
        "roster": roster,
        "extraction_directories": {
            str(pass_number): str((run_dir / "extraction" / f"e{pass_number:02d}").resolve())
            for pass_number in passes
        },
        "dispatch_files": dispatch_files,
    }
    manifest = {
        **manifest_core,
        "run_manifest_sha256": canonical_sha256(manifest_core),
    }
    manifest_path = run_dir / "RUN_MANIFEST.json"
    if manifest_path.exists():
        observed = read_json(manifest_path)
        if observed != manifest:
            raise ValueError(
                f"refusing to mutate an existing run manifest whose bound inputs changed: {manifest_path}"
            )
    else:
        write_json_atomic(manifest_path, manifest)
    # Operational counts are returned to the caller but deliberately excluded
    # from the immutable run manifest: created/preserved changes on a harmless
    # idempotent re-deployment, while the bound run plan must not.
    return {**manifest, "seed_results": seed_results}
