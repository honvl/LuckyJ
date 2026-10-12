"""Chapter 36 of the personal guide: pushes and folds against a riichi, in rank points.

Every figure the chapter cites comes from ``analysis/push-ev-2026-10-12.json`` (``scripts/mine_push_ev.py``).
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "push-ev-2026-10-12.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str, chapter: str = "push-ev") -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index(f'<section class="point" id="{chapter}">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheModelTests(unittest.TestCase):
    def test_the_model(self):
        self.assertEqual((DATA["pool_hands"], DATA["sims"]), (2082, 4000))
        # an even start is worth about the average of the place values, less the points below 30,000
        for v in DATA["start_ev"]:
            self.assertTrue(-25 < v < -10, v)


class TheFiguresTests(unittest.TestCase):
    def cell(self, who, cell, side):
        b = DATA[who][cell][side]
        return (b["hands"], b["ev_change"], b["se"], b["fourth_change"])

    def test_the_first_table(self):
        self.assertEqual(self.cell("you", "thin", "pushes"), (42, -18.6, 8.4, 4.1))
        self.assertEqual(self.cell("you", "thin", "folds"), (15, -6.6, 8.9, -1.1))
        self.assertEqual(self.cell("luckyj", "thin", "pushes"), (196, 3.0, 4.0, -0.3))
        self.assertEqual(self.cell("luckyj", "thin", "folds"), (40, -12.9, 8.2, 3.0))
        self.assertEqual(self.cell("you", "all", "pushes"), (219, -0.4, 4.2, 0.3))
        self.assertEqual(self.cell("you", "all", "folds"), (61, -7.3, 3.8, 0.1))
        self.assertEqual(self.cell("luckyj", "all", "pushes"), (1238, 1.0, 1.6, 0.4))
        self.assertEqual(self.cell("luckyj", "all", "folds"), (267, -8.5, 2.6, 1.6))

    def test_the_gaps(self):
        you, lj = DATA["you"], DATA["luckyj"]
        gap = you["thin"]["folds"]["ev_change"] - you["thin"]["pushes"]["ev_change"]
        se = (you["thin"]["folds"]["se"] ** 2 + you["thin"]["pushes"]["se"] ** 2) ** 0.5
        self.assertEqual(round(gap), 12)
        self.assertLess(gap / se, 1.1)  # about one standard error
        self.assertEqual(round(you["all"]["pushes"]["ev_change"] - you["all"]["folds"]["ev_change"]), 7)
        self.assertEqual(round(lj["all"]["pushes"]["ev_change"] - lj["all"]["folds"]["ev_change"], 1), 9.5)
        self.assertEqual(you["all"]["pushes"]["hands"] + you["all"]["folds"]["hands"], 280)

    def test_by_place(self):
        you, lj = DATA["you"]["all"]["by_place"], DATA["luckyj"]["all"]["by_place"]
        self.assertEqual([you[p]["pushed_pct"] for p in "1234"], [80.5, 78.8, 65.4, 89.7])
        self.assertEqual([you[p]["pushes"]["ev_change"] for p in "1234"], [-1.8, -0.1, 10.5, -8.3])
        self.assertEqual([abs(you[p]["folds"]["ev_change"]) if p == "2" else you[p]["folds"]["ev_change"] for p in "1234"],
                         [-18.7, 0.0, -1.7, -14.6])
        self.assertEqual([lj[p]["pushed_pct"] for p in "1234"], [83.7, 80.1, 81.7, 83.2])
        self.assertTrue(all(lj[p]["folds"]["ev_change"] < 0 for p in "1234"))
        stages = [DATA["luckyj"]["all"]["by_stage"][s]["pushed_pct"] for s in ("East", "South 1-3", "South 4 on")]
        self.assertEqual([round(s) for s in stages], [83, 81, 81])

    def test_where_pushes_cost(self):
        t = DATA["you"]["thin"]
        self.assertEqual((t["by_place"]["2"]["pushes"]["hands"], t["by_place"]["2"]["pushes"]["ev_change"]), (10, -42.2))
        s = t["by_stage"]["South 1-3"]
        self.assertEqual((s["pushes"]["hands"], s["pushes"]["ev_change"], s["folds"]["hands"], s["folds"]["ev_change"]), (18, -24.6, 10, 0.4))
        lj = DATA["luckyj"]["thin"]
        self.assertEqual((lj["by_place"]["2"]["pushes"]["ev_change"], lj["by_stage"]["South 1-3"]["pushes"]["ev_change"]), (-2.8, 2.5))

    def test_chapter_35_cards(self):
        spots = {(r["game"][:15], r["round"], r["turn"]): r for r in DATA["your_spots"]}
        fold = spots[("261002-b0ec9f2d", "South 3-0", 14)]
        self.assertEqual((fold["pushed"], fold["place_before"], fold["ev_change"]), (False, 3, 70.3))
        push = spots[("260907-0d113184", "East 2-1", 13)]
        self.assertEqual((push["pushed"], push["place_before"], push["ev_change"], push["fourth_change"]), (True, 2, -95.4, 25.7))


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("4,000 times", "199 Jade games", "2,082 hands", "6.6 rank points", "42 pushes 18.6", "4.1 points",
                       "1.1", "12 rank points", "gained 3.0", "lost 12.9", "70.3", "95.4", "25.7", "280 push-or-fold",
                       "0.4 rank points", "7.3", "gained 1.0", "lost 8.5", "+0.1 points against +0.3", "80% to 84%",
                       "81% to 83%", "65.4%", "+10.5", "42.2", "24.6", "2.8 and +2.5", "about 7", "about 9.5", "1,255"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_chapter_35_is_corrected(self):
        for lang in PAGES:
            page = PAGES[lang].read_text(encoding="utf-8")
            start = page.index('<mark id="fix-35-folds"')
            mark = page[start:page.index("</mark>", start)]
            self.assertIn("6.6", mark)
            self.assertIn("18.6", mark)
            self.assertIn("36", mark)
            self.assertIn('href="#fix-35-folds"', page)

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))


if __name__ == "__main__":
    unittest.main()
