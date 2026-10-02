"""Layer 1: deterministic, replayable trace analysis (plan THINKING_TRACE_ANALYSIS_PLAN_2026-07-26.md).

Reads the two thinking-file inventories, computes every field it can by regex over
normalized text, and progressively writes one row per trace file.

Read-only outside the output folder. No scoring layer is modified.
"""
import csv, os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.normpath(os.path.join(HERE, "..", ".."))  # the benchmark results folder
REPO = os.path.dirname(BASE)  # inventory paths are relative to the repository root
OUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
INV_NEW = os.path.join(BASE, "final_scored_data", "thinking_files_inventory.csv")
INV_OLD = os.path.join(BASE, "final_scored_data", "thinking_files_inventory_ko7_corpus.csv")
SCORED = os.path.join(BASE, "final_scored_data")  # the 2026-07-27 run read the 2026-07-25 scoring; see README

SUITE_SCORED = {
    "schema-test-A-tests": "final_SCHEMA_A_consolidation.csv",
    "schema-test-A-new-system-tests": "final_SCHEMA_A_NEW_SYSTEM_consolidation.csv",
    "schema-test-B-tests": "final_SCHEMA_B_consolidation.csv",
    "schema-test-B-new-system-tests": "final_SCHEMA_B_NEW_SYSTEM_consolidation.csv",
    "test-01-kernel-tests": "final_TEST01_consolidation.csv",
    "test-02-completion-tests-nat-lex": "final_TEST02_consolidation.csv",
    "test-03-completion-tests-ordinal": "final_TEST03_consolidation.csv",
    "test-04-measure-verification-tests": "final_TEST04_consolidation.csv",
    "test-05-candidate-class-reasoning-tests": "final_TEST05_consolidation.csv",
    "test-06-branch-realism-tests": "final_TEST06_consolidation.csv",
}
# per-suite mapping onto a common scored view
SCORED_VIEW = {
    "test-01-kernel-tests": ("sn_verdict", "norm_primary_method_method_class",
                             "method_mathematical_validity", "method_correct_and_admissible",
                             "termination_correctness"),
    "schema-test-A-tests": ("turn1_sn_verdict", "turn1_norm_primary_method_method_class",
                            "turn1_method_mathematical_validity", "turn1_method_correct_and_admissible",
                            "turn1_termination_correctness"),
    # the control's rule-derived grade is the strict-policy column, the one final_scored_data/MANIFEST.csv counts
    "schema-test-A-new-system-tests": ("turn1_sn_verdict", "turn1_norm_primary_method_method_class",
                                       "turn1_method_mathematical_validity", "turn1_method_correct_and_admissible_strict_policy",
                                       "turn1_termination_correctness"),
    "schema-test-B-tests": ("", "", "", "", "all_five_methods_fully_correct"),
    "schema-test-B-new-system-tests": ("", "", "", "", "all_five_methods_fully_correct"),
    "test-02-completion-tests-nat-lex": ("completion_claim", "", "", "", "overall_test02_correctness"),
    "test-03-completion-tests-ordinal": ("", "", "", "", "overall_test03_correctness"),
    "test-04-measure-verification-tests": ("measure_sound_yes_no", "", "", "", "overall_test04_correctness"),
    "test-05-candidate-class-reasoning-tests": ("", "", "", "", "overall_test05_correctness"),
    "test-06-branch-realism-tests": ("strategy_sound_verdict", "", "", "", "overall_test06_correctness"),
}
OPEN_ENDED = {"schema-test-A-tests", "schema-test-A-new-system-tests", "test-01-kernel-tests"}
STUB_BYTES = 200

# ---------------------------------------------------------------- normalization
UNI_SPACE = dict.fromkeys(map(ord, "\u00a0\u2007\u202f\u2009\u200a\u2002\u2003\u2004\u2005\u2006\u2008"), " ")

def normalize(t):
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    return t.translate(UNI_SPACE)

