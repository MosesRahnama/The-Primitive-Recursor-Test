"""Hash-bound authority receipts for scope/transport upgrades.

A lower checker proves only the construction it directly checks.  This module may
upgrade the certificate's supported target only after verifying an explicit,
content-addressed external authority against the loaded benchmark contract.

The current authority format supports archived CPF/CeTA receipts.  It verifies the
exact CPF input TRS, source TRS, processor tags, projection coordinate, certification
log, and every declared SHA-256.  It does not claim to execute CeTA locally.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .common import canonical_sha256, read_json, resolve_within, sha256_file
from .config import InstanceContract
from .native_math import Term, call_measure_dependency_pair_decision, parse_term
from .scoring import CheckerResult

AUTHORITY_REGISTRY_VERSION = "tgc-authority-registry/1.0.0"
AUTHORITY_RECEIPT_VERSION = "tgc-authority-receipt/1.0.0"
CALL_MEASURE_DP_BRIDGE_VERSION = "tgc-call-measure-dp-authority-bridge/1.1.0"

# Closed field surface of a registry entry. Every field here is either
# hash-verified, cross-checked against an archived artifact, enum-pinned, or
# consumed by one of those cross-checks. Nothing in a registry entry is
# allowed to be inert: an entry carrying an unknown field, or missing a known
# one, fails closed rather than being absorbed into the receipt hash.
AUTHORITY_ENTRY_FIELDS: frozenset[str] = frozenset(
    {
        "authority_id",
        "instance_key",
        "construction_kind",
        "payload_constraints",
        "source_path",
        "source_sha256",
        "external_artifact_path",
        "external_artifact_sha256",
        "certification_log_path",
        "certification_log_sha256",
        "certificate_filename",
        "certifier",
        "prover",
        "proof_status",
        "processor_stack",
        "projection_symbol",
        "projection_argument_one_based",
        "relation_scope",
        "closure_scope",
        "supported_targets",
        "negative_inference_allowed",
        "symbol_aliases",
    }
)

AUTHORITY_PROOF_STATUSES = frozenset({"externally_certified_archived"})
AUTHORITY_RELATION_SCOPES = frozenset({"source_trs"})
AUTHORITY_CLOSURE_SCOPES = frozenset({"context_closed", "root_only"})
AUTHORITY_TARGET_VOCABULARY = frozenset(
    {
        "full_contextual_sn",
        "root_only_termination",
        "dependency_pair_termination",
        "local_descent",
    }
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class AuthorityError(ValueError):
    """An authority exists but does not verify for the requested claim."""


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def _verify_registry_entry(authority: dict[str, Any]) -> None:
    """Structural pin over the CLOSED registry field surface.

    Runs for every entry at registry load, so an added, removed, or
    wrong-typed field is rejected before any receipt can be built.
    """

    observed = set(authority)
    missing = sorted(AUTHORITY_ENTRY_FIELDS - observed)
    unknown = sorted(observed - AUTHORITY_ENTRY_FIELDS)
    if missing or unknown:
        raise AuthorityError(
            f"authority entry field surface mismatch: missing={missing}, unknown={unknown}"
        )
    for field in (
        "authority_id",
        "instance_key",
        "construction_kind",
        "source_path",
        "external_artifact_path",
        "certification_log_path",
        "certificate_filename",
        "certifier",
        "prover",
    ):
        value = authority.get(field)
        if not isinstance(value, str) or not value.strip():
            raise AuthorityError(f"authority field {field} must be a nonempty string")
    for field in ("source_sha256", "external_artifact_sha256", "certification_log_sha256"):
        value = authority.get(field)
        if not isinstance(value, str) or not _SHA256_PATTERN.fullmatch(value):
            raise AuthorityError(f"authority field {field} must be a lowercase sha256")
    if authority.get("proof_status") not in AUTHORITY_PROOF_STATUSES:
        raise AuthorityError(
            f"unsupported authority proof_status {authority.get('proof_status')!r}"
        )
    if authority.get("relation_scope") not in AUTHORITY_RELATION_SCOPES:
        raise AuthorityError(
            f"unsupported authority relation_scope {authority.get('relation_scope')!r}"
        )
    if authority.get("closure_scope") not in AUTHORITY_CLOSURE_SCOPES:
        raise AuthorityError(
            f"unsupported authority closure_scope {authority.get('closure_scope')!r}"
        )
    if authority.get("negative_inference_allowed") is not False:
        raise AuthorityError("current authority format forbids negative inference")
    if not isinstance(authority.get("payload_constraints"), dict):
        raise AuthorityError("authority payload_constraints must be an object")
    aliases = authority.get("symbol_aliases")
    if not isinstance(aliases, dict) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in aliases.items()
    ):
        raise AuthorityError("authority symbol_aliases must be a string map")
    stack = authority.get("processor_stack")
    if not isinstance(stack, list) or not stack or any(
        not isinstance(item, str) or not item for item in stack
    ):
        raise AuthorityError("processor_stack must be a nonempty string array")
    if not isinstance(authority.get("projection_symbol"), str) or not authority[
        "projection_symbol"
    ]:
        raise AuthorityError("authority projection_symbol must be a nonempty string")
    argument = authority.get("projection_argument_one_based")
    if not isinstance(argument, int) or isinstance(argument, bool) or argument < 1:
        raise AuthorityError(
            "authority projection_argument_one_based must be a positive integer"
        )
    targets = authority.get("supported_targets")
    if not isinstance(targets, list) or not targets or any(
        not isinstance(item, str) or item not in AUTHORITY_TARGET_VOCABULARY
        for item in targets
    ):
        raise AuthorityError("authority supported_targets is malformed")
    # The scope fields are not decoration: a context-closed target has to be
    # backed by a context-closed, source-relation authority.
    if "full_contextual_sn" in targets and (
        authority.get("closure_scope") != "context_closed"
        or authority.get("relation_scope") != "source_trs"
    ):
        raise AuthorityError(
            "full_contextual_sn requires relation_scope=source_trs and "
            "closure_scope=context_closed"
        )
    if authority["certificate_filename"] != Path(
        authority["external_artifact_path"]
    ).name:
        raise AuthorityError(
            "certificate_filename does not name the external artifact: "
            f"{authority['certificate_filename']!r} vs "
            f"{authority['external_artifact_path']!r}"
        )


def _verify_attribution(
    authority: dict[str, Any],
    log_text: str,
    cpf_root: ET.Element,
) -> dict[str, Any]:
    """Cross-check the attribution fields against the archived artifacts.

    ``certifier`` and ``prover`` used to be copied into the receipt unchecked,
    so flipping either one only changed the receipt hash instead of being
    rejected (channel L-17). Both are now bound to content: the certifier must
    be named by the archived certification log, and the prover must be named
    by that log AND by the CPF's own proof origin.
    """

    haystack = _normalize(log_text)
    certifier = _normalize(authority["certifier"])
    prover = _normalize(authority["prover"])
    if certifier not in haystack:
        raise AuthorityError(
            f"certifier {authority['certifier']!r} is not named by the archived "
            f"certification log {authority['certification_log_path']!r}"
        )
    if prover not in haystack:
        raise AuthorityError(
            f"prover {authority['prover']!r} is not named by the archived "
            f"certification log {authority['certification_log_path']!r}"
        )
    tool = cpf_root.find("./origin/proofOrigin/tool")
    if tool is None:
        raise AuthorityError("CPF carries no proof origin tool element")
    name = tool.find("name")
    version = tool.find("version")
    origin = _normalize(
        f"{(name.text or '') if name is not None else ''} "
        f"{(version.text or '') if version is not None else ''}"
    )
    if not origin:
        raise AuthorityError("CPF proof origin tool has no name or version")
    if prover not in origin:
        raise AuthorityError(
            f"prover {authority['prover']!r} does not match the CPF proof origin "
            f"tool {origin!r}"
        )
    return {
        "certifier_named_by_certification_log": True,
        "prover_named_by_certification_log": True,
        "prover_matches_cpf_proof_origin": True,
        "cpf_proof_origin_tool": origin,
    }


def _registry_path(artifact_root: Path) -> Path:
    return resolve_within(
        artifact_root,
        "authorities/registry.json",
        label="authority registry",
        must_exist=True,
    )


def load_authority_registry(artifact_root: Path) -> dict[str, Any]:
    path = _registry_path(artifact_root)
    value = read_json(path)
    if not isinstance(value, dict):
        raise AuthorityError("authority registry must be an object")
    if value.get("authority_registry_version") != AUTHORITY_REGISTRY_VERSION:
        raise AuthorityError(
            f"unsupported authority registry version {value.get('authority_registry_version')!r}"
        )
    authorities = value.get("authorities")
    if not isinstance(authorities, list) or any(
        not isinstance(item, dict) for item in authorities
    ):
        raise AuthorityError("authority registry authorities must be an object array")
    identifiers = [str(item.get("authority_id") or "") for item in authorities]
    if any(not item for item in identifiers) or len(set(identifiers)) != len(identifiers):
        raise AuthorityError("authority IDs must be nonempty and unique")
    for item in authorities:
        _verify_registry_entry(item)
    return {
        "path": path,
        "value": value,
        "sha256": sha256_file(path),
        "canonical_sha256": canonical_sha256(value),
    }


def authority_registry_binding(artifact_root: Path) -> dict[str, Any] | None:
    try:
        registry = load_authority_registry(artifact_root)
    except (FileNotFoundError, AuthorityError, OSError, json.JSONDecodeError):
        return None
    return {
        "registry_path": "authorities/registry.json",
        "registry_sha256": registry["sha256"],
        "registry_canonical_sha256": registry["canonical_sha256"],
        "registry_version": AUTHORITY_REGISTRY_VERSION,
    }


def _first_child(element: ET.Element) -> ET.Element:
    for child in element:
        return child
    raise AuthorityError(f"CPF element <{element.tag}> has no term child")


def _cpf_term(element: ET.Element) -> tuple[str, str, tuple[Any, ...]]:
    if element.tag == "var":
        name = (element.text or "").strip()
        if not name:
            raise AuthorityError("CPF variable has no name")
        return ("var", name, ())
    if element.tag != "funapp":
        raise AuthorityError(f"unsupported CPF term element <{element.tag}>")
    direct_name = element.find("name")
    sharp_name = element.find("sharp/name")
    name_element = direct_name if direct_name is not None else sharp_name
    if name_element is None or not (name_element.text or "").strip():
        raise AuthorityError("CPF function application has no symbol name")
    arguments = tuple(_cpf_term(_first_child(arg)) for arg in element.findall("arg"))
    return ("fun", (name_element.text or "").strip(), arguments)


def _native_term(
    term: Term,
    signature: set[str],
) -> tuple[str, str, tuple[Any, ...]]:
    head, arguments = term
    if not arguments and head not in signature:
        return ("var", head, ())
    return ("fun", head, tuple(_native_term(item, signature) for item in arguments))


def _rename_symbols(
    term: tuple[str, str, tuple[Any, ...]],
    aliases: dict[str, str],
) -> tuple[str, str, tuple[Any, ...]]:
    tag, name, arguments = term
    if tag == "var":
        return term
    return (
        "fun",
        aliases.get(name, name),
        tuple(_rename_symbols(item, aliases) for item in arguments),
    )


def _alpha_rule(
    lhs: tuple[str, str, tuple[Any, ...]],
    rhs: tuple[str, str, tuple[Any, ...]],
) -> tuple[Any, Any]:
    names: dict[str, str] = {}

    def visit(term: tuple[str, str, tuple[Any, ...]]) -> tuple[Any, ...]:
        tag, name, arguments = term
        if tag == "var":
            canonical = names.setdefault(name, f"v{len(names)}")
            return ("var", canonical)
        return ("fun", name, tuple(visit(item) for item in arguments))

    return visit(lhs), visit(rhs)


def _contract_rules(contract: InstanceContract) -> list[tuple[Any, Any]]:
    signature = contract.signature_symbols
    return sorted(
        (
            _alpha_rule(
                _native_term(parse_term(str(rule["lhs"])), signature),
                _native_term(parse_term(str(rule["rhs"])), signature),
            )
            for rule in contract.rules
        ),
        key=repr,
    )


def _cpf_input_rules(
    cpf_root: ET.Element,
    aliases: dict[str, str],
) -> list[tuple[Any, Any]]:
    rule_elements = cpf_root.findall("./input/trsInput/trs/rules/rule")
    if not rule_elements:
        raise AuthorityError("CPF has no input TRS rules")
    output: list[tuple[Any, Any]] = []
    for rule in rule_elements:
        lhs = rule.find("lhs")
        rhs = rule.find("rhs")
        if lhs is None or rhs is None:
            raise AuthorityError("CPF input rule is missing lhs or rhs")
        output.append(
            _alpha_rule(
                _rename_symbols(_cpf_term(_first_child(lhs)), aliases),
                _rename_symbols(_cpf_term(_first_child(rhs)), aliases),
            )
        )
    return sorted(output, key=repr)


def _source_trs_rules(
    path: Path,
    contract: InstanceContract,
    aliases: dict[str, str],
) -> list[tuple[Any, Any]]:
    text = path.read_text(encoding="utf-8-sig")
    signature = contract.signature_symbols | set(aliases)
    output: list[tuple[Any, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("(VAR") or line in {"(RULES", ")"}:
            continue
        if "->" not in line:
            continue
        lhs_text, rhs_text = (part.strip() for part in line.split("->", 1))
        lhs = _rename_symbols(_native_term(parse_term(lhs_text), signature), aliases)
        rhs = _rename_symbols(_native_term(parse_term(rhs_text), signature), aliases)
        output.append(_alpha_rule(lhs, rhs))
    if not output:
        raise AuthorityError("authority source TRS has no parsed rules")
    return sorted(output, key=repr)


def _verify_processor_stack(
    cpf_root: ET.Element,
    authority: dict[str, Any],
) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    stack = authority.get("processor_stack")
    if not isinstance(stack, list) or any(not isinstance(item, str) for item in stack):
        raise AuthorityError("processor_stack must be a string array")
    tag_requirements = {
        "dependency_pairs": ".//dpTrans",
        "dependency_graph": ".//depGraphProc",
        "scc": ".//component/realScc",
        "subterm_criterion": ".//subtermProc",
    }
    for processor in stack:
        if processor not in tag_requirements:
            raise AuthorityError(f"unsupported processor tag {processor!r}")
        elements = cpf_root.findall(tag_requirements[processor])
        if processor == "scc":
            ok = any((item.text or "").strip().lower() == "true" for item in elements)
        else:
            ok = bool(elements)
        checks[processor] = ok
        if not ok:
            raise AuthorityError(f"CPF lacks required processor {processor}")
    return checks


def _verify_projection(cpf_root: ET.Element, authority: dict[str, Any]) -> dict[str, Any]:
    wanted_symbol = str(authority.get("projection_symbol") or "")
    wanted_argument = authority.get("projection_argument_one_based")
    if not wanted_symbol or not isinstance(wanted_argument, int):
        raise AuthorityError("authority projection metadata is incomplete")
    observed: list[dict[str, Any]] = []
    for entry in cpf_root.findall(".//argumentFilterEntry"):
        name = entry.find("sharp/name")
        collapsing = entry.find("collapsing")
        if name is None or collapsing is None:
            continue
        try:
            argument = int((collapsing.text or "").strip())
        except ValueError:
            continue
        observed.append(
            {
                "symbol": (name.text or "").strip(),
                "argument_one_based": argument,
            }
        )
    match = any(
        item["symbol"] == wanted_symbol
        and item["argument_one_based"] == wanted_argument
        for item in observed
    )
    if not match:
        raise AuthorityError(
            f"CPF projection {wanted_symbol}[{wanted_argument}] not found; observed={observed}"
        )
    return {"wanted": [wanted_symbol, wanted_argument], "observed": observed}


def _verified_file(
    artifact_root: Path,
    authority: dict[str, Any],
    path_field: str,
    hash_field: str,
) -> Path:
    relative = authority.get(path_field)
    expected = authority.get(hash_field)
    if not isinstance(relative, str) or not isinstance(expected, str):
        raise AuthorityError(f"authority lacks {path_field}/{hash_field}")
    path = resolve_within(
        artifact_root,
        relative,
        label=path_field,
        must_exist=True,
    )
    if path.is_symlink() or not path.is_file():
        raise AuthorityError(f"authority asset is not a regular file: {relative}")
    observed = sha256_file(path)
    if observed != expected:
        raise AuthorityError(
            f"authority hash mismatch for {relative}: expected {expected}, observed {observed}"
        )
    return path


def _authority_matches(
    authority: dict[str, Any],
    contract: InstanceContract,
    kind: str,
    payload: dict[str, Any],
) -> bool:
    if authority.get("instance_key") != contract.instance_key:
        return False
    if authority.get("construction_kind") != kind:
        return False
    constraints = authority.get("payload_constraints")
    return isinstance(constraints, dict) and all(
        payload.get(key) == value for key, value in constraints.items()
    )


def _registered_call_measures(contract: InstanceContract) -> set[str]:
    schema = contract.payload_schemas.get("call_measure") or {}
    properties = schema.get("properties") or {}
    measure = properties.get("measure") or {}
    values = measure.get("enum") or []
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        return set()
    return set(values)


def _call_measure_bridge_query(
    contract: InstanceContract,
    core: dict[str, Any],
    checker_object: dict[str, Any],
    lower_certificate: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Translate one exact call-level object to an authority lookup query.

    This does not change the source construction kind.  It establishes only
    that the already-certified local call descent is the same argument
    projection consumed by a ``dp_projection`` authority.  The resulting
    bridge metadata, including the lower-certificate hash, is folded into the
    authority receipt hash by :func:`verify_authority`.
    """

    core_payload = core.get("payload")
    checker_payload = checker_object.get("payload")
    if not isinstance(core_payload, dict) or not isinstance(checker_payload, dict):
        return None, "call_measure_bridge_payload_missing"
    if core_payload != checker_payload:
        return None, "call_measure_bridge_core_checker_payload_mismatch"
    allowed_fields = {"scope", "argument", "measure", "measure_mode"}
    extra_fields = sorted(set(checker_payload) - allowed_fields)
    if extra_fields:
        return None, f"call_measure_bridge_extra_fields[{extra_fields}]"
    if checker_payload.get("scope") != "dependency_pair":
        return None, "call_measure_bridge_scope_not_dependency_pair"
    argument = checker_payload.get("argument")
    if not isinstance(argument, int) or isinstance(argument, bool) or argument < 1:
        return None, "call_measure_bridge_argument_missing_or_invalid"
    registered = _registered_call_measures(contract)
    measure_was_defaulted = "measure" not in checker_payload
    measure = checker_payload.get("measure", "size")
    if not isinstance(measure, str) or measure not in registered:
        return None, f"call_measure_bridge_measure_unregistered[{measure!r}]"
    if measure_was_defaulted and "size" not in registered:
        return None, "call_measure_bridge_default_size_unregistered"

    if not isinstance(lower_certificate, dict):
        return None, "call_measure_bridge_local_certificate_missing"
    checker_sha256 = canonical_sha256(checker_object)
    if lower_certificate.get("certificate_type") != (
        "contract-native-mathematical-decision/v1"
    ):
        return None, "call_measure_bridge_local_certificate_type_mismatch"
    if lower_certificate.get("kind") != "call_measure":
        return None, "call_measure_bridge_local_certificate_kind_mismatch"
    if lower_certificate.get("instance_key") != contract.instance_key:
        return None, "call_measure_bridge_local_certificate_instance_mismatch"
    if lower_certificate.get("contract") != contract.binding():
        return None, "call_measure_bridge_local_certificate_contract_mismatch"
    if lower_certificate.get("checker_object_sha256") != checker_sha256:
        return None, "call_measure_bridge_local_certificate_object_mismatch"
    if lower_certificate.get("verdict") != "PASS":
        return None, "call_measure_bridge_local_certificate_not_pass"
    if lower_certificate.get("supported_targets") != ["local_descent"]:
        return None, "call_measure_bridge_local_certificate_scope_mismatch"
    decision = lower_certificate.get("decision")
    if not isinstance(decision, dict):
        return None, "call_measure_bridge_local_decision_missing"
    expected_decision = call_measure_dependency_pair_decision(
        core,
        checker_object,
        contract.rules,
        contract.signature,
        registered,
    )
    if decision != expected_decision:
        return None, "call_measure_bridge_local_decision_not_contract_replay"
    if (
        decision.get("status") != "ok"
        or decision.get("holds") is not True
        or decision.get("decision_family")
        != "dependency_pair_argument_proper_subterm"
        or decision.get("argument") != argument
        or decision.get("measure") != measure
        or decision.get("measure_mode") != checker_payload.get("measure_mode", "total")
        or decision.get("measure_was_defaulted") is not measure_was_defaulted
        or decision.get("strict_proper_subterm_descent") is not True
    ):
        return None, "call_measure_bridge_local_decision_mismatch"
    table = decision.get("rule_table")
    if not isinstance(table, list) or not table:
        return None, "call_measure_bridge_local_rule_table_missing"
    calls = [
        call
        for row in table
        if isinstance(row, dict) and isinstance(row.get("calls"), list)
        for call in row["calls"]
    ]
    if (
        not calls
        or len(calls) != decision.get("recursive_call_total")
        or any(
            not isinstance(call, dict)
            or call.get("proper_subterm") is not True
            or not call.get("proper_subterm_paths_one_based")
            or call.get("measure_strict") is not True
            or not call.get("measure_strict_paths_one_based")
            for call in calls
        )
    ):
        return None, "call_measure_bridge_local_rule_table_mismatch"

    return {
        "lookup_kind": "dp_projection",
        "lookup_payload": {"argument": argument},
        "bridge": {
            "bridge_version": CALL_MEASURE_DP_BRIDGE_VERSION,
            "source_construction_kind": "call_measure",
            "authority_construction_kind": "dp_projection",
            "argument": argument,
            "measure": measure,
            "measure_mode": checker_payload.get("measure_mode", "total"),
            "measure_was_defaulted": measure_was_defaulted,
            "source_checker_object_sha256": checker_sha256,
            "local_certificate_sha256": canonical_sha256(lower_certificate),
            "local_decision_family": "dependency_pair_argument_proper_subterm",
        },
    }, None


