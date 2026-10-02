"""Account for every source paragraph without classifying its mathematical content."""

from __future__ import annotations

import re
from typing import Any

from .evidence import _all_occurrences


def paragraph_anchors(sources: dict[str, str], max_characters: int = 4000) -> dict[str, dict[str, Any]]:
    """Split on blank lines; split long paragraphs within the anchor length limit."""
    if max_characters < 1:
        raise ValueError("anchor length limit must be positive")
    result = {}
    for source_number, (source_id, text) in enumerate(sorted(sources.items()), 1):
        boundaries = [0]
        for separator in re.finditer(r"\n[ \t\r]*\n(?:[ \t\r]*\n)*", text):
            boundaries.extend((separator.start(), separator.end()))
        boundaries.append(len(text))
        paragraph_number = 0
        for index in range(0, len(boundaries) - 1, 2):
            start, end = boundaries[index:index + 2]
            while start < end and text[start].isspace():
                start += 1
            while start < end and text[end - 1].isspace():
                end -= 1
            while start < end:
                stop = min(start + max_characters, end)
                if stop < end:
                    split = max(text.rfind("\n", start, stop), text.rfind(" ", start, stop))
                    if split > start:
                        stop = split
                quote = text[start:stop]
                paragraph_number += 1
                result[f"p{source_number:02d}_{paragraph_number:04d}"] = {
                    "source_id": source_id,
                    "text": quote,
                    "occurrence": _all_occurrences(text, quote).index(start) + 1,
                }
                start = stop
                while start < end and text[start].isspace():
                    start += 1
    return result


def seed_paragraph_coverage(record: dict[str, Any], sources: dict[str, str], limit: int) -> None:
    record["anchors"] = paragraph_anchors(sources, limit)
    record["coverage"]["mention_dispositions"] = [
        {"anchor_id": anchor_id, "disposition": "<FILL: claim | nonconstruction | unresolved>",
         "claim_ids": [], "reason": "<FILL: reason for nonconstruction or unresolved; empty for claim>"}
        for anchor_id in record["anchors"]
    ]


def paragraph_coverage_issues(record: dict[str, Any], sources: dict[str, str], limit: int) -> list[dict[str, str]]:
    expected = paragraph_anchors(sources, limit)
    anchors = record.get("anchors") if isinstance(record.get("anchors"), dict) else {}
    coverage = record.get("coverage") if isinstance(record.get("coverage"), dict) else {}
    dispositions = coverage.get("mention_dispositions")
    if not isinstance(dispositions, list):
        dispositions = []
    by_anchor = {item["anchor_id"]: item for item in dispositions
                 if isinstance(item, dict) and isinstance(item.get("anchor_id"), str)}
    issues = []
    linked = set()
    for anchor_id, locator in expected.items():
        if anchors.get(anchor_id) != locator:
            issues.append({"code": "SOURCE_PARAGRAPH_CHANGED_OR_MISSING", "path": f"$.anchors.{anchor_id}",
                           "message": "retain the seeded source paragraph and its occurrence unchanged"})
        item = by_anchor.get(anchor_id)
        if item is None:
            issues.append({"code": "SOURCE_PARAGRAPH_UNACCOUNTED", "path": "$.coverage.mention_dispositions",
                           "message": f"account for source paragraph {anchor_id}"})
        elif item.get("disposition") == "claim" and isinstance(item.get("claim_ids"), list):
            linked.update(cid for cid in item["claim_ids"] if isinstance(cid, str))
    claims = record.get("claims") if isinstance(record.get("claims"), list) else []
    for claim in claims:
        if isinstance(claim, dict) and claim.get("local_id") not in linked:
            issues.append({"code": "CLAIM_SOURCE_PARAGRAPH_REQUIRED", "path": "$.coverage.mention_dispositions",
                           "message": f"link claim {claim.get('local_id')!r} to its source paragraph"})
    if coverage.get("completeness_status") == "complete" and any(
        isinstance(item, dict) and item.get("disposition") == "unresolved" for item in dispositions
    ):
        issues.append({"code": "COVERAGE_COMPLETE_WITH_UNRESOLVED", "path": "$.coverage.completeness_status",
                       "message": "unresolved source passages require uncertain coverage"})
    return issues
