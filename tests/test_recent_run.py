"""Chapter 48 of the personal guide: what changed in the ten games from 19 October 23:20 to 22 October.

Every figure the chapter cites comes from ``analysis/recent-run-2026-10-22.json`` (``scripts/mine_recent_run.py``).
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
DATA = json.loads((ROOT / "analysis" / "recent-run-2026-10-22.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="ten-games">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheRunTests(unittest.TestCase):
    def test_the_results(self):
        r = DATA["results"]
        self.assertEqual((DATA["games"], r["new"]["places"], r["new"]["rank_points"], r["new"]["rank_points_a_game"]), (10, [7, 2, 0, 1], 866, 86.6))
        self.assertEqual((r["before"]["games"], r["before"]["rank_points_a_game"]), (217, -3.8))
        self.assertEqual((r["luck"]["z_vs_before"], r["luck"]["p_firsts_at_least"], r["luck"]["first_rate_before"]), (1.93, 0.0048, 26.3))

    def test_the_hands_and_the_luck_in_them(self):
        h = DATA["hands"]
        self.assertEqual((h["new"]["hands"], h["old"]["hands"], h["new"]["tsumo_wins"], h["tsumo_wins_expected"], h["p_tsumo_wins_at_least"]), (103, 2259, 15, 8.0, 0.0138))
        self.assertEqual((h["new"]["riichi_wins"], h["old"]["riichi_wins"], h["new"]["won"], h["new"]["average_win"], h["old"]["average_win"]), (9, 203, 31, 7006, 6395))
        self.assertEqual((h["new"]["open"], h["old"]["open"], h["new"]["deal_ins_into"]["riichi"]), (42, 813, 2))
        self.assertEqual((h["new"]["average_deal_in"], h["old"]["average_deal_in"], h["new"]["big_deal_ins"]), (3980, 5109, 1))

    def test_the_bad_deals_got_won(self):
        d = DATA["poor_deals"]
        self.assertEqual([(d[k]["4+"]["hands"], d[k]["4+"]["won"], d[k]["4+"]["won_pct"]) for k in ("new", "old")], [(61, 18, 29.5), (1201, 198, 16.5)])
        self.assertEqual([(d[k]["3"]["hands"], d[k]["3"]["won_pct"]) for k in ("new", "old")], [(35, 28.6), (845, 26.9)])
        self.assertEqual([(d[k]["0-2"]["hands"], d[k]["0-2"]["won_pct"]) for k in ("new", "old")], [(7, 42.9), (213, 38.5)])
        self.assertEqual((d["z_4_plus_new_vs_old"], d["share_4_plus"]["new"], d["share_4_plus"]["old"]), (2.6, 59.2, 53.2))


class TheSpeedTests(unittest.TestCase):
    def test_speed(self):
        s = DATA["speed"]
        self.assertEqual([(s["you"][k]["haipai_shanten"], s["you"][k]["removed_by_turn_9"], s["you"][k]["tenpai_by_turn_10_pct"]) for k in ("old", "new")],
                         [(3.59, 2.35, 31.2), (3.74, 2.64, 38.8)])
        self.assertEqual([s["others"][k]["removed_by_turn_9"] for k in ("old", "new")], [2.32, 2.41])

    def test_callers_only_hands(self):
        c = DATA["situations"]["callers only"]
        self.assertEqual([(c[k]["hands"], c[k]["tenpai_pct"], c[k]["won_pct"]) for k in ("old", "new")], [(942, 54.2, 24.7), (44, 68.2, 34.1)])

    def test_the_early_game(self):
        e = DATA["early"]
        self.assertEqual([(e[k]["flagged_turns_1_to_6_a_game"], e[k]["lone_terminals_and_honors_after_discard"]["6"], e[k]["matched_pct"]) for k in ("old", "new")],
                         [(4.72, 1.43, 72.8), (3.1, 1.27, 74.6)])


class TheFoldTests(unittest.TestCase):
    def test_a_lone_riichi_never_found_you(self):
        l = DATA["lone_riichi"]
        self.assertEqual([(l[k]["hands"], l[k]["dealt_in"], l[k]["held_a_winning_tile"]) for k in ("old", "new")], [(947, 74, 609), (41, 0, 24)])
        self.assertEqual((l["expected_new_deal_ins"], l["p_no_deal_in"]), (3.2, 0.0356))
        self.assertEqual(round(100 * 74 / 947, 1), 7.8)

    def test_the_fold_rates(self):
        f = DATA["folds"]
        self.assertEqual([(f[k]["far_first_discard"]["n"], f[k]["far_first_discard"]["safe"]) for k in ("old", "new")], [(368, 261), (18, 15)])
        self.assertEqual([round(100 * f[k]["far_first_discard"]["safe"] / f[k]["far_first_discard"]["n"], 1) for k in ("old", "new")], [70.9, 83.3])
        self.assertEqual([(f[k]["had_genbutsu"], f[k]["decisions"]["n"]) for k in ("old", "new")], [(2871, 3311), (124, 135)])
        self.assertEqual([round(100 * f[k]["had_genbutsu"] / f[k]["decisions"]["n"], 1) for k in ("old", "new")], [86.7, 91.9])
        e = DATA["early"]
        self.assertEqual([(e[k]["safe_tile_against_a_riichi"]["you_pct"], e[k]["safe_tile_against_a_riichi"]["mortal_pct"]) for k in ("old", "new")], [(82.7, 82.8), (83.1, 84.9)])

    def test_the_deal_ins(self):
        d = DATA["deal_ins"]
        self.assertEqual([(d[k]["deal_ins"], d[k]["points_paid_a_game"], d[k]["mortal_under_25"]) for k in ("old", "new")], [(258, 6051, 60), (10, 3980, 4)])
        big = [x for x in d["list"] if x["paid"] >= 7000]
        self.assertEqual([(x["kind"], x["paid"], x["mortal"]) for x in big], [("riichi", 12300, 0.995)])
        self.assertEqual(sorted(x["paid"] for x in d["list"] if x["mortal"] < 0.25), [1000, 2300, 4200, 6100])


class TheMinerTests(unittest.TestCase):
    def test_tails_and_z(self):
        import mine_recent_run as m

        self.assertAlmostEqual(m.binom_tail_ge(0, 10, 0.3), 1.0)
        self.assertAlmostEqual(m.binom_tail_ge(10, 10, 0.5), 0.5 ** 10)
        self.assertEqual(m.two_prop_z((18, 61), (198, 1201)), 2.6)
        self.assertEqual(m.norm("5pr"), "5p")
        self.assertEqual(m.norm("5p"), "5p")


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("10 games from 19 October to 22 October, 103 hands", "217 games before", "+866 rank points, 86.6 a game", "1.9 standard errors", "3.8",
                       "0.5% of the time", "213 hands, 38.5% won", "7 hands, 42.9% won", "845 hands, 26.9% won", "35 hands, 28.6% won", "1,201 hands, 16.5% won", "61 hands, 29.5% won",
                       "59%, were dealt 4-shanten or worse, against 53%", "18 of those 61", "2.6 standard errors", "The 15 tsumo wins in 103 hands", "8.0 would be usual", "1.4% of the time",
                       "3.59", "3.74", "2.35", "2.64", "2.32", "2.41", "31.2%", "38.8%", "40.8%", "36.0%", "942", "54.2%", "68.2% of 44", "24.7%", "34.1%", "4.72", "3.1", "1.43", "1.27",
                       "947", "74, 7.8%", "609", "82.7%, Mortal 82.8%", "83.1%, Mortal 84.9%", "261 of 368, 70.9%", "15 of 18, 83.3%", "86.7%", "91.9%", "6,051", "3,980",
                       "dealt in 0 times", "3.2", "3.6% of the time", "24 of them", "15 times in 18", "124 of 135", "9 of 103 hands, 8.7%", "7,006", "6,395", "31 wins",
                       "Four of the 10 deal-ins", "1,000 to 6,100", "12,300", "99.5%", "about twenty numbers", "30 more games", "7.8%", "1,000/2,000", "3,900 all", "11,600"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = ["replay.html?g=261022-fd2b87ad-ac61-41fd-b9d5-5c421ffb029e&amp;r=East+1-1&amp;t=8",
                "replay.html?g=261022-88fceb37-c1c9-47c8-9ebd-1e8055a78685&amp;r=South+2-1&amp;t=15",
                "replay.html?g=261022-88fceb37-c1c9-47c8-9ebd-1e8055a78685&amp;r=South+2-2&amp;t=14",
                "replay.html?g=261022-fd2b87ad-ac61-41fd-b9d5-5c421ffb029e&amp;r=South+3-1&amp;t=7"]
        for lang in PAGES:
            links = re.findall(r'href="(replay\.html\?[^"]+)"', section(lang))
            self.assertEqual(links, want)
            for link in links:
                self.assertTrue((ROOT / "site" / "replays" / f"{link.split('g=')[1].split('&')[0]}.json").exists(), link)

    def test_the_examples_are_what_the_chapter_says(self):
        for prefix, rnd, shanten in (("261022-fd2b87ad", "East 1-1", 5), ("261022-88fceb37", "South 2-1", 4), ("261022-88fceb37", "South 2-2", 4)):
            path = next((ROOT / "site/replays").glob(f"{prefix}-*.json"))
            game = json.loads(path.read_text())
            hand = next(h for h in game["hands"] if h["round"] == rnd)
            win = next(w for w in hand["end"]["wins"] if w["seat"] == game["hero"])
            self.assertTrue(win)
        hand = next(h for h in json.loads(next((ROOT / "site/replays").glob("261022-fd2b87ad-*.json")).read_text())["hands"] if h["round"] == "East 1-1")
        self.assertEqual(hand["end"]["wins"][0]["value"], "30 fu 3 han, 1,000/2,000")

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))
        self.assertLessEqual(len(re.findall(r"\bnot [a-z ]+, it is\b|\bis not [a-z ]+\. It is\b", prose("en"))), 1)

    def test_the_notice_is_in_the_list_and_the_chain_of_links(self):
        # chapter 48 was the latest notice until chapter 49 went up on the same day
        for lang, label in (("en", '<a href="#ten-games">Chapter 48 looks at your last ten games'), ("ja", '<a href="#ten-games">第48章は、直近10半荘を調べる')):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            self.assertIn(label, page)
            self.assertEqual(page.count('<span class="contents-num">48</span>'), 1)
            self.assertIn('href="#ten-games"><span class="chapter-next-label">', page)


if __name__ == "__main__":
    unittest.main()
