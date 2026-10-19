"""Chapter 45 of the personal guide: why the rank points fall.

Every figure the chapter cites comes from ``analysis/rank-drain-2026-10-19.json`` (``scripts/mine_rank_drain.py``).
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
DATA = json.loads((ROOT / "analysis" / "rank-drain-2026-10-19.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
GROUPS = ("you", "jade_human", "luckyj", "tokujou_human")


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="rank-drain">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class ThePaceTests(unittest.TestCase):
    def test_the_counts(self):
        self.assertEqual((DATA["games"], DATA["periods"]), (216, {"before": 87, "climb": 62, "since": 67}))
        self.assertEqual(DATA["formula_checked_against_the_records"], 216)

    def test_places_and_rank_points(self):
        p = DATA["pace"]
        self.assertEqual([(p[k]["games"], p[k]["places"], p[k]["mean_score"], p[k]["rank_points"]) for k in ("before", "climb", "since", "you")],
                         [(87, [20, 25, 22, 20], 24528, -13.9), (62, [20, 18, 20, 4], 29694, 44.8), (67, [17, 14, 16, 20], 25864, -31.7),
                          (216, [57, 57, 58, 44], 26425, -2.6)])
        self.assertEqual([(p[k]["games"], p[k]["places"], p[k]["mean_score"], p[k]["rank_points"]) for k in ("jade_human", "luckyj", "tokujou_human")],
                         [(648, [159, 159, 158, 172], 24525, -23.6), (1079, [342, 297, 258, 182], 28787, 16.2),
                          (3237, [737, 782, 821, 897], 23726, -29.8)])

    def test_the_spread(self):
        s = DATA["spread"]
        self.assertEqual((s["sd_a_game"], s["stretch_se"]["since"], s["climb_vs_2026"], s["since_vs_2026"], s["since_vs_humans"]), (147.6, 18.0, 2.5, -1.6, -0.4))
        self.assertEqual((s["career_games"], s["career_fourth_pct"]), (4458, 21.4))
        f = s["fourths"]
        self.assertEqual((f["since"]["fourths"], f["since"]["expected"], f["since"]["sd"]), (20, 14.4, 1.7))
        self.assertEqual((f["climb"]["fourths"], f["climb"]["games"], f["climb"]["sd"]), (4, 62, -2.9))


class TheEdgeTests(unittest.TestCase):
    def test_where_the_points_come_from(self):
        e = DATA["edges"]
        self.assertEqual([(e["you"][k]["points"], e["luckyj"][k]["points"]) for k in ("win", "deal_ins", "tsumo_paid", "other", "net")],
                         [(103, 2448), (1798, 2440), (-163, 311), (165, -138), (1903, 5061)])
        self.assertEqual([(e["you"][k]["se"], e["luckyj"][k]["se"]) for k in ("win", "deal_ins", "net")], [(902, 419), (541, 251), (1186, 531)])
        g = DATA["gap_to_luckyj"]
        self.assertEqual([(g[k]["points"], g[k]["rank_points"]) for k in ("win", "deal_ins", "tsumo_paid", "other", "net")],
                         [(2345, 19.5), (642, 5.3), (474, 3.9), (-303, -2.5), (3158, 26.2)])
        self.assertEqual(sum(g[k]["points"] for k in ("win", "deal_ins", "tsumo_paid", "other")), g["net"]["points"])
        self.assertEqual((e["you"]["net"]["rank_points"], DATA["rank_points_per_1000_points"]), (15.8, 8.3))
        self.assertEqual(round(DATA["pace"]["you"]["rank_points"] - DATA["pace"]["jade_human"]["rank_points"], 1), 21.0)

    def test_the_wins(self):
        w = DATA["wins"]
        self.assertEqual([(w[k]["wins_per_100"], w[k]["average"]) for k in GROUPS[:3]], [(22.6, 6395), (21.1, 6789), (22.9, 7317)])
        self.assertEqual([(w[k]["riichi"]["average"], w[k]["dama"]["average"], w[k]["open"]["average"]) for k in GROUPS[:3]],
                         [(8680, 5934, 4629), (8994, 5575, 4962), (9227, 7676, 5477)])
        self.assertEqual([(w[k]["open_hands"]["share_of_hands"], w[k]["open_hands"]["four_han_or_more_pct"], w[k]["open_hands"]["net_a_hand"]) for k in GROUPS[:3]],
                         [(35.4, 18, 338), (31.3, 23, 255), (36.0, 27, 578)])
        g = w["gap_to_luckyj"]
        self.assertEqual((g["average_win"]["points"], g["average_win"]["se"]), (-922, 207))
        self.assertEqual([(g["average_win_by_kind"][k]["points"], g["average_win_by_kind"][k]["se"]) for k in ("riichi", "dama", "open")],
                         [(-547, 323), (-1742, 567), (-848, 242)])
        self.assertEqual((g["wins_a_game"], g["rank_points_per_100_on_the_average_win"], g["rank_points_for_the_whole_gap"]), (2.35, 1.9, 18.0))


class TheBigDealInTests(unittest.TestCase):
    def test_the_rate_by_stretch(self):
        b = DATA["big_deal_ins"]
        self.assertEqual([(b[k]["big"], b[k]["per_100"]) for k in ("before", "climb", "since")], [(25, 2.75), (17, 2.66), (34, 4.86)])
        self.assertEqual([b[k]["per_100"] for k in ("jade_human", "luckyj", "tokujou_human")], [4.69, 3.41, 4.94])
        self.assertEqual(b["shift"], {"before_the_peak_per_100": 2.71, "since_per_100": 4.86, "z": 2.6, "expected_since_at_the_early_rate": 19.0,
                                      "points_a_game": 2086, "rank_points_a_game": 17.3})

    def test_the_tables_did_not_change_much(self):
        t = DATA["tables"]
        self.assertEqual([t[k]["big_wins_per_100"] for k in ("before", "climb", "since")], [9.01, 8.76, 10.11])
        self.assertEqual([t[k]["riichi_per_100"] for k in ("before", "climb", "since")], [19.9, 18.4, 18.7])

    def test_what_mortal_thought_of_them(self):
        c = DATA["cases"]
        self.assertEqual((c["since"], c["mortal_under_25"], c["mortal_under_25_points"]), (34, 8, 92800))
        self.assertEqual([(c["by_period"][k]["big"], c["by_period"][k]["flagged"], c["by_period"][k]["other"]) for k in ("before", "climb", "since")],
                         [(25, 3, 22), (17, 4, 13), (34, 8, 26)])
        self.assertEqual([c["by_period"][k]["flagged_per_100"] for k in ("before", "climb", "since")], [0.33, 0.63, 1.14])
        self.assertEqual([c["by_period"][k]["other_per_100"] for k in ("before", "climb", "since")], [2.42, 2.03, 3.72])
        self.assertEqual((c["excess_since"]["flagged"], c["excess_since"]["other"]), (4.8, 10.2))
        o = c["own_riichi_into_open"]
        self.assertEqual((o["count"], o["declared_at_99_percent"], o["winner_not_yet_open"], o["per_100_hands"], o["humans_per_100"], o["luckyj_per_100"]),
                         (7, 5, 3, 1.0, 0.28, 0.38))

    def test_the_six_cuts(self):
        cuts = [c for c in DATA["cases"]["low_cases"] if c["kind"] == "cut"]
        self.assertEqual(sum(c["paid"] for c in cuts), 68200)
        self.assertEqual(sum(c["paid"] for c in DATA["cases"]["low_cases"] if c["kind"] == "riichi"), 24600)
        want = [("261004-3d4685b3", "South 1-1", 8, "9m", 12300), ("261017-c062d7a5", "South 3-1", 15, "6m", 12300), ("261007-c265c423", "South 4-0", 12, "P", 12000),
                ("261011-10d214ef", "East 3-0", 11, "8p", 12000), ("261008-6c28a9cb", "South 2-0", 15, "7s", 11600), ("261018-65bbd1fc", "South 2-1", 11, "6s", 8000)]
        got = sorted([(c["game"][:15], c["round"], c["turn"], c["tile"], c["paid"]) for c in cuts], key=lambda x: -x[4])
        self.assertEqual(sorted(got), sorted(want))
        self.assertEqual([round(100 * c["mortal"]) for c in sorted(cuts, key=lambda c: (-c["paid"], c["game"]))], [5, 0, 12, 1, 0, 0])


class TheTiltTests(unittest.TestCase):
    def test_no_tilt(self):
        t = DATA["tilt"]
        self.assertEqual((t["after_a_fourth"]["games"], t["after_a_fourth"]["fourths"], t["after_a_fourth"]["fourth_pct"]), (18, 5, 27.8))
        self.assertEqual((t["after_a_first_to_third"]["games"], t["after_a_first_to_third"]["fourths"], t["after_a_first_to_third"]["fourth_pct"]), (139, 26, 18.7))
        self.assertEqual([t["by_place_in_session"][str(k)]["fourth_pct"] for k in range(1, 6)], [22.0, 20.0, 17.1, 25.9, 18.0])
        self.assertEqual([t["mortal_agreement"][k]["matched_pct"] for k in ("before", "climb", "since")], [73.2, 73.4, 73.0])
        self.assertEqual([t["mortal_agreement"][k]["discards"] for k in ("before", "climb", "since")], [10579, 7306, 8093])

    def test_the_last_hand(self):
        l = DATA["last_hand"]
        self.assertEqual([(l[k]["third"]["n"], l[k]["third"]["fell"]) for k in GROUPS], [(55, 8), (161, 19), (255, 19), (824, 95)])
        self.assertEqual([(l[k]["fourth_escaped_by_gap_to_third"]["0-3k"]["n"], l[k]["fourth_escaped_by_gap_to_third"]["0-3k"]["escaped"]) for k in GROUPS[:3]],
                         [(12, 10), (34, 9), (40, 18)])


class TheMinerTests(unittest.TestCase):
    def test_rank_points_and_places(self):
        import mine_rank_drain as m

        self.assertEqual(m.rank_points(39000, 1), 139)  # 9 for the score, 130 for first
        self.assertEqual(m.rank_points(12300, 4), -267)  # -17.7 - 250 = -267.7, rounded up
        self.assertEqual(m.places_of([25000, 25000, 25000, 25000]), [1, 2, 3, 4])  # ties go to the earlier seat
        self.assertEqual(m.places_of([9400, 27000, 39000, 24600]), [4, 2, 1, 3])

    def test_the_turn_of_a_discard_counts_calls_and_skips_replacement_draws(self):
        import mine_rank_drain as m

        hand = {"ev": [["t", 0, "1m"], ["d", 0, "9p", 0], ["p", 0, 1, "5s", ["5s", "5s"]], ["d", 0, "2m", 0], ["t", 0, "3m", 1], ["d", 0, "4m", 0], ["t", 0, "6m"], ["d", 0, "7m", 0]]}
        tm = m.turn_map(hand, 0)
        self.assertEqual([tm[i] for i in range(8)], [1, 1, 2, 2, 2, 2, 3, 3])


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("216 games", "23.6 rank points a game", "lose 23.6 a game", "29.8", "lost 2.6", "147.6", "moves 18.0", "+44.8", "2.5 of those steps",
                       "1.6 below", "0.4 below", "20 of the 67 games", "21.4% over 4,458 games", "gives 14.4", "1.7 standard deviations over", "2.9 under",
                       "25,864", "1,339 points above", "24,525", "8 below", "73.2%", "73.4%", "73.0%", "5 times in 18 (27.8%)", "26 in 139 after anything else (18.7%)",
                       "22.0, 20.0, 17.1, 25.9 and 18.0%", "8 times in 55 (14.5%)", "19 in 161 (11.8%)", "19 in 255 (7.5%)", "10 times in 12", "9 in 34", "18 in 40",
                       "4.7 times per 100 hands", "149 games", "last 67", "2.6 standard deviations", "34 hits", "19.0", "15 extra hits", "2,086 points a game",
                       "17.3 rank points", "14.4 and not", "8 of the 34 hits", "92,800 points", "1,385 a game", "11.5 rank points", "7 of 42", "4.8 of the 15", "10.2",
                       "1.0 per 100 hands", "0.28", "0.38", "5 of the 7", "99% or more", "in 3 the winner", "1,903 points a game", "error of 1,186", "15.8 rank points",
                       "21.0", "5,061", "error of 531", "3,158 above you", "+1,798", "+2,440", "3.3 times", "541", "+103", "+2,448", "902 and 419", "2,345 of the 3,158",
                       "19.5 of the 26.2", "922 less", "error of 207", "5,477 against 4,629, error 242", "7,676 against 5,934, error 567", "547 in riichi (error 323)",
                       "35.4% against 36.0%", "18% of your open wins", "LuckyJ s have 27%", "2.35 wins a game", "about 2 rank points", "the whole 922 would be 18.0",
                       "68,200", "99.6%", "98.9%", "99.7%", "8,000", "tanyao, 3 dora and a red five", "14.9 rank points", "1,798 points a game"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = ["replay.html?g=261004-3d4685b3-96b5-421f-9f25-7f7459b95553&amp;r=South+1-1&amp;t=8",
                "replay.html?g=261017-c062d7a5-938e-4e8f-8061-ca646da43a03&amp;r=South+3-1&amp;t=15",
                "replay.html?g=261007-c265c423-64d7-4171-ae24-ea000701511e&amp;r=South+4-0&amp;t=12",
                "replay.html?g=261011-10d214ef-4cc3-414b-ab98-38e19ba751e2&amp;r=East+3-0&amp;t=11",
                "replay.html?g=261008-6c28a9cb-7fd0-48ff-a4f0-18b3bcf51dde&amp;r=South+2-0&amp;t=15",
                "replay.html?g=261018-65bbd1fc-5557-4dc2-a5ce-3baedec8a46b&amp;r=South+2-1&amp;t=11",
                "replay.html?g=261018-65bbd1fc-5557-4dc2-a5ce-3baedec8a46b&amp;r=East+3-0&amp;t=12"]
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

    def test_the_latest_notice_comes_first(self):
        for lang, label in (("en", "Chapter 45 looks for why your rank points fall"), ("ja", "第45章は、段位ポイントが減る理由を調べる")):
            page = PAGES[lang].read_text(encoding="utf-8")
            first = page.index('<li class="is-latest">')
            self.assertEqual(page.index(label) > first, True)
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            self.assertLess(first, page.index(label))
            self.assertIn('<a href="#rank-drain">', page[first:first + 400])


if __name__ == "__main__":
    unittest.main()
