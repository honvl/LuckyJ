"""Chapter 29 of the personal guide: the ten newest games, their deal-ins sorted by Mortal, and the riichis.

Every figure the chapter cites comes from ``analysis/costly-run-2026-10-07.json``
(``scripts/mine_costly_run.py``). The cards come from ``data/personal_guide_spots.json``.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "costly-run-2026-10-07.json").read_text())
SPOTS = json.loads((ROOT / "data" / "personal_guide_spots.json").read_text(encoding="utf-8"))["spots"]
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def pct(v: float, digits: int = 1) -> str:
    return f"{100 * v:.{digits}f}%"


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="costly-run">')
    return page[start:page.index("</section>", start)]


class TheRunTests(unittest.TestCase):
    def test_the_games(self):
        self.assertEqual((DATA["window"]["first"], DATA["window"]["last"]), ("2026-10-03 14:11", "2026-10-07 15:27"))
        recent, before = DATA["places"]["recent"], DATA["places"]["before"]
        self.assertEqual((recent["games"], recent["places"], round(recent["average"], 2)), (10, [3, 1, 1, 5], 2.8))
        self.assertEqual((before["games"], round(before["average"], 2)), (163, 2.34))

    def test_the_hands(self):
        before, recent, lj = (DATA["hands"][k] for k in ("before", "recent", "luckyj"))
        self.assertEqual((before["hands"], recent["hands"], lj["hands"]), (1690, 110, 11272))
        self.assertEqual([pct(h["won_rate"]) for h in (before, recent, lj)], ["22.5%", "23.6%", "22.9%"])
        self.assertEqual([round(h["avg_win"]) for h in (before, recent, lj)], [6420, 5777, 7317])
        self.assertEqual([pct(h["deal_in_rate"]) for h in (before, recent, lj)], ["10.9%", "17.3%", "10.3%"])
        self.assertEqual([round(h["avg_deal_in"]) for h in (before, recent, lj)], [-4769, -6921, -5308])
        self.assertEqual([round(100 * h["big_deal_in_rate"], 1) for h in (before, recent, lj)], [2.6, 9.1, 3.4])
        self.assertEqual([round(h["points_a_hand"]) for h in (before, recent, lj)], [176, -511, 363])
        # 19 deal-ins in 110 hands where the earlier rate gives about 12
        self.assertEqual((recent["dealt_in"], round(recent["hands"] * before["deal_in_rate"])), (19, 12))

    def test_mortal_agreed_as_ever(self):
        before, recent = DATA["mortal"]["before"], DATA["mortal"]["recent"]
        self.assertEqual((recent["discards"], recent["matched"], before["discards"], before["matched"]),
                         (1241, 927, 19486, 14284))
        self.assertEqual((pct(recent["matched"] / recent["discards"]), pct(before["matched"] / before["discards"])),
                         ("74.7%", "73.3%"))
        self.assertEqual((recent["calls"], recent["calls_matched"], before["calls"], before["calls_matched"]),
                         (345, 322, 5431, 5048))
        riichis = DATA["riichis"]
        self.assertEqual((riichis["count"], riichis["mortal_low"]), (24, 2))
        self.assertGreater(riichis["lowest_agreed"], 0.91)

    def test_the_deal_ins(self):
        s = DATA["deal_in_summary"]
        self.assertEqual((s["total"], s["mortal_half"], s["mortal_low"]), (19, 12, 6))
        self.assertEqual((s["big"], s["big_mortal_half"], s["big_mortal_low"], s["big_low_paid"]), (10, 5, 5, 60500))
        self.assertEqual(round(100 * s["big_mortal_half"] / DATA["hands"]["recent"]["hands"], 1), 4.5)
        low_big = sorted(d["paid"] for d in DATA["deal_ins"] if d["paid"] >= 7000 and d["mortal"] < 0.25)
        self.assertEqual(low_big, [11600, 12000, 12300, 12300, 12300])
        # the small one the chapter explains without a card: 5 October, East 4-1, the live chun
        small = [d for d in DATA["deal_ins"] if d["mortal"] < 0.25 and d["paid"] < 7000]
        self.assertEqual([(d["round"], d["tile"], d["paid"]) for d in small], [("East 4-1", "C", 2900)])
        self.assertLess(small[0]["mortal"], 0.01)

    def test_the_riichis_mortal_would_not_declare(self):
        low, agreed = (DATA["riichi_outcomes_since_january"][k] for k in ("mortal_low", "mortal_agreed"))
        self.assertEqual((low["riichis"], low["won"], low["dealt"], low["into_a_riichi"]), (32, 5, 9, 14))
        self.assertEqual((agreed["riichis"], agreed["won"], agreed["dealt"], agreed["into_a_riichi"]), (322, 163, 35, 46))
        self.assertEqual((round(low["average_turn"], 1), round(agreed["average_turn"], 1)), (9.9, 8.4))
        self.assertEqual(low["riichis"] + agreed["riichis"], 354)


class TheCardsTests(unittest.TestCase):
    cards = [s for s in SPOTS if s["chapter"] == "costly-run"]

    def test_four_cards_in_game_order(self):
        self.assertEqual([c["id"] for c in self.cards],
                         ["dealer-riichi-haku", "dealer-call-7s", "dama-1p-4p", "riichi-three-callers"])

    def test_the_two_discards_have_a_safe_tile_and_the_riichis_are_close_calls(self):
        verdicts = {c["id"]: c.get("verdict", "mistake") for c in self.cards}
        self.assertEqual(verdicts, {"dealer-riichi-haku": "mistake", "dealer-call-7s": "mistake",
                                    "dama-1p-4p": "close", "riichi-three-callers": "close"})
        for c in self.cards[:2]:
            self.assertTrue(c["frames"][0]["better"])

    def test_both_editions_carry_the_chapter(self):
        for lang, page in PAGES.items():
            text = section(lang)
            self.assertIn('data-guide-examples="costly-run"', text, lang)
            self.assertIn("60,500", text, lang)
            for fragment in ("22", "24", "32", "354", "163", "322", "1,241", "19,486", "5,777", "7,317"):
                self.assertIn(fragment, text, (lang, fragment))
            self.assertIn('href="#plateau"', text, lang)
            self.assertIn('id="costly-run"', page.read_text(encoding="utf-8"), lang)

    def test_the_chapter_is_listed_and_announced(self):
        for lang, page in PAGES.items():
            text = page.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r'href="#costly-run"', text)), 3, lang)  # news, list, previous chapter's next link


if __name__ == "__main__":
    unittest.main()
