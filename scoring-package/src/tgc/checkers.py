from __future__ import annotations

import importlib.util
import json
import re
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .authority import authority_registry_binding, upgrade_checker_result
from .canonical import canonical_tuple_order, fold_presentation
from .common import (
    V3_CHECKER_INPUT_VERSION,
    canonical_sha256,
    project_v3_checker_input,
    resolve_within,
    sha256_file,
)
from .config import InstanceContract
from .measure_eval import call_measure_step_counterexample, measure_step_counterexample
from .native_math import (
    call_measure_dependency_pair_decision,
    interpretation_monotonicity_verified,
    path_order_decision,
    polynomial_interpretation_decision,
)
from .path_order_obligations import omitted_source_status
from .policy import boundary_policy
from .proof_obligations import (
    ground_term_interpretation_decision,
    interpretation_payload_matches,
    rule_size_decision,
)
from .root_control_obligations import check_payload, source_objects
from .scoring import Checker, CheckerResult

# These routes inspect every reader's input themselves. A text dispute is
# deferred to that checker, not discarded: differing decisions return UNKNOWN.
# Retain the exported name for existing integrations.
CONTRACT_DERIVED_KINDS: frozenset[str] = frozenset({"root_control_proof"})


def _require_checker_input_schema(
    consensus_claim: dict[str, Any],
    expected_version: str | None,
) -> None:
    if expected_version is None:
        return
    observed = consensus_claim.get("checker_input_schema_version")
    if observed != expected_version:
        raise ValueError(
            "checker claim schema mismatch: "
            f"expected {expected_version!r}, observed {observed!r}"
        )
    checker_object = consensus_claim.get("representative_checker_object")
    if checker_object is not None:
        project_v3_checker_input(checker_object)


def frame_only_kinds(contract: InstanceContract) -> frozenset[str]:
    """Kinds the CONTRACT declares to carry no mathematical object.

    A definition with neither identity fields nor concrete-required fields
    holds nothing a checker could evaluate: `structural_induction_untyped` is
    selected precisely when "no separate complete order/measure/projection is
    defined", and `other_unparseable` when nothing parsed. Such a claim is a
    proof FRAME, so it can never be the concrete checkable witness, and the
    honest outcome is NO_CONCRETE_WITNESS rather than an Unknown that implies
    the engine merely failed to look. Derived from the registry, never from a
    hardcoded kind list, so a new frame-only kind inherits the behaviour.

    A definition carries a mathematical object if the registry demands ANY
    payload for it: identity fields, unconditionally required concrete fields,
    or a `concrete_any_of` branch (the registry's second required-payload
    mechanism). All three must be empty before a kind is swept in here; no
    current kind is affected, but omitting `concrete_any_of` would let a future
    kind with an either/or payload be read as carrying nothing.
    """

    kinds: set[str] = set()
    for kind, definition in contract.construction_registry.definitions.items():
        if definition.is_frame_only:
            kinds.add(str(kind))
    return frozenset(kinds)


def _checker_bundle_core(binding: dict[str, Any]) -> dict[str, Any]:
    core: dict[str, Any] = {
        "module": str(binding.get("module") or ""),
        "function": str(binding.get("function") or "check_object"),
        "sha256": str(binding.get("sha256") or ""),
        "dependencies": sorted(
            [
                {
                    "path": str(item.get("path") or ""),
                    "sha256": str(item.get("sha256") or ""),
                }
                for item in binding.get("dependencies", [])
                if isinstance(item, dict)
            ],
            key=lambda item: item["path"],
        ),
    }
    # Absent for historical bindings, so their published bundle hashes remain
    # byte-for-byte stable. New adapters should state the interface explicitly.
    if binding.get("interface") is not None:
        core["interface"] = str(binding["interface"])
    return core


def _verified_python_binding(
    binding: dict[str, Any],
    *,
    artifact_root: Path,
) -> tuple[dict[str, Any], Path]:
    core = _checker_bundle_core(binding)
    module_path = resolve_within(
        artifact_root,
        core["module"],
        label="checker module",
        must_exist=True,
    )
    if module_path.is_symlink():
        raise ValueError(f"checker module may not be a symlink: {module_path}")
    if not module_path.is_file():
        raise FileNotFoundError(module_path)
    observed_module = sha256_file(module_path)
    if observed_module != core["sha256"]:
        raise ValueError(
            f"checker hash mismatch for {module_path}: "
            f"expected {core['sha256']}, observed {observed_module}"
        )
    for item in core["dependencies"]:
        dependency_path = resolve_within(
            artifact_root,
            item["path"],
            label="checker dependency",
            must_exist=True,
        )
        if dependency_path.is_symlink():
            raise ValueError(
                f"checker dependency may not be a symlink: {dependency_path}"
            )
        if not dependency_path.is_file():
            raise FileNotFoundError(dependency_path)
        observed = sha256_file(dependency_path)
        if observed != item["sha256"]:
            raise ValueError(
                f"checker dependency hash mismatch for {dependency_path}: "
                f"expected {item['sha256']}, observed {observed}"
            )
    bundle_sha256 = canonical_sha256(core)
    declared_bundle = binding.get("checker_bundle_sha256")
    if declared_bundle is not None and declared_bundle != bundle_sha256:
        raise ValueError(
            "checker bundle hash mismatch: "
            f"expected {declared_bundle}, observed {bundle_sha256}"
        )
    return {
        **dict(binding),
        "dependencies": core["dependencies"],
        "checker_bundle_sha256": bundle_sha256,
    }, module_path


def _path_order_support_issue(consensus_claim: dict[str, Any]) -> str | None:
    core = consensus_claim.get("mathematical_core")
    if not isinstance(core, dict):
        return None
    kind = core.get("kind")
    if kind not in {"lpo", "rpo"}:
        return None
    payload = core.get("payload") or {}
    status = payload.get("status") or {"mode": "unspecified"}
    mode = status.get("mode")
    order = status.get("argument_order")
    if mode == "unparseable":
        return "path_status_unparseable"
    # SA live-round fix (2026-07-27): a status-FREE rpo routes to the legacy
    # lex/graph decision — the same policy the v1 deterministic baseline uses
    # (its reason string is rpo_via_lex_graph_decision) and consistent with
    # the T01 rule that only an EXPLICIT multiset status names a different
    # order. RPO's standard multiset status is implemented by the contract-
    # native checker; other explicit non-lex statuses stay blocked fail-closed.
    supported = {"lex", "unspecified"}
    if kind == "rpo":
        supported.add("multiset")
    if mode not in supported:
        if kind == "lpo" and mode == "multiset":
            return "legacy_lpo_checker_does_not_implement_multiset_status"
        return f"legacy_{kind}_checker_does_not_implement_status[{mode}]"
    if order is not None and (
        not isinstance(order, list)
        or not order
        or any(type(index) is not int or index < 1 for index in order)
        or len(set(order)) != len(order)
    ):
        return f"path_argument_order_malformed[{order}]"
    return None


# ---- context-closure licensing (lane beta, 2026-07-28) --------------------
# `full_contextual_sn` asserts strong normalization under EVERY context. A
# certificate may carry it only when the deciding path either
#   (a) rests on a named standard theory whose orders are closed under
#       contexts by construction (simplification orders), or
#   (b) machine-checked, for the concrete transcribed object, the property
#       that makes the measure survive contexts.
# Every grant records WHICH license it used, so the upgrade is visible in the
# certificate instead of implicit in the construction kind. Anything else caps
# at root-only scope: the L-14 failure family (a size measure patched by
# "the increasing rules yield normal forms") is exactly a root-only argument
# transcribed as a global one, and must never be credited as contextual.
SIMPLIFICATION_ORDER_LICENSE = "simplification-order-standard-theory/v1"
VERIFIED_MONOTONICITY_LICENSE = "verified-strict-monotonicity-every-argument/v1"
GLOBAL_ADDITIVE_MEASURE_LICENSE = (
    "global-additive-count-measure-context-invariance/v1"
)
SANS_GLOBAL_MULTISET_LICENSE = (
    "sans-global-F-subterm-multiset-context-closure/v1"
)

FULL_SN_TARGETS = ["full_contextual_sn", "root_only_termination", "local_descent"]
ROOT_ONLY_TARGETS = ["root_only_termination", "local_descent"]
PATH_ORDER_KINDS = frozenset({"lpo", "rpo"})


def _support(
    targets: list[str],
    *,
    basis: str,
    license_marker: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "supported_targets": list(targets),
        "supported_targets_basis": basis,
    }
    if license_marker is not None:
        value["context_closure_license"] = license_marker
    return value


def _target_support(
    consensus_claim: dict[str, Any],
    checker_object: dict[str, Any],
    *,
    legacy_surface: str | None = None,
    contract_instance_key: str | None = None,
    checker_detail: str | None = None,
) -> dict[str, Any]:
    """Supported targets (plus the license or cap reason) for a legacy PASS.

    The legacy tuple interface reports ``(verdict, compliant, detail, family)``
    only: no generic per-position monotonicity result crosses it. Interpretation
    and measure kinds therefore cap at root-only scope unless an exact,
    instance-bound legacy theorem receipt is recognized below. Path orders keep
    contextual scope under an explicit standard-theory license.
    """

    core = consensus_claim.get("mathematical_core") or consensus_claim.get("core") or {}
    kind = core.get("kind")
    payload = checker_object.get("payload") or {}
    if kind in {"root_control_proof", "structural_induction_untyped"}:
        return _support(ROOT_ONLY_TARGETS, basis="root_only_argument_shape")
    if kind == "dp_projection":
        # A verified pair processor establishes the transformed pair problem.
        # Full source-system SN requires a separate, hash-bound transport
        # authority and is never inferred from the construction kind alone.
        return _support(
            ["dependency_pair_termination", "local_descent"],
            basis="pair_processor_without_transport_authority",
        )
    if kind in {"counter_projection", "size_change"}:
        # Bare coordinate/call-graph descent is local evidence only. The
        # current payloads do not encode a complete processor or transport.
        return _support(["local_descent"], basis="bare_coordinate_or_call_graph_descent")
    if kind == "call_measure" and payload.get("scope") == "dependency_pair":
        return _support(["local_descent"], basis="dependency_pair_scope_measure")
    if kind == "call_measure":
        # This is an INSTANCE- and OBJECT-specific theorem, not a generic
        # call-measure upgrade.  For the non-duplicating SANS fixture, the
        # multiset of arg-3 values over every F-subterm strictly decreases under
        # every contextual step when the value is either term size or S-count:
        # the base rule removes an element; the recursive rule replaces the
        # redex element by a smaller one; contributions below the redex are not
        # duplicated; and enclosing contributions are unchanged (size) or
        # decrease (S-count).  Require the exact hash-bound legacy surface,
        # contract instance, payload, and legacy proof receipt.  Anything else
        # retains the root-only cap below.
        sans_measure = payload.get("measure")
        expected_sans_detail = (
            "global_multiset_arg3_certified"
            f"[{sans_measure}|element_removed_or_strictly_decreased|"
            "non_duplicating|multiset_order_wellfounded]"
            "|compliance_policy_pending"
        )
        if (
            legacy_surface == "SANS"
            and contract_instance_key == "schema-a-new"
            and set(payload) == {"scope", "argument", "measure"}
            and payload.get("scope") == "all_F_subterms_multiset"
            and payload.get("argument") == 3
            and sans_measure in {"size", "S_count"}
            and checker_detail == expected_sans_detail
        ):
            return _support(
                FULL_SN_TARGETS,
                basis=(
                    "sans_nonduplicating_global_F_subterm_multiset_"
                    "decreases_under_every_contextual_step"
                ),
                license_marker=SANS_GLOBAL_MULTISET_LICENSE,
            )
    if kind in PATH_ORDER_KINDS:
        # LPO/RPO are simplification orders: monotone in every argument and
        # stable under substitution by construction, so orienting every rule
        # closes under contexts. The license names the theory being used.
        return _support(
            FULL_SN_TARGETS,
            basis="path_order_is_a_context_closed_reduction_order",
            license_marker=SIMPLIFICATION_ORDER_LICENSE,
        )
    return _support(
        ROOT_ONLY_TARGETS,
        basis=f"no_machine_checked_context_monotonicity_on_legacy_path[{kind}]",
    )


