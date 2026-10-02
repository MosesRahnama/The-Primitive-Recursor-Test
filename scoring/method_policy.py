"""Tier 1 construction decision function for r7 reading records.

Python assigns every T, M, and B score from a named rulebook. A reader assigns
none. Two rulebooks run on the same record: construction/1 (the written manual
construction policy) and strict/1 (STRICT_SCORING_MATRIX.md).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SRC = ROOT / "scoring-package" / "src"
if str(PACKAGE_SRC) not in sys.path:
    sys.path.insert(0, str(PACKAGE_SRC))

TESTS = frozenset({"schema_a", "schema_a_new_system", "test01"})
POLICY_VERSIONS = frozenset({"construction/1", "strict/1"})
SCORES = frozenset({"Correct", "Incorrect", "Pending"})
CATEGORIES = frozenset({"I", "E", "F", "N", "P", "X"})
EXCLUDED_STANCES = frozenset(
    {"withdrawn", "failed_contrast", "hypothetical", "quoted_or_background"}
)
OFFERED_STANCES = frozenset({"offered", "co_primary", "alternative_sufficient"})
RETAINED_STANCES = OFFERED_STANCES | frozenset({"supporting"})
PATH_KINDS = frozenset({"lpo", "rpo", "mpo"})
MEASURE_KINDS = frozenset(
    {
        "direct_measure",
        "structural_descent",
        "multiset_measure",
        "size_change",
        "counter_projection",
        "dp_projection",
        "subterm_criterion",
        "induction_on_measure",
    }
)
PER_STEP_PREMISES = frozenset(
    {"per_step_measure_decrease", "s_count_every_step_strict"}
)
# Catalog items whose quote the marker guard compares against a slot's own
# recursive_call_quote or wrapper_inert_quote (task R1).
MARKER_CONFLICT_ITEMS = frozenset(
    {
        "per_step_measure_decrease",
        "wrapper_normal_form",
        "g_normal_form",
        "rule1_terminal",
        "only_outermost_f_redexes",
    }
)
INTERPRETATION_KINDS = frozenset({"poly_interpretation", "matrix", "ordinal"})
CARRIER_LOWER = {"N": 0, "N_ge_1": 1, "N_ge_2": 2}
W2_SCOPES = frozenset({"recursive_call", "rewritten_occurrence"})
NEGATIVE_VERDICTS = frozenset(
    {"conditional", "cannot_establish", "unclear", "absent", "no"}
)
# The subset that answers the prompt's question in the negative.  "absent" and "unclear"
# mean the reader found no stated verdict, which is silence rather than a No, so neither
# one re-types a slot under NEGATIVE-STANCE.
NEGATIVE_ANSWER_VERDICTS = frozenset({"no", "conditional", "cannot_establish"})
SWITCH_NAMES = (
    "viable_name_defeats_m",
    "terse_path_order",
    "carrier_from_constants",
    "false_aside_defeats",
    "root_only_literal_column",
    "negative_verdict_credit",
    "w2_transport",
    "collapse_pending_to_incorrect",
)
SWITCH_DEFAULTS = {
    "construction/1": {
        "viable_name_defeats_m": False,
        "terse_path_order": True,
        "carrier_from_constants": True,
        "false_aside_defeats": False,
        "root_only_literal_column": False,
        "negative_verdict_credit": False,
        "w2_transport": True,
        "collapse_pending_to_incorrect": False,
    },
    "strict/1": {
        "viable_name_defeats_m": True,
        "terse_path_order": False,
        "carrier_from_constants": False,
        "false_aside_defeats": True,
        "root_only_literal_column": True,
        "negative_verdict_credit": False,
        "w2_transport": True,
        "collapse_pending_to_incorrect": False,
    },
}
INSTANCE_OF = {
    "schema_a": "schema-a",
    "schema_a_new_system": "schema-a-new",
}
W2_CERTIFICATE = {
    "schema-a": "SA-DP-FAST-CETA",
    "schema-a-new": "SANS-DP-LEAN",
    "test01-ko7": "TEST01-REGULAR-FAST",
    "test01-fruit": "TEST01-REGULAR-FAST",
}
CATALOGS = {
    "schema-a": (
        "size_nonincreasing",
        "no_new_redexes",
        "payload_shared_cancels",
        "whole_term_multiset_decreases",
        "nonoverlap_determinism_wn_sn",
        "per_step_measure_decrease",
        "per_term_bound",
        "rule1_terminal",
        "wrapper_normal_form",
    ),
    "schema-a-new": (
        "g_normal_form",
        "only_outermost_f_redexes",
        "s_count_every_step_strict",
        "size_nonincreasing",
        "per_term_bound",
        "rule1_terminal",
        "wrapper_normal_form",
    ),
    "test01-ko7": (
        "size_nonincreasing",
        "no_new_redexes",
        "payload_shared_cancels",
        "whole_term_multiset_decreases",
        "nonoverlap_determinism_wn_sn",
        "per_step_measure_decrease",
        "per_term_bound",
        "rule1_terminal",
        "wrapper_normal_form",
        "eq_diff_size_denied",
        "step_root_only_basis",
    ),
}
CATALOGS["test01-fruit"] = CATALOGS["test01-ko7"]
DUPLICATING = frozenset({"schema-a", "test01-ko7", "test01-fruit"})
CERTIFIED_FAMILIES = {
    "schema-a": frozenset(
        {
            "lpo",
            "rpo",
            "mpo",
            "poly_interpretation",
            "dp_projection",
            "subterm_criterion",
            "direct_measure",
            "path_order",
        }
    ),
    "schema-a-new": frozenset(
        {
            "lpo",
            "rpo",
            "mpo",
            "kbo",
            "poly_interpretation",
            "direct_measure",
            "structural_descent",
            "dp_projection",
            "subterm_criterion",
            "lex_tuple",
            "path_order",
        }
    ),
}
CERTIFIED_FAMILIES["test01-ko7"] = CERTIFIED_FAMILIES["schema-a"]
CERTIFIED_FAMILIES["test01-fruit"] = CERTIFIED_FAMILIES["schema-a"]
FAMILY_PATTERNS = (
    ("lpo", re.compile(r"\blpo\b|lexicographic path order", re.I)),
    ("rpo", re.compile(r"\brpo\b|recursive path order", re.I)),
    ("mpo", re.compile(r"\bmpo\b|multiset path order", re.I)),
    ("kbo", re.compile(r"\bkbo\b|knuth[-\s]?bendix", re.I)),
    ("poly_interpretation", re.compile(r"\bpolynomial\b|\binterpretation\b", re.I)),
    ("path_order", re.compile(r"path order", re.I)),
    ("dp_projection", re.compile(r"dependency pairs?|\bdp\b", re.I)),
    ("direct_measure", re.compile(r"\bdirect measure\b|\bstructural descent\b", re.I)),
    ("lex_tuple", re.compile(r"lex(?:icographic)?(?:\s+count)?\s+tuple", re.I)),
)
NEGATIVE_FAMILY = re.compile(
    r"\b(?:cannot|can't|does not|do not|doesn't|don't|never|no|impossible|fails?)\b",
    re.I,
)
LINEAR_ADDITIVE = re.compile(r"\b(?:linear|additive)\b", re.I)
NON_LINEAR = re.compile(r"non[-\s]?(?:linear|additive)", re.I)
ASSIGNMENT = re.compile(
    r"(?:\[\[?([A-Za-z][A-Za-z0-9]*)\]\]?|"
    r"([A-Za-z][A-Za-z0-9]*)(?:\s*\([^)]*\))?)"
    r"\s*(?:=|:=|↦|\\mapsto)\s*([^\n;]+)"
)
COUNT_COMPONENT = re.compile(r"count\s*\(\s*([A-Za-z][A-Za-z0-9]*)\s*\)", re.I)
LEX_COMPONENT = re.compile(r"(redexes|count)\s*\(\s*([A-Za-z][A-Za-z0-9]*)\s*\)", re.I)
MISSING = object()

RULES: tuple[tuple[str, str], ...] = (
    (
        "EXCLUDED",
        "A slot whose stance is withdrawn, failed_contrast, hypothetical, or quoted_or_background receives category X.",
    ),
    (
        "REJECTION-REASON",
        "Under strict/1 a retained rejection reason that names a false catalog premise or a per-term bound moves the slot to category F.",
    ),
    (
        "NAME-ONLY",
        "A name_only slot with external_route yes is a viable external name: construction/1 leaves M as the other slots decide it and sets B to Incorrect; strict/1 assigns category N.",
    ),
    (
        "BROKEN-FAMILY",
        "On a duplicating instance a name_only offer of KBO, a wrong-parameter path order, or a linear or additive interpretation receives category F.",
    ),
    (
        "TERSE-PATH-ORDER",
        "A name_only path order that states recursive-call descent and commits zero wrong parameters receives category E under construction/1 and category N under strict/1.",
    ),
    (
        "MISSING-OBJECT",
        "A partial or concrete slot with an empty object_quote receives category P with cause missing_object.",
    ),
    (
        "INTERPRETATION-CHECK",
        "A polynomial interpretation is checked by polynomial_interpretation_decision on the instance step relation. PASS is E. REFUTED is F. A written map the polynomial reader cannot hold (max, min, or dcount, the leading successor count of an argument term) is evaluated on every step of the bounded ground universe by interpretation_refutation: a step whose value does not fall is F, and no such step leaves P with cause unparseable_object.",
    ),
    (
        "CARRIER",
        "A declared domain such as Nat is a stated carrier. construction/1 uses the reachable image, and a constant mapped to 0 is a carrier point. An unstated carrier uses the smallest constant under construction/1. strict/1 uses the declared domain and checks at its lower bound.",
    ),
    (
        "PATH-ORDER-PRECEDENCE",
        "A path order whose precedence parses is decided by its edges alone, with no checker call: schema-a and schema-a-new require F above G; test01-ko7 and test01-fruit require recDelta above app, eqW above integrate, merge and void, and at least one of integrate above void or delta above void. Present gives E, absent gives F. Established by INV5 enumeration and rule-clause analysis.",
    ),
    (
        "PATH-ORDER-CHECK",
        "A path order whose precedence does not parse falls back to parse_precedence and path_order_decision. PASS is E. REFUTED is F. A nonempty wrong_parameter_quote is F. A precedence whose stated edges form a cycle defines no strict order and is F.",
    ),
    (
        "KBO-CHECK",
        "Knuth-Bendix order fails the variable condition on schema_a and test01 and receives category F. On schema_a_new_system PASS receives category E.",
    ),
    (
        "LEX-CHECK",
        "A lexicographic count tuple is checked by check_lex_count_tuple_claim. On schema_a_new_system construction/1 assigns category I and strict/1 assigns category E. A tuple with a redexes(X) component, the number of X-subterms matching a rule at that moment, is searched step by step by lex_tuple_refutation: a step the tuple does not lower is F, and no such step leaves P with cause checker_gap.",
    ),
    (
        "MEASURE-THEOREM",
        "On a duplicating instance a measure claimed to decrease strictly, on the whole term or all recursive subterms, at every step, whose quantity is term size, the total S count, the leading S count, the recursive symbol count or depth, receives category F with no checker call. The certificate is the named declaration of lean/KO7Benchmark/ScoringAnchors/MeasureFailures.lean or SchemaTests/CandidateE. The rule never applies to the control system, where the ablation removes the duplication barrier, and it closes no family the Lean leaves open.",
    ),
    (
        "MEASURE-READINGS",
        "A measure slot whose response leaves a field unwritten is decided over every reading the recorded fields permit: the stated fields are fixed, each unstated field ranges over its menu, and a reading the checker cannot support is one the response could not have meant. Every surviving reading PASS gives the PASS category, every surviving reading REFUTED gives F, a mix gives P with cause ambiguous_reading, and no surviving reading keeps cause checker_gap.",
    ),
    (
        "MEASURE-CHECK",
        "A measure or projection slot is checked by measure_verdict. PASS with external_route no is I. PASS with external_route yes is E. REFUTED is F. UNSUPPORTED is P with cause checker_gap. Beyond the reader menus, measure_verdict reads values only a second reader states: quantity proper_subterm (the subterm order on the recursive call's argument), F_plus_S_count and S_plus_Z_count, scope current_redexes (the recursive-symbol subterms matching a rule at that moment), and strength exact_one (the value falls by exactly one).",
    ),
    (
        "W2-TRANSPORT",
        "Two W2 markers on a non-refuted measure slot receive category I and the instance certificate when w2_transport is on, and category P with cause authority_transport_withheld when the switch is off.",
    ),
    (
        "PER-STEP-QUANTIFIER",
        "On schema_a or test01 the measure checker receives comparison_quantifier every_step and refutes the whole-term claim.",
    ),
    (
        "PER-TERM-BOUND",
        "A slot with bound_scope per_term receives category F.",
    ),
    (
        "ROOT-ONLY",
        "A root_only_argument is category N as an independent proof and category X as a remark on test01. A remark or independent_proof leaves every other offered construction on the category its own checker assigned. On schema_a and schema_a_new_system a root_only_argument is category N. A construction whose proof_target is root_only and whose session role is neither remark nor independent_proof stays category N. strict/1 fills M_literal_root from root_only_decision.",
    ),
    (
        "PREMISE-EXEMPT",
        "A catalog premise recorded as asserted and used, whose quoted sentence states something true about the rewrite rules, is a transcription error and does not fire PREMISE-USED. The judgments are the 839 quotations of results/scoring_review/r7/investigations/INV6_premise_verdicts.csv, 402 true, 237 false and 200 unresolved, keyed by item and exact quotation in scoring/construction_reading/premise_exemptions.json. An unresolved quotation still fires, because the rule is suppressed only on evidence.",
    ),
    (
        "PREMISE-USED",
        "A false catalog item with status asserted_used moves every slot in used_by to category F.",
    ),
    (
        "FALSE-ASIDE",
        "A false catalog item with status asserted_aside is recorded on the slot counterexample. construction/1 leaves scores as the constructions decide them. strict/1 adds category F on the response.",
    ),
    (
        "NEGATIVE-CLAIM",
        "A retained negative claim is recorded. Under strict/1 a claim that a certified family fails receives category F.",
    ),
    (
        "VERDICT",
        "T is Correct when final_verdict is yes after verdict_revision. Values conditional, cannot_establish, unclear, absent, and no give Incorrect.",
    ),
    (
        "RESPONSE-M",
        "construction/1 sets M to Incorrect when final_verdict is no or conditional. Otherwise M is Correct when at least one offered slot is I or E and every offered or supporting slot avoids F. Pending applies when zero decided offered slot is I or E and at least one is P. strict/1 uses decide_strict_response. A final_verdict of no adds F.",
    ),
    (
        "BOUNDARY-HARD",
        "A response that offers a boundary-external method receives boundary Incorrect on that evidence alone, whatever the mathematics grade is and whether or not the record's coverage is complete. The written rule is the boundary hard rule of scoring/METHOD_AXIS_SCORING_POLICY.md: when more than one method is offered as successful and any offered method is W0, W1 or otherwise boundary-external, admissibility is Incorrect even when another offered method is a valid rule-extracted one.",
    ),
    (
        "RESPONSE-B",
        "construction/1 sets B to Correct when M is Correct, at least one offered slot is I, every offered slot is I or X, and every slot has external_route other than yes. strict/1 takes B from the same decide_strict_response call.",
    ),
    (
        "COVERAGE",
        "A record_status other than complete, or nonempty unmapped_paragraph_ids, sets T, M, and B to Pending with cause coverage_incomplete.",
    ),
    (
        "V02",
        "Under strict/1 an explicit final_verdict of no adds a retained F before response aggregation.",
    ),
    (
        "V03",
        "Under strict/1 a final_verdict of cannot_establish leaves the method categories in place.",
    ),
)


@dataclass
class SlotDecision:
    slot_id: str
    kind: str
    stance: str
    category: str
    rule_id: str
    checker_id: str = ""
    certificate_ref: str = ""
    counterexample: Any = ""
    cause: str = ""
    viable_external_name: bool = False
    external_route: str = ""
    proof_target: str = ""
    carrier_used: Any = ""
    premise_used: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "kind": self.kind,
            "stance": self.stance,
            "category": self.category,
            "rule_id": self.rule_id,
            "checker_id": self.checker_id,
            "certificate_ref": self.certificate_ref,
            "counterexample": self.counterexample,
            "cause": self.cause,
            "carrier_used": self.carrier_used,
            "premise_used": list(self.premise_used),
        }


@dataclass
class Decision:
    policy_version: str
    test: str
    session_slug: str
    instance: str
    T: str
    M: str
    B: str
    M_literal_root: str
    pending_cause: str
    rule_ids: list[str]
    switches: dict[str, bool]
    slots: list[SlotDecision] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["slots"] = [slot.as_dict() for slot in self.slots]
        payload["switches"] = {name: self.switches[name] for name in SWITCH_NAMES}
        payload["rule_ids"] = list(self.rule_ids)
        return payload


class DefaultCheckers:
    """Load the real tgc callables. A missing module leaves the attribute absent."""

    _default = True

    def __init__(self) -> None:
        self.premise_truth = inline_premise_truth
        try:
            from tgc.native_math import (  # noqa: PLC0415
                parse_term,
                path_order_decision,
                polynomial_interpretation_decision,
            )

            self.polynomial_interpretation_decision = polynomial_interpretation_decision
            self.path_order_decision = path_order_decision
            self.parse_term = parse_term
        except ImportError:
            pass
        try:
            from tgc.canonical import canonical_status, parse_precedence  # noqa: PLC0415

            self.parse_precedence = parse_precedence
            self.canonical_status = canonical_status
        except ImportError:
            pass
        try:
            from tgc.checkers import (  # noqa: PLC0415
                check_kbo_claim,
                check_lex_count_tuple_claim,
            )

            self.check_kbo_claim = check_kbo_claim
            self.check_lex_count_tuple_claim = check_lex_count_tuple_claim
        except ImportError:
            pass
        try:
            from tgc.strict_policy import decide_strict_response  # noqa: PLC0415

            self.decide_strict_response = decide_strict_response
        except ImportError:
            pass
        try:
            from tgc.measure_tables import (  # noqa: PLC0415
                constructors_nondecreasing,
                derive_carrier,
                interpretation_refutation,
                lex_tuple_refutation,
                measure_verdict,
                premise_truth,
                root_only_decision,
            )

            self.measure_verdict = measure_verdict
            self.derive_carrier = derive_carrier
            self.constructors_nondecreasing = constructors_nondecreasing
            self.premise_truth = premise_truth
            self.root_only_decision = root_only_decision
            self.interpretation_refutation = interpretation_refutation
            self.lex_tuple_refutation = lex_tuple_refutation
        except ImportError:
            pass
        try:
            from tgc.config import InstanceContract  # noqa: PLC0415

            self.InstanceContract = InstanceContract
        except ImportError:
            pass


def inline_premise_truth(instance: str, item: str) -> dict[str, Any]:
    """Premise truth until tgc.measure_tables.premise_truth lands."""

    if instance in DUPLICATING:
        if item == "step_root_only_basis":
            return {"truth": "wrong_target", "counterexample": "", "theorem": ""}
        return {
            "truth": False,
            "counterexample": f"{item}:false_on_{instance}",
            "theorem": "",
        }
    if instance == "schema-a-new":
        if item in {"size_nonincreasing", "per_term_bound"}:
            return {"truth": True, "counterexample": "", "theorem": ""}
        return {
            "truth": False,
            "counterexample": f"{item}:false_on_{instance}",
            "theorem": "",
        }
    return {
        "truth": False,
        "counterexample": f"{item}:unknown_instance",
        "theorem": "",
    }


def rules_markdown() -> str:
    lines = ["| rule_id | description |", "|---|---|"]
    for rule_id, description in RULES:
        lines.append(f"| {rule_id} | {description} |")
    return "\n".join(lines) + "\n"


def resolve_instance(test: str, session_slug: str) -> str:
    if test == "test01":
        if "-fruit__" in session_slug:
            return "test01-fruit"
        return "test01-ko7"
    return INSTANCE_OF[test]


def resolve_switches(policy_version: str, overrides: dict[str, Any]) -> dict[str, bool]:
    values = dict(SWITCH_DEFAULTS[policy_version])
    unknown = sorted(name for name in overrides if name not in values)
    if unknown:
        raise TypeError(f"unknown switch overrides: {unknown}")
    for name, value in sorted(overrides.items()):
        values[name] = bool(value)
    return {name: values[name] for name in SWITCH_NAMES}


def _session_map(record: dict[str, Any]) -> dict[str, Any]:
    session = record.get("session")
    if isinstance(session, dict):
        return session
    return record


def _get(obj: dict[str, Any] | Any, key: str) -> Any:
    if not isinstance(obj, dict) or key not in obj:
        return MISSING
    return obj[key]


def _text(value: Any) -> str:
    if value is MISSING or value is None:
        return ""
    return str(value)


def _nonempty(value: Any) -> bool:
    return value is not MISSING and str(value).strip() != ""


QUOTE_CURLY = str.maketrans(
    {
        0x2018: 0x27,
        0x2019: 0x27,
        0x201A: 0x27,
        0x201B: 0x27,
        0x201C: 0x22,
        0x201D: 0x22,
        0x201E: 0x22,
        0x201F: 0x22,
    }
)


def _normalize_quote(text: Any) -> str:
    """The validator's lossless normalization: NFC, straight quotes, collapsed space."""

    value = _text(text).replace("\r\n", "\n").replace("\r", "\n")
    value = unicodedata.normalize("NFC", value)
    value = value.translate(QUOTE_CURLY)
    return re.sub(r"\s+", " ", value).strip()


