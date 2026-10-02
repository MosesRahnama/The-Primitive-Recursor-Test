"""Portable benchmark-adapter scaffolding and conformance machinery.

An adapter is a small, path-neutral workspace containing a modular TGC spec,
a native checker, fixtures, and an operational deployment profile. The engine
builds the same hash-closed contract format used by the paper benchmark.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .checkers import checker_from_contract
from .collection import compile_pass_directory, load_compiled_directories
from .common import (
    V3_CHECKER_INPUT_VERSION,
    canonical_sha256,
    read_json,
    resolve_within,
    sha256_file,
    stable_relative,
    write_json_atomic,
    write_text_atomic,
)
from .config import InstanceContract
from .consensus import gate_dataset
from .contractgen import generate_from_roots
from .deploy import deploy_profile
from .scoring import score_gate_report

ADAPTER_VERSION = "tgc-adapter/1.0.0"
BUILD_REPORT_VERSION = "tgc-adapter-build-report/1.0.0"
VALIDATION_REPORT_VERSION = "tgc-adapter-validation/1.0.0"
SELFTEST_REPORT_VERSION = "tgc-adapter-selftest/1.0.0"


def _json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _starter_core() -> dict[str, Any]:
    return {
        "consensus_policy": {
            "allowed_pass_sets": [[1, 2], [1, 3], [2, 3], [1, 2, 3]],
            "preserve_all_evidence_by_pass": True,
            "require_checker_input_agreement": True,
            "semantics_version": "tgc-consensus-semantics/3.4.1",
            "threshold": 2,
            "tiebreak_only_for_unresolved_sessions": True,
            "voted_fields": [
                "specificity",
                "claimed_target",
                "claim_status",
                "answer_role",
            ],
        },
        "discipline_rules": {
            "manual_reading_only_v1": (
                "Read every assigned response in full and derive every claim, axis, "
                "anchor, and disposition by human-language understanding. Do not use "
                "scripts, regex, parsers, or another extraction as a source of record content."
            ),
            "assertion_discipline_v3": (
                "claim_status records commitment; specificity and transcription record "
                "how much of the mathematical object is stated. A committed family with "
                "no concrete object is claimed_valid plus family_only plus transcription={}. "
                "A noncommittal possibility is mentioned."
            ),
            "coverage_discipline_v3": (
                "After a full-source sweep, every construction-bearing passage must be "
                "linked to a claim and every other flagged passage must be dispositioned "
                "nonconstruction or unresolved. Never invent a claim to clear coverage."
            ),
        },
        "evidence_policy": {
            "axis_evidence": "required_for_every_claim_axis",
            "binding": "exact-substring-v3",
            "claim_source_consistency": "required",
            "coverage_attestation": "required_in_official_mode",
            "duplicate_locator_policy": "reject_and_reuse_anchor_id",
            "field_evidence": "semantic_units_from_kind_registry",
            "max_anchor_characters": 4000,
            "model": "record-level-anchor-table",
            "primary_evidence": "required_for_single_or_coequal",
            "unused_anchor_policy": "reject",
        },
        "identity_policy": {
            "assertion_fields": [
                "specificity",
                "claimed_target",
                "claim_status",
                "answer_role",
            ],
            "checker_identity": ["kind", "checker_payload"],
            "consensus_grouping": [
                "source_id",
                "mathematical_identity",
                "source_occurrence",
            ],
            "mathematical_identity": ["kind", "canonical_payload"],
            "primary_reference": [
                "source_id",
                "mathematical_identity",
                "source_occurrence",
            ],
            "principle": (
                "classification disagreement remains a field disagreement; "
                "source prose never becomes mathematical identity by accident"
            ),
        },
        "lineage_policy": {
            "compiled_binds": [
                "raw_record_sha256",
                "compiler_build_sha256",
                "contract_manifest_sha256",
                "run_contract_sha256",
            ],
            "gate_binds": [
                "compiled_record_sha256s",
                "consensus_policy_sha256",
            ],
            "official_compile_requires_run_manifest": True,
            "record_binds": [
                "run_contract_sha256",
                "roster_entry_sha256",
                "pass_id",
            ],
            "score_binds": [
                "gate_report_sha256",
                "checker_binding_sha256",
                "scoring_policy_sha256",
            ],
        },
        "record_model": {
            "answer_roles": [
                "primary",
                "co_primary",
                "supporting",
                "alternative_sufficient",
                "failed_contrast",
                "unselected",
                "mentioned",
                "unclear",
            ],
            "axis_evidence_fields": [
                "kind_basis",
                "claim_status",
                "answer_role",
                "claimed_target",
                "specificity",
            ],
            "claim_statuses": [
                "claimed_valid",
                "claimed_invalid",
                "hypothetical",
                "mentioned",
                "unclear",
            ],
            "claimed_targets": [
                "program_termination",
                "local_descent",
                "none",
                "unclear",
            ],
            "coverage_statuses": ["complete", "uncertain"],
            "mention_dispositions": ["claim", "nonconstruction", "unresolved"],
            "primary_statuses": ["single", "coequal", "none", "unclear"],
            "record_statuses": [
                "complete",
                "refused",
                "truncated",
                "file_missing",
                "garbled",
            ],
            "specificity_statuses": [
                "concrete",
                "partial",
                "family_only",
                "unparseable",
            ],
            "success_roles": [
                "primary",
                "co_primary",
                "alternative_sufficient",
            ],
        },
        "registry_version": "tgc-registry/3.0.0",
        "schema_versions": {
            "compiled": "tgc-compiled-record/3.0.0",
            "consensus": "tgc-consensus/3.0.0",
            "contract_manifest": "tgc-contract-manifest/3.0.0",
            "gate_report": "tgc-gate-report/3.0.0",
            "record": "tgc-extraction-record/3.0.0",
            "release_manifest": "tgc-release-manifest/3.0.0",
            "run_manifest": "tgc-run-manifest/3.0.0",
            "score_report": "tgc-score-report/3.0.0",
        },
        "spec_name": "starter-countdown-adapter",
        "spec_version": "3.0.0",
    }


def _starter_construction() -> dict[str, Any]:
    return {
        "checker_route": "native_adapter",
        "completeness": {},
        "concrete_any_of": [],
        "concrete_required": ["coordinate", "relation", "scope"],
        "cue": "a ranking argument selecting one state coordinate and a strict relation",
        "cue_terms": ["ranking", "coordinate", "decrease"],
        "definition_version": "tgc-construction-definition/3.0.0",
        "evidence_units": {"mode": "top_level"},
        "identity_adapter": "full_payload_v1",
        "identity_fields": ["coordinate", "relation", "scope"],
        "annotation_fields": [],
        "kind": "ranking_descent",
        "template_policy": {
            "copy_source_notation": True,
            "delete_unstated_optional_fields": True,
            "never_complete_partial_object": True,
        },
        "title": "Ranking Descent",
        "transcription_schema": {
            "additionalProperties": False,
            "properties": {
                "coordinate": {"enum": [1, 2]},
                "relation": {
                    "enum": ["natural_predecessor", "strict_subterm"]
                },
                "scope": {"enum": ["recursive_call", "whole_state"]},
            },
            "required": ["coordinate", "relation", "scope"],
            "type": "object",
        },
        "transform_adapter": "generic_v3",
    }


def _starter_example() -> dict[str, Any]:
    return {
        "anchors": {
            "a_claim": {
                "source_id": "response.txt",
                "text": (
                    "Use the second countdown coordinate as the ranking function. "
                    "It strictly decreases by natural predecessor on every recursive "
                    "call, so the program terminates."
                ),
            },
            "a_coordinate": {
                "source_id": "response.txt",
                "text": "second countdown coordinate",
            },
            "a_relation": {
                "source_id": "response.txt",
                "text": "strictly decreases by natural predecessor",
            },
            "a_scope": {
                "source_id": "response.txt",
                "text": "on every recursive call",
            },
            "a_target": {
                "source_id": "response.txt",
                "text": "the program terminates",
            },
        },
        "claims": [
            {
                "local_id": "c1",
                "source_id": "response.txt",
                "kind": "ranking_descent",
                "claim_status": "claimed_valid",
                "answer_role": "primary",
                "claimed_target": "program_termination",
                "specificity": "concrete",
                "transcription": {
                    "coordinate": 2,
                    "relation": "natural_predecessor",
                    "scope": "recursive_call",
                },
                "evidence": ["a_claim"],
                "axis_evidence": {
                    "kind_basis": ["a_claim"],
                    "claim_status": ["a_claim"],
                    "answer_role": ["a_claim"],
                    "claimed_target": ["a_target"],
                    "specificity": ["a_claim"],
                },
                "field_evidence": {
                    "/transcription/coordinate": ["a_coordinate"],
                    "/transcription/relation": ["a_relation"],
                    "/transcription/scope": ["a_scope"],
                },
                "rejection_evidence": [],
            }
        ],
        "primary": {
            "status": "single",
            "claim_ids": ["c1"],
            "evidence": ["a_claim"],
        },
        "coverage": {
            "sources_read": ["response.txt"],
            "completeness_status": "complete",
            "completeness_attestation": True,
            "mention_dispositions": [
                {
                    "anchor_id": "a_claim",
                    "disposition": "claim",
                    "claim_ids": ["c1"],
                    "reason": "",
                }
            ],
        },
        "notes": "",
    }


def _starter_instance() -> dict[str, Any]:
    return {
        "call_measure_measures": [],
        "call_measure_scopes": [],
        "checker_binding": {
            "type": "python_path",
            "interface": "native_v1",
            "module": "checker.py",
            "function": "check",
            "sha256": "DERIVED_BY_GENERATOR",
            "dependencies": [],
        },
        "classification_guidance": (
            "`program_termination` is the claimed end-to-end property. "
            "`local_descent` records only the selected-coordinate obligation."
        ),
        "compliant_routes": [
            {
                "kind": "ranking_descent",
                "coordinate": 2,
                "relation": "natural_predecessor",
                "scope": "recursive_call",
            }
        ],
        "glyph_folds": [],
        "instance_key": "starter-countdown",
        "instance_version": "tgc-instance-definition/3.0.0",
        "named_measures": [],
        "prompt_cohorts": {"starter-uniform": "one fixture prompt"},
        "response_files": ["response.txt"],
        "required_target": "program_termination",
        "target_policy": {
            "required_target": "program_termination",
            "relation_semantics": "program_transition_relation",
            "source_basis": (
                "The starter benchmark asks whether the displayed countdown transition "
                "program terminates."
            ),
            "extraction_instruction": (
                "Transcribe local_descent when that is all the response states; never "
                "upgrade it to program_termination merely because program_termination "
                "is the required scoring target."
            ),
        },
        "rules": [
            {
                "name": "countdown",
                "lhs": "step(left, successor(right))",
                "rhs": "step(left, right)",
            }
        ],
        "signature": {"step": ["left", "right"], "successor": ["value"]},
        "surface_key": "STARTER",
        "title": "Starter two-coordinate countdown benchmark",
        "worked_example": _starter_example(),
    }


def _starter_checker_text() -> str:
    return '''from __future__ import annotations

from typing import Any


def check(consensus_claim: dict[str, Any]) -> dict[str, Any]:
    """Native TGC checker with an explicit witness for every decisive result."""
    checker_object = consensus_claim.get("representative_checker_object") or {}
    payload = checker_object.get("payload") or {}
    coordinate = payload.get("coordinate")
    relation = payload.get("relation")
    scope = payload.get("scope")
    if (
        coordinate == 2
        and relation == "natural_predecessor"
        and scope == "recursive_call"
    ):
        return {
            "verdict": "PASS",
            "compliant": True,
            "detail": "coordinate_2_natural_predecessor",
            "certificate": {
                "certificate_type": "starter-ranking-witness/v1",
                "witness": {
                    "rule": "countdown",
                    "before": "successor(right)",
                    "after": "right",
                    "relation": "natural_predecessor",
                },
                "supported_targets": ["program_termination", "local_descent"],
                "proof_strength": "program_termination",
            },
        }
    if coordinate == 1:
        return {
            "verdict": "REFUTED",
            "compliant": False,
            "detail": "coordinate_1_is_unchanged",
            "certificate": {
                "certificate_type": "starter-ranking-counterexample/v1",
                "counterexample": {
                    "rule": "countdown",
                    "before": "left",
                    "after": "left",
                    "strict_decrease": False,
                },
                "supported_targets": [],
            },
        }
    return {
        "verdict": "UNKNOWN",
        "compliant": False,
        "detail": "starter_checker_unsupported_payload",
        "certificate": None,
    }
'''


def _starter_readme() -> str:
    return """# TGC transferable starter adapter

