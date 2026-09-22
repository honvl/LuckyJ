"""Regression tests for the Mahjong Soul corpus tooling and the win-speed review.

Two single-hand fixtures under ``tests/fixtures`` come from real Jade-room games
converted by tensoul. Each exposed a replay bug: an open kan called from the
right-hand player, and a riichi declaration tile that was ronned.
"""

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import review_win_speed as ws  # noqa: E402
import tenhou_replay as tr  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
GAME = ROOT / "data/self_games/2026-09-07-hanchan.json"
GAME_2 = ROOT / "data/self_games/2026-09-07-hanchan-2.txt"


def fixture(name):
    return json.loads((FIXTURES / f"{name}-hand.json").read_text(encoding="utf-8"))["log"]


class MeldSourceTests(unittest.TestCase):
    def test_open_kan_source_follows_the_same_rule_as_pon(self):
        self.assertEqual(tr.parse_meld("m45454545")["from_offset"], 3)  # left player
        self.assertEqual(tr.parse_meld("45m454545")["from_offset"], 2)  # across
        self.assertEqual(tr.parse_meld("454545m45")["from_offset"], 1)  # right player
        self.assertEqual(tr.parse_meld("2828p28")["from_offset"], 1)

    def test_open_kan_hand_replays_and_reconciles(self):
        log = fixture("daiminkan")
        game = tr.replay(log)
        for player in game["players"]:
            self.assertEqual(player["ci"], len(player["discards"]))
            self.assertLessEqual(len(player["hand"]), 13)
        kan = [m for m in game["players"][0]["melds"] if m["kind"] == "m"]
        self.assertEqual(len(kan), 1)
        self.assertEqual(kan[0]["src"], 1)
        # the winner's tenpai hand is 13 tiles with the kan counted as three
        self.assertEqual(tr.shanten(game["players"][0]["hand"], game["players"][0]["meld_tiles"], closed=False), 0)


class CallPriorityTests(unittest.TestCase):
    def test_pon_beats_a_pending_chi_for_the_same_tile(self):
        log = fixture("pon-over-chi")
        game = tr.replay(log)
        for player in game["players"]:
            self.assertEqual(player["ci"], len(player["discards"]))
            self.assertLessEqual(len(player["hand"]), 13)
        calls = [(e["seat"], e["called"]["kind"], e["called"]["tile"]) for e in game["events"] if e["called"]]
        self.assertIn((3, "p", 15), calls)
        self.assertIn((1, "c", 15), calls)
        self.assertLess(calls.index((3, "p", 15)), calls.index((1, "c", 15)))


class RiichiStickTests(unittest.TestCase):
    def test_ronned_riichi_tile_pays_no_stick(self):
        log = fixture("riichi_ronned")
        self.assertEqual(tr.riichi_sticks_paid(log), [1, 0, 0, 0])
        self.assertEqual(tr.result_deltas(log[-1]), [13000, 0, -12000, 0])

    def test_established_riichi_pays_one_stick(self):
        for log in tr.load_logs(GAME):
            declared = [any(isinstance(d, str) and d.startswith("r") for d in log[6 + 3 * s]) for s in range(4)]
            paid = tr.riichi_sticks_paid(log)
            ronned = set()
            for _, detail in tr.result_blocks(log[-1]):
                if detail[0] != detail[1]:
                    ronned.add(detail[1])
            for seat in range(4):
                if declared[seat] and seat not in ronned:
                    self.assertEqual(paid[seat], 1)
                if not declared[seat]:
                    self.assertEqual(paid[seat], 0)


class AcceptanceTests(unittest.TestCase):
    def test_ryanmen_tenpai_counts_unseen_copies_of_both_waits(self):
        # 123m 456p 789s 22p 56s waits on 4s and 7s; one 7s is already in hand
        hand = [11, 12, 13, 24, 25, 26, 37, 38, 39, 22, 22, 35, 36]
        visible = Counter(tr.base(t) for t in hand)
        s, live, kinds = ws.acceptance(hand, (), True, visible)
        self.assertEqual(s, 0)
        self.assertEqual(sorted(kinds), [34, 37])
        self.assertEqual(live, 7)

    def test_visible_copies_reduce_acceptance(self):
        hand = [11, 12, 13, 24, 25, 26, 37, 38, 39, 22, 22, 35, 36]
        visible = Counter(tr.base(t) for t in hand)
        visible[34] += 3
        _, live, _ = ws.acceptance(hand, (), True, visible)
        self.assertEqual(live, 4)

    def test_best_discard_prefers_the_widest_same_shanten_cut(self):
        # 14 tiles: 123m 456p 789s 22p 56s + 1s; 1s is the only shanten-neutral cut
        hand = [11, 12, 13, 24, 25, 26, 37, 38, 39, 22, 22, 35, 36, 31]
        visible = Counter(tr.base(t) for t in hand)
        best = ws.best_discard(hand, (), True, visible)
        self.assertEqual(best["shanten"], 0)
        self.assertEqual(best["ukeire"], 7)
        self.assertEqual(best["by_tile"][31][0], 0)


