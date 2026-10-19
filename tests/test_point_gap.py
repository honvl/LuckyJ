"""Chapter 47 of the personal guide: the point gap before and after the guide's dora chapters, and the correction it makes to chapter 45.

Every figure the chapter cites comes from ``analysis/point-gap-2026-10-19.json`` (``scripts/mine_point_gap.py``).
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
DATA = json.loads((ROOT / "analysis" / "point-gap-2026-10-19.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str, ident: str = "point-gap") -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index(f'<section class="point" id="{ident}">')
    return page[start:page.index("</section>", start)]


def prose(lang: str, text: str | None = None) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang) if text is None else text)
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheSplitTests(unittest.TestCase):
    def test_the_games(self):
        self.assertEqual((DATA["guide"], DATA["games"], DATA["rank_points_per_1000_points"]), ("2026-09-22 14:17", {"before": 80, "since": 136}, 8.3))

    def test_the_edges_and_the_gap_on_wins(self):
        e = DATA["edges"]
        self.assertEqual([(e[k]["win"]["points"], e[k]["win"]["se"]) for k in ("before", "since", "luckyj")], [(-1809, 1283), (1227, 1212), (2448, 419)])
        g = DATA["gap_on_wins"]
        self.assertEqual([(g[k]["wins_points"], g[k]["se"], g[k]["rank_points"]) for k in ("before", "since")], [(4257, 1350, 35.3), (1221, 1282, 10.1)])
        # the 80 games before the guide carry two thirds of chapter 45's 2,345
        self.assertAlmostEqual((80 * 4257 + 136 * 1221) / 216, 2345, delta=2)
        self.assertGreater(80 * 4257 / 216 / 2345, 0.66)

    def test_the_wins_by_kind(self):
        w = DATA["wins"]
        self.assertEqual([(w[k]["wins_per_100"], w[k]["average"]) for k in ("before", "since", "jade_human", "luckyj")],
                         [(21.3, 5992), (23.3, 6612), (21.1, 6789), (22.9, 7317)])
        self.assertEqual([(w[k]["riichi"]["average"], w[k]["open"]["average"], w[k]["dama"]["average"]) for k in ("before", "since", "jade_human", "luckyj")],
                         [(8021, 4342, 5880), (9034, 4781, 5964), (8994, 4962, 5575), (9227, 5477, 7676)])
        self.assertEqual([(w[k]["open_hands"]["four_han_or_more_pct"], w[k]["open_hands"]["net_a_hand"]) for k in ("before", "since", "jade_human", "luckyj")],
                         [(13, -18), (21, 560), (23, 255), (27, 578)])
        self.assertEqual(w["since"]["dama"]["wins"], 36)
        self.assertEqual(w["luckyj"]["dama"]["wins"], 245)


class TheDoraHandTests(unittest.TestCase):
    def test_the_table(self):
        d = DATA["dealt"]
        self.assertEqual([(d[k]["dora"]["hands"], d[k]["dora"]["tenpai_pct"], d[k]["dora"]["won_of_tenpai_pct"], d[k]["dora"]["average_win"], d[k]["dora"]["win_points_a_hand"])
                          for k in ("you_before", "you_since", "luckyj")],
                         [(411, 51.6, 36.8, 6505, 1235), (725, 51.6, 45.7, 7597, 1792), (5692, 51.7, 47.2, 8366, 2040)])
        self.assertEqual([(d[k]["dora"]["declared_pct"], d[k]["dora"]["live_tiles_at_the_first_tenpai"]) for k in ("you_before", "you_since", "luckyj")],
                         [(66.7, 4.91), (75.4, 4.92), (74.2, 4.98)])
        self.assertEqual([d[k]["no_dora"]["win_points_a_hand"] for k in ("you_before", "you_since", "luckyj")], [1320, 1274, 1307])

    def test_what_the_wins_are_made_of(self):
        w = DATA["dora_wins"]
        self.assertEqual([(w[k]["shape_yaku_pct"], w[k]["flush_pct"], w[k]["kept_all_dealt_pct"]) for k in ("you_before", "you_since", "luckyj")],
                         [(39.7, 1.3, 79), (53.2, 10.5, 84), (54.9, 7.1, 85)])
        self.assertEqual((w["you_since"]["wins"], w["luckyj"]["wins"]), (171, 1388))

    def test_what_is_left(self):
        d = DATA["dealt"]
        self.assertEqual(d["you_since"]["dora"]["average_win_se"], 341)
        self.assertEqual([(d[k]["two_or_more"]["average_win"], d[k]["two_or_more"]["won_pct"]) for k in ("you_since", "luckyj")], [(9587, 23.8), (9524, 28.1)])
        self.assertEqual(DATA["gap_on_dora_hands"], {"points_a_hand": 248, "se_a_hand": 155, "points_a_game": 1322, "se_a_game": 824, "rank_points_a_game": 11.0})
        self.assertEqual(DATA["six_cuts"], {"points": 68200, "games": 67, "points_a_game": 1018, "rank_points_a_game": 8.4})


class TheMinerTests(unittest.TestCase):
    def test_yaku_from_either_log(self):
        import mine_point_gap as m

        majsoul = [0, 0, 0, "30符4飜7700点", "立直(1飜)", "断幺九(1飜)", "ドラ(1飜)", "赤ドラ(1飜)"]
        tenhou = [0, 0, 0, "40符5飜8000点", "yaku1(1飜)", "yaku34(2飜)", "yaku52(2飜)"]
        self.assertEqual(m.parse_yaku(majsoul), [("riichi", 1), ("tanyao", 1), ("dora", 1), ("red", 1)])
        self.assertEqual(m.parse_yaku(tenhou), [("riichi", 1), ("honitsu", 2), ("dora", 2)])


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("136 games since 22 September", "80 games before it and 136 after", "1,809 points a game below", "error of 1,283", "1,227 above", "error of 1,212",
                       "2,448 above its humans", "from 4,257 to 1,221", "35.3 rank points a game and then 10.1", "error of 1,282", "two thirds",
                       "36.8% of those tenpais", "47.2%", "39.7% of your wins carried a shape yaku against 54.9%", "1.3% of your wins, now 10.5%", "7.1%", "75.4% of the time",
                       "74.2%", "4.92 live tiles", "4.98", "7,597 against 8,366", "error of 341", "9,587 against 9,524", "23.8% against 28.1%", "248 points less",
                       "error of 155", "1,322 points a game, 11.0 rank points", "error of 824", "68,200 points over 67 games", "1,018 a game and 8.4 rank points",
                       "18,000", "4,000/8,000", "60 more games", "5,964 (36 wins)", "7,676 (245)", "4 han or more without the riichi", "1,274", "1,307"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = ["replay.html?g=261011-d33a542c-0b96-40a8-9c4f-2edae62a9ae7&amp;r=South+1-2&amp;t=17",
                "replay.html?g=261003-a2261800-30b4-480a-95e4-2d04e2b94064&amp;r=East+1-1&amp;t=6",
                "replay.html?g=260930-22b377c9-b876-49c6-abf8-6b843f7eb454&amp;r=East+1-0&amp;t=19"]
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


class TheCorrectionTests(unittest.TestCase):
    def test_chapter_45_marks_the_changed_sentences(self):
        for lang in PAGES:
            ch = section(lang, "rank-drain")
            self.assertEqual(len(re.findall(r'<mark id="fix-45-(?:wins|rule)" class="guide-changed">', ch)), 2)
            for ident in ("fix-45-wins", "fix-45-rule"):
                self.assertEqual(PAGES[lang].read_text(encoding="utf-8").count(f'href="#{ident}"'), 1)
        wins = re.search(r'<mark id="fix-45-wins".*?</mark>', section("en", "rank-drain"), re.S).group(0)
        for phrase in ("216 games", "80 of them", "22 September", "1,227", "2,448", "1,221", "1,282"):
            self.assertIn(phrase, prose("en", wins), phrase)

    def test_the_news_list_has_one_latest_and_the_correction(self):
        for lang, latest, correction in (("en", "Chapter 47 answers your question about the point gap", "Chapter 45 named the size of your wins"),
                                         ("ja", "第47章は、点数の差についての質問に答える", "第45章は、あなたのアガリの大きさをLuckyJとの最大の差とした")):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            first = page.index('<li class="is-latest">')
            self.assertLess(first, page.index(latest))
            self.assertLess(page.index(latest), page.index(correction))
            self.assertIn('class="is-correction"', page[page.index(latest):page.index(correction)])

    def test_the_chapter_list_and_the_chain_of_links(self):
        en = PAGES["en"].read_text(encoding="utf-8")
        ja = PAGES["ja"].read_text(encoding="utf-8")
        self.assertIn("Forty-seven chapters", en)
        self.assertIn("47の章", ja)
        for page in (en, ja):
            self.assertEqual(page.count('<span class="contents-num">46</span>'), 1)
            self.assertEqual(page.count('<span class="contents-num">47</span>'), 1)
            self.assertIn('href="#count-copies"><span class="chapter-next-label">', page)
            self.assertIn('href="#point-gap"><span class="chapter-next-label">', page)
        self.assertIn("mine_defense_spots.py", en)
        self.assertIn("mine_point_gap.py", ja)


if __name__ == "__main__":
    unittest.main()
