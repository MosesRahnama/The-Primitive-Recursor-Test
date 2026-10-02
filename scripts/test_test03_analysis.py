"""Check Test 03 override application and report regeneration."""
import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "results/analysis/test-03-completion-tests-ordinal"
sys.path.insert(0, str(ROOT / "scoring"))
sys.path.insert(0, str(ROOT / "results/analysis"))
import validate_final_scored_data as validator
import _analysis_runtime as runtime

spec = importlib.util.spec_from_file_location("test03_report", REPORT_DIR / "analysis.py")
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

CORRECTED = {
    "claude-sonnet-5__2026-07-02T17-59-22-00000",
    "grok-4.5__2026-07-10T04-23-23-00093",
}
THRESHOLD_CASES = {
    "gpt-5.6-terra__2026-07-10T05-16-30-00344",
    "gpt-5.6-terra__2026-07-10T05-16-41-00346",
    "gpt-5.6-terra__2026-07-10T05-16-56-00348",
}


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class Test03AnalysisTests(unittest.TestCase):
    def test_corrected_overrides_record_manual_evidence(self):
        rows = read_csv(ROOT / "results/final_scored_data/overrides/test03_semantic_review_overrides.csv")
        self.assertEqual(len(rows), 240)
        indexed = {row["session_slug"]: row for row in rows}
        self.assertEqual(len(indexed), 240)
        for slug in CORRECTED:
            row = indexed[slug]
            self.assertEqual(row["hard_case_semantic_correctness_override"], "Incorrect")
            self.assertEqual(row["evidence_authority"], "manual_derivation")
            self.assertEqual(row["evidence_anchor"], "manual_derivation")
            self.assertIn("R_rec_succ", row["test03_semantic_review_note"])
            self.assertIn("R_eq_diff", row["test03_semantic_review_note"])
            self.assertIn("lines", row["test03_semantic_review_note"])
            self.assertEqual(hashlib.sha256((ROOT / row["evidence_path"]).read_bytes()).hexdigest(), row["response_sha256"])
        for slug in THRESHOLD_CASES:
            self.assertEqual(indexed[slug]["hard_case_semantic_correctness_override"], "Correct")

    def test_full_test03_validation(self):
        # construction/1 tables are written from the FINAL_SCORES.csv that scoring_phase.json names.
        phase = json.loads((ROOT / "results/final_scored_data/scoring_phase.json").read_text(encoding="utf-8"))
        decisions = validator.read_decisions(ROOT / phase["decisions"]["final_scores"])
        checks = []
        with patch.object(validator, "OUT_DIR", validator.PRODUCTION_OUT_DIR):
            validator.validate_test03(checks, "final", decisions)
        self.assertEqual(len(checks), 4)
        self.assertTrue(all(row["status"] == "pass" for row in checks), checks)

    def test_source_fields_and_counts(self):
        source = read_csv(ROOT / "results/normalized_data/final_TEST03_consolidation.csv")
        scored = read_csv(ROOT / "results/final_scored_data/final_TEST03_consolidation.csv")
        self.assertEqual([r["session_slug"] for r in source], [r["session_slug"] for r in scored])
        for original, current in zip(source, scored):
            for key, value in original.items():
                # Scored quotes already use LF where normalized inputs use CRLF.
                self.assertEqual(current[key].replace("\r\n", "\n"), value.replace("\r\n", "\n"), (original["session_slug"], key))
        manifest = next(r for r in read_csv(ROOT / "results/final_scored_data/MANIFEST.csv") if r["file"] == "final_TEST03_consolidation.csv")
        self.assertEqual(sum(r["overall_test03_correctness"] == "Correct" for r in scored), int(manifest["overall_or_methodD_correct"]))
        # MANIFEST.csv has no semantic column; 3 is the construction/1 count in the table it hashes (md5 c70ad455f1).
        self.assertEqual(sum(r["hard_case_semantic_correctness"] == "Correct" for r in scored), 3)
        self.assertEqual(sum(r["hard_case_delivery_correctness"] == "Correct" for r in scored), 232)
        # construction/1 (MANIFEST.csv md5 c70ad455f1): the three passes are GPT-5.4 Pro, GPT-5.5 and GPT-5.6 Terra.
        for model, expected in [("Claude Sonnet 5", 0), ("Grok 4.5", 0)]:
            self.assertEqual(sum(r["model"] == model and r["overall_test03_correctness"] == "Correct" for r in scored), expected)

    def test_manifest_matches_test03(self):
        scored = ROOT / "results/final_scored_data/final_TEST03_consolidation.csv"
        row = next(r for r in read_csv(scored.parent / "MANIFEST.csv") if r["file"] == scored.name)
        self.assertEqual(row["n"], "240")
        self.assertEqual(row["overall_or_methodD_correct"], str(sum(r["overall_test03_correctness"] == "Correct" for r in read_csv(scored))))
        self.assertEqual(row["md5_prefix"], hashlib.md5(scored.read_bytes()).hexdigest()[:10])

    def test_all_test03_reports_reproduce(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            with patch.object(report, "HERE", output), patch.object(runtime, "analysis_folder", return_value=output):
                report.run()
                for name in runtime.cfg_reports("test-03"):
                    runtime.gen_test("test-03", name)
                runtime.gen_folder_summary("test-03")
                runtime.gen_index("test-03")
            generated = list(output.iterdir())
            self.assertEqual(len(generated), 10)
            for path in generated:
                self.assertEqual(path.read_bytes(), (REPORT_DIR / path.name).read_bytes(), path.name)

    def test_test03_rows_in_combined_findings(self):
        combined = read_csv(ROOT / "results/analysis/FINDINGS.csv")
        actual = [row for row in combined if row["test"] == report.TEST]
        self.assertEqual(actual, read_csv(REPORT_DIR / "analysis.csv"))


if __name__ == "__main__":
    unittest.main()
