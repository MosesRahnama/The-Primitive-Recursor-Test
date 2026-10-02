from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class Decision(str, Enum):
    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    ABSTAIN = "ABSTAIN"
    BLOCK = "BLOCK"


class Severity(str, Enum):
    ADVISORY = "advisory"
    SOFT = "soft"
    HARD = "hard"


class ClaimStatus(str, Enum):
    OPEN = "open"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    WITHDRAWN = "withdrawn"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _plain(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _plain(dataclasses.asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        plain_items = [_plain(item) for item in value]
        return sorted(plain_items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def stable_json(value: Any) -> str:
    return json.dumps(
        _plain(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def digest_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def strict_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a JSON boolean")
    return value


@dataclass(frozen=True)
class Claim:
    claim_id: str
    proposition: str
    kind: str = "factual"
    polarity: bool = True
    risk: str = "high"
    requires_evidence: bool = True
    dependencies: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Claim":
        if not isinstance(value, Mapping):
            raise ValueError("claim must be an object")
        allowed = {
            "claim_id",
            "proposition",
            "kind",
            "polarity",
            "risk",
            "requires_evidence",
            "dependencies",
            "payload",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"unknown claim fields {unknown}")
        claim_id = value.get("claim_id")
        proposition = value.get("proposition")
        kind = value.get("kind", "factual")
        risk = value.get("risk", "high")
        dependencies = value.get("dependencies", [])
        payload = value.get("payload", {})
        if not isinstance(claim_id, str) or not claim_id:
            raise ValueError("claim.claim_id must be a nonempty string")
        if not isinstance(proposition, str) or not proposition.strip():
            raise ValueError("claim.proposition must be a nonempty string")
        if not isinstance(kind, str) or not kind:
            raise ValueError("claim.kind must be a nonempty string")
        if not isinstance(risk, str) or not risk:
            raise ValueError("claim.risk must be a nonempty string")
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item for item in dependencies
        ):
            raise ValueError("claim.dependencies must be an array of nonempty strings")
        if len(dependencies) != len(set(dependencies)):
            raise ValueError("claim.dependencies cannot contain duplicates")
        if not isinstance(payload, Mapping):
            raise ValueError("claim.payload must be an object")
        return cls(
            claim_id=claim_id,
            proposition=proposition,
            kind=kind,
            polarity=strict_bool(value.get("polarity", True), "claim.polarity"),
            risk=risk,
            requires_evidence=strict_bool(value.get("requires_evidence", True), "claim.requires_evidence"),
            dependencies=tuple(dependencies),
            payload=dict(payload),
        )

    @property
    def digest(self) -> str:
        return digest_json(
            {
                "claim_id": self.claim_id,
                "proposition": self.proposition,
                "kind": self.kind,
                "polarity": self.polarity,
                "risk": self.risk,
                "requires_evidence": self.requires_evidence,
                "dependencies": sorted(self.dependencies),
                "payload": self.payload,
            }
        )


@dataclass(frozen=True)
class EvidenceReceipt:
    receipt_id: str
    claim_digest: str
    context_digest: str
    tool: str
    tool_version: str
    issued_at: str
    run_nonce: str
    verdict: str
    result_digest: str
    issuer: str
    independently_verified: bool = False
    capability: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    integrity_digest: str = ""

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceReceipt":
        if not isinstance(value, Mapping):
            raise ValueError("receipt must be an object")
        allowed = {
            "receipt_id",
            "claim_digest",
            "context_digest",
            "tool",
            "tool_version",
            "issued_at",
            "run_nonce",
            "verdict",
            "result_digest",
            "issuer",
            "independently_verified",
            "capability",
            "metadata",
            "integrity_digest",
        }
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"unknown receipt fields {unknown}")
        string_fields = {
            name: value.get(name, "")
            for name in (
                "receipt_id",
                "claim_digest",
                "context_digest",
                "tool",
                "tool_version",
                "issued_at",
                "run_nonce",
                "verdict",
                "result_digest",
                "issuer",
                "capability",
                "integrity_digest",
            )
        }
        if not all(isinstance(item, str) for item in string_fields.values()):
            raise ValueError("receipt string fields must be strings")
        metadata = value.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("receipt.metadata must be an object")
        return cls(
            receipt_id=string_fields["receipt_id"],
            claim_digest=string_fields["claim_digest"],
            context_digest=string_fields["context_digest"],
            tool=string_fields["tool"],
            tool_version=string_fields["tool_version"],
            issued_at=string_fields["issued_at"],
            run_nonce=string_fields["run_nonce"],
            verdict=string_fields["verdict"] or "unknown",
            result_digest=string_fields["result_digest"],
            issuer=string_fields["issuer"],
            independently_verified=strict_bool(
                value.get("independently_verified", False), "receipt.independently_verified"
            ),
            capability=string_fields["capability"],
            metadata=dict(metadata),
            integrity_digest=string_fields["integrity_digest"],
        )

    def body(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "claim_digest": self.claim_digest,
            "context_digest": self.context_digest,
            "tool": self.tool,
            "tool_version": self.tool_version,
            "issued_at": self.issued_at,
            "run_nonce": self.run_nonce,
            "verdict": self.verdict,
            "result_digest": self.result_digest,
            "issuer": self.issuer,
            "independently_verified": self.independently_verified,
            "capability": self.capability,
            "metadata": self.metadata,
        }

    @property
    def computed_integrity_digest(self) -> str:
        return digest_json(self.body())

    def sealed(self) -> "EvidenceReceipt":
        return dataclasses.replace(self, integrity_digest=self.computed_integrity_digest)


@dataclass(frozen=True)
class TraceEvent:
    event_id: str
    event_type: str
    timestamp: str
    claim_id: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TraceEvent":
        if not isinstance(value, Mapping):
            raise ValueError("trace event must be an object")
        allowed = {"event_id", "event_type", "timestamp", "claim_id", "data"}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError(f"unknown trace-event fields {unknown}")
        data = value.get("data", {})
        if not isinstance(data, Mapping):
            raise ValueError("trace_event.data must be an object")
        strings = {name: value.get(name, "") for name in ("event_id", "event_type", "timestamp", "claim_id")}
        if not all(isinstance(item, str) for item in strings.values()):
            raise ValueError("trace-event identifiers and types must be strings")
        return cls(
            event_id=strings["event_id"],
            event_type=strings["event_type"] or "thought",
            timestamp=strings["timestamp"],
            claim_id=strings["claim_id"],
            data=dict(data),
        )


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    claim_id: str = ""
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _plain(self)


@dataclass(frozen=True)
class BoundaryMetrics:
    claims_total: int
    claims_supported: int
    claims_refuted: int
    claims_invalid: int
    claims_unknown: int
    unexplained_assumptions: int
    dependency_cycles: int
    invalid_receipts: int
    hard_findings: int
    advisory_findings: int

    @property
    def evidence_coverage(self) -> float:
        if self.claims_total == 0:
            return 0.0
        return self.claims_supported / self.claims_total


@dataclass(frozen=True)
class Assessment:
    request_id: str
    decision: Decision
    claim_statuses: Mapping[str, ClaimStatus]
    findings: tuple[Finding, ...]
    metrics: BoundaryMetrics
    context_digest: str
    output_digest: str
    released_output: str
    audit: Mapping[str, Any]
    assessed_at: str
    assessment_digest: str = ""

    def body(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "decision": self.decision,
            "claim_statuses": self.claim_statuses,
            "findings": self.findings,
            "metrics": self.metrics,
            "context_digest": self.context_digest,
            "output_digest": self.output_digest,
            "released_output": self.released_output,
            "audit": self.audit,
            "assessed_at": self.assessed_at,
        }

    def sealed(self) -> "Assessment":
        return dataclasses.replace(self, assessment_digest=digest_json(self.body()))

    def to_dict(self) -> dict[str, Any]:
        result = _plain(self)
        result["metrics"]["evidence_coverage"] = self.metrics.evidence_coverage
        return result
