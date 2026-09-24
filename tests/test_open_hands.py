"""Tests for the miners behind the guide's open-hands chapter: call chances, kuikae, routes, buckets."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mine_call_chances as calls  # noqa: E402
import mine_open_vs_open as ovo  # noqa: E402


class CallOptionTests(unittest.TestCase):
    def test_pon_keeps_the_red_five_in_hand(self):
        self.assertEqual(calls.call_options([15, 51, 15, 22], 15, from_left=False), [("p", [15, 15])])

    def test_chi_only_off_the_left_seat(self):
        self.assertEqual(calls.call_options([13, 14, 22], 15, from_left=False), [])
        self.assertEqual(calls.call_options([13, 14, 22], 15, from_left=True), [("c", [13, 14])])

    def test_every_chi_shape_is_offered(self):
        opts = calls.call_options([13, 14, 16, 17], 15, from_left=True)
        self.assertEqual(sorted(used for _, used in opts), [[13, 14], [14, 16], [16, 17]])

    def test_honors_cannot_be_chied(self):
        self.assertEqual(calls.call_options([45, 46, 47], 46, from_left=True), [])


class KuikaeTests(unittest.TestCase):
    def test_pon_forbids_the_same_tile(self):
        self.assertEqual(calls.kuikae("p", 47, [47, 47]), {47})

    def test_chi_on_an_end_forbids_the_other_end(self):
        self.assertEqual(calls.kuikae("c", 13, [14, 15]), {13, 16})
        self.assertEqual(calls.kuikae("c", 15, [13, 14]), {15, 12})

    def test_chi_in_the_middle_forbids_only_the_tile(self):
        self.assertEqual(calls.kuikae("c", 14, [13, 15]), {14})

    def test_no_extension_past_the_suit(self):
        self.assertEqual(calls.kuikae("c", 17, [18, 19]), {17})
        self.assertEqual(calls.kuikae("c", 13, [11, 12]), {13})


class RouteTests(unittest.TestCase):
    def test_yakuhai_pon(self):
        # East 1: seat 0 sits East, the round wind is East
        self.assertEqual(calls.route("p", 41, [41, 41, 41], [22, 23], 0, 0), "yakuhai pon")
        self.assertEqual(calls.route("p", 47, [47, 47, 47], [22, 23], 2, 0), "yakuhai pon")

    def test_guest_wind_pon_is_not_yakuhai(self):
        self.assertNotEqual(calls.route("p", 43, [43, 43, 43], [22, 23], 1, 0), "yakuhai pon")

    def test_tanyao_allows_one_tile_to_clear(self):
        self.assertEqual(calls.route("c", 15, [13, 14, 15], [22, 23, 24, 36, 37, 11], 0, 0), "tanyao")
        self.assertEqual(calls.route("c", 15, [13, 14, 15], [22, 23, 24, 36, 11, 19], 0, 0), "other")

    def test_flush(self):
        self.assertEqual(calls.route("c", 13, [11, 12, 13], [14, 15, 16, 18, 19, 45], 0, 0), "flush")

    def test_open_hand_reaching_tanyao_has_a_yaku(self):
        # after a 2m-3m-4m chi: 345p, 67s, 55m, 6p-8p and a loose 2s is a 1-shanten that can reach tanyao
        rest = (15, 15, 23, 24, 25, 26, 28, 32, 36, 37)
        self.assertTrue(calls.yaku_reachable(rest, (12, 13, 14), "c", 1, 0, frozenset()))

    def test_open_hand_with_no_yaku_in_reach(self):
        # after a 1m-2m-3m chi nothing but a lone west could give a yaku, and one draw cannot make it a triplet
        rest = (15, 15, 21, 22, 23, 26, 28, 36, 37, 43)
        self.assertFalse(calls.yaku_reachable(rest, (11, 12, 13), "c", 1, 0, frozenset()))

    def test_rows_and_buckets(self):
        self.assertEqual([calls.row_of(t) for t in (1, 6, 7, 12, 13, 18)], [1, 1, 2, 2, 3, 3])
        self.assertEqual([calls.acc1_bucket(a) for a in (11, 12, 19, 20)],
                         ["under 12 tiles", "12-19 tiles", "12-19 tiles", "20+ tiles"])
        self.assertEqual([calls.acc2_bucket(a) for a in (23, 24, 39, 40)],
                         ["under 24 tiles", "24-39 tiles", "24-39 tiles", "40+ tiles"])


class OpenAgainstOpenTests(unittest.TestCase):
    def test_value_and_tell_buckets(self):
        self.assertEqual([ovo.value_bucket(h) for h in (0, 1, 2, 3, 6)], ["no yaku", "1 han", "2 han", "3+ han", "3+ han"])
        self.assertEqual([ovo.tells_bucket(n) for n in (0, 1, 2, 3)], ["no tells", "1 tell", "2-3 tells", "2-3 tells"])

    def test_yakuhai_depend_on_the_seat_and_the_round(self):
        # East 1, dealer seat 0: seat 1 sits South, the round wind is East
        self.assertEqual(ovo.yakuhai_for(1, 0), {45, 46, 47, 42, 41})
        self.assertTrue(ovo.yakuhai_triplet({"kind": "p", "tiles": [42, 42, 42]}, 1, 0))
        self.assertFalse(ovo.yakuhai_triplet({"kind": "p", "tiles": [43, 43, 43]}, 1, 0))
        self.assertFalse(ovo.yakuhai_triplet({"kind": "c", "tiles": [13, 14, 15]}, 1, 0))

    def test_a_closed_kan_does_not_open_the_hand(self):
        self.assertFalse(ovo.is_open([{"kind": "a", "tiles": [45, 45, 45, 45]}]))
        self.assertTrue(ovo.is_open([{"kind": "a", "tiles": [45, 45, 45, 45]}, {"kind": "c", "tiles": [13, 14, 15]}]))


if __name__ == "__main__":
    unittest.main()