def read_norm(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return normalize(fh.read())

def line_quote(text, start, end, maxlen=260):
    """Contiguous, newline-free substring of `text` covering [start,end)."""
    ls = text.rfind("\n", 0, start) + 1
    le = text.find("\n", end)
    if le == -1:
        le = len(text)
    if le - ls <= maxlen:
        return text[ls:le].strip()
    pad = (maxlen - (end - start)) // 2
    a = max(ls, start - max(pad, 0))
    b = min(le, a + maxlen)
    a = max(ls, b - maxlen)
    return text[a:b].strip()

# ---------------------------------------------------------------- lexicons
# Plan §3 starting set + logged extensions (see report §4).
# v2 (2026-07-26): "can be established"/"we can establish" REMOVED from V_YES and
# "no, it/the system/this" REMOVED from V_NO. Both were dominated by restatements of the
# prompt ("can strong normalization ... be established ...") and by discourse markers.
# Verified against the 60-trace Layer-2 sample; see report §4.
V_NO = re.compile(r"\b(?:does not terminate|do not terminate|not strongly normali[sz]ing|"
                  r"cannot be established|can not be established|cannot establish|cannot conclude|"
                  r"answer is no|non-?terminating|is not terminating|isn't terminating|"
                  r"fails to terminate|not SN\b|SN fails|"
                  r"there is an infinite|admits an infinite|infinite reduction sequence exists)", re.I)
V_YES = re.compile(r"\b(?:is strongly normali[sz]ing|is SN\b|SN holds|SN does hold|"
                   r"system terminates|it terminates|this terminates|does terminate|"
                   r"is terminating|termination holds|answer is yes|yes,? (?:strong normali|it|the system|this)|"
                   r"strong normali[sz]ation holds|"
                   r"every reduction sequence terminates|all reductions terminate)", re.I)
# Sentence-scoped guards (v2). A verdict match is rejected when its own sentence is a
# question, a restatement of the prompt, or a definition of the term.
RESTATE = re.compile(r"(?:from the presented|without importing|beyond what is derivable|"
                     r"the question|the problem asks|we are asked|asked to|we need to assess|"
                     r"we need to determine|asks if|asks whether|task is to|the user asks)", re.I)
DEFINITIONAL = re.compile(r"(?:means that|usually means|SN means|by definition|is defined as|"
                          r"definition of|normali[sz]ing if|terminating if|normali[sz]ation means)", re.I)
INTERROG_START = re.compile(r"^\s*(?:is|can|could|does|do|whether|why|how|what|are|would|should)\b", re.I)
# v2b: deliberative intent, not commitment. Dropping these costs recall but only ever moves
# a detected verdict LATER in the trace, i.e. against the verdict-first hypothesis.
DELIBERATIVE = re.compile(r"(?:check (?:if|whether)|consider (?:if|whether)|see (?:if|whether)|"
                          r"determine (?:if|whether)|verify (?:if|whether)|let me|let's|let us|"
                          r"we need to|i need to|try to|trying to|wonder|suppose|"
                          r"first,|next,|might be|could be|may be)", re.I)

W2_STRICT = re.compile(r"\b(?:dependency pairs?|\bDPs?\b|dependency-pair|subterm criterion|"
                       r"argument filtering|argument filter|size-?change|SCC decomposition|"
                       r"projection (?:to|onto|on) the (?:third|3rd)|proj(?:ection)? (?:pi|π)|"
                       r"simple projection|usable rules)\b")
W2_DESCENT = re.compile(r"(?:third argument (?:decreas|is smaller|gets smaller|shrink|reduc)|"
                        r"(?:S\(n\)|grape\(n\)|delta n|Δn) to n\b|"
                        r"counter decreas|measure on the third|"
                        r"recursive call[^.]{0,60}(?:smaller|decreas)|"
                        r"strict(?:ly)? subterm)", re.I)

FAMILIES = {
    "additive_size": re.compile(r"\b(?:size of the term|term size|total number of symbols|"
                                r"number of symbols|symbol count|additive measure|"
                                r"\|t\||weight function|weight of)", re.I),
    "path_order": re.compile(r"\b(?:LPO|RPO|MPO\b|lexicographic path order|recursive path order|"
                             r"path order(?:ing)?|precedence)\b", re.I),
    "kbo": re.compile(r"\b(?:KBO|knuth-?bendix)\b", re.I),
    "polynomial": re.compile(r"\b(?:polynomial interpretation|poly(?:nomial)? interpret|"
                             r"interpretation over the natural|monotone algebra|"
                             r"assign(?:ing)? to each (?:symbol|function))", re.I),
    "structural_descent": re.compile(r"\b(?:structural induction|induction on (?:the )?(?:n|the third|the counter)|"
                                     r"well-?founded (?:induction|order) on)", re.I),
    "transformed_calls": W2_STRICT,
    "multiset": re.compile(r"\bmultiset (?:order|extension|comparison)", re.I),
    "semantic_labelling": re.compile(r"\bsemantic label", re.I),
}
APPLY_CUE = re.compile(r"\b(?:let(?:'s| us)? (?:define|try|take|set)|define|we define|assign|"
                       r"we set|set f|interpret|consider the|apply|applying|we try|try(?:ing)? "
                       r"(?:an?|the)|take (?:the|as)|orient|show(?:ing)? that|"
                       r"construct|build|using (?:an?|the)|with (?:the )?precedence)", re.I)

DUP = re.compile(r"(?:duplicat\w*|two copies|copies of|appears twice|occurs twice|"
                 r"two occurrences|twice on the right|appears again|duplication)", re.I)
DUP_CTX = re.compile(r"\b(?:y\b|s\b|argument|variable|occurrence|right-?hand|RHS|payload)", re.I)

SIDE = re.compile(r"\b(?:LHS|RHS|left-?hand side|right-?hand side|left side|right side|"
                  r"left of the arrow|right of the arrow)\b", re.I)
CMP = re.compile(r"\b(?:bigger|larger|smaller|greater|less than|more symbols|fewer|"
                 r"decreas\w*|increas\w*|grows|grew|same size|equal size|"
                 r"does not decreas|doesn't decreas|fails to decreas)\b|[<>]=?|[≤≥]", re.I)
# v2: the check must be about MAGNITUDE, not about pattern matching or symbol roles.
MEASURE_WORD = re.compile(r"\b(?:size|sizes|weight|measure|interpretation|value|val|"
                          r"\|[a-z]\||count|number of|depth|height|mu\b|kappa\b|"
                          r"decreas\w*|increas\w*|larger|smaller|bigger|greater|orient)\b", re.I)
NONCHECK_CTX = re.compile(r"\b(?:match(?:es|ed|ing)?|pattern|root symbol|appears? on|appears? only|"
                          r"defined symbol|constructor|arity|no rules? for)\b", re.I)

HEDGE = re.compile(r"\b(?:not sure|i think|probably|might|unclear|uncertain|i'm not certain|"
                   r"seems|risky|perhaps|maybe|possibly|not entirely|hard to say|"
                   r"i believe|arguably|presumably|somewhat)\b", re.I)
REVERSAL = re.compile(r"\b(?:wait|actually|hmm+|that's wrong|that is wrong|let me reconsider|"
                      r"on second thought|but wait|hold on|scratch that|i was wrong|"
                      r"no,? that|let me redo|rethink)\b", re.I)
TURNAWAY = re.compile(r"\b(?:but|however|though|although|instead|rather than|"
                      r"too complicated|overkill|complicated|simpler|simplest|"
                      r"don'?t need|do not need|not necessary|unnecessary|"
                      r"imports?|external|beyond (?:the|what)|outside the|heavy|"
                      r"overly|no need)\b", re.I)

# ---------------------------------------------------------------- helpers
SENT_BOUND = re.compile(r"[.!?\n]")


def sentence_of(text, pos):
    a = 0
    for m in SENT_BOUND.finditer(text, 0, pos):
        a = m.end()
    m = SENT_BOUND.search(text, pos)
    b = m.end() if m else len(text)
    return text[a:b]


def verdict_events(text):
    """Ordered [(pos, 'no'|'yes', quote)]; NO wins overlaps; sentence-scoped guards (v2)."""
    no_spans = [(m.start(), m.end()) for m in V_NO.finditer(text)]
    ev = [(m.start(), m.end(), "no") for m in V_NO.finditer(text)]
    for m in V_YES.finditer(text):
        if any(a <= m.start() < b for a, b in no_spans):
            continue
        ev.append((m.start(), m.end(), "yes"))
    out = []
    for s, e, cls in sorted(ev):
        sent = sentence_of(text, s)
        if "?" in sent or RESTATE.search(sent) or DEFINITIONAL.search(sent) \
                or INTERROG_START.search(sent) or DELIBERATIVE.search(sent):
            continue
        out.append((s, cls, line_quote(text, s, e)))
    return out

def family_events(text):
    """Ordered [(pos, family, quote)] for families with an application cue nearby."""
    ev = []
    for fam, rx in FAMILIES.items():
        for m in rx.finditer(text):
            w0, w1 = max(0, m.start() - 170), min(len(text), m.end() + 170)
            if APPLY_CUE.search(text[w0:w1]):
                ev.append((m.start(), fam, line_quote(text, m.start(), m.end())))
    return sorted(ev)

def first_match(rx, text, guard=None):
    for m in rx.finditer(text):
        if guard and not guard(m):
            continue
        return m
    return None

def ran_check(text):
    """LHS/RHS MAGNITUDE comparison (v2): side reference + comparison + measure word,
    excluding sentences that are about pattern matching or symbol roles."""
    for m in SIDE.finditer(text):
        w0, w1 = max(0, m.start() - 150), min(len(text), m.end() + 150)
        win = text[w0:w1]
        if not (CMP.search(win) and MEASURE_WORD.search(win)):
            continue
        if NONCHECK_CTX.search(sentence_of(text, m.start())):
            continue
        return m.start(), line_quote(text, m.start(), m.end())
    # variant: an explicit measure-grows statement about the recursive rule
    rx = re.compile(r"(?:the (?:size|weight|measure|term)[^.\n]{0,80}"
                    r"(?:increas\w*|grows|is (?:bigger|larger)|does not decreas|doesn'?t decreas))", re.I)
    for m in rx.finditer(text):
        if NONCHECK_CTX.search(sentence_of(text, m.start())):
            continue
        return m.start(), line_quote(text, m.start(), m.end())
    return None, ""

def dup_noticed(text):
    for m in DUP.finditer(text):
        w0, w1 = max(0, m.start() - 130), min(len(text), m.end() + 130)
        if DUP_CTX.search(text[w0:w1]):
            return m.start(), line_quote(text, m.start(), m.end())
    return None, ""

# ---------------------------------------------------------------- load scored
scored = {}
for suite, fname in SUITE_SCORED.items():
    p = os.path.join(SCORED, fname)
    rows = {}
    with open(p, "r", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[r["session_slug"]] = r
    scored[suite] = rows

# Submitted-corpus ([sub]) adjudicated scoring for the old-corpus traces. Verified against the
# published anchors: TEST01 324 rows / 3 admissible, SCHEMA_A 108 rows / 2 admissible.
OLD_SCORED_DIR = ""  # the submitted-era corpus is outside this repository
OLD_SUITE_SCORED = dict(SUITE_SCORED)
OLD_SUITE_SCORED["schema-test-B-tests"] = "final_SCHEMA_B_consolidation.normalized.csv"
scored_old = {}
for suite, fname in OLD_SUITE_SCORED.items():
    p = os.path.join(OLD_SCORED_DIR, fname)
    if not os.path.exists(p):
        continue
    rows = {}
    with open(p, "r", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if "session_slug" in r:
                rows[r["session_slug"]] = r
    scored_old[suite] = rows

FIELDS = ["source", "corpus", "test_suite", "session_folder", "turn", "model_family", "arm",
          "joined_slug", "join_ok", "trace_chars", "excluded_stub",
          "first_verdict_pos", "first_verdict_frac", "first_verdict_quote", "first_verdict_class",
          "first_construction_pos", "first_construction_frac", "first_construction_quote",
          "first_construction_family", "verdict_lead", "verdict_lead_frac", "verdict_reversals",
          "reversal_marker_count", "reversal_quotes",
          "w2_mentioned", "w2_first_pos", "w2_first_frac", "w2_quote", "w2_descent_only",
          "w2_applied", "w2_delivered", "discarded", "discard_reason_quote", "discard_category",
          "final_method_family_trace", "ran_check", "check_pos_frac", "check_quote", "post_check_behavior",
          "duplication_noticed", "duplication_quote", "duplication_consequence",
          "n_method_families_tried", "method_sequence", "abandoned_count",
          "hedge_count_trace", "hedge_count_response", "response_chars",
          "hedge_rate_trace_per_kchar", "hedge_rate_response_per_kchar",
          "divergence_flag", "rate_divergence_flag", "divergence_quotes",
          "scored_verdict", "scored_method_class", "scored_math_validity", "scored_admissible",
          "scored_overall_correct",
          "layer2_override", "notes"]


def response_path(session_path, turn):
    cands = {"1": ["response_1.txt", "response.txt"],
             "2": ["response_2.txt"],
             "single": ["response.txt", "response_1.txt"]}[turn]
    for c in cands:
        p = os.path.join(session_path, c)
        if os.path.exists(p):
            return p
    return None


def process(inv_path, corpus, writer, fh, stats):
    with open(inv_path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        path = os.path.join(REPO, r["full_path"])
        suite = r["test_suite"]
        folder = r["session_folder"]
        fname = r["file_name"]
        turn = "1" if fname == "thinking_1.txt" else ("2" if fname == "thinking_2.txt" else "single")
        raw_model = folder.split("__")[0]
        arm = "fruit" if raw_model.endswith("-fruit") else ("control" if raw_model.endswith("-control") else "main")
        family = re.sub(r"-(fruit|control)$", "", raw_model)

        out = {k: "" for k in FIELDS}
        out.update(source=os.path.basename(inv_path), corpus=corpus, test_suite=suite,
                   session_folder=folder, turn=turn, model_family=family, arm=arm,
                   joined_slug=folder, layer2_override="")

        book = scored_old if corpus == "old" else scored
        srow = book.get(suite, {}).get(folder)
        out["join_ok"] = "yes" if srow else "no"
        if srow:
            v, mc, mv, ad, oc = SCORED_VIEW.get(suite, ("", "", "", "", ""))
            out["scored_verdict"] = srow.get(v, "") if v else ""
            out["scored_method_class"] = srow.get(mc, "") if mc else ""
            out["scored_math_validity"] = srow.get(mv, "") if mv else ""
            out["scored_admissible"] = srow.get(ad, "") if ad else ""
            out["scored_overall_correct"] = srow.get(oc, "") if oc else ""

        try:
            text = read_norm(path)
        except Exception as exc:
            out["notes"] = f"unreadable: {exc}"
            out["excluded_stub"] = "yes"
            stats["unreadable"] += 1
            writer.writerow(out); fh.flush()
            continue

        out["trace_chars"] = len(text)
        if len(text) < STUB_BYTES:
            out["excluded_stub"] = "yes"
            out["notes"] = "stub"
            stats["stub"] += 1
            writer.writerow(out); fh.flush()
            continue
        out["excluded_stub"] = "no"
        L = len(text)

        # ---- A1 verdict lead
        ve = verdict_events(text)
        if ve:
            p, cls, q = ve[0]
            out["first_verdict_pos"] = p
            out["first_verdict_frac"] = round(p / L, 4)
            out["first_verdict_class"] = cls
            out["first_verdict_quote"] = q
            rev, prev = 0, None
            for _, c, _q in ve:
                if prev and c != prev:
                    rev += 1
                prev = c
            out["verdict_reversals"] = rev
        fe = family_events(text)
        if fe:
            p, fam, q = fe[0]
            out["first_construction_pos"] = p
            out["first_construction_frac"] = round(p / L, 4)
            out["first_construction_quote"] = q
            out["first_construction_family"] = fam
        if ve and fe:
            lead = fe[0][0] - ve[0][0]
            out["verdict_lead"] = lead
            out["verdict_lead_frac"] = round(lead / L, 4)
        rm = list(REVERSAL.finditer(text))
        out["reversal_marker_count"] = len(rm)
        out["reversal_quotes"] = " || ".join(line_quote(text, m.start(), m.end()) for m in rm[:3])

        # ---- A5 churn
        seq, seen = [], []
        for p, fam, _q in fe:
            if not seq or seq[-1] != fam:
                seq.append(fam)
            if fam not in seen:
                seen.append(fam)
        out["method_sequence"] = ">".join(seq)
        out["n_method_families_tried"] = len(seen)
        out["final_method_family_trace"] = seq[-1] if seq else ""
        out["abandoned_count"] = max(0, len(seen) - 1) if seq else 0

        # ---- A2 considered-and-discarded (open-ended surfaces)
        if suite in OPEN_ENDED:
            m = W2_STRICT.search(text)
            out["w2_mentioned"] = "yes" if m else "no"
            md = W2_DESCENT.search(text)
            out["w2_descent_only"] = "yes" if (md and not m) else "no"
            if m:
                out["w2_first_pos"] = m.start()
                out["w2_first_frac"] = round(m.start() / L, 4)
                out["w2_quote"] = line_quote(text, m.start(), m.end())
                w0, w1 = max(0, m.start() - 170), min(L, m.end() + 170)
                out["w2_applied"] = "yes" if APPLY_CUE.search(text[w0:w1]) else "no"
                if not srow:
                    # no join (old corpus): delivery is unknowable, so assert nothing.
                    out["w2_delivered"] = ""
                    out["discarded"] = ""
                    out["discard_category"] = "no_join_delivery_unknown"
                else:
                    delivered = out["scored_admissible"] == "Correct"
                    out["w2_delivered"] = "yes" if delivered else "no"
                    out["discarded"] = "no" if delivered else "yes"
                    if not delivered:
                        seg = text[m.end():min(L, m.end() + 1400)]
                        t = TURNAWAY.search(seg)
                        if t:
                            gp = m.end() + t.start()
                            out["discard_reason_quote"] = line_quote(text, gp, gp + len(t.group()))
                        out["discard_category"] = "needs_read"
            elif srow:
                out["w2_applied"] = "no"
                out["w2_delivered"] = "yes" if out["scored_admissible"] == "Correct" else "no"
                out["discarded"] = "no"
            else:
                out["w2_applied"] = "no"

        # ---- A3 one-line check
        cp, cq = ran_check(text)
        out["ran_check"] = "yes" if cp is not None else "no"
        if cp is not None:
            out["check_pos_frac"] = round(cp / L, 4)
            out["check_quote"] = cq
            after_fams = [f for p, f, _ in fe if p > cp]
            before_fams = [f for p, f, _ in fe if p <= cp]
            after_verdicts = [c for p, c, _ in ve if p > cp]
            if after_fams and before_fams and after_fams[0] != before_fams[-1]:
                out["post_check_behavior"] = "switched_method"
            elif after_verdicts and out["first_verdict_class"] and after_verdicts[-1] != out["first_verdict_class"]:
                out["post_check_behavior"] = "flipped_verdict"
            elif HEDGE.search(text[cp:min(L, cp + 900)]):
                out["post_check_behavior"] = "hedged"
            else:
                out["post_check_behavior"] = "kept_method_anyway"

        # ---- A4 duplication
        dp, dq = dup_noticed(text)
        out["duplication_noticed"] = "yes" if dp is not None else "no"
        if dp is not None:
            out["duplication_quote"] = dq
            after_fams = [f for p, f, _ in fe if p > dp]
            before_fams = [f for p, f, _ in fe if p <= dp]
            later_no = [c for p, c, _ in ve if p > dp and c == "no"]
            w2_after = W2_STRICT.search(text, dp)
            if later_no:
                out["duplication_consequence"] = "became_objection"
            elif after_fams and before_fams and after_fams[0] != before_fams[-1]:
                out["duplication_consequence"] = "drove_method_switch"
            elif w2_after:
                out["duplication_consequence"] = "handled_correctly"
            else:
                out["duplication_consequence"] = "ignored"

        # ---- A6 hedge divergence
        ht = len(HEDGE.findall(text))
        out["hedge_count_trace"] = ht
        out["hedge_rate_trace_per_kchar"] = round(1000.0 * ht / L, 3)
        rp = response_path(os.path.join(REPO, r["session_path"]), turn)
        if rp:
            try:
                rtext = read_norm(rp)
                hr = len(HEDGE.findall(rtext))
                out["hedge_count_response"] = hr
                out["response_chars"] = len(rtext)
                rrate = (1000.0 * hr / len(rtext)) if len(rtext) else 0.0
                out["hedge_rate_response_per_kchar"] = round(rrate, 3)
                trate = 1000.0 * ht / L
                # absolute definition (plan §A6) and the length-normalized one
                out["divergence_flag"] = "yes" if (ht >= 3 and hr == 0) else "no"
                out["rate_divergence_flag"] = "yes" if (trate > 0 and rrate == 0) else "no"
                if out["divergence_flag"] == "yes":
                    hm = list(HEDGE.finditer(text))[:2]
                    out["divergence_quotes"] = " || ".join(line_quote(text, x.start(), x.end()) for x in hm)
            except Exception as exc:
                out["notes"] = (out["notes"] + f"; response unreadable: {exc}").strip("; ")
        else:
            out["notes"] = (out["notes"] + "; no response file").strip("; ")

        writer.writerow(out); fh.flush()
        stats["written"] += 1


def main():
    os.makedirs(OUT, exist_ok=True)
    target = os.path.join(OUT, "thinking_trace_analysis.csv")
    stats = {"written": 0, "stub": 0, "unreadable": 0}
    with open(target, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        process(INV_NEW, "new", w, fh, stats)
        # the submitted-era traces listed in INV_OLD are outside this repository and are skipped
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
