"""Test 10: the 108-rule HOL Light numeral-arithmetic system (TPDB Kaliszyk_19/arith)."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from _lib import *  # noqa: E402,F401,F403

TEST = "test-10-bigger-system-cascade-tests"


def run():
    df = add_families(load("TEST10"))
    rows, md = [], []
    n = len(df)
    md += ["# Test 10: the 108-rule arithmetic system (TPDB Kaliszyk_19/arith, HOL Light numeral clauses)", "",
           "Source `final_TEST10_consolidation.csv`: 100 sessions, 10 models, 10 each, Test 01 wording, one follow-up turn with the four boundary questions. "
           "Certified terminating (TTT2 automatic and dependency-pair proofs, CeTA); bounded searches for LPO, KBO and polynomial orders return MAYBE, "
           "which is not an impossibility, and quasi-precedence path orders do orient the system, so `refuted_family_claim` is `na` throughout. "
           "The system has ten duplicating rules; the marked cases are the exponentiation-by-squaring rules that duplicate the recursive call. "
           "`propagation_event` is provisional (its input column was set aside when the two extraction passes disagreed). No proof-validity axis.", ""]

    v = int((df.termination_verdict_correctness == "Correct").sum())
    wrong = df[df.termination_verdict_correctness != "Correct"]
    md += ["## 1. Verdict and route", "", f"Correct termination verdict: {cell(v, n)}. Wrong verdicts: " + ", ".join(f"{r.model} ({r.negative_verdict_subtype})" for r in wrong.itertuples()) + ".", "",
           dist_table(df.assign(all="arith"), "all", "family", order=FAMILY_ORDER + ["none", "other"]), ""]
    rows.append(rate_row(TEST, "verdict", "arith", "all", "termination verdict correct", v, n))
    items = {"dependency pairs primary (label-first family)": (df.family == "dependency_pairs").sum(),
             "dependency pairs mentioned in the method label": df.mentions_dp.sum(),
             "recursive-call abstraction named anywhere (flag_w2_method_named)": (df.flag_w2_method_named == "yes").sum(),
             "explicit recursive-call method (transformed_call_signal)": (df.transformed_call_signal == "explicit_w2_method").sum(),
             "path order primary": (df.family == "path_order").sum(),
             "interpretation primary": (df.family == "interpretation").sum(),
             "menu of families in the label": df.menu.sum(),
             "more than one approach proposed": (df.more_than_one_approach_proposed == "yes").sum(),
             "answer mode: method": (df.primary_answer_mode == "method").sum()}
    md += [md_table(["measure", "sessions"], [[k, cell(int(v_), n, ci=False)] for k, v_ in items.items()]), ""]
    for k, v_ in items.items():
        rows.append(rate_row(TEST, "route", "arith", "all", k, int(v_), n))
    for fam in FAMILY_ORDER + ["none", "other"]:
        rows.append(rate_row(TEST, "route", "arith", "all", f"primary family {fam}", int((df.family == fam).sum()), n))

    md += ["## 2. Duplicating rules and witness claims", ""]
    flags = {"duplication noted": (df.flag_duplication_noted == "yes").sum(),
             "specific order or interpretation asserted": (df.flag_specific_order_asserted == "yes").sum(),
             "claims every rule was checked": (df.flag_claims_all_rules_checked == "yes").sum(),
             "uninterpreted if symbol noticed": (df.flag_conditional_if_symbol_noted == "yes").sum(),
             "propagation event (provisional)": (df.propagation_event == "yes").sum()}
    md += [md_table(["flag", "sessions"], [[k, cell(int(v_), n, ci=False)] for k, v_ in flags.items()]), "",
           dist_table(df.assign(all="arith"), "all", "exp_squaring_handling", order=["discharged", "asserted", "skipped", "misstated"]), ""]
    for k, v_ in flags.items():
        rows.append(rate_row(TEST, "duplicating rules", "arith", "all", k, int(v_), n))
    for val in ["discharged", "asserted", "skipped", "misstated"]:
        rows.append(rate_row(TEST, "duplicating rules", "arith", "all", f"exp squaring rule {val}", int((df.exp_squaring_handling == val).sum()), n))
    ct = pd.crosstab(df.flag_specific_order_asserted, df.flag_claims_all_rules_checked)
    md += ["Specific witness asserted (rows) against claims every rule checked (columns):", "",
           md_table(["specific witness"] + [f"claims all checked: {c}" for c in ct.columns], [[i] + [int(x) for x in r] for i, r in ct.iterrows()]), ""]

    md += ["## 3. Follow-up: the four boundary questions", ""]
    fu = {"q2 method relies on choices not fixed by the rules: yes": (df.q2_imports_external == "yes").sum(),
          "q3 that places it outside the boundary: yes": (df.q3_outside_boundary == "yes").sum(),
          "q3 outside the boundary: no": (df.q3_outside_boundary == "no").sum(),
          "q4 still strongly normalizing: yes": (df.q4_still_sn == "yes").sum()}
    md += [md_table(["question", "sessions"], [[k, cell(int(v_), n, ci=False)] for k, v_ in fu.items()]), ""]
    for k, v_ in fu.items():
        rows.append(rate_row(TEST, "self-report", "arith", "all", k, int(v_), n))

    md += ["## 4. Per model", "",
           per_model_table(df, {"verdict correct": df.termination_verdict_correctness == "Correct", "DP primary": df.family == "dependency_pairs",
                                "DP mentioned": df.mentions_dp, "path order primary": df.family == "path_order", "duplication noted": df.flag_duplication_noted == "yes",
                                "exp squaring discharged": df.exp_squaring_handling == "discharged", "exp squaring skipped": df.exp_squaring_handling == "skipped",
                                "specific witness": df.flag_specific_order_asserted == "yes", "claims all rules checked": df.flag_claims_all_rules_checked == "yes",
                                "q3 outside boundary: yes": df.q3_outside_boundary == "yes"}), ""]

    md += ["## 5. Against the independent audit (`results-docs/test-10-cascade/independent-audit-2026-08-03/AUDIT-REPORT.md`)", "",
           "The audit read all 100 responses under its own rubric; the scored file was extracted separately. Matching quantities:", "",
           md_table(["quantity", "audit", "this file"], [
               ["correct verdict", "98/100", f"{v}/100"],
               ["dependency pairs strict primary", "6/100", f"{int((df.family == 'dependency_pairs').sum())}/100 (label-first family)"],
               ["dependency pairs mentioned in the final answer", "45/100", f"{int(df.mentions_dp.sum())}/100 in the method label; {int((df.flag_w2_method_named == 'yes').sum())}/100 named anywhere"],
               ["concrete or partial constructions", "62/100 (59 checker-instantiated, 14 refuted)", f"{int((df.flag_specific_order_asserted == 'yes').sum())}/100 specific witness asserted (never checked here)"],
               ["final answers addressing duplication", "57/100", f"{int((df.flag_duplication_noted == 'yes').sum())}/100 duplication noted"],
               ["rule coverage", "no session checks all 108 rules; 32 of 108 rules ever cited", f"{int((df.flag_claims_all_rules_checked == 'yes').sum())}/100 claim every rule was checked"],
               ["follow-up: choices not fixed by the rules", "97 yes, 3 no", f"{int((df.q2_imports_external == 'yes').sum())} yes"],
               ["follow-up: outside the boundary", "31 yes, 62 no, 7 equivocal", f"{int((df.q3_outside_boundary == 'yes').sum())} yes, {int((df.q3_outside_boundary == 'no').sum())} no, {int((df.q3_outside_boundary == 'unclear').sum())} unclear"]]), "",
           "Reading: on the largest system in the programme the verdict is at ceiling, the route stays in the direct family (path orders and menus) "
           "with dependency pairs as a mention far more often than a commitment, the exp-squaring duplication is skipped or merely asserted in more "
           "than half of the sessions, and most responses claim full rule coverage that the audit's executable checks refute."]
    write_outputs(HERE, md, rows)
    return rows


if __name__ == "__main__":
    run()
