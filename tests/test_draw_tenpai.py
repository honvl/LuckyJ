"""Chapter 52 of the personal guide: 58 games toward Celestial, the calls, the safe tiles and tenpai at the draw.

Every figure the chapter cites comes from ``analysis/draw-tenpai-2026-11-18.json`` (``scripts/mine_draw_tenpai.py``).
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
DATA = json.loads((ROOT / "analysis" / "draw-tenpai-2026-11-18.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
LINKS = ["replay.html?g=261115-8f60ec0b-2ce5-4e9e-a9b2-d7df0a74dfa9&amp;r=South+1-0&amp;t=17",
         "replay.html?g=261118-a0e0c4fb-60e1-4ca1-b013-38465dead06e&amp;r=East+4-0&amp;t=16"]


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="draw-tenpai">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'<nav class="chapter-next".*?</nav>', "", section(lang), flags=re.S)  # the next chapter's title is not this chapter's prose
    text = re.sub(r'href="[^"]*"', "", text)
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


def replay_hand(prefix: str, rnd: str) -> tuple[dict, dict]:
    game = json.loads(next((ROOT / "site/replays").glob(f"{prefix}-*.json")).read_text())
    return game, next(h for h in game["hands"] if h["round"] == rnd)


class TheResultsTests(unittest.TestCase):
    def test_the_58_games(self):
        r = DATA["results"]
        self.assertEqual(DATA["windows"], {"before": [80, 303], "climb": [303, 335], "recent": [335, 361], "new": [303, 361], "last_10": [351, 361]})
        self.assertEqual([(r[k]["places"], r[k]["rank_points"]) for k in ("new", "climb", "recent", "last_10")],
                         [([20, 16, 17, 5], 2438), ([13, 9, 10, 0], 2441), ([7, 7, 7, 5], -3), ([0, 4, 5, 1], -87)])
        self.assertEqual((r["new"]["rank_points_a_game"], r["climb"]["rank_points_a_game"]), (42.0, 76.3))
        self.assertEqual(r["rank"], {"start": 5620, "after_climb": 8061, "now": 8058, "best": 8265})

    def test_the_thirds(self):
        r = DATA["results"]
        self.assertEqual((r["new"]["third_pct"], r["before"]["third_pct"], r["thirds"]), (29.3, 24.2, {"expected": 14.0, "p_at_least": 0.222}))

    def test_where_the_points_went(self):
        s = DATA["sources"]
        self.assertEqual([[s[k][c] for c in ("won", "deal_ins", "tsumo_paid", "draws", "net")] for k in ("before", "climb", "recent")],
                         [[16579, 6072, 5905, -249, 2541], [20619, 2916, 6225, -234, 9681], [14704, 6596, 6554, -385, -23]])


class TheCallTests(unittest.TestCase):
    def test_the_hand_mix(self):
        st = DATA["style"]
        keys = ("open_pct", "riichi_pct", "average_win", "open_net", "closed_net", "with_yaku_declared_pct")
        self.assertEqual([[st[k][c] for c in keys] for k in ("before", "climb", "recent", "luckyj")],
                         [[35.3, 18.2, 6710, 626, 32, 63.5], [37.3, 15.4, 7095, 2138, 215, 54.3], [43.3, 11.6, 5792, 401, -310, 48.6], [36.5, 19.3, 7317, 611, 220, 67.2]])
        self.assertEqual((st["new"]["open_net"], st["new"]["with_yaku_declared_pct"], st["new"]["with_yaku_closed_tenpais"]), (1287, 51.8, 83))

    def test_mortal_on_the_calls_and_the_riichi(self):
        m = DATA["mortal"]
        self.assertEqual((m["new"]["call_chances_a_game"], m["new"]["you_call_pct"], m["new"]["mortal_calls_pct"]), (33.45, 20.3, 21.0))
        self.assertEqual((m["recent"]["you_call_pct"], m["recent"]["mortal_calls_pct"]), (21.2, 20.7))
        self.assertEqual((m["new"]["riichi_chances"], m["new"]["you_declare_pct"], m["new"]["mortal_declares_pct"]), (133, 52.6, 56.2))


class TheSafeTileTests(unittest.TestCase):
    def test_genbutsu_held(self):
        s = DATA["safe_tiles"]
        self.assertEqual([(s[k]["closed_held_pct"], s[k]["open_held_pct"]) for k in ("before", "climb", "recent", "luckyj")], [(85.3, 78.0), (83.8, 60.7), (80.0, 80.0), (85.3, 80.2)])
        self.assertEqual([(s[k]["closed_held"], s[k]["closed_first_discards"], s[k]["open_held"], s[k]["open_first_discards"]) for k in ("before", "climb", "recent")],
                         [(586, 687, 138, 177), (83, 99, 17, 28), (60, 75, 24, 30)])
        self.assertEqual(s["new_open_without_genbutsu"], {"first_discards": 17, "dealt_in_that_hand": 0})
        self.assertEqual(s["new"]["open_first_discards"] - s["new"]["open_held"], 17)


class TheDrawTests(unittest.TestCase):
    def test_the_draw_table(self):
        d = DATA["draws"]
        self.assertEqual([(d[k]["tenpai_pct"], d[k]["draw_points_a_game"], d[k]["riichi_out_share_pct"], d[k]["riichi_out"]["tenpai_pct"], d[k]["no_riichi"]["tenpai_pct"]) for k in ("before", "new", "luckyj")],
                         [(43.1, -249, 54.7, 24.6, 65.5), (37.5, -302, 62.5, 20.0, 66.7), (46.7, -42, 51.1, 28.4, 65.8)])
        self.assertEqual((d["jade_human"]["tenpai_pct"], d["jade_human"]["draw_points_a_game"]), (48.8, 87))
        gap = d["luckyj"]["draw_points_a_game"] - d["new"]["draw_points_a_game"]
        self.assertEqual((gap, round(gap * DATA["rank_points_per_1000_points"] / 1000, 1)), (260, 2.2))

    def test_the_late_calls_pay(self):
        c = DATA["late_calls"]
        self.assertEqual([(c[k]["a_game"], c[k]["won_pct"], c[k]["net"]) for k in ("new", "luckyj")], [(0.6, 34.3, 1129), (0.41, 27.4, 714)])

    def test_the_late_pushes(self):
        p = DATA["late_pushes"]
        self.assertEqual([(p[k]["pushed"]["a_game"], p[k]["pushed"]["median_outs"]) for k in ("you", "luckyj")], [(0.53, 11.0), (0.49, 11.0)])
        self.assertEqual(p["you"]["mortal"], {"rated": 150, "under_25": 48, "at_least_25": 102})
        rows = [(p["you"][a][b]["hands"], p["you"][a][b]["draw_tenpai_pct"], p["you"][a][b]["net"], p["luckyj"][a][b]["draw_tenpai_pct"], p["luckyj"][a][b]["net"])
                for a, b in (("pushed", "more_outs"), ("pushed", "few_outs"), ("safe_only", "more_outs"), ("safe_only", "few_outs"))]
        self.assertEqual(rows, [(120, 10.8, -1139, 15.1, -753), (30, 0.0, -2057, 8.7, -1350), (110, 12.7, -660, 13.6, -770), (57, 8.8, -1049, 4.6, -1236)])
        self.assertEqual(p["you"]["pushed"]["few_outs"]["dealt_in_pct"], 20.0)
        cost = p["you"]["pushed"]["few_outs"]["a_game"] * (p["you"]["safe_only"]["few_outs"]["net"] - p["you"]["pushed"]["few_outs"]["net"])
        self.assertEqual((round(cost, -1), round(cost * DATA["rank_points_per_1000_points"] / 1000, 1)), (110, 0.9))


class TheExampleTests(unittest.TestCase):
    def test_the_chi_then_the_west(self):
        game, hand = replay_hand("261115-8f60ec0b", "South 1-0")
        hero, ev = game["hero"], hand["ev"]
        ais = {a["i"]: a for a in hand["ai"]}
        call = next(i for i, x in enumerate(ev) if x[0] == "c" and x[1] == hero)
        self.assertEqual((ev[call][3], ev[call][4], ev[call + 1][2]), ("6m", ["7m", "8m"], "W"))
        self.assertEqual(round(100 * dict(ais[call]["p"])["7s"], 1), 86.6)
        self.assertEqual(round(100 * dict(ais[call]["p"])["W"], 1), 12.9)
        self.assertGreater(dict(ais[call - 1]["p"])["chi-mid"], 0.5)
        self.assertEqual((hand["scores"][hero], hand["end"]["kind"], hand["end"]["deltas"][hero]), (16900, "draw", -1500))
        self.assertEqual(sorted(hand["scores"]).index(hand["scores"][hero]), 0)

    def test_the_dealers_nine_of_dots(self):
        game, hand = replay_hand("261118-a0e0c4fb", "East 4-0")
        hero, ev = game["hero"], hand["ev"]
        ais = {a["i"]: a for a in hand["ai"]}
        cut = next(i for i, x in enumerate(ev) if x[0] == "d" and x[1] == hero and x[2] == "9p" and i > 100)
        p = dict(ais[cut - 1]["p"])
        self.assertEqual((round(100 * p["5p"], 1), round(100 * p["9p"], 1)), (82.5, 0.4))
        self.assertEqual((hand["scores"][hero], max(hand["scores"]), hand["end"]["deltas"][hero]), (30200, 30200, -1500))

    def test_the_games_ended_as_the_chapter_says(self):
        index = {g["id"]: g for g in json.loads((ROOT / "site/replays/index.json").read_text())["games"]}
        self.assertEqual([(index[l.split("g=")[1].split("&")[0]]["date"], index[l.split("g=")[1].split("&")[0]]["placement"]) for l in LINKS],
                         [("2026-11-14 20:48", 4), ("2026-11-17 18:10", 3)])


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("58 games from 11 to 18 November", "20 firsts, 16 seconds, 17 thirds and 5 fourths", "+2,438 rank points, 42.0 a game, from 5,620 to 8,058", "best of 8,265 on 17 November",
                       "13, 9, 10, 0 for +2,441, 76.3 a game", "7, 7, 7, 5 for 3", "0, 4, 5, 1 for 87", "17 thirds in 58 games is 29.3%", "24.2%", "14.0", "22.2% of the time", "10 thirds in 32",
                       "6,596 a game in deal-ins, near your usual 6,072", "2,916", "14,704 a game, against your usual 16,579", "+1,287 points", "+611", "20.3% of your 33.45 call chances",
                       "21.0%", "21.2% against 20.7%", "11.6% of your hands", "18.2%", "19.3%", "51.8% of 83 times", "67.2%", "63.5%", "56.2% of the time and you 52.6%, over 133 chances",
                       "5,792", "17 of 28", "24 of 30", "none of the 17 open hands", "302 points a game", "loses 42", "48.8%", "gain 87", "260 points, 2.2 rank points", "66.7% against 65.8%",
                       "62.5% of your draws against 51.1%", "0.60 times a game", "34.3%", "+1,129 each", "0.41 times a game", "+714", "0.53 times a game, LuckyJ 0.49", "median of 11",
                       "102 of your 150", "10.8% of the time, LuckyJ", "15.1%", "120 hands", "none of your 30", "20.0% dealt in", "2,057 points", "cost 1,049", "1,350 against", "1,236",
                       "0.11 hands a game, about 110 points, 0.9 rank points", "16,900", "86.6%", "12.9%", "1,500", "30,200", "82.5%", "0.4%", "8 or more unseen tiles", "chapter 36",
                       "281 games", "only 36 of them", "1,079 Tokujou games"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        for lang in PAGES:
            links = re.findall(r'href="(replay\.html\?[^"]+)"', section(lang))
            self.assertEqual(links, LINKS)
            for link in links:
                self.assertTrue((ROOT / "site" / "replays" / f"{link.split('g=')[1].split('&')[0]}.json").exists(), link)

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))
        self.assertLessEqual(len(re.findall(r"\bnot [a-z ]+, it is\b|\bis not [a-z ]+\. It is\b", prose("en"))), 1)

    def test_the_notice_and_the_chain_of_links(self):
        for lang, latest in (("en", '<a href="#draw-tenpai">Chapter 52 looks at your 58 games'), ("ja", '<a href="#draw-tenpai">第52章は、魂天へ向かう58半荘を調べる')):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            self.assertEqual(page.count(latest), 1)  # chapter 53 is the latest notice now (tests/test_tier_ranking.py)
            self.assertEqual(page.count('<span class="contents-num">52</span>'), 1)
            self.assertIn('href="#draw-tenpai"><span class="chapter-next-label">', page)
            self.assertIn("mine_draw_tenpai.py", page)
            self.assertEqual(page.count('aria-label="After the chapters"') + page.count('aria-label="本編の後"'), 1)
        self.assertIn("Fifty-five chapters", PAGES["en"].read_text(encoding="utf-8"))
        self.assertIn("55の章", PAGES["ja"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
