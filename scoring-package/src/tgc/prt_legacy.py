"""Exact replay adapters for frozen PRT v3 evidence."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from .common import sha256_file
from .config import InstanceContract

PRT_REPLAY_MIGRATION_VERSION = "prt-frozen-v3-replay/2"

_TARGET_POLICIES = {
    "schema-a": {
        "required_target": "full_contextual_sn",
        "relation_semantics": "standard_contextual_closure",
        "source_basis": (
            "The benchmark treats the displayed first-order rewrite rules as "
            "generating the standard context-closed rewrite relation."
        ),
        "extraction_instruction": (
            "A response explicitly restricted to root steps or denying contextual "
            "closure claims root_only_termination, not full_contextual_sn, even "
            "though full_contextual_sn is the benchmark-required target."
        ),
    },
    "test01-ko7": {
        "required_target": "full_contextual_sn",
        "relation_semantics": "standard_contextual_closure",
        "source_basis": (
            "Benchmark scoring interprets the displayed Step constructors as the "
            "root contractions of the standard context-closed first-order rewrite "
            "relation. The Lean Step datatype itself enumerates only root "
            "contractions, so this policy is stated explicitly rather than inferred "
            "from that datatype."
        ),
        "extraction_instruction": (
            "A response that explicitly reasons only about Lean Step, root steps, "
            "or absence of congruence claims root_only_termination and does not meet "
            "the benchmark-required full_contextual_sn target. Never silently "
            "upgrade it."
        ),
    },
}


def load_prt_replay_contract(
    contract_dir: Path,
) -> tuple[InstanceContract, dict[str, Any] | None]:
    """Load a current contract or add the exact PRT target to an early-v3 contract."""
    try:
        return InstanceContract.load(contract_dir), None
    except ValueError as error:
        if not any(
            marker in str(error)
            for marker in ("requires required_target", "requires target_policy")
        ):
            raise
    frozen = InstanceContract.load(contract_dir, allow_early_v3_replay=True)
    if frozen.instance_key not in _TARGET_POLICIES:
        raise ValueError(
            f"no PRT replay target policy for {frozen.instance_key!r}"
        )
    policy = dict(_TARGET_POLICIES[frozen.instance_key])
    if frozen.required_target not in {None, "", policy["required_target"]}:
        raise ValueError("frozen PRT required_target conflicts with replay policy")
    if frozen.target_policy:
        for field, value in frozen.target_policy.items():
            if field not in policy or policy[field] != value:
                raise ValueError(
                    f"frozen PRT target_policy.{field} conflicts with replay policy"
                )
    rules = frozen.rules
    reference_binding = None
    fields_added = [
        field
        for field in ("required_target", "target_policy")
        if not getattr(frozen, field)
    ]
    if not rules and frozen.instance_key == "test01-ko7":
        reference_dir = (
            Path(__file__).resolve().parents[2]
            / "spec/generated/test01-ko7/v3"
        )
        reference = InstanceContract.load(reference_dir)
        if reference.signature != frozen.signature:
            raise ValueError("frozen and current Test 01 signatures differ")
        rules = reference.rules
        reference_binding = reference.binding()
        fields_added.append("rules")
    migrated = replace(
        frozen,
        required_target=policy["required_target"],
        target_policy=policy,
        rules=rules,
    )
    receipt = {
        "migration_version": PRT_REPLAY_MIGRATION_VERSION,
        "instance_key": frozen.instance_key,
        "source_contract": frozen.binding(),
        "fields_added": sorted(fields_added),
        "required_target": policy["required_target"],
        "relation_semantics": policy["relation_semantics"],
        "source_contract_modified": False,
        "rule_table_reference_contract": reference_binding,
        "format_semantics": {
            "path_order_without_precedence_quantifier": (
                "literal stated relation only; canonicalized as exact_partial"
            ),
            "basis": (
                "frozen schemas had no quantifier field and prohibited adding "
                "unstated precedence edges"
            ),
        },
    }
    return migrated, receipt


def resolve_prt_checker_root(
    contract: InstanceContract,
    package_root: Path,
) -> tuple[Path, dict[str, Any]]:
    """Find an existing artifact root whose files match every pinned checker hash."""
    binding = contract.checker_binding
    if binding.get("type") != "python_path":
        return package_root.resolve(), {
            "migration_version": PRT_REPLAY_MIGRATION_VERSION,
            "artifact_root": str(package_root.resolve()),
            "binding_type": binding.get("type"),
            "all_hashes_verified": True,
        }
    relative_files = [binding.get("module", "")] + [
        item.get("path", "") for item in binding.get("dependencies", [])
    ]
    expected = [binding.get("sha256", "")] + [
        item.get("sha256", "") for item in binding.get("dependencies", [])
    ]
    if any(not item for item in relative_files + expected):
        raise ValueError("PRT checker binding lacks a path or hash")
    module_rel = Path(relative_files[0])
    candidates = [package_root.resolve()]
    for module_path in package_root.rglob(module_rel.name):
        parts = module_rel.parts
        if len(module_path.parts) < len(parts):
            continue
        if tuple(module_path.parts[-len(parts):]) != parts:
            continue
        root = module_path.parents[len(parts) - 1]
        if root not in candidates:
            candidates.append(root)
    for root in candidates:
        paths = [root / relative for relative in relative_files]
        if all(path.is_file() for path in paths) and all(
            sha256_file(path) == digest for path, digest in zip(paths, expected)
        ):
            return root, {
                "migration_version": PRT_REPLAY_MIGRATION_VERSION,
                "artifact_root": str(root),
                "binding_type": binding["type"],
                "checker_interface": binding.get("interface") or "legacy_tuple_v1",
                "interface_was_missing": not bool(binding.get("interface")),
                "verified_files": len(paths),
                "all_hashes_verified": True,
            }
    raise ValueError("no existing artifact root matches the pinned PRT checker bundle")
