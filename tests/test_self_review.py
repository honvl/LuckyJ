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
FIXTURE_LINKS = ROOT / "data/self_games/2026-09-07-hanchan-2.txt"


def table(discards, riichi=None, indicator=11):
    """What the safety grading reads, at the discard that follows ``discards``.

    ``discards`` lists every earlier discard in order as (seat, tile); ``riichi``
    maps a seat to the position of its declaring discard.
    """
    events = [{"index": i, "seat": s, "tile": t, "melds": []} for i, (s, t) in enumerate(discards)]
    game = {"events": events, "players": [{"melds": []} for _ in range(4)], "dora_indicators": [indicator]}
    rivers = {s: [t for seat, t in discards if seat == s] for s in range(4)}
    riichi_seats = {s: (riichi or {}).get(s) for s in range(4)}
    return game, {"index": len(events), "rivers": rivers, "riichi_seats": riichi_seats}


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
        # 4 of 8: the 8m on East 2-1 turn 11 had been passed after p3's riichi
        self.assertEqual(push["0"], 50.0)
        self.assertEqual(push["2"], 0.0)
        # the one far cut, the 8p on South 2-0 turn 11, is suji: a 5p went by after p1's riichi
        self.assertEqual(push["3+"], 0.0)

    def test_first_answers_count_in_every_game_of_a_manifest(self):
        # games share round names such as "East 1-0"; each hand still has its own first answer
        _, stats, findings = review.build_report(self.logs, hero=0)
        answers = sum(stats["first_answer_bucket"].values())
        self.assertGreater(answers, 0)
        review.build_report(self.logs, 0, stats, findings)
        self.assertEqual(sum(stats["first_answer_bucket"].values()), 2 * answers)

    def test_the_expensive_hand_is_flagged(self):
        kinds = {(f["kind"], f["round"]) for f in self.findings}
        self.assertIn(("deal-in", "South 2-0"), kinds)
        self.assertIn(("thin-riichi", "East 1-0"), kinds)

    def test_suji_anchored_by_a_passed_tile_is_not_a_push(self):
        # South 2-0 turn 11: the 8p looks live against p1's river, but a 5p was cut after p1's
        # riichi without a ron, so the 8p is suji; it is neither a far push nor an unused safe tile
        kinds = {(f["kind"], f["round"]) for f in self.findings}
        self.assertNotIn(("far-push", "South 2-0"), kinds)
        self.assertNotIn(("unnamed-safety", "South 2-0"), kinds)

    def test_thin_riichi_names_the_live_tile_count(self):
        thin = [f for f in self.findings if f["kind"] == "thin-riichi"]
        self.assertEqual(len(thin), 1)
        self.assertIn("only 2 live tile", thin[0]["text"])

    def test_unnamed_safety_reports_a_tile_that_was_actually_held(self):
        for f in self.findings:
            if f["kind"] != "unnamed-safety":
                continue
            self.assertRegex(f["text"], r"holding a genbutsu for every threat \(p\d: ")


