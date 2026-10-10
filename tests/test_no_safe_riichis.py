"""Chapter 32 of the personal guide: the riichis that found the user with no safe tile in hand.

Every figure the chapter cites comes from ``analysis/no-safe-riichis-2026-10-10.json`` (``scripts/mine_no_safe_riichis.py``).
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "no-safe-riichis-2026-10-10.json").read_text())
SPOTS = json.loads((ROOT / "data" / "personal_guide_spots.json").read_text())["spots"]
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="no-safe-tile">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheFiguresTests(unittest.TestCase):
    def test_the_counts(self):
        self.assertEqual((DATA["window"]["games"], DATA["riichis"], DATA["no_safe_tile"]), (16, 107, 14))
        self.assertEqual(DATA["groups"], {"ended": 3, "early": 1, "tenpai": 2, "same": 5, "kept": 3})
        self.assertEqual(DATA["most_in_one_game"], 5)
        w = DATA["not_tenpai"]
        self.assertEqual((w["riichis"], w["no_safe_tile"], w["luckyj_rate"]), (92, 11, 7.8))
        t = DATA["terminal_leftovers"]
        self.assertEqual((t["choices"], round(t["you_rate"]), round(t["luckyj_rate"])), (120, 73, 72))

    def test_the_kept_tiles(self):
        kept = {(x["game"][:15], x["round"]): x for x in DATA["riichis_with_no_safe_tile"] if x["group"] == "kept"}
        self.assertEqual(set(kept), {("261011-99feaaaa", "South 1-0"), ("261011-99feaaaa", "East 2-0"),
                                     ("261010-201c40e5", "East 1-0")})
        first = next(c for c in kept[("261011-99feaaaa", "South 1-0")]["cuts"] if c["turn"] == 1)
        self.assertEqual((first["tile"], round(100 * first["mortal"]), first["mortal_top"], round(100 * first["mortal_top_p"])), ("9p", 20, "9m", 32))
        north = next(c for c in kept[("261011-99feaaaa", "East 2-0")]["cuts"] if c["turn"] == 1)
        self.assertEqual((north["tile"], round(100 * north["mortal"]), north["mortal_top"], round(100 * north["mortal_top_p"])), ("N", 39, "9m", 56))
        east = next(c for c in kept[("261010-201c40e5", "East 1-0")]["cuts"] if c["turn"] == 3)
        self.assertEqual((east["tile"], east["mortal_top"]), ("E", "P"))
        # the haku Mortal threw instead was also safe against the later riichi, and you threw it on turn 9
        self.assertIn(("P", 9), [(c["tile"], c["turn"]) for c in kept[("261010-201c40e5", "East 1-0")]["cuts"]])

    def test_the_two_cards(self):
        cards = [s for s in SPOTS if s["chapter"] == "no-safe-tile"]
        self.assertEqual([c["id"] for c in cards], ["dealer-9p-first-turn", "north-over-9m"])
        self.assertEqual([[(f["turn"], f["expect_cut"]) for f in c["frames"]] for c in cards],
                         [[(1, "9p"), (9, "W")], [(1, "N"), (8, "1m")]])
        self.assertEqual(cards[1]["verdict"], "close")


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("14 of the 107 riichis", "8.5%", "only three of the 14, all before you were tenpai", "Five of the 14", "73% of the time",
                       "LuckyJ 72%", "11 of 92", "7.8%", "in five", "56% to 39%", "1,255", "120"):
            self.assertIn(phrase, text, phrase)

    def test_the_table_has_every_riichi(self):
        for lang in PAGES:
            self.assertEqual(section(lang).count("<tr><td>"), DATA["no_safe_tile"], lang)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))


if __name__ == "__main__":
    unittest.main()