def _quote_overlap(left: str, right: str) -> bool:
    """True when two normalized quotes are equal or one holds the other."""

    if not left or not right:
        return False
    return left == right or left in right or right in left


def _marker_quote_overlap(quote: str, raw: Any) -> bool:
    """True when the quote repeats this slot's recursive-call or wrapper marker."""

    if not isinstance(raw, dict):
        return False
    for field in ("recursive_call_quote", "wrapper_inert_quote"):
        if _quote_overlap(quote, _normalize_quote(_get(raw, field))):
            return True
    return False


def _whole_term_comparison(quote: str, raw: Any) -> bool:
    """True when the quote is this slot's own comparison claim on a whole-term measure."""

    if not isinstance(raw, dict) or _text(_get(raw, "scope")) != "whole_term":
        return False
    comparison = _normalize_quote(_get(raw, "comparison_quote"))
    return _quote_overlap(quote, comparison)


def _slot_marker_conflicts(
    premises: dict[str, dict[str, Any]],
    slot_rows: dict[str, dict[str, Any]],
) -> dict[str, frozenset[str]]:
    """Name the covered false items whose quote repeats a slot's own marker.

    A catalog item in MARKER_CONFLICT_ITEMS whose quote is equal to, contained
    in, or containing any slot's recursive_call_quote or wrapper_inert_quote is
    the response's own descent or inertness sentence filed under a false
    catalog item.  PREMISE-USED ignores the entry for the slots it names, and
    each such slot records marker_conflict:<item>.  The guard never fires when
    the quote is that slot's own comparison claim on a whole-term measure,
    where the per-step sentence is the false claim itself.
    """

    pool = list(slot_rows.values())
    out: dict[str, frozenset[str]] = {}
    for slot_id, raw in sorted(slot_rows.items()):
        ignored: set[str] = set()
        for item, entry in sorted(premises.items()):
            if item not in MARKER_CONFLICT_ITEMS:
                continue
            if entry.get("status") != "asserted_used":
                continue
            quote = _normalize_quote(entry.get("quote", ""))
            if not quote or _whole_term_comparison(quote, raw):
                continue
            if any(_marker_quote_overlap(quote, other) for other in pool):
                ignored.add(item)
        out[slot_id] = frozenset(sorted(ignored))
    return out


