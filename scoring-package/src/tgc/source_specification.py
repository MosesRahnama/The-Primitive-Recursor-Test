"""Source completeness is a reader assertion, not a mathematical certificate."""

from __future__ import annotations

from typing import Any


def specification_schema(
    model: dict[str, Any],
    *,
    quotes: bool = False,
    kind: str | None = None,
) -> dict[str, Any]:
    components = model["source_specification"]["missing_components_by_kind"]
    allowed = (
        components.get(kind, [])
        if kind is not None
        else sorted({component for values in components.values() for component in values})
    )
    evidence = {"type": "array", "minItems": 1, "uniqueItems": True,
                "items": {"type": "string", "minLength": 1}}
    return {
        "type": "object", "additionalProperties": False,
        "required": ["status", "missing_components", "quotes" if quotes else "evidence"],
        "properties": {
            "status": {"enum": ["complete", "missing_definition", "ambiguous"]},
            "missing_components": {
                "type": "array", "uniqueItems": True,
                "items": {"enum": sorted(allowed)},
            },
            "quotes" if quotes else "evidence": evidence,
        },
        "allOf": [{
            "if": {"properties": {"status": {"const": "missing_definition"}},
                   "required": ["status"]},
            "then": {"properties": {"missing_components": {"minItems": 1}}},
            "else": {"properties": {"missing_components": {"maxItems": 0}}},
        }],
    }


def specification_issues(
    claim: dict[str, Any],
    model: dict[str, Any],
    *,
    complete_contract_issues: tuple[dict[str, str], ...] = (),
) -> list[str]:
    """Check annotation consistency; exact quotations do not prove an omission."""
    spec = claim.get("source_specification")
    if not isinstance(spec, dict):
        return []
    problems = []
    status = spec.get("status")
    if status == "missing_definition":
        if claim.get("specificity") not in {"partial", "unparseable"}:
            problems.append("missing_definition requires partial or unparseable specificity")
        allowed = model["source_specification"]["missing_components_by_kind"].get(claim.get("kind"), [])
        missing = spec.get("missing_components")
        if isinstance(missing, list) and any(c not in allowed for c in missing):
            problems.append("missing component is not declared for this construction kind")
    if status == "complete" and claim.get("specificity") == "partial":
        for issue in complete_contract_issues:
            problems.append(
                "complete source cannot omit template-supported content: "
                + issue["message"]
            )
    return problems
