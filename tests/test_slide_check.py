"""Chapter 42 of the personal guide: folding more since the peak, and still losing.

Every figure the chapter cites comes from ``analysis/slide-check-2026-10-16.json`` (``scripts/mine_slide_check.py``).
"""

from __future__ import annotations

import json
import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "slide-check-2026-10-16.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
PERIODS = ("before", "climb", "since")


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="slide-check">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class ThePlacesTests(unittest.TestCase):
    def test_the_periods(self):
        p = DATA["placements"]["periods"]
        self.assertEqual([p[k]["games"] for k in PERIODS], [87, 62, 54])
        self.assertEqual([p[k]["places"] for k in PERIODS], [[20, 25, 22, 20], [20, 18, 20, 4], [14, 11, 13, 16]])
        self.assertEqual([p[k]["points_a_game"] for k in PERIODS], [-13.9, 44.8, -31.1])
        self.assertEqual(p["since"]["points"], -1680)
        self.assertEqual((p["new"]["games"], p["new"]["places"]), (4, [0, 2, 0, 2]))
        self.assertEqual((p["2026"]["games"], p["2026"]["points_a_game"]), (203, -0.6))

    def test_the_fourths_against_the_career_rate(self):
        pl = DATA["placements"]
        self.assertEqual((pl["career_games"], pl["career_fourths"]), (4458, 21.4))
        p = pl["periods"]
        self.assertEqual((p["climb"]["fourths_expected"], p["climb"]["fourths_sd"]), (13.3, -2.9))
        self.assertEqual((p["since"]["fourths_expected"], p["since"]["fourths_sd"]), (11.6, 1.5))
        self.assertEqual((pl["rank"]["start"]["date"], pl["rank"]["peak"]["date"]), ("2026-09-23 18:40", "2026-10-01 22:20"))


class TheHandsTests(unittest.TestCase):
    def test_the_table(self):
        h = DATA["hands"]
        cols = PERIODS + ("luckyj",)
        self.assertEqual([h[k]["won"] for k in cols], [21.1, 25.0, 21.8, 22.9])
        self.assertEqual([h[k]["avg_win"] for k in cols], [6006, 6815, 6462, 7317])
        self.assertEqual([h[k]["dealt_in"] for k in cols], [11.6, 9.9, 12.7, 10.3])
        self.assertEqual([h[k]["big_deal_ins_per_100"] for k in cols], [2.7, 2.7, 4.9, 3.4])
        self.assertEqual([h[k]["points_a_hand"] for k in cols], [-46, 454, 51, 363])
        d = DATA["defense"]
        self.assertEqual([d["riichi"][k]["one"]["live"] for k in cols], [6.9, 6.2, 6.3, 7.8])
        self.assertEqual([d["tenpai_push"][k]["pushed_pct"] for k in cols], [76.9, 82.4, 75.9, 82.3])
        r = DATA["riichi"]
        self.assertEqual([r[k]["declared_pct"] for k in PERIODS], [74.1, 81.1, 62.3])
        self.assertEqual([r[k]["luckyj_pct"] for k in PERIODS], [78.4, 79.5, 74.4])

    def test_folding_more_is_about_five_hands(self):
        t = DATA["defense"]["tenpai_push"]
        self.assertEqual(round(t["since"]["hands"] * (t["climb"]["pushed_pct"] - t["since"]["pushed_pct"]) / 100), 5)

    def test_the_dama(self):
        r = DATA["riichi"]["since"]
        self.assertEqual(r["sd"], -3.6)
        o = r["outcomes"]
        self.assertEqual((o["luckyj declares 70% or more, riichi"]["tenpais"], o["luckyj declares 70% or more, riichi"]["net"]), (61, 3018))
        self.assertEqual((o["luckyj declares 70% or more, dama"]["tenpais"], o["luckyj declares 70% or more, dama"]["net"]), (15, 640))
        m = DATA["mortal_riichi"]
        self.assertEqual((m["hands"]["climb"]["declared_pct"], m["hands"]["since"]["declared_pct"]), (94.2, 82.4))
        last = [d["riichi"] for d in m["dama"] if d["game"].startswith("261016-76fdbc7c")]
        self.assertEqual(sorted(last), [0.93, 0.94, 0.94, 0.99])


class TheNewGamesTests(unittest.TestCase):
    def test_the_real_folds(self):
        n = DATA["new"]
        self.assertEqual((sum(n["real_folds"].values()), n["real_folds"]["genbutsu"]), (25, 22))
        self.assertEqual([(d["round"], d["turn"], d["label"]) for d in n["real_fold_deal_ins"]], [("South 2-1", 9, "live terminal")])

    def test_the_deal_ins(self):
        games = {g["game"][:15]: g for g in DATA["new"]["games"]}
        first, second = games["261016-7cc3ee5d"], games["261016-76fdbc7c"]
        self.assertEqual([(d["round"], d["turn"], d["you"], d["points"], d["into"]) for d in first["deal_ins"]],
                         [("South 4-0", 18, "2p", 7700, "no riichi")])
        self.assertEqual([d["points"] for d in second["deal_ins"]], [5200, 8300, 8300, 7700])
        self.assertEqual([d["ippatsu"] for d in second["deal_ins"]], [False, True, True, True])
        self.assertTrue(all(d["you"] == d["mortal_top"][0] for g in (first, second) for d in g["deal_ins"]))
        self.assertEqual([d["mortal_you"] for d in second["deal_ins"]], [0.97, 0.96, 0.63, 1.0])
        self.assertEqual([games[k]["placement"] for k in sorted(games)], [2, 2, 4, 4])


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("54 games", "1,680 rank points, 31.1 a game", "4,458 games", "21.4%", "13.3 fourths in 62 games",
                       "2.9 standard deviations", "11.6 in 54", "1.5 over", "203 games", "0.6 rank points", "+51 points each",
                       "6.3% of the time", "6.2% on the climb", "25 real folds", "22 of them", "75.9%", "82.4% on the climb",
                       "82.3%", "about 7 rank points", "about 5 hands in 54 games", "4,500 points", "18th turn", "7,700",
                       "5,200, 8,300, 8,300 and 7,700", "at 99%", "93% to 99%", "62.3%", "74.4%", "3.6 standard deviations",
                       "82.4% of the time, against 94.2%", "61 you declared earned +3,018", "15 you kept dama +640",
                       "4 in 62 games", "16 in 54 since", "1,079"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        for lang in PAGES:
            links = re.findall(r'href="(replay\.html\?[^"]+)"', section(lang))
            self.assertEqual(links, ["replay.html?g=261016-7cc3ee5d-65fc-4333-a381-7cb5db6923eb&amp;r=South+4-0&amp;t=18",
                                     "replay.html?g=261016-76fdbc7c-8746-4b3b-97fd-c0b15a1e161f&amp;r=East+4-0&amp;t=5"])
            for link in links:
                self.assertTrue((ROOT / "site" / "replays" / f"{link.split('g=')[1].split('&')[0]}.json").exists(), link)

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))


if __name__ == "__main__":
    unittest.main()
