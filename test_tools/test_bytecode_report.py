"""Bytecode summaries must count robot turns, not checkpoints or file bytes."""

import contextlib
import csv
import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sim_report import BYTECODE_COUNTERS, print_summary, write_report


def pair(case="farm-A", checkpoint="FINAL", candidate=(10, 1000, 200, 1000, 0),
         baseline=(10, 1000, 200, 1000, 0)):
    result = []
    for role, values in (("candidate", candidate), ("baseline", baseline)):
        row = dict(Case=case, Map="farm", CandidateSide="A", Role=role,
                   Checkpoint=checkpoint, Round=2000 if checkpoint == "FINAL" else 1000,
                   Side="A" if role == "candidate" else "B", Seed=7,
                   DeliveredCheese=100, ReserveCheese=100, Kings=1, BabyRats=4,
                   CatDamage=0, Cooperation="true", Winner="candidate", WinType="MORE_POINTS",
                   FinalRound=2000, LastKingAliveRound=2000, BytecodeStatus="AVAILABLE")
        for prefix, counts in (("BabyRat", values), ("RatKing", (2, 1000, 600, 2000, 0))):
            row.update({prefix + key: value for key, value in zip(BYTECODE_COUNTERS, counts)})
        result.append(row)
    return result


class BytecodeReportTests(unittest.TestCase):
    def reports(self, rows, expected=1, manifest=None):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_report(output, rows, manifest or {}, expected)
            markdown = (output / "summary.md").read_text(encoding="utf-8")
            note = (output / "pr-summary.md").read_text(encoding="utf-8")
            with (output / "results.csv").open(encoding="utf-8", newline="") as handle:
                saved = list(csv.DictReader(handle))
        terminal = io.StringIO()
        with contextlib.redirect_stdout(terminal):
            print_summary(rows, expected)
        return markdown, note, saved, terminal.getvalue()

    def test_average_weights_robot_turns_and_peak_is_a_single_turn(self):
        rows = pair(candidate=(1, 100, 100, 1000, 0))
        rows += pair(case="farm-B", candidate=(9, 8100, 900, 1000, 0))
        markdown, note, _, terminal = self.reports(rows, 2)
        expected = "| Candidate | Baby Rat | 2/2 | 10 | 820.0 | 900 | 1,000 | 82.0% | 90.0% | 0 (0.0%) |"
        self.assertIn(expected, markdown)
        self.assertIn(expected, note)
        self.assertIn("average 820.0 (82.0% of budget), peak 900 (90.0% of budget)", terminal)
        self.assertIn("including startup", markdown)
        self.assertIn("total executed bytecodes divided by recorded robot turns", markdown)

    def test_checkpoints_never_double_count_cumulative_counters(self):
        rows = pair() + pair(checkpoint="ROUND_1000", candidate=(99, 99000, 1000, 1000, 99))
        rows += pair(checkpoint="COMMON_1000", candidate=(99, 99000, 1000, 1000, 99))
        markdown, _, saved, _ = self.reports(rows)
        self.assertIn("| Candidate | Baby Rat | 1/1 | 10 | 100.0 | 200 |", markdown)
        self.assertIn("cumulative through each checkpoint", markdown)
        self.assertIn("adding checkpoint rows would count turns repeatedly", markdown)
        self.assertEqual(6, len(saved))
        self.assertEqual("99000", saved[2]["BabyRatBytecodesTotal"])

    def test_older_measurements_are_unavailable_instead_of_zero(self):
        rows = pair()
        for row in rows:
            for key in list(row):
                if key.startswith(("BabyRat", "RatKing")) and key != "BabyRats":
                    del row[key]
            del row["BytecodeStatus"]
        markdown, note, _, terminal = self.reports(rows)
        expected = "| Candidate | Baby Rat | 0/1 | unavailable | unavailable |"
        self.assertIn(expected, markdown)
        self.assertIn(expected, note)
        self.assertIn("unavailable does not mean zero usage", markdown)
        self.assertIn("Baby Rat excluded pairs: 1 missing or unavailable, 0 invalid", markdown)
        self.assertIn("average unavailable", terminal)

    def test_mixed_measurements_use_the_same_covered_pairs_for_both_roles(self):
        rows = pair()
        old = pair(case="farm-B", candidate=(100, 99900, 999, 1000, 0))
        for key in BYTECODE_COUNTERS:
            del old[1]["BabyRat" + key]
        del old[1]["BytecodeStatus"]
        markdown, _, _, _ = self.reports(rows + old, 2)
        self.assertIn("| Candidate | Baby Rat | 1/2 | 10 | 100.0 | 200 |", markdown)
        self.assertIn("| Baseline | Baby Rat | 1/2 | 10 | 100.0 | 200 |", markdown)
        self.assertIn("| Candidate | Rat King | 1/2 |", markdown)
        self.assertIn("Rat King excluded pairs: 0 missing or unavailable, 1 invalid", markdown)

    def test_zero_turn_type_has_a_budget_but_no_average_or_peak(self):
        rows = pair(candidate=(0, 0, 0, 1000, 0), baseline=(0, 0, 0, 1000, 0))
        markdown, _, _, _ = self.reports(rows)
        self.assertIn("| Candidate | Baby Rat | 1/1 | 0 | n/a (no robot turns) | n/a | 1,000 | n/a | n/a | n/a |", markdown)
        self.assertNotIn("nan", markdown.lower())
        self.assertNotIn("inf%", markdown)

    def test_budget_hits_include_exact_limit_and_above_limit_without_forced_yield_claim(self):
        rows = pair(candidate=(4, 3100, 1100, 1000, 2))
        markdown, note, _, terminal = self.reports(rows)
        expected = "| Candidate | Baby Rat | 1/1 | 4 | 775.0 | 1,100 | 1,000 | 77.5% | 110.0% | 2 (50.0%) |"
        self.assertIn(expected, markdown)
        self.assertIn(expected, note)
        self.assertIn("does not prove a forced yield", markdown)
        self.assertIn("budget reached 2 (50.0%)", terminal)

    def test_incomplete_or_duplicate_pairs_never_supply_bytecode_data(self):
        rows = pair() + pair(case="farm-B", candidate=(1, 999, 999, 1000, 0))[:1]
        rows += pair(case="farm-C") + pair(case="farm-C")[:1]
        markdown, _, _, _ = self.reports(rows, 3)
        self.assertIn("**INCOMPLETE: 1/3 complete match pairs.**", markdown)
        self.assertIn("| Candidate | Baby Rat | 1/1 | 10 | 100.0 | 200 |", markdown)

    def test_noninteger_negative_and_impossible_counters_are_excluded(self):
        invalid = [
            ("Turns", -1), ("Turns", 1.5), ("Turns", True), ("Turns", "ten"),
            ("Turns", 0), ("Turns", 1), ("BytecodesTotal", 199),
            ("BytecodesTotal", 2001), ("BytecodesMax", 1001),
            ("BytecodeLimit", 0), ("BudgetHits", 11), ("BudgetHits", 1),
        ]
        for key, value in invalid:
            with self.subTest(key=key, value=value):
                rows = pair()
                rows[0]["BabyRat" + key] = value
                markdown, _, _, _ = self.reports(rows)
                self.assertIn("| Candidate | Baby Rat | 0/1 | unavailable |", markdown)
                self.assertIn("Baby Rat excluded pairs: 0 missing or unavailable, 1 invalid", markdown)

    def test_partial_counters_and_missing_available_status_are_invalid(self):
        for key in ("BabyRatBytecodesMax", "BytecodeStatus"):
            with self.subTest(key=key):
                rows = pair()
                del rows[0][key]
                markdown, _, _, _ = self.reports(rows)
                self.assertIn("Baby Rat excluded pairs: 0 missing or unavailable, 1 invalid", markdown)

    def test_hit_count_must_be_possible_for_the_total_and_peak(self):
        for counts in ((3, 4000, 1500, 1000, 1), (3, 2400, 1500, 1000, 2)):
            with self.subTest(counts=counts):
                markdown, _, _, _ = self.reports(pair(candidate=counts))
                self.assertIn("| Candidate | Baby Rat | 0/1 | unavailable |", markdown)

    def test_different_budgets_between_roles_cannot_be_compared(self):
        rows = pair()
        rows[0]["BabyRatBytecodeLimit"] = 2000
        markdown, _, _, _ = self.reports(rows)
        self.assertIn("| Candidate | Baby Rat | 0/1 | unavailable |", markdown)
        self.assertIn("Baby Rat excluded pairs: 0 missing or unavailable, 1 invalid", markdown)

    def test_different_budgets_between_matches_are_not_combined(self):
        rows = pair() + pair(case="farm-B", candidate=(10, 1000, 200, 2000, 0),
                              baseline=(10, 1000, 200, 2000, 0))
        markdown, _, _, _ = self.reports(rows, 2)
        self.assertIn("| Candidate | Baby Rat | 0/2 | unavailable |", markdown)
        self.assertIn("2 invalid (conflicting engine budgets)", markdown)

    def test_unreliable_engine_records_show_the_reason_and_header_only_csv(self):
        rows = pair()
        for row in rows:
            row["BytecodeStatus"] = "UNAVAILABLE: duplicate robot turn | <detail>"
            for prefix in ("BabyRat", "RatKing"):
                for key in BYTECODE_COUNTERS:
                    row[prefix + key] = ""
        manifest = {"cases": [{"case": "farm-A", "bytecodes": "farm A-bytecodes.csv"}]}
        markdown, note, _, terminal = self.reports(rows, manifest=manifest)
        self.assertIn("Unavailable replay measurements (1 complete pairs): UNAVAILABLE: duplicate robot turn &#124; &lt;detail&gt;", markdown)
        self.assertIn("UNAVAILABLE: duplicate robot turn &#124; &lt;detail&gt;", note)
        self.assertIn("[bytecodes (header only)](farm%20A-bytecodes.csv)", markdown)
        self.assertIn("bytecode CSV contains only a header", markdown)
        self.assertIn("Bytecodes unavailable for 1 complete pairs", terminal)

    def test_available_raw_sample_csv_is_linked_and_fields_survive_results_csv(self):
        rows = pair()
        rows[0]["BytecodeCSV"] = "farm A-bytecodes.csv"
        markdown, _, saved, _ = self.reports(rows)
        self.assertIn("[bytecodes](farm%20A-bytecodes.csv)", markdown)
        self.assertEqual("1000", saved[0]["BabyRatBytecodesTotal"])
        self.assertEqual("AVAILABLE", saved[0]["BytecodeStatus"])

    def test_empty_run_has_unavailable_metrics_and_zero_coverage(self):
        markdown, note, saved, terminal = self.reports([], 2)
        self.assertIn("| Candidate | Baby Rat | 0/0 | unavailable |", markdown)
        self.assertIn("| Baseline | Rat King | 0/0 | unavailable |", note)
        self.assertEqual([], saved)
        self.assertIn("0/0 measured pairs", terminal)


if __name__ == "__main__":
    unittest.main()
