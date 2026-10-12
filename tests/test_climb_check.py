"""Chapter 33 of the personal guide: the climb against the games since the peak, and the riichis that went missing.

Every figure the chapter cites comes from ``analysis/climb-check-2026-10-11.json`` (``scripts/mine_climb_check.py``).
The cards come from ``data/personal_guide_spots.json``.
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "climb-check-2026-10-11.json").read_text())
SPOTS = json.loads((ROOT / "data" / "personal_guide_spots.json").read_text(encoding="utf-8"))["spots"]
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def half_up(v: float) -> int:
    return int(v + 0.5)


def section(lang: str, chapter: str = "climb-riichi") -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index(f'<section class="point" id="{chapter}">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


def mark(lang: str, mark_id: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index(f'<mark id="{mark_id}"')
    return page[start:page.index("</mark>", start)]


class TheClimbTests(unittest.TestCase):
    def test_the_rank_path(self):
        r = DATA["rank"]
        self.assertEqual((r["start"]["date"], r["start"]["points"], r["peak"]["date"], r["peak"]["points"], r["now"]["points"]),
                         ("2026-09-23 18:40", 3972, "2026-10-01 22:20", 6749, 6278))
        p = r["periods"]
        self.assertEqual((p["climb"]["games"], p["climb"]["places"], p["climb"]["points_a_game"]), (62, [20, 18, 20, 4], 44.8))
        self.assertEqual((p["since"]["games"], p["since"]["places"], p["since"]["points_a_game"]), (47, [14, 9, 13, 11], -10.0))
        self.assertEqual((p["before"]["games"], p["before"]["places"]), (87, [20, 25, 22, 20]))
        # fourths: 6% on the climb, 23% before it and since
        self.assertEqual([half_up(100 * p[k]["places"][3] / p[k]["games"]) for k in ("climb", "before", "since")], [6, 23, 23])

    def test_the_defense_held(self):
        d = DATA["defense"]["riichi"]
        rows = [(d[p]["tenpai"]["live"], d[p]["one"]["live"], d[p]["two_or_more"]["live"], d[p]["dealt_per_100"])
                for p in ("climb", "since", "luckyj")]
        self.assertEqual(rows, [(3.3, 6.2, 4.1, 1.95), (4.8, 6.9, 4.4, 2.18), (6.1, 7.8, 3.6, 1.71)])
        t = DATA["defense"]["tenpai_push"]
        self.assertEqual([(t[p]["pushed_pct"], t[p]["pushed_avg"]) for p in ("climb", "since", "luckyj")],
                         [(82.4, 1023), (76.5, 1310), (82.3, 518)])

    def test_the_hands(self):
        h = DATA["hands"]
        self.assertEqual([(h[p]["won"], h[p]["dealt_in"], h[p]["riichis_per_100"], h[p]["riichi_wins_per_100"])
                          for p in ("climb", "since", "luckyj")],
                         [(25.0, 9.9, 21.9, 10.2), (22.4, 11.9, 16.1, 8.5), (22.9, 10.3, 19.3, 10.0)])
        into_open = [DATA["deal_ins"][p]["not tenpai into open hand"]["per_100"] for p in ("climb", "since")]
        self.assertEqual(into_open, [1.9, 3.0])
        # the biggest part of the rise in deal-ins
        rise = h["since"]["dealt_in"] - h["climb"]["dealt_in"]
        self.assertGreater(into_open[1] - into_open[0], rise / 2)


class TheRiichiTests(unittest.TestCase):
    def test_the_fit_matches_luckyj(self):
        m = DATA["riichi"]["model"]
        self.assertEqual(m["tenpais"], 2177)
        for name, c in m["calibration"].items():
            if name != "an opponent on 2+ calls":
                self.assertLessEqual(abs(c["actual"] - c["fit"]), 1.0, name)

    def test_the_periods(self):
        p = DATA["riichi"]["periods"]
        self.assertEqual((p["climb"]["tenpais"], p["climb"]["declared"], p["climb"]["luckyj"]), (132, 107, 104.9))
        self.assertEqual((p["since"]["tenpais"], p["since"]["declared"], p["since"]["luckyj"], p["since"]["sd"]), (94, 60, 70.7, -3.1))
        self.assertEqual(half_up(p["since"]["luckyj"] - p["since"]["declared"]), 11)
        s = p["since"]
        self.assertEqual((s["cheap"]["tenpais"], s["cheap"]["declared"], s["cheap"]["luckyj"]), (70, 52, 58.5))
        self.assertEqual((s["big"]["tenpais"], s["big"]["declared"], s["big"]["luckyj"]), (24, 8, 12.2))
        self.assertEqual((s["by_turn"]["13 on"]["tenpais"], s["by_turn"]["13 on"]["declared"], s["by_turn"]["13 on"]["luckyj"]), (17, 5, 9.9))
        c = p["climb"]["big"]
        self.assertEqual((c["tenpais"], c["declared"], c["luckyj"]), (29, 19, 16.1))

    def test_the_stretches(self):
        s = DATA["riichi"]["stretches"]
        self.assertEqual([(v["games"], v["tenpais"], v["declared"], v["luckyj"]) for v in s.values()],
                         [(50, 117, 95, 92.9), (30, 68, 50, 53.2), (15, 25, 14, 17.0), (7, 16, 8, 12.5)])

    def test_late_tenpais(self):
        late = DATA["late"]
        self.assertEqual((late["cheap"]["declared_pct"], late["big"]["declared_pct"]), (76.0, 34.4))
        by_live = late["cheap_by_live"]
        self.assertEqual([half_up(by_live[k]["declared_pct"]) for k in ("4-5", "6 or more")], [81, 88])
        you, lj = late["riichis"]["you"], late["riichis"]["luckyj"]
        self.assertEqual((you["n"], you["wins"], half_up(lj["won"])), (33, 2, 31))
        self.assertEqual((round(you["live"], 1), round(lj["live"], 1)), (5.1, 5.0))
        self.assertLess(abs(you["turn"] - lj["turn"]), 0.5)
        self.assertLess(abs(you["wall"] - lj["wall"]), 0.5)
        firsts = late["first_tenpais"]
        self.assertEqual((firsts["you"]["dama"]["won"], firsts["luckyj_all"]["dama"]["won"]), (14.0, 26.0))


class TheCardsTests(unittest.TestCase):
    def test_the_four_cards(self):
        cards = [s for s in SPOTS if s["chapter"] == "climb-riichi"]
        self.assertEqual([c["id"] for c in cards], ["climb-late-riichi", "no-yaku-dama", "late-pinfu-dama", "dealer-pinfu-dama"])
        examples = {(e["game"][:15], e["round"], e["turn"]): e for e in DATA["examples"]}
        rates = []
        for c in cards:
            e = examples[(c["game"], c["round"], c["frames"][0]["turn"])]
            first = c == cards[0]
            self.assertEqual(e["period"], "climb" if first else "since", c["id"])
            self.assertEqual(e["declared"], first, c["id"])
            self.assertEqual(c.get("verdict"), "fine" if first else None, c["id"])
            if not first:
                self.assertEqual(c["frames"][0]["kind"], "riichi")
                self.assertLessEqual(e["han"], 3)
            rates.append(half_up(100 * e["luckyj"]))
            self.assertIn(f"{rates[-1]}%", c["luckyj"], c["id"])
            self.assertIn(f"{rates[-1]}%", c["ja"]["luckyj"], c["id"])
        self.assertEqual(rates, [74, 88, 74, 96])
        self.assertEqual([e["date"] >= "2026-10-10 18:11" for e in DATA["examples"]], [False, False, True, True])


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("3,972", "6,749", "20 firsts and 4 fourths", "+44.8", "14 firsts and 11 fourths", "10.0 a game",
                       "6,278", "+1,310 a hand", "2,177", "107 of 132", "104.9", "60 of 94", "70.7", "about 11",
                       "3.1 standard deviations", "21.9 to 16.1", "19.3", "10.2 to 8.5", "25.0% of hands to 22.4%",
                       "8 of 16", "12.5", "52 of 70", "58.5", "8 of 24", "12.2", "19 of 29", "16.1", "5 of 17", "9.9",
                       "76%", "81%", "88%", "34%", "2 of 33", "31%", "5.1 against 5.0", "14% against", "26%",
                       "9.9% of hands to 11.9%", "1.9 per 100", "3.0 since", "is 6%", "23%", "74% to 96%",
                       "196 games", "1,079", "1,255", "6,700"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_voice(self):
        for lang in PAGES:
            s = section(lang)
            self.assertNotIn("&#8212;", s)
            self.assertNotIn("—", s)
        self.assertNotIn("Of course", section("en"))

    def test_the_corrections(self):
        for lang in PAGES:
            for mark_id in ("fix-29-rule", "fix-31-late", "fix-31-rule"):
                self.assertIn("33", mark(lang, mark_id), (lang, mark_id))
        self.assertNotIn("5 live tiles", mark("en", "fix-29-rule"))
        self.assertNotIn("13th turn or later", mark("en", "fix-31-rule"))
        self.assertIn("31%", mark("en", "fix-31-late"))


if __name__ == "__main__":
    unittest.main()
