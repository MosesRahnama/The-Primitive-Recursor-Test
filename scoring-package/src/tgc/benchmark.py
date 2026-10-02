"""Portable benchmark-package descriptors and contract generation.

A benchmark package is a directory containing ``benchmark.json``, a modular
``spec/v3`` tree, one or more checker modules, and optional checker fixtures.
All descriptor paths are relative and confined to the package root. Generated
contracts are deterministic and may be recreated after relocating the package.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path, PureWindowsPath
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .common import canonical_sha256, read_json, resolve_within, sha256_file
from .config import InstanceContract
from .contractgen import generate_from_roots

PACKAGE_FORMAT = "tgc-benchmark-package/1.0.0"
_DESCRIPTOR_NAME = "benchmark.json"
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True)
class BenchmarkPackage:
    root: Path
    descriptor_path: Path
    descriptor: dict[str, Any]
    name: str
    version: str
    spec_root: Path
    generated_root: Path
    artifact_root: Path
    fixtures_path: Path | None
    strict_portability: bool

    @property
    def descriptor_sha256(self) -> str:
        return sha256_file(self.descriptor_path)

    @property
    def instance_keys(self) -> tuple[str, ...]:
        values = self.descriptor.get("instance_keys")
        if isinstance(values, list) and values:
            return tuple(str(item) for item in values)
        instances = self.spec_root / "instances"
        return tuple(path.stem for path in sorted(instances.glob("*.json")))

    def generated_contract(self, instance_key: str) -> Path:
        return self.generated_root / instance_key / "v3"


def _schema() -> dict[str, Any]:
    path = resources.files("tgc").joinpath(
        "resources/schemas/benchmark-package.schema.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_descriptor_path(value: Path) -> tuple[Path, Path]:
    resolved = value.resolve()
    if resolved.is_dir():
        descriptor = resolved / _DESCRIPTOR_NAME
        root = resolved
    else:
        descriptor = resolved
        root = resolved.parent
    if not descriptor.is_file():
        raise FileNotFoundError(descriptor)
    return root, descriptor


def _relative_path(root: Path, value: Any, *, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty relative path")
    if value == ".":
        return root.resolve()
    return resolve_within(root, value, label=label)


def load_benchmark_package(value: Path) -> BenchmarkPackage:
    root, descriptor_path = _resolve_descriptor_path(value)
    descriptor = read_json(descriptor_path)
    errors = sorted(
        Draft202012Validator(_schema()).iter_errors(descriptor),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        rendered = "; ".join(
            f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in errors[:20]
        )
        raise ValueError(f"invalid {_DESCRIPTOR_NAME}: {rendered}")
    name = str(descriptor["name"])
    if not _SLUG_RE.fullmatch(name):
        raise ValueError(
            "benchmark package name must match [a-z0-9][a-z0-9._-]*"
        )
    spec_root = _relative_path(root, descriptor["spec_root"], label="spec_root")
    generated_root = _relative_path(
        root, descriptor["generated_root"], label="generated_root"
    )
    artifact_root = _relative_path(
        root, descriptor.get("artifact_root", "."), label="artifact_root"
    )
    fixtures = descriptor.get("checker_fixtures")
    fixtures_path = (
        _relative_path(root, fixtures, label="checker_fixtures")
        if fixtures is not None
        else None
    )
    return BenchmarkPackage(
        root=root,
        descriptor_path=descriptor_path,
        descriptor=descriptor,
        name=name,
        version=str(descriptor["version"]),
        spec_root=spec_root,
        generated_root=generated_root,
        artifact_root=artifact_root,
        fixtures_path=fixtures_path,
        strict_portability=bool(descriptor.get("strict_portability", True)),
    )


def _looks_absolute(text: str) -> bool:
    if not text:
        return False
    return (
        Path(text).is_absolute()
        or PureWindowsPath(text).is_absolute()
        or bool(re.match(r"^[A-Za-z]:[\\/]", text))
        or text.startswith("\\\\")
    )


def _walk_strings(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk_strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def validate_benchmark_package(value: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    try:
        package = load_benchmark_package(value)
    except Exception as error:
        return {
            "validation_version": "tgc-benchmark-package-validation/1.0.0",
            "valid": False,
            "issues": [
                {"code": "BENCHMARK_DESCRIPTOR", "path": "$", "message": str(error)}
            ],
        }

    required = (
        package.spec_root / "core.json",
        package.spec_root / "constructions",
        package.spec_root / "instances",
    )
    for path in required:
        if not path.exists():
            issues.append(
                {
                    "code": "BENCHMARK_SPEC_MISSING",
                    "path": str(path),
                    "message": "required modular-spec path is missing",
                }
            )
    construction_files = sorted((package.spec_root / "constructions").glob("*.json"))
    instance_files = sorted((package.spec_root / "instances").glob("*.json"))
    if not construction_files:
        issues.append(
            {
                "code": "BENCHMARK_CONSTRUCTIONS_EMPTY",
                "path": str(package.spec_root / "constructions"),
                "message": "at least one construction definition is required",
            }
        )
    if not instance_files:
        issues.append(
            {
                "code": "BENCHMARK_INSTANCES_EMPTY",
                "path": str(package.spec_root / "instances"),
                "message": "at least one instance definition is required",
            }
        )

    source_files = [package.spec_root / "core.json", *construction_files, *instance_files]
    source_hashes: dict[str, str] = {}
    for path in source_files:
        if not path.is_file():
            continue
        if path.is_symlink():
            issues.append(
                {
                    "code": "BENCHMARK_SPEC_SYMLINK",
                    "path": str(path),
                    "message": "specification files may not be symlinks",
                }
            )
            continue
        try:
            parsed = read_json(path)
        except Exception as error:
            issues.append(
                {"code": "BENCHMARK_SPEC_JSON", "path": str(path), "message": str(error)}
            )
            continue
        source_hashes[path.relative_to(package.spec_root).as_posix()] = sha256_file(path)
        if package.strict_portability:
            for json_path, text in _walk_strings(parsed):
                if _looks_absolute(text):
                    issues.append(
                        {
                            "code": "BENCHMARK_ABSOLUTE_PATH",
                            "path": f"{path}:{json_path}",
                            "message": text,
                        }
                    )
            for forbidden in ("sessions_root", "working_dir"):
                if forbidden in parsed:
                    issues.append(
                        {
                            "code": "BENCHMARK_OPERATIONAL_FIELD",
                            "path": f"{path}:$.{forbidden}",
                            "message": "operational paths belong in deployment profiles, not contract source",
                        }
                    )

    instance_keys = tuple(path.stem for path in instance_files)
    declared_keys = package.descriptor.get("instance_keys")
    if declared_keys is not None and tuple(sorted(map(str, declared_keys))) != tuple(
        sorted(instance_keys)
    ):
        issues.append(
            {
                "code": "BENCHMARK_INSTANCE_SET",
                "path": "$.instance_keys",
                "message": f"declared={declared_keys!r}, observed={list(instance_keys)!r}",
            }
        )
    if package.fixtures_path is not None:
        if not package.fixtures_path.is_file():
            issues.append(
                {
                    "code": "BENCHMARK_FIXTURES_MISSING",
                    "path": str(package.fixtures_path),
                    "message": "checker fixture file is missing",
                }
            )
        else:
            try:
                fixtures = read_json(package.fixtures_path)
            except Exception as error:
                issues.append(
                    {"code": "BENCHMARK_FIXTURES_JSON", "path": str(package.fixtures_path), "message": str(error)}
                )
            else:
                if not isinstance(fixtures.get("cases"), list) or not fixtures["cases"]:
                    issues.append(
                        {
                            "code": "BENCHMARK_FIXTURES_EMPTY",
                            "path": str(package.fixtures_path),
                            "message": "fixtures must contain a nonempty cases array",
                        }
                    )
    result = {
        "validation_version": "tgc-benchmark-package-validation/1.0.0",
        "package": {
            "name": package.name,
            "version": package.version,
            "root": str(package.root),
            "descriptor_sha256": package.descriptor_sha256,
            "strict_portability": package.strict_portability,
        },
        "source_hashes": source_hashes,
        "instance_keys": list(instance_keys),
        "valid": not issues,
        "issues": issues,
    }
    result["validation_sha256"] = canonical_sha256(result)
    return result


def generate_benchmark_contracts(
    value: Path,
    *,
    destination: Path | None = None,
) -> dict[str, Any]:
    package = load_benchmark_package(value)
    validation = validate_benchmark_package(package.descriptor_path)
    if not validation["valid"]:
        raise ValueError(
            "benchmark package validation failed: "
            + json.dumps(validation["issues"], ensure_ascii=False)
        )
    target = destination.resolve() if destination is not None else package.generated_root
    manifest = generate_from_roots(
        package.spec_root,
        target,
        artifact_root=package.artifact_root,
    )
    contracts: dict[str, dict[str, Any]] = {}
    for instance_key in package.instance_keys:
        contract_dir = target / instance_key / "v3"
        contract = InstanceContract.load(contract_dir)
        contracts[instance_key] = {
            "path": str(contract_dir),
            "contract_manifest_sha256": contract.manifest_sha256,
            "modular_registry_sha256": contract.modular_registry_sha256,
            "checker_binding": contract.checker_binding,
        }
    result = {
        "generation_version": "tgc-benchmark-generation/1.0.0",
        "package_name": package.name,
        "package_version": package.version,
        "descriptor_sha256": package.descriptor_sha256,
        "generated_root": str(target),
        "generated_manifest_sha256": manifest["generated_manifest_sha256"],
        "contracts": contracts,
    }
    result["generation_sha256"] = canonical_sha256(result)
    return result


def copy_portable_source(package: BenchmarkPackage, destination: Path) -> None:
    """Copy only the portable benchmark source surface for relocation tests."""
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(destination)
    generated_name = package.generated_root.relative_to(package.root).parts[0]
    ignore = shutil.ignore_patterns(
        generated_name,
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    )
    shutil.copytree(package.root, destination, ignore=ignore)

