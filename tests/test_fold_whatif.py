"""Chapter 37 of the personal guide: chapter 35's 15 folds played out both ways by ``mortal_whatif.py``.

Every figure the chapter cites comes from ``analysis/fold-whatif-2026-10-12.json`` (``scripts/mine_fold_whatif.py``).
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "fold-whatif-2026-10-12.json").read_text())
THIN = json.loads((ROOT / "analysis" / "thin-pushes-2026-10-12.json").read_text())
SPOTS = json.loads((ROOT / "data" / "personal_guide_spots.json").read_text(encoding="utf-8"))["spots"]
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="fold-whatif">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheRunsTests(unittest.TestCase):
    def test_every_fold_ran_cleanly(self):
        folds = DATA["folds"]
        self.assertEqual(len(folds), 15)
        self.assertEqual({(f["game"], f["round"], f["turn"]) for f in folds},
                         {(r["game"], r["round"], r["turn"]) for r in THIN["your_folds"]})
        for f in folds:
            self.assertEqual((f["samples"], f["errors"]), (500, 0), f["game"])
            # the push is a tile that kept the tenpai
            self.assertIn(f["push"], [o[0] for o in f["options"]])

    def test_the_summary(self):
        self.assertEqual((DATA["mean_push_gain"], DATA["mean_push_gain_se_across_folds"]), (-4.2, 8.8))
        self.assertEqual((DATA["push_better"], DATA["fold_better"], DATA["push_deals_in_every_time"]), (4, 4, 4))
        self.assertEqual(DATA["mortal_kept"], {"folds": 6, "mean_push_gain": 10.2})
        self.assertEqual(DATA["mortal_folded"], {"folds": 9, "mean_push_gain": -13.9})
        better = sorted(f["push_gain"] for f in DATA["folds"] if f["push_gain"] - 2 * f["push_gain_se"] > 0)
        worse = sorted(f["push_gain"] for f in DATA["folds"] if f["push_gain"] + 2 * f["push_gain_se"] < 0)
        self.assertEqual((round(better[0]), round(better[-1]), round(-worse[-1]), round(-worse[0])), (23, 38, 21, 95))
        # the right folds held back the riichi's winning tile; Mortal folded three of them and split on one
        right = [f for f in DATA["folds"] if f["push_gain"] + 2 * f["push_gain_se"] < 0]
        self.assertTrue(all(f["push_line"]["hand"]["dealt in"] == 100.0 for f in right))
        self.assertEqual(sorted(f["mortal_keep"] > 0.5 for f in right), [False, False, False, True])

    def test_the_cards(self):
        cards = [s for s in SPOTS if s["chapter"] == "fold-whatif"]
        self.assertEqual([(c["id"], c.get("verdict")) for c in cards], [("split-fold-right", "fine"), ("newest-fold-8s", None)])
        by = {(f["game"][:15], f["round"], f["turn"]): f for f in DATA["folds"]}
        split = by[("261002-fc3b2f83", "East 3-0", 12)]
        self.assertEqual((round(100 * split["mortal_keep"]), split["push_gain"]), (58, -37.1))
        self.assertIn("37.1", cards[0]["luckyj"])
        newest = by[("261012-7b808921", "South 3-0", 12)]
        self.assertEqual((newest["push"], newest["push_gain"], newest["push_line"]["hand"]["won"], newest["push_line"]["hand"]["dealt in"]),
                         ("8s", 23.0, 36.6, 6.0))
        for figure in ("54%", "36.6%", "6.0%", "23.0"):
            self.assertIn(figure, cards[1]["luckyj"])


class TheChapterTests(unittest.TestCase):
    def test_the_table_has_every_fold(self):
        text = section("en")
        for f in DATA["folds"]:
            self.assertIn(f"[[{f['fold']}]] &#8594; [[{f['push']}]]", text)
            self.assertIn(f"{abs(f['push_gain']):.1f} &#177; {f['push_gain_se']:.1f}", text)

    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("15 folds", "500 times", "499 times", "4.2 rank points", "8.8", "23 to 38", "21 to 95",
                       "10.2 rank points", "13.9", "+38.2", "+36.2", "23,500", "23.0 rank points"):
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
