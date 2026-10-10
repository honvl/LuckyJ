"""Chapter 30 of the personal guide: whether the user spends fewer safe tiles than LuckyJ.

Every figure the chapter cites comes from ``analysis/defense-check-2026-10-10.json`` (``scripts/mine_defense_check.py``).
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "defense-check-2026-10-10.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def half_up(v: float) -> int:
    return int(v + 0.5)


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="defense-check">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheFiguresTests(unittest.TestCase):
    def test_the_window_and_the_hands(self):
        self.assertEqual((DATA["window"]["first"], DATA["window"]["last"], DATA["window"]["games"]),
                         ("2026-10-07 18:25", "2026-10-10 14:43", 16))
        self.assertEqual(DATA["places"]["new"]["places"], [4, 3, 7, 2])
        hands = DATA["hands"]["new"]
        self.assertEqual((hands["hands"], hands["won"], hands["dealt_in"], hands["big_deal_ins"]), (179, 37, 19, 5))
        self.assertEqual((round(100 * hands["deal_in_rate"], 1), round(100 * hands["won_rate"], 1)), (10.6, 20.7))
        self.assertEqual((round(hands["avg_win"]), round(hands["avg_deal_in"]), round(hands["points_a_hand"])), (6719, -4705, 273))
        self.assertEqual(round(100 * hands["big_deal_in_rate"], 1), 2.8)
        self.assertEqual(round(DATA["hands"]["luckyj"]["won_rate"] * hands["hands"]), 41)
        rank = DATA["rank_points"]
        self.assertEqual((rank["before_new"], rank["after_new"], rank["change"]), (5805, 5996, 191))
        m = DATA["mortal"]
        self.assertEqual((round(100 * m["matched"] / m["discards"], 1), m["discards"], m["calls_matched"], m["calls"]), (73.0, 2101, 556, 591))

    def test_the_three_tests(self):
        r = DATA["riichi"]
        self.assertEqual([r[w]["one"]["live"] for w in ("before", "ch29", "new", "luckyj")], [6.8, 5.2, 6.6, 7.8])
        self.assertEqual([r[w]["two_or_more"]["live"] for w in ("before", "ch29", "new", "luckyj")], [2.9, 8.6, 3.3, 3.6])
        self.assertEqual([r[w]["weaker_kind"] for w in ("before", "ch29", "new", "luckyj")], [3.9, 9.5, 5.0, 4.0])
        self.assertEqual((r["new"]["discards"], r["luckyj"]["discards"]), (389, 24560))
        c = DATA["callers"]
        self.assertEqual([(half_up(c[w][h]["live"]), half_up(c[w][h]["luckyj"])) for h in ("far", "one") for w in ("before", "ch29", "new")],
                         [(68, 75), (87, 78), (71, 74), (65, 66), (73, 65), (67, 67)])
        self.assertEqual((c["new"]["far"]["turns"], c["new"]["one"]["turns"], c["new"]["discards"], c["new"]["dealt"]), (78, 43, 373, 2))
        h = DATA["held"]
        self.assertEqual([(h[w]["safe"], h[w]["safe_luckyj"]) for w in ("before", "ch29", "new")], [(2.96, 3.0), (2.72, 2.87), (2.95, 3.03)])
        self.assertEqual([(h[w]["none_rate"], h[w]["none_rate_luckyj"]) for w in ("before", "ch29", "new")], [(9.4, 9.0), (8.7, 9.4), (13.1, 8.5)])
        self.assertEqual((h["new"]["none"], h["new"]["riichis"], h["luckyj_riichis"]), (14, 107, 6668))
        # under two standard errors: 14 against 107 times LuckyJ's rate
        expected = h["new"]["riichis"] * h["new"]["none_rate_luckyj"] / 100
        sd = (expected * (1 - h["new"]["none_rate_luckyj"] / 100)) ** 0.5
        self.assertLess((h["new"]["none"] - expected) / sd, 2)

    def test_the_deal_ins(self):
        s = DATA["deal_in_summary"]
        self.assertEqual((s["total"], s["mortal_half"], s["mortal_low"], s["paid"]), (19, 13, 6, 89400))
        deals = {(d["game"][:15], d["round"]): d for d in DATA["deal_ins"]}
        slips = [deals[("261008-d9f44c77", "East 3-0")], deals[("261010-6323aa6f", "South 1-0")]]
        self.assertEqual(sum(d["paid"] for d in slips), 4600)
        self.assertEqual([d["mortal_top"][0][0] for d in slips], ["1s", "7s"])
        near = deals[("261010-201c40e5", "East 3-1")]
        self.assertEqual((near["tile"], near["paid"], near["mortal_top"][0], round(100 * near["mortal"])), ("4m", 2300, ["8p", 0.723], 3))
        today = [d for d in DATA["deal_ins"] if d["date"].startswith("2026-10-10 14:")]
        self.assertEqual((len(today), sum(d["paid"] for d in today)), (5, 28900))
        self.assertTrue(all(d["mortal"] >= 0.5 for d in today))
        hatsu = deals[("261011-285cf167", "East 4-2")]
        self.assertEqual([t for t, _ in hatsu["mortal_top"][:2]], ["F", "8s"])
        self.assertEqual((round(100 * hatsu["mortal"]), round(100 * hatsu["mortal_top"][1][1])), (58, 41))


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("10.6% of your hands", "10.9% before", "10.3%", "4 firsts, 3 seconds, 7 thirds and 2 fourths",
                       "+190 rank points", "5,800 to 6,000", "28,900", "73.0% of 2,101 turns", "556 of 591", "37 wins",
                       "about 41", "6,719", "8.6% of those turns", "twice in 373 discards", "14 of 107", "8.5%",
                       "2.95 against 3.03", "13 were choices", "4,600 points", "72% to your 3%", "2,300", "7,700",
                       "98%", "8,000", "96%", "179", "389", "24,560", "1,255", "78 from a far hand", "43 from one-shanten",
                       "6,668"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_name_your_tiles(self):
        for lang in PAGES:
            links = re.findall(r'r=((?:East|South)\+\d-\d)&amp;t=(\d+)" target="_blank" rel="noopener" data-you="([^"]+)"', section(lang))
            self.assertEqual(links, [("East+3-1", "4", "4m"), ("East+2-0", "8", "1m")], lang)


if __name__ == "__main__":
    unittest.main()
