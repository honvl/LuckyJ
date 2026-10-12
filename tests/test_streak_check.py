"""Chapter 34 of the personal guide: three fourths in a row, from riichis LuckyJ declares.

Every figure the chapter cites comes from ``analysis/streak-check-2026-10-11.json`` (``scripts/mine_streak_check.py``).
The cards come from ``data/personal_guide_spots.json``.
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "streak-check-2026-10-11.json").read_text())
SPOTS = json.loads((ROOT / "data" / "personal_guide_spots.json").read_text(encoding="utf-8"))["spots"]
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def half_up(v: float) -> int:
    return int(v + 0.5)


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="three-fourths">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheGamesTests(unittest.TestCase):
    def test_three_fourths(self):
        g = DATA["games"]
        self.assertEqual([(x["date"], x["place"], x["score"]) for x in g],
                         [("2026-10-11 20:27", 4, 13000), ("2026-10-11 21:09", 4, 15200), ("2026-10-11 21:33", 4, 16200)])
        self.assertEqual((g[0]["before"], g[-1]["after"]), (6278, 5484))
        a = DATA["agreement"]
        self.assertEqual((a["window"]["discards"], a["before"]["discards"], a["window"]["calls"], a["before"]["calls"], a["before"]["games"]),
                         (74.4, 73.2, 94.2, 93.1, 196))

    def test_the_riichis(self):
        r = DATA["riichis"]
        self.assertEqual(len(r), 8)
        mortal = sorted(x["mortal"] for x in r)
        self.assertEqual((sum(m >= 0.94 for m in mortal), half_up(100 * mortal[0])), (7, 60))
        lj = [x["luckyj"] for x in r if x["luckyj"] is not None]
        self.assertEqual((len(lj), half_up(100 * min(lj)), half_up(100 * max(lj))), (5, 82, 98))
        self.assertEqual((sum(x["won"] for x in r), sum(x["dealt"] for x in r), sum(x["net"] for x in r)), (2, 3, -5800))
        self.assertEqual(sum(not x["won"] and not x["dealt"] for x in r), 3)
        values = [d["value"].split(", ")[-1] for d in DATA["deal_ins"] if d["in_riichi"]]
        self.assertEqual(values, ["3,900", "8,000", "7,700"])

    def test_the_draw(self):
        luck = DATA["luck"]
        self.assertEqual((luck["riichis"], luck["dealt"], luck["points"], luck["p_dealt"], luck["p_points"]), (8, 3, -5800, 8.4, 6.2))
        s = DATA["streaks"]
        self.assertEqual((s["games"], s["runs"], s["chance_in_199"]), (1255, [3, 4, 3], 51.3))
        lr = DATA["long_run"]
        self.assertEqual([(lr[k]["riichis"], lr[k]["won"], lr[k]["dealt"], lr[k]["points"], lr[k]["lost_points"])
                          for k in ("you", "luckyj", "you_first", "luckyj_first", "window")],
                         [(382, 48.7, 12.8, 2464, 37.4), (2171, 51.8, 13.7, 2941, 34.7), (296, 51.7, 11.1, 2721, 33.8),
                          (1665, 54.7, 12.2, 3303, 30.3), (8, 25.0, 37.5, -725, 37.5)])

    def test_where_the_points_went(self):
        w = DATA["where"]
        self.assertEqual([(w[k]["hands"], w[k]["points"]) for k in ("deal-in", "tsumo against you", "your riichi", "draw", "your win", "others")],
                         [(5, -13200), (4, -10100), (8, -5800), (4, -5000), (2, 3500), (6, 0)])
        self.assertEqual(sum(v["points"] for v in w.values()), sum(g["score"] for g in DATA["games"]) - 75000)

    def test_the_deal_ins_without_a_riichi(self):
        d = [x for x in DATA["deal_ins"] if not x["in_riichi"]]
        tops = [x["mortal_top"][0] for x in d]
        self.assertEqual([t for t, _ in tops], ["6m", "riichi", "8s", "8p", "2s"])
        self.assertEqual([half_up(100 * p) for t, p in tops if t not in ("riichi", "2s")], [58, 52, 64])
        east = d[-1]
        self.assertEqual((east["tile"], east["paid"], dict(east["mortal_top"])["E"]), ("E", 2500, 0.007))


class TheCardsTests(unittest.TestCase):
    def test_the_four_cards(self):
        cards = [s for s in SPOTS if s["chapter"] == "three-fourths"]
        self.assertEqual([(c["id"], c.get("verdict")) for c in cards],
                         [("dealer-riichi-mangan", "unlucky"), ("chase-riichi-7700", "unlucky"), ("live-east-seven-pairs", None),
                          ("all-last-3s", "unlucky")])
        riichi = {(x["game"][:15], x["round"], x["turn"]): x for x in DATA["riichis"]}
        mangan = riichi[("261012-1d8ad962", "East 2-0", 12)]
        self.assertIn(f"{half_up(100 * mangan['luckyj'])}%", cards[0]["luckyj"])
        self.assertTrue(mangan["dealt"])
        chase = riichi[("261012-1d8ad962", "South 1-1", 11)]
        self.assertTrue(chase["into_a_riichi"] and chase["dealt"])
        c = DATA["chase"]
        self.assertEqual(half_up(c["1-2 han, 4-5 live"]["declared_pct"]), 59)
        self.assertEqual((c["1-2 han, 4-5 live, two-sided, turns 10-12"]["declared"], c["1-2 han, 4-5 live, two-sided, turns 10-12"]["tenpais"]), (14, 16))
        for card in cards:
            self.assertNotIn("—", json.dumps(card, ensure_ascii=False))


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("13,000, 15,200 and 16,200", "6,278 to 5,484", "74.4%", "73.2%", "196", "94.2% against 93.1%",
                       "8 riichis", "7 of them at 94%", "at 60%", "82% to 98%", "5,800 points with the sticks",
                       "3,900, 8,000 and 7,700", "2,171", "8.4%", "6.2%", "34.7%", "1,255", "51.3%", "199 games",
                       "+2,464", "+2,941", "30,600", "58%, 52% and 64%", "7,800 behind", "2,500 points", "0.7%"):
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
