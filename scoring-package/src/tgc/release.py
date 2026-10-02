from __future__ import annotations

import json
import re
import shutil
import tempfile
import tomllib
import zipfile
from pathlib import Path
from typing import Any

from .common import (
    canonical_sha256,
    read_json,
    resolve_within,
    retired_forward_schema_hits,
    sha256_file,
    stable_relative,
    validate_archive_member,
    write_json_atomic,
)
from .config import InstanceContract

DEFAULT_INCLUDE = (
    "README.md",
    "CHANGELOG.md",
    "SELECTIVE-SCORING.md",
    "SINGLE-EXTRACTOR.md",
    "EVALUATION_DOSSIER.md",
    "LICENSE.md",
    "PRODUCTION_SCORING_ENGINE.md",
    "LEGACY_COMPATIBILITY.md",
    "run_prt_scoring_engine.ps1",
    "pyproject.toml",
    "src/tgc",
    "authorities",
    "spec/generate_v3.py",
    "spec/v3",
    "spec/generated",
    "docs/README.md",
    "docs/01-ARCHITECTURE.md",
    "docs/02-ADAPTATION-GUIDE.md",
    "docs/03-EXTRACTION-PROMPTS.md",
    "docs/04-PITFALLS.md",
    "docs/05-CONSTRUCTION-CATALOG.md",
    "docs/07-RELEASE-PROTOCOL.md",
    "docs/09-TRANSFERABILITY-KIT.md",
    "docs/10-ADAPTER-SPECIFICATION.md",
    "docs/11-SECURITY-TRUST-BOUNDARIES.md",
    "transferability",
    "pilot/vendor",
    "pilot/r7_pilot_score.py",
    "pilot-t01/vendor",
    "pilot-t01/r7_t01_score.py",
)

LEGACY_REPLAY_INCLUDE = DEFAULT_INCLUDE + (
    "docs/06-TGC-V2-DESIGN.md",
    "docs/06-V2-MODULAR-ARCHITECTURE.md",
    "docs/07-V2-EXTRACTION-CONTRACT.md",
    "docs/08-MIGRATION-FROM-V1.md",
    "docs/08-V2-RELEASE-PROTOCOL.md",
    "spec/README.md",
    "spec/benchmark_spec.json",
    "spec/generate.py",
    "spec/generate_v2.py",
    "spec/validate.py",
    "pilot/r7_pilot_gate.py",
    "pilot-t01/r7_t01_gate.py",
)

FORWARD_V3_PROFILE = "forward_v3"
LEGACY_REPLAY_PROFILE = "legacy_replay"

TRANSIENT_DIRECTORY_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
TRANSIENT_FILE_NAMES = {".DS_Store", "Thumbs.db"}
TRANSIENT_SUFFIXES = {".pyc", ".pyo"}
GENERATED_RELEASE_METADATA = {
    "ARTIFACT_METADATA.json",
    "SBOM.json",
    "SOURCE_MANIFEST.json",
    "RELEASE_MANIFEST.json",
}


def _copy_manifest_asset(
    generated: Path,
    destination: Path,
    relative: str,
) -> None:
    source = resolve_within(
        generated,
        relative,
        label="generated release asset",
        must_exist=True,
    )
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"generated release asset is not a regular file: {source}")
    target = resolve_within(
        destination,
        relative,
        label="generated release destination",
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _legacy_asset_entries(generated: Path) -> dict[str, str]:
    manifest = read_json(generated / "assets_manifest.json")
    if not isinstance(manifest, dict):
        return {}
    raw_assets = manifest.get("assets", {})
    if not isinstance(raw_assets, dict):
        return {}
    return {
        str(relative): str(wanted)
        for relative, wanted in raw_assets.items()
        if "/v3/" not in f"/{relative}"
    }


def _copy_generated_assets(
    root: Path,
    stage: Path,
    *,
    include_legacy_replay: bool,
) -> None:
    generated = root / "spec" / "generated"
    destination = stage / "spec" / "generated"
    v3_manifest_path = generated / "v3_assets_manifest.json"
    if v3_manifest_path.is_symlink():
        raise ValueError(f"generated manifest may not be a symlink: {v3_manifest_path}")
    v3_manifest = read_json(v3_manifest_path)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(v3_manifest_path, destination / v3_manifest_path.name)
    for relative in sorted(v3_manifest.get("assets", {})):
        _copy_manifest_asset(generated, destination, str(relative))

    if include_legacy_replay:
        legacy_assets = _legacy_asset_entries(generated)
        for relative in sorted(legacy_assets):
            _copy_manifest_asset(generated, destination, relative)
        legacy_core = {
            "generated_manifest_version": "tgc-legacy-replay-assets/1.0.0",
            "source_manifest_repository_path": (
                "spec/generated/assets_manifest.json"
            ),
            "source_manifest_sha256": sha256_file(
                generated / "assets_manifest.json"
            ),
            "assets": legacy_assets,
        }
        write_json_atomic(
            destination / "legacy_replay_assets_manifest.json",
            {
                **legacy_core,
                "generated_manifest_sha256": canonical_sha256(legacy_core),
            },
        )


def _copy_entry(
    root: Path,
    stage: Path,
    relative: str,
    *,
    include_legacy_replay: bool = False,
) -> None:
    if relative == "spec/generated":
        _copy_generated_assets(
            root,
            stage,
            include_legacy_replay=include_legacy_replay,
        )
        return
    source = resolve_within(
        root, relative, label="release include", must_exist=True
    )
    destination = resolve_within(stage, relative, label="release destination")
    if source.is_symlink():
        raise ValueError(f"release include may not be a symlink: {source}")
    if source.is_dir():
        symlinks = sorted(
            path.relative_to(source).as_posix()
            for path in source.rglob("*")
            if path.is_symlink()
        )
        if symlinks:
            raise ValueError(
                f"release include contains symlinks: {relative}: {symlinks}"
            )
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "gen_*",
                "output",
                ".pytest_cache",
            ),
        )
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _is_transient_runtime_path(path: Path, root: Path) -> bool:
    relative = path.resolve().relative_to(root.resolve())
    return (
        any(part in TRANSIENT_DIRECTORY_NAMES for part in relative.parts)
        or path.name in TRANSIENT_FILE_NAMES
        or path.suffix.lower() in TRANSIENT_SUFFIXES
    )


