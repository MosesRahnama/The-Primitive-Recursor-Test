from __future__ import annotations

import json
from typing import Any

from .config import InstanceContract

STANCE_MAP = {
    "asserted": "claimed_valid",
    "rejected": "claimed_invalid",
    "mentioned": "mentioned",
    "unclear": "unclear",
}


def _leaf_pointers(value: Any, path: str = "/transcription") -> list[str]:
    if isinstance(value, dict):
        result: list[str] = []
        for key, child in value.items():
            result.extend(_leaf_pointers(child, f"{path}/{key}"))
        return result
    if isinstance(value, list):
        result = []
        for index, child in enumerate(value):
            result.extend(_leaf_pointers(child, f"{path}/{index}"))
        return result
    return [path]


def _upgrade_payload(
    kind: str,
    payload: dict[str, Any],
    contract: InstanceContract,
) -> tuple[str, dict[str, Any]]:
    value = json.loads(json.dumps(payload))
    if value.pop("family_only", False) is True:
        return "family_only", {}
    if value.pop("unparseable", False) is True:
        return "unparseable", {}
    if kind in {"poly_interpretation", "additive_measure"} and isinstance(value.get("map"), dict):
        value["map"] = {
            symbol: {
                "parameters": list(contract.signature.get(symbol, [])),
                "expression": str(expression),
            }
            for symbol, expression in value["map"].items()
        }
    return "concrete", value


def migrate_construction_array(
    legacy_objects: list[dict[str, Any]],
    *,
    primary_idx: int,
    source_id: str,
    contract: InstanceContract,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    claims: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    local_by_idx: dict[int, str] = {}
    for position, legacy in enumerate(legacy_objects, start=1):
        idx = legacy.get("idx") if isinstance(legacy.get("idx"), int) else position
        local_id = f"legacy-{idx}"
        local_by_idx[idx] = local_id
        kind = legacy.get("kind", "other_unparseable")
        specificity, transcription = _upgrade_payload(
            kind,
            legacy.get("payload") or {},
            contract,
        )
        quote = str(legacy.get("quote") or "")
        evidence = [{"source_id": source_id, "text": quote}] if quote else []
        rejection_text = str(legacy.get("rejection_quote") or "")
        rejection = (
            [{"source_id": source_id, "text": rejection_text}]
            if rejection_text
            else []
        )
        role = "primary" if idx == primary_idx else "unclear"
        field_evidence = {
            pointer: list(evidence)
            for pointer in _leaf_pointers(transcription)
        }
        claims.append(
            {
                "local_id": local_id,
                "source_id": source_id,
                "kind": kind,
                "claim_status": STANCE_MAP.get(legacy.get("stance"), "unclear"),
                "answer_role": role,
                "claimed_target": "unclear",
                "specificity": specificity,
                "transcription": transcription,
                "evidence": evidence,
                "field_evidence": field_evidence,
                "rejection_evidence": rejection,
            }
        )
        warnings.append(
            {
                "local_id": local_id,
                "code": "LEGACY_COARSE_FIELD_EVIDENCE",
                "message": "Every payload leaf is bound to the construction-level legacy quote because v1 did not record field-specific evidence.",
            }
        )
    if primary_idx == 0:
        primary = {"status": "none", "claim_ids": []}
    elif primary_idx in local_by_idx:
        primary = {"status": "single", "claim_ids": [local_by_idx[primary_idx]]}
    else:
        primary = {"status": "unclear", "claim_ids": []}
        warnings.append(
            {
                "code": "LEGACY_PRIMARY_MISSING",
                "message": f"primary index {primary_idx} did not identify a migrated object",
            }
        )
    return claims, primary, warnings
