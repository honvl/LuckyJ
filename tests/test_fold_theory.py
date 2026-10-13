"""Chapter 38 of the personal guide: why the user should fold a little more than LuckyJ, and what makes the gap.

Every figure the chapter cites comes from ``analysis/fold-theory-2026-10-13.json`` (``scripts/mine_fold_theory.py``).
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "fold-theory-2026-10-13.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="fold-theory">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheSuspectsTests(unittest.TestCase):
    def test_not_the_point_system(self):
        s = DATA["systems"]
        self.assertEqual((s["jade"]["push_gain"], s["jade"]["share_of_range"]), (-4.2, -1.11))
        self.assertEqual((s["tenhou_tokujou_10dan"]["push_gain"], s["tenhou_tokujou_10dan"]["share_of_range"]), (-3.0, -1.18))
        self.assertEqual(s["jade_score"]["push_gain"], -0.1)
        # Tenhou takes 2.4 times its first-place gain for fourth, the Jade room 1.9 times
        self.assertEqual((round(180 / 75, 1), round(250 / 130, 1)), (2.4, 1.9))

    def test_not_the_opponents(self):
        o = DATA["opponents"]
        self.assertEqual((o["you"]["won"], o["you"]["live"], o["you"]["points"], o["you"]["turn"]), (48.3, 5.37, 2419, 9.1))
        self.assertEqual((o["luckyj"]["won"], o["luckyj"]["live"], o["luckyj"]["points"], o["luckyj"]["turn"]), (47.7, 5.32, 2384, 9.1))

    def test_the_read(self):
        r = DATA["read"]
        self.assertEqual((r["pushes"], r["on_push_deal_ins"], r["luckyj_expects"]), (219, 27, 20.3))
        k = r["kinds"]
        self.assertEqual([k[x]["you"][1:] + k[x]["luckyj"][1:] for x in ("live honor", "live terminal", "half suji", "live 2-3-7-8", "live 4-5-6")],
                         [[15, 6.7, 134, 5.2], [41, 12.2, 215, 9.8], [45, 11.1, 200, 6.5], [82, 14.6, 524, 10.1], [34, 11.8, 159, 12.6]])
        w = r["wins_after_pushing"]
        self.assertEqual((w["4-7"]["you"][2], w["4-7"]["luckyj"][2], w["3 or fewer"]["you"][2], w["3 or fewer"]["luckyj"][2]),
                         (33.8, 33.1, 11.1, 20.3))
        c = r["cost"]
        self.assertEqual((c["excess_points"], c["deal_in_on_the_push"], c["no_deal_in"], round(c["per_push"], 1)), (3.07, -57.8, 18.5, 2.3))
        n = r["near_riichi_tile"]
        near = "1-2 ranks from the riichi tile"
        self.assertEqual((n["you"][near]["share"], n["luckyj"][near]["share"], n["you"][near]["dealt"], n["you"][near]["pushes"],
                          n["you"][near]["dealt_pct"], n["luckyj"][near]["dealt_pct"]), (14.9, 14.4, 6, 30, 20.0, 9.5))

    def test_the_cells(self):
        c = DATA["cells"]
        rows = [("1-2 han, 3 or fewer live", (65.6, -14.0, -2.0), (39.3, -15.8, -4.4)),
                ("1-2 han, 4-7 live", (73.9, -4.9, -11.3), (75.9, -2.8, -12.2)),
                ("3+ han, 3 or fewer live", (83.1, 3.0, -12.9), (73.7, -18.6, -6.6)),
                ("3+ han, 4-7 live", (93.7, 5.0, 0.4), (95.0, 10.3, -15.3))]
        errors = []
        for name, lj, you in rows:
            self.assertEqual((c[name]["luckyj"]["pushed_pct"], c[name]["luckyj"]["push"][0], c[name]["luckyj"]["fold"][0]), lj, name)
            self.assertEqual((c[name]["you"]["pushed_pct"], c[name]["you"]["push"][0], c[name]["you"]["fold"][0]), you, name)
            errors += [c[name][w][s][1] for w in ("you", "luckyj") for s in ("push", "fold")]
        self.assertEqual((round(min(errors)), round(max(errors))), (3, 13))
        self.assertEqual(round(c["1-2 han, 4-7 live"]["luckyj"]["push"][0] - c["1-2 han, 4-7 live"]["luckyj"]["fold"][0], 1), 6.4)


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("2.4 times", "1.9 times", "1.18% of the range against 1.11%", "0.1 rank points", "11.1% of the time against 6.5%",
                       "14.6% against 10.1%", "3.1 percentage points", "33.8% against 33.1%", "11.1% against 20.3%", "57.8", "18.5",
                       "about 2.3 rank points", "14.9%", "14.4%", "6 of your 30", "20.0%", "9.5%", "39.3% of the time to its 65.6%",
                       "by 6.4", "gain 10.3", "lose 15.3", "3 to 13 rank points", "199 games", "1,079", "1,255"):
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