def _file_table(
    root: Path,
    *,
    exclude_names: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    excluded = exclude_names or set()
    symlinks = sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_symlink()
    )
    if symlinks:
        raise ValueError(f"file table root contains symlinks: {symlinks}")
    return {
        stable_relative(path, root): {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name not in excluded
        and not _is_transient_runtime_path(path, root)
    }


def _verify_asset_hashes(
    generated: Path,
    assets: dict[str, Any],
    issues: list[dict[str, str]],
    *,
    code_prefix: str,
) -> None:
    for relative, wanted in sorted(assets.items()):
        try:
            path = resolve_within(
                generated,
                relative,
                label="generated asset",
                must_exist=True,
            )
        except Exception as error:
            issues.append(
                {
                    "code": f"{code_prefix}_ASSET_PATH",
                    "path": str(relative),
                    "message": str(error),
                }
            )
            continue
        if path.is_symlink():
            issues.append(
                {
                    "code": f"{code_prefix}_ASSET_SYMLINK",
                    "path": str(relative),
                    "message": "symlinks are forbidden",
                }
            )
            continue
        if not path.is_file():
            issues.append(
                {
                    "code": f"{code_prefix}_ASSET_MISSING",
                    "path": str(relative),
                    "message": "missing",
                }
            )
            continue
        observed = sha256_file(path)
        if observed != wanted:
            issues.append(
                {
                    "code": f"{code_prefix}_ASSET_HASH",
                    "path": str(relative),
                    "message": f"expected {wanted}, observed {observed}",
                }
            )


def _verify_generated_assets(
    package_root: Path,
    *,
    include_legacy_replay: bool = False,
) -> dict[str, Any]:
    generated = package_root / "spec" / "generated"
    v3_manifest_path = generated / "v3_assets_manifest.json"
    issues: list[dict[str, str]] = []
    contracts: dict[str, dict[str, Any]] = {}
    v3_manifest: dict[str, Any] = {}
    v3_assets: dict[str, str] = {}
    if not v3_manifest_path.is_file():
        issues.append(
            {
                "code": "V3_GENERATED_MANIFEST_MISSING",
                "path": "spec/generated/v3_assets_manifest.json",
                "message": "missing",
            }
        )
    else:
        if v3_manifest_path.is_symlink():
            issues.append(
                {
                    "code": "V3_GENERATED_MANIFEST_SYMLINK",
                    "path": "spec/generated/v3_assets_manifest.json",
                    "message": "symlinks are forbidden",
                }
            )
        loaded_v3_manifest = read_json(v3_manifest_path)
        if not isinstance(loaded_v3_manifest, dict):
            issues.append(
                {
                    "code": "V3_GENERATED_MANIFEST_SHAPE",
                    "path": "spec/generated/v3_assets_manifest.json",
                    "message": "manifest must be an object",
                }
            )
            loaded_v3_manifest = {}
        v3_manifest = loaded_v3_manifest
        if (
            v3_manifest.get("generated_manifest_version")
            != "tgc-v3-generated-assets/3.0.0"
        ):
            issues.append(
                {
                    "code": "V3_GENERATED_MANIFEST_VERSION",
                    "path": "spec/generated/v3_assets_manifest.json",
                    "message": repr(
                        v3_manifest.get("generated_manifest_version")
                    ),
                }
            )
        core = dict(v3_manifest)
        declared = core.pop("generated_manifest_sha256", None)
        observed = canonical_sha256(core)
        if declared != observed:
            issues.append(
                {
                    "code": "V3_GENERATED_MANIFEST_HASH",
                    "path": "spec/generated/v3_assets_manifest.json",
                    "message": f"expected {declared}, observed {observed}",
                }
            )

        raw_v3_assets = v3_manifest.get("assets", {})
        if not isinstance(raw_v3_assets, dict):
            issues.append(
                {
                    "code": "V3_GENERATED_MANIFEST_ASSETS",
                    "path": "spec/generated/v3_assets_manifest.json",
                    "message": "assets must be an object",
                }
            )
            raw_v3_assets = {}
        v3_assets = {
            str(relative): str(wanted)
            for relative, wanted in raw_v3_assets.items()
        }
        _verify_asset_hashes(
            generated,
            v3_assets,
            issues,
            code_prefix="V3_GENERATED",
        )

        source_root = package_root / "spec" / "v3"
        raw_source_hashes = v3_manifest.get("source_hashes", {})
        if not isinstance(raw_source_hashes, dict):
            issues.append(
                {
                    "code": "V3_GENERATED_MANIFEST_SOURCES",
                    "path": "spec/generated/v3_assets_manifest.json",
                    "message": "source_hashes must be an object",
                }
            )
            raw_source_hashes = {}
        declared_sources = {
            str(relative): str(wanted)
            for relative, wanted in raw_source_hashes.items()
        }
        actual_sources = {
            stable_relative(path, source_root)
            for path in source_root.rglob("*.json")
            if path.is_file()
        }
        if set(declared_sources) != actual_sources:
            issues.append(
                {
                    "code": "V3_SOURCE_FILE_SET",
                    "path": "spec/v3",
                    "message": (
                        f"missing={sorted(set(declared_sources)-actual_sources)} "
                        f"extra={sorted(actual_sources-set(declared_sources))}"
                    ),
                }
            )
        for relative, wanted in sorted(declared_sources.items()):
            try:
                source_path = resolve_within(
                    source_root,
                    relative,
                    label="v3 source",
                    must_exist=True,
                )
            except Exception as error:
                issues.append(
                    {
                        "code": "V3_SOURCE_PATH",
                        "path": str(relative),
                        "message": str(error),
                    }
                )
                continue
            observed_source = sha256_file(source_path)
            if observed_source != wanted:
                issues.append(
                    {
                        "code": "V3_SOURCE_HASH",
                        "path": stable_relative(source_path, package_root),
                        "message": (
                            f"expected {wanted}, observed {observed_source}"
                        ),
                    }
                )

        expected_v3_files = set(v3_assets)
        actual_v3_files = {
            stable_relative(path, generated)
            for path in generated.rglob("*")
            if path.is_file()
            and len(path.relative_to(generated).parts) >= 3
            and path.relative_to(generated).parts[1] == "v3"
        }
        if expected_v3_files != actual_v3_files:
            issues.append(
                {
                    "code": "V3_GENERATED_FILE_SET",
                    "path": "spec/generated",
                    "message": (
                        f"missing={sorted(expected_v3_files-actual_v3_files)} "
                        f"extra={sorted(actual_v3_files-expected_v3_files)}"
                    ),
                }
            )

        instance_keys = sorted(
            {
                relative.split("/", 1)[0]
                for relative in v3_assets
                if relative.endswith("/v3/contract_manifest.json")
            }
        )
        for instance_key in instance_keys:
            contract_dir = generated / instance_key / "v3"
            try:
                contract = InstanceContract.load(contract_dir)
            except Exception as error:
                issues.append(
                    {
                        "code": "CONTRACT_INVALID",
                        "path": stable_relative(contract_dir, package_root),
                        "message": str(error),
                    }
                )
                continue
            contracts[f"{instance_key}/v3"] = {
                "manifest_sha256": contract.manifest_sha256,
                "config_version": contract.config_version,
                "schema_version": contract.schema_version,
                "modular_registry_sha256": contract.modular_registry_sha256,
            }

        try:
            from .contractgen import generate_from_roots

            with tempfile.TemporaryDirectory() as temporary:
                regenerated_root = Path(temporary) / "generated"
                regenerated = generate_from_roots(
                    source_root,
                    regenerated_root,
                    artifact_root=package_root,
                )
                if regenerated != v3_manifest:
                    issues.append(
                        {
                            "code": "V3_REGENERATION_MANIFEST_DRIFT",
                            "path": "spec/generated/v3_assets_manifest.json",
                            "message": (
                                f"committed={canonical_sha256(v3_manifest)} "
                                f"regenerated={canonical_sha256(regenerated)}"
                            ),
                        }
                    )
                regenerated_manifest_path = (
                    regenerated_root / "v3_assets_manifest.json"
                )
                if (
                    regenerated_manifest_path.read_bytes()
                    != v3_manifest_path.read_bytes()
                ):
                    issues.append(
                        {
                            "code": "V3_REGENERATION_MANIFEST_BYTES",
                            "path": "spec/generated/v3_assets_manifest.json",
                            "message": "temporary regeneration is not byte-identical",
                        }
                    )
                for relative, wanted in sorted(v3_assets.items()):
                    regenerated_path = regenerated_root / relative
                    if (
                        not regenerated_path.is_file()
                        or sha256_file(regenerated_path) != wanted
                    ):
                        issues.append(
                            {
                                "code": "V3_REGENERATION_ASSET_DRIFT",
                                "path": str(relative),
                                "message": "temporary regeneration differs",
                            }
                        )
                regenerated_files = {
                    stable_relative(path, regenerated_root)
                    for path in regenerated_root.rglob("*")
                    if path.is_file()
                }
                expected_regenerated_files = {
                    "v3_assets_manifest.json",
                    *v3_assets,
                }
                if regenerated_files != expected_regenerated_files:
                    issues.append(
                        {
                            "code": "V3_REGENERATION_FILE_SET",
                            "path": "spec/generated",
                            "message": (
                                "temporary regeneration emitted an unexpected "
                                "file set"
                            ),
                        }
                    )
        except Exception as error:
            issues.append(
                {
                    "code": "V3_REGENERATION_FAILED",
                    "path": "spec/v3",
                    "message": str(error),
                }
            )

    legacy_assets: dict[str, str] = {}
    if include_legacy_replay:
        legacy_manifest_path = generated / "assets_manifest.json"
        if not legacy_manifest_path.is_file():
            issues.append(
                {
                    "code": "LEGACY_GENERATED_MANIFEST_MISSING",
                    "path": "spec/generated/assets_manifest.json",
                    "message": "missing",
                }
            )
        else:
            if legacy_manifest_path.is_symlink():
                issues.append(
                    {
                        "code": "LEGACY_GENERATED_MANIFEST_SYMLINK",
                        "path": "spec/generated/assets_manifest.json",
                        "message": "symlinks are forbidden",
                    }
                )
            loaded_legacy_manifest = read_json(legacy_manifest_path)
            if not isinstance(loaded_legacy_manifest, dict):
                issues.append(
                    {
                        "code": "LEGACY_GENERATED_MANIFEST_SHAPE",
                        "path": "spec/generated/assets_manifest.json",
                        "message": "manifest must be an object",
                    }
                )
                loaded_legacy_manifest = {}
            legacy_manifest = loaded_legacy_manifest
            if not isinstance(legacy_manifest.get("assets", {}), dict):
                issues.append(
                    {
                        "code": "LEGACY_GENERATED_MANIFEST_ASSETS",
                        "path": "spec/generated/assets_manifest.json",
                        "message": "assets must be an object",
                    }
                )
            legacy_assets = _legacy_asset_entries(generated)
            _verify_asset_hashes(
                generated,
                legacy_assets,
                issues,
                code_prefix="LEGACY_GENERATED",
            )
            spec_relative = str(
                legacy_manifest.get("spec_file", "benchmark_spec.json")
            )
            spec_parts = Path(spec_relative).parts
            candidate = (
                spec_relative
                if spec_parts and spec_parts[0] == "spec"
                else f"spec/{spec_relative}"
            )
            wanted_spec = legacy_manifest.get("spec_sha256")
            try:
                spec_file = resolve_within(
                    package_root,
                    candidate,
                    label="legacy specification",
                    must_exist=True,
                )
                observed_spec = sha256_file(spec_file)
            except Exception as error:
                issues.append(
                    {
                        "code": "LEGACY_SOURCE_PATH",
                        "path": candidate,
                        "message": str(error),
                    }
                )
                observed_spec = None
            if observed_spec != wanted_spec:
                issues.append(
                    {
                        "code": "LEGACY_SOURCE_HASH",
                        "path": candidate,
                        "message": (
                            f"expected {wanted_spec}, observed {observed_spec}"
                        ),
                    }
                )
            for relative in sorted(legacy_assets):
                if not relative.endswith("/v2/contract_manifest.json"):
                    continue
                contract_dir = generated / Path(relative).parent
                try:
                    contract = InstanceContract.load(contract_dir)
                except Exception as error:
                    issues.append(
                        {
                            "code": "LEGACY_CONTRACT_INVALID",
                            "path": stable_relative(
                                contract_dir, package_root
                            ),
                            "message": str(error),
                        }
                    )
                    continue
                contracts[
                    f"{Path(relative).parts[0]}/v2"
                ] = {
                    "manifest_sha256": contract.manifest_sha256,
                    "config_version": contract.config_version,
                    "schema_version": contract.schema_version,
                    "modular_registry_sha256": (
                        contract.modular_registry_sha256
                    ),
                }
    return {
        "valid": not issues,
        "profile": (
            LEGACY_REPLAY_PROFILE
            if include_legacy_replay
            else FORWARD_V3_PROFILE
        ),
        "asset_count": len(v3_assets) + len(legacy_assets),
        "v3_asset_count": len(v3_assets),
        "legacy_asset_count": len(legacy_assets),
        "contracts": contracts,
        "issues": issues,
    }


def _verify_forward_schema_surfaces(package_root: Path) -> list[dict[str, str]]:
    roots = [
        package_root / "spec" / "v3",
        package_root / "transferability" / "starter_adapter" / "spec",
    ]
    generated_roots = (
        package_root / "spec" / "generated",
        package_root
        / "transferability"
        / "starter_adapter"
        / "generated",
    )
    for generated_root in generated_roots:
        if not generated_root.is_dir():
            continue
        roots.extend(
            path / "v3"
            for path in sorted(generated_root.iterdir())
            if path.is_dir() and (path / "v3").is_dir()
        )

    issues: list[dict[str, str]] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".json", ".md"}:
                continue
            text = path.read_text(encoding="utf-8-sig")
            for token in retired_forward_schema_hits(text):
                issues.append(
                    {
                        "code": "FORWARD_SCHEMA_RETIRED_TOKEN",
                        "path": stable_relative(path, package_root),
                        "message": token,
                    }
                )
    return issues


