"""Chapter 49 of the personal guide: a high net win efficiency and still a fourth in about 22% of games.

Every figure the chapter cites comes from ``analysis/fourth-rate-2026-10-22.json`` (``scripts/mine_fourth_rate.py``).
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
DATA = json.loads((ROOT / "analysis" / "fourth-rate-2026-10-22.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="fourth-rate">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheEfficiencyTests(unittest.TestCase):
    def test_the_table(self):
        e = DATA["efficiency"]
        keys = ("win_efficiency", "deal_in_loss", "net_win_efficiency", "tsumo_paid", "draws_and_sticks", "real_points_a_hand")
        self.assertEqual([[e[g][k] for k in keys] for g in ("last_100", "all_2026", "jade_human", "luckyj")],
                         [[1567, 628, 939, -501, -162, 276], [1465, 573, 892, -545, -172, 174], [1421, 755, 666, -541, -185, -60], [1677, 546, 1131, -578, -191, 363]])
        self.assertEqual(e["amae_career"]["net_win_efficiency"], 772)
        for g in ("last_100", "all_2026", "jade_human", "luckyj"):
            self.assertEqual(e[g]["win_efficiency"] - e[g]["deal_in_loss"], e[g]["net_win_efficiency"])
        self.assertEqual(e["last_100"]["hands"], 1032)

    def test_the_places(self):
        p = DATA["places"]
        self.assertEqual((p["last_100"]["places"], p["last_100"]["rank_points_a_game"], p["last_100"]["mean_score"]), ([32, 22, 23, 23], -3.3, 27851))
        self.assertEqual((p["all_2026"]["fourth_pct"], p["jade_human_fourth_pct"], p["luckyj_fourth_pct"]), (20.3, 26.5, 16.9))
        self.assertEqual(DATA["formula"], {"rank_points_by_place": {"1": 144, "2": 66, "3": -10, "4": -272}, "break_even_fourth_pct": 20.3})


class TheFourthsTests(unittest.TestCase):
    def test_by_place(self):
        b = DATA["by_place"]
        self.assertEqual([(b[k]["games"], b[k]["points_won"], b[k]["deal_ins"], b[k]["tsumo_paid"], b[k]["with_a_big_deal_in_pct"]) for k in "1234"],
                         [(32, 28578, 3491, 3388, 12), (22, 15018, 3359, 4632, 14), (23, 10457, 7052, 6274, 39), (23, 5748, 13070, 7043, 70)])
        self.assertEqual(DATA["big_deal_in_games"], {"games_with_one": 32, "fourths_among_them": 16, "games_without": 68, "fourths_among_those": 7})

    def test_the_fourths_that_turn_on_one_deal_in(self):
        f = DATA["fourths"]
        self.assertEqual((f["count"], f["no_deal_in"], f["with_a_big_deal_in"], f["not_fourth_without_the_biggest"]), (23, 2, 16, 14))
        by = {x["game"][:15]: x for x in f["list"]}
        self.assertEqual([(by[g]["paid"], by[g]["place_without"]) for g in ("261008-ce956cd8", "261011-10d214ef", "261020-cab68a97")], [(12300, 3), (12000, 3), (12000, 3)])

    def test_the_simulation(self):
        s = DATA["simulation"]
        self.assertEqual((s["big_deal_ins"], s["games_with_one"]), (44, 32))
        self.assertEqual((s["avoid_0"]["fourths_of_100"], s["avoid_0"]["rank_points_a_game"]), (23.0, -3.3))
        self.assertEqual([(s[k]["fourths_of_100"], s[k]["rank_points_a_game"]) for k in ("avoid_25", "avoid_50")], [(19.9, 7.9), (17.2, 18.4)])


class TheMinerTests(unittest.TestCase):
    def test_places_break_ties_by_seat(self):
        import mine_fourth_rate as m

        self.assertEqual(m.places_of([25000, 25000, 30000, 20000]), [2, 3, 1, 4])


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("23 of 100", "939", "666", "1,131", "772", "1,567", "628", "1,677", "546", "501 a hand", "162", "+276, not 939", "26.5% for the humans, 23% for you and 16.9% for LuckyJ",
                       "272 rank points", "144", "20.3%", "At 23% you are at 3.3 rank points a game", "27,851", "44 hands of 7,000 or more, in 32 games", "16 times, 50%", "7 times, 10%",
                       "28,578", "13,070", "7,043", "Of the 23 fourths, 2 had no deal-in", "16 had one of 7,000 or more", "14 would not have been fourths", "12,300", "12,000",
                       "19.9 fourths and +7.9", "17.2 fourths and +18.4", "1,032 hands", "227 of 2026", "400 times"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = ["replay.html?g=261008-ce956cd8-7f83-4165-97aa-e5be24fff49c&amp;r=East+1-1&amp;t=13",
                "replay.html?g=261011-10d214ef-4cc3-414b-ab98-38e19ba751e2&amp;r=East+3-0&amp;t=11",
                "replay.html?g=261020-cab68a97-96dc-4b97-9353-53ec05899810&amp;r=South+4-0&amp;t=6"]
        for lang in PAGES:
            links = re.findall(r'href="(replay\.html\?[^"]+)"', section(lang))
            self.assertEqual(links, want)
            for link in links:
                self.assertTrue((ROOT / "site" / "replays" / f"{link.split('g=')[1].split('&')[0]}.json").exists(), link)

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))
        self.assertLessEqual(len(re.findall(r"\bnot [a-z ]+, it is\b|\bis not [a-z ]+\. It is\b", prose("en"))), 1)

    def test_the_notice_is_in_the_list_and_the_chain_of_links(self):
        # chapter 49 was the latest notice until chapter 50 went up on 23 October
        for lang, label in (("en", '<a href="#fourth-rate">Chapter 49 answers why a high net win efficiency still gives fourths'), ("ja", '<a href="#fourth-rate">第49章は、純打点効率が高くても4着になる理由に答える')):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            self.assertIn(label, page)
            self.assertEqual(page.count('<span class="contents-num">49</span>'), 1)
            self.assertIn('href="#fourth-rate"><span class="chapter-next-label">', page)


if __name__ == "__main__":
    unittest.main()