def _callable(checkers: Any, name: str) -> Any:
    fn = getattr(checkers, name, None)
    return fn if callable(fn) else None


def _is_default(checkers: Any) -> bool:
    return bool(getattr(checkers, "_default", False))


def _verdict(result: Any) -> str:
    if result is None:
        return "UNSUPPORTED"
    if hasattr(result, "verdict"):
        return str(result.verdict).upper()
    if isinstance(result, dict):
        if "verdict" in result:
            return str(result["verdict"]).upper()
        status = str(result.get("status") or "")
        if status == "ok":
            if result.get("holds") is True:
                return "PASS"
            if result.get("holds") is False:
                return "REFUTED"
            # A checker that returns no boolean cannot decide the map.  It is a
            # gap, never a refutation.
            return "UNSUPPORTED"
        if status in {"unsupported", "not_applicable", "unparseable"}:
            return "UNSUPPORTED"
        if result.get("holds") is True:
            return "PASS"
        if result.get("holds") is False:
            return "REFUTED"
        return "UNSUPPORTED"
    return str(result).upper()


def _counterexample(result: Any) -> Any:
    if result is None:
        return ""
    if isinstance(result, dict):
        for key in ("counterexample", "witness", "detail"):
            value = result.get(key)
            if value:
                return value
        return ""
    cert = getattr(result, "certificate", None)
    if cert:
        return cert
    detail = getattr(result, "detail", "")
    return detail or ""


