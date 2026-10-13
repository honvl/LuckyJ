"""Chapter 39 of the personal guide: the user's pushes beside the human players at both tables, chasers and callers.

Every figure the chapter cites comes from ``analysis/push-company-2026-10-13.json`` (``scripts/mine_push_company.py``).
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "push-company-2026-10-13.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
GROUPS = ("you", "jade_players", "tokujou_humans", "luckyj")


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="push-company">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheGroupsTests(unittest.TestCase):
    def test_the_first_table(self):
        g = DATA["groups"]
        self.assertEqual([g[k]["spots"] for k in GROUPS], [280, 719, 4833, 1505])
        self.assertEqual([g[k]["pushed"] for k in GROUPS], [78.2, 80.4, 78.8, 82.3])
        self.assertEqual([g[k]["on_the_push"][2] for k in GROUPS], [12.3, 11.1, 11.5, 9.2])
        self.assertEqual([g[k]["kinds"]["half suji"][2] for k in GROUPS], [11.1, 11.2, 12.0, 6.5])
        self.assertEqual([g[k]["kinds"]["live 2-3-7-8"][2] for k in GROUPS], [14.6, 9.8, 11.8, 10.1])
        self.assertEqual([g[k]["won"] for k in GROUPS], [27.9, 29.6, 29.6, 30.9])
        self.assertEqual([g[k]["thin_wins"][2] for k in GROUPS], [11.1, 23.4, 21.9, 20.3])
        self.assertEqual(g["you"]["thin_wins"][:2], [6, 54])
        # the humans' rates give about 12 wins in 54
        self.assertEqual([round(54 * g[k]["thin_wins"][2] / 100) for k in ("jade_players", "tokujou_humans")], [13, 12])

    def test_chasers(self):
        c = DATA["chasing"]
        self.assertEqual((c["you"]["hands"], c["you"]["chased"], c["you"]["chaser_won"]), (943, 17.6, 5.9))
        self.assertEqual((c["luckyj"]["hands"], c["luckyj"]["chased"], c["luckyj"]["chaser_won"]), (5026, 15.5, 5.7))
        g = DATA["groups"]
        self.assertEqual((g["you"]["two_riichis"], g["jade_players"]["two_riichis"]), (6.4, 6.4))
        self.assertEqual((g["you"]["later_deal_ins"], g["luckyj"]["later_deal_ins"]), (11.0, 11.6))

    def test_callers(self):
        g = DATA["groups"]
        self.assertEqual([g[k]["with_a_caller"] for k in GROUPS], [45.7, 48.3, 49.5, 47.2])
        self.assertEqual([g[k]["winners"]["pushes"]["an open hand"] for k in GROUPS], [6.4, 7.6, 8.2, 7.0])
        self.assertEqual([g[k]["callers"]["a caller"]["on_the_push"][1] for k in GROUPS], [11.1, 14.3, 13.3, 10.6])
        self.assertEqual([g[k]["callers"]["no caller"]["on_the_push"][1] for k in GROUPS], [13.3, 8.0, 9.9, 8.1])
        self.assertEqual((g["you"]["callers"]["no caller"]["on_the_push"][0], g["you"]["callers"]["no caller"]["pushes"]), (16, 120))
        a = (g["you"]["callers"]["a caller"], g["luckyj"]["callers"]["a caller"])
        self.assertEqual((a[0]["won"], a[0]["dealt"], a[1]["won"], a[1]["dealt"]), (27.3, 20.2, 29.0, 21.7))

    def test_the_waits(self):
        w = DATA["waits"]
        self.assertEqual((w["you"]["others|half suji"][2], w["luckyj"]["others|half suji"][2]), (9.7, 9.6))
        self.assertEqual((w["you"]["others|live 2-3-7-8"][2], w["luckyj"]["others|live 2-3-7-8"][2]), (8.1, 8.6))
        self.assertEqual((w["you"]["hero|half suji"][2], w["you"]["hero|live 2-3-7-8"][2]), (8.4, 8.2))


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("199 Jade games", "1,255", "12.3%", "11.1%, and Tokujou", "11.5%", "11.2% and 12.0%", "6.5%", "14.6% of the time",
                       "9.8%", "11.8%", "6 times in 54", "about 12 wins", "17.6%", "15.5%", "5.9% and 5.7%", "6.4%", "11.0% of pushes against 11.6%",
                       "45.7%", "48.3%", "7.6%", "27.3%", "20.2%", "29.0%", "21.7%", "16 times in 120", "13.3%", "8.0%", "8.1%",
                       "9.7%", "9.6%", "8.1% and 8.6%", "8.4% and 8.2%", "943", "5,026", "1,079"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))


if __name__ == "__main__":
    unittest.main()