class SafetyRuleTests(unittest.TestCase):
    def test_tile_passed_after_a_riichi_is_genbutsu(self):
        # p1 declares with N; p2 then throws 9m and p1 does not ron, so p1 is furiten on it
        game, e = table([(0, 13), (1, 44), (2, 19), (3, 41)], riichi={1: 1})
        self.assertEqual(review.tile_safety(19, 1, e, game, [19]), "genbutsu")

    def test_tile_passed_before_the_riichi_is_not_genbutsu(self):
        game, e = table([(0, 13), (1, 44), (2, 19), (3, 41)], riichi={1: 1})
        self.assertEqual(review.tile_safety(13, 1, e, game, [13]), "live-outer")

    def test_tile_passed_after_a_riichi_anchors_suji(self):
        # p1 declares with N; p2 then throws 1p unpunished, so 4p is suji for p1 as well
        game, e = table([(0, 13), (1, 44), (2, 21), (3, 41)], riichi={1: 1})
        self.assertEqual(review.tile_safety(24, 1, e, game, [24]), "live-middle")  # 7p side still open
        game, e = table([(0, 13), (1, 27), (2, 21), (3, 41)], riichi={1: 1})
        self.assertEqual(review.tile_safety(24, 1, e, game, [24]), "suji")  # nakasuji: 7p in river, 1p passed
        game, e = table([(0, 21), (1, 27), (2, 13), (3, 41)], riichi={1: 1})
        self.assertEqual(review.tile_safety(24, 1, e, game, [24]), "live-middle")  # 1p went before the riichi

    def test_passed_tiles_prove_nothing_against_a_hand_without_riichi(self):
        game, e = table([(0, 13), (1, 44), (2, 19), (3, 41)])
        self.assertEqual(review.tile_safety(19, 1, e, game, [19]), "live-terminal")

    def test_quiet_honors_are_folds_not_pushes(self):
        """A lone honor with two other copies showing sits under the 5% danger line."""
        # every chun below was thrown before p1's riichi, so riichi furiten does not apply
        game, e = table([(2, 47), (3, 47), (0, 12), (1, 44)], riichi={1: 3})
        self.assertEqual(review.tile_safety(47, 1, e, game, [47]), "quiet-honor")
        game, e = table([(2, 47), (3, 11), (0, 12), (1, 44)], riichi={1: 3})
        self.assertEqual(review.tile_safety(47, 1, e, game, [47]), "live-honor")
        self.assertEqual(review.tile_safety(47, 1, e, game, [47, 47]), "quiet-honor")  # own second copy
        game, e = table([(2, 47), (3, 11), (0, 12), (1, 44)], riichi={1: 3}, indicator=47)
        self.assertEqual(review.tile_safety(47, 1, e, game, [47]), "quiet-honor")  # the indicator shows one
        game, e = table([(2, 47), (3, 47), (0, 47), (1, 44)], riichi={1: 3})
        self.assertEqual(review.tile_safety(47, 1, e, game, [47]), "dead")
        self.assertIn("quiet-honor", review.NOT_A_PUSH)
        self.assertNotIn("live-honor", review.NOT_A_PUSH)


class RiichiFuritenTests(unittest.TestCase):
    """East 1 of the second hanchan: p2 declares on turn 3 and the hero keeps discarding."""

    @classmethod
    def setUpClass(cls):
        cls.game = tr.replay(tr.load_logs(FIXTURE_LINKS)[0])
        cls.mine = {e["turn"]: e for e in cls.game["events"] if e["seat"] == 0}

    def safety(self, turn):
        e = self.mine[turn]
        return review.tile_safety(e["tile"], 2, e, self.game, e["hand_before"])

    def test_tiles_passed_after_the_riichi_are_genbutsu(self):
        self.assertEqual(self.safety(7), "genbutsu")   # chun: p1 threw one after the declaration
        self.assertEqual(self.safety(16), "genbutsu")  # red 5m: p1 threw a 5m the turn before

    def test_an_honor_pair_with_nothing_else_showing_is_live(self):
        self.assertEqual(self.safety(9), "live-honor")  # South from a pair, no other copy out yet

    def test_melds_count_from_the_turn_they_are_declared(self):
        # p1 declares a closed kan of 4p between the hero's turns 12 and 13
        self.assertEqual(review.visible_count(24, self.mine[12], self.game), 0)
        self.assertEqual(review.visible_count(24, self.mine[13], self.game), 4)


class KanAndMultiWinnerTests(unittest.TestCase):
    """The second hanchan has closed kans, an added kan, and a double ron."""

    @classmethod
    def setUpClass(cls):
        cls.logs = tr.load_logs(FIXTURE_LINKS)

    def test_links_file_parses(self):
        self.assertEqual(len(self.logs), 10)

    def test_closed_kan_keeps_the_hand_at_thirteen_tiles(self):
        game = tr.replay(self.logs[0])
        kan_seats = [p["seat"] for p in game["players"]
                     if any(m["kind"] in "akm" for m in p["melds"])]
        self.assertIn(1, kan_seats)
        for event in game["events"]:
            total = len(event["hand_after"]) + len(event["meld_tiles"])
            self.assertEqual(total, 13, f"seat {event['seat']} turn {event['turn']}")

    def test_double_ron_sums_both_winners(self):
        result = self.logs[8][-1]
        self.assertEqual(len(tr.result_blocks(result)), 2)
        self.assertEqual(tr.result_deltas(result), [0, 1300, -9900, 10600])

    def test_exhaustive_draw_deltas_still_read(self):
        self.assertEqual(tr.result_deltas(self.logs[0][-1]), [-1000, -1000, 3000, -1000])

    def test_second_game_reconciles_to_its_final_score(self):
        hands, stats, _ = review.build_report(self.logs, hero=0)
        self.assertEqual(hands[0]["start_scores"][0] + stats["score_delta"], 10200)


if __name__ == "__main__":
    unittest.main()
