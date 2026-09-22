"""Tests for the personal guide builder and its safety rules."""

import json
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_personal_guide as guide  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
SPOTS = ROOT / "data/personal_guide_spots.json"


def event(index, rivers, riichi_seats):
    return {"index": index, "rivers": rivers, "riichi_seats": riichi_seats}


class TileNameTests(unittest.TestCase):
    def test_site_tiles(self):
        self.assertEqual(guide.site_tile(52), "5pr")
        self.assertEqual(guide.site_tile(25), "5p")
        self.assertEqual(guide.site_tile(45), "P")
        self.assertEqual(guide.site_tile(47), "C")
        self.assertEqual(guide.site_tile(39), "9s")

    def test_spot_file_names_parse(self):
        for text, code in (("0p", 52), ("5pr", 52), ("haku", 45), ("P", 45), ("chun", 47), ("E", 41), ("9s", 39)):
            self.assertEqual(guide.parse_tile(text), code, text)


class SafetyTests(unittest.TestCase):
    def test_tile_passed_after_riichi_is_genbutsu(self):
        # Seat 1 declares riichi at event 3; seat 2 later discards 3m (13) without being ronned.
        game = {"events": [{"tile": 41}, {"tile": 42}, {"tile": 43}, {"tile": 44}, {"tile": 13}, {"tile": 29}]}
        e = event(6, {0: [], 1: [44], 2: [13], 3: []}, {0: None, 1: 3, 2: None, 3: None})
        self.assertEqual(guide.safety(13, 1, e, game, Counter()), "genbutsu")

    def test_tile_passed_before_riichi_is_not_genbutsu(self):
        game = {"events": [{"tile": 13}, {"tile": 42}, {"tile": 43}, {"tile": 44}, {"tile": 29}]}
        e = event(5, {0: [13], 1: [44], 2: [], 3: []}, {0: None, 1: 3, 2: None, 3: None})
        self.assertNotEqual(guide.safety(13, 1, e, game, Counter()), "genbutsu")

    def test_open_hand_uses_its_own_river_only(self):
        game = {"events": [{"tile": 13}]}
        e = event(1, {0: [13], 1: [], 2: [], 3: []}, {0: None, 1: None, 2: None, 3: None})
        self.assertEqual(guide.safety(16, 1, e, game, Counter()), "live 4-5-6")

    def test_honor_labels_count_other_copies(self):
        game = {"events": []}
        e = event(0, {0: [], 1: [], 2: [], 3: []}, {0: None, 1: None, 2: None, 3: None})
        self.assertEqual(guide.safety(47, 1, e, game, Counter({47: 3})), "dead")
        self.assertEqual(guide.safety(47, 1, e, game, Counter({47: 2})), "honor, 2 seen")
        self.assertEqual(guide.safety(47, 1, e, game, Counter({47: 1})), "live honor")

    def test_middle_suji_needs_both_sides(self):
        game = {"events": []}
        one_side = event(0, {0: [], 1: [32], 2: [], 3: []}, {0: None, 1: None, 2: None, 3: None})
        both = event(0, {0: [], 1: [32, 38], 2: [], 3: []}, {0: None, 1: None, 2: None, 3: None})
        self.assertEqual(guide.safety(35, 1, one_side, game, Counter()), "half suji")
        self.assertEqual(guide.safety(35, 1, both, game, Counter()), "nakasuji")

    def test_tile_passed_after_riichi_anchors_suji(self):
        # Seat 1 has 7p in the river and declares at event 1; seat 2 later passes 1p, so 4p is nakasuji.
        game = {"events": [{"tile": 27}, {"tile": 27}, {"tile": 21}]}
        e = event(3, {0: [], 1: [27], 2: [21], 3: []}, {0: None, 1: 1, 2: None, 3: None})
        self.assertEqual(guide.safety(24, 1, e, game, Counter()), "nakasuji")
        before = event(3, {0: [21], 1: [27], 2: [], 3: []}, {0: None, 1: None, 2: None, 3: None})
        self.assertEqual(guide.safety(24, 1, before, game, Counter()), "half suji")

    def test_virtual_nakasuji_needs_the_outer_suji_and_an_early_five(self):
        game = {"events": []}
        riichi = {0: None, 1: None, 2: None, 3: None}
        four = event(0, {0: [], 1: [25, 21], 2: [], 3: []}, riichi)  # early 5p, 1p: 4p
        six = event(0, {0: [], 1: [25, 29], 2: [], 3: []}, riichi)  # early 5p, 9p: 6p
        late_five = event(0, {0: [], 1: [21, 41, 42, 43, 44, 45, 25], 2: [], 3: []}, riichi)
        inner = event(0, {0: [], 1: [25, 27], 2: [], 3: []}, riichi)  # 7p covers the same side as the 5p
        self.assertEqual(guide.safety(24, 1, four, game, Counter()), "virtual nakasuji")
        self.assertEqual(guide.safety(26, 1, six, game, Counter()), "virtual nakasuji")
        self.assertEqual(guide.safety(24, 1, late_five, game, Counter()), "half suji")
        self.assertEqual(guide.safety(24, 1, inner, game, Counter()), "half suji")


