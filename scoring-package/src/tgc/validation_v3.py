from __future__ import annotations

from typing import Any

from .config import InstanceContract
from .coverage import CoverageOracleError, coverage_oracle_receipt
from .evidence import bind_anchor_table
from .lineage import find_pass, find_roster_entry, verify_run_manifest
from .source_coverage import paragraph_coverage_issues
from .source_specification import specification_issues, specification_schema
from .source_values import argument_evidence_check
from .validation import (
    ValidationIssue,
    _full_schema_issues,
    _is_placeholder,
    _payload_schema_issues,
    _pointer_exists,
    load_sources,
)

TOP_LEVEL_FIELDS = {
    "schema_version",
    "contract",
    "run_binding",
    "session",
    "extractor",
    "record_status",
    "anchors",
    "claims",
    "primary",
    "coverage",
    "notes",
}

CLAIM_FIELDS = {
    "local_id",
    "source_id",
    "kind",
    "claim_status",
    "answer_role",
    "claimed_target",
    "specificity",
    "transcription",
    "evidence",
    "axis_evidence",
    "field_evidence",
    "rejection_evidence",
}


def _issue(code: str, path: str, message: Any) -> ValidationIssue:
    return ValidationIssue(code, path, str(message))


def _check_exact_fields(
    value: Any,
    wanted: set[str],
    *,
    path: str,
    prefix: str,
) -> list[ValidationIssue]:
    if not isinstance(value, dict):
        return [_issue(f"{prefix}_TYPE", path, "must be an object")]
    issues: list[ValidationIssue] = []
    for key in sorted(set(value) - wanted):
        issues.append(_issue(f"{prefix}_FIELD_UNKNOWN", f"{path}.{key}", "unexpected field"))
    for key in sorted(wanted - set(value)):
        issues.append(_issue(f"{prefix}_FIELD_REQUIRED", path, f"missing {key!r}"))
    return issues


