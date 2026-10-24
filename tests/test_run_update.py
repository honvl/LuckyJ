"""Chapter 50 of the personal guide: fifteen more games after chapter 48's ten, and the correction it makes to chapter 48.

Every figure the chapter cites comes from ``analysis/run-update-2026-10-23.json`` (``scripts/mine_run_update.py``).
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
DATA = json.loads((ROOT / "analysis" / "run-update-2026-10-23.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str, ident: str = "run-update") -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index(f'<section class="point" id="{ident}">')
    return page[start:page.index("</section>", start)]


def prose(lang: str, text: str | None = None) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang) if text is None else text)
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheResultsTests(unittest.TestCase):
    def test_the_results(self):
        r = DATA["results"]
        self.assertEqual([(r[k]["games"], r[k]["places"], r[k]["rank_points"], r[k]["rank_points_a_game"]) for k in ("before", "first", "second", "run")],
                         [(217, [57, 57, 58, 45], -831, -3.8), (10, [7, 2, 0, 1], 866, 86.6), (15, [5, 4, 4, 2], 473, 31.5), (25, [12, 6, 4, 3], 1339, 53.6)])
        self.assertEqual((r["since_the_peak"]["games"], r["since_the_peak"]["rank_points"], r["since_the_peak"]["rank_points_a_game"]), (93, -1057, -11.4))

    def test_the_hands(self):
        h = DATA["hands"]
        self.assertEqual([(h[k]["hands"], h[k]["won_pct"], h[k]["tenpai_by_turn_10_pct"], h[k]["open_pct"], h[k]["big_per_100"]) for k in ("before", "first", "second", "run")],
                         [(2259, 22.4, 31.2, 36.0, 3.4), (103, 30.1, 38.8, 40.8, 1.0), (154, 33.1, 37.0, 40.3, 3.9), (257, 31.9, 37.7, 40.5, 2.7)])
        self.assertEqual(h["second"]["z_won_vs_before"], 3.1)
        self.assertEqual(sum(1 for k in ("first", "second") if h[k]["tsumo_wins"]), 2)

    def test_the_bad_deals_held(self):
        p = DATA["poor_deals"]
        self.assertEqual([(p[k]["hands"], p[k]["won"], p[k]["won_pct"]) for k in ("before", "first", "second", "run")], [(1201, 198, 16.5), (61, 18, 29.5), (82, 24, 29.3), (143, 42, 29.4)])
        self.assertEqual((p["second"]["z_vs_before"], p["run"]["z_vs_before"]), (3.0, 3.8))
        s = DATA["speed"]
        self.assertEqual([(s[k]["you_removed_by_turn_9"], s[k]["others_removed_by_turn_9"]) for k in ("before", "second")], [(2.35, 2.32), (2.48, 2.31)])
        self.assertEqual([DATA["mortal"][k]["flagged_a_game"] for k in ("before", "first", "second")], [11.44, 10.4, 9.33])


class TheLoneRiichiTests(unittest.TestCase):
    def test_the_shutout_did_not_hold(self):
        l = DATA["lone_riichi"]
        self.assertEqual([(l[k]["hands"], l[k]["dealt_in"]) for k in ("before", "first", "second", "run")], [(947, 74), (41, 0), (65, 4), (106, 4)])
        self.assertEqual((l["usual_pct"], l["second"]["expected"], l["run"]["expected"], l["run"]["p_at_most"]), (7.8, 5.1, 8.3, 0.076))
        self.assertEqual(round(100 * 4 / 65, 1), 6.2)


class TheDealInTests(unittest.TestCase):
    def test_the_disliked_deal_ins(self):
        d = DATA["deal_ins"]
        self.assertEqual((d["count"], d["mortal_under_25"], sum(x["paid"] for x in d["low"])), (17, 7, 35100))
        self.assertEqual(round(35100 / 15), 2340)
        by = {(x["game"][:15], x["round"]): x for x in d["list"]}
        want = [(("261023-0dd4b0d4", "South 2-1"), "5s", 13, 8000, 0.002), (("261023-40608f64", "East 4-1"), "1s", 11, 8300, 0.064),
                (("261024-a1892da4", "South 4-0"), "7s", 8, 8000, 0.007), (("261024-a2a0e15e", "East 1-0"), "1p", 13, 3900, 0.005)]
        for key, tile, turn, paid, mortal in want:
            x = by[key]
            self.assertEqual((x["tile"], x["turn"], x["paid"], x["mortal"]), (tile, turn, paid, mortal))

    def test_the_two_fourths(self):
        f = {x["game"][:15]: x for x in DATA["fourths"]}
        self.assertEqual((f["261024-a1892da4"]["final"], f["261024-a1892da4"]["win_points"], f["261024-a1892da4"]["deal_in_points"], f["261024-a1892da4"]["tsumo_paid"]), (11200, 13000, 12900, 12900))
        self.assertEqual((f["261024-c177dc72"]["final"], f["261024-c177dc72"]["wins"], f["261024-c177dc72"]["win_points"], f["261024-c177dc72"]["tsumo_paid"], f["261024-c177dc72"]["deal_in_points"]),
                         (11900, 1, 3600, 11200, 2000))


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("15 more games: 5 firsts, 4 seconds, 4 thirds and 2 fourths, +473 rank points", "31.5 a game", "25 games at +1,339, 53.6 a game", "1,057 over 93 games", "11.4 a game", "2,396 over 68",
                       "57, 57, 58, 45", "7, 2, 0, 1", "5, 4, 4, 2", "12, 6, 4, 3", "22.4%", "30.1%", "33.1%", "31.9%", "16.5%, 198 of 1,201", "29.5%, 18 of 61", "29.3%, 24 of 82", "29.4%, 42 of 143",
                       "31.2%", "38.8%", "37.0%", "37.7%", "36.0%", "40.8%", "40.3%", "40.5%", "74 of 947, 7.8%", "0 of 41", "4 of 65", "4 of 106", "3.4", "3.9",
                       "24 of 82 hands dealt 4-shanten or worse, 29.3%", "3.8 standard errors", "2.48 shanten", "2.31", "2.35", "2.32", "3.1 standard errors", "9.33", "11.44",
                       "0 times in 41 such hands", "4 in 65, where 5.1 would be usual", "8.3 expected is a 7.6% chance", "17 times", "7 of them under 25%", "35,100 points, 2,340 a game", "1,524",
                       "98.4%", "6.4%", "8,300", "98.8%", "8,000", "3,900", "11,200", "11,900", "12,900", "6,000", "55 games", "29%"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = ["replay.html?g=261023-0dd4b0d4-25f1-464d-9735-b54cb785362b&amp;r=South+2-1&amp;t=13",
                "replay.html?g=261023-40608f64-436d-4515-8f45-4b74826ce80c&amp;r=East+4-1&amp;t=11",
                "replay.html?g=261024-a1892da4-29e8-4ae6-bd2d-7a3a16e0b878&amp;r=South+4-0&amp;t=8",
                "replay.html?g=261024-a2a0e15e-65cd-43c3-9053-c8d2b941ac0e&amp;r=East+1-0&amp;t=13"]
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
    def test_chapter_48_marks_the_sentence(self):
        for lang in PAGES:
            ch = section(lang, "ten-games")
            self.assertEqual(len(re.findall(r'<mark id="fix-48-lone" class="guide-changed">', ch)), 1)
            self.assertEqual(PAGES[lang].read_text(encoding="utf-8").count('href="#fix-48-lone"'), 1)
        marked = re.search(r'<mark id="fix-48-lone".*?</mark>', section("en", "ten-games"), re.S).group(0)
        for phrase in ("15 games", "4 times in 65 hands", "5.1", "chapter 50"):
            self.assertIn(phrase, prose("en", marked), phrase)

    def test_the_notices_and_the_chain_of_links(self):
        for lang, latest, correction in (("en", '<a href="#run-update">Chapter 50 tests chapter 48 on 15 more games', "Chapter 48 listed your 41 hands"),
                                         ("ja", '<a href="#run-update">第50章は、第48章をさらに15半荘で確かめる', "第48章は、1人のリーチに放銃しなかった41局を")):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            first = page.index('<li class="is-latest">')
            self.assertIn(latest, page[first:first + 300])
            self.assertLess(page.index(latest), page.index(correction))
            self.assertIn('class="is-correction"', page[page.index(latest):page.index(correction)])
            self.assertEqual(page.count('<span class="contents-num">50</span>'), 1)
            self.assertIn('href="#run-update"><span class="chapter-next-label">', page)
        self.assertIn("Fifty chapters", PAGES["en"].read_text(encoding="utf-8"))
        self.assertIn("50の章", PAGES["ja"].read_text(encoding="utf-8"))
        self.assertIn("mine_run_update.py", PAGES["en"].read_text(encoding="utf-8"))
        self.assertIn("mine_run_update.py", PAGES["ja"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