class VisibleCounterTests(unittest.TestCase):
    def test_called_tile_counts_once(self):
        # Seat 2 discarded 5s (35) and seat 3 ponned it: it sits in the river and in the meld.
        players = [{"melds": []}, {"melds": []}, {"melds": []}, {"melds": [{"kind": "p", "called": 35}]}]
        e = {"rivers": {0: [], 1: [], 2: [35], 3: []}}
        snap = {0: [], 1: [], 2: [], 3: [[35, 35, 35]]}
        seen = guide.visible_counter([], e, players, snap, [])
        self.assertEqual(seen[35], 3)


@unittest.skipUnless(MANIFEST.exists(), "self-game records are local only")
class GuideSpotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = json.loads(SPOTS.read_text(encoding="utf-8"))
        cls.spec = spec
        cls.data = guide.build(spec, json.loads(MANIFEST.read_text(encoding="utf-8")))

    def examples(self):
        return [ex for exs in self.data["chapters"].values() for ex in exs]

    def test_every_spot_builds_with_its_recorded_cut(self):
        self.assertEqual(len(self.examples()), len(self.spec["spots"]))
        for spot in self.spec["spots"]:
            ex = next(e for e in self.examples() if e["id"] == spot["id"])
            for fspec, frame in zip(spot["frames"], ex["frames"]):
                if fspec.get("expect_cut"):
                    self.assertEqual(frame["you"]["tile"], guide.site_tile(guide.parse_tile(fspec["expect_cut"])), spot["id"])

    def test_better_cut_is_never_less_safe(self):
        rank = guide.DANGER
        for ex in self.examples():
            for frame in ex["frames"]:
                if frame["kind"] != "discard" or not frame.get("better") or ex["id"] == "keep-eight-tiles":
                    continue
                # a turn with nobody in riichi or open has no safety to compare
                you = max((rank[label] for label in frame["you"]["safety"]), default=0)
                better = max((rank[label] for label in frame["better"]["safety"]), default=0)
                self.assertLessEqual(better, you, f"{ex['id']} turn {frame['turn']}")

    def test_furiten_safe_tile_is_labelled_genbutsu(self):
        ex = next(e for e in self.examples() if e["id"] == "two-p-three-turns")
        frame = ex["frames"][0]
        riichi = next(i for i, t in enumerate(frame["threats"]) if t["kind"] == "riichi")
        self.assertEqual(frame["you"]["tile"], "3s")
        self.assertEqual(frame["you"]["safety"][riichi], "genbutsu")

    def test_tables_match_the_site_format(self):
        for ex in self.examples():
            for frame in ex["frames"]:
                table = frame["table"]
                self.assertEqual({p["seat"] for p in table["players"]}, {"self", "shimocha", "toimen", "kamicha"})
                me = next(p for p in table["players"] if p["seat"] == "self")
                tiles = me["hand"].split()
                meld_tiles = sum(len(m["tiles"]) for m in me["melds"] if m["kind"] != "kakan")
                expected = 13 if frame["kind"] == "call" else 14
                self.assertEqual(len(tiles) + meld_tiles - sum(1 for m in me["melds"] if len(m["tiles"]) == 4), expected, ex["id"])


class PageChapterTests(unittest.TestCase):
    """Every chapter with examples has a place on the page, and every placeholder has examples."""

    def test_spot_chapters_match_the_page_placeholders(self):
        import re

        page = (ROOT / "site/honver.html").read_text(encoding="utf-8")
        placeholders = set(re.findall(r'data-guide-examples="([^"]+)"', page))
        chapters = {s["chapter"] for s in json.loads(SPOTS.read_text(encoding="utf-8"))["spots"]}
        self.assertEqual(placeholders, chapters)

    def test_new_chapters_are_listed_at_the_top(self):
        page = (ROOT / "site/honver.html").read_text(encoding="utf-8")
        for anchor in ("dora-points", "dora-shape", "dora-tells", "shape-start"):
            self.assertIn(f'id="{anchor}"', page)
            self.assertIn(f'href="#{anchor}"', page)


class OpenTenpaiHanTests(unittest.TestCase):
    def test_only_real_red_fives_take_the_red_ids(self):
        import mine_open_tenpai_push as otp

        ids = otp.to136([15, 15, 51, 25, 52, 35, 11], Counter())
        self.assertEqual(ids[:3], [17, 18, 16])  # plain 5m, plain 5m, red 5m
        self.assertEqual(ids[3:5], [53, 52])  # plain 5p, red 5p
        self.assertEqual(ids[5], 89)  # plain 5s never lands on 88
        self.assertEqual(ids[6], 0)


if __name__ == "__main__":
    unittest.main()
