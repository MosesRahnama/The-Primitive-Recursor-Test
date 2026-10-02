from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .common import (
    V3_CONSENSUS_SEMANTICS_VERSION,
    canonical_sha256,
    read_json,
    resolve_within,
    sha256_file,
)
from .coverage import validate_coverage_policy
from .registry import ConstructionDefinition, ConstructionRegistry

V2_CONFIG_VERSION = "tgc-instance-config/2.0.0"
V3_CONFIG_VERSION = "tgc-instance-config/3.0.0"
V2_SCHEMA_VERSION = "tgc-extraction-record/2.0.0"
V2_CONTRACT_MANIFEST_VERSION = "tgc-contract-manifest/2.0.0"
V3_SCHEMA_VERSIONS = {
    "compiled": "tgc-compiled-record/3.0.0",
    "consensus": "tgc-consensus/3.0.0",
    "contract_manifest": "tgc-contract-manifest/3.0.0",
    "gate_report": "tgc-gate-report/3.0.0",
    "record": "tgc-extraction-record/3.0.0",
    "release_manifest": "tgc-release-manifest/3.0.0",
    "run_manifest": "tgc-run-manifest/3.0.0",
    "score_report": "tgc-score-report/3.0.0",
}


@dataclass(frozen=True)
class InstanceContract:
    config_version: str
    contract_major: int
    instance_key: str
    spec_version: str
    schema_version: str
    schema_versions: dict[str, str]
    title: str
    signature: dict[str, list[str]]
    glyph_folds: tuple[tuple[str, str], ...]
    construction_kinds: tuple[str, ...]
    claim_statuses: tuple[str, ...]
    answer_roles: tuple[str, ...]
    claimed_targets: tuple[str, ...]
    specificity_statuses: tuple[str, ...]
    primary_statuses: tuple[str, ...]
    record_statuses: tuple[str, ...]
    payload_schemas: dict[str, dict[str, Any]]
    construction_registry: ConstructionRegistry
    semantic_identity_stripping: dict[str, tuple[str, ...]]
    response_files: tuple[str, ...]
    required_target: str | None
    target_policy: dict[str, Any]
    compliant_routes: tuple[dict[str, Any], ...]
    rules: tuple[dict[str, Any], ...]
    checker_binding: dict[str, Any]
    record_model: dict[str, Any]
    evidence_policy: dict[str, Any]
    coverage_oracle: dict[str, Any] | None
    identity_policy: dict[str, Any]
    consensus_policy: dict[str, Any]
    lineage_policy: dict[str, Any]
    modular_registry_sha256: str | None
    contract_dir: Path
    schema_path: Path
    config_path: Path
    manifest_path: Path
    schema_sha256: str
    config_sha256: str
    manifest_sha256: str

    @property
    def signature_symbols(self) -> set[str]:
        return set(self.signature)

    @property
    def is_v3(self) -> bool:
        return self.contract_major == 3

    def definition(self, kind: str) -> ConstructionDefinition:
        return self.construction_registry.get(kind)

    @classmethod
    def load(
        cls,
        contract_dir: Path,
        *,
        allow_early_v3_replay: bool = False,
    ) -> "InstanceContract":
        contract_dir = contract_dir.resolve()
        config_path = contract_dir / "instance_config.json"
        schema_path = contract_dir / "record.schema.json"
        manifest_path = contract_dir / "contract_manifest.json"
        config = read_json(config_path)
        manifest = read_json(manifest_path)
        assets = manifest.get("assets", {})
        if not isinstance(assets, dict) or not assets:
            raise ValueError("contract manifest has no asset table")
        observed_assets: dict[str, str] = {}
        for name, wanted in sorted(assets.items()):
            asset_path = resolve_within(
                contract_dir,
                name,
                label="contract asset",
                must_exist=True,
            )
            if asset_path.is_symlink():
                raise ValueError(
                    f"contract asset may not be a symlink: {asset_path}"
                )
            if not asset_path.is_file():
                raise ValueError(f"contract asset missing: {asset_path}")
            observed = sha256_file(asset_path)
            observed_assets[name] = observed
            if wanted != observed:
                raise ValueError(
                    f"contract asset hash mismatch for {name}: expected {wanted}, observed {observed}"
                )
        unlisted = sorted(
            path.relative_to(contract_dir).as_posix()
            for path in contract_dir.rglob("*")
            if path.is_file()
            and path.name != "contract_manifest.json"
            and path.relative_to(contract_dir).as_posix() not in assets
        )
        symlinks = sorted(
            path.relative_to(contract_dir).as_posix()
            for path in contract_dir.rglob("*")
            if path.is_symlink()
        )
        if symlinks:
            raise ValueError(f"contract contains symlinks: {symlinks}")
        if unlisted:
            raise ValueError(f"contract contains unmanifested assets: {unlisted}")
        core = dict(manifest)
        declared_manifest_hash = core.pop("contract_manifest_sha256", None)
        observed_manifest_hash = canonical_sha256(core)
        if declared_manifest_hash != observed_manifest_hash:
            raise ValueError(
                "contract manifest self-hash mismatch: "
                f"expected {declared_manifest_hash}, observed {observed_manifest_hash}"
            )

        config_version = str(config.get("config_version") or "")
        if config_version == V3_CONFIG_VERSION:
            contract_major = 3
            schema_versions = {
                str(key): str(value)
                for key, value in config["schema_versions"].items()
            }
            if schema_versions != V3_SCHEMA_VERSIONS:
                raise ValueError(
                    "unsupported v3 schema version registry: "
                    f"{schema_versions!r}"
                )
            if config.get("spec_version") != "3.0.0":
                raise ValueError(
                    f"unsupported v3 spec version {config.get('spec_version')!r}"
                )
            if (
                manifest.get("contract_manifest_version")
                != V3_SCHEMA_VERSIONS["contract_manifest"]
            ):
                raise ValueError(
                    "unsupported v3 contract manifest version "
                    f"{manifest.get('contract_manifest_version')!r}"
                )
            required_target_value = config.get("required_target")
            if (
                not isinstance(required_target_value, str)
                or not required_target_value.strip()
            ) and not allow_early_v3_replay:
                raise ValueError("current v3 contract requires required_target")
            target_policy_value = config.get("target_policy")
            if (
                not isinstance(target_policy_value, dict)
                or not target_policy_value
            ) and not allow_early_v3_replay:
                raise ValueError("current v3 contract requires target_policy")
            if not isinstance(target_policy_value, dict):
                target_policy_value = {}
            required_target_policy_fields = {
                "required_target",
                "relation_semantics",
                "source_basis",
                "extraction_instruction",
            }
            missing_target_policy_fields = (
                required_target_policy_fields - set(target_policy_value)
            )
            if missing_target_policy_fields and not allow_early_v3_replay:
                raise ValueError(
                    "current v3 target_policy missing "
                    f"{sorted(missing_target_policy_fields)}"
                )
            if (
                target_policy_value
                and target_policy_value.get("required_target")
                != required_target_value
            ):
                raise ValueError(
                    "current v3 target_policy.required_target must match "
                    "required_target"
                )
            if target_policy_value and target_policy_value.get(
                "relation_semantics"
            ) not in {
                "standard_contextual_closure",
                "root_only_relation",
                "dependency_pair_relation",
                "program_transition_relation",
            }:
                raise ValueError(
                    "current v3 target_policy has unsupported relation_semantics"
                )
            for field in ("source_basis", "extraction_instruction"):
                value = target_policy_value.get(field)
                if target_policy_value and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise ValueError(
                        f"current v3 target_policy.{field} must be nonempty"
                    )
            checker_binding_value = config.get("checker_binding")
            if (
                not isinstance(checker_binding_value, dict)
                or not checker_binding_value
            ):
                raise ValueError("current v3 contract requires checker_binding")
            checker_binding_type = checker_binding_value.get("type")
            checker_interface = checker_binding_value.get("interface")
            allowed_checker_interfaces = {
                "builtin": {"native_v1"},
                "python_path": {"legacy_tuple_v1", "native_v1"},
            }
            if checker_binding_type not in allowed_checker_interfaces:
                raise ValueError(
                    "current v3 contract has unsupported checker binding type "
                    f"{checker_binding_type!r}"
                )
            if checker_interface is None and allow_early_v3_replay:
                pass
            elif checker_interface not in allowed_checker_interfaces[
                checker_binding_type
            ]:
                raise ValueError(
                    "current v3 contract requires an explicit compatible "
                    "checker interface"
                )
            consensus_policy_value = config.get("consensus_policy")
            if not isinstance(consensus_policy_value, dict):
                raise ValueError("current v3 contract requires consensus_policy")
            required_consensus_fields = {
                "allowed_pass_sets",
                "semantics_version",
                "threshold",
                "voted_fields",
            }
            missing_consensus_fields = (
                required_consensus_fields - set(consensus_policy_value)
            )
            if missing_consensus_fields and not allow_early_v3_replay:
                raise ValueError(
                    "current v3 consensus_policy missing "
                    f"{sorted(missing_consensus_fields)}"
                )
            allowed_pass_sets = consensus_policy_value.get(
                "allowed_pass_sets"
            )
            if allowed_pass_sets is not None and (
                not isinstance(allowed_pass_sets, list)
                or not allowed_pass_sets
                or any(
                    not isinstance(pass_set, list)
                    or not pass_set
                    or any(
                        not isinstance(item, int) or isinstance(item, bool)
                        for item in pass_set
                    )
                    for pass_set in allowed_pass_sets
                )
            ):
                raise ValueError(
                    "current v3 consensus_policy.allowed_pass_sets is malformed"
                )
            threshold_value = consensus_policy_value.get("threshold")
            if threshold_value is not None and (
                not isinstance(threshold_value, int)
                or isinstance(threshold_value, bool)
                or threshold_value < 1
            ):
                raise ValueError(
                    "current v3 consensus_policy.threshold is malformed"
                )
            voted_fields_value = consensus_policy_value.get("voted_fields")
            if voted_fields_value is not None and (
                not isinstance(voted_fields_value, list)
                or not voted_fields_value
                or any(
                    not isinstance(item, str) or not item
                    for item in voted_fields_value
                )
            ):
                raise ValueError(
                    "current v3 consensus_policy.voted_fields is malformed"
                )
            semantics_value = consensus_policy_value.get("semantics_version")
            if (
                not allow_early_v3_replay
                and semantics_value != V3_CONSENSUS_SEMANTICS_VERSION
            ):
                raise ValueError(
                    "unsupported current v3 consensus semantics version "
                    f"{semantics_value!r}"
                )
            if allow_early_v3_replay and semantics_value is not None and (
                not isinstance(semantics_value, str) or not semantics_value
            ):
                raise ValueError(
                    "early-v3 consensus semantics version must be a string"
                )
            schema_version = schema_versions["record"]
            record_model = dict(config["record_model"])
            definitions = dict(config["construction_definitions"])
            registry = ConstructionRegistry.from_config(
                definitions,
                allow_legacy_identity_policy=allow_early_v3_replay,
            )
            construction_kinds = registry.kinds
            payload_schemas = {
                kind: definition.transcription_schema
                for kind, definition in registry.definitions.items()
            }
            claim_statuses = tuple(record_model["claim_statuses"])
            answer_roles = tuple(record_model["answer_roles"])
            claimed_targets = tuple(record_model["claimed_targets"])
            specificity_statuses = tuple(record_model["specificity_statuses"])
            primary_statuses = tuple(record_model["primary_statuses"])
            record_statuses = tuple(record_model["record_statuses"])
            modular_registry_sha256 = str(config["modular_registry_sha256"])
            evidence_policy = dict(config["evidence_policy"])
            coverage_oracle = (
                dict(config["coverage_oracle"])
                if isinstance(config.get("coverage_oracle"), dict)
                else None
            )
            validate_coverage_policy(coverage_oracle)
            identity_policy = dict(config["identity_policy"])
            consensus_policy = dict(config["consensus_policy"])
            lineage_policy = dict(config["lineage_policy"])
            semantic_identity_stripping: dict[str, tuple[str, ...]] = {}
        elif config_version == V2_CONFIG_VERSION:
            contract_major = 2
            schema_version = str(config["schema_version"])
            if schema_version != V2_SCHEMA_VERSION:
                raise ValueError(
                    f"unsupported v2 record schema version {schema_version!r}"
                )
            if config.get("spec_version") != "2.0.0":
                raise ValueError(
                    f"unsupported v2 spec version {config.get('spec_version')!r}"
                )
            if (
                manifest.get("contract_manifest_version")
                != V2_CONTRACT_MANIFEST_VERSION
            ):
                raise ValueError(
                    "unsupported v2 contract manifest version "
                    f"{manifest.get('contract_manifest_version')!r}"
                )
            schema_versions = {
                "record": schema_version,
                "compiled": "tgc-compiled-record/2.0.0",
                "consensus": "tgc-consensus/2.0.0",
                "gate_report": "tgc-gate-report/2.0.0",
                "score_report": "tgc-score-report/2.0.0",
            }
            construction_kinds = tuple(config["construction_kinds"])
            payload_schemas = dict(config["payload_schemas"])
            # V2 did not publish per-kind modules. Synthesize a registry so
            # downstream code has one access path while preserving v2 behavior.
            registry = ConstructionRegistry.from_config(
                {
                    kind: {
                        "kind": kind,
                        "title": kind.replace("_", " ").title(),
                        "cue": "v2 synthesized definition",
                        "cue_terms": [],
                        "transcription_schema": payload_schemas[kind],
                        "concrete_required": payload_schemas[kind].get("required", []),
                        "concrete_any_of": [],
                        "completeness": {},
                        "transform_adapter": (
                            "path_order_v3"
                            if kind in {"lpo", "rpo"}
                            else "polynomial_definitions_v3"
                            if kind in {"poly_interpretation", "additive_measure"}
                            else "generic_v3"
                        ),
                        "evidence_units": {"mode": "top_level"},
                        "checker_route": "legacy_adapter",
                        "template_policy": {},
                    }
                    for kind in construction_kinds
                },
                allow_legacy_identity_policy=True,
            )
            claim_statuses = tuple(config["claim_statuses"])
            answer_roles = tuple(config["answer_roles"])
            claimed_targets = tuple(config["claimed_targets"])
            specificity_statuses = tuple(config["specificity_statuses"])
            primary_statuses = tuple(config["primary_statuses"])
            record_statuses = tuple(config["record_statuses"])
            record_model = {
                "claim_statuses": list(claim_statuses),
                "answer_roles": list(answer_roles),
                "claimed_targets": list(claimed_targets),
                "specificity_statuses": list(specificity_statuses),
                "primary_statuses": list(primary_statuses),
                "record_statuses": list(record_statuses),
                "axis_evidence_fields": [],
            }
            modular_registry_sha256 = None
            evidence_policy = {"model": "inline-locators-v2"}
            coverage_oracle = None
            identity_policy = {
                "mathematical_identity": [
                    "kind",
                    "specificity",
                    "claimed_target",
                    "canonical_payload",
                ]
            }
            consensus_policy = {
                "allowed_pass_sets": [[1, 2], [1, 2, 3]],
                "threshold": 2,
                "voted_fields": ["claim_status", "answer_role"],
            }
            lineage_policy = {"official_compile_requires_run_manifest": False}
            semantic_identity_stripping = {
                key: tuple(value)
                for key, value in config.get(
                    "semantic_identity_stripping", {}
                ).items()
            }
        else:
            raise ValueError(f"unsupported instance config version {config_version!r}")

        return cls(
            config_version=config_version,
            contract_major=contract_major,
            instance_key=config["instance_key"],
            spec_version=config["spec_version"],
            schema_version=schema_version,
            schema_versions=schema_versions,
            title=config["title"],
            signature={
                key: list(value) for key, value in config["signature"].items()
            },
            glyph_folds=tuple(tuple(item) for item in config.get("glyph_folds", [])),
            construction_kinds=construction_kinds,
            claim_statuses=claim_statuses,
            answer_roles=answer_roles,
            claimed_targets=claimed_targets,
            specificity_statuses=specificity_statuses,
            primary_statuses=primary_statuses,
            record_statuses=record_statuses,
            payload_schemas=payload_schemas,
            construction_registry=registry,
            semantic_identity_stripping=semantic_identity_stripping,
            response_files=tuple(config["response_files"]),
            required_target=(
                str(config["required_target"])
                if config.get("required_target") is not None
                else None
            ),
            target_policy=dict(config.get("target_policy", {})),
            compliant_routes=tuple(config.get("compliant_routes", [])),
            rules=tuple(config.get("rules", [])),
            checker_binding=dict(config.get("checker_binding", {})),
            record_model=record_model,
            evidence_policy=evidence_policy,
            coverage_oracle=coverage_oracle,
            identity_policy=identity_policy,
            consensus_policy=consensus_policy,
            lineage_policy=lineage_policy,
            modular_registry_sha256=modular_registry_sha256,
            contract_dir=contract_dir,
            schema_path=schema_path,
            config_path=config_path,
            manifest_path=manifest_path,
            schema_sha256=observed_assets["record.schema.json"],
            config_sha256=observed_assets["instance_config.json"],
            manifest_sha256=str(declared_manifest_hash),
        )

    def binding(self) -> dict[str, str]:
        value = {
            "instance_key": self.instance_key,
            "spec_version": self.spec_version,
            "schema_version": self.schema_version,
            "schema_sha256": self.schema_sha256,
            "instance_config_sha256": self.config_sha256,
            "contract_manifest_sha256": self.manifest_sha256,
        }
        if self.modular_registry_sha256 is not None:
            value["modular_registry_sha256"] = self.modular_registry_sha256
        return value
