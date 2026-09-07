"""Regression tests for the self-game review tooling.

The fixture is the 2026-09-07 hanchan stored under ``data/self_games``. It is a
real game with a known ending score, so a replay bug shows up as a score that
no longer reconciles.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import review_self_game as review  # noqa: E402
import tenhou_replay as tr  # noqa: E402

FIXTURE = ROOT / "data/self_games/2026-09-07-hanchan.json"


class TenhouReplayTests(unittest.TestCase):
    def test_meld_tokens_decode_caller_and_tile(self):
        chi = tr.parse_meld("c212223")
        self.assertEqual((chi["kind"], chi["called"], chi["from_offset"]), ("c", 21, 3))
        pon_across = tr.parse_meld("34p3434")
        self.assertEqual((pon_across["kind"], pon_across["called"], pon_across["from_offset"]), ("p", 34, 2))
        pon_right = tr.parse_meld("2828p28")
        self.assertEqual(pon_right["from_offset"], 1)

    def test_red_fives_collapse_for_shape_but_keep_identity(self):
        self.assertEqual(tr.base(52), 25)
        self.assertTrue(tr.is_red(52))
        self.assertEqual(tr.tile34(52), tr.tile34(25))

    def test_seat_and_round_winds(self):
        self.assertEqual(tr.seat_wind(0, 0), 41)   # dealer in East 1 is East
        self.assertEqual(tr.seat_wind(0, 1), 44)   # same seat is North in East 2
        self.assertEqual(tr.round_wind(4), 42)     # South rounds
        self.assertIn(45, tr.yakuhai_for(0, 0))

    def test_replay_consumes_every_draw_and_discard(self):
        for log in tr.load_logs(FIXTURE):
            game = tr.replay(log)
            for player in game["players"]:
                self.assertEqual(player["ci"], len(player["discards"]))
                self.assertLessEqual(len(player["hand"]), 13)


class SelfReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logs = tr.load_logs(FIXTURE)
        cls.hands, cls.stats, cls.findings = review.build_report(cls.logs, hero=0)

    def test_baselines_come_from_the_mined_artifacts(self):
        bl = review.load_baselines()
        self.assertEqual(bl["push_vs_riichi"]["0"], 58.9)
        self.assertEqual(bl["push_vs_riichi"]["3+"], 14.1)
        self.assertEqual(bl["declare_by_waits"]["<=3"], 33.7)
        self.assertEqual(bl["declare_by_waits_dealer"]["<=3"], 41.9)
        self.assertEqual(bl["yakuhai_pon_first_copy"], 75.9)
        self.assertEqual(bl["chi_closed"], 6.7)

    def test_score_reconciles_to_the_real_final_score(self):
        self.assertEqual(len(self.hands), 11)
        start = self.hands[0]["start_scores"][0]
        self.assertEqual(start, 25000)
        self.assertEqual(start + self.stats["score_delta"], 15800)

    def test_push_curve_is_measured_against_luckyj(self):
        push = {b: review.pct(self.stats["push_taken"][b], self.stats["push_chances"][b])
                for b in self.stats["push_chances"]}
        self.assertEqual(push["0"], 62.5)
        self.assertEqual(push["2"], 0.0)
        self.assertEqual(push["3+"], 30.0)

    def test_the_expensive_hand_is_flagged(self):
        kinds = {(f["kind"], f["round"]) for f in self.findings}
        self.assertIn(("deal-in", "South 2-0"), kinds)
        self.assertIn(("unnamed-safety", "South 2-0"), kinds)
        self.assertIn(("far-push", "South 2-0"), kinds)
        self.assertIn(("thin-riichi", "East 1-0"), kinds)

    def test_thin_riichi_names_the_live_tile_count(self):
        thin = [f for f in self.findings if f["kind"] == "thin-riichi"]
        self.assertEqual(len(thin), 1)
        self.assertIn("only 2 live tile", thin[0]["text"])

    def test_unnamed_safety_reports_a_tile_that_was_actually_held(self):
        for f in self.findings:
            if f["kind"] != "unnamed-safety":
                continue
            self.assertRegex(f["text"], r"holding a genbutsu for every threat \(p\d: ")


if __name__ == "__main__":
    unittest.main()
