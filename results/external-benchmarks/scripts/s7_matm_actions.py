"""Study 7: signals in the agent's action record against the environment's success record (MATM population runs).

matm_boundary_probe.py reads each run's actions, observations, and reasoning, never its outcome. Its predictions were
written, and their hash recorded, before any outcome was joined. score_matm_predictions.py stops unless the predictions
and both dataset files match the recorded hashes; it then joins the outcomes and computes, for each signal, the failure
rates of flagged and unflagged runs, a two-sided Fisher test with Holm adjustment over the five signals, a 95% interval
for the difference from 10,000 resamples of task ids, and a Mantel-Haenszel odds ratio within task.
landmark_matm_robustness.py rescores the runs still active after 3, 5, and 10 steps on those steps only, so every
compared run has the same number of steps in which a signal can occur; its Holm adjustment covers its 12 comparisons.
The three files are the study's scripts, unedited. This script runs them and writes tables/s7_matm_actions.csv.

Signals (WebArena unless stated):
  null_progress_loop               the same action with the same observation, inventory, and URL on three
                                   consecutive steps (WebArena and ALFWorld)
  blocked_family_persistence       the same action on the same element id, absent from the page, on consecutive steps
  interface_action_gap             an action on an element id absent from the page
  hard_local_claim_counterwitness  that absent id together with reasoning that states the element is on the page
"""
import csv, os, sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CORPORA, DATA, TABLES
import matm_boundary_probe as probe
import score_matm_predictions as score
import landmark_matm_robustness as landmark

ROOT = Path(CORPORA) / "matm-trajectories"
PREDICTIONS = Path(DATA) / "matm_action_predictions.csv"
OUT = Path(TABLES) / "s7_matm_actions.csv"
FIELDS = ["analysis", "environment", "signal", "horizon_steps", "flagged_failures", "flagged_n", "unflagged_failures",
          "unflagged_n", "flagged_failure_pct", "unflagged_failure_pct", "difference_pts", "interval_low_pts",
          "interval_high_pts", "fisher_p_holm", "within_task_odds_ratio", "within_task_p", "note"]


def pts(x):
    return "" if x is None else round(100 * x, 2)


def sig(x):
    return "" if x is None else "%.3g" % x


def table_row(analysis, s, fisher_holm, within_p, horizon, note):
    low, high = s["task_cluster_bootstrap_risk_difference95"]
    return {"analysis": analysis, "environment": s["environment"], "signal": s["signal"], "horizon_steps": horizon,
            "flagged_failures": s["flagged_failures"], "flagged_n": s["flagged_n"],
            "unflagged_failures": s["unflagged_failures"], "unflagged_n": s["unflagged_n"],
            "flagged_failure_pct": pts(s["flagged_failure_rate"]), "unflagged_failure_pct": pts(s["unflagged_failure_rate"]),
            "difference_pts": pts(s["risk_difference"]), "interval_low_pts": pts(low), "interval_high_pts": pts(high),
            "fisher_p_holm": sig(fisher_holm), "within_task_odds_ratio": sig(s["task_stratified_common_odds_ratio"]),
            "within_task_p": sig(within_p), "note": note}


def main():
    count, digest = probe.run(ROOT, PREDICTIONS)
    print("predictions", count, "hash", digest)
    rows = score.enrich(score.read_and_verify_predictions(PREDICTIONS), ROOT)
    report = score.statistics(rows)
    out = []
    for s in report["signal_statistics"]:
        out.append(table_row("full_run", s, s["fisher_p_holm5"], s["task_stratified_cmh_p_holm5"], "",
                             "Holm over five signals; within-task p also Holm over five"))
    for s in landmark.run(ROOT)["signal_statistics"]:
        out.append(table_row("landmark", s, s["exploratory_fisher_p_holm12"], s["task_stratified_cmh_p"],
                             s["horizon_steps"], "runs active at the landmark, scored on that many steps; Holm over 12; "
                             "within-task p unadjusted"))
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    for environment, counts in report["outcome_counts"].items():
        print(environment, counts)
    for r in out:
        print(r["analysis"], r["environment"], r["signal"], r["horizon_steps"], r["flagged_failure_pct"],
              r["unflagged_failure_pct"], r["difference_pts"], [r["interval_low_pts"], r["interval_high_pts"]])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