def _supported_targets(
    consensus_claim: dict[str, Any],
    checker_object: dict[str, Any],
) -> list[str]:
    return _target_support(consensus_claim, checker_object)["supported_targets"]


def _checker_result_schema() -> dict[str, Any]:
    path = resources.files("tgc").joinpath(
        "resources/schemas/checker-result.schema.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _native_checker_result(
    value: Any,
    *,
    binding: dict[str, Any],
    checker_object: dict[str, Any],
) -> CheckerResult:
    """Normalize the public ``native_v1`` checker interface.

    Native adapters receive the complete consensus claim and may return either
    :class:`CheckerResult` or a JSON-shaped mapping. Decisive certificates are
    bound to the exact checker object and checker bundle by this trusted wrapper;
    the adapter remains responsible for its domain witness and supported targets.
    """
    if isinstance(value, CheckerResult):
        result = value
    elif isinstance(value, dict):
        errors = sorted(
            Draft202012Validator(_checker_result_schema()).iter_errors(value),
            key=lambda item: list(item.absolute_path),
        )
        if errors:
            rendered = "; ".join(
                f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
                for error in errors[:20]
            )
            raise ValueError(f"invalid native_v1 checker result: {rendered}")
        verdict = str(value.get("verdict") or "")
        detail = str(value.get("detail") or "")
        result = CheckerResult(
            verdict=verdict,
            compliant=bool(value.get("compliant", False)),
            detail=detail,
            certificate=value.get("certificate"),
        )
    else:
        raise ValueError(
            "native_v1 checker must return CheckerResult or an object; "
            f"received {type(value).__name__}"
        )
    mapped = {"UNDECIDED": "UNKNOWN"}.get(result.verdict, result.verdict)
    if mapped not in {"PASS", "REFUTED", "UNKNOWN"}:
        raise ValueError(f"native_v1 checker returned invalid verdict {mapped!r}")
    certificate = result.certificate
    if mapped in {"PASS", "REFUTED"}:
        if not isinstance(certificate, dict):
            raise ValueError(f"native_v1 {mapped} requires a certificate object")
        certificate = dict(certificate)
        input_sha256 = canonical_sha256(checker_object)
        certificate.setdefault("certificate_type", "native-checker-certificate/v1")
        certificate.setdefault("checker_object_sha256", input_sha256)
        certificate.setdefault("input_sha256", input_sha256)
        certificate.setdefault("verdict", mapped)
        certificate.setdefault("checker_binding", binding)
        certificate.setdefault("checker_binding_sha256", canonical_sha256(binding))
        certificate.setdefault("checker_bundle_sha256", binding.get("checker_bundle_sha256"))
        if mapped == "PASS":
            targets = certificate.get("supported_targets")
            if (
                not isinstance(targets, list)
                or not targets
                or any(not isinstance(item, str) or not item for item in targets)
            ):
                raise ValueError(
                    "native_v1 PASS certificate requires nonempty supported_targets"
                )
    return CheckerResult(
        verdict=mapped,
        compliant=bool(result.compliant),
        detail=str(result.detail),
        certificate=certificate,
    )


