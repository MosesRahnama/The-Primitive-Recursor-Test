from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import express_extraction as express
import sync_extraction_sessions as sync


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


class SyncExtractionSessionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.test_key = "test-04-measure-verification-tests"
        test_dir = self.root / "results" / self.test_key
        batch_dir = test_dir / "extraction" / "batches"
        dispatch_dir = batch_dir / "dispatch"
        dispatch_dir.mkdir(parents=True)
        prompt = dispatch_dir / "TEST04_INCREMENTAL_ROUND1_PROMPTS.md"
        prompt.write_text("fixture\n", encoding="utf-8")
        ledger = batch_dir / "TEST04_LEDGER.csv"
        e1 = batch_dir / "TEST04_r1_extractor_01.csv"
        e2 = batch_dir / "TEST04_r1_extractor_02.csv"
        cons = batch_dir / "TEST04_r1_consolidation.csv"
        master = batch_dir / "TEST04_master_output.csv"
        existing = "alpha__2026-01-01T00-00-00-00000"
        write_csv(ledger, ["session_slug", "model", "provider", "prompt_variant"], [[existing, "Alpha", "P", "n/a"]])
        write_csv(e1, ["session_slug", "value"], [[existing, "done"]])
        write_csv(e2, ["session_slug", "value"], [[existing, "done"]])
        write_csv(
            cons,
            ["session_slug", "extractor1_value", "extractor2_value", "final_value"],
            [[existing, "done", "done", "done"]],
        )
        write_csv(master, ["session_slug"], [[existing]])
        round_contract = express.RoundContract(
            number=1,
            source_prompt=prompt,
            extractor_01_block="",
            extractor_02_block="",
            consolidator_block="",
            extractor_01_csv=e1,
            extractor_02_csv=e2,
            consolidation_csv=cons,
            extractor_header=["session_slug", "value"],
            response_file="response.txt",
        )
        self.contract = express.TestContract(
            key=self.test_key,
            test_dir=test_dir,
            batch_dir=batch_dir,
            dispatch_dir=dispatch_dir,
            prefix="TEST04",
            ledger_csv=ledger,
            master_output_csv=master,
            rounds=(round_contract,),
        )
        self.roster = {
            "alpha": {"display": "Alpha", "provider": "P", "live": True},
            "beta": {"display": "Beta", "provider": "P", "live": True},
            "retired": {"display": "Retired", "provider": "P", "live": False},
        }
        self.add_session(existing, "alpha", "2026-01-01T00:00:00Z")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def add_session(
        self,
        slug: str,
        model: str,
        generated: str,
        response: str = "usable answer",
    ) -> None:
        session = self.contract.test_dir / "test-sessions" / slug
        session.mkdir(parents=True)
        (session / "session.json").write_text(
            json.dumps(
                {
                    "model_slug": model,
                    "test_folder": self.test_key,
                    "variant_suffix": "",
                    "generated_utc": generated,
                    "provider": "P",
                }
            ),
            encoding="utf-8",
        )
        (session / "response.txt").write_text(response, encoding="utf-8")

    def test_selects_only_needed_usable_live_sessions(self) -> None:
        self.add_session("alpha__2026-01-02T00-00-00-00001", "alpha", "2026-01-02T00:00:00Z")
        self.add_session("alpha__2026-01-03T00-00-00-00002", "alpha", "2026-01-03T00:00:00Z")
        self.add_session("beta__2026-01-01T00-00-00-00003", "beta", "2026-01-01T00:00:00Z")
        self.add_session("beta__2026-01-02T00-00-00-00004", "beta", "2026-01-02T00:00:00Z")
        self.add_session("beta__2026-01-03T00-00-00-00005", "beta", "2026-01-03T00:00:00Z", "[ERROR] timeout")
        self.add_session("retired__2026-01-01T00-00-00-00006", "retired", "2026-01-01T00:00:00Z")
        self.add_session("unknown__2026-01-01T00-00-00-00007", "unknown", "2026-01-01T00:00:00Z")
        bad = self.contract.test_dir / "extraction" / "bad_sessions.md"
        bad.write_text(
            "| session_slug | session_path | bad_data_reason | logged_by |\n"
            "|---|---|---|---|\n"
            "| beta__2026-01-04T00-00-00-00008 | p | truncated | E1 |\n",
            encoding="utf-8",
        )
        self.add_session("beta__2026-01-04T00-00-00-00008", "beta", "2026-01-04T00:00:00Z")

        plan = sync.build_sync_plan(self.contract, self.roster, target=2)

        self.assertEqual(
            plan.selected,
            [
                "alpha__2026-01-02T00-00-00-00001",
                "beta__2026-01-01T00-00-00-00003",
                "beta__2026-01-02T00-00-00-00004",
            ],
        )
        self.assertEqual(plan.shortfall, 0)
        self.assertEqual(plan.over_target_new, ["alpha__2026-01-03T00-00-00-00002"])
        self.assertEqual(len(plan.invalid_new), 1)
        self.assertEqual(len(plan.bad_new), 1)
        self.assertEqual(len(plan.out_of_roster_new), 2)

    def test_repairs_partially_synchronized_csvs(self) -> None:
        slug = "beta__2026-01-01T00-00-00-00003"
        self.add_session(slug, "beta", "2026-01-01T00:00:00Z")
        path = self.contract.rounds[0].extractor_02_csv
        with path.open("a", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerow([slug, ""])

        plan = sync.build_sync_plan(self.contract, self.roster, target=1)

        self.assertEqual(plan.partial_slugs, [slug])
        self.assertEqual(sum(len(slugs) for slugs in plan.repair_rows.values()), 3)
        run_id = "repair_test"
        run_dir = sync.apply_repairs(
            self.contract, plan, self.roster, run_id, self.root
        )
        self.assertIsNotNone(run_dir)
        self.assertTrue((run_dir / "repair_manifest.json").exists())
        for target in express.target_records(self.contract):
            target_path = Path(target["path"])
            header, rows = express.read_csv(target_path)
            matching = [row for row in rows if row[header.index("session_slug")] == slug]
            self.assertEqual(len(matching), 1)
            if target["kind"] != "ledger":
                self.assertFalse(
                    any(
                        cell
                        for index, cell in enumerate(matching[0])
                        if header[index] != "session_slug"
                    )
                )
        repaired = sync.build_sync_plan(self.contract, self.roster, target=1)
        self.assertEqual(repaired.partial_slugs, [])
        self.assertEqual(repaired.selected, [])

    def test_allows_historical_order_differences(self) -> None:
        second = "beta__2026-01-01T00-00-00-00003"
        self.add_session(second, "beta", "2026-01-01T00:00:00Z")
        for target in express.target_records(self.contract):
            path = Path(target["path"])
            header, _rows = express.read_csv(path)
            values = {"session_slug": second, "model": "Beta", "provider": "P"}
            with path.open("a", encoding="utf-8", newline="") as handle:
                csv.writer(handle).writerow([values.get(column, "") for column in header])
        e2 = self.contract.rounds[0].extractor_02_csv
        header, rows = express.read_csv(e2)
        write_csv(e2, header, list(reversed(rows)))

        plan = sync.build_sync_plan(self.contract, self.roster, target=1)

        self.assertEqual(plan.selected, [])
        self.assertEqual(plan.shortfall, 0)

    def test_schema_a_requires_response_mirror(self) -> None:
        contract = express.TestContract(
            key="schema-test-A-tests",
            test_dir=self.contract.test_dir,
            batch_dir=self.contract.batch_dir,
            dispatch_dir=self.contract.dispatch_dir,
            prefix=self.contract.prefix,
            ledger_csv=self.contract.ledger_csv,
            master_output_csv=self.contract.master_output_csv,
            rounds=(
                express.RoundContract(
                    **{
                        **self.contract.rounds[0].__dict__,
                        "response_file": "response_1.txt",
                    }
                ),
            ),
        )
        slug = "alpha__2026-01-05T00-00-00-00009"
        session = contract.test_dir / "test-sessions" / slug
        session.mkdir(parents=True)
        (session / "session.json").write_text(
            json.dumps(
                {
                    "model_slug": "alpha",
                    "test_folder": "schema-test-A-tests",
                    "variant_suffix": "",
                }
            ),
            encoding="utf-8",
        )
        (session / "response_1.txt").write_text("answer", encoding="utf-8")
        info = sync.inspect_session(contract, slug)
        self.assertIn("missing:response.txt", info.problems)


if __name__ == "__main__":
    unittest.main()
