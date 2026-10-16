"""Chapter 43 of the personal guide: seven pairs on a dora against an honor, and the all-last tenpai with no yaku.

Every figure the chapter cites comes from ``analysis/chiitoi-tanki-2026-10-16.json`` (``scripts/mine_chiitoi_tanki.py``).
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
DATA = json.loads((ROOT / "analysis" / "chiitoi-tanki-2026-10-16.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="honor-wait">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheWaitsTests(unittest.TestCase):
    def test_the_counts(self):
        self.assertEqual((DATA["moments"], DATA["riichi_hands"]), (4364, 509))

    def test_riichi_hands_by_the_wait(self):
        r = DATA["riichi"]
        self.assertEqual([(r[k]["hands"], r[k]["won_pct"], r[k]["points_a_hand"]) for k in
                          ("dora number", "honor, not dora", "number or terminal, not dora")],
                         [(44, 18.2, 1618), (180, 56.1, 5579), (268, 47.8, 4476)])
        self.assertEqual((r["dora number"]["won"], r["dora number"]["tsumo"]), (8, 6))
        self.assertEqual((r["dora number"]["avg_win"], r["honor, not dora"]["avg_win"]), (15838, 11117))

    def test_dama_on_a_dora(self):
        d = DATA["dama"]["dora number"]
        self.assertEqual((d["hands"], d["won_pct"], d["points_a_hand"]), (71, 25.4, 1608))

    def test_the_wait_is_released(self):
        r = DATA["release"]
        self.assertEqual((r["dora"]["turns"], r["dora"]["released"], r["dora"]["per_100_turns"]), (277, 2, 0.7))
        self.assertEqual([r[k]["per_100_turns"] for k in ("dragon or round wind", "an opponent's seat wind", "number 2-8")], [7.0, 10.3, 6.4])
        others = [k for k in r if k not in ("dora", "dora honor")]
        self.assertTrue(all(6 <= r[k]["per_100_turns"] <= 10.5 for k in others))

    def test_what_luckyj_keeps(self):
        c = DATA["choices"]
        self.assertEqual((c["hands"]["luckyj"]["hands"], c["hands"]["luckyj"]["kept_other"]), (18, 10))
        self.assertEqual((c["hands"]["tokujou_human"]["hands"], c["hands"]["tokujou_human"]["kept_dora"]), (49, 40))
        self.assertEqual((c["hands"]["you"]["hands"], c["hands"]["you"]["kept_dora"]), (5, 4))
        self.assertEqual((c["riichi"]["luckyj"]["declarations"], c["riichi"]["luckyj"]["kept_other"]), (2, 2))


class TheCasesTests(unittest.TestCase):
    def test_east_four(self):
        e = DATA["cases"]["seven_pairs"]["East 4-0"]
        turn = e["turns"]["5"]
        self.assertEqual([(o["discard"], o["wait"], o["dora"], o["unseen"]) for o in turn["options"]],
                         [("6p", "Hatsu", False, 2), ("Hatsu", "6p", True, 3)])
        self.assertEqual((turn["mortal"]["played"][0], turn["mortal"]["after_riichi"][0]), (["riichi", 0.995], ["6p", 0.771]))
        self.assertEqual((e["right_riichi_after_your_turn"], e["pushed_discards"], e["deal_in"]), (5, 8, {"turn": 13, "tile": "2m", "points": 5200}))
        self.assertEqual([(h["who"], h["turn"], h["kind"]) for h in e["hatsu_after_turn_5"]], [("across", 6, "discard"), ("you", 8, "your draw")])

    def test_south_one(self):
        s = DATA["cases"]["seven_pairs"]["South 1-0"]
        self.assertTrue(s["dealer"])
        t = s["turns"]
        self.assertEqual([t[k]["mortal"]["played"][0] for k in ("5", "6", "7")], [["riichi", 0.945], ["riichi", 0.99], ["riichi", 0.763]])
        self.assertEqual([t[k]["mortal"]["after_riichi"][0] for k in ("5", "6", "7")], [["3s", 0.998], ["2s", 0.968], ["2s", 0.715]])
        self.assertEqual([[(o["wait"], o["unseen"]) for o in t[k]["options"]] for k in ("6", "7")],
                         [[("East", 2), ("2s", 3)], [("Haku", 3), ("2s", 3)]])
        self.assertEqual((s["east_after_turn_6"], s["win"]), ([], {"points": 9600, "from": "left", "after_your_turn": 7}))

    def test_the_all_last_hand(self):
        a = DATA["cases"]["all_last"]
        self.assertEqual((a["dealer"], a["start_scores"][:2], a["tiles_left_after_your_draw"]), (True, [20600, 16100], 6))
        o = a["options"]
        self.assertEqual([(o[k]["waits"], o[k]["live"], o[k]["thrown_by"]) for k in ("2p", "3p", "5p")],
                         [(["3p", "4p"], 3, ["across", "left"]), (["2p"], 1, ["right", "across"]), (["1p", "4p"], 6, [])])
        self.assertTrue(all(set(h) == {0} for k in o for h in [o[k]["ron_han"]]))
        self.assertEqual((a["winner"]["seat"], a["winner"]["calls"], a["winner"]["waits"]), ("right", 0, ["2p", "5p"]))
        self.assertEqual([(d["tile"], d["drawn_and_thrown"]) for d in a["winner"]["last_discards"]],
                         [("7s", True), ("2s", True), ("6p", True), ("6p", True), ("1m", False)])
        self.assertEqual(a["others_calls"], {"right": 0, "across": 1, "left": 2})
        self.assertEqual(a["mortal"], [["2p", 0.57], ["3p", 0.36], ["5p", 0.07]])
        self.assertEqual(a["deal_in"], {"points": 7700, "tile": "2p", "final": 12900})


class TheMinerTests(unittest.TestCase):
    def test_six_pairs_and_a_single(self):
        import mine_chiitoi_tanki as m

        hand = [11, 11, 22, 22, 33, 33, 15, 15, 26, 26, 47, 47, 46]
        self.assertEqual(m.seven_pairs_single(hand), 46)
        self.assertIsNone(m.seven_pairs_single([11, 11, 11, 11, 22, 22, 33, 33, 15, 15, 26, 26, 46]))  # two of the same pair
        self.assertIsNone(m.seven_pairs_single(hand[:-1] + [47]))

    def test_the_kind_of_a_wait(self):
        import mine_chiitoi_tanki as m

        game = {"kyoku": 4}  # South 1, the dealer is seat 0
        self.assertEqual(m.kind_of(26, {26}, game, 0), "dora")
        self.assertEqual(m.kind_of(46, set(), game, 0), "dragon or round wind")
        self.assertEqual(m.kind_of(41, set(), game, 0), "a wind nobody needs")  # East, your own seat wind
        self.assertEqual(m.kind_of(43, set(), game, 0), "an opponent's seat wind")
        self.assertEqual(m.kind_of(19, set(), game, 0), "terminal")


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("203 Jade games", "1,255 Tokujou games", "509 riichi hands", "15,838 points against 11,117", "0.7 times per 100 turns",
                       "2 times in 277 turns", "7.0 for a dragon or the round wind", "10.3", "6.4", "6 of its 8 wins",
                       "10 of 18 hands", "40 of 49", "4 of 5", "99.5%", "77% of the time", "pushed 8 tiles", "5,200",
                       "3 han, 3,200", "94.5%", "99.0%", "96.8%", "76.3%", "71.5%", "4 han and 9,600", "3 han and 4,800",
                       "+5,579", "+1,608", "6 tiles left", "20,600", "16,100", "7,700", "12,900", "267 rank points",
                       "57%", "36%", "7%", "across had 1, left 2"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = ["replay.html?g=261016-76fdbc7c-8746-4b3b-97fd-c0b15a1e161f&amp;r=East+4-0&amp;t=5",
                "replay.html?g=261016-76fdbc7c-8746-4b3b-97fd-c0b15a1e161f&amp;r=South+1-0&amp;t=6",
                "replay.html?g=261016-7cc3ee5d-65fc-4333-a381-7cb5db6923eb&amp;r=South+4-0&amp;t=18"]
        for lang in PAGES:
            links = re.findall(r'href="(replay\.html\?[^"]+)"', section(lang))
            self.assertEqual(links, want)
            for link in links:
                self.assertTrue((ROOT / "site" / "replays" / f"{link.split('g=')[1].split('&')[0]}.json").exists(), link)

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))
        self.assertLessEqual(len(re.findall(r"\bnot [a-z ]+, it is\b|\bis not [a-z ]+\. It is\b", prose("en"))), 1)


if __name__ == "__main__":
    unittest.main()
