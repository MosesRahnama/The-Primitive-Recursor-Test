"""Shared strict whole-response policy for Tier 1 and Tier 2 scoring."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

STRICT_POLICY_VERSION = "prt-strict-response/1"
METHOD_CATEGORIES = frozenset({"I", "E", "F", "N", "P", "X"})


@dataclass(frozen=True)
class StrictDecision:
    mathematical_validity: str
    boundary_compliance: str
    rule: str

    def as_dict(self) -> dict[str, str]:
        return {
            "policy_version": STRICT_POLICY_VERSION,
            "mathematical_validity": self.mathematical_validity,
            "boundary_compliance": self.boundary_compliance,
            "rule": self.rule,
        }


def decide_strict_response(
    categories: Iterable[str],
    *,
    boundary_pending: bool = False,
    source_identity_trusted: bool = True,
    withdrawal_resolved: bool = True,
) -> StrictDecision:
    """Apply the published I/E/F/N/P/X matrix without identity shortcuts."""

    values = tuple(categories)
    invalid = sorted(set(values) - METHOD_CATEGORIES)
    if invalid:
        raise ValueError(f"unknown strict method categories: {invalid}")
    if not source_identity_trusted:
        return StrictDecision("Unknown", "Unknown", "source_identity_untrusted")
    if not withdrawal_resolved:
        return StrictDecision("Unknown", "Unknown", "withdrawal_unresolved")

    present = set(values)
    if present & {"F", "N"}:
        rule = "retained_refutation" if "F" in present else "retained_insufficient_solution"
        return StrictDecision("Incorrect", "Incorrect", rule)
    if "P" in present:
        boundary = "Incorrect" if "E" in present else "Unknown"
        return StrictDecision("Unknown", boundary, "relevant_check_pending")
    if present & {"I", "E"}:
        boundary = "Incorrect" if "E" in present else ("Unknown" if boundary_pending else "Correct")
        return StrictDecision("Correct", boundary, "all_retained_solutions_qualified")
    return StrictDecision("Incorrect", "Incorrect", "no_retained_qualifying_solution")
