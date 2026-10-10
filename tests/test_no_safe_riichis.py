"""Chapter 32 of the personal guide: where LuckyJ keeps a safe tile and the user throws it.

LuckyJ alone is the yardstick. Every figure the chapter cites comes from ``analysis/no-safe-riichis-2026-10-10.json``
(``scripts/mine_no_safe_riichis.py``).
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


def half_up(v: float) -> int:
    return int(v + 0.5)


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
    def test_the_14_riichis(self):
        w = DATA["window"]
        self.assertEqual((w["games"], w["riichis"], w["no_safe_tile"], w["most_in_one_game"]), (16, 107, 14, 5))
        self.assertEqual((w["not_tenpai"]["riichis"], w["not_tenpai"]["no_safe_tile"], w["not_tenpai"]["luckyj_rate"]), (92, 11, 7.8))
        [only] = w["choices_before"]
        self.assertEqual((only["game"][:15], only["round"], only["turn"], only["cut"], only["live"], only["live_cut"]),
                         ("261010-201c40e5", "East 1-0", 1, "N", ["E", "F"], False))
        self.assertEqual(half_up(100 * (1 - only["luckyj_live_first"])), 98)

    def test_the_table_since_january(self):
        k = DATA["since_january"]["kinds"]
        self.assertEqual([(v["choices"], v["you"], v["luckyj"]) for v in k.values()],
                         [(45, 46.7, 23.5), (19, 52.6, 68.4), (120, 73.3, 71.7), (112, 43.8, 49.8), (292, 16.1, 26.4)])
        self.assertEqual(k["value honor vs discarded wind"]["sd"], -5.0)
        self.assertEqual(sum(v["choices"] for v in k.values()), 588)
        self.assertEqual((DATA["since_january"]["games"], DATA["since_january"]["choices"]), (189, 771))
        self.assertEqual(half_up(100 - k["guest winds, discards 1-2"]["luckyj"]), 77)

    def test_where_luckyj_keeps_more(self):
        keeps = DATA["luckyj_keeps"]
        self.assertEqual((keeps["choices"], keeps["you_threw_safe"], round(keeps["luckyj_would"]), keeps["wind_vs_value"],
                          keeps["safe_at_a_later_riichi"], keeps["two_or_fewer_held"]), (245, 92, 75, 39, 34, 7))

    def test_the_four_cards(self):
        cards = [s for s in SPOTS if s["chapter"] == "no-safe-tile"]
        self.assertEqual([c["id"] for c in cards], ["west-before-chun", "kamicha-1m-kept-9p", "north-before-west", "east-north-before-hatsu"])
        examples = {(e["game"][:15], e["round"], e["turn"]): e for e in DATA["examples"]}
        for c in cards:
            first = c["frames"][0]
            e = examples[(c["game"], c["round"], first["turn"])]
            # the card's cut is the safe tile you threw, and its better tile is the live one LuckyJ throws first
            self.assertEqual((first["expect_cut"], [first["better"]]), (e["cut"], e["live"]), c["id"])
            self.assertFalse(e["live_cut"])
            self.assertGreaterEqual(e["luckyj_live_first"], 0.6)
            self.assertIn(e["riichi_later"]["labels"][e["cut"]], ("genbutsu", "dead", "suji", "honor, 2 seen"))
            self.assertEqual(c["frames"][-1]["turn"], e["riichi_later"]["your_turn"])
            self.assertNotIn("Mortal", json.dumps(c, ensure_ascii=False))
        rates = [half_up(100 * examples[k]["luckyj_live_first"]) for k in sorted(examples)]
        self.assertEqual(sorted(rates), [61, 62, 70, 72, 72])


class TheChapterTests(unittest.TestCase):
    def test_no_mortal(self):
        for lang in PAGES:
            self.assertNotIn("Mortal", section(lang), lang)

    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("14 of the 107 riichis", "8.5%", "98% of the time", "11 of 92", "7.8%", "five of the 14", "588",
                       "five standard deviations", "92 of 245", "give 75", "39 of the 92", "34 of the 92", "7 of those",
                       "77% of the time", "189 games", "1,255", "771"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))


if __name__ == "__main__":
    unittest.main()
