"""Chapter 35 of the personal guide: big hands on thin waits, pushed against a riichi.

Every figure the chapter cites comes from ``analysis/thin-pushes-2026-10-12.json`` (``scripts/mine_thin_pushes.py``).
The cards come from ``data/personal_guide_spots.json``.
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "thin-pushes-2026-10-12.json").read_text())
SPOTS = json.loads((ROOT / "data" / "personal_guide_spots.json").read_text(encoding="utf-8"))["spots"]
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def half_up(v: float) -> int:
    return int(v + 0.5)


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="thin-pushes">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheSpotTests(unittest.TestCase):
    def test_the_table(self):
        y, l = DATA["you"], DATA["luckyj"]
        self.assertEqual((y["thin"], y["pushed"], y["pushed_pct"], l["thin"], l["pushed"], l["pushed_pct"]), (57, 42, 73.7, 236, 196, 83.1))
        self.assertEqual((y["pushes"]["won"], y["pushes"]["points"], l["pushes"]["won"], l["pushes"]["points"]), (11.9, -1655, 23.0, 618))
        self.assertEqual((y["deal_in_rates"]["on_the_push"], y["deal_in_rates"]["later_into_the_riichi"]), (21.4, 11.9))
        self.assertEqual((l["deal_in_rates"]["on_the_push"], l["deal_in_rates"]["later_into_the_riichi"]), (10.7, 8.2))
        self.assertEqual((y["folds"]["hands"], y["folds"]["points"], l["folds"]["points"]), (15, -1820, -1488))
        # every deal-in of yours in the spot went to the riichi, and you were still tenpai each time
        self.assertEqual((y["deal_ins"]["into_someone_else"], y["deal_ins"]["still_tenpai"]), (0, 14))

    def test_your_pushes_were_luckyjs(self):
        self.assertEqual(DATA["tile_choice"], {"you": {"with_a_choice": 22, "least_dangerous": 15},
                                               "luckyj": {"with_a_choice": 93, "least_dangerous": 63}})
        self.assertEqual((DATA["you"]["wait_safe"]["share"], DATA["luckyj"]["wait_safe"]["share"]), (42.9, 41.8))
        m = DATA["mortal"]
        self.assertEqual((m["pushes_rated"], half_up(100 * m["keep_tenpai"]), m["on_push_deal_ins"], m["on_push_backed"]), (42, 90, 9, 9))
        self.assertEqual((m["other_tile_preferred"], m["folds_rated"], m["folds_mortal_keeps"]), (5, 15, 6))
        tops = sorted(max(q for _, q in r["mortal"]["top"]) for r in DATA["your_pushes"]
                      if r["mortal"]["cut"] <= 0.2 and r["mortal"]["keep_tenpai"] >= 0.8)
        self.assertEqual(half_up(100 * tops[0]), 84)

    def test_the_luck(self):
        y, l = DATA["you"]["pushes"], DATA["luckyj"]["pushes"]
        self.assertEqual((y["a_win"], y["a_deal_in"], l["a_win"], l["a_deal_in"]), (8360, -5721, 8996, -5597))
        self.assertEqual(DATA["on_push_expected"], {"thin": {"pushes": 42, "deal_ins": 9, "luckyj_expects": 5.1},
                                                    "other": {"pushes": 177, "deal_ins": 18, "luckyj_expects": 15.7}})
        self.assertEqual((DATA["chance"]["on_push_deal_ins"], DATA["chance"]["points"]), (6.1, 0.3))
        o = DATA["other_pushes"]
        self.assertEqual((o["you"]["hands"], o["you"]["won"], o["you"]["dealt"], o["you"]["points"]), (177, 31.6, 20.9, 698))
        self.assertEqual((o["luckyj"]["won"], o["luckyj"]["dealt"], o["luckyj"]["points"]), (32.4, 21.0, 499))
        w = DATA["wait_kinds"]["luckyj"]
        self.assertEqual((w["honor"]["won"], w["number"]["won"]), (35.3, 20.4))
        self.assertEqual(DATA["luckyj_one_live"], {"spots": 5, "pushed": 2})


class TheCardsTests(unittest.TestCase):
    def test_the_four_cards(self):
        cards = [s for s in SPOTS if s["chapter"] == "thin-pushes"]
        self.assertEqual([(c["id"], c.get("verdict")) for c in cards],
                         [("mangan-dama-ippatsu", "unlucky"), ("seven-pairs-last-9p", None), ("lone-haku-wait", None),
                          ("folded-dora-tanki", None)])
        pushes = {(r["game"][:15], r["round"], r["turn"]): r for r in DATA["your_pushes"]}
        folds = {(r["game"][:15], r["round"], r["turn"]): r for r in DATA["your_folds"]}
        first = pushes[("260907-0d113184", "East 2-1", 13)]
        self.assertTrue(first["deal"]["on_decision"])
        self.assertIn(f"{half_up(100 * first['mortal']['cut'])}%", cards[0]["luckyj"])
        for card, table in ((cards[1], pushes), (cards[2], pushes), (cards[3], folds)):
            r = table[(card["game"], card["round"], card["frames"][0]["turn"])]
            better = card["frames"][0]["better"]
            weight = dict(r["mortal"]["top"])[better]
            self.assertGreaterEqual(weight, 0.9, card["id"])
            self.assertIn(f"{100 * weight:.0f}%" if weight < 0.95 or card is cards[1] else f"{100 * weight:.1f}%", card["luckyj"])

    def test_the_dora_corrections(self):
        for card_id, wrong in (("dealer-pinfu-dama", "the dora [[3m]]"), ("chase-riichi-7700", "the dora [[4m]]")):
            card = next(s for s in SPOTS if s["id"] == card_id)
            self.assertNotIn(wrong, card["situation"])
            self.assertNotIn("ドラの[[", card["ja"]["situation"])
            self.assertEqual(card["corrected"]["date"], "12 October")


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("57 times", "42 of them", "1,820", "1,488", "618", "83% of the time to your 74%", "15 times in 22",
                       "63 times in 93", "42.9%", "41.8%", "averaged 90%", "75% or more on all 9", "8,360 and 5,721",
                       "8,996 and 5,597", "about 5.1 times", "9 times", "6.1%", "0.3%", "177 pushes won 31.6%", "20.9%",
                       "+698", "32.4%, 21.0% and +499", "Five times", "84% or more", "35.3%", "20.4%", "6 of your 15",
                       "4 times in 5", "2 of its 5", "199 games", "1,255", "100,000"):
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
