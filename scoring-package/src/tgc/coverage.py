"""Deterministic recall oracle for method-bearing source regions.

The oracle is deliberately non-semantic.  It never selects a construction kind,
commitment, role, target, or verdict.  It finds source regions containing a
contract-bound vocabulary and requires an extractor to account for each region
through the existing claim/nonconstruction/unresolved disposition channel.
"""

from __future__ import annotations

import re
from typing import Any

from .common import canonical_sha256

COVERAGE_ORACLE_VERSION = "tgc-coverage-oracle/1.0.0"
_POLICY_FIELDS = {
    "version",
    "enabled",
    "merge_gap",
    "patterns",
    "enforcement",
    "policy_sha256",
}
_PATTERN_FIELDS = {"label", "regex"}


class CoverageOracleError(ValueError):
    """The contract's coverage-oracle policy is malformed or inconsistent."""


def coverage_policy_core(policy: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in policy.items() if key != "policy_sha256"}


def finalize_coverage_policy(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Validate source policy and add a canonical self-hash for generation."""

    if value is None:
        return None
    policy = dict(value)
    policy.pop("policy_sha256", None)
    validate_coverage_policy(policy, require_hash=False)
    policy["policy_sha256"] = canonical_sha256(policy)
    return policy


def validate_coverage_policy(
    policy: dict[str, Any] | None,
    *,
    require_hash: bool = True,
) -> None:
    if policy is None:
        return
    if not isinstance(policy, dict):
        raise CoverageOracleError("coverage_oracle must be an object or null")
    unknown = sorted(set(policy) - _POLICY_FIELDS)
    if unknown:
        raise CoverageOracleError(f"unknown coverage-oracle fields: {unknown}")
    if policy.get("version") != COVERAGE_ORACLE_VERSION:
        raise CoverageOracleError(
            f"unsupported coverage-oracle version {policy.get('version')!r}"
        )
    if not isinstance(policy.get("enabled"), bool):
        raise CoverageOracleError("coverage-oracle enabled must be boolean")
    gap = policy.get("merge_gap")
    if not isinstance(gap, int) or isinstance(gap, bool) or not 0 <= gap <= 4000:
        raise CoverageOracleError("coverage-oracle merge_gap must be 0..4000")
    if policy.get("enforcement") not in {
        "official_complete_records",
        "all_complete_records",
    }:
        raise CoverageOracleError("unsupported coverage-oracle enforcement mode")
    patterns = policy.get("patterns")
    if not isinstance(patterns, list) or not patterns:
        raise CoverageOracleError("coverage-oracle patterns must be a nonempty array")
    labels: set[str] = set()
    for index, item in enumerate(patterns):
        if not isinstance(item, dict) or set(item) != _PATTERN_FIELDS:
            raise CoverageOracleError(
                f"coverage-oracle pattern {index} must contain exactly label/regex"
            )
        label = item.get("label")
        regex = item.get("regex")
        if not isinstance(label, str) or not label or len(label) > 80:
            raise CoverageOracleError(f"coverage-oracle pattern {index} has invalid label")
        if label in labels:
            raise CoverageOracleError(f"duplicate coverage-oracle label {label!r}")
        labels.add(label)
        if not isinstance(regex, str) or not regex or len(regex) > 300:
            raise CoverageOracleError(f"coverage-oracle pattern {index} has invalid regex")
        try:
            compiled = re.compile(r"\b(?:" + regex + r")\b", re.IGNORECASE)
        except re.error as error:
            raise CoverageOracleError(
                f"coverage-oracle pattern {label!r} is invalid: {error}"
            ) from error
        # Capturing groups create unstable match APIs and serve no purpose here.
        if compiled.groups:
            raise CoverageOracleError(
                f"coverage-oracle pattern {label!r} may not contain capturing groups"
            )
    if require_hash:
        declared = policy.get("policy_sha256")
        observed = canonical_sha256(coverage_policy_core(policy))
        if declared != observed:
            raise CoverageOracleError(
                f"coverage-oracle policy hash mismatch: declared {declared}, observed {observed}"
            )


def coverage_regions(text: str, policy: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return maximal contract-defined method-bearing regions in source offsets."""

    if policy is None or not policy.get("enabled"):
        return []
    validate_coverage_policy(policy)
    hits: list[dict[str, Any]] = []
    for item in policy["patterns"]:
        regex = re.compile(r"\b(?:" + item["regex"] + r")\b", re.IGNORECASE)
        for match in regex.finditer(text):
            hits.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "label": item["label"],
                    "text": match.group(0),
                }
            )
    hits.sort(key=lambda item: (item["start"], item["end"], item["label"]))
    gap = int(policy["merge_gap"])
    regions: list[dict[str, Any]] = []
    for hit in hits:
        if regions and hit["start"] - regions[-1]["end"] <= gap:
            region = regions[-1]
            region["end"] = max(region["end"], hit["end"])
            region["labels"] = sorted(set(region["labels"]) | {hit["label"]})
            region["hits"].append(hit)
        else:
            regions.append(
                {
                    "start": hit["start"],
                    "end": hit["end"],
                    "labels": [hit["label"]],
                    "hits": [hit],
                }
            )
    return regions


def _overlaps(left_start: int, left_end: int, right_start: int, right_end: int) -> bool:
    return left_start < right_end and right_start < left_end


def coverage_oracle_receipt(
    *,
    sources: dict[str, str],
    bound_anchors: dict[str, dict[str, Any]],
    mention_dispositions: list[dict[str, Any]],
    policy: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if policy is None or not policy.get("enabled"):
        return None
    validate_coverage_policy(policy)
    disposition_anchor_ids = sorted(
        {
            str(item.get("anchor_id"))
            for item in mention_dispositions
            if isinstance(item, dict)
            and isinstance(item.get("anchor_id"), str)
            and item.get("anchor_id") in bound_anchors
        }
    )
    accounted_anchors = [bound_anchors[item] for item in disposition_anchor_ids]
    source_receipts: list[dict[str, Any]] = []
    unaccounted: list[dict[str, Any]] = []
    for source_id, text in sorted(sources.items()):
        regions = coverage_regions(text, policy)
        region_receipts: list[dict[str, Any]] = []
        for index, region in enumerate(regions, start=1):
            supporting = sorted(
                anchor["anchor_id"]
                for anchor in accounted_anchors
                if anchor.get("source_id") == source_id
                and _overlaps(
                    int(anchor["start"]),
                    int(anchor["end"]),
                    int(region["start"]),
                    int(region["end"]),
                )
            )
            item = {
                "region_id": f"{source_id}:coverage:{index:03d}",
                "source_id": source_id,
                "start": region["start"],
                "end": region["end"],
                "labels": region["labels"],
                "supporting_disposition_anchor_ids": supporting,
                "accounted": bool(supporting),
                "excerpt": text[region["start"] : region["end"]],
            }
            region_receipts.append(item)
            if not supporting:
                unaccounted.append(item)
        source_receipts.append(
            {
                "source_id": source_id,
                "region_count": len(region_receipts),
                "regions": region_receipts,
            }
        )
    core = {
        "receipt_version": "tgc-coverage-oracle-receipt/1.0.0",
        "policy_sha256": policy["policy_sha256"],
        "disposition_anchor_ids": disposition_anchor_ids,
        "source_receipts": source_receipts,
        "region_count": sum(item["region_count"] for item in source_receipts),
        "unaccounted_count": len(unaccounted),
        "unaccounted_regions": unaccounted,
    }
    return {**core, "receipt_sha256": canonical_sha256(core)}