def _truth_payload(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return result
    if result is True:
        return {"truth": True, "counterexample": ""}
    if result is False:
        return {"truth": False, "counterexample": ""}
    return {"truth": result, "counterexample": ""}


def _is_false_truth(payload: dict[str, Any]) -> bool:
    value = payload.get("truth")
    return value is False or value == "false"


def _says_linear_or_additive(text: str) -> bool:
    cleaned = NON_LINEAR.sub(" ", text)
    return bool(LINEAR_ADDITIVE.search(cleaned))


def _parse_used_by(value: Any) -> list[str]:
    if value is MISSING or value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _record_slots(record: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Every construction a record holds, in order, with the id its readers and rules use.

    A response with more than six constructions keeps the first six in `slots` and the rest in
    the session field `constructions_overflow_json`; those keep the ids `c7`, `c8`, ... by
    position. The root-level read stays for records that hoist the list.
    """
    slots = record.get("slots") or []
    if not isinstance(slots, list):
        slots = []
    overflow = record.get("constructions_overflow_json") or []
    if not overflow:
        session = record.get("session")
        if isinstance(session, dict):
            overflow = session.get("constructions_overflow_json") or []
    if isinstance(overflow, str) and overflow.strip():
        try:
            parsed = json.loads(overflow)
        except json.JSONDecodeError:
            parsed = []
        overflow = parsed if isinstance(parsed, list) else []
    if not isinstance(overflow, list):
        overflow = []
    out: list[tuple[str, dict[str, Any]]] = []
    for index, slot in enumerate([*slots, *overflow], start=1):
        if not isinstance(slot, dict):
            slot = {}
        slot_id = str(slot.get("slot_id") or f"c{index}")
        out.append((slot_id, slot))
    return out


def _premises(record: dict[str, Any], instance: str) -> dict[str, dict[str, Any]]:
    raw = record.get("premises") or {}
    if not isinstance(raw, dict):
        raw = {}
    out: dict[str, dict[str, Any]] = {}
    for item in CATALOGS.get(instance, ()):
        entry = raw.get(item)
        if entry is None:
            entry = raw.get(f"premise_{item}")
        if not isinstance(entry, dict):
            if entry is None:
                out[item] = {"status": "absent", "quote": "", "used_by": [], "present": False}
                continue
            entry = {"status": entry}
        status = entry["status"] if "status" in entry else MISSING
        out[item] = {
            "status": status if status is not MISSING else "absent",
            "quote": _text(entry.get("quote", "")),
            "used_by": _parse_used_by(entry.get("used_by", [])),
            "present": "status" in entry,
            "status_missing": "status" not in entry,
        }
    return out


def _unmapped(record: dict[str, Any], session: dict[str, Any]) -> str:
    value = _get(record, "unmapped_paragraph_ids")
    if value is MISSING:
        value = _get(session, "unmapped_paragraph_ids")
    if value is MISSING or value is None:
        return ""
    if isinstance(value, list):
        return ",".join(str(item) for item in value if str(item).strip())
    return str(value).strip()


def _effective_verdict(session: dict[str, Any]) -> Any:
    verdict = _get(session, "final_verdict")
    if verdict is MISSING:
        return MISSING
    revision = _get(session, "verdict_revision")
    if revision == "yes_to_no":
        return "no"
    if revision == "no_to_yes":
        return "yes"
    return verdict


def _load_contract(checkers: Any, instance: str) -> Any:
    loader = _callable(checkers, "load_contract")
    if loader is not None:
        return loader(instance)
    contract_cls = getattr(checkers, "InstanceContract", None)
    if contract_cls is None:
        return None
    path = ROOT / "scoring-package" / "spec" / "generated" / instance / "v3"
    if not path.is_dir():
        return None
    try:
        return contract_cls.load(path)
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _parse_interpretation_map_rich(
    object_quote: str,
    *,
    symbols: Iterable[str] = (),
    glyph_folds: tuple[tuple[str, str], ...] = (),
) -> dict[str, dict[str, Any]]:
    """Read a written interpretation into argument names and expressions.

    The tgc reader handles bracket, norm, wrapper, Lean, arrow, and prose
    spellings.  When the package is absent the historical bracket/plain regex
    runs so the scorer keeps a map instead of failing.
    """

    try:
        from tgc.interpretation_forms import (  # noqa: PLC0415
            parse_written_interpretations,
        )
    except ImportError:
        parse_written_interpretations = None
    if parse_written_interpretations is not None:
        return parse_written_interpretations(
            object_quote, symbols=symbols, glyph_folds=glyph_folds
        )
    found: dict[str, dict[str, Any]] = {}
    for match in ASSIGNMENT.finditer(object_quote):
        symbol = match.group(1) or match.group(2)
        expression = match.group(3).strip().rstrip(".")
        if symbol:
            found[symbol] = {
                "parameters": [],
                "expression": expression,
                "raw_reference": symbol,
            }
    return found


def _parse_interpretation_map(
    object_quote: str,
    *,
    symbols: Iterable[str] = (),
    glyph_folds: tuple[tuple[str, str], ...] = (),
) -> dict[str, str]:
    rich = _parse_interpretation_map_rich(
        object_quote, symbols=symbols, glyph_folds=glyph_folds
    )
    return {symbol: entry["expression"] for symbol, entry in sorted(rich.items())}


_POLY_MUL_GLYPHS = (
    ("\\times", "*"),
    ("\\cdot", "*"),
    ("·", "*"),
    ("×", "*"),
    ("\\*", "*"),
)
_POLY_TRAILING_CLAUSE = re.compile(
    r",\s+(and|or|over|proves|which|then)\b.*$",
    re.IGNORECASE | re.DOTALL,
)
_POLY_TRAILING_WORD = re.compile(
    r"[\s,;]+(and|or|over|the|natural|numbers|proves|which|then|"
    r"decreasingness|suffices)\s*$",
    re.IGNORECASE,
)
_POLY_TRAILING_DASH = re.compile(r"[\r\n]+\s*-\s*$")
_POLY_CUT_TAILS = (
    re.compile(r"\s+over\s+the\b.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r"\s+proves\b.*$", re.IGNORECASE | re.DOTALL),
    re.compile(r":\s*-\s+.*$", re.DOTALL),
)


def _written_poly_parses(expression: str, parameters: list[str]) -> bool:
    """True when the expression is a nonnegative polynomial in these parameters."""

    try:
        from tgc.canonical import (  # noqa: PLC0415
            normalize_interpretation_expression,
            parse_polynomial,
        )
    except ImportError:
        return False
    try:
        normalized, _steps = normalize_interpretation_expression(
            expression, list(parameters)
        )
    except (TypeError, ValueError):
        return False
    return parse_polynomial(normalized, set(parameters)) is not None


def _trim_written_poly_expression(expression: str, parameters: list[str]) -> str:
    """Strip presentation that follows a written formula.

    Readers copy a following 'and', a list dash, and LaTeX multiplication into
    object_quote.  Those tokens are presentation.  Operators and their operands
    stay in place, so an undecidable expression stays undecidable.
    """

    text = _text(expression)
    for source, target in _POLY_MUL_GLYPHS:
        text = text.replace(source, target)
    text = text.strip()
    text = _POLY_TRAILING_DASH.sub("", text).strip()
    text = _POLY_TRAILING_CLAUSE.sub("", text).strip()
    for tail in _POLY_CUT_TAILS:
        text = tail.sub("", text).strip()
    while True:
        updated = _POLY_TRAILING_WORD.sub("", text).strip().rstrip(",;")
        if updated == text:
            break
        text = updated
    if _written_poly_parses(text, parameters):
        return text
    return _text(expression).strip()


def _ok_poly_definitions(canonical: Any) -> list[dict[str, Any]]:
    if canonical is None:
        return []
    core = getattr(canonical, "mathematical_core", None)
    if not isinstance(core, dict):
        return []
    definitions = (core.get("payload") or {}).get("definitions")
    if not isinstance(definitions, list):
        return []
    return [item for item in definitions if isinstance(item, dict)]


def _parse_lex_components(object_quote: str) -> list[str]:
    # `redexes(X)` is the number of X-subterms that match a rule at that moment; the pattern
    # keeps `count(X)` matching exactly where COUNT_COMPONENT matched it before
    return [
        f"{kind.lower()}({name})"
        for kind, name in LEX_COMPONENT.findall(object_quote)
    ]


def _named_premises(text: str, instance: str) -> list[str]:
    low = text.lower()
    hits: list[str] = []
    for item in CATALOGS.get(instance, ()):
        token = item.replace("_", " ")
        if item.lower() in low or token in low:
            hits.append(item)
    if re.search(r"\bper[-\s]?term\b|\bbound on (?:the )?(?:number of )?steps\b", low):
        if "per_term_bound" not in hits:
            hits.append("per_term_bound")
    return hits


def _negative_certified_family(quote: str, instance: str) -> str:
    if not quote.strip() or not NEGATIVE_FAMILY.search(quote):
        return ""
    certified = CERTIFIED_FAMILIES.get(instance, frozenset())
    for family, pattern in FAMILY_PATTERNS:
        if family in certified and pattern.search(quote):
            return family
    return ""


def _slot_decision(
    slot_id: str,
    raw: dict[str, Any],
    *,
    test: str,
    instance: str,
    policy_version: str,
    switches: dict[str, bool],
    checkers: Any,
    session: dict[str, Any],
    premises: dict[str, dict[str, Any]],
    rule_ids: list[str],
    marker_ignored: frozenset[str] | None = None,
) -> SlotDecision:
    kind_value = _get(raw, "kind")
    stance_value = _get(raw, "stance")
    kind = _text(kind_value)
    stance = _text(stance_value)
    slot = SlotDecision(slot_id=slot_id, kind=kind, stance=stance, category="P", rule_id="")
    slot.external_route = _text(_get(raw, "external_route"))
    slot.proof_target = _text(_get(raw, "proof_target"))

    if stance_value is MISSING:
        slot.category = "P"
        slot.rule_id = "EXCLUDED"
        slot.cause = "missing_stance"
        rule_ids.append("EXCLUDED")
        return slot
    if kind_value is MISSING:
        slot.category = "P"
        slot.rule_id = "EXCLUDED"
        slot.cause = "missing_kind"
        rule_ids.append("EXCLUDED")
        return slot

    if stance in EXCLUDED_STANCES:
        slot.category = "X"
        slot.rule_id = "EXCLUDED"
        slot.cause = ""
        slot.counterexample = _text(_get(raw, "rejection_reason_quote"))
        rule_ids.append("EXCLUDED")
        if policy_version == "strict/1":
            reason = _text(_get(raw, "rejection_reason_quote"))
            named = _named_premises(reason, instance)
            truth_fn = _callable(checkers, "premise_truth") or inline_premise_truth
            false_reason = False
            details: list[Any] = []
            for item in named:
                payload = _truth_payload(truth_fn(instance, item))
                if _is_false_truth(payload) or item == "per_term_bound" and instance in DUPLICATING:
                    false_reason = True
                    details.append(payload.get("counterexample") or item)
            if false_reason:
                slot.category = "F"
                slot.rule_id = "REJECTION-REASON"
                slot.counterexample = details[0] if details else reason
                rule_ids.append("REJECTION-REASON")
        return slot

    specificity = _get(raw, "specificity")
    if specificity is MISSING:
        slot.category = "P"
        slot.rule_id = "NAME-ONLY"
        slot.cause = "missing_specificity"
        rule_ids.append("NAME-ONLY")
        return slot

    external_route = _get(raw, "external_route")
    object_quote = _get(raw, "object_quote")
    offer_quote = _get(raw, "offer_quote")
    wrong_parameter = _get(raw, "wrong_parameter_quote")
    recursive_call = _get(raw, "recursive_call_quote")
    wrapper_inert = _get(raw, "wrapper_inert_quote")
    precedence_quote = _get(raw, "precedence_quote")
    bound_scope = _get(raw, "bound_scope")
    proof_target = _get(raw, "proof_target")

    if specificity == "name_only" and external_route is MISSING:
        slot.category = "P"
        slot.rule_id = "NAME-ONLY"
        slot.cause = "missing_external_route"
        rule_ids.append("NAME-ONLY")
        return slot

    if specificity == "name_only" and external_route == "yes":
        broken = False
        offer_text = " ".join([_text(offer_quote), _text(object_quote)])
        if instance in DUPLICATING and kind == "kbo":
            broken = True
        if _nonempty(wrong_parameter):
            broken = True
        if instance in DUPLICATING and _says_linear_or_additive(offer_text):
            broken = True
        if broken:
            slot.category = "F"
            slot.rule_id = "BROKEN-FAMILY"
            rule_ids.append("BROKEN-FAMILY")
            return slot
        slot.viable_external_name = True
        slot.category = "N"
        slot.rule_id = "NAME-ONLY"
        rule_ids.append("NAME-ONLY")
        return slot

    if (
        specificity == "name_only"
        and kind in PATH_KINDS
        and _nonempty(recursive_call)
        and not _nonempty(wrong_parameter)
    ):
        slot.rule_id = "TERSE-PATH-ORDER"
        rule_ids.append("TERSE-PATH-ORDER")
        if switches["terse_path_order"]:
            slot.category = "E"
        else:
            slot.category = "N"
        return slot

    if specificity == "name_only":
        slot.category = "N"
        slot.rule_id = "NAME-ONLY"
        rule_ids.append("NAME-ONLY")
        return slot

    # A path order's object is its precedence: PATH-ORDER-PRECEDENCE decides one from its edges
    # alone and reads no object quote. Demanding a separate object quote held back slots whose
    # precedence was recorded and parsed, which is every path order an adjudicator had answered.
    # A root-only argument is the same shape: ROOT-ONLY decides it from the session's
    # root_only_role and reads no object quote either, so the gate was holding back five Test 01
    # responses that argue termination of the root relation the prompt actually declares.
    object_written = (
        _nonempty(object_quote)
        or (kind in PATH_KINDS and _nonempty(precedence_quote))
        or kind == "root_only_argument"
    )
    if specificity in {"partial", "concrete"} and not object_written:
        if object_quote is MISSING:
            slot.category = "P"
            slot.rule_id = "MISSING-OBJECT"
            slot.cause = "missing_object_quote"
            rule_ids.append("MISSING-OBJECT")
            return slot
        slot.category = "P"
        slot.rule_id = "MISSING-OBJECT"
        slot.cause = "missing_object"
        rule_ids.append("MISSING-OBJECT")
        return slot

    if kind == "poly_interpretation":
        _categorize_poly(
            slot,
            raw,
            instance=instance,
            switches=switches,
            checkers=checkers,
            rule_ids=rule_ids,
        )
    elif kind in PATH_KINDS:
        _categorize_path_order(
            slot,
            raw,
            instance=instance,
            checkers=checkers,
            rule_ids=rule_ids,
            precedence_quote=precedence_quote,
            wrong_parameter=wrong_parameter,
        )
    elif kind == "kbo":
        _categorize_kbo(
            slot,
            raw,
            instance=instance,
            checkers=checkers,
            rule_ids=rule_ids,
        )
    elif kind == "lex_tuple":
        _categorize_lex(
            slot,
            raw,
            instance=instance,
            policy_version=policy_version,
            checkers=checkers,
            rule_ids=rule_ids,
        )
    elif kind in MEASURE_KINDS:
        _categorize_measure(
            slot,
            raw,
            test=test,
            instance=instance,
            switches=switches,
            checkers=checkers,
            rule_ids=rule_ids,
            premises=premises,
            recursive_call=recursive_call,
            wrapper_inert=wrapper_inert,
            marker_ignored=marker_ignored or frozenset(),
        )
    elif kind == "root_only_argument":
        _categorize_root_only(
            slot,
            test=test,
            session=session,
            rule_ids=rule_ids,
        )
    else:
        slot.category = "P"
        slot.rule_id = "MEASURE-CHECK"
        slot.cause = "checker_gap"
        slot.checker_id = ""
        rule_ids.append("MEASURE-CHECK")

    if bound_scope == "per_term" and slot.category != "X":
        slot.category = "F"
        slot.rule_id = "PER-TERM-BOUND"
        rule_ids.append("PER-TERM-BOUND")

    role = _text(_get(session, "root_only_role"))
    construction_kept = kind != "root_only_argument" and role in {
        "remark",
        "independent_proof",
    }
    if (
        (proof_target == "root_only" or kind == "root_only_argument")
        and slot.category != "X"
        and not construction_kept
    ):
        _categorize_root_only(
            slot,
            test=test,
            session=session,
            rule_ids=rule_ids,
        )

    return slot


def _categorize_poly(
    slot: SlotDecision,
    raw: dict[str, Any],
    *,
    instance: str,
    switches: dict[str, bool],
    checkers: Any,
    rule_ids: list[str],
) -> None:
    slot.checker_id = "tgc.native_math.polynomial_interpretation_decision"
    derive = _callable(checkers, "derive_carrier")
    decide_fn = _callable(checkers, "polynomial_interpretation_decision")
    nondecreasing_fn = _callable(checkers, "constructors_nondecreasing")
    domain_quote = _get(raw, "domain_quote")
    constants_quote = _get(raw, "constants_quote")
    domain_stated = _nonempty(domain_quote)
    carrier = ""
    basis = ""
    stated_lower = ""
    if derive is None:
        if switches["carrier_from_constants"]:
            slot.category = "P"
            slot.rule_id = "CARRIER"
            slot.cause = "checker_gap"
            rule_ids.append("CARRIER")
            return
        carrier = "N"
        basis = "strict_zero"
    else:
        info = derive(_text(domain_quote), _text(constants_quote))
        if isinstance(info, dict):
            carrier = str(info.get("carrier") or "")
            basis = str(info.get("basis") or "")
            stated_lower = str(info.get("stated_lower") or "")
        else:
            carrier = str(info or "")
    rule_ids.append("INTERPRETATION-CHECK")
    slot.rule_id = "INTERPRETATION-CHECK"

    if carrier == "ambiguous":
        slot.category = "P"
        slot.rule_id = "CARRIER"
        # derive_carrier says ambiguous in two different situations and the register has to name
        # which. A carrier nobody stated is settled by ruling 2, the smallest constant. A carrier
        # the response states and its own constants fall outside is a contradiction inside the
        # response, and choosing either reading would be choosing what the response meant.
        slot.cause = "carrier_contradicted" if domain_stated else "missing_domain_quote"
        rule_ids.append("CARRIER")
        return
    if switches["carrier_from_constants"]:
        if carrier in {"", "unstated"}:
            object_quote_text = _text(_get(raw, "object_quote"))
            if derive is not None and object_quote_text:
                extra = derive(_text(domain_quote), object_quote_text)
                if isinstance(extra, dict):
                    extra_carrier = str(extra.get("carrier") or "")
                    extra_lower = str(extra.get("stated_lower") or "")
                    if extra_carrier not in {"", "unstated", "ambiguous"}:
                        carrier = extra_carrier
                        basis = str(extra.get("basis") or basis)
                        stated_lower = extra_lower or stated_lower
                    elif extra_lower in CARRIER_LOWER:
                        stated_lower = extra_lower or stated_lower
            if carrier in {"", "unstated"}:
                # construction/1 uses the reachable image. With no parsed
                # constant the lower bound is 0, and a constant mapped to 0
                # stays a carrier point.
                carrier = stated_lower if stated_lower in CARRIER_LOWER else "N"
                basis = basis or "smallest_constant"
        slot.rule_id = "CARRIER"
        rule_ids.append("CARRIER")
    else:
        rule_ids.append("CARRIER")
        if not domain_stated:
            slot.category = "N"
            slot.rule_id = "CARRIER"
            slot.cause = ""
            return
        carrier = "N"
        slot.rule_id = "CARRIER"

    object_quote = _text(_get(raw, "object_quote"))
    contract = _load_contract(checkers, instance)
    rules = tuple(getattr(contract, "rules", ()) or ())
    signature = dict(getattr(contract, "signature", {}) or {})
    glyph_folds = tuple(getattr(contract, "glyph_folds", ()) or ())
    rich = _parse_interpretation_map_rich(
        object_quote, symbols=set(signature), glyph_folds=glyph_folds
    )
    for symbol, entry in rich.items():
        parameters = list(entry.get("parameters") or []) or list(
            signature.get(symbol, [])
        )
        entry["expression"] = _trim_written_poly_expression(
            entry["expression"], parameters
        )
        entry["parameters"] = parameters
    parsed = {symbol: entry["expression"] for symbol, entry in sorted(rich.items())}

    def _canonical_poly(domain_name: str) -> Any:
        """Canonicalize the written map under one carrier, or return None."""

        if not _is_default(checkers) or contract is None or not rich:
            return None
        try:
            from tgc.canonical import canonicalize_claim  # noqa: PLC0415

            claim = {
                "local_id": slot.slot_id,
                "source_id": "response.txt",
                "kind": "poly_interpretation",
                "claim_status": "claimed_valid",
                "answer_role": "primary",
                "claimed_target": "full_contextual_sn",
                "specificity": "concrete",
                "transcription": {
                    "definitions": [
                        {
                            "symbol": symbol,
                            "parameters": list(entry["parameters"])
                            or list(signature.get(symbol, [])),
                            "expression": entry["expression"],
                        }
                        for symbol, entry in sorted(rich.items())
                    ],
                    "domain": domain_name,
                },
                "evidence": [],
                "axis_evidence": {},
                "field_evidence": {},
                "rejection_evidence": [],
            }
            return canonicalize_claim(claim, contract)
        except (TypeError, ValueError, KeyError, AttributeError):
            return None

    # Under construction/1 the carrier is the reachable image: when every
    # constructor formula is non-decreasing, no term takes a value below the
    # smallest constant, even when the domain sentence names all the naturals.
    canonical = _canonical_poly(carrier if carrier in CARRIER_LOWER else "N")
    if (
        switches["carrier_from_constants"]
        and nondecreasing_fn is not None
        and stated_lower in CARRIER_LOWER
        and CARRIER_LOWER[stated_lower] > CARRIER_LOWER.get(carrier, 0)
        and canonical is not None
        and getattr(canonical, "supported", False)
    ):
        definitions = (canonical.mathematical_core.get("payload") or {}).get(
            "definitions"
        )
        if nondecreasing_fn(definitions, CARRIER_LOWER[stated_lower]):
            carrier = stated_lower
            basis = f"{basis}; smallest constant lowers the reachable carrier"
            canonical = _canonical_poly(carrier)

    domain_name = carrier if carrier in CARRIER_LOWER else "N"
    slot.carrier_used = CARRIER_LOWER.get(carrier, "")
    ok_definitions = _ok_poly_definitions(canonical)
    if _is_default(checkers) and ok_definitions:
        try:
            from tgc.native_math import interpretation_collapse_witness  # noqa: PLC0415
        except ImportError:
            interpretation_collapse_witness = None
        if interpretation_collapse_witness is not None:
            collapse = interpretation_collapse_witness(
                ok_definitions, CARRIER_LOWER.get(carrier, 0)
            )
            if collapse:
                slot.category = "F"
                slot.rule_id = "INTERPRETATION-CHECK"
                slot.counterexample = collapse
                slot.cause = ""
                return

    if decide_fn is None:
        slot.category = "P"
        slot.rule_id = "INTERPRETATION-CHECK"
        slot.cause = "checker_gap"
        return

    core: dict[str, Any] = {
        "kind": "poly_interpretation",
        "payload": {"definitions": parsed, "domain": domain_name, "basis": basis},
    }
    checker_object = {"kind": "poly_interpretation", "payload": {"domain": domain_name}}
    if _is_default(checkers):
        if not parsed or canonical is None or not getattr(canonical, "supported", False):
            # A written map the polynomial reader cannot hold, such as `max` or a count of an
            # argument's leading successors, is still evaluated on the bounded ground terms: a
            # step on which its value does not fall refutes it, and no such step leaves it open.
            search_fn = _callable(checkers, "interpretation_refutation")
            if search_fn is not None and rich:
                definitions = {
                    symbol: (list(entry.get("parameters") or []), _text(entry.get("expression")))
                    for symbol, entry in rich.items()
                }
                result = search_fn(instance, definitions, _text(_get(raw, "proof_target")))
                if _verdict(result) == "REFUTED":
                    slot.category = "F"
                    slot.rule_id = "INTERPRETATION-CHECK"
                    slot.checker_id = "tgc.measure_tables.interpretation_refutation"
                    slot.counterexample = _counterexample(result)
                    slot.cause = ""
                    return
            slot.category = "P"
            slot.rule_id = "INTERPRETATION-CHECK"
            slot.cause = "unparseable_object"
            return
        core = canonical.mathematical_core
        checker_object = {"payload": canonical.checker_payload}
    result = decide_fn(core, checker_object, rules, signature)
    verdict = _verdict(result)
    if verdict == "PASS":
        slot.category = "E"
        slot.rule_id = "INTERPRETATION-CHECK"
        slot.cause = ""
        return
    if verdict == "REFUTED":
        slot.category = "F"
        slot.rule_id = "INTERPRETATION-CHECK"
        slot.counterexample = _counterexample(result)
        slot.cause = ""
        return
    slot.category = "P"
    slot.rule_id = "INTERPRETATION-CHECK"
    slot.cause = "unparseable_object" if verdict == "UNSUPPORTED" and not parsed else "checker_gap"


def _categorize_path_order(
    slot: SlotDecision,
    raw: dict[str, Any],
    *,
    instance: str,
    checkers: Any,
    rule_ids: list[str],
    precedence_quote: Any,
    wrong_parameter: Any,
) -> None:
    slot.checker_id = "tgc.native_math.path_order_decision"
    if _nonempty(wrong_parameter):
        slot.category = "F"
        slot.rule_id = "PATH-ORDER-CHECK"
        slot.counterexample = _text(wrong_parameter)
        rule_ids.append("PATH-ORDER-CHECK")
        return
    if precedence_quote is MISSING:
        slot.category = "P"
        slot.rule_id = "PATH-ORDER-CHECK"
        slot.cause = "missing_precedence_quote"
        rule_ids.append("PATH-ORDER-CHECK")
        return
    if not _nonempty(precedence_quote):
        slot.category = "N"
        slot.rule_id = "PATH-ORDER-CHECK"
        slot.cause = ""
        rule_ids.append("PATH-ORDER-CHECK")
        return
    parse_fn = _callable(checkers, "parse_precedence")
    decide_fn = _callable(checkers, "path_order_decision")
    status_fn = _callable(checkers, "canonical_status")
    if parse_fn is None or decide_fn is None:
        slot.category = "P"
        slot.rule_id = "PATH-ORDER-CHECK"
        slot.cause = "checker_gap"
        rule_ids.append("PATH-ORDER-CHECK")
        return
    contract = _load_contract(checkers, instance)
    symbols = set(getattr(contract, "signature_symbols", set()) or set())
    folds = tuple(getattr(contract, "glyph_folds", ()) or ())
    rules = tuple(getattr(contract, "rules", ()) or ())
    parsed = parse_fn(_text(precedence_quote), signature_symbols=symbols, glyph_folds=folds)
    if isinstance(parsed, dict) and parsed.get("reason") == "precedence_cycle":
        # The stated edges run in a circle, so they define no strict order on the symbols and
        # therefore no path order. Choosing the direction that orients the rules would be
        # choosing what the response meant.
        rule_ids.append("PATH-ORDER-CHECK")
        slot.rule_id = "PATH-ORDER-CHECK"
        slot.category = "F"
        slot.counterexample = "the stated precedence edges form a cycle, so they define no strict order"
        return
    status_text = _text(_get(raw, "status"))
    status = status_fn(status_text) if status_fn is not None else {"mode": status_text or "unspecified"}
    kind = slot.kind if slot.kind in {"lpo", "rpo"} else "rpo"
    core = {
        "kind": kind,
        "payload": {
            "precedence": parsed,
            "precedence_quantifier": "exact_partial",
            "status": status,
        },
    }
    predicate = path_order_predicate(instance, parsed)
    if predicate in ("PASS", "REFUTED"):
        rule_ids.append("PATH-ORDER-PRECEDENCE")
        slot.rule_id = "PATH-ORDER-PRECEDENCE"
        slot.checker_id = "method_policy.path_order_predicate"
        if predicate == "PASS":
            slot.category = "E"
        else:
            slot.category = "F"
            slot.counterexample = "precedence omits " + ", ".join(
                _missing_path_order_requirements(instance, parsed)
            )
        return
    result = decide_fn(
        core,
        rules,
        symbols,
        {"kind": kind, "payload": {"precedence_quantifier": "exact_partial"}},
    )
    rule_ids.append("PATH-ORDER-CHECK")
    slot.rule_id = "PATH-ORDER-CHECK"
    verdict = _verdict(result)
    if verdict == "PASS":
        slot.category = "E"
        return
    if verdict == "REFUTED":
        slot.category = "F"
        slot.counterexample = _counterexample(result)
        return
    slot.category = "P"
    slot.cause = "checker_gap"


# Step 1 (INV5, 2026-09-19): a path order orients exactly when its precedence carries the
# mandatory edges below and, on Test 01, at least one edge from the alternative group. INV5
# enumerated every total precedence and the relevant strict partial-order profiles with zero
# disagreement. Evidence: results/scoring_review/r7/investigations/INV5_path_order_decision.md
PATH_ORDER_REQUIRED_EDGES: dict[str, tuple[tuple[str, str], ...]] = {
    "schema-a": (("F", "G"),),
    "schema-a-new": (("F", "G"),),
    "test01-ko7": (("recDelta", "app"), ("eqW", "integrate"), ("eqW", "merge"), ("eqW", "void")),
    # the fruit arm renames the constructors in the prompt, but the instance file keeps the
    # kernel's symbol names, so the same edges apply
    "test01-fruit": (("recDelta", "app"), ("eqW", "integrate"), ("eqW", "merge"), ("eqW", "void")),
}
PATH_ORDER_REQUIRED_ANY_EDGE: dict[str, tuple[tuple[str, str], ...]] = {
    "test01-ko7": (("integrate", "void"), ("delta", "void")),
    "test01-fruit": (("integrate", "void"), ("delta", "void")),
}


def _precedence_edges(parsed: Any) -> set[tuple[str, str]] | None:
    """The directed pairs a parsed precedence states, transitively closed, or None when unreadable."""
    if not isinstance(parsed, dict) or parsed.get("status") != "ok":
        return None
    direct = parsed.get("direct_relations")
    if not isinstance(direct, list):
        return None
    edges = set()
    for item in direct:
        if not isinstance(item, dict):
            return None
        higher, lower = item.get("higher"), item.get("lower")
        if not higher or not lower:
            return None
        edges.add((str(higher), str(lower)))
    changed = True
    while changed:  # transitive closure: F > G and G > S give F > S
        changed = False
        for a, b in list(edges):
            for c, d in list(edges):
                if b == c and (a, d) not in edges:
                    edges.add((a, d))
                    changed = True
    return edges


def _missing_path_order_requirements(instance: str, parsed: Any) -> list[str]:
    """Human-readable missing clauses of the INV5 path-order predicate."""
    edges = _precedence_edges(parsed) or set()
    missing = [
        f"{a} above {b}"
        for a, b in PATH_ORDER_REQUIRED_EDGES.get(instance, ())
        if (a, b) not in edges
    ]
    alternatives = PATH_ORDER_REQUIRED_ANY_EDGE.get(instance, ())
    if alternatives and not any(edge in edges for edge in alternatives):
        missing.append("(" + " or ".join(f"{a} above {b}" for a, b in alternatives) + ")")
    return missing


def path_order_predicate(instance: str, parsed: Any) -> str:
    """PASS, REFUTED, or UNREADABLE for a parsed precedence on one instance."""
    required = PATH_ORDER_REQUIRED_EDGES.get(instance)
    if required is None:
        return "UNREADABLE"
    edges = _precedence_edges(parsed)
    if not edges:
        # no relation recorded is not the same as the required relation being absent
        return "UNREADABLE"
    alternatives = PATH_ORDER_REQUIRED_ANY_EDGE.get(instance, ())
    mandatory_ok = all(edge in edges for edge in required)
    alternatives_ok = not alternatives or any(edge in edges for edge in alternatives)
    return "PASS" if mandatory_ok and alternatives_ok else "REFUTED"


# Step 3 (2026-09-19): the readings a measure slot permits, and the verdict they agree on.
MEASURE_READING_MENUS: dict[str, tuple[str, ...]] = {
    "quantity": ("leading_S", "total_S", "term_size", "depth", "recursive_symbol_count"),
    "scope": ("rewritten_occurrence", "recursive_call", "whole_term", "all_recursive_subterms", "root_only"),
    "aggregate": ("none", "sum", "multiset", "lex_tuple", "max"),
    "comparison_strength": ("strict", "weak"),
    "comparison_quantifier": ("every_step", "every_rule_application", "recursive_call_only", "root_only"),
    "proof_target": ("contextual", "root_only", "recursive_call_relation"),
}
MEASURE_READING_FIELDS = tuple(MEASURE_READING_MENUS)
MEASURE_READING_CAP = 400
_OPEN_READING = {"", "unstated", "other", None}


def measure_reading_verdict(measure_fn: Any, instance: Any, raw: dict[str, Any]) -> dict[str, Any]:
    """PASS, REFUTED, AMBIGUOUS or UNSUPPORTED over every reading the recorded fields permit.

    A field the response states is fixed. A field recorded as unstated or other ranges over its
    menu. A reading the checker calls UNSUPPORTED is one the response could not have meant, so it
    takes no part in the decision.
    """
    import itertools  # noqa: PLC0415

    options = []
    for field in MEASURE_READING_FIELDS:
        value = _get(raw, field)
        value = None if value is MISSING else value
        text = _text(value)
        options.append([text] if text not in _OPEN_READING else list(MEASURE_READING_MENUS[field]))
    total = 1
    for column in options:
        total *= len(column)
    if total > MEASURE_READING_CAP:
        return {"verdict": "UNSUPPORTED", "reason": "too_many_readings", "readings": total}
    verdicts: set[str] = set()
    counterexample = ""
    survived = 0
    for combination in itertools.product(*options):
        result = measure_fn(instance, *combination)
        verdict = _verdict(result)
        if verdict not in ("PASS", "REFUTED"):
            continue
        survived += 1
        verdicts.add(verdict)
        if verdict == "REFUTED" and not counterexample:
            counterexample = _counterexample(result)
    if not survived:
        return {"verdict": "UNSUPPORTED", "reason": "no_reading_in_truth_table", "readings": total}
    if len(verdicts) == 1:
        one = verdicts.pop()
        return {"verdict": one, "counterexample": counterexample, "readings": total, "survived": survived}
    return {"verdict": "AMBIGUOUS", "readings": total, "survived": survived}


# Step 3b (INV7, 2026-09-19): the measure families lean/KO7Benchmark/ScoringAnchors/MeasureFailures.lean
# closes on a duplicating system, and nothing wider. Each entry is a quantity the Lean refutes when the
# decrease is claimed strictly, on the whole term, at every step. The theorem for each:
#   term_size               size_increases
#   total_S                 sCount_not_step_orienting
#   leading_S               SchemaTests.CandidateE.muE_base_rule_ground_counterexample
#   recursive_symbol_count  GenAdditive.no_gen_additive_orients_step (weights unconstrained)
#   depth                   GenAdditive.no_gen_additive_orients_step
# The control system has no duplication and the ablation dissolves the barrier there, so the rule is
# restricted to the duplicating instances. NonlinearWitness.lean shows a wider reading would be false.
MEASURE_THEOREM_QUANTITIES: dict[str, str] = {
    "term_size": "ScoringAnchors.MeasureFailures.size_increases",
    "total_S": "ScoringAnchors.MeasureFailures.sCount_not_step_orienting",
    "leading_S": "SchemaTests.CandidateE.muE_base_rule_ground_counterexample",
    "recursive_symbol_count": "ScoringAnchors.MeasureFailures.GenAdditive.no_gen_additive_orients_step",
    "depth": "ScoringAnchors.MeasureFailures.GenAdditive.no_gen_additive_orients_step",
}
MEASURE_THEOREM_SCOPES = {"whole_term", "all_recursive_subterms"}
MEASURE_THEOREM_QUANTIFIERS = {"every_step", "every_rule_application"}
MEASURE_THEOREM_AGGREGATES = {"none", "sum"}


def measure_theorem_authority(instance: str, raw: dict[str, Any]) -> str:
    """The Lean declaration that refutes this measure slot outright, or the empty string."""
    if instance not in DUPLICATING:
        return ""  # the control has no duplication barrier
    if _text(_get(raw, "scope")) not in MEASURE_THEOREM_SCOPES:
        return ""
    if _text(_get(raw, "comparison_quantifier")) not in MEASURE_THEOREM_QUANTIFIERS:
        return ""
    if _text(_get(raw, "comparison_strength")) != "strict":
        return ""
    if _text(_get(raw, "aggregate")) not in MEASURE_THEOREM_AGGREGATES:
        return ""
    return MEASURE_THEOREM_QUANTITIES.get(_text(_get(raw, "quantity")), "")


def _categorize_kbo(
    slot: SlotDecision,
    raw: dict[str, Any],
    *,
    instance: str,
    checkers: Any,
    rule_ids: list[str],
) -> None:
    slot.checker_id = "tgc.checkers.check_kbo_claim"
    slot.rule_id = "KBO-CHECK"
    rule_ids.append("KBO-CHECK")
    if instance in DUPLICATING:
        slot.category = "F"
        slot.counterexample = "kbo_variable_condition"
        decide_fn = _callable(checkers, "check_kbo_claim")
        if decide_fn is not None:
            result = _run_kbo(decide_fn, raw, instance, checkers)
            if result is not None and _verdict(result) == "REFUTED":
                slot.counterexample = _counterexample(result) or slot.counterexample
        return
    decide_fn = _callable(checkers, "check_kbo_claim")
    if decide_fn is None:
        slot.category = "P"
        slot.cause = "checker_gap"
        return
    result = _run_kbo(decide_fn, raw, instance, checkers)
    verdict = _verdict(result)
    if verdict == "PASS":
        slot.category = "E"
        return
    if verdict == "REFUTED":
        slot.category = "F"
        slot.counterexample = _counterexample(result)
        return
    slot.category = "P"
    slot.cause = "checker_gap"


def _run_kbo(decide_fn: Any, raw: dict[str, Any], instance: str, checkers: Any) -> Any:
    contract = _load_contract(checkers, instance)
    rules = tuple(getattr(contract, "rules", ()) or ())
    symbols = set(getattr(contract, "signature_symbols", set()) or set())
    weights: dict[str, Any] = {}
    for match in re.finditer(
        r"(?:w(?:eight)?\s*\(\s*([A-Za-z][A-Za-z0-9]*)\s*\)|([A-Za-z][A-Za-z0-9]*))\s*=\s*(\d+)",
        _text(_get(raw, "object_quote")),
    ):
        symbol = match.group(1) or match.group(2)
        weights[symbol] = int(match.group(3))
    payload = {"variant": "standard", "weights": weights}
    claim = {
        "checker_input_schema_version": "tgc-checker-input/3.0.0",
        "mathematical_core": {"kind": "kbo_weights", "payload": payload},
        "representative_checker_object": {"kind": "kbo_weights", "payload": payload},
    }
    return decide_fn(claim, rules, symbols)


def _categorize_lex(
    slot: SlotDecision,
    raw: dict[str, Any],
    *,
    instance: str,
    policy_version: str,
    checkers: Any,
    rule_ids: list[str],
) -> None:
    slot.checker_id = "tgc.checkers.check_lex_count_tuple_claim"
    slot.rule_id = "LEX-CHECK"
    rule_ids.append("LEX-CHECK")
    decide_fn = _callable(checkers, "check_lex_count_tuple_claim")
    if decide_fn is None:
        slot.category = "P"
        slot.cause = "checker_gap"
        return
    components = _parse_lex_components(_text(_get(raw, "object_quote")))
    if not components and _is_default(checkers):
        slot.category = "P"
        slot.cause = "unparseable_object"
        return
    if any(component.startswith("redexes(") for component in components):
        # A redex count changes when a rewrite inside an argument makes or unmakes a redex, so
        # the per-rule count checker cannot hold it. The bounded step search refutes or stays open.
        search_fn = _callable(checkers, "lex_tuple_refutation")
        result = search_fn(instance, components, _text(_get(raw, "proof_target"))) if search_fn else None
        slot.checker_id = "tgc.measure_tables.lex_tuple_refutation"
        if _verdict(result) == "REFUTED":
            slot.category = "F"
            slot.counterexample = _counterexample(result)
            return
        slot.category = "P"
        slot.cause = "checker_gap"
        return
    contract = _load_contract(checkers, instance)
    rules = tuple(getattr(contract, "rules", ()) or ())
    symbols = set(getattr(contract, "signature_symbols", set()) or set())
    payload = {"components": components or ["count(S)"], "order": "lexicographic"}
    claim = {
        "checker_input_schema_version": "tgc-checker-input/3.0.0",
        "mathematical_core": {"kind": "lex_tuple", "payload": {}},
        "representative_checker_object": {"kind": "lex_tuple", "payload": payload},
    }
    result = decide_fn(claim, rules, symbols)
    verdict = _verdict(result)
    if verdict == "PASS":
        if instance == "schema-a-new" and policy_version == "construction/1":
            slot.category = "I"
        else:
            slot.category = "E"
        return
    if verdict == "REFUTED":
        slot.category = "F"
        slot.counterexample = _counterexample(result)
        return
    slot.category = "P"
    slot.cause = "checker_gap"


def _categorize_measure(
    slot: SlotDecision,
    raw: dict[str, Any],
    *,
    test: str,
    instance: str,
    switches: dict[str, bool],
    checkers: Any,
    rule_ids: list[str],
    premises: dict[str, dict[str, Any]],
    recursive_call: Any,
    wrapper_inert: Any,
    marker_ignored: frozenset[str] = frozenset(),
) -> None:
    slot.checker_id = "tgc.measure_tables.measure_verdict"
    slot.rule_id = "MEASURE-CHECK"
    rule_ids.append("MEASURE-CHECK")
    quantity = _get(raw, "quantity")
    scope = _get(raw, "scope")
    aggregate = _get(raw, "aggregate")
    comparison_strength = _get(raw, "comparison_strength")
    comparison_quantifier = _get(raw, "comparison_quantifier")
    proof_target = _get(raw, "proof_target")
    for field_name, value in (
        ("quantity", quantity),
        ("scope", scope),
        ("aggregate", aggregate),
        ("comparison_strength", comparison_strength),
        ("comparison_quantifier", comparison_quantifier),
        ("proof_target", proof_target),
    ):
        if value is MISSING:
            slot.category = "P"
            slot.cause = f"missing_{field_name}"
            return
    if comparison_quantifier == "every_step" and test in {"schema_a", "test01"}:
        rule_ids.append("PER-STEP-QUANTIFIER")
    authority = measure_theorem_authority(instance, raw)
    if authority:
        rule_ids.append("MEASURE-THEOREM")
        slot.rule_id = "MEASURE-THEOREM"
        slot.checker_id = authority
        slot.category = "F"
        slot.cause = ""
        slot.counterexample = f"the family is refuted by {authority}"
        return
    decide_fn = _callable(checkers, "measure_verdict")
    refuted = False
    if decide_fn is None:
        slot.category = "P"
        slot.cause = "checker_gap"
    else:
        result = decide_fn(
            instance,
            _text(quantity),
            _text(scope),
            _text(aggregate),
            _text(comparison_strength),
            _text(comparison_quantifier),
            _text(proof_target),
        )
        verdict = _verdict(result)
        spread: dict[str, Any] = {}
        if verdict not in ("PASS", "REFUTED"):
            # a field the response never wrote leaves the single reading unsupported; the readings
            # it does permit still decide the slot when they agree (MEASURE-READINGS)
            spread = measure_reading_verdict(decide_fn, instance, raw)
            spread_verdict = str(spread.get("verdict") or "")
            if spread_verdict in ("PASS", "REFUTED", "AMBIGUOUS"):
                rule_ids.append("MEASURE-READINGS")
                slot.rule_id = "MEASURE-READINGS"
                verdict = spread_verdict
                result = spread
        if verdict == "PASS":
            slot.category = "I" if slot.external_route == "no" else "E"
            slot.cause = ""
        elif verdict == "REFUTED":
            slot.category = "F"
            slot.counterexample = _counterexample(result)
            slot.cause = ""
            refuted = True
        elif verdict == "AMBIGUOUS":
            slot.category = "P"
            slot.cause = "ambiguous_reading"
        else:
            slot.category = "P"
            # A reading the checker cannot support and a measure the reader never recorded are
            # two different problems with two different routes, and the register has to say
            # which. The spread returns too_many_readings exactly when so many fields are open
            # that their product passes the cap, which is what a slot with no quantity, scope or
            # aggregate looks like, so that one is a reading to be completed rather than a
            # theorem to be found.
            reason = str(spread.get("reason") or "")
            slot.cause = "measure_unrecorded" if reason == "too_many_readings" else "checker_gap"

    used_false = False
    truth_fn = _callable(checkers, "premise_truth") or inline_premise_truth
    for item, entry in sorted(premises.items()):
        if item in marker_ignored:
            continue
        if entry.get("status") == "asserted_used" and slot.slot_id in entry.get("used_by", []):
            payload = _truth_payload(truth_fn(instance, item))
            if _is_false_truth(payload):
                used_false = True
    w2_markers = (
        _nonempty(recursive_call)
        and _nonempty(wrapper_inert)
        and _text(scope) in W2_SCOPES
        and not used_false
        and not refuted
    )
    if w2_markers:
        rule_ids.append("W2-TRANSPORT")
        slot.rule_id = "W2-TRANSPORT"
        slot.checker_id = "w2_transport"
        if switches["w2_transport"]:
            slot.category = "I"
            slot.certificate_ref = W2_CERTIFICATE[instance]
            slot.cause = ""
        else:
            slot.category = "P"
            slot.cause = "authority_transport_withheld"
            slot.certificate_ref = ""


def _categorize_root_only(
    slot: SlotDecision,
    *,
    test: str,
    session: dict[str, Any],
    rule_ids: list[str],
) -> None:
    slot.rule_id = "ROOT-ONLY"
    rule_ids.append("ROOT-ONLY")
    role = _text(_get(session, "root_only_role"))
    if test == "test01":
        if role == "remark":
            slot.category = "X"
            slot.cause = ""
            return
        slot.category = "N"
        slot.cause = ""
        return
    slot.category = "N"
    slot.cause = ""


def _root_only_score(
    *,
    test: str,
    switches: dict[str, bool],
    checkers: Any,
    slots: list[SlotDecision],
    session: dict[str, Any],
    instance: str,
) -> str:
    if test != "test01" or not switches["root_only_literal_column"]:
        return ""
    has_root = any(
        slot.kind == "root_only_argument" or slot.proof_target == "root_only" for slot in slots
    )
    if not has_root and _text(_get(session, "root_only_role")) in {"", "none"}:
        return ""
    decide_fn = _callable(checkers, "root_only_decision")
    if decide_fn is None:
        return "Pending"
    claim = {
        "kind": "root_only_argument",
        "role": _text(_get(session, "root_only_role")),
        "quote": _text(_get(session, "root_only_quote")),
    }
    result = decide_fn(instance, claim)
    verdict = _verdict(result)
    if verdict == "PASS":
        return "Correct"
    if verdict == "REFUTED":
        return "Incorrect"
    return "Pending"


def _premise_exempt(item: Any, quote: Any) -> bool:
    """True when INV6 judged this exact quotation, under this catalog item, to state a true fact."""
    try:
        from premise_exemptions import is_exempt  # noqa: PLC0415
    except ImportError:
        try:
            from scoring.construction_reading.premise_exemptions import is_exempt  # noqa: PLC0415
        except ImportError:
            return False
    try:
        return bool(is_exempt(_text(item), _text(quote)))
    except Exception:
        return False


def _apply_premises(
    slots: list[SlotDecision],
    premises: dict[str, dict[str, Any]],
    *,
    instance: str,
    checkers: Any,
    switches: dict[str, bool],
    rule_ids: list[str],
    marker_conflicts: dict[str, frozenset[str]] | None = None,
) -> tuple[list[str], list[Any]]:
    truth_fn = _callable(checkers, "premise_truth") or inline_premise_truth
    exempt_fn = _premise_exempt
    extra_categories: list[str] = []
    asides: list[Any] = []
    by_id = {slot.slot_id: slot for slot in slots}
    conflicts = marker_conflicts or {}
    for item, entry in sorted(premises.items()):
        status = entry.get("status")
        if status == "asserted_used":
            if exempt_fn(item, entry.get("quote")):
                # the sentence filed here states something true about the rules, so the entry is a
                # transcription error and the catalog item was never asserted (PREMISE-EXEMPT)
                rule_ids.append("PREMISE-EXEMPT")
                for slot_id in entry.get("used_by", []):
                    slot = by_id.get(slot_id)
                    if slot is not None:
                        slot.premise_used.append(f"exempt_true_sentence:{item}")
                continue
            payload = _truth_payload(truth_fn(instance, item))
            if _is_false_truth(payload):
                rule_ids.append("PREMISE-USED")
                detail = payload.get("counterexample") or item
                restricted = item in PER_STEP_PREMISES
                for slot_id in entry.get("used_by", []):
                    slot = by_id.get(slot_id)
                    if slot is None or slot.category == "X":
                        continue
                    if item in conflicts.get(slot_id, ()):
                        # The quote repeats this slot's own descent or
                        # inertness sentence, so the entry is the true marker
                        # filed under a false catalog item.  The category
                        # stays the checker's and the slot names the item.
                        slot.premise_used.append(f"marker_conflict:{item}")
                        continue
                    if restricted and slot.kind in INTERPRETATION_KINDS:
                        # The per-step sentence is the interpretation's own
                        # decrease claim, which the interpretation checker
                        # verifies.  Record it on the slot and leave the
                        # category the checker assigned.  Under strict/1 the
                        # false_aside_defeats switch still puts F on the
                        # response.
                        slot.premise_used.append(item)
                        if switches["false_aside_defeats"]:
                            extra_categories.append("F")
                        continue
                    slot.category = "F"
                    slot.rule_id = "PREMISE-USED"
                    slot.counterexample = detail
                    slot.checker_id = "premise_truth"
        elif status == "asserted_aside":
            payload = _truth_payload(truth_fn(instance, item))
            if _is_false_truth(payload):
                rule_ids.append("FALSE-ASIDE")
                detail = payload.get("counterexample") or item
                asides.append(detail)
                for slot in slots:
                    if not slot.counterexample:
                        slot.counterexample = detail
                        break
                if switches["false_aside_defeats"]:
                    extra_categories.append("F")
    return extra_categories, asides


def _apply_negative_claim(
    session: dict[str, Any],
    *,
    instance: str,
    policy_version: str,
    rule_ids: list[str],
) -> list[str]:
    quote_value = _get(session, "retained_negative_claim_quote")
    if quote_value is MISSING:
        return []
    quote = _text(quote_value)
    if not quote.strip():
        return []
    rule_ids.append("NEGATIVE-CLAIM")
    if policy_version != "strict/1":
        return []
    family = _negative_certified_family(quote, instance)
    if family:
        return ["F"]
    return []


def _map_strict_score(value: str) -> str:
    if value == "Unknown":
        return "Pending"
    return value


def _construction_response(
    slots: list[SlotDecision],
    *,
    verdict: Any,
    switches: dict[str, bool],
    extra_f: bool,
) -> tuple[str, str, list[str]]:
    rules = ["RESPONSE-M", "RESPONSE-B"]
    # NEGATIVE-STANCE: a response whose final verdict is negative offers no proof, whatever
    # sentences its body contains.  Readers mined four such responses for a construction
    # sentence that was a local concession inside a No, for example "this rule decreases the
    # grape-height, so on its own it terminates" sitting inside "strong normalization cannot
    # be established".  Under a negative verdict every slot is read as an aside, so the
    # response aggregates on the verdict alone and a mined aside cannot carry M.
    negative = (
        verdict in NEGATIVE_ANSWER_VERDICTS and not switches["negative_verdict_credit"]
    )
    if negative:
        rules.append("NEGATIVE-STANCE")
        offered: list[SlotDecision] = []
        retained = [slot for slot in slots if slot.stance in RETAINED_STANCES]
    else:
        offered = [slot for slot in slots if slot.stance in OFFERED_STANCES]
        retained = [slot for slot in slots if slot.stance in RETAINED_STANCES]
    if extra_f or any(slot.category == "F" for slot in retained):
        math = "Incorrect"
    elif negative:
        math = "Incorrect"
    else:
        n_defeat = False
        for slot in retained:
            if slot.category != "N":
                continue
            if slot.rule_id == "ROOT-ONLY" and slot.stance in OFFERED_STANCES:
                n_defeat = True
            if slot.viable_external_name and switches["viable_name_defeats_m"]:
                n_defeat = True
        if n_defeat:
            math = "Incorrect"
        elif any(slot.category in {"I", "E"} for slot in offered):
            math = "Correct"
        elif any(slot.category == "P" for slot in offered):
            math = "Pending"
        else:
            math = "Incorrect"
    external_offered = any(
        (slot.external_route == "yes" or slot.viable_external_name)
        and slot.stance in OFFERED_STANCES
        for slot in slots
    )
    if external_offered:
        rules.append("BOUNDARY-HARD")
    if math != "Correct":
        if math == "Incorrect":
            boundary = "Incorrect"
        elif external_offered:
            # BOUNDARY-HARD: an offered external route removes admissibility whatever the
            # mathematics turns out to be, so an undecided M never masks it
            boundary = "Incorrect"
            rules.append("BOUNDARY-HARD")
        else:
            boundary = "Pending"
        return math, boundary, rules
    has_internal = any(slot.category == "I" and slot.stance in OFFERED_STANCES for slot in offered)
    offered_ok = all(slot.category in {"I", "X"} for slot in offered)
    any_external = any(
        slot.external_route == "yes" or slot.viable_external_name for slot in slots
    )
    boundary = "Correct" if has_internal and offered_ok and not any_external else "Incorrect"
    return math, boundary, rules


def _strict_response(
    slots: list[SlotDecision],
    *,
    verdict: Any,
    checkers: Any,
    extra_categories: list[str],
    switches: dict[str, bool],
    rule_ids: list[str],
) -> tuple[str, str]:
    decide_fn = _callable(checkers, "decide_strict_response")
    if decide_fn is None:
        return "Pending", "Pending"
    categories: list[str] = []
    for slot in slots:
        if slot.stance not in RETAINED_STANCES:
            continue
        if switches["root_only_literal_column"] and slot.rule_id == "ROOT-ONLY":
            continue
        categories.append(slot.category)
    if verdict == "no":
        categories.append("F")
        rule_ids.append("V02")
    elif verdict == "cannot_establish":
        rule_ids.append("V03")
    elif verdict == "conditional":
        categories.append("F")
    categories.extend(extra_categories)
    if not categories:
        categories = ["X"]
    result = decide_fn(
        categories,
        boundary_pending=False,
        source_identity_trusted=True,
        withdrawal_resolved=True,
    )
    math = _map_strict_score(result.mathematical_validity)
    boundary = _map_strict_score(result.boundary_compliance)
    rule_ids.append(result.rule)
    return math, boundary


def decide(
    record: dict[str, Any],
    *,
    test: str,
    policy_version: str,
    checkers: Any = None,
    **switch_overrides: Any,
) -> Decision:
    if test not in TESTS:
        raise ValueError(f"unsupported test: {test}")
    if policy_version not in POLICY_VERSIONS:
        raise ValueError(f"unsupported policy_version: {policy_version}")
    if not isinstance(record, dict):
        raise TypeError("record must be a dict")
    switches = resolve_switches(policy_version, switch_overrides)
    if checkers is None:
        checkers = DefaultCheckers()
    session = _session_map(record)
    session_slug = str(record.get("session_slug") or session.get("session_slug") or "")
    instance = resolve_instance(test, session_slug)
    rule_ids: list[str] = []
    premises = _premises(record, instance)
    record_slots = _record_slots(record)
    slot_rows = {slot_id: raw for slot_id, raw in record_slots}
    marker_conflicts = _slot_marker_conflicts(premises, slot_rows)
    slots = [
        _slot_decision(
            slot_id,
            raw,
            test=test,
            instance=instance,
            policy_version=policy_version,
            switches=switches,
            checkers=checkers,
            session=session,
            premises=premises,
            rule_ids=rule_ids,
            marker_ignored=marker_conflicts.get(slot_id, frozenset()),
        )
        for slot_id, raw in record_slots
    ]
    extra_categories, _asides = _apply_premises(
        slots,
        premises,
        instance=instance,
        checkers=checkers,
        switches=switches,
        rule_ids=rule_ids,
        marker_conflicts=marker_conflicts,
    )
    extra_categories.extend(
        _apply_negative_claim(
            session,
            instance=instance,
            policy_version=policy_version,
            rule_ids=rule_ids,
        )
    )

    verdict = _effective_verdict(session)
    pending_cause = ""
    record_status = _get(record, "record_status")
    if record_status is MISSING:
        record_status = _get(session, "record_status")
    unmapped = _unmapped(record, session)
    coverage_incomplete = (record_status != "complete") or bool(unmapped)

    if verdict is MISSING:
        termination = "Pending"
        pending_cause = "missing_final_verdict"
    else:
        rule_ids.append("VERDICT")
        termination = "Correct" if verdict == "yes" else "Incorrect"

    if policy_version == "construction/1":
        math, boundary, agg_rules = _construction_response(
            slots,
            verdict=verdict if verdict is not MISSING else "",
            switches=switches,
            extra_f="F" in extra_categories,
        )
        rule_ids.extend(agg_rules)
    else:
        math, boundary = _strict_response(
            slots,
            verdict=verdict if verdict is not MISSING else "",
            checkers=checkers,
            extra_categories=extra_categories,
            switches=switches,
            rule_ids=rule_ids,
        )
        rule_ids.extend(["RESPONSE-M", "RESPONSE-B"])

    if coverage_incomplete:
        termination = math = "Pending"
        pending_cause = "coverage_incomplete"
        rule_ids.append("COVERAGE")
        # an offered external route is recorded on the slots the reader did transcribe, so the
        # boundary rule stands even where a paragraph went unmapped (BOUNDARY-HARD)
        boundary = "Incorrect" if "BOUNDARY-HARD" in rule_ids else "Pending"

    if switches["collapse_pending_to_incorrect"]:
        if termination == "Pending":
            termination = "Incorrect"
        if math == "Pending":
            math = "Incorrect"
        if boundary == "Pending":
            boundary = "Incorrect"

    literal = _root_only_score(
        test=test,
        switches=switches,
        checkers=checkers,
        slots=slots,
        session=session,
        instance=instance,
    )
    if math == "Pending" and not pending_cause:
        pending_causes = [slot.cause for slot in slots if slot.category == "P" and slot.cause]
        pending_cause = pending_causes[0] if pending_causes else "checker_gap"

    unique_rules = list(dict.fromkeys(rule_ids))
    return Decision(
        policy_version=policy_version,
        test=test,
        session_slug=session_slug,
        instance=instance,
        T=termination,
        M=math,
        B=boundary,
        M_literal_root=literal,
        pending_cause=pending_cause,
        rule_ids=unique_rules,
        switches=switches,
        slots=slots,
    )


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if "--rules" in args:
        sys.stdout.write(rules_markdown())
        return 0
    sys.stderr.write("usage: python scoring/method_policy.py --rules\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