def _declared_package_version(package_root: Path) -> tuple[str | None, str | None]:
    pyproject = tomllib.loads(
        (package_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project_version = pyproject.get("project", {}).get("version")
    init_text = (package_root / "src" / "tgc" / "__init__.py").read_text(
        encoding="utf-8-sig"
    )
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        init_text,
        flags=re.MULTILINE,
    )
    return (
        str(project_version) if project_version is not None else None,
        match.group(1) if match else None,
    )


def preflight_release(
    package_root: Path,
    *,
    expected_version: str | None = None,
    include: tuple[str, ...] | None = None,
    include_legacy_replay: bool = False,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    release_profile = (
        LEGACY_REPLAY_PROFILE
        if include_legacy_replay
        else FORWARD_V3_PROFILE
    )
    effective_include = (
        include
        if include is not None
        else LEGACY_REPLAY_INCLUDE
        if include_legacy_replay
        else DEFAULT_INCLUDE
    )
    generated = _verify_generated_assets(
        package_root,
        include_legacy_replay=include_legacy_replay,
    )
    pyproject = tomllib.loads(
        (package_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = pyproject.get("project", {})
    project_version, module_version = _declared_package_version(package_root)
    issues: list[dict[str, str]] = list(generated["issues"])
    forward_schema_issues = _verify_forward_schema_surfaces(package_root)
    issues.extend(forward_schema_issues)

    if not project_version or not module_version:
        issues.append(
            {
                "code": "PACKAGE_VERSION_MISSING",
                "path": "pyproject.toml/src/tgc/__init__.py",
                "message": (
                    f"project={project_version!r}, module={module_version!r}"
                ),
            }
        )
    elif project_version != module_version:
        issues.append(
            {
                "code": "PACKAGE_VERSION_DRIFT",
                "path": "pyproject.toml/src/tgc/__init__.py",
                "message": f"project={project_version}, module={module_version}",
            }
        )
    if expected_version is not None and project_version != expected_version:
        issues.append(
            {
                "code": "RELEASE_VERSION_MISMATCH",
                "path": "pyproject.toml",
                "message": (
                    f"requested={expected_version}, package={project_version}"
                ),
            }
        )
    changelog = (package_root / "CHANGELOG.md").read_text(encoding="utf-8-sig")
    changelog_version = expected_version or project_version
    if changelog_version and not re.search(
        rf"^##+\s+(?:\[)?{re.escape(changelog_version)}(?:\])?(?:\s|$)",
        changelog,
        flags=re.MULTILINE,
    ):
        issues.append(
            {
                "code": "CHANGELOG_VERSION_MISSING",
                "path": "CHANGELOG.md",
                "message": str(changelog_version),
            }
        )

    include_status: dict[str, dict[str, Any]] = {}
    for relative in effective_include:
        try:
            source = resolve_within(
                package_root,
                relative,
                label="release include",
                must_exist=True,
            )
        except Exception as error:
            issues.append(
                {
                    "code": "RELEASE_INCLUDE_PATH",
                    "path": relative,
                    "message": str(error),
                }
            )
            continue
        if relative == "spec/generated":
            # The generated tree is a curated manifest closure. Its selected
            # paths are checked above; excluded historical paths do not affect
            # a forward-v3 build.
            symlinks = []
        else:
            symlinks = (
                [source]
                if source.is_symlink()
                else [path for path in source.rglob("*") if path.is_symlink()]
                if source.is_dir()
                else []
            )
        if symlinks:
            issues.append(
                {
                    "code": "RELEASE_INCLUDE_SYMLINK",
                    "path": relative,
                    "message": repr(
                        sorted(
                            path.relative_to(package_root).as_posix()
                            for path in symlinks
                        )
                    ),
                }
            )
        include_status[relative] = {
            "type": "directory" if source.is_dir() else "file",
            "symlink_count": len(symlinks),
        }

    portable_source_issues: list[dict[str, str]] = []

    def walk_strings(value: Any, path: str = "$"):
        if isinstance(value, str):
            yield path, value
        elif isinstance(value, dict):
            for key, child in value.items():
                yield from walk_strings(child, f"{path}.{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from walk_strings(child, f"{path}[{index}]")

    portable_roots = [
        package_root / "spec" / "v3",
        package_root / "transferability" / "starter_adapter" / "spec",
    ]
    for portable_root in portable_roots:
        if not portable_root.is_dir():
            continue
        for source_path in sorted(portable_root.rglob("*.json")):
            try:
                source_value = read_json(source_path)
            except Exception as error:
                portable_source_issues.append(
                    {
                        "code": "PORTABLE_SOURCE_JSON",
                        "path": stable_relative(source_path, package_root),
                        "message": str(error),
                    }
                )
                continue
            if source_path.parent.name == "instances":
                for forbidden in ("sessions_root", "working_dir"):
                    if forbidden in source_value:
                        portable_source_issues.append(
                            {
                                "code": "PORTABLE_OPERATIONAL_FIELD",
                                "path": stable_relative(source_path, package_root),
                                "message": forbidden,
                            }
                        )
            for json_path, string_value in walk_strings(source_value):
                if (
                    (len(string_value) >= 3 and string_value[1:3] in {":\\", ":/"})
                    or string_value.startswith("/home/")
                    or string_value.startswith("/Users/")
                ):
                    portable_source_issues.append(
                        {
                            "code": "PORTABLE_ABSOLUTE_PATH",
                            "path": (
                                f"{stable_relative(source_path, package_root)}:{json_path}"
                            ),
                            "message": string_value,
                        }
                    )
    issues.extend(portable_source_issues)

    adapter_validation: dict[str, Any] | None = None
    adapter_selftest_result: dict[str, Any] | None = None
    starter = package_root / "transferability" / "starter_adapter"
    if "transferability" in effective_include and starter.is_dir():
        try:
            from .adapters import adapter_selftest, validate_adapter

            adapter_validation = validate_adapter(starter)
            if not adapter_validation["valid"]:
                issues.append(
                    {
                        "code": "STARTER_ADAPTER_INVALID",
                        "path": "transferability/starter_adapter",
                        "message": json.dumps(
                            adapter_validation["issues"], ensure_ascii=False
                        ),
                    }
                )
            adapter_selftest_result = adapter_selftest(starter)
            if not adapter_selftest_result["valid"]:
                issues.append(
                    {
                        "code": "STARTER_ADAPTER_SELFTEST",
                        "path": "transferability/starter_adapter",
                        "message": json.dumps(
                            adapter_selftest_result["issues"], ensure_ascii=False
                        ),
                    }
                )
        except Exception as error:
            issues.append(
                {
                    "code": "STARTER_ADAPTER_EXCEPTION",
                    "path": "transferability/starter_adapter",
                    "message": str(error),
                }
            )

    result = {
        "preflight_version": "tgc-release-preflight/3.3.0",
        "release_profile_version": "tgc-release-profile/1.0.0",
        "release_profile": release_profile,
        "package_name": project.get("name"),
        "package_version": project_version,
        "module_version": module_version,
        "expected_version": expected_version,
        "generated_assets": generated,
        "forward_schema_issues": forward_schema_issues,
        "include_status": include_status,
        "included_roots": list(effective_include),
        "portable_source_issues": portable_source_issues,
        "starter_adapter_validation": adapter_validation,
        "starter_adapter_selftest": adapter_selftest_result,
        "issues": issues,
    }
    result["valid"] = not issues
    result["preflight_sha256"] = canonical_sha256(result)
    return result


def _write_release_metadata(
    package_root: Path,
    stage: Path,
    *,
    version: str,
    include: tuple[str, ...],
    preflight: dict[str, Any],
) -> None:
    pyproject = tomllib.loads(
        (package_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project = pyproject.get("project", {})
    sbom_core = {
        "sbom_version": "tgc-sbom/3.0.0",
        "format": "TGC deterministic dependency inventory",
        "component": {
            "name": project.get("name"),
            "version": version,
            "requires_python": project.get("requires-python"),
            "license": project.get("license"),
        },
        "runtime_dependencies": project.get("dependencies", []),
        "optional_dependencies": project.get("optional-dependencies", {}),
        "build_system": pyproject.get("build-system", {}),
    }
    sbom = {**sbom_core, "sbom_sha256": canonical_sha256(sbom_core)}
    write_json_atomic(stage / "SBOM.json", sbom)

    metadata_core = {
        "artifact_metadata_version": "tgc-artifact-metadata/3.0.0",
        "artifact_name": "Transcribe-Gate-Certify",
        "artifact_version": version,
        "release_profile_version": "tgc-release-profile/1.0.0",
        "release_profile": preflight["release_profile"],
        "build_epoch_policy": "no wall-clock timestamp; ZIP timestamp fixed to 1980-01-01T00:00:00",
        "hash_algorithm": "SHA-256",
        "archive_order": "UTF-8 relative paths in lexicographic order",
        "included_roots": list(include),
        "preflight": preflight,
    }
    metadata = {
        **metadata_core,
        "artifact_metadata_sha256": canonical_sha256(metadata_core),
    }
    write_json_atomic(stage / "ARTIFACT_METADATA.json", metadata)

    source_core = {
        "source_manifest_version": "tgc-source-manifest/3.0.0",
        "files": _file_table(
            stage,
            exclude_names={"SOURCE_MANIFEST.json", "RELEASE_MANIFEST.json"},
        ),
    }
    source_manifest = {
        **source_core,
        "source_manifest_sha256": canonical_sha256(source_core),
    }
    write_json_atomic(stage / "SOURCE_MANIFEST.json", source_manifest)


def _manifest_core(
    stage: Path,
    version: str,
    *,
    release_profile: str,
) -> dict[str, Any]:
    files = _file_table(stage, exclude_names={"RELEASE_MANIFEST.json"})
    return {
        "release_manifest_version": "tgc-release-manifest/3.0.0",
        "artifact_name": "Transcribe-Gate-Certify",
        "artifact_version": version,
        "release_profile_version": "tgc-release-profile/1.0.0",
        "release_profile": release_profile,
        "file_count": len(files),
        "files": files,
    }


def _write_deterministic_zip(
    stage: Path, zip_path: Path, *, overwrite: bool = False
) -> None:
    if zip_path.exists() and not overwrite:
        raise FileExistsError(
            f"immutable release archive already exists: {zip_path}"
        )
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        zip_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        files = [
            path
            for path in stage.rglob("*")
            if path.is_file()
            and not _is_transient_runtime_path(path, stage)
        ]
        for path in sorted(
            files, key=lambda value: stable_relative(value, stage)
        ):
            relative = stable_relative(path, stage)
            info = zipfile.ZipInfo(relative)
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def verify_release_archive(
    archive_path: Path, stage: Path | None = None
) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    issues: list[dict[str, str]] = []
    with zipfile.ZipFile(archive_path, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        safe_names: set[str] = set()
        for name in names:
            try:
                safe_names.add(validate_archive_member(name))
            except ValueError as error:
                issues.append(
                    {
                        "code": "ARCHIVE_UNSAFE_ENTRY",
                        "message": str(error),
                    }
                )
        if len(names) != len(set(names)):
            issues.append(
                {
                    "code": "ARCHIVE_DUPLICATE_ENTRY",
                    "message": "archive contains duplicate names",
                }
            )
        if names != sorted(names):
            issues.append(
                {
                    "code": "ARCHIVE_ORDER",
                    "message": "archive entries are not lexicographically ordered",
                }
            )
        for info in infos:
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                issues.append(
                    {
                        "code": "ARCHIVE_TIMESTAMP",
                        "message": f"{info.filename}: {info.date_time}",
                    }
                )
            if info.compress_type != zipfile.ZIP_DEFLATED:
                issues.append(
                    {
                        "code": "ARCHIVE_COMPRESSION",
                        "message": info.filename,
                    }
                )
        if stage is not None:
            stage = stage.resolve()
            wanted = {
                stable_relative(path, stage): sha256_file(path)
                for path in stage.rglob("*")
                if path.is_file()
                and not _is_transient_runtime_path(path, stage)
            }
            if set(names) != set(wanted):
                issues.append(
                    {
                        "code": "ARCHIVE_FILE_SET",
                        "message": (
                            f"missing={sorted(set(wanted)-set(names))} "
                            f"extra={sorted(set(names)-set(wanted))}"
                        ),
                    }
                )
            for name in sorted(safe_names & set(wanted)):
                observed = __import__("hashlib").sha256(
                    archive.read(name)
                ).hexdigest()
                if observed != wanted[name]:
                    issues.append(
                        {
                            "code": "ARCHIVE_ENTRY_HASH",
                            "message": (
                                f"{name}: expected {wanted[name]}, observed {observed}"
                            ),
                        }
                    )
    return {
        "archive": str(archive_path),
        "valid": not issues,
        "archive_sha256": sha256_file(archive_path),
        "entry_count": len(names),
        "issues": issues,
    }


def build_release(
    package_root: Path,
    destination_root: Path,
    *,
    version: str,
    include: tuple[str, ...] | None = None,
    license_path: Path | None = None,
    include_legacy_replay: bool = False,
) -> dict[str, Any]:
    package_root = package_root.resolve()
    destination_root = destination_root.resolve()
    effective_include = (
        include
        if include is not None
        else LEGACY_REPLAY_INCLUDE
        if include_legacy_replay
        else DEFAULT_INCLUDE
    )
    preflight = preflight_release(
        package_root,
        expected_version=version,
        include=effective_include,
        include_legacy_replay=include_legacy_replay,
    )
    if not preflight["valid"]:
        raise ValueError(
            "release preflight failed: "
            + json.dumps(preflight["issues"], ensure_ascii=False)
        )
    artifact_stem = f"Transcribe-Gate-Certify-{version}"
    if include_legacy_replay:
        artifact_stem += "-legacy-replay"
    stage = destination_root / artifact_stem
    if stage.exists():
        raise FileExistsError(
            f"immutable release stage already exists: {stage}"
        )
    stage.mkdir(parents=True)
    try:
        for relative in effective_include:
            _copy_entry(
                package_root,
                stage,
                relative,
                include_legacy_replay=include_legacy_replay,
            )
        if license_path is not None:
            if not license_path.exists():
                raise FileNotFoundError(license_path)
            shutil.copy2(license_path, stage / "LICENSE.md")
        _write_release_metadata(
            package_root,
            stage,
            version=version,
            include=effective_include,
            preflight=preflight,
        )
        core = _manifest_core(
            stage,
            version,
            release_profile=preflight["release_profile"],
        )
        manifest = {
            **core,
            "release_manifest_sha256": canonical_sha256(core),
        }
        write_json_atomic(stage / "RELEASE_MANIFEST.json", manifest)
        verified_stage = verify_release(stage)
        if not verified_stage["valid"]:
            raise ValueError(
                "fresh release stage failed verification: "
                + json.dumps(verified_stage["issues"])
            )

        zip_path = destination_root / f"{artifact_stem}.zip"
        _write_deterministic_zip(stage, zip_path)
        with tempfile.TemporaryDirectory(dir=destination_root) as temporary:
            shadow = Path(temporary) / "shadow.zip"
            _write_deterministic_zip(stage, shadow)
            first_hash = sha256_file(zip_path)
            second_hash = sha256_file(shadow)
            if first_hash != second_hash:
                raise ValueError(
                    "deterministic archive double-build mismatch: "
                    f"{first_hash} != {second_hash}"
                )
        archive_verification = verify_release_archive(zip_path, stage)
        if not archive_verification["valid"]:
            raise ValueError(
                "fresh release archive failed verification: "
                + json.dumps(archive_verification["issues"])
            )
        result = {
            "release_result_version": "tgc-release-result/3.0.0",
            "release_profile_version": "tgc-release-profile/1.0.0",
            "release_profile": preflight["release_profile"],
            "stage": str(stage),
            "archive": str(zip_path),
            "archive_sha256": sha256_file(zip_path),
            "archive_reproducibility": {
                "first_sha256": first_hash,
                "second_sha256": second_hash,
                "byte_identical": first_hash == second_hash,
            },
            "archive_verification": archive_verification,
            "release_manifest_sha256": manifest[
                "release_manifest_sha256"
            ],
            "preflight_sha256": preflight["preflight_sha256"],
            "file_count": manifest["file_count"],
        }
        result["release_result_sha256"] = canonical_sha256(result)
        write_json_atomic(
            destination_root / f"{artifact_stem}.release.json",
            result,
        )
        return result
    except Exception:
        # A failed build never leaves a partially valid stage. The archive is
        # immutable once successful, but partial files are removed on failure.
        shutil.rmtree(stage, ignore_errors=True)
        partial_archive = destination_root / f"{artifact_stem}.zip"
        if partial_archive.exists():
            partial_archive.unlink()
        raise


def _verify_self_hashed_file(
    stage: Path,
    name: str,
    hash_field: str,
    expected_version: str,
    version_field: str,
) -> list[dict[str, str]]:
    path = stage / name
    if not path.is_file():
        return [
            {"code": "RELEASE_METADATA_MISSING", "message": name}
        ]
    value = read_json(path)
    issues: list[dict[str, str]] = []
    if value.get(version_field) != expected_version:
        issues.append(
            {
                "code": "RELEASE_METADATA_VERSION",
                "message": f"{name}: {value.get(version_field)}",
            }
        )
    core = dict(value)
    declared = core.pop(hash_field, None)
    observed = canonical_sha256(core)
    if declared != observed:
        issues.append(
            {
                "code": "RELEASE_METADATA_HASH",
                "message": f"{name}: declared {declared}, observed {observed}",
            }
        )
    return issues


def _verify_staged_profile(
    stage: Path,
    release_profile: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    generated = stage / "spec" / "generated"
    issues.extend(_verify_forward_schema_surfaces(stage))
    v3_result = _verify_generated_assets(stage)
    issues.extend(v3_result["issues"])
    v3_manifest_path = generated / "v3_assets_manifest.json"
    if not v3_manifest_path.is_file():
        return issues
    v3_manifest = read_json(v3_manifest_path)
    if not isinstance(v3_manifest, dict):
        return issues
    raw_v3_assets = v3_manifest.get("assets", {})
    if not isinstance(raw_v3_assets, dict):
        return issues
    expected_files = {
        "v3_assets_manifest.json",
        *map(str, raw_v3_assets),
    }

    if release_profile == LEGACY_REPLAY_PROFILE:
        legacy_path = generated / "legacy_replay_assets_manifest.json"
        if not legacy_path.is_file():
            issues.append(
                {
                    "code": "LEGACY_REPLAY_MANIFEST_MISSING",
                    "message": stable_relative(legacy_path, stage),
                }
            )
        else:
            legacy_manifest = read_json(legacy_path)
            if not isinstance(legacy_manifest, dict):
                issues.append(
                    {
                        "code": "LEGACY_REPLAY_MANIFEST_INVALID",
                        "message": "manifest must be an object",
                    }
                )
                return issues
            legacy_core = dict(legacy_manifest)
            declared = legacy_core.pop("generated_manifest_sha256", None)
            if (
                legacy_manifest.get("generated_manifest_version")
                != "tgc-legacy-replay-assets/1.0.0"
                or declared != canonical_sha256(legacy_core)
            ):
                issues.append(
                    {
                        "code": "LEGACY_REPLAY_MANIFEST_INVALID",
                        "message": "version or self-hash mismatch",
                    }
                )
            raw_legacy_assets = legacy_manifest.get("assets", {})
            if not isinstance(raw_legacy_assets, dict):
                raw_legacy_assets = {}
            legacy_assets = {
                str(relative): str(wanted)
                for relative, wanted in raw_legacy_assets.items()
            }
            _verify_asset_hashes(
                generated,
                legacy_assets,
                issues,
                code_prefix="LEGACY_REPLAY",
            )
            expected_files.update(legacy_assets)
            expected_files.add("legacy_replay_assets_manifest.json")

    actual_files = {
        stable_relative(path, generated)
        for path in generated.rglob("*")
        if path.is_file() and not _is_transient_runtime_path(path, generated)
    }
    if actual_files != expected_files:
        issues.append(
            {
                "code": "RELEASE_PROFILE_GENERATED_FILE_SET",
                "message": (
                    f"missing={sorted(expected_files-actual_files)} "
                    f"extra={sorted(actual_files-expected_files)}"
                ),
            }
        )
    if release_profile == FORWARD_V3_PROFILE:
        legacy_only_roots = set(LEGACY_REPLAY_INCLUDE) - set(DEFAULT_INCLUDE)
        forbidden = sorted(
            relative
            for relative in _file_table(stage)
            if any(
                relative == root or relative.startswith(f"{root}/")
                for root in legacy_only_roots
            )
            or relative.startswith("tests/")
            or relative.startswith("ci/")
        )
        if forbidden:
            issues.append(
                {
                    "code": "FORWARD_RELEASE_LEGACY_SURFACE",
                    "message": repr(forbidden),
                }
            )
    return issues


def verify_release(stage: Path) -> dict[str, Any]:
    stage = stage.resolve()
    manifest_path = stage / "RELEASE_MANIFEST.json"
    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8-sig")
    )
    core = dict(manifest)
    declared = core.pop("release_manifest_sha256", None)
    observed = canonical_sha256(core)
    issues: list[dict[str, str]] = []
    if declared != observed:
        issues.append(
            {
                "code": "RELEASE_MANIFEST_HASH",
                "message": f"declared {declared}, observed {observed}",
            }
        )
    declared_files = manifest.get("files", {})
    transient_files = sorted(
        stable_relative(path, stage)
        for path in stage.rglob("*")
        if path.is_file() and _is_transient_runtime_path(path, stage)
    )
    symlinks = sorted(
        path.relative_to(stage).as_posix()
        for path in stage.rglob("*")
        if path.is_symlink()
    )
    if symlinks:
        issues.append(
            {
                "code": "RELEASE_SYMLINK",
                "message": repr(symlinks),
            }
        )
    actual_files = {
        stable_relative(path, stage)
        for path in stage.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.name != "RELEASE_MANIFEST.json"
        and not _is_transient_runtime_path(path, stage)
    }
    if actual_files != set(declared_files):
        issues.append(
            {
                "code": "RELEASE_FILE_SET",
                "message": (
                    f"missing={sorted(set(declared_files)-actual_files)} "
                    f"extra={sorted(actual_files-set(declared_files))}"
                ),
            }
        )
    for relative, expected in declared_files.items():
        try:
            path = resolve_within(
                stage,
                relative,
                label="release manifest file",
                must_exist=True,
            )
        except Exception as error:
            issues.append(
                {
                    "code": "RELEASE_MANIFEST_PATH",
                    "message": f"{relative}: {error}",
                }
            )
            continue
        if path.is_symlink():
            issues.append(
                {
                    "code": "RELEASE_FILE_SYMLINK",
                    "message": str(relative),
                }
            )
            continue
        observed_hash = sha256_file(path)
        observed_size = path.stat().st_size
        if (
            observed_hash != expected["sha256"]
            or observed_size != expected["bytes"]
        ):
            issues.append(
                {
                    "code": "RELEASE_FILE_HASH",
                    "message": (
                        f"{relative}: expected {expected}, observed "
                        f"sha256={observed_hash} bytes={observed_size}"
                    ),
                }
            )
    manifest_version = manifest.get("release_manifest_version")
    if manifest_version != "tgc-release-manifest/3.0.0":
        issues.append(
            {
                "code": "RELEASE_MANIFEST_VERSION",
                "message": repr(manifest_version),
            }
        )
    else:
        release_profile = manifest.get("release_profile")
        artifact_metadata_path = stage / "ARTIFACT_METADATA.json"
        artifact_metadata = (
            read_json(artifact_metadata_path)
            if artifact_metadata_path.is_file()
            else {}
        )
        current_profiled_manifest = (
            manifest.get("release_profile_version") is not None
            or release_profile is not None
            or artifact_metadata.get("release_profile_version") is not None
            or artifact_metadata.get("release_profile") is not None
        )
        if current_profiled_manifest and (
            manifest.get("release_profile_version")
            != "tgc-release-profile/1.0.0"
            or release_profile
            not in {FORWARD_V3_PROFILE, LEGACY_REPLAY_PROFILE}
        ):
            issues.append(
                {
                    "code": "RELEASE_PROFILE",
                    "message": (
                        f"version={manifest.get('release_profile_version')!r} "
                        f"profile={release_profile!r}"
                    ),
                }
            )
        issues.extend(
            _verify_self_hashed_file(
                stage,
                "ARTIFACT_METADATA.json",
                "artifact_metadata_sha256",
                "tgc-artifact-metadata/3.0.0",
                "artifact_metadata_version",
            )
        )
        issues.extend(
            _verify_self_hashed_file(
                stage,
                "SBOM.json",
                "sbom_sha256",
                "tgc-sbom/3.0.0",
                "sbom_version",
            )
        )
        if current_profiled_manifest and artifact_metadata_path.is_file():
            if (
                artifact_metadata.get("release_profile_version")
                != manifest.get("release_profile_version")
                or artifact_metadata.get("release_profile")
                != release_profile
            ):
                issues.append(
                    {
                        "code": "RELEASE_PROFILE_BINDING",
                        "message": "artifact metadata and release manifest disagree",
                    }
                )
        if current_profiled_manifest and release_profile in {
            FORWARD_V3_PROFILE,
            LEGACY_REPLAY_PROFILE,
        }:
            issues.extend(_verify_staged_profile(stage, release_profile))
        issues.extend(
            _verify_self_hashed_file(
                stage,
                "SOURCE_MANIFEST.json",
                "source_manifest_sha256",
                "tgc-source-manifest/3.0.0",
                "source_manifest_version",
            )
        )
    return {
        "release": str(stage),
        "valid": not issues,
        "release_manifest_version": manifest.get(
            "release_manifest_version"
        ),
        "release_profile_version": manifest.get("release_profile_version"),
        "release_profile": manifest.get("release_profile"),
        "file_count": len(declared_files),
        "ignored_transient_count": len(transient_files),
        "ignored_transient_files": transient_files,
        "issues": issues,
    }
