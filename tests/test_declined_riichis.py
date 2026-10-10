"""Chapter 31 of the personal guide: the riichis Mortal would not declare, and four checks to make first.

Every figure the chapter cites comes from ``analysis/declined-riichis-2026-10-07.json``
(``scripts/mine_declined_riichis.py``). The cards come from ``data/personal_guide_spots.json``.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "declined-riichis-2026-10-07.json").read_text())
SPOTS = json.loads((ROOT / "data" / "personal_guide_spots.json").read_text(encoding="utf-8"))["spots"]
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
SCREENS = {
    "furiten": lambda r: bool(r["furiten"]),
    "late": lambda r: r["turn"] >= 13,
    "thin_with_yaku": lambda r: r["live"] <= 3 and r["yaku"],
    "into_a_riichi": lambda r: r["into_a_riichi"] and r["live"] <= 3,
}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="declined-riichis">')
    return page[start:page.index("</section>", start)]


def tally(rows: list[dict]) -> tuple[int, int, int, int]:
    return (len(rows), sum(1 for r in rows if r["mortal"] < 0.25),
            sum(1 for r in rows if r["result"] == "won"), sum(1 for r in rows if r["result"] == "dealt"))


class TheChecksTests(unittest.TestCase):
    rows = DATA["riichis"]

    def test_the_table(self):
        self.assertEqual(tally(self.rows), (354, 32, 168, 44))
        self.assertEqual([tally([r for r in self.rows if f(r)]) for f in SCREENS.values()],
                         [(4, 1, 0, 1), (30, 6, 2, 7), (29, 9, 12, 5), (10, 8, 1, 3)])
        flagged = [r for r in self.rows if any(f(r) for f in SCREENS.values())]
        self.assertEqual(tally(flagged), (64, 18, 14, 13))
        self.assertEqual(tally([r for r in self.rows if r not in flagged]), (290, 14, 154, 31))
        self.assertEqual({k: DATA["screens"][k]["riichis"] for k in SCREENS}, {"furiten": 4, "late": 30, "thin_with_yaku": 29, "into_a_riichi": 10})

    def test_the_split_by_yaku(self):
        flagged = [r for r in self.rows if any(f(r) for f in SCREENS.values())]
        with_yaku = [r for r in flagged if r["yaku"]]
        without = [r for r in flagged if not r["yaku"]]
        rest = [r for r in self.rows if r not in flagged and r["yaku"]]
        self.assertEqual((len(with_yaku), sum(1 for r in with_yaku if r["result"] == "won")), (48, 14))
        self.assertEqual((len(rest), sum(1 for r in rest if r["result"] == "won")), (159, 91))
        self.assertEqual((len(without), sum(1 for r in without if r["result"] == "won")), (16, 0))

    def test_the_declined_riichis_that_trip_nothing(self):
        declined = [r for r in self.rows if r["mortal"] < 0.25]
        self.assertEqual(sum(1 for r in declined if not any(f(r) for f in SCREENS.values())), 14)

    def test_the_furiten_riichis(self):
        furiten = DATA["furiten_riichis"]
        self.assertEqual([(r["round"], r["result"]) for r in furiten if r["date"] == "2026-10-07 15:27"],
                         [("South 2-1", "dealt")])
        # the chapter says 87% to 98%: 86.5% rounds up
        self.assertEqual(sorted(int(100 * r["mortal"] + 0.5) for r in furiten if r["mortal"] >= 0.25), [87, 97, 98])
        self.assertEqual(sum(1 for r in furiten if r["result"] == "won"), 0)
        # the 15:27 hand: a 9p thrown on the 3rd turn
        mine = [r for r in furiten if r["date"] == "2026-10-07 15:27"][0]
        self.assertEqual((mine["waits"], mine["furiten"], mine["live"]), (["6p", "9p"], ["9p"], 5))

    def test_the_late_riichis(self):
        late = [r for r in self.rows if r["turn"] >= 13]
        self.assertEqual(sum(1 for r in late if r["result"] == "won"), 2)
        self.assertEqual(sum(1 for r in late if r["result"] == "dealt"), 7)


class TheCardsTests(unittest.TestCase):
    cards = [s for s in SPOTS if s["chapter"] == "declined-riichis"]

    def test_four_cards_one_per_check_and_the_fourth_is_furiten(self):
        self.assertEqual([c["id"] for c in self.cards],
                         ["chiitoi-dora-tanki", "riichi-into-riichi-8s", "late-riichi-7m", "furiten-riichi-9p"])
        self.assertIn("furiten", self.cards[3]["situation"])
        self.assertIn("[[9p]]", self.cards[3]["situation"])
        self.assertIn("フリテン", self.cards[3]["ja"]["situation"])

    def test_both_editions_carry_the_chapter(self):
        for lang in PAGES:
            text = section(lang)
            self.assertIn('data-guide-examples="declined-riichis"', text, lang)
            for fragment in ("354", "32", "64", "290", "154", "22%", "53%", "14", "29", "30", "10", "16"):
                self.assertIn(fragment, text, (lang, fragment))
            self.assertIn('href="#costly-run"', text, lang)

    def test_the_chapter_is_listed_and_announced(self):
        for lang, page in PAGES.items():
            text = page.read_text(encoding="utf-8")
            # news, list, previous chapter's next link, and the three pointers from chapter 29
            self.assertEqual(len(re.findall(r'href="#declined-riichis"', text)), 6, lang)


if __name__ == "__main__":
    unittest.main()