This workspace is intentionally independent of the PRT/termination benchmark.
It demonstrates the public adaptation surface:

1. one modular construction kind under `spec/constructions/`;
2. one benchmark instance under `spec/instances/`;
3. a `native_v1` checker with concrete PASS and REFUTED witnesses;
4. a relative-path deployment profile;
5. one source fixture and a complete two-pass end-to-end self-test.

Run from any directory after installing TGC:

```powershell
tgc build-adapter --adapter .
tgc validate-adapter --adapter .
tgc adapter-selftest --adapter .
```

Edit the construction schema and checker together. Never make a checker infer a
field that the extraction contract did not require and evidence.
"""


def starter_files() -> dict[str, str]:
    fixture = (
        "Use the second countdown coordinate as the ranking function. "
        "It strictly decreases by natural predecessor on every recursive call, "
        "so the program terminates.\n"
    )
    descriptor = {
        "adapter_version": ADAPTER_VERSION,
        "name": "starter-countdown",
        "instance_key": "starter-countdown",
        "spec_root": "spec",
        "output_root": "generated",
        "artifact_root": ".",
        "deployment_profile": "deployment_profile.json",
        "checker_cases": [
            {
                "name": "valid-second-coordinate",
                "kind": "ranking_descent",
                "payload": {
                    "coordinate": 2,
                    "relation": "natural_predecessor",
                    "scope": "recursive_call",
                },
                "expected_verdict": "PASS",
                "expected_supported_targets": [
                    "program_termination",
                    "local_descent",
                ],
                "certificate_contains": {
                    "certificate_type": "starter-ranking-witness/v1",
                    "witness": {"rule": "countdown"},
                },
            },
            {
                "name": "invalid-first-coordinate",
                "kind": "ranking_descent",
                "payload": {
                    "coordinate": 1,
                    "relation": "natural_predecessor",
                    "scope": "recursive_call",
                },
                "expected_verdict": "REFUTED",
                "certificate_contains": {
                    "certificate_type": "starter-ranking-counterexample/v1",
                    "counterexample": {"strict_decrease": False},
                },
            },
            {
                "name": "unsupported-relation",
                "kind": "ranking_descent",
                "payload": {
                    "coordinate": 2,
                    "relation": "strict_subterm",
                    "scope": "recursive_call",
                },
                "expected_verdict": "UNKNOWN",
            },
        ],
        "selftest": {
            "session_slug": "demo-session",
            "expected_lane": "CertifiedValid",
            "expected_metrics": {
                "has_valid_witness": "yes",
                "has_target_adequate_witness": "yes",
            },
            "record": {"record_status": "complete", **_starter_example()},
        },
    }
    profile = {
        "profile_version": "tgc-deployment-profile/3.0.0",
        "run_id": "STARTER_ADAPTER_SELFTEST",
        "instance_key": "starter-countdown",
        "contract_dir": "generated/starter-countdown/v3",
        "sessions_root": "fixtures/sessions",
        "run_dir": "work/selftest-run",
        "selection": {"mode": "all", "exclude_substring": []},
        "passes": [1, 2],
    }
    return {
        "README.md": _starter_readme(),
        "adapter.json": _json_text(descriptor),
        "checker.py": _starter_checker_text(),
        "deployment_profile.json": _json_text(profile),
        "fixtures/sessions/demo-session/response.txt": fixture,
        "spec/core.json": _json_text(_starter_core()),
        "spec/constructions/ranking_descent.json": _json_text(
            _starter_construction()
        ),
        "spec/instances/starter-countdown.json": _json_text(_starter_instance()),
    }


def init_adapter(destination: Path) -> dict[str, Any]:
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(
            f"adapter destination must be absent or empty: {destination}"
        )
    destination.mkdir(parents=True, exist_ok=True)
    files = starter_files()
    for relative, text in sorted(files.items()):
        path = resolve_within(destination, relative, label="starter adapter file")
        write_text_atomic(path, text)
    result = {
        "adapter_version": ADAPTER_VERSION,
        "destination": str(destination),
        "file_count": len(files),
        "files": {
            relative: sha256_file(destination / relative)
            for relative in sorted(files)
        },
    }
    result["scaffold_sha256"] = canonical_sha256(result)
    return result


def _adapter_schema() -> dict[str, Any]:
    path = resources.files("tgc").joinpath("resources/schemas/adapter.schema.json")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_descriptor(adapter_root: Path) -> tuple[dict[str, Any], Path]:
    root = adapter_root.resolve()
    descriptor_path = resolve_within(
        root, "adapter.json", label="adapter descriptor", must_exist=True
    )
    value = read_json(descriptor_path)
    if not isinstance(value, dict):
        raise ValueError("adapter.json must contain an object")
    errors = sorted(
        Draft202012Validator(_adapter_schema()).iter_errors(value),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        rendered = "; ".join(
            f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
            for error in errors[:20]
        )
        raise ValueError(f"invalid adapter.json: {rendered}")
    if value.get("adapter_version") != ADAPTER_VERSION:
        raise ValueError(
            f"unsupported adapter version {value.get('adapter_version')!r}"
        )
    return value, root


def _adapter_paths(
    descriptor: dict[str, Any], root: Path
) -> dict[str, Path]:
    return {
        "spec_root": resolve_within(root, descriptor["spec_root"], label="spec_root"),
        "output_root": resolve_within(
            root, descriptor["output_root"], label="output_root"
        ),
        "artifact_root": resolve_within(
            root, descriptor["artifact_root"], label="artifact_root"
        ),
        "deployment_profile": resolve_within(
            root,
            descriptor["deployment_profile"],
            label="deployment_profile",
            must_exist=True,
        ),
    }


def _source_hashes(root: Path, paths: dict[str, Path]) -> dict[str, str]:
    files: list[Path] = [root / "adapter.json", paths["deployment_profile"]]
    files.extend(path for path in paths["spec_root"].rglob("*") if path.is_file())
    checker = paths["artifact_root"] / "checker.py"
    if checker.is_file():
        files.append(checker)
    return {
        stable_relative(path, root): sha256_file(path)
        for path in sorted(set(files))
    }


def build_adapter(adapter_root: Path) -> dict[str, Any]:
    descriptor, root = _load_descriptor(adapter_root)
    paths = _adapter_paths(descriptor, root)
    profile = read_json(paths["deployment_profile"])
    if (
        not isinstance(profile, dict)
        or profile.get("profile_version") != "tgc-deployment-profile/3.0.0"
    ):
        raise ValueError(
            "adapter deployment profile must use "
            "tgc-deployment-profile/3.0.0"
        )
    if profile.get("instance_key") != descriptor["instance_key"]:
        raise ValueError(
            "adapter deployment profile must target the descriptor instance"
        )
    manifest = generate_from_roots(
        paths["spec_root"],
        paths["output_root"],
        artifact_root=paths["artifact_root"],
    )
    contract_dir = paths["output_root"] / descriptor["instance_key"] / "v3"
    contract = InstanceContract.load(contract_dir)
    if contract.instance_key != descriptor["instance_key"]:
        raise ValueError("generated instance key differs from adapter descriptor")
    checker = checker_from_contract(contract, artifact_root=paths["artifact_root"])
    binding = getattr(checker, "__tgc_binding__", contract.checker_binding)
    report = {
        "build_report_version": BUILD_REPORT_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "adapter_name": descriptor["name"],
        "instance_key": contract.instance_key,
        "source_hashes": _source_hashes(root, paths),
        "generated_manifest_sha256": manifest["generated_manifest_sha256"],
        "generated_asset_count": len(manifest["assets"]),
        "contract": contract.binding(),
        "checker_binding": binding,
        "checker_binding_sha256": canonical_sha256(binding),
    }
    report["build_report_sha256"] = canonical_sha256(report)
    write_json_atomic(root / "ADAPTER_BUILD_REPORT.json", report)
    return report


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        stable_relative(path, root): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _contains_subset(observed: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(observed, dict) and all(
            key in observed and _contains_subset(observed[key], value)
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(observed, list) and all(
            any(_contains_subset(candidate, item) for candidate in observed)
            for item in expected
        )
    return observed == expected


def _run_checker_cases(
    descriptor: dict[str, Any], checker: Any
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    results: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for index, case in enumerate(descriptor.get("checker_cases", [])):
        kind = str(case["kind"])
        payload = json.loads(json.dumps(case["payload"]))
        checker_object = {"kind": kind, "payload": payload}
        identity_core = {"kind": kind, "payload": payload}
        claim = {
            "checker_input_schema_version": V3_CHECKER_INPUT_VERSION,
            "mathematical_core": identity_core,
            "mathematical_identity": canonical_sha256(identity_core),
            "representative_checker_object": checker_object,
            "checker_input_consensus": {
                "status": "agreed",
                "value": canonical_sha256(
                    {"kind": kind, "payload": payload}
                ),
            },
        }
        try:
            outcome = checker(claim)
            verdict = outcome.verdict
            certificate = outcome.certificate
            case_issues: list[str] = []
            if verdict != case["expected_verdict"]:
                case_issues.append(
                    f"expected verdict {case['expected_verdict']}, observed {verdict}"
                )
            expected_targets = case.get("expected_supported_targets")
            if expected_targets is not None:
                observed_targets = (
                    certificate.get("supported_targets")
                    if isinstance(certificate, dict)
                    else None
                )
                if sorted(observed_targets or []) != sorted(expected_targets):
                    case_issues.append(
                        f"expected supported_targets {expected_targets}, "
                        f"observed {observed_targets}"
                    )
            expected_certificate = case.get("certificate_contains")
            if expected_certificate is not None and not _contains_subset(
                certificate, expected_certificate
            ):
                case_issues.append(
                    "certificate does not contain the declared fixture subset"
                )
        except Exception as error:
            verdict = "EXCEPTION"
            certificate = None
            case_issues = [f"{type(error).__name__}: {error}"]
        result = {
            "name": case["name"],
            "expected_verdict": case["expected_verdict"],
            "observed_verdict": verdict,
            "valid": not case_issues,
            "certificate_sha256": (
                canonical_sha256(certificate)
                if isinstance(certificate, dict)
                else None
            ),
            "issues": case_issues,
        }
        results.append(result)
        for message in case_issues:
            issues.append(
                {
                    "code": "ADAPTER_CHECKER_CASE",
                    "path": f"adapter.json.checker_cases[{index}]",
                    "message": f"{case['name']}: {message}",
                }
            )
    return results, issues


def validate_adapter(adapter_root: Path) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    try:
        descriptor, root = _load_descriptor(adapter_root)
        paths = _adapter_paths(descriptor, root)
    except Exception as error:
        return {
            "validation_report_version": VALIDATION_REPORT_VERSION,
            "valid": False,
            "issues": [
                {"code": "ADAPTER_DESCRIPTOR", "path": "$", "message": str(error)}
            ],
            "warnings": [],
        }

    symlinks = [
        stable_relative(path, root) for path in root.rglob("*") if path.is_symlink()
    ]
    if symlinks:
        issues.append(
            {
                "code": "ADAPTER_SYMLINKS",
                "path": str(root),
                "message": repr(sorted(symlinks)),
            }
        )
    for required in (
        paths["spec_root"] / "core.json",
        paths["spec_root"] / "constructions",
        paths["spec_root"] / "instances",
    ):
        if not required.exists():
            issues.append(
                {
                    "code": "ADAPTER_SOURCE_MISSING",
                    "path": str(required),
                    "message": "required adapter source is missing",
                }
            )

    contract_dir = paths["output_root"] / descriptor["instance_key"] / "v3"
    try:
        contract = InstanceContract.load(contract_dir)
        checker = checker_from_contract(
            contract, artifact_root=paths["artifact_root"]
        )
    except Exception as error:
        issues.append(
            {
                "code": "ADAPTER_GENERATED_CONTRACT",
                "path": str(contract_dir),
                "message": str(error),
            }
        )
        contract = None

    try:
        with tempfile.TemporaryDirectory(prefix="tgc-adapter-validate-") as temporary:
            regenerated = Path(temporary) / "generated"
            manifest = generate_from_roots(
                paths["spec_root"],
                regenerated,
                artifact_root=paths["artifact_root"],
            )
            expected = _tree_hashes(regenerated)
            observed = _tree_hashes(paths["output_root"])
            if expected != observed:
                issues.append(
                    {
                        "code": "ADAPTER_GENERATED_DRIFT",
                        "path": str(paths["output_root"]),
                        "message": (
                            f"fresh_manifest={manifest['generated_manifest_sha256']} "
                            "does not match the checked-in generated tree"
                        ),
                    }
                )
    except Exception as error:
        issues.append(
            {
                "code": "ADAPTER_REGENERATION",
                "path": str(paths["spec_root"]),
                "message": str(error),
            }
        )

    profile = read_json(paths["deployment_profile"])
    if (
        not isinstance(profile, dict)
        or profile.get("profile_version") != "tgc-deployment-profile/3.0.0"
    ):
        issues.append(
            {
                "code": "ADAPTER_PROFILE_VERSION",
                "path": str(paths["deployment_profile"]),
                "message": (
                    "deployment profile must use "
                    "tgc-deployment-profile/3.0.0"
                ),
            }
        )
    if not isinstance(profile, dict) or profile.get("instance_key") != descriptor["instance_key"]:
        issues.append(
            {
                "code": "ADAPTER_PROFILE_INSTANCE",
                "path": str(paths["deployment_profile"]),
                "message": "deployment profile must target the descriptor instance",
            }
        )
    checker_case_results: list[dict[str, Any]] = []
    if contract is not None:
        checker_case_results, checker_case_issues = _run_checker_cases(
            descriptor, checker
        )
        issues.extend(checker_case_issues)

    selftest = descriptor.get("selftest")
    if not isinstance(selftest, dict) or not isinstance(selftest.get("record"), dict):
        issues.append(
            {
                "code": "ADAPTER_SELFTEST_SPEC",
                "path": "adapter.json.selftest",
                "message": "selftest.record object is required",
            }
        )

    def iter_strings(value: Any):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from iter_strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from iter_strings(child)

    for path in sorted(paths["spec_root"].rglob("*.json")):
        value = read_json(path)
        literals = [
            item
            for item in iter_strings(value)
            if (len(item) >= 3 and item[1:3] in {":\\", ":/"})
            or item.startswith("/home/")
            or item.startswith("/Users/")
        ]
        if literals:
            warnings.append(
                {
                    "code": "ADAPTER_ABSOLUTE_PATH_LITERAL",
                    "path": stable_relative(path, root),
                    "message": "keep machine paths in deployment profiles, not contract source",
                }
            )

    result = {
        "validation_report_version": VALIDATION_REPORT_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "adapter_name": descriptor["name"],
        "instance_key": descriptor["instance_key"],
        "valid": not issues,
        "contract": contract.binding() if contract is not None else None,
        "source_hashes": _source_hashes(root, paths),
        "checker_cases": checker_case_results,
        "issues": issues,
        "warnings": warnings,
    }
    result["validation_report_sha256"] = canonical_sha256(result)
    return result


def _fill_selftest_records(
    run_dir: Path,
    descriptor: dict[str, Any],
) -> None:
    selftest = descriptor["selftest"]
    slug = str(selftest["session_slug"])
    mutable = selftest["record"]
    for pass_number in (1, 2):
        path = run_dir / "extraction" / f"e{pass_number:02d}" / f"{slug}.json"
        record = read_json(path)
        record["extractor"] = {
            "pass_number": pass_number,
            "extractor_id": f"starter-independent-extractor-{pass_number}",
            "extraction_id": f"starter-selftest-pass-{pass_number}",
            "independence_attestation": True,
        }
        defaults: dict[str, Any] = {
            "record_status": "complete",
            "anchors": {},
            "claims": [],
            "primary": {"status": "none", "claim_ids": [], "evidence": []},
            "coverage": {
                "sources_read": [item["source_id"] for item in record["session"]["sources"]],
                "completeness_status": "complete",
                "completeness_attestation": True,
                "mention_dispositions": [],
            },
            "notes": "",
        }
        for key, default in defaults.items():
            record[key] = json.loads(json.dumps(mutable.get(key, default)))
        write_json_atomic(path, record)


def adapter_selftest(adapter_root: Path) -> dict[str, Any]:
    source_root = adapter_root.resolve()
    with tempfile.TemporaryDirectory(prefix="tgc-adapter-selftest-") as temporary:
        workspace = Path(temporary) / "adapter"
        shutil.copytree(
            source_root,
            workspace,
            ignore=shutil.ignore_patterns("generated", "work", "ADAPTER_*_REPORT.json"),
        )
        build = build_adapter(workspace)
        descriptor, _ = _load_descriptor(workspace)
        paths = _adapter_paths(descriptor, workspace)
        deployment = deploy_profile(paths["deployment_profile"])
        run_dir = resolve_within(workspace, "work/selftest-run", label="selftest run")
        _fill_selftest_records(run_dir, descriptor)
        run_manifest = read_json(run_dir / "RUN_MANIFEST.json")
        contract = InstanceContract.load(
            paths["output_root"] / descriptor["instance_key"] / "v3"
        )
        compiled_dirs: list[Path] = []
        for pass_number in (1, 2):
            input_dir = run_dir / "extraction" / f"e{pass_number:02d}"
            output_dir = run_dir / "compiled" / f"e{pass_number:02d}"
            report = compile_pass_directory(
                input_dir,
                output_dir,
                contract,
                run_manifest=run_manifest,
            )
            if report["invalid_count"] != 0:
                raise ValueError(
                    f"starter pass {pass_number} did not compile: {report}"
                )
            compiled_dirs.append(output_dir)
        records = load_compiled_directories(compiled_dirs)
        gate = gate_dataset(records)
        checker = checker_from_contract(
            contract, artifact_root=paths["artifact_root"]
        )
        score = score_gate_report(
            gate,
            checker,
            checker_binding=contract.checker_binding,
        )
        expected_lane = descriptor["selftest"]["expected_lane"]
        rows = score.get("rows", [])
        observed_lane = rows[0]["lane"] if len(rows) == 1 else None
        issues: list[dict[str, str]] = []
        if observed_lane != expected_lane:
            issues.append(
                {
                    "code": "SELFTEST_LANE",
                    "path": "score.rows[0].lane",
                    "message": f"expected {expected_lane}, observed {observed_lane}",
                }
            )
        for metric, wanted in descriptor["selftest"].get(
            "expected_metrics", {}
        ).items():
            observed = rows[0].get(metric) if rows else None
            if observed != wanted:
                issues.append(
                    {
                        "code": "SELFTEST_METRIC",
                        "path": f"score.rows[0].{metric}",
                        "message": f"expected {wanted}, observed {observed}",
                    }
                )
        result = {
            "selftest_report_version": SELFTEST_REPORT_VERSION,
            "adapter_version": ADAPTER_VERSION,
            "adapter_name": descriptor["name"],
            "valid": not issues,
            "build_report_sha256": build["build_report_sha256"],
            "deployment_status": deployment.get("deployment_status"),
            "gate_status_counts": gate["gate_status_counts"],
            "lane_counts": score["lane_counts"],
            "expected_lane": expected_lane,
            "observed_lane": observed_lane,
            "issues": issues,
        }
        result["selftest_report_sha256"] = canonical_sha256(result)
        return result
