"""Test 08 surface transport: the same mathematics in three costumes, plus the blinded factorial."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from _lib import *  # noqa: E402,F401,F403

TEST = "test-08-surface-transport"
ARMS = ["bmssp_functional", "bmssp_trs", "bmssp_blinded", "eqprefix_functional", "eqprefix_trs", "eqprefix_blinded", "fac_functional_blinded", "fac_trs_blinded"]
ARM_DESC = {"bmssp_functional": "BMSSP walk-weight, source functional equations (n=10)", "bmssp_trs": "same, first-order TRS (n=10)",
            "bmssp_blinded": "same TRS, symbols blinded (n=10)", "eqprefix_functional": "extract_prefix, source equations with let (n=10)",
            "eqprefix_trs": "same, let-lifted TRS (n=10)", "eqprefix_blinded": "same TRS, symbols blinded (n=10)",
            "fac_functional_blinded": "TPDB factorial, functional equations, names kept (W1, n=40)", "fac_trs_blinded": "TPDB factorial, TRS, symbols blinded (W3, n=40)"}
FIVE = ["Claude Sonnet 5", "DeepSeek V4 Pro", "Gemini 3.1 Pro Preview", "GPT-5.6 Sol", "Grok 4.5"]


def run():
    df = add_families(load("TEST08"))
    rows, md = [], []
    md += ["# Test 08: surface transport (notation costumes)", "",
           "Source `final_TEST08_consolidation.csv`: 140 sessions, 5 models, three turns each. Every system terminates (TTT2 with CeTA replay); "
           "the B and E systems certify under a path order alone, so an imported order is a valid LLM-supplied proof there. The two W arms are the "
           "TPDB factorial, where the self-embedding rule excludes any whole-system simplification order, shown as functional equations (names kept) "
           "and as a blinded TRS. No proof-validity axis on this surface.", "",
           md_table(["arm", "what the model saw"], [[a, ARM_DESC[a]] for a in ARMS]), ""]

    md += ["## 1. Verdict and route by arm", ""]
    tab = []
    for arm in ARMS:
        d = df[df.system_arm == arm]; n = len(d)
        v = int((d.termination_verdict_correctness == "Correct").sum())
        tab.append([arm, cell(v, n, ci=False), ", ".join(f"{a}={b}" for a, b in d[d.termination_verdict_correctness != "Correct"].negative_verdict_subtype.value_counts().items()) or "none"])
        rows.append(rate_row(TEST, "verdict", arm, "all", "termination verdict correct", v, n))
    md += [md_table(["arm", "correct verdict", "wrong-verdict subtypes"], tab), "",
           dist_table(df, "system_arm", "family", order=FAMILY_ORDER + ["none", "other"], arm_order=ARMS), ""]
    for arm in ARMS:
        d = df[df.system_arm == arm]
        for fam in FAMILY_ORDER + ["none", "other"]:
            rows.append(rate_row(TEST, "route", arm, "all", f"primary family {fam}", int((d.family == fam).sum()), len(d)))

    md += ["## 2. Route and costume flags by arm", ""]
    flags = {"recursive-call abstraction named": "flag_w2_method_named", "argues by structural recursion on an argument": "flag_structural_recursion_language",
             "imported order or interpretation named": "flag_imported_order_named", "missing base case noted": "flag_missing_base_case_noted",
             "duplication noted": "flag_duplication_noted", "helper totality discussed": "flag_helper_totality_discussed"}
    tab = []
    for arm in ARMS:
        d = df[df.system_arm == arm]; n = len(d)
        vals = [int((d[c] == "yes").sum()) for c in flags.values()]
        tab.append([arm] + [cell(v, n, ci=False) for v in vals])
        for (k, _), v in zip(flags.items(), vals):
            rows.append(rate_row(TEST, "flags", arm, "all", k, v, n))
    md += [md_table(["arm"] + list(flags), tab), ""]

    md += ["## 3. Costume trend inside the B and E systems (functional -> TRS -> blinded)", ""]
    tab = []
    for sysname in ["bmssp", "eqprefix"]:
        f_, t_, b_ = (df[df.system_arm == f"{sysname}_{c}"] for c in ["functional", "trs", "blinded"])
        for metric, fn in [("structural-recursion language", lambda d: d.flag_structural_recursion_language == "yes"),
                           ("imported order named", lambda d: d.flag_imported_order_named == "yes"),
                           ("path order primary", lambda d: d.family == "path_order"),
                           ("structural primary", lambda d: d.family == "structural")]:
            kf, kt, kb = int(fn(f_).sum()), int(fn(t_).sum()), int(fn(b_).sum())
            p = fisher(kf, len(f_) - kf, kb, len(b_) - kb)
            tab.append([sysname, metric, f"{kf}/{len(f_)}", f"{kt}/{len(t_)}", f"{kb}/{len(b_)}", f"{p:.3f}"])
            rows.append(value_row(TEST, "costume trend", sysname, "all", f"{metric}: functional/trs/blinded", f"{kf}/{len(f_)}, {kt}/{len(t_)}, {kb}/{len(b_)}", f"Fisher functional vs blinded p={p:.3f}"))
    md += [md_table(["system", "metric", "functional", "TRS", "blinded", "Fisher p (functional vs blinded)"], tab), ""]

    md += ["## 4. The blinded factorial (W arms) against the named factorial (Test 07 fac_full, same five models, same full wording)", ""]
    t7 = add_families(load("TEST07"))
    named = t7[(t7.system_arm == "fac_full") & t7.model.isin(FIVE)]
    tab = []
    for label, d in [("Test 07 fac_full (names, TRS)", named), ("W1 functional (names kept)", df[df.system_arm == "fac_functional_blinded"]), ("W3 TRS blinded", df[df.system_arm == "fac_trs_blinded"])]:
        n = len(d)
        tab.append([label, n, cell(int((d.termination_verdict_correctness == "Correct").sum()), n, ci=False),
                    cell(int((d.family == "dependency_pairs").sum()), n, ci=False), cell(int((d.flag_w2_method_named == "yes").sum()), n, ci=False),
                    cell(int((d.family == "path_order").sum()), n, ci=False), cell(int((d.flag_duplication_noted == "yes").sum()), n, ci=False)])
        rows += [rate_row(TEST, "blinded factorial", label, "5 models", "dependency pairs primary", int((d.family == "dependency_pairs").sum()), n),
                 rate_row(TEST, "blinded factorial", label, "5 models", "recursive-call abstraction named", int((d.flag_w2_method_named == "yes").sum()), n),
                 rate_row(TEST, "blinded factorial", label, "5 models", "path order primary", int((d.family == "path_order").sum()), n)]
    md += [md_table(["surface", "n", "correct verdict", "DP primary", "recursive-call abstraction named", "path order primary", "duplication noted"], tab), ""]
    w3 = df[df.system_arm == "fac_trs_blinded"]
    c = paired_contrast(w3.family == "dependency_pairs", w3.model, named.family == "dependency_pairs", named.model)
    md += [f"Paired DP-primary difference, blinded TRS minus named TRS: {100*c['diff']:+.1f} pp, model-cluster 95% [{100*c['ci_low']:+.1f}, {100*c['ci_high']:+.1f}], sign-flip p = {c['p_signflip']:.3f}.", ""]
    rows.append(value_row(TEST, "blinded factorial", "W3 minus fac_full", "paired 5 models", "DP primary difference pp", round(100 * c["diff"], 1), f"CI [{100*c['ci_low']:.1f}, {100*c['ci_high']:.1f}] p={c['p_signflip']:.3f}"))
    w1 = df[df.system_arm == "fac_functional_blinded"]
    c2 = paired_contrast(w1.family == "dependency_pairs", w1.model, w3.family == "dependency_pairs", w3.model)
    md += [f"Paired DP-primary difference, functional (names) minus blinded TRS: {100*c2['diff']:+.1f} pp [{100*c2['ci_low']:+.1f}, {100*c2['ci_high']:+.1f}], p = {c2['p_signflip']:.3f}. "
           f"Missing base case noted: W1 {int((w1.flag_missing_base_case_noted == 'yes').sum())}/{len(w1)}, W3 {int((w3.flag_missing_base_case_noted == 'yes').sum())}/{len(w3)}.", ""]
    rows.append(value_row(TEST, "blinded factorial", "W1 minus W3", "paired 5 models", "DP primary difference pp", round(100 * c2["diff"], 1), f"CI [{100*c2['ci_low']:.1f}, {100*c2['ci_high']:.1f}] p={c2['p_signflip']:.3f}"))

    md += ["## 5. Follow-ups by arm", "", dist_table(df, "system_arm", "stated_reason_class", arm_order=ARMS), "",
           dist_table(df, "system_arm", "self_compliance_claim", order=["complied", "partly", "did_not_comply"], arm_order=ARMS), "",
           dist_table(df, "system_arm", "stance", order=["maintains", "concedes", "hedges", "reverses"], arm_order=ARMS), ""]
    for arm in ARMS:
        d = df[df.system_arm == arm]; n = len(d)
        for k, v in {"cites an obstruction": (d.flag_cites_obstruction == "yes").sum(), "cites familiarity": (d.flag_cites_familiarity == "yes").sum(),
                     "self-compliance claim: complied": (d.self_compliance_claim == "complied").sum(), "changes verdict at turn 3": (d.verdict_change == "yes").sum(),
                     "classifies supplied structure as inside the boundary": (d.classifies_supplied_as == "inside_boundary").sum()}.items():
            rows.append(rate_row(TEST, "follow-ups", arm, "all", k, int(v), n))

    md += ["## 6. Per model and arm", "",
           per_model_table(df, {"verdict correct": df.termination_verdict_correctness == "Correct", "DP primary": df.family == "dependency_pairs",
                                "path order primary": df.family == "path_order", "structural language": df.flag_structural_recursion_language == "yes",
                                "imported order named": df.flag_imported_order_named == "yes"}, arm_col="system_arm"), "",
           "Reading: the costume moves the route while the mathematics stays fixed (functional equations draw structural-recursion arguments, TRS "
           "and blinded TRS draw imported orders), and the factorial's dependency-pair ascent survives blinding, so it is the visible obstruction and "
           "not recognition of the famous system that produces it; the functional costume of the factorial also makes models notice the undefined "
           "base cases that the TRS costume hides."]
    write_outputs(HERE, md, rows)
    return rows


if __name__ == "__main__":
    run()