def _anchor_refs(
    value: Any,
    *,
    path: str,
    anchors: dict[str, dict[str, Any]],
    used: set[str],
    expected_source: str | None = None,
    require_nonempty: bool = True,
) -> tuple[list[str], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        return [], [_issue("ANCHOR_REFS_TYPE", path, "must be an array of anchor IDs")]
    if require_nonempty and not value:
        issues.append(_issue("ANCHOR_REFS_EMPTY", path, "at least one anchor ID is required"))
    if len(set(value)) != len(value):
        issues.append(_issue("ANCHOR_REFS_DUPLICATE", path, "anchor IDs may not repeat"))
    valid: list[str] = []
    for index, anchor_id in enumerate(value):
        if anchor_id not in anchors:
            issues.append(_issue("ANCHOR_REF_UNKNOWN", f"{path}[{index}]", anchor_id))
            continue
        if expected_source is not None and anchors[anchor_id]["source_id"] != expected_source:
            issues.append(
                _issue(
                    "ANCHOR_SOURCE_MISMATCH",
                    f"{path}[{index}]",
                    f"claim source {expected_source!r}, anchor source {anchors[anchor_id]['source_id']!r}",
                )
            )
            continue
        used.add(anchor_id)
        valid.append(anchor_id)
    return valid, issues


FAITHFULNESS_PROVENANCE_ANCHOR = (
    "OperatorKO7.Meta.DomainTransformerCertificate_Faithfulness."
    "invariants_one_to_five_imply_faithful"
)


def evaluate_construction_faithfulness(
    record: dict[str, Any],
    contract: InstanceContract,
) -> dict[str, Any]:
    """Report structural anchoring separately from semantic fidelity.

    A quote's presence does not establish its entailment of a payload, role,
    or scope. The historical I1-I4 names remain structural checks only.
    The cited abstract theorem is not a proof of this implementation.
    """
    claims = record.get("claims") or []
    i2 = True
    i3 = True
    i5 = True
    for claim in claims:
        kind = claim.get("kind")
        schema = contract.payload_schemas.get(kind) or {}
        properties = set((schema.get("properties") or {}).keys())
        transcription = claim.get("transcription") or {}
        if isinstance(transcription, dict):
            if not set(transcription).issubset(properties):
                i2 = False
            if claim.get("specificity") == "concrete" and not set(
                schema.get("required") or []
            ).issubset(set(transcription)):
                i2 = False
        if not claim.get("evidence"):
            i3 = False
        axis_evidence = claim.get("axis_evidence") or {}
        for axis in contract.record_model.get(
            "axis_evidence_fields",
            ("claim_status", "answer_role", "claimed_target", "specificity"),
        ):
            if not axis_evidence.get(axis):
                i3 = False
        field_evidence = claim.get("field_evidence") or {}
        if isinstance(transcription, dict):
            try:
                required_evidence = contract.definition(
                    str(kind)
                ).required_evidence_pointers(transcription)
            except KeyError:
                i2 = False
                required_evidence = ()
            if any(not field_evidence.get(pointer) for pointer in required_evidence):
                i5 = False
    dispositions = (record.get("coverage") or {}).get(
        "mention_dispositions"
    ) or []
    claimed_ids = {
        claim_id
        for item in dispositions
        for claim_id in item.get("claim_ids") or []
    }
    i4 = all(
        claim.get("local_id") in claimed_ids for claim in claims
    )
    invariants = {
        "i1_syntactic": True,
        "i2_schema": i2,
        "i3_invertibility": i3,
        "i4_coverage": i4,
        "field_anchors_present": i5,
    }
    extraction_id = str(
        (record.get("extractor") or {}).get("extraction_id") or ""
    )
    return {
        "faithfulness_version": "construction_evidence/v2",
        **invariants,
        "all_pass": all(invariants.values()),
        "assurance_scope": "structural_anchoring_only",
        "i5_conservativity": False if not i5 else None,
        "semantic_fidelity": "not_established",
        "explicit_value_checks": [
            argument_evidence_check(claim, record.get("anchors") or {})
            for claim in claims
        ],
        "mode": (
            "constructed"
            if extraction_id.startswith("construct-")
            else "extracted"
        ),
        "provenance_anchor": FAITHFULNESS_PROVENANCE_ANCHOR,
        "provenance_anchor_status": "cited",
    }


def _run_binding_issues(
    record: dict[str, Any],
    contract: InstanceContract,
    run_manifest: dict[str, Any] | None,
    *,
    official_mode: bool,
    extra_pass_entry: dict[str, Any] | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    binding = record.get("run_binding")
    wanted = {"run_id", "run_contract_sha256", "roster_entry_sha256", "pass_id"}
    issues.extend(_check_exact_fields(binding, wanted, path="$.run_binding", prefix="RUN_BINDING"))
    if not isinstance(binding, dict):
        return issues
    for key in wanted:
        if not isinstance(binding.get(key), str) or not binding.get(key):
            issues.append(_issue("RUN_BINDING_VALUE", f"$.run_binding.{key}", "must be nonempty"))
    if run_manifest is None:
        if official_mode:
            issues.append(
                _issue(
                    "RUN_MANIFEST_REQUIRED",
                    "$.run_binding",
                    "official v3 validation requires the deployed RUN_MANIFEST.json",
                )
            )
        return issues
    for item in verify_run_manifest(run_manifest):
        issues.append(_issue(item["code"], item["path"], item["message"]))
    if run_manifest.get("instance_key") != contract.instance_key:
        issues.append(_issue("RUN_INSTANCE", "$.run_binding", run_manifest.get("instance_key")))
    if run_manifest.get("contract") != contract.binding():
        issues.append(_issue("RUN_CONTRACT_BINDING", "$.run_binding", "manifest contract differs"))
    if binding.get("run_id") != run_manifest.get("run_id"):
        issues.append(_issue("RUN_ID_BINDING", "$.run_binding.run_id", run_manifest.get("run_id")))
    if binding.get("run_contract_sha256") != run_manifest.get("run_contract_sha256"):
        issues.append(
            _issue(
                "RUN_CONTRACT_BINDING",
                "$.run_binding.run_contract_sha256",
                run_manifest.get("run_contract_sha256"),
            )
        )
    session = record.get("session") or {}
    slug = session.get("session_slug")
    entry = find_roster_entry(run_manifest, slug)
    if entry is None:
        issues.append(_issue("RUN_ROSTER_MISSING", "$.session.session_slug", slug))
    else:
        if binding.get("roster_entry_sha256") != entry.get("roster_entry_sha256"):
            issues.append(
                _issue(
                    "RUN_ROSTER_BINDING",
                    "$.run_binding.roster_entry_sha256",
                    entry.get("roster_entry_sha256"),
                )
            )
        declared_sources = sorted(
            session.get("sources", []), key=lambda item: str(item.get("source_id"))
        )
        roster_sources = sorted(
            entry.get("sources", []), key=lambda item: str(item.get("source_id"))
        )
        if declared_sources != roster_sources:
            issues.append(
                _issue(
                    "RUN_SOURCE_BINDING",
                    "$.session.sources",
                    "record sources differ from the immutable roster entry",
                )
            )
    extractor = record.get("extractor") or {}
    pass_number = extractor.get("pass_number")
    pass_entry = find_pass(run_manifest, pass_number) if isinstance(pass_number, int) else None
    if (
        pass_entry is None
        and isinstance(extra_pass_entry, dict)
        and extra_pass_entry.get("pass_number") == pass_number
    ):
        # Tiebreak pass: registered post-gate by the hash-verified
        # TIEBREAK_MANIFEST (resolved by the caller), never by mutating the
        # immutable run manifest.
        pass_entry = extra_pass_entry
    if pass_entry is None:
        issues.append(_issue("RUN_PASS_MISSING", "$.extractor.pass_number", pass_number))
    elif binding.get("pass_id") != pass_entry.get("pass_id"):
        issues.append(_issue("RUN_PASS_BINDING", "$.run_binding.pass_id", pass_entry.get("pass_id")))
    return issues


def validate_record_v3(
    record: dict[str, Any],
    contract: InstanceContract,
    *,
    require_independence: bool = True,
    bind_evidence: bool = True,
    run_manifest: dict[str, Any] | None = None,
    official_mode: bool = True,
    extra_pass_entry: dict[str, Any] | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not isinstance(record, dict):
        return [_issue("RECORD_TYPE", "$", "record must be an object")]
    if _is_placeholder(record):
        issues.append(_issue("UNFILLED_PLACEHOLDER", "$", "record contains a placeholder"))
    issues.extend(_check_exact_fields(record, TOP_LEVEL_FIELDS, path="$", prefix="RECORD"))
    if TOP_LEVEL_FIELDS - set(record):
        return issues
    if record.get("schema_version") != contract.schema_version:
        issues.append(_issue("SCHEMA_VERSION", "$.schema_version", contract.schema_version))
    if record.get("contract") != contract.binding():
        issues.append(_issue("CONTRACT_BINDING", "$.contract", "record does not match loaded contract"))
    issues.extend(
        _run_binding_issues(
            record,
            contract,
            run_manifest,
            official_mode=official_mode,
            extra_pass_entry=extra_pass_entry,
        )
    )

    status = record.get("record_status")
    if status not in contract.record_statuses:
        issues.append(_issue("RECORD_STATUS", "$.record_status", status))
    if not isinstance(record.get("notes"), str):
        issues.append(_issue("NOTES_TYPE", "$.notes", "must be a string"))

    extractor = record.get("extractor")
    expected_extractor = {
        "pass_number",
        "extractor_id",
        "extraction_id",
        "independence_attestation",
    }
    issues.extend(
        _check_exact_fields(
            extractor, expected_extractor, path="$.extractor", prefix="EXTRACTOR"
        )
    )
    if isinstance(extractor, dict):
        number = extractor.get("pass_number")
        if not isinstance(number, int) or isinstance(number, bool) or number not in {1, 2, 3}:
            issues.append(_issue("PASS_NUMBER", "$.extractor.pass_number", number))
        for key in ("extractor_id", "extraction_id"):
            if not isinstance(extractor.get(key), str) or not extractor.get(key):
                issues.append(_issue("EXTRACTOR_FIELD", f"$.extractor.{key}", "must be nonempty"))
        if require_independence and extractor.get("independence_attestation") is not True:
            issues.append(
                _issue(
                    "INDEPENDENCE_ATTESTATION",
                    "$.extractor.independence_attestation",
                    "official records require true",
                )
            )

    session = record.get("session")
    issues.extend(
        _check_exact_fields(
            session, {"session_slug", "sources"}, path="$.session", prefix="SESSION"
        )
    )
    sources: dict[str, str] = {}
    if isinstance(session, dict):
        if not isinstance(session.get("session_slug"), str) or not session.get("session_slug"):
            issues.append(_issue("SESSION_SLUG", "$.session.session_slug", "must be nonempty"))
        sources, source_issues = load_sources(record)
        issues.extend(source_issues)
        declared = {
            item.get("source_id")
            for item in session.get("sources", [])
            if isinstance(item, dict)
        }
        if declared != set(contract.response_files):
            issues.append(
                _issue(
                    "SOURCE_SET",
                    "$.session.sources",
                    f"expected {sorted(contract.response_files)}, found {sorted(str(item) for item in declared)}",
                )
            )

    raw_anchors = record.get("anchors")
    if not isinstance(raw_anchors, dict):
        issues.append(_issue("ANCHORS_TYPE", "$.anchors", "must be an object"))
        raw_anchors = {}
    max_chars = int(contract.evidence_policy.get("max_anchor_characters", 4000))
    for anchor_id, locator in raw_anchors.items():
        if isinstance(locator, dict) and isinstance(locator.get("text"), str):
            if len(locator["text"]) > max_chars:
                issues.append(
                    _issue(
                        "ANCHOR_MAX_LENGTH",
                        f"$.anchors.{anchor_id}.text",
                        f"exceeds {max_chars} decoded characters",
                    )
                )
    if bind_evidence and sources:
        anchors, anchor_errors = bind_anchor_table(raw_anchors, sources)
        issues.extend(_issue(error.code, error.path, error.message) for error in anchor_errors)
    else:
        anchors = {
            anchor_id: {"anchor_id": anchor_id, **locator}
            for anchor_id, locator in raw_anchors.items()
            if isinstance(locator, dict)
        }

    claims = record.get("claims")
    if not isinstance(claims, list):
        issues.append(_issue("CLAIMS_TYPE", "$.claims", "must be an array"))
        return issues
    local_ids: set[str] = set()
    claim_by_id: dict[str, dict[str, Any]] = {}
    used_anchors: set[str] = set()
    claim_mention_links: set[str] = set()

    for index, claim in enumerate(claims):
        path = f"$.claims[{index}]"
        wanted = CLAIM_FIELDS
        if (contract.record_model.get("source_specification")
                and isinstance(claim, dict) and "source_specification" in claim):
            wanted = wanted | {"source_specification"}
        issues.extend(_check_exact_fields(claim, wanted, path=path, prefix="CLAIM"))
        if not isinstance(claim, dict):
            continue
        # Register the local ID even when the claim has field-level issues:
        # mention_dispositions and primary reference PRESENT claims, and an
        # invalid claim must surface its own root defect once, not cascade
        # into MENTION_CLAIM_UNKNOWN / PRIMARY_ID_UNKNOWN noise (157 cascade
        # issue lines in the first live round came from this).
        local_id = claim.get("local_id")
        if isinstance(local_id, str) and local_id:
            if local_id in local_ids:
                issues.append(_issue("LOCAL_ID_DUPLICATE", f"{path}.local_id", local_id))
            else:
                local_ids.add(local_id)
                claim_by_id[local_id] = claim
        elif "local_id" in claim:
            issues.append(_issue("LOCAL_ID", f"{path}.local_id", "must be nonempty"))
        if CLAIM_FIELDS - set(claim):
            continue
        source_id = claim.get("source_id")
        if source_id not in contract.response_files:
            issues.append(_issue("CLAIM_SOURCE", f"{path}.source_id", source_id))
        kind = claim.get("kind")
        if kind not in contract.construction_kinds:
            issues.append(_issue("CLAIM_KIND", f"{path}.kind", kind))
            continue
        definition = contract.definition(kind)
        claim_status = claim.get("claim_status")
        role = claim.get("answer_role")
        target = claim.get("claimed_target")
        specificity = claim.get("specificity")
        if claim_status not in contract.claim_statuses:
            issues.append(_issue("CLAIM_STATUS", f"{path}.claim_status", claim_status))
        if role not in contract.answer_roles:
            issues.append(_issue("ANSWER_ROLE", f"{path}.answer_role", role))
        if target not in contract.claimed_targets:
            issues.append(_issue("CLAIMED_TARGET", f"{path}.claimed_target", target))
        if specificity not in contract.specificity_statuses:
            issues.append(_issue("SPECIFICITY", f"{path}.specificity", specificity))
        transcription = claim.get("transcription")
        if not isinstance(transcription, dict):
            issues.append(_issue("TRANSCRIPTION_TYPE", f"{path}.transcription", "must be an object"))
            transcription = {}
        if specificity in {"concrete", "partial"}:
            issues.extend(
                _payload_schema_issues(
                    kind,
                    transcription,
                    definition.transcription_schema,
                    f"{path}.transcription",
                    enforce_required=specificity == "concrete",
                    full_schema=True,
                )
            )
            if specificity == "partial" and not transcription:
                issues.append(
                    _issue(
                        "PARTIAL_TRANSCRIPTION_EMPTY",
                        f"{path}.transcription",
                        "partial requires at least one typed field",
                    )
                )
            for item in definition.completeness_issues(
                transcription, contract.signature, specificity=str(specificity),
                glyph_folds=contract.glyph_folds,
            ):
                issues.append(_issue(item["code"], f"{path}{item['path']}", item["message"]))
        elif transcription:
            issues.append(
                _issue(
                    "NONSPECIFIC_TRANSCRIPTION",
                    f"{path}.transcription",
                    "family_only and unparseable keep content in anchors, not payload",
                )
            )

        success_roles = set(contract.record_model.get("success_roles", []))
        if role in success_roles and claim_status != "claimed_valid":
            issues.append(_issue("SUCCESS_ROLE_STATUS", f"{path}.answer_role", f"{role} requires claimed_valid"))
        if role == "failed_contrast" and claim_status not in {"claimed_invalid", "hypothetical", "unclear"}:
            issues.append(_issue("FAILED_CONTRAST_STATUS", f"{path}.claim_status", claim_status))
        if claim_status in {"claimed_valid", "claimed_invalid"} and target == "none":
            issues.append(_issue("POLAR_CLAIM_TARGET", f"{path}.claimed_target", target))

        _, ref_issues = _anchor_refs(
            claim.get("evidence"),
            path=f"{path}.evidence",
            anchors=anchors,
            used=used_anchors,
            expected_source=source_id if isinstance(source_id, str) else None,
        )
        issues.extend(ref_issues)

        if (run_manifest and run_manifest.get("extraction_mode") == "single"
                and claim.get("specificity") in {"partial", "unparseable"}
                and "source_specification" not in claim):
            issues.append(_issue(
                "SOURCE_SPECIFICATION_REQUIRED", f"{path}.source_specification",
                "single extraction must distinguish missing definitions, source ambiguity and checker limits",
            ))
        if "source_specification" in claim and contract.record_model.get("source_specification"):
            spec = claim["source_specification"]
            spec_path = f"{path}.source_specification"
            issues.extend(_full_schema_issues(
                spec,
                specification_schema(contract.record_model, kind=claim.get("kind")),
                spec_path,
            ))
            complete_contract_issues = tuple(
                definition.completeness_issues(
                    transcription,
                    contract.signature,
                    specificity="concrete",
                    glyph_folds=contract.glyph_folds,
                )
            )
            for problem in specification_issues(
                claim,
                contract.record_model,
                complete_contract_issues=complete_contract_issues,
            ):
                issues.append(_issue("SOURCE_SPECIFICATION_CONFLICT", spec_path, problem))
            if isinstance(spec, dict):
                _, ref_issues = _anchor_refs(
                    spec.get("evidence"), path=f"{spec_path}.evidence", anchors=anchors,
                    used=used_anchors, expected_source=source_id if isinstance(source_id, str) else None,
                )
                issues.extend(ref_issues)

        rejection = claim.get("rejection_evidence")
        if claim_status == "claimed_invalid":
            _, ref_issues = _anchor_refs(
                rejection,
                path=f"{path}.rejection_evidence",
                anchors=anchors,
                used=used_anchors,
                expected_source=source_id if isinstance(source_id, str) else None,
            )
            issues.extend(ref_issues)
        else:
            if rejection:
                issues.append(
                    _issue(
                        "REJECTION_EVIDENCE_UNEXPECTED",
                        f"{path}.rejection_evidence",
                        "only claimed_invalid may carry rejection evidence",
                    )
                )
            elif not isinstance(rejection, list):
                issues.append(_issue("REJECTION_EVIDENCE_TYPE", f"{path}.rejection_evidence", "must be an array"))

        axis = claim.get("axis_evidence")
        wanted_axes = set(contract.record_model.get("axis_evidence_fields", []))
        issues.extend(
            _check_exact_fields(
                axis, wanted_axes, path=f"{path}.axis_evidence", prefix="AXIS_EVIDENCE"
            )
        )
        if isinstance(axis, dict):
            for field in wanted_axes:
                _, ref_issues = _anchor_refs(
                    axis.get(field),
                    path=f"{path}.axis_evidence.{field}",
                    anchors=anchors,
                    used=used_anchors,
                    expected_source=source_id if isinstance(source_id, str) else None,
                )
                issues.extend(ref_issues)

        field_evidence = claim.get("field_evidence")
        if not isinstance(field_evidence, dict):
            issues.append(_issue("FIELD_EVIDENCE_TYPE", f"{path}.field_evidence", "must be an object"))
            field_evidence = {}
        for pointer, refs in field_evidence.items():
            if not isinstance(pointer, str) or not pointer.startswith("/transcription/") or not _pointer_exists(claim, pointer):
                issues.append(_issue("FIELD_EVIDENCE_POINTER", f"{path}.field_evidence", pointer))
                continue
            _, ref_issues = _anchor_refs(
                refs,
                path=f"{path}.field_evidence[{pointer!r}]",
                anchors=anchors,
                used=used_anchors,
                expected_source=source_id if isinstance(source_id, str) else None,
            )
            issues.extend(ref_issues)
        required_pointers = (
            set(definition.required_evidence_pointers(transcription))
            if specificity in {"concrete", "partial"}
            else set()
        )
        for pointer in sorted(required_pointers - set(field_evidence)):
            issues.append(
                _issue(
                    "FIELD_EVIDENCE_REQUIRED",
                    f"{path}.field_evidence",
                    f"missing semantic-unit evidence for {pointer}",
                )
            )

        value_check = argument_evidence_check(claim, anchors)
        if value_check["status"] == "contradicted":
            issues.append(_issue(
                "FIELD_SOURCE_VALUE_MISMATCH", f"{path}.transcription.argument",
                f"typed {value_check['value']}, cited source states {value_check['source_values']}",
            ))

    primary = record.get("primary")
    issues.extend(
        _check_exact_fields(
            primary, {"status", "claim_ids", "evidence"}, path="$.primary", prefix="PRIMARY"
        )
    )
    if isinstance(primary, dict):
        primary_status = primary.get("status")
        ids = primary.get("claim_ids")
        if primary_status not in contract.primary_statuses:
            issues.append(_issue("PRIMARY_STATUS", "$.primary.status", primary_status))
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            issues.append(_issue("PRIMARY_IDS", "$.primary.claim_ids", "must be local-ID array"))
            ids = []
        unknown = set(ids) - local_ids
        if unknown:
            issues.append(_issue("PRIMARY_ID_UNKNOWN", "$.primary.claim_ids", sorted(unknown)))
        if primary_status == "single" and len(ids) != 1:
            issues.append(_issue("PRIMARY_SINGLE_CARDINALITY", "$.primary.claim_ids", len(ids)))
        if primary_status == "coequal" and len(ids) < 2:
            issues.append(_issue("PRIMARY_COEQUAL_CARDINALITY", "$.primary.claim_ids", len(ids)))
        if primary_status in {"none", "unclear"} and ids:
            issues.append(_issue("PRIMARY_EMPTY_IDS", "$.primary.claim_ids", primary_status))
        evidence = primary.get("evidence")
        require_primary_evidence = primary_status in {"single", "coequal"}
        _, ref_issues = _anchor_refs(
            evidence,
            path="$.primary.evidence",
            anchors=anchors,
            used=used_anchors,
            require_nonempty=require_primary_evidence,
        )
        issues.extend(ref_issues)
        if not require_primary_evidence and evidence:
            issues.append(_issue("PRIMARY_EVIDENCE_UNEXPECTED", "$.primary.evidence", primary_status))
        for local_id in ids:
            role = claim_by_id.get(local_id, {}).get("answer_role")
            expected = "primary" if primary_status == "single" else "co_primary"
            if role != expected:
                issues.append(_issue("PRIMARY_ROLE_MISMATCH", "$.primary.claim_ids", f"{local_id}: {role!r} != {expected!r}"))

    coverage = record.get("coverage")
    coverage_fields = {
        "sources_read",
        "completeness_status",
        "completeness_attestation",
        "mention_dispositions",
    }
    issues.extend(
        _check_exact_fields(
            coverage, coverage_fields, path="$.coverage", prefix="COVERAGE"
        )
    )
    if isinstance(coverage, dict):
        sources_read = coverage.get("sources_read")
        if not isinstance(sources_read, list) or any(not isinstance(item, str) for item in sources_read):
            issues.append(_issue("COVERAGE_SOURCES", "$.coverage.sources_read", "must be source-ID array"))
        elif set(sources_read) != set(contract.response_files) or len(sources_read) != len(set(sources_read)):
            issues.append(_issue("COVERAGE_SOURCE_SET", "$.coverage.sources_read", contract.response_files))
        if coverage.get("completeness_status") not in contract.record_model.get("coverage_statuses", []):
            issues.append(_issue("COVERAGE_STATUS", "$.coverage.completeness_status", coverage.get("completeness_status")))
        if official_mode and coverage.get("completeness_attestation") is not True:
            issues.append(_issue("COVERAGE_ATTESTATION", "$.coverage.completeness_attestation", "official record requires true"))
        dispositions = coverage.get("mention_dispositions")
        if not isinstance(dispositions, list):
            issues.append(_issue("MENTION_DISPOSITIONS_TYPE", "$.coverage.mention_dispositions", "must be an array"))
            dispositions = []
        seen_mentions: set[str] = set()
        for index, item in enumerate(dispositions):
            path = f"$.coverage.mention_dispositions[{index}]"
            issues.extend(
                _check_exact_fields(
                    item,
                    {"anchor_id", "disposition", "claim_ids", "reason"},
                    path=path,
                    prefix="MENTION",
                )
            )
            if not isinstance(item, dict):
                continue
            anchor_id = item.get("anchor_id")
            if not isinstance(anchor_id, str) or anchor_id not in anchors:
                issues.append(_issue("MENTION_ANCHOR", f"{path}.anchor_id", anchor_id))
            else:
                used_anchors.add(anchor_id)
                if anchor_id in seen_mentions:
                    issues.append(_issue("MENTION_DUPLICATE", f"{path}.anchor_id", anchor_id))
                seen_mentions.add(anchor_id)
            disposition = item.get("disposition")
            ids = item.get("claim_ids")
            reason = item.get("reason")
            if disposition not in contract.record_model.get("mention_dispositions", []):
                issues.append(_issue("MENTION_DISPOSITION", f"{path}.disposition", disposition))
            if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
                issues.append(_issue("MENTION_CLAIM_IDS", f"{path}.claim_ids", "must be local-ID array"))
                ids = []
            if set(ids) - local_ids:
                issues.append(_issue("MENTION_CLAIM_UNKNOWN", f"{path}.claim_ids", sorted(set(ids)-local_ids)))
            if disposition == "claim":
                if not ids:
                    issues.append(_issue("MENTION_CLAIM_REQUIRED", f"{path}.claim_ids", "linked claim required"))
                claim_mention_links.update(ids)
            elif ids:
                issues.append(_issue("MENTION_NONCLAIM_IDS", f"{path}.claim_ids", disposition))
            if disposition in {"nonconstruction", "unresolved"} and (not isinstance(reason, str) or not reason.strip()):
                issues.append(_issue("MENTION_REASON_REQUIRED", f"{path}.reason", disposition))
        if coverage.get("completeness_status") == "uncertain" and not any(
            isinstance(item, dict) and item.get("disposition") == "unresolved"
            for item in dispositions
        ):
            issues.append(
                _issue(
                    "COVERAGE_UNCERTAIN_UNEXPLAINED",
                    "$.coverage.completeness_status",
                    "uncertain coverage requires an anchored unresolved mention disposition",
                )
            )
        for local_id in sorted(local_ids - claim_mention_links):
            issues.append(
                _issue(
                    "CLAIM_MENTION_DISPOSITION_REQUIRED",
                    "$.coverage.mention_dispositions",
                    f"claim {local_id!r} has no linked construction-mention disposition",
                )
            )

    if run_manifest and run_manifest.get("extraction_mode") == "single" and sources:
        issues.extend(
            _issue(item["code"], item["path"], item["message"])
            for item in paragraph_coverage_issues(record, sources, max_chars)
        )

    oracle_policy = contract.coverage_oracle
    should_enforce_oracle = (
        status == "complete"
        and isinstance(oracle_policy, dict)
        and oracle_policy.get("enabled") is True
        and (
            oracle_policy.get("enforcement") == "all_complete_records"
            or (
                oracle_policy.get("enforcement") == "official_complete_records"
                and official_mode
            )
        )
    )
    if should_enforce_oracle:
        try:
            oracle_receipt = coverage_oracle_receipt(
                sources=sources,
                bound_anchors=anchors,
                mention_dispositions=(
                    (record.get("coverage") or {}).get("mention_dispositions")
                    or []
                ),
                policy=oracle_policy,
            )
        except CoverageOracleError as error:
            issues.append(
                _issue(
                    "COVERAGE_ORACLE_POLICY",
                    "$.coverage",
                    error,
                )
            )
        else:
            if oracle_receipt is not None:
                for region in oracle_receipt["unaccounted_regions"]:
                    excerpt = str(region.get("excerpt") or "").replace("\n", " ")
                    if len(excerpt) > 180:
                        excerpt = excerpt[:177] + "..."
                    issues.append(
                        _issue(
                            "COVERAGE_ORACLE_REGION_UNACCOUNTED",
                            "$.coverage.mention_dispositions",
                            (
                                f"{region['source_id']}[{region['start']}:{region['end']}] "
                                f"labels={region['labels']} excerpt={excerpt!r}"
                            ),
                        )
                    )

    if status != "complete":
        if claims:
            issues.append(_issue("BAD_RECORD_CLAIMS", "$.claims", "non-complete record must have []"))
        if raw_anchors:
            issues.append(_issue("BAD_RECORD_ANCHORS", "$.anchors", "non-complete record must have {}"))

    for anchor_id in sorted(set(anchors) - used_anchors):
        issues.append(
            _issue(
                "ANCHOR_UNUSED",
                f"$.anchors.{anchor_id}",
                "every anchor must support a claim, primary decision, or mention disposition",
            )
        )
    return issues
