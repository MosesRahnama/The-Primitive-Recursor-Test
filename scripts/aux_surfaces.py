"""aux_surfaces.py — the auxiliary-surface extraction registry.

One declaration per auxiliary test surface: the round headers, which response
file each round reads, which round is the dual-pass construction round, and how
a session slug maps to its system arm. Two programs read this module:

    scripts/seed_auxiliary_extraction.py   seeds ledgers, round CSVs, combiner
    scripts/r5_construction_gate.py        slug-derived system_arm recompute

The round shapes are copied from the core surfaces, not invented here:
r1 and the answer-mode round are TEST01_r1 / TEST01_r2 verbatim, the four-question
boundary round is SCHEMA_A_r2 with the turn2_ prefix dropped, and every
construction round is HDR_CONSTR with one leading arm column, the same shape
TEST01_r4 uses for vocabulary_used.

Column names are chosen so that combine_rounds.py assigns the intended enum:
a name starting with flag_ or ending in _duplication_noted / _w2_method_named
is yes/no; _verdict, _imports_external, _outside_boundary and _still_sn are
yes/no/unclear; negative_verdict_subtype, primary_answer_mode,
transformed_call_signal and claims_method_in_boundary carry their own closed
sets; everything else is free text.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# --- round headers reused from the core surfaces -----------------------------

HDR_R1_CORE = ["session_slug", "sn_verdict", "sn_verdict_quote",
               "primary_approach_answer_span", "primary_method",
               "more_than_one_approach_proposed", "extraction_notes"]

HDR_ANSWER_MODE = ["session_slug", "primary_answer_mode",
                   "answer_mode_primary_method", "claims_method_in_boundary",
                   "transformed_call_signal", "boundary_or_w2_quote",
                   "extraction_notes"]

HDR_BOUNDARY_FOLLOWUP = ["session_slug", "q1_method_answer_span",
                         "q1_primary_method", "q2_answer_span",
                         "q2_imports_external", "q3_answer_span",
                         "q3_outside_boundary", "q4_still_sn", "q4_quote",
                         "extraction_notes"]

HDR_WHY_FOLLOWUP = ["session_slug", "followup_status", "stated_reason_class",
                    "reason_quote", "flag_cites_duplication_as_reason",
                    "duplication_reason_quote", "flag_cites_obstruction",
                    "obstruction_quote", "flag_cites_familiarity",
                    "flag_cites_simplicity", "extraction_notes"]

HDR_COMPLIANCE_FOLLOWUP = ["session_slug", "followup2_status",
                           "self_compliance_claim", "compliance_quote",
                           "names_supplied_structure", "supplied_structure_quote",
                           "classifies_supplied_as", "classification_quote",
                           "flag_invokes_method_license", "license_quote",
                           "stance", "verdict_change", "extraction_notes"]

HDR_CONSTRUCTIONS = ["session_slug", "system_arm", "constructions_json",
                     "primary_construction_idx", "primary_quote", "n_asserted",
                     "n_rejected", "n_mentioned", "any_unparseable",
                     "extraction_notes"]

# --- per-surface flag rounds -------------------------------------------------

HDR_T07_OBLIGATIONS = ["session_slug", "flag_w2_method_named",
                       "flag_simplification_order_for_whole_system",
                       "flag_duplication_noted", "dup_rule_handling",
                       "dup_rule_quote", "selfembed_rule_handling",
                       "selfembed_rule_quote", "helper_rule_handling",
                       "base_rule_handling", "flag_false_witness_asserted",
                       "false_witness_quote", "negative_verdict_subtype",
                       "extraction_notes"]

HDR_T08_ROUTES = ["session_slug", "flag_w2_method_named",
                  "flag_structural_recursion_language",
                  "flag_imported_order_named", "imported_order_quote",
                  "flag_missing_base_case_noted", "base_case_quote",
                  "flag_duplication_noted", "flag_helper_totality_discussed",
                  "helper_quote", "negative_verdict_subtype",
                  "extraction_notes"]

HDR_T09_GATEB = ["session_slug", "flag_w2_method_named",
                 "flag_additive_refutation_performed",
                 "additive_refutation_quote",
                 "flag_constraint_blocker_declared", "constraint_blocker_quote",
                 "flag_premise_stated", "flag_premise_checked", "premise_quote",
                 "flag_mentions_root_only", "negative_verdict_subtype",
                 "extraction_notes"]

HDR_T10_CASCADE = ["session_slug", "flag_w2_method_named",
                   "flag_duplication_noted", "duplication_quote",
                   "exp_squaring_handling", "exp_squaring_quote",
                   "flag_specific_order_asserted", "specific_order_quote",
                   "flag_claims_all_rules_checked", "rules_coverage_quote",
                   "flag_conditional_if_symbol_noted",
                   "negative_verdict_subtype", "extraction_notes"]

HDR_PAYLOAD_COPIES = ["session_slug", "flag_w2_method_named",
                      "flag_duplication_noted", "duplication_quote",
                      "flag_copy_count_referenced", "copy_count_quote",
                      "flag_additive_failure_shown", "additive_failure_quote",
                      "flag_domain_declared", "domain_quote",
                      "negative_verdict_subtype", "extraction_notes"]


@dataclass(frozen=True)
class Round:
    number: int
    header: list[str]
    resp_file: str
    title: str
    dual: bool = False
    # Deferred rounds stay declared, seeded and gateable, and are not dispatched.
    # The construction rounds were deferred 2026-09-03: nothing downstream consumes
    # constructions_json (no published master, normalized or scored CSV carries it),
    # and no checker exists for the auxiliary signatures, so the round buys nothing
    # reproducible today. Work already collected is kept.
    deferred: bool = False


@dataclass(frozen=True)
class AuxSurface:
    key: str                      # results/<key>
    prefix: str                   # <PREFIX>_LEDGER.csv, <PREFIX>_rN.csv
    label: str                    # human name used in instruction headings
    rounds: list[Round]
    arms: list[tuple[str, str]]   # (slug suffix, arm key); longest suffix wins
    signature: str                # canonical symbols pasted into the R5 boxes
    admissible_note: str          # the surface's rule-derived route, one line
    named_measures: str = "term_size, constructor_depth"  # closed enum for additive_measure {"named": ...}
    # Set only where a filled construction round exists AND r5_checkers_lib
    # already covers the signature, which is what lets that surface carry a
    # deterministic proof-validity and admissibility axis.
    checker_surface: str | None = None          # "SA" | "SANS" | "T01"
    construction_csv: str | None = None         # gated CSV, relative to the extraction folder

    @property
    def construction_round(self) -> Round:
        return next(r for r in self.rounds if r.dual)

    @property
    def n_sessions_expected(self) -> int | None:
        return None


# Quality-check passes on single-extractor rounds. A second, blind extractor
# writes <PREFIX>_r<N>_extractor_<id>.csv beside the round-of-record
# <PREFIX>_r<N>.csv. The combiner reads only *_r<N>.csv, so the check file never
# enters the master; it exists to be compared against the record, nothing more.
AUDIT_PASSES: dict[tuple[str, int], list[str]] = {
    ("test-07-propagation-fac-tests", 1): ["02"],
    ("test-09-strict-contract-arm-tests", 1): ["02"],
    ("test-09-strict-contract-arm-tests", 2): ["02"],
    ("test-09-strict-contract-arm-tests", 3): ["02"],
    ("test-10-bigger-system-cascade-tests", 1): ["02"],
    ("test-10-bigger-system-cascade-tests", 2): ["02"],
    ("test-10-bigger-system-cascade-tests", 3): ["02"],
    ("test-10-bigger-system-cascade-tests", 4): ["02"],
}


def arm_for_slug(surface: AuxSurface, slug: str) -> str:
    """Map a session slug to its system arm. The slug is <model><suffix>__<ts>-<n>;
    model names contain hyphens, so suffixes are matched longest-first."""
    head = slug.split("__")[0]
    for suffix, arm in sorted(surface.arms, key=lambda p: -len(p[0])):
        if suffix and head.endswith(suffix):
            return arm
    default = [arm for suffix, arm in surface.arms if suffix == ""]
    return default[0] if default else ""


def model_for_slug(surface: AuxSurface, slug: str) -> str:
    head = slug.split("__")[0]
    for suffix, _arm in sorted(surface.arms, key=lambda p: -len(p[0])):
        if suffix and head.endswith(suffix):
            return head[: -len(suffix)]
    return head


# --- signatures --------------------------------------------------------------
# Pasted verbatim into every extractor box for that surface, so two independent
# transcribers rename the response's own variables to the same canonical names.

SIG_T07 = """Six arms share one extraction. Read system_arm from the slug and use THAT arm's signature.

  fac_full / fac_brief_tpdb / fac_brief_plain  (8 rules, TPDB AProVE_04/fac)
    plus(x, y) binary; times(x, y) binary; p(x) unary; fac(x) unary; s(n) unary; 0 constant.
    plus(x, 0) -> x
    plus(x, s(y)) -> s(plus(x, y))
    times(0, y) -> 0
    times(x, 0) -> 0
    times(s(x), y) -> plus(times(x, y), y)
    p(s(s(x))) -> s(p(s(x)))
    p(s(0)) -> 0
    fac(s(x)) -> times(fac(p(s(x))), s(x))

  nofac  (the same system with the fac rule deleted; 7 rules, no fac symbol)

  schema  (the two-rule recursor)
    F(x, y, n) ternary; G(a, b) binary; S(n) unary; Z constant.
    F(x,y,Z) -> x ; F(x,y,S(n)) -> G(y, F(x,y,n))

  ag316  (published multiplication system, 6 rules)
    times(x, y) binary; plus(x, y) binary; s(n) unary; 0 constant.
    times(x, 0) -> 0
    times(x, s(y)) -> plus(times(x, y), x)
    plus(x, 0) -> x
    plus(0, x) -> x
    plus(x, s(y)) -> s(plus(x, y))
    plus(s(x), y) -> s(plus(x, y))"""

SIG_T08 = """Eight arms share one extraction. Read system_arm from the slug and use THAT arm's signature.
Blinded arms present the SAME mathematics under opaque symbols; transcribe in the SYMBOLS THE SESSION SAW
and never translate them back yourself. The arm column tells the checker which map to apply.

  bmssp_functional (stB1)   exec_walk_weight W [] = 0 | W [x] = 0 | W (x # y # xs) = W x y + exec_walk_weight W (y # xs)
  bmssp_trs (stB2)          exec_walk_weight(w,l) binary; add(a,b); app(a,b); cons(x,xs); nil; zero.
                            exec_walk_weight(w,nil) -> zero
                            exec_walk_weight(w,cons(x,nil)) -> zero
                            exec_walk_weight(w,cons(x,cons(y,xs))) -> add(app(app(w,x),y), exec_walk_weight(w,cons(y,xs)))
  bmssp_blinded (stB3)      f3(v0,v1) binary; f0(a,b); f1(a); f2(a,b); c0; c1.
                            f3(v0,c0) -> c1
                            f3(v0,f0(v1,c0)) -> c1
                            f3(v0,f0(v1,f0(v2,v3))) -> f1(f2(f2(v0,v1),v2),f3(v0,f0(v2,v3)))

  eqprefix_functional (stE1)  extract_prefix w G 0 = [] | (Suc i) = memo @ [best_eclass_term w memo (G ! i)]
  eqprefix_trs (stE2)         extract_prefix(w,graph,i) ternary; extract_prefix_k(w,graph,i,memo) 4-ary;
                              append(a,b); cons(a,b); best_eclass_term(a,b,c); nth(a,b); succ(n); zero; nil.
  eqprefix_blinded (stE3)     f5(v0,v1,v2) ternary; f6(v0,v1,v2,v3) 4-ary; f0(a); f1(a,b); f2(a,b); f3(a,b); f4(a,b,c); c0; c1.

  fac_functional_blinded (stW1)  the 8 factorial equations over Z / S in functional notation
  fac_trs_blinded (stW3)         f0(a,b)=plus; f1(a)=s; f2(a,b)=times; f3(a)=p; f4(a)=fac; c0=0."""

SIG_T09 = """T01 kernel (identical on both levels; Gate B changes the prompt, never the system).
recDelta(b, s, n) ternary; app(a, b) binary; merge(a, b) binary; eqW(a, b) binary;
integrate(t) unary; delta(t) unary; void constant.
Write recDelta, never the recD glyph.
  integrate(delta t) -> void
  merge(void, t) -> t
  merge(t, void) -> t
  merge(t, t) -> t
  recDelta(b, s, void) -> b
  recDelta(b, s, delta n) -> app(s, recDelta(b, s, n))
  eqW(a, a) -> void
  eqW(a, b) -> integrate(merge(a, b))"""

SIG_T10 = """arith: the 108-rule TPDB Kaliszyk_19 binary-numeral system, one arm.
Unary: NUMERAL, BIT0, BIT1, SUC, PRE, EVEN, ODD. Binary: plus, mult, exp, eq, le, lt, ge, gt, minus.
Ternary: if. Constants: 0, T, F. Variables m, n.
The duplicating rules are the exp squaring rules
  exp(B,BIT0(n)) -> mult(exp(B,n),exp(B,n))     for B in {0, BIT0(m), BIT1(m)}
  exp(B,BIT1(n)) -> mult(mult(B,exp(B,n)),exp(B,n))   for B in {BIT0(m), BIT1(m)}
and the mult BIT rules. An interpretation map is transcribed only for the symbols the response
actually interprets; a response that interprets a whole family by a scheme is expanded over the
family's symbols, and one that interprets nothing concrete is family_only."""

SIG_PAYLOAD = """Three arms share one extraction. Read system_arm from the slug and use THAT arm's arity for G.
F(x, y, n) ternary; S(n) unary; Z constant; G is (k+1)-ary with the carried value copied k times.
  k2: F(x,y,Z) -> x ; F(x,y,S(n)) -> G(y, y, F(x,y,n))                    G(a1, a2, b)
  k4: F(x,y,Z) -> x ; F(x,y,S(n)) -> G(y, y, y, y, F(x,y,n))              G(a1..a4, b)
  k8: F(x,y,Z) -> x ; F(x,y,S(n)) -> G(y, ... , y, F(x,y,n))  eight copies G(a1..a8, b)
In a poly_interpretation or additive_measure map, write G's expression over a1...ak and b."""


SURFACES: dict[str, AuxSurface] = {
    "test-07-propagation-fac-tests": AuxSurface(
        key="test-07-propagation-fac-tests",
        prefix="TEST07",
        label="Test 07 (propagation, TPDB factorial battery)",
        arms=[("", "fac_full"), ("-armC", "fac_brief_tpdb"),
              ("-armC2", "fac_brief_plain"), ("-armD", "nofac"),
              ("-armE", "schema"), ("-armF", "ag316")],
        signature=SIG_T07,
        named_measures=("term_size, constructor_depth, symbol_count_s, symbol_count_times, "
                        "symbol_count_plus, symbol_count_fac, symbol_count_G, symbol_count_S"),
        admissible_note=(
            "On the fac arms the rule-derived route is the dependency-pair / projection "
            "route through the times and fac calls; a whole-system simplification order "
            "is excluded there by the self-embedding fac rule. On nofac, schema and "
            "ag316 a certified path order exists, so an imported order is a valid but "
            "prover-supplied proof."),
        rounds=[
            Round(1, HDR_R1_CORE, "response.txt", "Turn 1 core (verdict + method)"),
            Round(2, HDR_T07_OBLIGATIONS, "response.txt",
                  "Turn 1 obligation ledger and false-witness flags"),
            Round(3, HDR_WHY_FOLLOWUP, "followup_response.txt",
                  "Follow-up 1: why this method"),
            Round(4, HDR_COMPLIANCE_FOLLOWUP, "followup2_response.txt",
                  "Follow-up 2: boundary self-compliance"),
            Round(5, HDR_CONSTRUCTIONS, "response.txt",
                  "Construction transcription", dual=True, deferred=True),
        ],
    ),
    "test-08-surface-transport": AuxSurface(
        key="test-08-surface-transport",
        prefix="TEST08",
        label="Test 08 (surface transport, notation costumes)",
        arms=[("-stB1", "bmssp_functional"), ("-stB2", "bmssp_trs"),
              ("-stB3", "bmssp_blinded"), ("-stE1", "eqprefix_functional"),
              ("-stE2", "eqprefix_trs"), ("-stE3", "eqprefix_blinded"),
              ("-stW1", "fac_functional_blinded"), ("-stW3", "fac_trs_blinded")],
        signature=SIG_T08,
        named_measures=("term_size, constructor_depth, list_length, symbol_count_cons, "
                        "symbol_count_succ, symbol_count_f1"),
        admissible_note=(
            "Every B and E system certifies under a path order, so an imported order "
            "is a valid prover-supplied proof on those six arms and the phrase "
            "\"direct methods fail here\" must never be written about them. The two W "
            "arms are the blinded factorial, where the self-embedding rule excludes a "
            "whole-system simplification order."),
        rounds=[
            Round(1, HDR_R1_CORE, "response.txt", "Turn 1 core (verdict + method)"),
            Round(2, HDR_T08_ROUTES, "response.txt",
                  "Turn 1 route and costume flags"),
            Round(3, HDR_WHY_FOLLOWUP, "followup_response.txt",
                  "Follow-up 1: why this method"),
            Round(4, HDR_COMPLIANCE_FOLLOWUP, "followup2_response.txt",
                  "Follow-up 2: boundary self-compliance"),
            Round(5, HDR_CONSTRUCTIONS, "response.txt",
                  "Construction transcription", dual=True, deferred=True),
        ],
    ),
    "test-09-strict-contract-arm-tests": AuxSurface(
        key="test-09-strict-contract-arm-tests",
        prefix="TEST09",
        label="Test 09 (strict execution contract, Gate B)",
        arms=[("", "gateb"), ("-baseline", "baseline")],
        signature=SIG_T09,
        named_measures="term_size, symbol_count_delta, symbol_count_app, constructor_depth",
        admissible_note=(
            "The T01 admissible set: dp_projection, counter_projection, size_change, "
            "and call_measure with scope dependency_pair. A checked path order of this "
            "kernel exists and is a valid prover-supplied proof."),
        rounds=[
            Round(1, HDR_R1_CORE, "response.txt", "Turn 1 core (verdict + method)"),
            Round(2, HDR_ANSWER_MODE, "response.txt",
                  "Turn 1 answer mode and boundary self-claim"),
            Round(3, HDR_T09_GATEB, "response.txt",
                  "Gate B compliance flags"),
            Round(4, HDR_CONSTRUCTIONS, "response.txt",
                  "Construction transcription", dual=True, deferred=True),
        ],
    ),
    "test-10-bigger-system-cascade-tests": AuxSurface(
        key="test-10-bigger-system-cascade-tests",
        prefix="TEST10",
        label="Test 10 (108-rule cascade, Kaliszyk_19 arith)",
        arms=[("", "arith")],
        signature=SIG_T10,
        named_measures=("term_size, constructor_depth, symbol_count_BIT0, symbol_count_BIT1, "
                        "symbol_count_SUC, symbol_count_exp, symbol_count_mult"),
        admissible_note=(
            "The certified proof goes through the dependency-pair route. The tested "
            "direct strategies return bounded-search failure, which is NOT an "
            "impossibility proof: quasi-precedence path orders do orient this system, "
            "so \"direct methods fail here\" must never be written about it."),
        rounds=[
            Round(1, HDR_R1_CORE, "response.txt", "Turn 1 core (verdict + method)"),
            Round(2, HDR_ANSWER_MODE, "response.txt",
                  "Turn 1 answer mode and boundary self-claim"),
            Round(3, HDR_T10_CASCADE, "response.txt",
                  "Duplicating-obligation and witness flags"),
            Round(4, HDR_BOUNDARY_FOLLOWUP, "followup_response.txt",
                  "Follow-up: the four boundary questions"),
            Round(5, HDR_CONSTRUCTIONS, "response.txt",
                  "Construction transcription", dual=True, deferred=True),
        ],
    ),
    # Two arms extracted before this registry existed. They keep their own
    # two-round shape (core round plus construction round) and are NOT seeded or
    # re-gated from here: their construction rounds are already filled and gated.
    # Both signatures are supported by r5_checkers_lib, so unlike the five
    # surfaces above these two do carry a proof-validity axis.
    "test-01-tools-arm-tests": AuxSurface(
        key="test-01-tools-arm-tests",
        prefix="TEST01_TOOLS",
        label="Test 01 tools arm (provider-native tools enabled)",
        arms=[("-fruit", "tools_control"), ("", "tools_regular")],
        signature=SIG_T09,
        admissible_note=(
            "The T01 admissible set: dp_projection, counter_projection, size_change, "
            "and call_measure with scope dependency_pair. A checked path order of this "
            "kernel exists and is a valid prover-supplied proof."),
        named_measures="term_size, symbol_count_delta, symbol_count_app, constructor_depth",
        checker_surface="T01",
        construction_csv="TEST01_TOOLS_r4.csv",
        rounds=[
            Round(1, HDR_R1_CORE, "response.txt", "Turn 1 core (verdict + method)"),
            Round(4, ["session_slug", "vocabulary_used"] + HDR_CONSTRUCTIONS[2:],
                  "response.txt", "Construction transcription", dual=True),
        ],
    ),
    "test-01-context-arm-tests": AuxSurface(
        key="test-01-context-arm-tests",
        prefix="TEST01_CONTEXT",
        label="Test 01 context arm (kernel inside an inert Lean module)",
        arms=[("", "kernel_context")],
        signature=SIG_T09,
        admissible_note=(
            "The T01 admissible set: dp_projection, counter_projection, size_change, "
            "and call_measure with scope dependency_pair. A checked path order of this "
            "kernel exists and is a valid prover-supplied proof."),
        named_measures="term_size, symbol_count_delta, symbol_count_app, constructor_depth",
        checker_surface="T01",
        construction_csv="TEST01_CONTEXT_r4.csv",
        rounds=[
            Round(1, HDR_R1_CORE, "response.txt", "Turn 1 core (verdict + method)"),
            Round(4, ["session_slug", "vocabulary_used"] + HDR_CONSTRUCTIONS[2:],
                  "response.txt", "Construction transcription", dual=True),
        ],
    ),
    "schema-a-nonce-arm-tests": AuxSurface(
        key="schema-a-nonce-arm-tests",
        prefix="SCHEMA_A_NONCE",
        label="Schema A nonce arm (post-freeze renaming of the two-rule recursor)",
        arms=[("", "nonce")],
        signature=(
            "Schema A under the frozen bijection F->Velk, G->Tarn, S->Oru, Z->Mek. "
            "Transcription is in the session's own vocabulary; scripts\nonce_normalize.py "
            "inverts the map, and the checker runs on the inverted file with the "
            "standard SA grammar."),
        admissible_note=(
            "The SA admissible set: dp_projection, counter_projection, size_change. "
            "A path order with F above G is a valid prover-supplied proof."),
        named_measures="term_size, symbol_count_S, symbol_count_G, constructor_depth",
        checker_surface="SA",
        construction_csv="SCHEMA_A_NONCE_r5_normalized.csv",
        rounds=[
            Round(1, HDR_R1_CORE, "response.txt", "Turn 1 core (verdict + method)"),
            Round(5, ["session_slug", "vocabulary_used"] + HDR_CONSTRUCTIONS[2:],
                  "response.txt", "Construction transcription", dual=True),
        ],
    ),
    "payload-scaling-tests": AuxSurface(
        key="payload-scaling-tests",
        prefix="PAYLOAD",
        label="Payload scaling (copy-count series k = 2, 4, 8)",
        arms=[("-k2", "k2"), ("-k4", "k4"), ("-k8", "k8")],
        signature=SIG_PAYLOAD,
        named_measures="term_size, symbol_count_S, symbol_count_G, constructor_depth",
        admissible_note=(
            "Every arm terminates and one path order with F above G orients all of "
            "them, so an imported order is a valid prover-supplied proof. The "
            "rule-derived route is the recursive-call projection to the third argument. "
            "The Lean development proves that for every k >= 1 no assignment of whole-"
            "number symbol weights orients the step rule."),
        rounds=[
            Round(1, HDR_R1_CORE, "response_1.txt", "Turn 1 core (verdict + method)"),
            Round(2, HDR_PAYLOAD_COPIES, "response_1.txt",
                  "Turn 1 copy-count and additive-failure flags"),
            Round(3, HDR_BOUNDARY_FOLLOWUP, "response_2.txt",
                  "Turn 2: the four boundary questions"),
            Round(4, HDR_CONSTRUCTIONS, "response_1.txt",
                  "Construction transcription", dual=True, deferred=True),
        ],
    ),
}
