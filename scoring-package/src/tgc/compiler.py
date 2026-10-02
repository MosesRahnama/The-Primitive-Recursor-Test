from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from .canonical import canonicalize_claim
from .common import content_id, read_json, sha256_file, write_json_atomic
from .config import InstanceContract
from .evidence import bind_locators
from .validation import ValidationIssue, load_sources, validate_record


def compile_record(
    record: dict[str, Any],
    contract: InstanceContract,
    *,
    require_independence: bool = True,
    run_manifest: dict[str, Any] | None = None,
    official_mode: bool = True,
    raw_record_sha256: str | None = None,
    extra_pass_entry: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
    if contract.is_v3:
        from .compiler_v3 import compile_record_v3

        return compile_record_v3(
            record,
            contract,
            require_independence=require_independence,
            run_manifest=run_manifest,
            official_mode=official_mode,
            raw_record_sha256=raw_record_sha256,
            extra_pass_entry=extra_pass_entry,
        )
    issues = validate_record(
        record,
        contract,
        require_independence=require_independence,
        bind_evidence=True,
    )
    if issues:
        return None, issues
    sources, source_issues = load_sources(record)
    if source_issues:
        return None, source_issues

    occurrences: Counter[str] = Counter()
    compiled_claims: list[dict[str, Any]] = []
    local_to_compiled: dict[str, dict[str, Any]] = {}
    for index, claim in enumerate(record["claims"]):
        canonical = canonicalize_claim(claim, contract)
        occurrences[canonical.identity] += 1
        occurrence = occurrences[canonical.identity]
        claim_id = content_id(
            "claim",
            {
                "identity": canonical.identity,
                "occurrence": occurrence,
            },
        )
        evidence, evidence_errors = bind_locators(
            claim["evidence"],
            sources,
            path=f"$.claims[{index}].evidence",
        )
        rejection, rejection_errors = bind_locators(
            claim["rejection_evidence"],
            sources,
            path=f"$.claims[{index}].rejection_evidence",
        )
        field_evidence: dict[str, list[dict[str, Any]]] = {}
        binding_errors = evidence_errors + rejection_errors
        for pointer, locators in sorted(claim["field_evidence"].items()):
            bound, errors = bind_locators(
                locators,
                sources,
                path=f"$.claims[{index}].field_evidence[{pointer!r}]",
            )
            field_evidence[pointer] = bound
            binding_errors.extend(errors)
        if binding_errors:
            return None, [
                ValidationIssue(error.code, error.path, error.message)
                for error in binding_errors
            ]
        compiled = {
            "claim_id": claim_id,
            "local_id": claim["local_id"],
            "source_id": claim["source_id"],
            "occurrence": occurrence,
            "canonical_identity": canonical.identity,
            "checker_equivalence_identity": canonical.checker_identity,
            "core": canonical.core,
            "checker_core": canonical.checker_core,
            "kind": claim["kind"],
            "specificity": claim["specificity"],
            "claimed_target": claim["claimed_target"],
            "claim_status": claim["claim_status"],
            "answer_role": claim["answer_role"],
            "transcription": claim["transcription"],
            "checker_object": {
                "idx": index + 1,
                "kind": claim["kind"],
                "stance": {
                    "claimed_valid": "asserted",
                    "claimed_invalid": "rejected",
                    "hypothetical": "mentioned",
                    "mentioned": "mentioned",
                    "unclear": "unclear",
                }[claim["claim_status"]],
                "payload": (
                    canonical.checker_payload
                    if claim["specificity"] in {"concrete", "partial"}
                    else {claim["specificity"]: True}
                ),
                "quote": evidence[0]["text"],
                **(
                    {"rejection_quote": rejection[0]["text"]}
                    if rejection
                    else {}
                ),
            },
            "evidence": evidence,
            "field_evidence": field_evidence,
            "rejection_evidence": rejection,
            "canonicalization": {
                "supported": canonical.supported,
                "issues": canonical.issues,
                "receipts": canonical.receipts,
            },
        }
        compiled_claims.append(compiled)
        local_to_compiled[claim["local_id"]] = compiled

    primary_ids = [
        local_to_compiled[local_id]["claim_id"]
        for local_id in record["primary"]["claim_ids"]
    ]
    primary_identities = [
        local_to_compiled[local_id]["canonical_identity"]
        for local_id in record["primary"]["claim_ids"]
    ]
    compiled_record = {
        "compiled_schema_version": "tgc-compiled-record/2.0.0",
        "contract": record["contract"],
        "session": record["session"],
        "extractor": record["extractor"],
        "record_status": record["record_status"],
        "claims": compiled_claims,
        "primary": {
            "status": record["primary"]["status"],
            "claim_ids": primary_ids,
            "canonical_identities": primary_identities,
        },
        "notes": record["notes"],
    }
    compiled_record["compiled_record_id"] = content_id(
        "record",
        {
            "contract": compiled_record["contract"],
            "session": compiled_record["session"],
            "extractor": compiled_record["extractor"],
            "claims": [
                {
                    "identity": claim["canonical_identity"],
                    "occurrence": claim["occurrence"],
                    "claim_status": claim["claim_status"],
                    "answer_role": claim["answer_role"],
                }
                for claim in compiled_claims
            ],
            "primary": compiled_record["primary"],
        },
    )
    return compiled_record, []


def compile_record_file(
    input_path: Path,
    output_path: Path,
    contract: InstanceContract,
    *,
    require_independence: bool = True,
    run_manifest: dict[str, Any] | None = None,
    official_mode: bool = True,
) -> list[ValidationIssue]:
    try:
        record = read_json(input_path)
    except Exception as error:
        return [ValidationIssue("RECORD_JSON", "$", str(error))]
    compiled, issues = compile_record(
        record,
        contract,
        require_independence=require_independence,
        run_manifest=run_manifest,
        official_mode=official_mode,
        raw_record_sha256=sha256_file(input_path),
    )
    if compiled is not None:
        write_json_atomic(output_path, compiled)
    return issues
