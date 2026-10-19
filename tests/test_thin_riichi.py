"""Chapter 44 of the personal guide: the user's riichis with five or fewer live tiles.

Every figure the chapter cites comes from ``analysis/thin-riichi-2026-10-19.json`` (``scripts/mine_thin_riichi.py``).
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
DATA = json.loads((ROOT / "analysis" / "thin-riichi-2026-10-19.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
GROUPS = ("you", "jade_human", "luckyj", "tokujou_human")


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="thin-riichis">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheRiichisTests(unittest.TestCase):
    def test_the_counts(self):
        self.assertEqual((DATA["riichis"], DATA["games"]), (11444, 216))

    def test_thin_riichis_from_the_eighth_turn(self):
        t = {g: DATA["thin"][g]["from_turn_8"] for g in GROUPS}
        self.assertEqual([(t[g]["n"], t[g]["won"], t[g]["ron"], t[g]["tsumo"], t[g]["dealt"], t[g]["net"]) for g in GROUPS],
                         [(103, 30.1, 16.5, 13.6, 14.6, 1081), (349, 41.3, 24.4, 16.9, 16.9, 1824),
                          (686, 45.3, 25.9, 19.4, 13.1, 2602), (1993, 38.5, 21.9, 16.6, 15.7, 1586)])

    def test_thin_and_wide_riichis_over_every_turn(self):
        self.assertEqual([DATA["thin"][g]["all"]["n"] for g in GROUPS[:1]] + [DATA["thin"][g]["all"]["won"] for g in GROUPS[:3]], [164, 41.5, 44.9, 50.8])
        w = DATA["wide"]
        self.assertEqual((w["you"]["n"], w["you"]["won"], w["you"]["net"], w["luckyj"]["won"], w["luckyj"]["net"]), (175, 62.3, 3796, 59.5, 3860))


class TheChecksTests(unittest.TestCase):
    def test_the_tile_choices(self):
        c = DATA["choices"]
        self.assertEqual([c[g]["taken_live"] for g in GROUPS], [5.14, 5.02, 5.05, 4.91])
        self.assertEqual([c[g]["to_fewer_live_pct"] for g in GROUPS], [2.9, 2.6, 2.7, 2.8])
        self.assertEqual([c[g]["dama_decisions"] for g in GROUPS], [411, 1178, 1508, 6703])
        gave = c["gave_up_live_tiles_at_the_declaration"]
        self.assertEqual([(gave[g]["better_cut_existed"], gave[g]["declarations"]) for g in GROUPS], [(14, 198), (51, 672), (133, 1252), (339, 3802)])
        self.assertEqual([round(100 * gave[g]["better_cut_existed"] / gave[g]["declarations"], 1) for g in GROUPS], [7.1, 7.6, 10.6, 8.9])

    def test_where_the_copies_were(self):
        self.assertEqual([DATA["luck"][g]["held_pct"] for g in GROUPS], [49.6, 48.2, 46.9, 48.2])

    def test_furiten_riichis(self):
        f = DATA["furiten"]
        self.assertEqual([(f[g]["furiten"], f[g]["riichis"], f[g]["won"]) for g in GROUPS], [(4, 417, 0), (18, 1287, 3), (19, 2489, 6), (85, 7251, 29)])

    def test_the_labels_and_the_neighbors(self):
        e = DATA["model"]["extra"]
        self.assertEqual((e["labels"]["you"]["without"], e["labels"]["you"]["with"]), (40.4, 40.0))
        self.assertEqual([e["safe_looking_share_of_live_tiles"][g] for g in GROUPS], [14.7, 18.3, 18.4, 18.5])
        self.assertEqual((e["near"]["coefficient"], e["near"]["se"]), (0.012, 0.026))


class TheGapTests(unittest.TestCase):
    def test_the_model(self):
        m = DATA["model"]["thin from turn 8"]
        self.assertEqual((m["you"]["wins"], m["you"]["expected_wins"], m["you"]["sd"]), (31, 41.6, -2.2))
        self.assertEqual((m["luckyj"]["wins"], m["luckyj"]["expected_wins"], m["luckyj"]["sd"]), (311, 274.2, 2.9))
        self.assertTrue(all(abs(DATA["model"]["six or more live"][g]["sd"]) < 1.2 for g in GROUPS))

    def test_the_table_throws_your_waits_less(self):
        r = DATA["released"]
        self.assertEqual((r["you"]["releases"], r["expected_for_you_at_the_humans_rate"]), (17, 24.1))

    def test_opponents_tenpai(self):
        o = DATA["opponents_tenpai"]
        self.assertEqual([(o["humans_thin_win"][k]["n"], o["humans_thin_win"][k]["won"]) for k in ("0", "1", "2")], [(2300, 51.7), (978, 36.2), (278, 20.5)])
        self.assertEqual((o["none_tenpai_share"]["you"], o["none_tenpai_share"]["luckyj"]), (62.8, 68.8))

    def test_the_cost(self):
        c = DATA["cost"]
        self.assertEqual((c["net_per_riichi"], c["standard_error_of_yours"]), ({"you": 1081, "humans": 1621, "luckyj": 2602}, 595))
        self.assertEqual((c["points_a_game_against_humans"], c["rank_points_a_game_against_humans"]), (-258, -2.1))
        self.assertEqual((c["points_a_game_against_luckyj"], c["rank_points_a_game_against_luckyj"]), (-725, -6.0))
        self.assertEqual((c["rank_points_per_1000_points"], c["records_fitted"]), (8.3, 308))

    def test_the_two_examples(self):
        e = DATA["examples"]
        self.assertEqual((e["wait_held"]["round"], e["wait_held"]["turn"], e["wait_held"]["live"], e["wait_held"]["held"], e["wait_held"]["net"]), ("East 1-1", 13, 5, 4, -13300))
        self.assertEqual((e["wall_empty"]["round"], e["wall_empty"]["turn"], e["wall_empty"]["live"], e["wall_empty"]["in_the_wall"], e["wall_empty"]["net"]), ("South 4-0", 15, 3, 0, 2000))


class TheMinerTests(unittest.TestCase):
    def test_how_safe_a_wait_looks(self):
        import mine_thin_riichi as m

        river = [22, 28, 31]  # 2p 8p 1s
        self.assertEqual(m.wait_label(25, {}, river, Counter()), "nakasuji")  # 5p, with 2p and 8p thrown
        self.assertEqual(m.wait_label(28, {}, river, Counter()), "furiten")
        self.assertEqual(m.wait_label(26, {}, river, Counter()), "live 4-5-6")  # 6p, neither 3p nor 9p thrown
        self.assertEqual(m.wait_label(26, {}, river + [23], Counter()), "half suji")  # 6p, with 3p thrown
        self.assertEqual(m.wait_label(19, {}, river, Counter()), "live terminal")
        self.assertEqual(m.wait_label(45, {}, river, Counter({45: 2})), "honor, 2 seen")
        self.assertEqual(m.wait_label(46, {}, river, Counter()), "live honor")


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("11,444 riichis", "216 games", "1,255", "30.1%", "16.5%", "13.6%", "+1,081", "+1,824", "+2,602", "+1,586",
                       "164 thin riichis won 41.5%", "44.9%", "50.8%", "62.3% of 175", "+3,796", "59.5%", "+3,860", "5.14", "5.02", "5.05", "4.91",
                       "198, 672, 1,252 and 3,802 declarations", "411, 1,178, 1,508 and 6,703 decisions",
                       "49.6%", "4 of 417", "18 of 1,287", "19 of 2,489", "85 of 7,251", "14.7%", "18.3% to 18.5%", "40.4% to 40.0%", "0.01 per tile",
                       "41.6 wins", "You won 31, 2.2 standard deviations short", "274.2", "311", "2.9 standard deviations over", "17 times", "24.1",
                       "51.7% of 2,300", "36.2% of 978", "20.5% of 278 with two or more", "62.8%", "68.8%", "540 points a riichi", "258", "2.1 rank points",
                       "8.3 rank points per 1,000 points", "308 records", "725 points a game", "6.0 rank points", "595", "13,300", "+2,000",
                       "0 of 4", "6 of 19", "4 times in 10"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = ["replay.html?g=261008-ce956cd8-7f83-4165-97aa-e5be24fff49c&amp;r=East+1-1&amp;t=13",
                "replay.html?g=261003-d9683a26-30d8-4712-b52c-17797ebfe3e2&amp;r=South+4-0&amp;t=15"]
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


if __name__ == "__main__":
    unittest.main()