def load_legacy_checker(
    module_path: Path,
    *,
    function_name: str = "check_object",
    expected_sha256: str | None = None,
    binding_metadata: dict[str, Any] | None = None,
    legacy_surface: str | None = None,
    contract_instance_key: str | None = None,
    expected_checker_input_schema_version: str | None = None,
) -> Checker:
    if expected_checker_input_schema_version not in {
        None,
        V3_CHECKER_INPUT_VERSION,
    }:
        raise ValueError(
            "unsupported checker input schema version "
            f"{expected_checker_input_schema_version!r}"
        )
    module_path = module_path.resolve()
    observed_sha256 = sha256_file(module_path)
    if expected_sha256 is not None and observed_sha256 != expected_sha256:
        raise ValueError(
            f"checker hash mismatch for {module_path}: "
            f"expected {expected_sha256}, observed {observed_sha256}"
        )
    module_parent = str(module_path.parent)
    if module_parent not in sys.path:
        sys.path.insert(0, module_parent)
    spec = importlib.util.spec_from_file_location(
        f"tgc_checker_{observed_sha256[:12]}",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import checker module {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, function_name)
    if legacy_surface is not None:
        # Instance-aware surface binding (2026-08-07, measured on the first
        # schema-a-new round): the pilot-era module hardcodes SURFACE = "SA",
        # so its SANS-certified control-arm routes (typed DP descent,
        # non-duplicating aggregates) were unreachable from the very instance
        # they certify, and a certified-correct round scored ZERO
        # CertifiedValid. The surface is data from the HASH-BOUND contract
        # (checker_binding.legacy_surface, pinned in instance_config), never
        # inferred, and the module bytes stay exactly the pinned hash. A
        # module without a SURFACE global refuses the parameter, fail-closed.
        if not hasattr(module, "SURFACE"):
            raise ValueError(
                f"checker module {module_path} does not expose SURFACE; "
                "legacy_surface cannot be bound"
            )
        module.SURFACE = str(legacy_surface)

    binding = binding_metadata or {
        "type": "python_path",
        "interface": "legacy_tuple_v1",
        "module": str(module_path),
        "function": function_name,
        "sha256": observed_sha256,
        "dependencies": [],
        "checker_bundle_sha256": canonical_sha256(
            {
                "module": str(module_path),
                "function": function_name,
                "sha256": observed_sha256,
                "dependencies": [],
            }
        ),
    }

    def checker(consensus_claim: dict[str, Any]) -> CheckerResult:
        _require_checker_input_schema(
            consensus_claim, expected_checker_input_schema_version
        )
        checker_object = consensus_claim.get("representative_checker_object")
        if not isinstance(checker_object, dict):
            return CheckerResult(
                verdict="UNKNOWN",
                compliant=False,
                detail="checker_input_not_agreed",
                certificate=None,
            )
        is_v3 = (
            expected_checker_input_schema_version
            == V3_CHECKER_INPUT_VERSION
        )
        if is_v3:
            try:
                checker_object = project_v3_checker_input(checker_object)
            except ValueError:
                return CheckerResult(
                    verdict="UNKNOWN",
                    compliant=False,
                    detail="checker_input_not_v3_kind_payload",
                    certificate=None,
                )
            checker_vote = consensus_claim.get("checker_input_consensus") or {}
            if (
                checker_vote.get("status") == "agreed"
                and checker_vote.get("value") != canonical_sha256(checker_object)
            ):
                return CheckerResult(
                    verdict="UNKNOWN",
                    compliant=False,
                    detail="checker_input_identity_mismatch",
                    certificate=None,
                )
            consensus_claim = {
                **consensus_claim,
                "representative_checker_object": checker_object,
            }
        interface = str(binding.get("interface") or "legacy_tuple_v1")
        if interface == "native_v1":
            return _native_checker_result(
                function(consensus_claim),
                binding=binding,
                checker_object=checker_object,
            )
        if interface != "legacy_tuple_v1":
            raise ValueError(f"unsupported checker interface {interface!r}")
        support_issue = _path_order_support_issue(consensus_claim)
        if support_issue is not None:
            return CheckerResult(
                verdict="UNKNOWN",
                compliant=False,
                detail=support_issue,
                certificate=None,
            )
        result = function(checker_object)
        if not isinstance(result, tuple) or len(result) != 4:
            raise ValueError(
                f"legacy checker {module_path}:{function_name} "
                f"returned unexpected result {result!r}"
            )
        verdict, checker_reported_compliant, detail, family = result
        mapped = {"UNDECIDED": "UNKNOWN"}.get(verdict, verdict)
        certificate = None
        if mapped in {"PASS", "REFUTED"}:
            checker_object_sha256 = canonical_sha256(checker_object)
            support = (
                _target_support(
                    consensus_claim,
                    checker_object,
                    legacy_surface=legacy_surface,
                    contract_instance_key=contract_instance_key,
                    checker_detail=str(detail),
                )
                if mapped == "PASS"
                else {"supported_targets": [], "supported_targets_basis": "refuted"}
            )
            supported_targets = support["supported_targets"]
            certificate = {
                "certificate_type": (
                    "deterministic-checker-replay/v3"
                    if is_v3
                    else "deterministic-checker-replay/v2"
                ),
                "checker_binding": binding,
                "checker_binding_sha256": canonical_sha256(binding),
                "checker_bundle_sha256": binding.get("checker_bundle_sha256"),
                "checker_path": str(module_path),
                "checker_sha256": observed_sha256,
                "checker_function": function_name,
                "checker_object_sha256": checker_object_sha256,
                "input_sha256": checker_object_sha256,
                "checker_input_identity": consensus_claim.get(
                    "checker_input_consensus", {}
                ).get("value"),
                "verdict": mapped,
                "checker_reported_compliant": bool(checker_reported_compliant),
                "family_recognition": bool(family),
                "supported_targets": supported_targets,
                "supported_targets_basis": support["supported_targets_basis"],
                "proof_strength": (
                    "full_contextual_sn"
                    if "full_contextual_sn" in supported_targets
                    else supported_targets[0]
                    if supported_targets
                    else None
                ),
                "detail": detail,
                "raw_result": [
                    verdict,
                    bool(checker_reported_compliant),
                    detail,
                    bool(family),
                ],
                "replay": {
                    "function": function_name,
                    "input": checker_object,
                },
            }
            if "context_closure_license" in support:
                certificate["context_closure_license"] = support[
                    "context_closure_license"
                ]
        return CheckerResult(
            verdict=mapped,
            # Compatibility telemetry only. V3 scoring computes boundary policy
            # independently from the contract's declarative route table.
            compliant=bool(checker_reported_compliant),
            detail=(
                f"{detail}|family_recognition" if family else str(detail)
            ),
            certificate=certificate,
        )

    setattr(checker, "__tgc_binding__", binding)
    return checker



def check_contract_native_math(
    consensus_claim: dict[str, Any],
    contract: InstanceContract,
) -> CheckerResult | None:
    """Run exact contract-bound decisions before historical legacy adapters.

    The decision consumes only the typed canonical payload and the contract's
    rule/signature table.  It never completes omitted response data.
    """

    mathematical_core = consensus_claim.get("mathematical_core")
    checker_object = consensus_claim.get("representative_checker_object")
    if not isinstance(mathematical_core, dict) or not isinstance(checker_object, dict):
        return None
    kind = mathematical_core.get("kind")
    from .assertion_obligations import bound_assertion_issue

    bound_issue = bound_assertion_issue(consensus_claim)
    if bound_issue:
        return CheckerResult(verdict="UNKNOWN", compliant=False, detail=bound_issue, certificate=None)
    scoped = check_scoped_obligation(consensus_claim, contract)
    if scoped is not None:
        return scoped
    if kind in {"lpo", "rpo"}:
        source_issue = omitted_source_status(consensus_claim)
        if source_issue:
            return CheckerResult(verdict="UNKNOWN", compliant=False, detail=source_issue, certificate=None)
        decision = path_order_decision(
            mathematical_core,
            contract.rules,
            contract.signature_symbols,
            checker_object,
        )
    elif kind in {"poly_interpretation", "additive_measure"}:
        decision = polynomial_interpretation_decision(
            mathematical_core,
            checker_object,
            contract.rules,
            contract.signature,
        )
    elif kind == "call_measure":
        measure_schema = (
            (contract.payload_schemas.get("call_measure") or {})
            .get("properties", {})
            .get("measure", {})
        )
        registered_measures = set(measure_schema.get("enum") or [])
        decision = call_measure_dependency_pair_decision(
            mathematical_core,
            checker_object,
            contract.rules,
            contract.signature,
            registered_measures,
        )
    else:
        return None

    status = decision.get("status")
    if status == "not_applicable":
        return None
    if status != "ok" or decision.get("holds") is None:
        return CheckerResult(
            verdict="UNKNOWN",
            compliant=False,
            detail=f"native_{kind}_unsupported[{decision.get('reason', status)}]",
            certificate=None,
        )

    monotonicity_only = str(decision.get("reason", "")).startswith(
        "strict_monotonicity_fails"
    )
    root_family_claim = False
    if monotonicity_only:
        # A monotonicity counterexample refutes the CONTEXT-CLOSURE licence,
        # which is exactly what a full-contextual claim needs — those stay
        # REFUTED, unchanged. It refutes NOTHING about a claim whose every
        # substantive target vote is root-only/local (an argument-dropping
        # interpretation claimed for top-level reduction is a correct method
        # there): with the rule table proved, that claim PASSES with root-only
        # support; with the rule table unresolved it is UNKNOWN. Mixed or
        # absent target votes stay UNKNOWN, fail-closed — a refutation must
        # not rest on one resolution of an unresolved vote.
        votes = (
            (consensus_claim.get("field_consensus") or {})
            .get("claimed_target", {})
            .get("votes")
            or {}
        )
        substantive = [
            vote for vote in votes.values() if vote not in (None, "unclear", "none")
        ]
        all_full = bool(substantive) and all(
            vote == "full_contextual_sn" for vote in substantive
        )
        root_family_claim = bool(substantive) and all(
            vote in ROOT_ONLY_TARGETS for vote in substantive
        )
        if not all_full and not root_family_claim:
            return CheckerResult(
                verdict="UNKNOWN",
                compliant=False,
                detail=(
                    f"native_{kind}_target_dependent"
                    f"[{decision.get('reason')}|rules_hold="
                    f"{decision.get('rules_hold')}]"
                ),
                certificate=None,
            )
        if root_family_claim and decision.get("rules_hold") is not True:
            return CheckerResult(
                verdict="UNKNOWN",
                compliant=False,
                detail=(
                    f"native_{kind}_unsupported"
                    "[root_claim_rule_table_unresolved]"
                ),
                certificate=None,
            )

    verdict = "PASS" if bool(decision.get("holds")) else "REFUTED"
    if monotonicity_only and root_family_claim:
        verdict = "PASS"
    checker_object_sha256 = canonical_sha256(checker_object)
    if verdict != "PASS":
        support = {"supported_targets": [], "supported_targets_basis": "refuted"}
    elif kind in PATH_ORDER_KINDS:
        # The decision oriented every contract rule in a lexicographic path
        # order. Path orders are simplification orders, hence closed under
        # contexts and substitutions: the license names that theory.
        support = _support(
            FULL_SN_TARGETS,
            basis="path_order_orients_every_rule",
            license_marker=SIMPLIFICATION_ORDER_LICENSE,
        )
    elif (
        kind == "call_measure"
        and decision.get("decision_family")
        == "dependency_pair_argument_proper_subterm"
    ):
        # The native route proves only the recursive-call comparison. Source
        # TRS transport is never inferred here; a verified archived authority
        # may add full_contextual_sn in upgrade_checker_result below.
        support = _support(
            ["local_descent"],
            basis="contract_rule_table_recursive_call_proper_subterm",
        )
    elif decision.get("decision_family") == "dependency_pair_polynomial_reduction_pair":
        support = _support(
            [*FULL_SN_TARGETS, "dependency_pair_termination"],
            basis="all_dependency_pairs_strict_and_complete_usable_rule_premises_checked",
        )
    elif interpretation_monotonicity_verified(decision):
        # The polynomial route computed one strict-monotonicity row per
        # (symbol, argument) of the complete signature interpretation and every
        # row is machine-verified, so every one-hole context strictly
        # increases and the per-rule decrease survives contexts.
        support = _support(
            FULL_SN_TARGETS,
            basis="strict_monotonicity_verified_in_every_argument_position",
            license_marker=VERIFIED_MONOTONICITY_LICENSE,
        )
    else:
        # PASS on the rule table without an all-verified monotonicity table
        # proves descent at the redex only. Never upgrade it.
        support = _support(
            ROOT_ONLY_TARGETS,
            basis="monotonicity_table_not_verified_in_every_argument_position",
        )
    supported_targets = support["supported_targets"]
    certificate: dict[str, Any] = {
        "certificate_type": "contract-native-mathematical-decision/v1",
        "checker_object_sha256": checker_object_sha256,
        "input_sha256": checker_object_sha256,
        "verdict": verdict,
        "kind": kind,
        "instance_key": contract.instance_key,
        "contract": contract.binding(),
        "decision": decision,
        "supported_targets": supported_targets,
        "supported_targets_basis": support["supported_targets_basis"],
        "proof_strength": (
            "full_contextual_sn"
            if "full_contextual_sn" in supported_targets
            else supported_targets[0]
            if supported_targets
            else None
        ),
    }
    if "context_closure_license" in support:
        certificate["context_closure_license"] = support["context_closure_license"]
    return CheckerResult(
        verdict=verdict,
        compliant=False,
        detail=(
            f"native_{kind}_certificate"
            if verdict == "PASS"
            else f"native_{kind}_counterexample[{decision.get('reason', 'failed')}]"
        ),
        certificate=certificate,
    )

def checker_from_contract(
    contract: InstanceContract,
    *,
    artifact_root: Path | None = None,
    allow_early_v3_replay: bool = False,
    early_v3_checker_interface: str | None = None,
) -> Checker:
    binding = dict(contract.checker_binding)
    binding_type = binding.get("type")
    interface = binding.get("interface")
    missing_early_v3_interface = contract.is_v3 and interface is None
    if missing_early_v3_interface and not allow_early_v3_replay:
        raise ValueError(
            "current v3 checker binding requires an explicit interface; "
            "a frozen early-v3 contract requires explicit replay authorization"
        )
    if missing_early_v3_interface and early_v3_checker_interface is None:
        raise ValueError(
            "a frozen early-v3 contract with no checker interface requires "
            "an explicit replay checker interface"
        )
    if early_v3_checker_interface is not None and not missing_early_v3_interface:
        raise ValueError(
            "early-v3 checker interface may be supplied only when the frozen "
            "contract omits it"
        )
    expected_interface = early_v3_checker_interface
    if contract.is_v3 and interface is not None:
        allowed = (
            {"native_v1"}
            if binding_type == "builtin"
            else {"legacy_tuple_v1", "native_v1"}
        )
        if interface not in allowed:
            raise ValueError(
                f"unsupported current-v3 checker interface {interface!r} "
                f"for binding type {binding_type!r}"
            )
    if missing_early_v3_interface:
        replay_allowed = (
            {"native_v1"}
            if binding_type == "builtin"
            else {"legacy_tuple_v1", "native_v1"}
        )
        if early_v3_checker_interface not in replay_allowed:
            raise ValueError(
                "unsupported early-v3 replay checker interface "
                f"{early_v3_checker_interface!r} for binding type "
                f"{binding_type!r}"
            )
    expected_checker_input_schema_version = (
        V3_CHECKER_INPUT_VERSION if contract.is_v3 else None
    )
    if binding_type == "builtin":
        if binding.get("callable") != "tgc.checkers:toy_checker":
            raise ValueError(f"unsupported builtin checker binding {binding!r}")
        effective_binding = dict(binding)
        if missing_early_v3_interface:
            effective_binding.update(
                {
                    "interface": expected_interface,
                    "early_v3_interface_assumption": {
                        "interface": expected_interface,
                        "source": "operator_supplied_replay_argument",
                    },
                }
            )

        def builtin(consensus_claim: dict[str, Any]) -> CheckerResult:
            _require_checker_input_schema(
                consensus_claim, expected_checker_input_schema_version
            )
            return toy_checker(consensus_claim)

        setattr(builtin, "__tgc_binding__", effective_binding)
        setattr(builtin, "__tgc_contract_binding__", contract.binding())
        setattr(
            builtin,
            "__tgc_boundary_policy__",
            boundary_policy(contract),
        )
        return builtin
    if binding_type == "python_path":
        root = (
            artifact_root.resolve()
            if artifact_root is not None
            else Path(__file__).resolve().parents[2]
        )
        verified_binding, module_path = _verified_python_binding(
            binding, artifact_root=root
        )
        if missing_early_v3_interface:
            verified_binding = {
                **verified_binding,
                "interface": expected_interface,
                "early_v3_interface_assumption": {
                    "interface": expected_interface,
                    "source": "operator_supplied_replay_argument",
                },
            }
        authority_binding = authority_registry_binding(root)
        if authority_binding is not None:
            verified_binding = {
                **verified_binding,
                "authority_registry": authority_binding,
            }
        checker = load_legacy_checker(
            module_path,
            function_name=str(binding.get("function") or "check_object"),
            expected_sha256=str(binding.get("sha256") or "") or None,
            binding_metadata=verified_binding,
            legacy_surface=(
                str(binding["legacy_surface"])
                if binding.get("legacy_surface")
                else None
            ),
            contract_instance_key=contract.instance_key,
            expected_checker_input_schema_version=(
                expected_checker_input_schema_version
            ),
        )
        base_checker = checker
        contract_rules = contract.rules
        contract_symbols = contract.signature_symbols

        instance_key = getattr(contract, "instance_key", None)

        def checker_with_native_routes(
            consensus_claim: dict[str, Any],
        ) -> CheckerResult:
            _require_checker_input_schema(
                consensus_claim, expected_checker_input_schema_version
            )
            # Native contract-bound routes run before the legacy adapter
            # (2026-07-27): root_control_proof decides against the contract's
            # structured rule table with a per-rule certificate; lex tuples
            # of global symbol counts get a duplication-aware decision.
            native = check_contract_native_math(consensus_claim, contract)
            if native is not None and native.detail == "source_bound_requires_separate_obligation":
                return native
            if native is None:
                native = check_kbo_claim(
                    consensus_claim, contract_rules, contract_symbols
                )
            if native is None:
                native = check_root_control_claim(
                    consensus_claim, contract_rules, contract_symbols
                )
            if native is None:
                native = check_lex_count_tuple_claim(
                    consensus_claim, contract_rules, contract_symbols
                )
            payload = (consensus_claim.get("representative_checker_object") or {}).get("payload", {})
            scoped = any(k in payload for k in ("rule_scope", "comparison", "interpretation_scope", "term_lower_bound"))
            if (native is None or native.verdict == "UNKNOWN") and not scoped:
                # Refutation-only; runs AFTER the certifying route so a payload
                # that route can decide is never diverted here. The certifying
                # route's UNKNOWN ("components outside the global-count
                # family") is a refusal to CERTIFY, not a decision, so it must
                # not shadow a refutation the weaker-premise routes can still
                # establish. A decided verdict (PASS/REFUTED) always stands.
                fallback = check_lex_occurrence_duplication_claim(
                    consensus_claim, contract_rules, contract_symbols
                )
                if fallback is None:
                    fallback = check_call_measure_step_counterexample_claim(
                        consensus_claim, contract
                    )
                if fallback is None:
                    # Ground-step search over the contract rule table; reaches
                    # the component shapes every route above must refuse
                    # (depths, positional counts, chains, root indicators).
                    fallback = check_measure_step_counterexample_claim(
                        consensus_claim, contract
                    )
                if fallback is not None:
                    native = fallback
            result = (
                native
                if native is not None
                else base_checker(consensus_claim)
            )
            result = upgrade_checker_result(
                result,
                consensus_claim,
                contract,
                root,
            )
            return _attach_lean_anchors(result, consensus_claim, instance_key)

        for attribute in ("__tgc_binding__",):
            if hasattr(base_checker, attribute):
                setattr(
                    checker_with_native_routes,
                    attribute,
                    getattr(base_checker, attribute),
                )
        setattr(
            checker_with_native_routes,
            "__tgc_contract_binding__",
            contract.binding(),
        )
        setattr(
            checker_with_native_routes,
            "__tgc_boundary_policy__",
            boundary_policy(contract),
        )
        if contract_rules:
            # Source-aware routes receive all readings, and bind certificates
            # to those readings as well as the contract rule table.
            setattr(
                checker_with_native_routes,
                "__tgc_contract_derived__",
                {
                    "kinds": set(CONTRACT_DERIVED_KINDS),
                    "input_sha256": root_control_input_sha256(
                        contract_rules, contract_symbols
                    ),
                    "input_sha256_for_claim": lambda claim: root_control_claim_input_sha256(
                        claim, contract_rules, contract_symbols
                    ),
                },
            )
        setattr(
            checker_with_native_routes,
            "__tgc_frame_only_kinds__",
            frame_only_kinds(contract),
        )
        return checker_with_native_routes
    raise ValueError(f"unsupported checker binding type {binding_type!r}")


def check_scoped_obligation(claim: dict[str, Any], contract: InstanceContract) -> CheckerResult | None:
    """Explicit restrictions never fall through to an unrestricted checker."""
    obj = claim.get("representative_checker_object") or {}
    payload = obj.get("payload") or {}
    core = claim.get("mathematical_core") or {}
    if payload.get("interpretation_scope") == "dependency_pair":
        # The dependency-pair route checks its pair set and complete usable-rule
        # premise in polynomial_interpretation_decision below.  It is not the
        # ground-term range obligation handled by this adapter.
        return None
    fields = {"rule_scope", "comparison", "interpretation_scope", "term_lower_bound"}
    named_size = (obj.get("kind") == core.get("kind") == "additive_measure"
                  and payload.get("named") == core.get("payload", {}).get("named") == "term_size"
                  and set(payload) <= {"named", "rule_scope", "comparison"})
    if not fields.intersection(payload) and not named_size:
        return None
    if any(core.get("payload", {}).get(k) != payload.get(k) for k in fields):
        return CheckerResult("UNKNOWN", False, "scope_core_checker_mismatch", None)
    decision = {"holds": None, "reason": "unsupported_scoped_obligation"}
    basis = "explicit_source_restriction"
    if (obj.get("kind") == core.get("kind") == "additive_measure"
            and payload.get("named") == "term_size"
            and core.get("payload", {}).get("named") == "term_size"
            and set(payload) <= {"named", "rule_scope", "comparison"}):
        all_rules = "rule_scope" not in payload
        scope = [r["name"] for r in contract.rules] if all_rules else payload["rule_scope"]
        decision = rule_size_decision(scope, payload.get("comparison", "strict"),
                                      contract.rules, contract.signature)
        basis = "node_count_descent_on_all_rules" if all_rules else "node_count_descent_on_selected_rules"
        if all_rules and decision.get("holds") and payload.get("comparison", "strict") == "strict":
            decision = {**decision, "supported_targets": FULL_SN_TARGETS,
                        "context_scope": "full_contextual_closure",
                        "context_size_identity": "size(C[t]) = size(t) + context_nodes(C)",
                        "context_constructor_weights": {symbol: {"constant": 1, "argument_weights": [1] * len(args)}
                                                        for symbol, args in contract.signature.items()}}
    elif (obj.get("kind") == core.get("kind") == "poly_interpretation"
          and payload.get("interpretation_scope") == "ground_terms"
          and interpretation_payload_matches(core, payload, contract.signature)
          and set(payload) <= {"map", "domain", "interpretation_scope", "term_lower_bound"}):
        decision = ground_term_interpretation_decision(
            core, contract.rules, contract.signature, payload.get("term_lower_bound"))
        basis = "proved_term_range_and_contextual_descent"
    holds = decision.get("holds")
    if holds is None:
        return CheckerResult("UNKNOWN", False, "scoped_obligation:" + decision["reason"], None)
    verdict = "PASS" if holds else "REFUTED"
    digest = canonical_sha256(obj)
    certificate = {
        "certificate_type": "scoped-proof-obligation/v1", "verdict": verdict,
        "input_sha256": digest, "checker_object_sha256": digest,
        "contract": contract.binding(), "decision": decision,
        "supported_targets": decision.get("supported_targets", []) if holds else [],
        "supported_targets_basis": basis,
    }
    if holds and "full_contextual_sn" in certificate["supported_targets"]:
        certificate["context_closure_license"] = (
            GLOBAL_ADDITIVE_MEASURE_LICENSE if named_size else "ground-term-range-strict-monotonicity/v1")
    return CheckerResult(verdict, False, decision["reason"], certificate)


def toy_checker(consensus_claim: dict[str, Any]) -> CheckerResult:
    """Small release self-test checker; not used for paper scoring."""
    core = consensus_claim.get("mathematical_core") or consensus_claim["core"]
    kind = core["kind"]
    payload = consensus_claim["representative_checker_object"].get("payload") or {}
    input_sha256 = canonical_sha256(
        consensus_claim["representative_checker_object"]
    )
    if (
        kind in {"dp_projection", "counter_projection"}
        and payload.get("argument") == 3
    ):
        return CheckerResult(
            "PASS",
            True,
            "toy_counter_projection_arg3",
            {
                "certificate_type": "toy-projection/v3",
                "checker_object_sha256": input_sha256,
                "input_sha256": input_sha256,
                "verdict": "PASS",
                "argument": 3,
                "supported_targets": [
                    "dependency_pair_termination",
                    "local_descent",
                ],
                "proof_strength": "dependency_pair_termination",
            },
        )
    if (
        kind in {"dp_projection", "counter_projection"}
        and payload.get("argument") in {1, 2}
    ):
        return CheckerResult(
            "REFUTED",
            False,
            f"toy_projection_wrong_argument[{payload.get('argument')}]",
            {
                "certificate_type": "toy-counterexample/v3",
                "checker_object_sha256": input_sha256,
                "input_sha256": input_sha256,
                "verdict": "REFUTED",
                "failing_rule": "step",
                "argument": payload.get("argument"),
                "supported_targets": [],
            },
        )
    return CheckerResult(
        "UNKNOWN", False, f"toy_checker_unsupported[{kind}]", None
    )


setattr(
    toy_checker,
    "__tgc_binding__",
    {
        "type": "builtin",
        "interface": "native_v1",
        "callable": "tgc.checkers:toy_checker",
        "version": "3.0.0",
    },
)


# ---- root-control checker (2026-07-27, coverage lever from RAND30 round 1) --
# Decides the root_control_proof claim against the contract's structured rule
# table: "every root step either yields a proper subterm of the redex or a
# term whose root symbol is irreducible at the root." Fully deterministic:
# parse the 8 rule terms, check each rule, certify with a per-rule table.


def _parse_term(text: str):
    """Parse name(arg,...) / bare-name terms. Returns (symbol, args) trees."""
    text = text.strip()
    if not text:
        raise ValueError("empty term")
    if "(" not in text:
        if not text.replace("_", "").isalnum():
            raise ValueError(f"bad term token {text!r}")
        return (text, [])
    head, rest = text.split("(", 1)
    head = head.strip()
    if not rest.endswith(")"):
        raise ValueError(f"unbalanced term {text!r}")
    body = rest[:-1]
    args, depth, current = [], 0, []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            args.append("".join(current))
            current = []
        else:
            current.append(char)
    if current or not body:
        args.append("".join(current))
    return (head, [_parse_term(item) for item in args if item.strip()])


def _is_proper_subterm(needle, haystack) -> bool:
    for arg in haystack[1]:
        if arg == needle or _is_proper_subterm(needle, arg):
            return True
    return False


def _rename_vars(term, signature_symbols: set[str], suffix: str):
    symbol, args = term
    if not args and symbol not in signature_symbols:
        return (symbol + suffix, [])
    return (
        symbol,
        [_rename_vars(arg, signature_symbols, suffix) for arg in args],
    )


def _unifies(left, right, signature_symbols: set[str]) -> bool:
    """Syntactic unifiability of two first-order terms (vars = non-signature
    leaves). Occurs-check included. Deterministic; used one-shot per pair."""

    def is_var(term):
        return not term[1] and term[0] not in signature_symbols

    def occurs(name, term):
        if is_var(term):
            return term[0] == name
        return any(occurs(name, arg) for arg in term[1])

    def substitute(term, bindings):
        while is_var(term) and term[0] in bindings:
            term = bindings[term[0]]
        if is_var(term):
            return term
        return (term[0], [substitute(arg, bindings) for arg in term[1]])

    bindings: dict[str, Any] = {}
    stack = [(left, right)]
    while stack:
        a, b = stack.pop()
        a = substitute(a, bindings)
        b = substitute(b, bindings)
        if a == b:
            continue
        if is_var(a):
            if occurs(a[0], b):
                return False
            bindings[a[0]] = b
            continue
        if is_var(b):
            if occurs(b[0], a):
                return False
            bindings[b[0]] = a
            continue
        if a[0] != b[0] or len(a[1]) != len(b[1]):
            return False
        stack.extend(zip(a[1], b[1]))
    return True


def root_control_decision(
    rules: tuple[dict[str, Any], ...],
    signature_symbols: set[str],
) -> dict[str, Any]:
    """Per-rule root-control table over the contract's structured rules.

    A rule satisfies the principle iff its RHS is a proper subterm of its LHS
    (strict structural descent) OR no instance of the RHS matches any rule
    LHS at the root (pattern-level: the RHS unifies with no LHS after
    renaming variables apart; symbol-level head tests are too coarse, e.g.
    integrate(merge(a,b)) never matches integrate(delta(t)))."""
    if not rules:
        return {"status": "unsupported", "reason": "contract_carries_no_rules"}
    parsed = []
    for rule in rules:
        lhs = _parse_term(str(rule["lhs"]))
        rhs = _parse_term(str(rule["rhs"]))
        parsed.append((str(rule.get("name")), lhs, rhs))
    table = []
    holds = True
    for name, lhs, rhs in parsed:
        proper = _is_proper_subterm(rhs, lhs)
        rhs_renamed = _rename_vars(rhs, signature_symbols, "#r")
        matching = [
            other_name
            for other_name, other_lhs, _ in parsed
            if _unifies(
                rhs_renamed,
                _rename_vars(other_lhs, signature_symbols, "#l"),
                signature_symbols,
            )
        ]
        root_irreducible = not matching
        ok = proper or root_irreducible
        holds = holds and ok
        table.append(
            {
                "rule": name,
                "rhs_proper_subterm_of_lhs": proper,
                "rhs_root": rhs[0],
                "rhs_root_irreducible_all_instances": root_irreducible,
                "rhs_matches_lhs_of": matching,
                "satisfies_principle": ok,
            }
        )
    return {"status": "ok", "holds": holds, "table": table}


# Public OperatorKO7 Lean declarations backing each construction family's
# decision semantics on the KO7/Schema-A instances. Anchor status is
# "cited": every string resolves to a real declaration on the public tree
# (github.com/MosesRahnama/OperatorKO7; resolution is pinned by a test),
# and a future runtime bridge may upgrade individual certificates to
# "replayed". Certificates on other instances carry no anchors.
KO7_KIND_LEAN_ANCHORS: dict[str, tuple[str, ...]] = {
    "additive_measure": (
        "OperatorKO7.Meta.BarrierClass_Classifier",
        "OperatorKO7.Meta.BarrierWitness",
    ),
    "poly_interpretation": (
        "OperatorKO7.Meta.BarrierClass_Classifier",
        "OperatorKO7.Meta.BarrierWitness",
    ),
    "call_measure": (
        "OperatorKO7.Meta.BarrierClass_Classifier",
    ),
    "lpo": (
        "OperatorKO7.Meta.TPDB_Export",
        "OperatorKO7.Meta.TTT2_CertificateReplay",
    ),
    "rpo": (
        "OperatorKO7.Meta.TPDB_Export",
        "OperatorKO7.Meta.TTT2_CertificateReplay",
    ),
    "dp_projection": (
        "OperatorKO7.Meta.DependencyPairs_TPDBExtraction",
        "OperatorKO7.Meta.TTT2_CertificateReplay.ko7FastReplay_sound",
    ),
    "counter_projection": (
        "OperatorKO7.Meta.DependencyPairs_TPDBExtraction",
    ),
    "size_change": (
        "OperatorKO7.Meta.DependencyPairs_TPDBExtraction",
    ),
}

_ANCHORED_INSTANCES = {"test01-ko7", "schema-a"}


def _attach_lean_anchors(
    result: CheckerResult,
    consensus_claim: dict[str, Any],
    instance_key: str | None,
) -> CheckerResult:
    if instance_key not in _ANCHORED_INSTANCES:
        return result
    if not isinstance(result.certificate, dict):
        return result
    core = consensus_claim.get("mathematical_core") or {}
    anchors = KO7_KIND_LEAN_ANCHORS.get(core.get("kind"))
    if not anchors:
        return result
    result.certificate.setdefault(
        "lean_anchors",
        {"anchors": list(anchors), "anchor_status": "cited"},
    )
    return result


def _symbol_and_var_counts(
    term, signature_symbols: set[str]
) -> tuple[dict[str, int], dict[str, int]]:
    symbols: dict[str, int] = {}
    variables: dict[str, int] = {}

    def walk(node):
        name, args = node
        if not args and name not in signature_symbols:
            variables[name] = variables.get(name, 0) + 1
            return
        symbols[name] = symbols.get(name, 0) + 1
        for arg in args:
            walk(arg)

    walk(term)
    return symbols, variables


def _nullary_signature_symbols(term, signature_symbols: set[str]) -> set[str]:
    constants: set[str] = set()

    def walk(node):
        name, args = node
        if name in signature_symbols and not args:
            constants.add(name)
        for arg in args:
            walk(arg)

    walk(term)
    return constants


def check_kbo_claim(
    consensus_claim: dict[str, Any],
    rules: tuple[dict[str, Any], ...],
    signature_symbols: set[str],
) -> CheckerResult | None:
    """Native v3 route for ``kbo_weights``; ``None`` = not this route's kind.

    The v3 contract carries an explicit ``variant`` enum, so the route reads
    the payload before it decides anything (the legacy adapter refuted every
    KBO claim on the instance label alone, channel L-12). Exactly one negative
    verdict is reachable, and only with a concrete witness: for STANDARD KBO
    the variable condition is necessary, so a rule whose RHS contains some
    variable more often than its LHS refutes the claim, and the certificate
    names that rule and that variable. Non-standard variants and standard
    claims with no violation stay UNKNOWN: no blanket refutation exists on
    this path. A stated nonpositive weight for a constant is also refuted,
    because standard KBO requires constants to weigh at least the positive
    variable weight.
    """

    core = consensus_claim.get("mathematical_core") or {}
    if core.get("kind") != "kbo_weights":
        return None
    checker_object = consensus_claim.get("representative_checker_object")
    if not isinstance(checker_object, dict):
        return CheckerResult("UNKNOWN", False, "kbo_checker_input_unavailable", None)
    payload = checker_object.get("payload") or {}
    variant = payload.get("variant")
    if variant != "standard":
        return CheckerResult(
            "UNKNOWN",
            False,
            f"kbo_variant_not_standard[{variant if variant is not None else 'absent'}]",
            None,
        )
    if not rules:
        return CheckerResult(
            "UNKNOWN",
            False,
            "standard_kbo_contract_carries_no_rules",
            None,
        )
    table: list[dict[str, Any]] = []
    constants: set[str] = set()
    for rule in rules:
        try:
            lhs = _parse_term(str(rule["lhs"]))
            rhs = _parse_term(str(rule["rhs"]))
            _, lhs_variables = _symbol_and_var_counts(lhs, signature_symbols)
            _, rhs_variables = _symbol_and_var_counts(rhs, signature_symbols)
            constants.update(_nullary_signature_symbols(lhs, signature_symbols))
            constants.update(_nullary_signature_symbols(rhs, signature_symbols))
        except (KeyError, ValueError) as error:
            return CheckerResult(
                "UNKNOWN",
                False,
                f"standard_kbo_rule_unparseable[{rule.get('name')}:{error}]",
                None,
            )
        violations = {
            variable: {
                "lhs_multiplicity": lhs_variables.get(variable, 0),
                "rhs_multiplicity": rhs_variables.get(variable, 0),
            }
            for variable in sorted(set(lhs_variables) | set(rhs_variables))
            if rhs_variables.get(variable, 0) > lhs_variables.get(variable, 0)
        }
        table.append(
            {
                "rule": str(rule.get("name") or ""),
                "lhs_variables": dict(sorted(lhs_variables.items())),
                "rhs_variables": dict(sorted(rhs_variables.items())),
                "variable_condition_violations": violations,
            }
        )
    weights = payload.get("weights")
    zero_weight_constants: list[dict[str, Any]] = []
    if isinstance(weights, dict):
        for symbol in sorted(constants):
            value = weights.get(symbol)
            if type(value) is int and value <= 0:
                zero_weight_constants.append({"symbol": symbol, "weight": value})
    input_sha256 = canonical_sha256(checker_object)
    if zero_weight_constants:
        witness = zero_weight_constants[0]
        return CheckerResult(
            "REFUTED",
            False,
            (
                "standard_kbo_constant_weight_not_positive"
                f"[symbol={witness['symbol']}|weight={witness['weight']}]"
            ),
            {
                "certificate_type": "standard-kbo-constant-admissibility-counterexample/v1",
                "checker_object_sha256": input_sha256,
                "input_sha256": input_sha256,
                "verdict": "REFUTED",
                "variant": "standard",
                "rule_table": table,
                "constant_weights_not_positive": zero_weight_constants,
                "witness": {
                    **witness,
                    "condition": (
                        "standard KBO assigns every constant at least the "
                        "positive variable weight"
                    ),
                },
                "supported_targets": [],
            },
        )
    failing = [row for row in table if row["variable_condition_violations"]]
    if failing:
        witness_row = failing[0]
        witness_variable, multiplicities = next(
            iter(sorted(witness_row["variable_condition_violations"].items()))
        )
        witness = {
            "rule": witness_row["rule"],
            "variable": witness_variable,
            "lhs_multiplicity": multiplicities["lhs_multiplicity"],
            "rhs_multiplicity": multiplicities["rhs_multiplicity"],
            "condition": "standard KBO requires |s|_x >= |t|_x for every variable x",
        }
        return CheckerResult(
            "REFUTED",
            False,
            (
                "standard_kbo_variable_condition_fails"
                f"[rule={witness['rule']}|variable={witness['variable']}"
                f"|lhs={witness['lhs_multiplicity']}"
                f"|rhs={witness['rhs_multiplicity']}]"
            ),
            {
                "certificate_type": "standard-kbo-variable-condition-counterexample/v1",
                "checker_object_sha256": input_sha256,
                "input_sha256": input_sha256,
                "verdict": "REFUTED",
                "variant": "standard",
                "rule_table": table,
                "failing_rules": [row["rule"] for row in failing],
                "witness": witness,
                "supported_targets": [],
            },
        )
    return CheckerResult(
        "UNKNOWN",
        False,
        "standard_kbo_variable_condition_holds_but_full_order_not_implemented",
        None,
    )


# A component is admissible for this route ONLY if it is a GLOBAL count of a
# signature symbol or the total term size. That restriction is load-bearing: the
# per-rule analysis covers full contextual closure precisely because those two
# measures are additive over term structure. Depth, positional, and redex counts
# are NOT additive that way, so they must never be folded in — this guard is
# checked BEFORE the accept patterns so a phrase like "count of grape in the
# third-argument position of any banana subterm" is refused rather than read as
# a global count.
_NON_GLOBAL_COMPONENT = re.compile(
    r"(?:depth|nest|level|position|arguments?\s+of|inside|within|subterms?\s+of"
    r"|redex|redices|top-?level|height|path|occurrence\s+in)",
    re.IGNORECASE,
)
# A trailing locative that names the WHOLE term is presentation, not a
# restriction: "number of eqW nodes in the term" is the same global count as
# "number of eqW nodes". Anything that narrows the region (a position, an
# argument, a subterm) is caught by `_NON_GLOBAL_COMPONENT` above, which is
# applied to the ORIGINAL text before this suffix is removed.
_WHOLE_TERM_LOCATIVE = re.compile(
    r"\s+(?:in|of|over|across)\s+(?:the\s+|a\s+)?"
    r"(?:whole\s+|entire\s+|full\s+)?(?:term|expression|trace|t)$",
    re.IGNORECASE,
)
_SIZE_COMPONENT = re.compile(
    r"^(?:total\s+)?(?:term\s+size|size(?:\s+of\s+(?:the\s+)?term)?"
    r"|(?:total\s+)?(?:number|count)\s+of\s+(?:all\s+)?constructors"
    r"|constructor[\s-]+count|(?:total\s+)?constructor\s+count)$",
    re.IGNORECASE,
)


def _parse_global_lex_component(
    component: Any, signature_symbols: set[str]
) -> tuple[str, str | None] | None:
    """Map one stated component to ('count', symbol) or ('size', None).

    Recognizes the canonical spellings the normalizer already emits plus the
    prose spellings measured on live rounds ("total # of delta constructors",
    "term size (number of constructors)"). Bounded to declared signature
    symbols and refused outright for any non-global qualifier.
    """

    if not isinstance(component, str):
        return None
    original = component.strip()
    if not original:
        return None
    # DENY FIRST, over the ORIGINAL text. The label and gloss strips below
    # delete a trailing parenthetical, so a disqualifying qualifier hidden
    # inside it ("number of delta constructors (in the third-argument position
    # of any recDelta subterm)") would never reach the guard if the guard ran
    # only over the stripped candidates. Measured 2026-07-30: that leak read a
    # positional count as a global one, which is exactly the premise the route's
    # context-closure license depends on.
    if _NON_GLOBAL_COMPONENT.search(original):
        return None
    text = original
    match = re.fullmatch(r"count\((\w+)\)", text)
    if match and match.group(1) in signature_symbols:
        return ("count", match.group(1))
    if text == "size":
        return ("size", None)
    # Drop a leading naming label ("d = ...", "S(t) = ...").
    text = re.sub(r"^[A-Za-z][\w']{0,12}(?:\s*\([^)]{0,12}\))?\s*=\s*", "", text)
    # Drop a parenthetical gloss ("term size (number of constructors)").
    stripped = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    for candidate in (stripped, text):
        if not candidate or _NON_GLOBAL_COMPONENT.search(candidate):
            continue
        normalized = re.sub(r"\s+", " ", candidate.strip().rstrip(".")).strip()
        normalized = _WHOLE_TERM_LOCATIVE.sub("", normalized).strip()
        if _SIZE_COMPONENT.fullmatch(normalized):
            return ("size", None)
        count = re.fullmatch(
            r"(?:total\s+)?(?:number|count|#)\s*(?:of\s+)?(\w+)\s*"
            r"(?:constructors?|symbols?|nodes?|occurrences?)?",
            normalized,
            re.IGNORECASE,
        )
        if count and count.group(1) in signature_symbols:
            return ("count", count.group(1))
        count = re.fullmatch(
            r"(\w+)[\s-]+(?:constructor\s+)?(?:count|occurrences?)",
            normalized,
            re.IGNORECASE,
        )
        if count and count.group(1) in signature_symbols:
            return ("count", count.group(1))
    return None


# --- refutation-only route: occurrence sums under a duplicating rule ---------
# Certifying a measure needs the monotone-algebra premise (a step inside any
# context shifts each component by the rule's local delta); depth and positional
# counts genuinely fail it, which is why `_NON_GLOBAL_COMPONENT` blocks them from
# the certifying route and must keep doing so.
#
# REFUTING needs strictly less: ONE substitution under which the measure fails to
# decrease. When a rule duplicates a variable x, a component that SUMS over
# occurrences in the whole term satisfies
#     mu(RHS.s) - mu(LHS.s) = base + SUM_v (mult_RHS(v) - mult_LHS(v)) * mu(s(v))
# with mult(x) strictly positive, so choosing s(x) with a large enough
# contribution drives the difference positive. The FIRST component increasing is
# already decisive: lexicographic comparison never consults the tail. That
# argument needs no additivity over contexts, so it applies exactly where the
# certifying route is (correctly) forbidden. Measured 2026-07-30: seven refused
# rows state such a measure and every one is baseline-Incorrect.
#
# This route can ONLY return REFUTED. It never grants a target licence and never
# reaches a PASS.
_OCCURRENCE_AGGREGATION = re.compile(
    r"\b(?:total|sum|number|count|multiset)\b|#", re.IGNORECASE
)
_WHOLE_TERM_SCOPE = re.compile(
    r"\b(?:all|every|any|each|subterms?|nodes?|constructors?|occurrences?)\b"
    r"|\bin\s+(?:the\s+)?(?:term|t)\b",
    re.IGNORECASE,
)
# A maximum or a rank is not a sum: duplicating a subterm need not raise it.
# A root-level measure counts nothing inside the duplicated variable.
_NOT_AN_OCCURRENCE_SUM = re.compile(
    r"\b(?:max|maximum|min|minimum|rank|top-?level|outermost|root)\b",
    re.IGNORECASE,
)


def _is_whole_term_occurrence_sum(component: Any) -> bool:
    """Conservative: an unbounded sum/count over occurrences in the WHOLE term."""

    if not isinstance(component, str) or not component.strip():
        return False
    text = component.strip()
    if _NOT_AN_OCCURRENCE_SUM.search(text):
        return False
    return bool(
        _OCCURRENCE_AGGREGATION.search(text) and _WHOLE_TERM_SCOPE.search(text)
    )


def duplicating_rules(
    rules: tuple[dict[str, Any], ...], signature_symbols: set[str]
) -> list[dict[str, Any]]:
    """Rules whose RHS contains a variable more often than their LHS."""

    found: list[dict[str, Any]] = []
    for rule in rules:
        _, lhs_var = _symbol_and_var_counts(
            _parse_term(str(rule["lhs"])), signature_symbols
        )
        _, rhs_var = _symbol_and_var_counts(
            _parse_term(str(rule["rhs"])), signature_symbols
        )
        duplicated = {
            name: {
                "lhs_multiplicity": lhs_var.get(name, 0),
                "rhs_multiplicity": rhs_var.get(name, 0),
            }
            for name in set(lhs_var) | set(rhs_var)
            if rhs_var.get(name, 0) > lhs_var.get(name, 0)
        }
        if duplicated:
            found.append(
                {"rule": str(rule.get("name") or ""), "duplicated": duplicated}
            )
    return found


def check_lex_occurrence_duplication_claim(
    consensus_claim: dict[str, Any],
    contract_rules: tuple[dict[str, Any], ...],
    signature_symbols: set[str],
) -> CheckerResult | None:
    """REFUTED-only route; returns None when it does not apply."""

    core = consensus_claim.get("mathematical_core") or {}
    if core.get("kind") != "lex_tuple":
        return None
    checker_object = consensus_claim.get("representative_checker_object")
    if not isinstance(checker_object, dict):
        return None
    payload = checker_object.get("payload") or {}
    components = payload.get("components")
    if not isinstance(components, list) or not components:
        return None
    if "order" in payload and canonical_tuple_order(payload.get("order")).get(
        "mode"
    ) != "lex":
        return None
    # The FIRST component decides: if it can increase, the tuple cannot decrease
    # whatever the tail means.
    leading = components[0]
    if not _is_whole_term_occurrence_sum(leading):
        return None
    duplicating = duplicating_rules(contract_rules, signature_symbols)
    if not duplicating:
        return None
    witness = duplicating[0]
    variable, multiplicities = next(iter(sorted(witness["duplicated"].items())))
    input_sha256 = canonical_sha256(checker_object)
    return CheckerResult(
        verdict="REFUTED",
        compliant=False,
        detail=(
            "lex_occurrence_sum_duplication_fails"
            f"[{witness['rule']}|duplicated:{variable}]"
        ),
        certificate={
            "certificate_type": "lex-occurrence-duplication-counterexample/v1",
            "checker_object_sha256": input_sha256,
            "input_sha256": input_sha256,
            "verdict": "REFUTED",
            "leading_component": str(leading),
            "leading_component_basis": "whole_term_occurrence_sum",
            "witness": {
                "rule": witness["rule"],
                "variable": variable,
                **multiplicities,
                "argument": (
                    "the leading component sums over occurrences in the whole "
                    "term, so substituting the duplicated variable with a large "
                    "enough contribution makes that component increase; "
                    "lexicographic comparison never reaches the tail"
                ),
            },
            "duplicating_rules": duplicating,
            "supported_targets": [],
        },
    )


def check_measure_step_counterexample_claim(
    consensus_claim: dict[str, Any],
    contract: InstanceContract,
) -> CheckerResult | None:
    """REFUTED-only ground-step route; returns None when it does not apply.

    Runs AFTER the certifying lex-count route and AFTER the duplication
    route: a payload either of those can decide is never diverted here. Its
    reach is the components those routes must refuse — depths, positional
    counts, chain lengths, root indicators — where certifying is genuinely
    obstructed (no additivity over contexts) but ONE concrete non-decreasing
    step still refutes the stated claim. The certificate is that step.
    """

    decision = measure_step_counterexample(
        consensus_claim,
        signature=contract.signature,
        rules=contract.rules,
        glyph_folds=contract.glyph_folds,
    )
    if decision is None:
        return None
    return CheckerResult(
        verdict=decision["verdict"],
        compliant=False,
        detail=decision["detail"],
        certificate=decision["certificate"],
    )


def check_call_measure_step_counterexample_claim(
    consensus_claim: dict[str, Any],
    contract: InstanceContract,
) -> CheckerResult | None:
    """Typed call-measure route, with fail-closed semantic extensions.

    The ground-step evaluator decides whole-term argument measures, exact
    recursive-subterm sums, and the closed affine leading-chain aggregate.
    Other aggregate refinements remain
    explicit checker input, but until an exact evaluator decides them they
    must shadow legacy adapters that would silently check a different object.
    """

    decision = call_measure_step_counterexample(
        consensus_claim,
        signature=contract.signature,
        rules=contract.rules,
    )
    if decision is None:
        core = consensus_claim.get("mathematical_core") or {}
        checker_object = consensus_claim.get("representative_checker_object")
        payload = (
            checker_object.get("payload") or {}
            if isinstance(checker_object, dict)
            else {}
        )
        if core.get("kind") == "call_measure":
            extended_fields = {"measure_mode", "occurrence_offset"}
            if extended_fields & payload.keys():
                return CheckerResult(
                    verdict="UNKNOWN",
                    compliant=False,
                    detail="extended_call_measure_semantics_unregistered",
                    certificate=None,
                )
            scope = payload.get("scope")
            supported_aggregate_measures = {
                "size",
                "term_size",
                "third_argument_size",
                "S_count",
                "symbol_count_S",
                "depth",
                "third_argument_depth",
            }
            aggregate_measures = {
                scope: supported_aggregate_measures
                for scope in (
                    "all_F_subterms_sum",
                    "all_recursive_subterms_sum",
                    "all_F_subterms_multiset",
                    "all_recursive_subterms_multiset",
                )
            }
            if scope in aggregate_measures and (
                payload.get("argument") != 3
                or payload.get("measure") not in aggregate_measures[scope]
            ):
                return CheckerResult(
                    verdict="UNKNOWN",
                    compliant=False,
                    detail="aggregate_call_measure_shape_unregistered",
                    certificate=None,
                )
        return None
    return CheckerResult(
        verdict=decision["verdict"],
        compliant=False,
        detail=decision["detail"],
        certificate=decision["certificate"],
    )


def lex_count_tuple_decision(
    components: list[str],
    rules: tuple[dict[str, Any], ...],
    signature_symbols: set[str],
) -> dict[str, Any]:
    """Duplication-aware decision for lexicographic tuples of GLOBAL symbol
    counts (count(X)) and term size. Global counts change under contextual
    rewriting exactly by the rule's local delta, so per-rule symbolic
    analysis covers full contextual closure. Per component the delta is
    base + sum(mult_delta(v) * value_in(v_sigma)); a component can increase
    for some substitution iff its base is positive or a variable is
    duplicated (mult_delta > 0) — the classic failure the live rounds hit
    on rec_succ duplicating s."""
    parsed_components = []
    unparsed_component: str | None = None
    for component in components:
        parsed = _parse_global_lex_component(component, signature_symbols)
        if parsed is None:
            # Prefix stop, not a hard failure: lexicographic comparison consults
            # components in order and never reaches the tail once an earlier one
            # settles the rule. A REFUTATION found inside the parsed prefix is
            # therefore sound whatever the tail means. A prefix that merely
            # looks decreasing is NOT promoted to a PASS (see below).
            unparsed_component = component
            break
        parsed_components.append(parsed)
    if not parsed_components:
        return {"status": "unsupported", "component": components[0]}
    if not rules:
        return {"status": "unsupported", "component": "<no rules>"}
    table = []
    holds = True
    for rule in rules:
        lhs_sym, lhs_var = _symbol_and_var_counts(
            _parse_term(str(rule["lhs"])), signature_symbols
        )
        rhs_sym, rhs_var = _symbol_and_var_counts(
            _parse_term(str(rule["rhs"])), signature_symbols
        )
        var_delta = {
            name: rhs_var.get(name, 0) - lhs_var.get(name, 0)
            for name in set(lhs_var) | set(rhs_var)
        }
        duplicated = sorted(
            name for name, delta in var_delta.items() if delta > 0
        )
        rule_result = None
        for mode, symbol in parsed_components:
            if mode == "count":
                base = rhs_sym.get(symbol, 0) - lhs_sym.get(symbol, 0)
            else:
                base = sum(rhs_sym.values()) - sum(lhs_sym.values())
            if base > 0 or duplicated:
                # SOUND failure witness: the component can strictly INCREASE
                # for some substitution (a positive base, or a variable the
                # rule copies), so the tuple provably fails to descend on this
                # rule whatever the unread tail means.
                rule_result = {
                    "rule": str(rule.get("name")),
                    "decreases": False,
                    "component": f"count({symbol})" if symbol else "size",
                    "base_delta": base,
                    "duplicated_variables": duplicated,
                    "witness_kind": "component_can_increase",
                }
                break
            strict = base < 0 or (
                mode == "size"
                and any(delta < 0 for delta in var_delta.values())
            )
            if strict:
                rule_result = {
                    "rule": str(rule.get("name")),
                    "decreases": True,
                    "component": f"count({symbol})" if symbol else "size",
                    "base_delta": base,
                }
                break
        if rule_result is None:
            # FLAT prefix: every parsed component is exactly equal on this rule
            # and none strictly decreased. With the whole tuple parsed that is a
            # sound refutation (take every variable to `void`: the tuple is then
            # equal, so it does not strictly descend). On a PARTIAL read it is
            # NOT: lexicographic comparison defers to the unread tail at exactly
            # this point, and the tail could supply the strict decrease.
            rule_result = {
                "rule": str(rule.get("name")),
                "decreases": False,
                "component": None,
                "reason": "no_strictly_decreasing_component",
                "witness_kind": "parsed_prefix_flat",
            }
        holds = holds and rule_result["decreases"]
        table.append(rule_result)
    failing = [row for row in table if not row["decreases"]]
    sound_witnesses = [
        row for row in failing if row.get("witness_kind") == "component_can_increase"
    ]
    if unparsed_component is not None:
        if holds:
            # The parsed prefix alone would certify, but the tail was never read
            # and the context-invariance premise below is only established for
            # global components. Refuse the PASS, fail-closed.
            return {
                "status": "unsupported",
                "component": unparsed_component,
                "reason": "prefix_would_pass_but_tail_unread",
            }
        if not sound_witnesses:
            # Every failure is a flat prefix, which the unread tail may settle.
            return {
                "status": "unsupported",
                "component": unparsed_component,
                "reason": "prefix_flat_tail_unread",
            }
    return {
        "status": "ok",
        "holds": holds,
        "table": table,
        "parsed_prefix_only": unparsed_component is not None,
        "unparsed_component": unparsed_component,
        # Rules whose failure is carried by a SOUND increase/duplication
        # witness. The certificate must name one of these rather than the
        # first failing row, so a published counterexample is never a flat
        # prefix that the tail could have settled.
        "sound_witness_rules": [row["rule"] for row in sound_witnesses],
        # Machine-checked premise for context closure, recorded so the license
        # is derived from the decision rather than from the construction kind:
        # every component is a GLOBAL count of a signature symbol or the total
        # term size, and both are additive over term structure. A step inside
        # any context C therefore shifts each component by exactly the rule's
        # local delta, so the per-rule symbolic analysis above already covers
        # every context. The analysis is duplication-aware, so a PASS also
        # certifies that no rule copies a variable.
        "context_invariance": {
            "measure_class": "global_symbol_counts_and_term_size",
            "all_components_context_additive": True,
            "components": [
                {"mode": mode, "symbol": symbol}
                for mode, symbol in parsed_components
            ],
            "duplication_checked": True,
        },
    }


def _lex_count_tuple_license(decision: dict[str, Any]) -> str | None:
    """Context-closure license for a lex-count-tuple PASS, or ``None``.

    Read strictly out of the decision: every component must have been parsed
    as a global symbol count or total size, every rule row must strictly
    decrease, and no rule row may carry a duplicated variable. Anything else
    caps at root-only scope.
    """

    invariance = decision.get("context_invariance")
    if not isinstance(invariance, dict):
        return None
    if invariance.get("measure_class") != "global_symbol_counts_and_term_size":
        return None
    if invariance.get("all_components_context_additive") is not True:
        return None
    if invariance.get("duplication_checked") is not True:
        return None
    components = invariance.get("components")
    if not isinstance(components, list) or not components:
        return None
    if any(
        not isinstance(item, dict) or item.get("mode") not in {"count", "size"}
        for item in components
    ):
        return None
    table = decision.get("table")
    if not isinstance(table, list) or not table:
        return None
    if any(
        row.get("decreases") is not True or row.get("duplicated_variables")
        for row in table
    ):
        return None
    return GLOBAL_ADDITIVE_MEASURE_LICENSE


def check_lex_count_tuple_claim(
    consensus_claim: dict[str, Any],
    contract_rules: tuple[dict[str, Any], ...],
    signature_symbols: set[str],
) -> CheckerResult | None:
    """Native route for lex tuples of global counts/size; None = not ours."""
    core = consensus_claim.get("mathematical_core") or {}
    if core.get("kind") != "lex_tuple":
        return None
    checker_object = consensus_claim.get("representative_checker_object")
    if not isinstance(checker_object, dict):
        return None
    payload = checker_object.get("payload") or {}
    components = payload.get("components")
    if not isinstance(components, list) or not components:
        return None
    if "order" in payload and canonical_tuple_order(payload.get("order")).get(
        "mode"
    ) != "lex":
        return None
    decision = lex_count_tuple_decision(
        [str(component) for component in components],
        contract_rules,
        signature_symbols,
    )
    if decision.get("status") != "ok":
        return None
    checker_object_sha256 = canonical_sha256(checker_object)
    if not decision["holds"]:
        failing = [
            row for row in decision["table"] if not row["decreases"]
        ]
        # Prefer a rule whose failure is carried by a sound increase or
        # duplication witness; a flat-prefix row is only ever a legitimate
        # witness on a FULLY parsed tuple, and even then the increase witness
        # is the stronger counterexample to publish.
        sound = [
            row
            for row in failing
            if row.get("witness_kind") == "component_can_increase"
        ]
        witness = (sound or failing)[0]
        return CheckerResult(
            verdict="REFUTED",
            compliant=False,
            detail=(
                "lex_count_tuple_fails["
                f"{witness['rule']}"
                + (
                    f"|duplicated:{','.join(witness['duplicated_variables'])}"
                    if witness.get("duplicated_variables")
                    else ""
                )
                + "]"
            ),
            certificate={
                "certificate_type": "lex-count-tuple/v1",
                "checker_object_sha256": checker_object_sha256,
                "input_sha256": checker_object_sha256,
                "verdict": "REFUTED",
                "rule_table": decision["table"],
                "witness_rules": [row["rule"] for row in failing],
                # The subset carrying a SOUND increase/duplication witness.
                # On a partial read this list is what licenses the refutation,
                # so it is published rather than left implicit in the table.
                "sound_witness_rules": decision.get("sound_witness_rules", []),
                "parsed_prefix_only": decision.get("parsed_prefix_only", False),
            },
        )
    license_marker = _lex_count_tuple_license(decision)
    support = (
        _support(
            FULL_SN_TARGETS,
            basis="global_additive_measure_delta_is_context_invariant",
            license_marker=license_marker,
        )
        if license_marker is not None
        else _support(
            ROOT_ONLY_TARGETS,
            basis="context_invariance_premise_not_established_by_decision",
        )
    )
    certificate: dict[str, Any] = {
        "certificate_type": "lex-count-tuple/v1",
        "checker_object_sha256": checker_object_sha256,
        "input_sha256": checker_object_sha256,
        "verdict": "PASS",
        "rule_table": decision["table"],
        "context_invariance": decision.get("context_invariance"),
        "supported_targets": support["supported_targets"],
        "supported_targets_basis": support["supported_targets_basis"],
    }
    if "context_closure_license" in support:
        certificate["context_closure_license"] = support["context_closure_license"]
    return CheckerResult(
        verdict="PASS",
        compliant=False,
        detail="lex_count_tuple_decreases_on_every_rule",
        certificate=certificate,
    )


def root_control_input_sha256(
    contract_rules: tuple[dict[str, Any], ...],
    signature_symbols: set[str],
) -> str:
    """Hash of the rule-table input, before any source-stated obligations."""
    return canonical_sha256(
        {
            "decision_source": "contract_rule_table",
            "rules": [dict(rule) for rule in contract_rules],
            "signature_symbols": sorted(signature_symbols),
        }
    )


def root_control_claim_input_sha256(claim, rules, symbols) -> str:
    objects = source_objects(claim)
    base = root_control_input_sha256(rules, symbols)
    if objects and all(isinstance(obj, dict) and obj.get("payload") == {}
                       for obj in objects.values()):
        return base
    return canonical_sha256({"contract_input_sha256": base, "source_objects": objects})


# Deterministic typers for the root_control_proof free-text fields. The
# template instructs extractors to transcribe the EXACT stated wording and
# promises that "deterministic code types it if supported" — this is that
# code, previously missing: any payload text fell through to the rule-table
# PASS, certifying a root-only decision for a claim whose own stated relation
# could be contextual (measured 2026-08-08 by an external audit:
# relation="this says contextual closure" earned PASS). Fail-closed: an
# ABSENT field is fine (the kind itself asserts the root-only argument); a
# PRESENT field must type, and a relation typing as contextual is not this
# route's object.
_ROOT_CONTROL_NEGATED_CONTEXTUAL = re.compile(
    r"\b(?:no|not|without|lacks?|absence of|is not|are not|never)\b"
    r"(?:\s+\S+){0,4}?\s*"
    r"(?:context(?:ual)?(?:[\s-]closure)?|congruence|compatible[\s-]closure)",
    re.IGNORECASE,
)
_ROOT_CONTROL_CONTEXTUAL = re.compile(
    r"\bcontextual\b|context(?:ual)?[\s-]closure|compatible[\s-]closure|congruence"
    r"|any position|at any position|inside (?:a |any )?(?:sub)?term"
    r"|under (?:a |any )?context|rewrite anywhere",
    re.IGNORECASE,
)
_ROOT_CONTROL_ROOT = re.compile(
    r"\broot\b|top[\s-]?level|outermost|head (?:position|step|symbol)"
    r"|as written|as literally (?:defined|written)|only what is (?:explicitly )?declared",
    re.IGNORECASE,
)
_ROOT_CONTROL_HEAD_FACT = re.compile(
    r"\b(?:no (?:rewrite )?rules? (?:exist )?for|has no (?:rewrite )?rules?|"
    r"no rule with|no lhs rules|which has no (?:rewrite )?rules?)\b"
    r"|\b(?:all )?redexes? (?:are|involve|possible|occur)\b"
    r"|\breductions? only occur within\b",
    re.IGNORECASE,
)
_ROOT_CONTROL_NEGATED_ROOT = re.compile(
    r"\b(?:not|never|without)\b(?:\s+[\w-]+){0,6}?\s+"
    r"(?:root|top[\s-]?level|outermost)\b|\bnon[\s-]root\b"
    r"|\b(?:below|beneath|under) (?:the )?root\b",
    re.IGNORECASE,
)


def _root_control_field_type(
    field: str, value: Any
) -> tuple[bool, str | None]:
    """(accept, reason-if-rejected) for one stated root_control field."""

    if value is None:
        return True, None
    text = fold_presentation(str(value), markdown_emphasis=True).strip()
    if not text:
        return True, None
    if field == "relation":
        negative = _ROOT_CONTROL_NEGATED_CONTEXTUAL.search(text)
        remaining = _ROOT_CONTROL_NEGATED_CONTEXTUAL.sub("", text)
        if _ROOT_CONTROL_NEGATED_ROOT.search(remaining):
            return False, "root_control_relation_negates_root_restriction"
        if _ROOT_CONTROL_CONTEXTUAL.search(remaining):
            return False, "root_control_relation_typed_contextual"
        if negative or _ROOT_CONTROL_ROOT.search(text):
            return True, None
        if _ROOT_CONTROL_HEAD_FACT.search(text):
            return True, None
        return False, "root_control_relation_untyped"
    return False, "root_control_principle_untyped"


def check_root_control_claim(
    consensus_claim: dict[str, Any],
    contract_rules: tuple[dict[str, Any], ...],
    signature_symbols: set[str],
) -> CheckerResult | None:
    """Native route for concrete root_control_proof claims; None = not ours."""
    core = consensus_claim.get("mathematical_core") or {}
    if core.get("kind") != "root_control_proof":
        return None
    decision = root_control_decision(contract_rules, signature_symbols)
    if decision.get("status") != "ok":
        return CheckerResult(
            verdict="UNKNOWN",
            compliant=False,
            detail=f"root_control_pending[{decision.get('reason')}]",
            certificate=None,
        )
    objects = source_objects(consensus_claim)
    expected_passes = {str(p) for p in consensus_claim.get("supporting_passes", [])}
    if not objects or (expected_passes and set(objects) != expected_passes):
        return CheckerResult("UNKNOWN", False, "root_control_readings_missing", None)
    readings = {}
    for pass_id, obj in sorted(objects.items()):
        if not isinstance(obj, dict) or obj.get("kind") != "root_control_proof":
            return CheckerResult("UNKNOWN", False, "root_control_reading_invalid", None)
        readings[pass_id] = check_payload(
            obj.get("payload"), contract_rules, signature_symbols,
            decision, _root_control_field_type,
        )
    verdicts = {reading["verdict"] for reading in readings.values()}
    if "UNKNOWN" in verdicts or len(verdicts) != 1:
        return CheckerResult(
            "UNKNOWN", False,
            "root_control_readings_unresolved[" + ";".join(
                f"{key}:{value['detail']}" for key, value in readings.items()
            ) + "]", None,
        )
    verdict = next(iter(verdicts))
    input_sha256 = root_control_claim_input_sha256(
        consensus_claim, contract_rules, signature_symbols
    )
    source_bound = any(obj.get("payload") for obj in objects.values())
    binding = {
        "certificate_type": "root-control-source-obligations/v1" if source_bound
        else "root-control-rule-table/v1",
        "input_sha256": input_sha256,
        "decision_source": "contract_rules_and_all_source_readings" if source_bound
        else "contract_rule_table",
        "input_independent": not source_bound,
        "source_objects": objects,
        "reading_decisions": readings,
    }
    if verdict == "REFUTED":
        failing = [
            row["rule"] for row in decision["table"]
            if not row["satisfies_principle"]
        ]
        failing = sorted(set(failing) | {
            reading["witness"]["rule"] for reading in readings.values()
            if "witness" in reading
        })
        return CheckerResult(
            verdict="REFUTED",
            compliant=False,
            detail=";".join(sorted({reading["detail"] for reading in readings.values()})),
            certificate={
                **binding,
                "verdict": "REFUTED",
                "rule_table": decision["table"],
                "witness_rules": failing,
            },
        )
    # Every supplied reading passed its own stated obligations. Root-only
    # termination still supplies no contextual-termination certificate.
    return CheckerResult(
        verdict="PASS",
        compliant=False,
        detail="root_control_rule_table_holds",
        certificate={
            **binding,
            "verdict": "PASS",
            "rule_table": decision["table"],
            "supported_targets": ["root_only_termination", "local_descent"],
        },
    )
