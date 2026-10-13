"""Chapter 40 of the personal guide: how LuckyJ reads a half-suji.

Every figure the chapter cites comes from ``analysis/half-suji-2026-10-13.json`` (``scripts/mine_half_suji.py``).
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "half-suji-2026-10-13.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="half-suji">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheFiguresTests(unittest.TestCase):
    def test_the_rates(self):
        s = DATA["sides"]
        self.assertEqual([(s[g]["throws"], s[g]["hit"]) for g in ("luckyj", "tokujou_humans", "jade_players", "you")],
                         [(566, 6.7), (1913, 10.2), (278, 9.7), (95, 8.4)])
        ctx = lambda g: [s[g]["contexts"][k] for k in ("kept tenpai", "folding, genbutsu in hand", "folding, no genbutsu in hand")]
        self.assertEqual(ctx("luckyj"), [[322, 8.4], [106, 6.6], [138, 2.9]])
        self.assertEqual(ctx("tokujou_humans"), [[1038, 11.8], [547, 8.2], [328, 8.5]])
        self.assertEqual(ctx("you"), [[63, 7.9], [16, 6.2], [16, 12.5]])

    def test_the_choices(self):
        s = DATA["sides"]
        c = lambda g: (s[g]["choices"]["sets"], s[g]["choices"]["thrown_hit"], s[g]["choices"]["kept_hit"])
        self.assertEqual([c(g) for g in ("luckyj", "tokujou_humans", "jade_players", "you")],
                         [(412, 6.1, 10.4), (1306, 10.7, 9.4), (184, 10.9, 9.6), (62, 8.1, 7.8)])
        p = DATA["humans_pooled"]
        self.assertEqual((p["sets"], p["thrown_hit"], p["checklist_pick"], p["random_pick"]), (1552, 10.6, 8.4, 9.8))
        self.assertEqual((s["you"]["choices"]["checklist_pick"], s["jade_players"]["choices"]["checklist_pick"]), (11.0, 10.4))

    def test_the_cues(self):
        c = DATA["cues"]
        self.assertEqual(c["every half-suji"], [6140, 9.5])
        self.assertEqual([c[k] for k in ("open two-sided wait impossible (no-chance)", "a wall on the open side (3+ copies of a tile it needs)",
                                         "riichi threw a tile 1-3 away on the open side, early", "riichi threw a tile 1-3 away on the open side, late",
                                         "nothing thrown 1-3 away on the open side", "covering tile thrown late from the hand", "dora 1-2 away")],
                         [[324, 2.8], [1625, 7.2], [760, 5.4], [901, 7.3], [4558, 10.5], [885, 10.6], [684, 10.5]])

    def test_luckyj_follows_the_cues_only_a_little_more(self):
        p = DATA["preferences"]
        self.assertEqual((p["a wall on the open side"]["luckyj"][1], p["a wall on the open side"]["tokujou_humans"][1]), (68.2, 63.0))
        self.assertEqual((p["an early discard on the open side"]["luckyj"][1], p["an early discard on the open side"]["tokujou_humans"][1]), (68.6, 63.3))
        self.assertEqual((p["fewer open two-sided combinations"]["luckyj"][1], p["fewer open two-sided combinations"]["tokujou_humans"][1]), (59.4, 54.7))
        m = DATA["model"]
        self.assertEqual((m["discards"], m["held_out"], m["auc"], m["half_suji"]["luckyj"], m["half_suji"]["tokujou_humans"]),
                         (18903, 3753, 0.6, 9.3, 9.4))
        self.assertEqual(DATA["by_table"], {"jade": 2569, "tenhou": 16334})


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("6.7% of the time over 566", "10.2%", "9.7%", "8.4%", "6.1% of the time and the ones it kept 10.4%",
                       "10.7% of the time and kept ones that hit 9.4%", "10.9% and 9.6%", "8.1% and 7.8%", "9.8% for the humans",
                       "2.9% of the time", "6,140", "9.5%", "68.2%", "63.0%", "68.6% against 63.3%", "59.4% against 54.7%",
                       "18,903", "9.3% against 9.4%", "1,552", "8.4% of the time instead of 10.6%", "11.0%", "10.4%", "2,569", "16,334",
                       "3,753", "60%", "12 May 2023", "15th turn"):
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