def _authority_query(
    contract: InstanceContract,
    core: dict[str, Any],
    checker_object: dict[str, Any],
    lower_certificate: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    kind = str(core.get("kind") or "")
    payload = checker_object.get("payload")
    if not isinstance(payload, dict):
        return None, "authority_payload_unavailable"
    if kind == "call_measure":
        return _call_measure_bridge_query(
            contract, core, checker_object, lower_certificate
        )
    return {
        "lookup_kind": kind,
        "lookup_payload": payload,
        "bridge": None,
    }, None


def verify_authority(
    contract: InstanceContract,
    consensus_claim: dict[str, Any],
    artifact_root: Path,
    *,
    lower_certificate: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Return a verified upgrade receipt, or a fail-closed diagnostic reason."""

    core = consensus_claim.get("mathematical_core")
    checker_object = consensus_claim.get("representative_checker_object")
    if not isinstance(core, dict) or not isinstance(checker_object, dict):
        return None, "authority_claim_shape_unavailable"
    query, query_reason = _authority_query(
        contract, core, checker_object, lower_certificate
    )
    if query is None:
        return None, query_reason
    kind = str(query["lookup_kind"])
    payload = query["lookup_payload"]
    try:
        registry = load_authority_registry(artifact_root)
    except (FileNotFoundError, AuthorityError, OSError, json.JSONDecodeError) as error:
        return None, f"authority_registry_unavailable[{type(error).__name__}:{error}]"
    matches = [
        item
        for item in registry["value"]["authorities"]
        if _authority_matches(item, contract, kind, payload)
    ]
    if not matches:
        return None, "no_matching_authority"
    if len(matches) != 1:
        return None, "multiple_matching_authorities"
    authority = matches[0]
    try:
        source_path = _verified_file(
            artifact_root, authority, "source_path", "source_sha256"
        )
        cpf_path = _verified_file(
            artifact_root,
            authority,
            "external_artifact_path",
            "external_artifact_sha256",
        )
        log_path = _verified_file(
            artifact_root,
            authority,
            "certification_log_path",
            "certification_log_sha256",
        )
        cpf_root = ET.fromstring(cpf_path.read_bytes())
        aliases = {
            str(key): str(value)
            for key, value in (authority.get("symbol_aliases") or {}).items()
        }
        contract_rules = _contract_rules(contract)
        cpf_rules = _cpf_input_rules(cpf_root, aliases)
        source_rules = _source_trs_rules(source_path, contract, aliases)
        if cpf_rules != contract_rules:
            raise AuthorityError("CPF input TRS does not match the loaded contract")
        if source_rules != contract_rules:
            raise AuthorityError("authority source TRS does not match the loaded contract")
        processor_checks = _verify_processor_stack(cpf_root, authority)
        projection_check = _verify_projection(cpf_root, authority)
        certificate_filename = str(authority.get("certificate_filename") or "")
        log_text = log_path.read_text(encoding="utf-8-sig")
        certified_line = next(
            (
                line
                for line in log_text.splitlines()
                if certificate_filename in line and re.search(r"\bCERTIFIED\b", line)
            ),
            None,
        )
        if certified_line is None:
            raise AuthorityError(
                f"certification log has no CERTIFIED row for {certificate_filename}"
            )
        # Re-run the closed-surface pin on the matched entry (defence in depth
        # against a caller that supplied a registry value directly) and bind
        # the attribution fields to the archived artifacts.
        _verify_registry_entry(authority)
        attribution_checks = _verify_attribution(authority, log_text, cpf_root)
        supported_targets = authority["supported_targets"]
        entry_sha256 = canonical_sha256(authority)
        receipt = {
            "authority_receipt_version": AUTHORITY_RECEIPT_VERSION,
            "authority_id": authority["authority_id"],
            "authority_entry_sha256": entry_sha256,
            "authority_registry_path": "authorities/registry.json",
            "authority_registry_sha256": registry["sha256"],
            "authority_registry_canonical_sha256": registry["canonical_sha256"],
            "proof_status": authority.get("proof_status"),
            "relation_scope": authority.get("relation_scope"),
            "closure_scope": authority.get("closure_scope"),
            "supported_targets": list(supported_targets),
            "negative_inference_allowed": False,
            "source_path": authority["source_path"],
            "source_sha256": authority["source_sha256"],
            "external_artifact_path": authority["external_artifact_path"],
            "external_artifact_sha256": authority["external_artifact_sha256"],
            "certification_log_path": authority["certification_log_path"],
            "certification_log_sha256": authority["certification_log_sha256"],
            "certifier": authority["certifier"],
            "prover": authority["prover"],
            "certificate_filename": certificate_filename,
            "certified_log_line": certified_line.strip(),
            "contract_binding": contract.binding(),
            "contract_rule_count": len(contract_rules),
            "cpf_input_rule_count": len(cpf_rules),
            "source_rule_count": len(source_rules),
            "processor_checks": processor_checks,
            "projection_check": projection_check,
            # The COMPLETE registry entry travels in the receipt, so no field
            # of the entry sits outside the receipt-verified surface.
            "authority_entry": {
                field: authority[field] for field in sorted(AUTHORITY_ENTRY_FIELDS)
            },
            "authority_entry_field_surface": sorted(AUTHORITY_ENTRY_FIELDS),
            "attribution_checks": attribution_checks,
            "verification_checks": {
                "all_hashes_match": True,
                "cpf_input_matches_contract": True,
                "source_trs_matches_contract": True,
                "processor_stack_matches": True,
                "projection_matches": True,
                "archived_certification_log_matches": True,
                "registry_entry_field_surface_closed": True,
                "certifier_matches_archived_log": True,
                "prover_matches_archived_log_and_cpf_origin": True,
                "scope_fields_support_declared_targets": True,
            },
        }
        if query["bridge"] is not None:
            receipt["construction_bridge"] = query["bridge"]
        receipt["authority_receipt_sha256"] = canonical_sha256(receipt)
        return receipt, None
    except (AuthorityError, ET.ParseError, FileNotFoundError, OSError, ValueError) as error:
        return None, f"authority_verification_failed[{type(error).__name__}:{error}]"


def upgrade_checker_result(
    result: CheckerResult,
    consensus_claim: dict[str, Any],
    contract: InstanceContract,
    artifact_root: Path,
) -> CheckerResult:
    """Upgrade a lower PASS only through a verified positive authority receipt."""

    if result.verdict != "PASS" or not isinstance(result.certificate, dict):
        return result
    core = consensus_claim.get("mathematical_core")
    if not isinstance(core, dict) or core.get("kind") not in {
        "dp_projection",
        "call_measure",
    }:
        return result
    receipt, reason = verify_authority(
        contract,
        consensus_claim,
        artifact_root,
        lower_certificate=result.certificate,
    )
    certificate = dict(result.certificate)
    if receipt is None:
        certificate["authority_resolution"] = {
            "status": "not_upgraded",
            "reason": reason,
        }
        return CheckerResult(
            verdict=result.verdict,
            compliant=result.compliant,
            detail=f"{result.detail}|authority_not_upgraded[{reason}]",
            certificate=certificate,
        )
    targets = sorted(
        set(certificate.get("supported_targets") or [])
        | set(receipt["supported_targets"])
    )
    certificate["supported_targets"] = targets
    certificate["supported_targets_basis"] = (
        "local_certificate_plus_hash_verified_authority_transport"
    )
    certificate["proof_strength"] = (
        "full_contextual_sn"
        if "full_contextual_sn" in targets
        else certificate.get("proof_strength")
    )
    certificate["authority_resolution"] = {
        "status": "upgraded",
        "receipt": receipt,
    }
    return CheckerResult(
        verdict=result.verdict,
        compliant=result.compliant,
        detail=f"{result.detail}|authority_upgraded[{receipt['authority_id']}]",
        certificate=certificate,
    )
