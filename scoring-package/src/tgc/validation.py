from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry
from referencing.exceptions import NoSuchResource

from .common import read_json, read_text, sha256_file
from .config import InstanceContract
from .evidence import bind_locators


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _is_placeholder(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_is_placeholder(child) for child in value.values())
    if isinstance(value, list):
        return any(_is_placeholder(child) for child in value)
    return isinstance(value, str) and ("<FILL:" in value or "<OPTIONAL:" in value)


def _primitive_leaves(value: Any, path: str = "") -> list[str]:
    leaves: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            leaves.extend(_primitive_leaves(child, f"{path}/{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            leaves.extend(_primitive_leaves(child, f"{path}/{index}"))
    else:
        leaves.append(path or "/")
    return leaves


def _pointer_exists(value: Any, pointer: str) -> bool:
    if not pointer.startswith("/"):
        return False
    current = value
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return False
    return True


def _schema_subset_issues(value: Any, schema: dict[str, Any], path: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    expected_type = schema.get("type")
    type_ok = {
        "string": lambda item: isinstance(item, str),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "boolean": lambda item: isinstance(item, bool),
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
    }.get(expected_type, lambda item: True)(value)
    if not type_ok:
        return [ValidationIssue("PAYLOAD_TYPE", path, f"expected {expected_type}")]
    if "enum" in schema and value not in schema["enum"]:
        issues.append(ValidationIssue("PAYLOAD_ENUM", path, f"{value!r} is not in {schema['enum']}"))
    if isinstance(value, str):
        if len(value) < int(schema.get("minLength", 0)):
            issues.append(ValidationIssue("PAYLOAD_MIN_LENGTH", path, "string is too short"))
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            issues.append(ValidationIssue("PAYLOAD_MAX_LENGTH", path, "string is too long"))
    if isinstance(value, list):
        if len(value) < int(schema.get("minItems", 0)):
            issues.append(ValidationIssue("PAYLOAD_MIN_ITEMS", path, "array has too few items"))
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            issues.append(ValidationIssue("PAYLOAD_MAX_ITEMS", path, "array has too many items"))
        if "items" in schema:
            for index, item in enumerate(value):
                issues.extend(_schema_subset_issues(item, schema["items"], f"{path}/{index}"))
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                issues.append(ValidationIssue("PAYLOAD_FIELD_REQUIRED", path, f"requires field {key!r}"))
        additional = schema.get("additionalProperties", True)
        for key, child in value.items():
            if key in properties:
                issues.extend(_schema_subset_issues(child, properties[key], f"{path}/{key}"))
            elif additional is False:
                issues.append(ValidationIssue("PAYLOAD_FIELD_UNKNOWN", f"{path}/{key}", f"unexpected field {key!r}"))
            elif isinstance(additional, dict):
                issues.extend(_schema_subset_issues(child, additional, f"{path}/{key}"))
        if len(value) < int(schema.get("minProperties", 0)):
            issues.append(ValidationIssue("PAYLOAD_MIN_PROPERTIES", path, "object has too few properties"))
        if "maxProperties" in schema and len(value) > int(schema["maxProperties"]):
            issues.append(ValidationIssue("PAYLOAD_MAX_PROPERTIES", path, "object has too many properties"))
    return issues


def _payload_schema_issues(
    kind: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
    path: str,
    *,
    enforce_required: bool,
    full_schema: bool = False,
) -> list[ValidationIssue]:
    effective = dict(schema)
    if not enforce_required:
        effective["required"] = []
    if not full_schema:
        # Frozen v1/v2 replay retains its historical validation semantics.
        return _schema_subset_issues(payload, effective, path)
    return _full_schema_issues(payload, effective, path)


def _no_remote_schema(uri: str) -> Any:
    raise NoSuchResource(ref=uri)


def _full_schema_issues(
    value: Any, schema: dict[str, Any], path: str
) -> list[ValidationIssue]:
    """Validate the complete local schema; never fetch a remote reference."""
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(
            schema, registry=Registry(retrieve=_no_remote_schema)
        )
        errors = sorted(
            validator.iter_errors(value),
            key=lambda error: (str(list(error.absolute_path)), error.message),
        )
    except Exception as error:
        return [ValidationIssue("PAYLOAD_SCHEMA_INVALID", path, str(error))]
    codes = {
        "type": "PAYLOAD_TYPE", "enum": "PAYLOAD_ENUM",
        "required": "PAYLOAD_FIELD_REQUIRED",
        "additionalProperties": "PAYLOAD_FIELD_UNKNOWN",
    }
    return [
        ValidationIssue(
            codes.get(str(error.validator), "PAYLOAD_SCHEMA"),
            path + "".join(f"/{part}" for part in error.absolute_path),
            error.message,
        )
        for error in errors
    ]


def load_sources(record: dict[str, Any]) -> tuple[dict[str, str], list[ValidationIssue]]:
    issues: list[ValidationIssue] = []
    sources: dict[str, str] = {}
    for index, source in enumerate(record.get("session", {}).get("sources", [])):
        path = f"$.session.sources[{index}]"
        source_id = source.get("source_id")
        file_value = source.get("path")
        if not isinstance(source_id, str) or not source_id:
            issues.append(ValidationIssue("SOURCE_ID", f"{path}.source_id", "source_id must be nonempty"))
            continue
        if source_id in sources:
            issues.append(ValidationIssue("SOURCE_ID_DUPLICATE", f"{path}.source_id", source_id))
            continue
        if not isinstance(file_value, str) or not file_value:
            issues.append(ValidationIssue("SOURCE_PATH", f"{path}.path", "source path must be nonempty"))
            continue
        file_path = Path(file_value)
        if not file_path.exists():
            issues.append(ValidationIssue("SOURCE_MISSING", f"{path}.path", str(file_path)))
            continue
        observed_hash = sha256_file(file_path)
        if observed_hash != source.get("sha256"):
            issues.append(ValidationIssue("SOURCE_HASH_MISMATCH", f"{path}.sha256", f"declared {source.get('sha256')}, observed {observed_hash}"))
            continue
        text = read_text(file_path)
        if source.get("characters") != len(text):
            issues.append(ValidationIssue("SOURCE_LENGTH_MISMATCH", f"{path}.characters", f"declared {source.get('characters')}, observed {len(text)}"))
            continue
        sources[source_id] = text
    return sources, issues


def validate_record(
    record: dict[str, Any],
    contract: InstanceContract,
    *,
    require_independence: bool = True,
    bind_evidence: bool = True,
    run_manifest: dict[str, Any] | None = None,
    official_mode: bool = True,
    extra_pass_entry: dict[str, Any] | None = None,
) -> list[ValidationIssue]:
    if contract.is_v3:
        # Lazy import avoids a module cycle while keeping one public API for
        # historical v2 and forward v3 records.
        from .validation_v3 import validate_record_v3

        return validate_record_v3(
            record,
            contract,
            require_independence=require_independence,
            bind_evidence=bind_evidence,
            run_manifest=run_manifest,
            official_mode=official_mode,
            extra_pass_entry=extra_pass_entry,
        )
    issues: list[ValidationIssue] = []
    if not isinstance(record, dict):
        return [ValidationIssue("RECORD_TYPE", "$", "record must be an object")]
    if _is_placeholder(record):
        issues.append(ValidationIssue("UNFILLED_PLACEHOLDER", "$", "record contains a <FILL: or <OPTIONAL: marker"))

    expected_top = {
        "schema_version",
        "contract",
        "session",
        "extractor",
        "record_status",
        "claims",
        "primary",
        "notes",
    }
    extra = set(record) - expected_top
    missing = expected_top - set(record)
    for key in sorted(extra):
        issues.append(ValidationIssue("RECORD_FIELD_UNKNOWN", f"$.{key}", "unexpected top-level field"))
    for key in sorted(missing):
        issues.append(ValidationIssue("RECORD_FIELD_REQUIRED", "$", f"missing {key!r}"))
    if missing:
        return issues

    if record.get("schema_version") != contract.schema_version:
        issues.append(ValidationIssue("SCHEMA_VERSION", "$.schema_version", f"expected {contract.schema_version!r}"))
    binding = record.get("contract")
    if not isinstance(binding, dict) or binding != contract.binding():
        issues.append(ValidationIssue("CONTRACT_BINDING", "$.contract", "record is not bound to the loaded contract hashes"))

    status = record.get("record_status")
    if status not in contract.record_statuses:
        issues.append(ValidationIssue("RECORD_STATUS", "$.record_status", str(status)))

    extractor = record.get("extractor")
    if not isinstance(extractor, dict):
        issues.append(ValidationIssue("EXTRACTOR_TYPE", "$.extractor", "extractor must be an object"))
    else:
        pass_number = extractor.get("pass_number")
        if not isinstance(pass_number, int) or isinstance(pass_number, bool) or pass_number < 1:
            issues.append(ValidationIssue("PASS_NUMBER", "$.extractor.pass_number", "must be a positive integer"))
        for key in ("extractor_id", "run_id"):
            if not isinstance(extractor.get(key), str) or not extractor.get(key):
                issues.append(ValidationIssue("EXTRACTOR_FIELD", f"$.extractor.{key}", "must be nonempty"))
        if require_independence and extractor.get("independence_attestation") is not True:
            issues.append(ValidationIssue("INDEPENDENCE_ATTESTATION", "$.extractor.independence_attestation", "official records require true"))

    session = record.get("session")
    if not isinstance(session, dict):
        issues.append(ValidationIssue("SESSION_TYPE", "$.session", "session must be an object"))
        sources: dict[str, str] = {}
    else:
        if not isinstance(session.get("session_slug"), str) or not session.get("session_slug"):
            issues.append(ValidationIssue("SESSION_SLUG", "$.session.session_slug", "must be nonempty"))
        sources, source_issues = load_sources(record)
        issues.extend(source_issues)
        expected_sources = set(contract.response_files)
        declared_sources = {item.get("source_id") for item in session.get("sources", []) if isinstance(item, dict)}
        if declared_sources != expected_sources:
            issues.append(ValidationIssue("SOURCE_SET", "$.session.sources", f"expected {sorted(expected_sources)}, found {sorted(str(x) for x in declared_sources)}"))

    claims = record.get("claims")
    if not isinstance(claims, list):
        issues.append(ValidationIssue("CLAIMS_TYPE", "$.claims", "claims must be an array"))
        return issues
    local_ids: set[str] = set()
    claim_by_id: dict[str, dict[str, Any]] = {}
    for index, claim in enumerate(claims):
        path = f"$.claims[{index}]"
        if not isinstance(claim, dict):
            issues.append(ValidationIssue("CLAIM_TYPE", path, "claim must be an object"))
            continue
        expected_claim = {
            "local_id",
            "source_id",
            "kind",
            "claim_status",
            "answer_role",
            "claimed_target",
            "specificity",
            "transcription",
            "evidence",
            "field_evidence",
            "rejection_evidence",
        }
        for key in sorted(set(claim) - expected_claim):
            issues.append(ValidationIssue("CLAIM_FIELD_UNKNOWN", f"{path}.{key}", "unexpected claim field"))
        for key in sorted(expected_claim - set(claim)):
            issues.append(ValidationIssue("CLAIM_FIELD_REQUIRED", path, f"missing {key!r}"))
        if expected_claim - set(claim):
            continue
        local_id = claim.get("local_id")
        if not isinstance(local_id, str) or not local_id:
            issues.append(ValidationIssue("LOCAL_ID", f"{path}.local_id", "must be nonempty"))
        elif local_id in local_ids:
            issues.append(ValidationIssue("LOCAL_ID_DUPLICATE", f"{path}.local_id", local_id))
        else:
            local_ids.add(local_id)
            claim_by_id[local_id] = claim
        if claim.get("source_id") not in contract.response_files:
            issues.append(ValidationIssue("CLAIM_SOURCE", f"{path}.source_id", str(claim.get("source_id"))))
        kind = claim.get("kind")
        if kind not in contract.construction_kinds:
            issues.append(ValidationIssue("CLAIM_KIND", f"{path}.kind", str(kind)))
        claim_status = claim.get("claim_status")
        if claim_status not in contract.claim_statuses:
            issues.append(ValidationIssue("CLAIM_STATUS", f"{path}.claim_status", str(claim_status)))
        role = claim.get("answer_role")
        if role not in contract.answer_roles:
            issues.append(ValidationIssue("ANSWER_ROLE", f"{path}.answer_role", str(role)))
        target = claim.get("claimed_target")
        if target not in contract.claimed_targets:
            issues.append(ValidationIssue("CLAIMED_TARGET", f"{path}.claimed_target", str(target)))
        specificity = claim.get("specificity")
        if specificity not in contract.specificity_statuses:
            issues.append(ValidationIssue("SPECIFICITY", f"{path}.specificity", str(specificity)))
        transcription = claim.get("transcription")
        if not isinstance(transcription, dict):
            issues.append(ValidationIssue("TRANSCRIPTION_TYPE", f"{path}.transcription", "must be an object"))
            transcription = {}
        if specificity in {"concrete", "partial"}:
            if kind in contract.payload_schemas:
                issues.extend(
                    _payload_schema_issues(
                        kind,
                        transcription,
                        contract.payload_schemas[kind],
                        f"{path}.transcription",
                        enforce_required=specificity == "concrete",
                    )
                )
            if specificity == "partial" and not transcription:
                issues.append(ValidationIssue("PARTIAL_TRANSCRIPTION_EMPTY", f"{path}.transcription", "partial requires at least one stated typed field"))
        elif transcription:
            issues.append(ValidationIssue("NONSPECIFIC_TRANSCRIPTION", f"{path}.transcription", "family_only and unparseable claims keep their exact source in evidence, not invented payload fields"))

        success_roles = {"primary", "co_primary", "supporting", "alternative_sufficient"}
        if role in success_roles and claim_status != "claimed_valid":
            issues.append(ValidationIssue("SUCCESS_ROLE_STATUS", f"{path}.answer_role", f"{role} requires claimed_valid"))
        if role == "failed_contrast" and claim_status not in {"claimed_invalid", "hypothetical", "unclear"}:
            issues.append(ValidationIssue("FAILED_CONTRAST_STATUS", f"{path}.claim_status", "failed_contrast requires claimed_invalid, hypothetical, or unclear"))
        if claim_status in {"claimed_valid", "claimed_invalid"} and target == "none":
            issues.append(ValidationIssue("POLAR_CLAIM_TARGET", f"{path}.claimed_target", "a positive or negative claim requires a target"))

        evidence = claim.get("evidence")
        rejection = claim.get("rejection_evidence")
        if not isinstance(evidence, list) or not evidence:
            issues.append(ValidationIssue("CLAIM_EVIDENCE", f"{path}.evidence", "every claim requires at least one exact evidence locator"))
        if not isinstance(rejection, list):
            issues.append(ValidationIssue("REJECTION_EVIDENCE_TYPE", f"{path}.rejection_evidence", "must be an array"))
            rejection = []
        if claim_status == "claimed_invalid" and not rejection:
            issues.append(ValidationIssue("REJECTION_EVIDENCE_REQUIRED", f"{path}.rejection_evidence", "claimed_invalid requires rejection evidence"))
        if claim_status != "claimed_invalid" and rejection:
            issues.append(ValidationIssue("REJECTION_EVIDENCE_UNEXPECTED", f"{path}.rejection_evidence", "only claimed_invalid may carry rejection evidence"))

        field_evidence = claim.get("field_evidence")
        if not isinstance(field_evidence, dict):
            issues.append(ValidationIssue("FIELD_EVIDENCE_TYPE", f"{path}.field_evidence", "must be an object"))
            field_evidence = {}
        for pointer, locators in field_evidence.items():
            if not pointer.startswith("/transcription/") or not _pointer_exists(claim, pointer):
                issues.append(ValidationIssue("FIELD_EVIDENCE_POINTER", f"{path}.field_evidence", f"{pointer!r} does not identify a transcription field"))
            if not isinstance(locators, list) or not locators:
                issues.append(ValidationIssue("FIELD_EVIDENCE_EMPTY", f"{path}.field_evidence.{pointer}", "must contain at least one locator"))
        if specificity in {"concrete", "partial"}:
            required_pointers = set(_primitive_leaves(transcription, "/transcription"))
            missing_pointers = required_pointers - set(field_evidence)
            for pointer in sorted(missing_pointers):
                issues.append(ValidationIssue("FIELD_EVIDENCE_REQUIRED", f"{path}.field_evidence", f"missing source evidence for {pointer}"))

        if bind_evidence and sources:
            for field_name, locators in (("evidence", evidence), ("rejection_evidence", rejection)):
                if isinstance(locators, list):
                    _, binding_errors = bind_locators(locators, sources, path=f"{path}.{field_name}")
                    issues.extend(ValidationIssue(err.code, err.path, err.message) for err in binding_errors)
            for pointer, locators in field_evidence.items():
                if isinstance(locators, list):
                    _, binding_errors = bind_locators(locators, sources, path=f"{path}.field_evidence[{pointer!r}]")
                    issues.extend(ValidationIssue(err.code, err.path, err.message) for err in binding_errors)

    primary = record.get("primary")
    if not isinstance(primary, dict):
        issues.append(ValidationIssue("PRIMARY_TYPE", "$.primary", "primary must be an object"))
    else:
        primary_status = primary.get("status")
        ids = primary.get("claim_ids")
        if primary_status not in contract.primary_statuses:
            issues.append(ValidationIssue("PRIMARY_STATUS", "$.primary.status", str(primary_status)))
        if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
            issues.append(ValidationIssue("PRIMARY_IDS", "$.primary.claim_ids", "must be an array of local IDs"))
            ids = []
        unknown = set(ids) - local_ids
        if unknown:
            issues.append(ValidationIssue("PRIMARY_ID_UNKNOWN", "$.primary.claim_ids", f"unknown IDs: {sorted(unknown)}"))
        if primary_status == "none" and ids:
            issues.append(ValidationIssue("PRIMARY_NONE_IDS", "$.primary.claim_ids", "none requires []"))
        if primary_status == "single" and len(ids) != 1:
            issues.append(ValidationIssue("PRIMARY_SINGLE_CARDINALITY", "$.primary.claim_ids", "single requires exactly one ID"))
        if primary_status == "coequal" and len(ids) < 2:
            issues.append(ValidationIssue("PRIMARY_COEQUAL_CARDINALITY", "$.primary.claim_ids", "coequal requires at least two IDs"))
        if primary_status == "unclear" and ids:
            issues.append(ValidationIssue("PRIMARY_UNCLEAR_IDS", "$.primary.claim_ids", "unclear requires []"))
        for local_id in ids:
            role = claim_by_id.get(local_id, {}).get("answer_role")
            expected_role = "primary" if primary_status == "single" else "co_primary"
            if role != expected_role:
                issues.append(ValidationIssue("PRIMARY_ROLE_MISMATCH", "$.primary.claim_ids", f"{local_id} has role {role!r}; expected {expected_role!r}"))
    return issues


def validate_record_file(
    path: Path,
    contract: InstanceContract,
    *,
    require_independence: bool = True,
    run_manifest: dict[str, Any] | None = None,
    official_mode: bool = True,
    extra_pass_entry: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[ValidationIssue]]:
    try:
        record = read_json(path)
    except Exception as error:
        return None, [ValidationIssue("RECORD_JSON", "$", str(error))]
    issues = validate_record(
        record,
        contract,
        require_independence=require_independence,
        run_manifest=run_manifest,
        official_mode=official_mode,
        extra_pass_entry=extra_pass_entry,
    )
    # Designated-file discipline (live-round finding 2026-07-27): a record
    # file's NAME is part of the contract — exactly <session_slug>.json.
    # An agent drafting under another name (or renaming) is caught at every
    # validation layer, not only by the compile-time file-set comparison.
    if isinstance(record, dict):
        session = record.get("session")
        slug = session.get("session_slug") if isinstance(session, dict) else None
        if isinstance(slug, str) and slug and path.stem != slug:
            issues = list(issues) + [
                ValidationIssue(
                    "RECORD_FILENAME",
                    "$",
                    f"file is named {path.name!r} but binds session "
                    f"{slug!r}; required name is {slug}.json",
                )
            ]
    return record, issues
