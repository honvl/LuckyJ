"""Tests for the miners behind the guide's dora chapter: win han, first-tenpai spots, caller tells, flushes."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mine_caller_tells as tells  # noqa: E402
import mine_dora_hands as dora  # noqa: E402
import mine_flush_calls as flush  # noqa: E402


def discard(index, turn, tile, tsumogiri=False, called=None):
    return {"index": index, "turn": turn, "tile": tile, "tsumogiri": tsumogiri, "called": called}


class WinHanTests(unittest.TestCase):
    def test_han_is_split_by_source(self):
        han, names = dora.win_han([2, 3, 2, "満貫8000点", "役牌:自風牌(1飜)", "ドラ(2飜)", "赤ドラ(1飜)"])
        self.assertEqual(han, {"yakuhai": 1, "dora": 2, "aka": 1})
        self.assertEqual(names, ["役牌:自風牌", "ドラ", "赤ドラ"])

    def test_numeric_yaku_ids_read_as_names(self):
        # NAGA-converted records write yaku ids: 34 is honitsu, 54 red fives, 53 ura (zero han is dropped)
        han, names = dora.win_han([1, 0, 1, "30符4飜7700点", "yaku34(2飜)", "yaku54(2飜)", "yaku53(0飜)"])
        self.assertEqual(han, {"shape": 2, "aka": 2})
        self.assertIn("混一色", names)

    def test_limit_head_without_a_han_count(self):
        han, _ = dora.win_han([0, 1, 0, "満貫8000点"])
        self.assertEqual(han, {"shape": 5})


class FirstTenpaiSpotTests(unittest.TestCase):
    def row(self, **first):
        base = {"turn": 8, "closed": True, "live": 5, "riichi": True, "threat": "quiet"}
        base.update(first)
        return {"first": base, "riichi_turn": 8 if base["riichi"] else None}

    def test_path_names_the_first_tenpai_play(self):
        self.assertEqual(dora.path(self.row()), "riichi first")
        self.assertEqual(dora.path(self.row(closed=False, riichi=False)), "open")
        dama = self.row(riichi=False)
        self.assertEqual(dora.path(dama), "dama")
        dama["riichi_turn"] = 11
        self.assertEqual(dora.path(dama), "riichi later")

    def test_cells_bucket_live_tiles_turn_and_table(self):
        self.assertEqual(dora.cell(self.row()), ("riichi", "quiet", 2, 1))
        self.assertEqual(dora.cell(self.row(live=2, turn=13, threat="2 call", riichi=False)), ("dama", "call", 0, 3))


class CallerTellTests(unittest.TestCase):
    def test_no_call_means_no_tells(self):
        events = [discard(0, 1, 41), discard(4, 2, 13)]
        self.assertFalse(any(tells.caller_tells(events, 0).values()))

    def test_a_late_call_and_two_tsumogiri(self):
        events = [discard(i * 4, i + 1, 41) for i in range(8)]
        events.append(discard(40, 9, 25, called={"kind": "c", "tile": 24}))
        events += [discard(44, 10, 19, tsumogiri=True), discard(48, 11, 28, tsumogiri=True)]
        t = tells.caller_tells(events, 1)
        self.assertTrue(t["late_call"])
        self.assertTrue(t["tsumogiri2"])
        self.assertFalse(t["two_calls"])
        self.assertFalse(t["inside_last"])  # the latest cut was a tsumogiri

    def test_an_early_call_with_cuts_from_hand(self):
        events = [discard(0, 1, 41), discard(4, 2, 45, called={"kind": "p", "tile": 45})]
        events += [discard(8, 3, 11), discard(12, 4, 39), discard(16, 5, 25)]
        t = tells.caller_tells(events, 2)
        self.assertFalse(t["late_call"])
        self.assertTrue(t["two_calls"])
        self.assertTrue(t["ted3"])
        self.assertTrue(t["inside_last"])  # 5p cut from hand
        self.assertFalse(t["tsumogiri2"])

    def test_tell_count_uses_the_three_main_tells(self):
        row = {"late_call": True, "two_calls": True, "tsumogiri2": False, "ted3": True, "inside_last": True}
        self.assertEqual(tells.tell_count(row), 2)


class NoChanceTests(unittest.TestCase):
    def test_wall_on_both_sides(self):
        from collections import Counter
        # 3p: shapes 4p-5p, 1p-2p and 2p-4p; all four 4p and all four 2p visible cover every shape
        self.assertTrue(tells.no_chance(23, Counter({24: 4, 22: 4})))
        self.assertFalse(tells.no_chance(23, Counter({24: 4})))  # 1p-2p still waits on 3p

    def test_terminal_needs_only_one_wall(self):
        from collections import Counter
        self.assertTrue(tells.no_chance(29, Counter({28: 4})))  # 9p: only 7p-8p waits on it
        self.assertTrue(tells.no_chance(11, Counter({12: 4})))  # 1m: only 2m-3m waits on it


class FlushCountTests(unittest.TestCase):
    def test_suit_plus_honors(self):
        tiles = [21, 22, 23, 24, 25, 26, 52, 28, 29, 41, 41, 41, 11, 12]
        self.assertEqual(flush.flush_count(tiles), (12, 2))  # the red 5p counts as pinzu

    def test_all_honors(self):
        self.assertEqual(flush.flush_count([41, 42, 43]), (3, None))

    def test_ties_pick_the_lower_suit(self):
        self.assertEqual(flush.flush_count([11, 12, 21, 22, 45]), (3, 1))


class ShapePlanTests(unittest.TestCase):
    def test_terminals_and_honors_count_tiles(self):
        import mine_shape_plans as shape
        self.assertEqual(shape.yaochuu([11, 19, 19, 25, 41, 45, 52]), 5)  # 1m, two 9m, East, haku; red 5p is a simple

    def test_flush_fit_and_main_suit(self):
        import mine_shape_plans as shape
        deal = [21, 22, 23, 25, 27, 29, 45, 45, 41, 13, 17, 34, 38]
        self.assertEqual(shape.flush_fit(deal), 9)  # six pinzu plus three honors
        self.assertEqual(shape.main_suit(deal), 2)
        self.assertEqual(shape.main_suit([11, 21]), 1)  # a tie goes to the lower suit

    def test_is_flush_ignores_honors(self):
        import mine_shape_plans as shape
        self.assertTrue(shape.is_flush([21, 25, 29, 41, 41, 47]))
        self.assertFalse(shape.is_flush([21, 25, 31]))


class RecentGamesTests(unittest.TestCase):
    def test_placement_by_score_with_seat_order_for_ties(self):
        import review_recent_games as recent
        players = [[1, "a", 0, 25000, 0], [2, "b", 0, 30000, 0], [3, "c", 0, 25000, 0], [4, "d", 0, 20000, 0]]
        self.assertEqual(recent.placement(players, 2), 1)
        self.assertEqual(recent.placement(players, 1), 2)  # tied with seat 3, earlier in the list
        self.assertEqual(recent.placement(players, 3), 3)
        self.assertEqual(recent.placement(players, 4), 4)

    def test_break_even_fourths(self):
        import review_recent_games as recent
        means = {1: 140.0, 2: 66.0, 3: -10.0, 4: -273.0}
        shares = {1: 0.25, 2: 0.25, 3: 0.25, 4: 0.25}
        expected = sum(shares[p] * means[p] for p in means)  # -19.25 per game
        target = recent.break_even_fourths(shares, means)
        self.assertAlmostEqual(target, 0.25 + expected / 263.0)
        moved = {**shares, 3: shares[3] + shares[4] - target, 4: target}
        self.assertAlmostEqual(sum(moved[p] * means[p] for p in means), 0.0)

    def test_late_place_ties_go_to_the_first_dealer_side(self):
        import mine_late_placement as late
        self.assertEqual(late.place([25000, 25000, 30000, 20000], 0), 2)
        self.assertEqual(late.place([25000, 25000, 30000, 20000], 1), 3)


if __name__ == "__main__":
    unittest.main()
