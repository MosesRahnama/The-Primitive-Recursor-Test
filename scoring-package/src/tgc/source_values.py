"""Check explicit source values without treating quotation as entailment."""

from __future__ import annotations

import re
from typing import Any

_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
_ARGUMENT = re.compile(
    r"\b(first|second|third|fourth|fifth|[1-9][0-9]*(?:st|nd|rd|th)?)"
    r"[\s\-\u2010-\u2015]+(?:argument|coordinate|component)\b"
    r"|\b(?:argument|coordinate|component)\s*(?:number\s*|#\s*)?([1-9][0-9]*)\b",
    re.IGNORECASE,
)


def explicit_argument_values(text: str) -> set[int]:
    values: set[int] = set()
    for match in _ARGUMENT.finditer(text):
        token = (match.group(1) or match.group(2)).lower()
        values.add(_ORDINALS[token] if token in _ORDINALS else int(re.match(r"\d+", token)[0]))
    return values


def argument_evidence_check(
    claim: dict[str, Any], anchors: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    value = (claim.get("transcription") or {}).get("argument")
    refs = (claim.get("field_evidence") or {}).get("/transcription/argument", [])
    if not isinstance(value, int) or isinstance(value, bool):
        return {"status": "not_applicable"}
    found: set[int] = set()
    for ref in refs if isinstance(refs, list) else []:
        item = anchors.get(ref, {})
        found.update(explicit_argument_values(str(item.get("text", ""))))
    status = (
        "contradicted"
        if found and value not in found
        else "explicit_value_matches"
        if found == {value}
        else "not_established"
    )
    return {
        "status": status,
        "field": "/transcription/argument",
        "value": value,
        "source_values": sorted(found),
    }