class VisibleCounterTests(unittest.TestCase):
    @staticmethod
    def seen_at(game, e):
        melds_now = ws.meld_snapshots(game, e["index"])
        return ws.visible_counter(e["hand_before"], e["rivers"], melds_now, game["dora_indicators"][:1],
                                  game["players"])

    def test_called_tile_counts_once(self):
        # seat 0 releases 5m twice: seat 3 pons the first (0m 5m 5m) and seat 1 chis the
        # second (3m 4m 5m). Both copies stay in seat 0's river as well as in the melds.
        game = tr.replay(fixture("pon-over-chi"))
        e = next(x for x in game["events"] if x["seat"] == 0 and x["index"] > 30)
        self.assertEqual(self.seen_at(game, e)[15], 4)

    def test_no_tile_is_seen_more_than_four_times(self):
        logs = tr.load_logs(GAME) + tr.load_logs(GAME_2) + [
            fixture(n) for n in ("daiminkan", "pon-over-chi", "riichi_ronned")]
        for log in logs:
            game = tr.replay(log)
            for e in game["events"]:
                seen = self.seen_at(game, e)
                self.assertLessEqual(max(seen.values()), 4, f"{game['round_name']} event {e['index']}")


class WinSpeedRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.logs = tr.load_logs(GAME)
        cls.records = [ws.hand_records(log, {0}) for log in cls.logs]

    def test_every_hand_yields_four_seat_records(self):
        for recs in self.records:
            self.assertEqual([r["seat"] for r in recs], [0, 1, 2, 3])

    def test_winners_and_turns_are_consistent(self):
        for log, recs in zip(self.logs, self.records):
            winners = {detail[0] for _, detail in tr.result_blocks(log[-1])}
            for r in recs:
                self.assertEqual(r["won"], r["seat"] in winners)
                if r["won"]:
                    self.assertEqual(r["win_turn"], r["turns"] + 1)
                    self.assertIsNotNone(r["tenpai_turn"])
                    self.assertLessEqual(r["tenpai_turn"], r["turns"] + 1)
                if r["riichi_turn"] is not None:
                    self.assertLessEqual(r["tenpai_turn"], r["riichi_turn"])
                    self.assertIsNotNone(r["riichi_live"])

    def test_efficiency_is_only_scored_for_requested_seats(self):
        for recs in self.records:
            self.assertEqual(sum(r["eff_events"] for r in recs if r["seat"] != 0), 0)

    def test_summary_matches_the_fixture_game(self):
        hero = ws.summarize([r for recs in self.records for r in recs if r["seat"] == 0])
        self.assertEqual(hero["hands"], 11)
        self.assertEqual(hero["win_rate_pct"], 9.1)
        self.assertEqual(hero["tenpai_rate_pct"], 54.5)
        self.assertEqual(hero["riichi_rate_pct"], 27.3)
        self.assertEqual(hero["open_rate_pct"], 45.5)
        self.assertEqual(hero["draw_tenpai_rate_pct"], 100.0)
        self.assertEqual(sum(c["n"] for c in hero["tenpai_conversion"].values()), 6)


@unittest.skipUnless((ROOT / "data/report_cache").exists(), "NAGA report cache is local-only")
class NagaConversionTests(unittest.TestCase):
    """Runs only where the analyzer cache exists; converts the first few reports."""

    def test_converted_games_replay_and_reconcile(self):
        import naga_to_tenhou as n2t

        rows = n2t.naga.parse_rows()[:3]
        for row in rows:
            result, err = n2t.convert_report(row)
            self.assertIsNone(err, f"{row['report_id']}: {err}")
            game = result["game"]
            self.assertEqual(len(game["name"]), 4)
            self.assertIn("LuckyJ", game["name"][result["manifest"]["hero_seat"]])
            for log in game["log"]:
                replayed = tr.replay(log)
                self.assertTrue(all(p["ci"] == len(p["discards"]) for p in replayed["players"]))


if __name__ == "__main__":
    unittest.main()
