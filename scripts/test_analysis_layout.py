"""Check analysis paths without regenerating reports or scores."""
import ast
import csv
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.dont_write_bytecode = True
ANALYSIS = Path(__file__).resolve().parents[1] / "results" / "analysis"
sys.path.insert(0, str(ANALYSIS))
import _analysis_runtime as core
import _roadmap_runtime as roadmap


class AnalysisLayoutTests(unittest.TestCase):
    def test_registry_and_source_folders(self):
        self.assertEqual(set(core.TESTS), set(core.TEST_FOLDERS))
        self.assertEqual(len(core.SURFACE_FOLDERS), 18)
        self.assertEqual(len(set(core.SURFACE_FOLDERS)), 18)
        self.assertEqual(roadmap.SESSION_FOLDERS, core.TEST_FOLDERS)
        for name in core.SURFACE_FOLDERS:
            self.assertTrue((ANALYSIS / name / "analysis.py").is_file(), name)
            self.assertTrue((ANALYSIS.parent / name / "test-sessions").is_dir(), name)
        for old in core.TEST_FOLDERS:
            self.assertFalse((ANALYSIS / old).exists(), old)

    def test_all_analysis_python_parses(self):
        for path in ANALYSIS.rglob("*.py"):
            with self.subTest(path=path):
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))

    def test_combined_builder_runs_both_report_sets(self):
        import build_analysis
        self.assertEqual(build_analysis.FOLDERS, [*core.SURFACE_FOLDERS, "cross-test"])
        called = []
        with patch.object(build_analysis, "main", side_effect=lambda: called.append("findings")), patch.object(core, "gen_all", side_effect=lambda: called.append("profiles")):
            runpy.run_path(str(ANALYSIS / "build_all_analysis.py"), run_name="__main__")
        self.assertEqual(called, ["findings", "profiles"])

    def test_core_writers_and_summary_readers(self):
        outputs = {}
        def capture(path, text):
            outputs[path] = text
            return path
        with patch.object(core, "write", side_effect=capture):
            wrappers = core.write_wrappers()
            for slug, folder in core.TEST_FOLDERS.items():
                for report in core.cfg_reports(slug):
                    result = core.gen_test(slug, report)
                    self.assertEqual(result.parent, ANALYSIS / folder)
                    self.assertIn(result.with_suffix(".py"), wrappers)
                self.assertEqual(core.gen_index(slug).parent, ANALYSIS / folder)
                summary = core.gen_folder_summary(slug)
                self.assertEqual(summary.parent, ANALYSIS / folder)
                self.assertIn("## ", outputs[summary])
            combined = core.gen_all_stats()
            for cfg in core.TESTS.values():
                self.assertIn(cfg["title"] + " Statistical Summary", outputs[combined])
        for path in outputs:
            self.assertNotIn(path.relative_to(ANALYSIS).parts[0], core.TEST_FOLDERS)

    def test_roadmap_writers_and_summary_readers(self):
        outputs = {}
        def capture(path, text):
            outputs[path] = text
            return path
        with patch.object(roadmap, "write", side_effect=capture):
            wrappers = roadmap.write_roadmap_wrappers()
            for name, cfg in roadmap.ROADMAP.items():
                # Statistical functions are unchanged; this test checks output routing.
                with patch.dict(cfg, {"fn": lambda: []}):
                    result = roadmap.gen_roadmap(name)
                self.assertEqual(result.parent, core.analysis_folder(cfg["folder"]))
                self.assertIn(result.with_suffix(".py"), wrappers)
            doc = roadmap.gen_roadmap_doc()
            self.assertIn("test-01-kernel-tests/answer_mode_profile.md", outputs[doc])
            summary = roadmap.gen_roadmap_summary()
            self.assertIn("Answer Mode Profile", outputs[summary])
        for path in outputs:
            self.assertNotIn(path.relative_to(ANALYSIS).parts[0], core.TEST_FOLDERS)

    def test_existing_analysis_outputs(self):
        failures = [r for r in core.validation_rows() if r[1] != "pass"]
        self.assertEqual(failures, [])

    def test_duplicate_and_stale_findings_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "schema-a").mkdir()
            for folder in [*core.SURFACE_FOLDERS, "cross-test"]:
                target = root / folder
                target.mkdir()
                (target / "analysis.py").touch()
                (target / "analysis.md").touch()
                with (target / "analysis.csv").open("w", newline="") as fh:
                    csv.writer(fh).writerows([["test", "metric"], [folder, "preserved"]])
            with (root / "FINDINGS.csv").open("w", newline="") as fh:
                csv.writer(fh).writerows([["test", "metric"], ["wrong", "stale"]])
            with patch.object(core, "ANALYSIS_DIR", root), patch.object(core, "ROOT", root):
                rows = {r[0]: r[1] for r in core.validation_rows()}
            self.assertEqual(rows["no short-name duplicate folders"], "fail")
            self.assertEqual(rows["FINDINGS.csv equals the ordered per-folder findings"], "fail")

    def test_validation_exit_status(self):
        with patch.object(core, "gen_validation", return_value="report"), patch.object(core, "validation_rows", return_value=[["test", "fail", ""]]):
            self.assertEqual(core.main(["validate"]), 1)


if __name__ == "__main__":
    unittest.main()
