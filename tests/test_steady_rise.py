"""Chapter 51 of the personal guide: why the rank is stuck and what a steady rise takes.

Every figure the chapter cites comes from ``analysis/steady-rise-2026-11-10.json`` (``scripts/mine_steady_rise.py``).
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
DATA = json.loads((ROOT / "analysis" / "steady-rise-2026-11-10.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
LINKS = ["replay.html?g=261024-118ce83e-b558-46d2-9f4e-c065f5aa7ac5&amp;r=South+2-2&amp;t=15",
         "replay.html?g=261025-cdcc1061-cbd2-44e8-b473-e65edc9a682c&amp;r=East+2-0&amp;t=11",
         "replay.html?g=261025-a1fd5d06-884e-4f41-afac-af027936f2dc&amp;r=South+4-0&amp;t=11",
         "replay.html?g=261026-fe735c5e-4625-4620-876a-ce6b1a73ff82&amp;r=South+2-0&amp;t=16",
         "replay.html?g=261027-98bda76e-0044-4e42-a95d-7df26624d497&amp;r=South+1-1&amp;t=7",
         "replay.html?g=261027-28f3770c-0dac-45a1-8b0c-6803af0a7ddf&amp;r=East+3-2&amp;t=18",
         "replay.html?g=261029-ea85ea87-bf8d-49e4-af7e-cb9f83e9cc2a&amp;r=South+4-0&amp;t=17",
         "replay.html?g=261103-2a236e21-57bd-4ed3-994a-b0c9888cfc32&amp;r=South+3-3&amp;t=4",
         "replay.html?g=261107-5c435428-ea0f-43d5-90da-ed09da830744&amp;r=South+4-0&amp;t=13",
         "replay.html?g=261110-99398e89-89bb-4f67-ab60-4a724183ed8b&amp;r=East+2-0&amp;t=9"]


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="steady-rise">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheGamesTests(unittest.TestCase):
    def test_the_61_games(self):
        r = DATA["results"]
        self.assertEqual(DATA["games"], {"all": 303, "before": 80, "since": 223, "run": 25, "new": 61})
        self.assertEqual((r["new"]["places"], r["new"]["rank_points"], r["new"]["rank_points_a_game"]), ([18, 17, 13, 13], -72, -1.2))
        self.assertEqual([(r[k]["games"], r[k]["places"], r[k]["rank_points"], r[k]["rank_points_a_game"]) for k in ("new_first", "new_second")],
                         [(30, [8, 7, 7, 8], -660, -22.0), (31, [10, 10, 6, 5], 588, 19.0)])
        self.assertEqual((r["sd_a_game"], r["se_over_the_new_games"], r["rank"]), (148.7, 1161, {"now": 5620, "peak": 6749, "below_the_peak": 1129}))
        self.assertEqual(round(r["rank"]["below_the_peak"] / r["since_the_guide"]["rank_points_a_game"], -1), 230)

    def test_chapter_50s_check_came_back_as_a_run(self):
        c = DATA["chapter_50_check"]
        self.assertEqual([(c[k]["games"], c[k]["dealt_4_shanten_or_worse"], c[k]["won"], c[k]["won_pct"]) for k in ("usual", "run", "new")],
                         [(217, 1201, 198, 16.5), (25, 143, 42, 29.4), (61, 359, 60, 16.7)])
        self.assertEqual([(c[k]["tenpai_by_turn_10_pct"], c[k]["won_pct_all_hands"], c[k]["dealt_in_pct"]) for k in ("usual", "run", "new")],
                         [(31.2, 22.4, 11.4), (37.7, 31.9, 10.1), (27.7, 21.1, 9.2)])


class ThePaceTests(unittest.TestCase):
    def test_every_seat_under_the_saint_3_formula(self):
        p = DATA["pace"]
        self.assertEqual([(p[k]["seat_games"], p[k]["fourth_pct"], p[k]["rank_points_a_game"]) for k in ("you", "jade_human", "luckyj", "tokujou_human")],
                         [(223, 19.7, 4.9), (669, 26.8, -26.1), (1079, 16.9, 16.2), (3237, 27.7, -29.8)])
        self.assertEqual((p["above_the_table"], p["luckyj_in_your_seat"]), ({"you": 31.0, "luckyj": 46.0}, 19.9))
        self.assertEqual(round(p["luckyj_in_your_seat"] - p["you"]["rank_points_a_game"]), 15)

    def test_the_chance_of_ending_ahead(self):
        self.assertEqual([(c["pace"], c["games_per_1000"], c["ahead_after_50_pct"], c["ahead_after_100_pct"], c["ahead_after_200_pct"]) for c in DATA["climb"]],
                         [(5, 200, 59, 63, 68), (11, 91, 70, 77, 85), (17, 59, 79, 87, 95), (20, 50, 83, 91, 97)])

    def test_the_edges(self):
        e = DATA["edges"]
        self.assertEqual([[e[k][c]["points"] for c in ("win", "deal_ins", "tsumo_paid", "other", "net")] for k in ("you", "luckyj", "gap")],
                         [[1418, 1947, 245, -210, 3400], [2448, 2440, 311, -138, 5061], [1030, 493, 66, 72, 1661]])
        self.assertEqual(e["you"]["win"]["se"], 971)


class TheLiveTileTests(unittest.TestCase):
    def test_the_table(self):
        t = DATA["live_tiles"]
        rows = [(t[k]["not_tenpai_at_a_riichi"]["throws_a_game"], t[k]["not_tenpai_at_a_riichi"]["live_pct"]) + tuple(t[k]["not_tenpai_at_a_riichi"]["live"][c] for c in ("a_game", "deal_in_pct", "points_a_throw", "points_a_game"))
                for k in ("you", "luckyj", "jade_human", "tokujou_human")]
        self.assertEqual(rows, [(18.21, 27.9, 5.08, 3.62, 248, 1257), (16.64, 27.4, 4.56, 2.78, 166, 756), (17.99, 35.2, 6.34, 4.69, 318, 2014), (17.34, 34.0, 5.9, 4.84, 309, 1822)])
        self.assertEqual((t["you"]["not_tenpai_at_a_riichi"]["live"]["deal_ins"], t["you"]["not_tenpai_at_a_riichi"]["live"]["throws"]), (41, 1132))
        self.assertEqual(t["gap_to_luckyj"], {"points_a_game": 501, "rank_points_a_game": 4.2, "z_deal_in_rate": 1.5})

    def test_what_matches_luckyj(self):
        t = DATA["live_tiles"]
        self.assertEqual([(t[k]["tenpai_at_a_riichi_live"]["deal_in_pct"], t[k]["tenpai_at_a_riichi_live"]["points_a_game"], t[k]["not_tenpai_at_two_calls"]["points_a_game"]) for k in ("you", "luckyj")],
                         [(8.6, 986, 431), (9.04, 1161, 479)])

    def test_mortal_marks_the_dangerous_ones(self):
        m = DATA["mortal_marker"]
        self.assertEqual([(m["not_tenpai"][k]["throws"], m["not_tenpai"][k]["a_game"], m["not_tenpai"][k]["deal_in_pct"], m["not_tenpai"][k]["points_a_throw"]) for k in ("disliked", "accepted")],
                         [(4772, 21.4, 0.9, 52.5), (19017, 85.28, 0.34, 17.3)])
        self.assertEqual([(m["live_at_a_riichi"][k]["throws"], m["live_at_a_riichi"][k]["deal_in_pct"], m["live_at_a_riichi"][k]["points_a_throw"]) for k in ("disliked", "accepted")],
                         [(367, 4.63, 339.8), (765, 3.14, 203.5)])
        self.assertEqual(m["at_the_accepted_cost"], {"points_a_game": 753, "rank_points_a_game": 6.2})


class TheLeverTests(unittest.TestCase):
    def test_the_deal_in_classes(self):
        l = DATA["levers"]
        self.assertEqual((l["deal_ins"], l["fourths"], l["points_a_game"]), (248, 44, 6072))
        self.assertEqual([(l["classes"][k]["deal_ins"], l["classes"][k]["points_a_game"], l["classes"][k]["fourths_handed_back"], l["classes"][k]["rank_points_a_game_handed_back"])
                          for k in ("cut_accepted", "cut_disliked", "riichi_accepted", "riichi_disliked")],
                         [(138, 3185, 28, 28.4), (50, 1301, 38, 12.1), (47, 1173, 38, 11.4), (13, 413, 43, 3.0)])
        self.assertEqual(l["classes"]["cut_accepted"]["deal_ins"] + l["classes"]["riichi_accepted"]["deal_ins"], 185)
        self.assertEqual(l["classes"]["cut_disliked"]["a_game"], 0.22)
        self.assertEqual([round(4.9 + x) for x in (DATA["mortal_marker"]["at_the_accepted_cost"]["rank_points_a_game"], l["classes"]["cut_disliked"]["rank_points_a_game_handed_back"])], [11, 17])

    def test_the_50_cuts(self):
        c = DATA["cuts"]["since_the_guide"]
        self.assertEqual((c["count"], c["points"], c["not_tenpai"], c["one_shanten"], c["two_shanten_or_worse"]), (50, 290200, 43, 18, 25))
        self.assertEqual((c["mortal_as_close_or_closer"], c["mortal_tile_genbutsu"], c["held_a_genbutsu"], c["mortal_tile_deals_in"]), (42, 18, 37, 3))
        self.assertEqual(c["into"], {"riichi": {"count": 19, "points": 140700}, "caller": {"count": 25, "points": 109700}, "dama": {"count": 6, "points": 39800}})
        self.assertEqual(c["late_not_tenpai"], {"from_turn": 15, "count": 8, "points": 57600})
        n = DATA["cuts"]["new_games"]
        self.assertEqual((n["count"], n["points"], n["not_tenpai"]), (10, 65100, 8))

    def test_the_table_of_ten_is_the_list(self):
        new_from = "261024-118ce83e"
        rows = DATA["cuts"]["list"]
        start = next(i for i, c in enumerate(rows) if c["game"].startswith(new_from))
        ten = sorted(rows[start:], key=lambda c: LINKS.index(next(l for l in LINKS if c["game"] in l)))
        self.assertEqual(len(ten), 10)
        text = prose("en")
        for c, link in zip(ten, LINKS):
            self.assertEqual(link, f"replay.html?g={c['game']}&amp;r={c['round'].replace(' ', '+')}&amp;t={c['turn']}")
            self.assertIn(f"{c['mortal_tile_pct']}%", text)
            self.assertIn(f"{c['paid']:,}", text)
        self.assertEqual([c["shanten"] for c in ten], [1, 2, 0, 0, 1, 1, 1, 3, 1, 2])
        self.assertEqual([c["into"] for c in ten], ["riichi", "riichi", "riichi", "caller", "dama", "riichi", "caller", "riichi", "caller", "caller"])
        self.assertEqual([c["tile"] for c in ten], ["8s", "2p", "4m", "2s", "4p", "3m", "5sr", "7p", "N", "9p"])
        self.assertEqual([c["mortal_tile"] for c in ten], ["5pr", "5p", "6s", "5mr", "S", "5m", "4m", "F", "S", "2p"])
        self.assertEqual([c["mortal_tile_deals_in"] for c in ten], [False, True] + [False] * 8)


class TheExampleTests(unittest.TestCase):
    def hand(self, prefix: str, rnd: str) -> tuple[dict, dict]:
        game = json.loads(next((ROOT / "site/replays").glob(f"{prefix}-*.json")).read_text())
        return game, next(h for h in game["hands"] if h["round"] == rnd)

    def last_cut(self, game: dict, hand: dict) -> tuple[int, dict]:
        last = max(i for i, x in enumerate(hand["ev"]) if x[0] == "d" and x[1] == game["hero"])
        return last, next(a for a in hand["ai"] if a["i"] in (last - 1, last))

    def test_the_last_discard_of_the_hand(self):
        game, hand = self.hand("261027-28f3770c", "East 3-2")
        last, ai = self.last_cut(game, hand)
        self.assertEqual(last, len(hand["ev"]) - 1)  # nobody drew after it
        self.assertEqual(hand["ev"][last][2], "3m")
        self.assertEqual(hand["ev"][last - 1][:3], ["t", game["hero"], "9m"])
        p = dict(ai["p"])
        self.assertEqual((round(100 * p["5m"], 1), round(100 * p["5mr"], 1), round(100 * p["3m"], 1)), (88.4, 11.1, 0.1))
        win = hand["end"]["wins"][0]
        self.assertEqual((-win["deltas"][game["hero"]], win["value"]), (8600, "mangan, 8,000"))
        self.assertIn(["houtei", 1], win["yaku"])

    def test_two_threats(self):
        game, hand = self.hand("261029-ea85ea87", "South 4-0")
        hero = game["hero"]
        last, ai = self.last_cut(game, hand)
        self.assertEqual((hand["ev"][last][2], hand["scores"][hero], sorted(hand["scores"], reverse=True).index(hand["scores"][hero]) + 1), ("5sr", 26000, 2))
        self.assertEqual(round(100 * dict(ai["p"])["4m"], 1), 89.7)
        win = hand["end"]["wins"][0]
        self.assertEqual((-win["deltas"][hero], [y[0] for y in win["yaku"]]), (7700, ["tanyao", "dora", "red five"]))
        riichi = next(x[1] for x in hand["ev"] if x[0] == "r")
        self.assertNotEqual(riichi, win["seat"])
        self.assertEqual(hand["scores"][riichi], min(hand["scores"]))
        river = lambda seat: [x[2] for x in hand["ev"][:last] if x[0] == "d" and x[1] == seat]  # noqa: E731
        self.assertEqual(sum(t in ("5s", "5sr") for t in river(riichi)), 2)
        self.assertIn("4m", river(riichi))
        self.assertTrue({"1m", "7m"} <= set(river(win["seat"])))
        self.assertEqual(sorted(hand["after"], reverse=True).index(hand["after"][hero]) + 1, 3)

    def test_the_first_discard_after_a_riichi(self):
        game, hand = self.hand("261103-2a236e21", "South 3-3")
        hero = game["hero"]
        last, ai = self.last_cut(game, hand)
        self.assertEqual((hand["ev"][last][2], hand["ev"][last][3], hand["scores"][hero]), ("7p", 1, 9700))
        p = dict(ai["p"])
        self.assertEqual([round(100 * p[t], 1) for t in ("F", "8s", "9m", "7p")], [59.8, 19.7, 14.8, 0.1])
        win = hand["end"]["wins"][0]
        self.assertEqual((-win["deltas"][hero], ["ippatsu", 1] in win["yaku"]), (8900, True))
        river = [x[2] for x in hand["ev"][:last] if x[0] == "d" and x[1] == win["seat"]]
        self.assertTrue({"8s", "9m"} <= set(river))


class TheMinerTests(unittest.TestCase):
    def test_helpers(self):
        import mine_steady_rise as m

        self.assertEqual([m.code(t) for t in ("1m", "5mr", "9p", "5sr", "E", "F", "C")], [11, 15, 29, 35, 41, 46, 47])
        self.assertEqual(m.chance_ahead(0, 50, 148.7), 50)
        self.assertEqual(m.chance_ahead(20, 50, 148.7), 83)
        self.assertGreater(m.chance_ahead(5, 200, 148.7), m.chance_ahead(5, 50, 148.7))


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("61 games from 23 October to 10 November", "18 firsts, 17 seconds, 13 thirds and 13 fourths", "72 rank points, 1.2 a game", "5,620", "1,129 under the peak of 6,749",
                       "+4.9 rank points a game", "8, 7, 7, 8", "660, 22.0 a game down", "10, 10, 6, 5 for +588, 19.0 a game up", "148.7", "about 1,161",
                       "16.5%, 198 of 1,201", "29.4%, 42 of 143", "16.7%, 60 of 359", "27.7%", "9.2%", "60 of the 359",
                       "31.0 rank points a game above", "46.0 above", "about +19.9 a game in your seat", "about 15 rank points a game",
                       "41 times in 100", "about 230 games", "17 times in 100", "over 200 games",
                       "error of 971", "1,030 on wins", "493 on deal-ins", "27.9% of these discards against 27.4%", "1,257 points a game against 756", "gap of 501 is 4.2 rank points",
                       "41 deal-ins in 1,132 throws", "1.5 standard errors", "8.60%", "986 a game", "9.04% and 1,161", "431 a game", "479",
                       "23,789 discards", "4,772 of them under 25%, 21.4 a game", "0.90%", "52.5 points a throw", "19,017 it accepted dealt in 0.34% and cost 17.3",
                       "367", "4.63%", "339.8", "765 it accepted 3.14% at 203.5", "Of the 248 deal-ins, 185 came on a tile or a riichi that Mortal rated 25% or more", "12.1 rank points a game, which is a ceiling", "753 points a game, 6.2 rank points",
                       "290,200 points", "Of the 50, 43", "18 at 1-shanten and 25 at 2-shanten or worse", "In 42 of the 50", "18 times, and you held one 37 times", "dealt in 3 times",
                       "19 times (140,700 points)", "25 times (109,700)", "6 times (39,800)", "8 came on your 15th turn or later", "57,600 points", "10 of them, 65,100 points, 8 from",
                       "8,600", "88.4%", "11.1%", "26,000", "7,700", "89.7%", "9,700", "8,900", "59.8%", "19.7%", "14.8%", "0.22 a game", "303 games", "1,079 Tokujou games"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = LINKS + [LINKS[5], LINKS[6], LINKS[7]]
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

    def test_the_notice_and_the_chain_of_links(self):
        for lang, latest in (("en", '<a href="#steady-rise">Chapter 51 answers'), ("ja", '<a href="#steady-rise">第51章は、')):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            self.assertIn(latest, page)
            self.assertEqual(page.count('<span class="contents-num">51</span>'), 1)
            self.assertIn('href="#steady-rise"><span class="chapter-next-label">', page)
            self.assertIn("mine_steady_rise.py", page)
            self.assertEqual(page.count('aria-label="After the chapters"') + page.count('aria-label="本編の後"'), 1)


if __name__ == "__main__":
    unittest.main()
