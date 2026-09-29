"""Chapter 20: when LuckyJ breaks its hand to fold. The page shows the data, and the figures the prose cites hold."""

import json
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_break_fold_figure as figure  # noqa: E402
import mine_break_folds as miner  # noqa: E402

DATA = json.loads(figure.DATA.read_text())
KINDS = DATA["kinds"]


def chapter(page: str) -> str:
    text = page[page.index('<section class="point" id="break-folds">'):]
    return text[: text.index("</section>")]


def table_cells(html: str, index: int) -> list[list[str]]:
    body = re.findall(r"<tbody>(.*?)</tbody>", html, flags=re.S)[index]
    return [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row)] for row in re.findall(r"<tr>(.*?)</tr>", body)]


class KindTests(unittest.TestCase):
    def test_the_mark_is_the_best_hand_the_draw_allows(self):
        # 1-shanten before the draw, nothing better on offer; a safe draw thrown back keeps it: free
        self.assertEqual(miner.kind_of(1, 1, [1, 2]), "free")
        # the draw reaches tenpai with a live tile only; the safe tile passes up the step: a break
        self.assertEqual(miner.kind_of(1, 0, [1]), "step")
        self.assertTrue(miner.costly({"kind": "step"}))
        # every safe tile goes back from where the hand stood: a break too
        self.assertEqual(miner.kind_of(1, 1, [2, 3]), "back")
        self.assertTrue(miner.costly({"kind": "back"}))
        # a safe draw that improves the hand reaches the best hand: free
        self.assertEqual(miner.kind_of(1, 0, [0, 1]), "free")
        self.assertEqual(miner.kind_of(0, 0, []), "none")


class FigureTests(unittest.TestCase):
    def test_the_pages_draw_the_data(self):
        for lang, path in figure.PAGES.items():
            with self.subTest(page=path.name):
                page = path.read_text(encoding="utf-8")
                start, end = page.index(figure.START), page.index(figure.END) + len(figure.END)
                self.assertEqual(page[start:end], figure.render(DATA, lang))
                self.assertIn(figure.START, chapter(page))

    def test_one_dot_per_whole_percent_and_a_fitted_curve_per_hand(self):
        for hand, curve in DATA["curves"].items():
            with self.subTest(hand=hand):
                xs = [p[0] for p in curve["points"]]
                self.assertEqual(xs, sorted(set(xs)))
                self.assertEqual(sum(p[2] for p in curve["points"]), curve["spots"])
                self.assertEqual(sum(p[1] for p in curve["points"]), curve["broke"])
                lo, hi = curve["range"]
                self.assertEqual((curve["grid"][0][0], curve["grid"][-1][0]), (lo, hi))
        self.assertEqual([DATA["curves"][h]["spots"] for h in ("tenpai", "one", "far")], [1797, 3457, 2057])


class ProseFigureTests(unittest.TestCase):
    def test_the_first_table(self):
        order = [("LuckyJ", "one riichi"), ("You", "one riichi"), ("LuckyJ", "one caller"), ("You", "one caller"),
                 ("LuckyJ", "two or more callers"), ("You", "two or more callers")]
        want = [[f"{KINDS[who][threat][hand]['costly']['pct']:.1f}%" for hand in ("tenpai", "one", "far")] for who, threat in order]
        self.assertEqual(want[0], ["18.3%", "53.4%", "79.5%"])
        self.assertEqual(want[2], ["3.3%", "4.9%", "4.1%"])
        for path in figure.PAGES.values():
            with self.subTest(page=path.name):
                cells = table_cells(chapter(path.read_text(encoding="utf-8")), 0)
                self.assertEqual([row[2:] for row in cells], want)

    def test_the_turn_counts_the_evidence_cites(self):
        one, two = KINDS["LuckyJ"]["one caller"], KINDS["LuckyJ"]["two or more callers"]
        self.assertEqual([(one[h]["costly"]["spots"], two[h]["costly"]["spots"]) for h in ("tenpai", "one", "far")],
                         [(1300, 544), (2545, 956), (1643, 444)])
        self.assertEqual([KINDS["LuckyJ"]["one riichi"][h]["costly"]["spots"] for h in ("tenpai", "one", "far")], [1310, 1583, 672])
        for table in (one, two):
            for h in ("tenpai", "one", "far"):
                self.assertEqual(table[h]["costly"]["spots"], table[h]["back"]["spots"] + table[h]["step"]["spots"])
        free = lambda h: round(100 * one[h]["free"]["spots"] / sum(one[h][k]["spots"] for k in ("free", "costly", "none")))
        self.assertEqual((free("one"), free("far")), (66, 75))
        self.assertEqual(KINDS["You"]["one riichi"]["tenpai"]["costly"]["spots"], 148)

    def test_the_curves_the_prose_reads(self):
        at = lambda h, x: DATA["curves"][h]["at"][str(x)][0]
        self.assertEqual([round(at("one", x)) for x in (10, 50, 80)], [1, 9, 16])
        self.assertEqual([round(at("far", x)) for x in (20, 50, 80)], [4, 23, 34])
        self.assertLess(max(g[1] for g in DATA["curves"]["tenpai"]["grid"]), 6)
        self.assertEqual(round(at("one", 35)), 5)

    def test_the_two_forms(self):
        form = lambda threat, kind: round(KINDS["LuckyJ"][threat]["tenpai"][kind]["pct"])
        self.assertEqual([form("one caller", "step"), form("one caller", "back"), form("one riichi", "step"), form("one riichi", "back")],
                         [10, 1, 31, 14])

    def test_the_value_table(self):
        hot = DATA["hot"]
        keys = ("all", "dora_pon", "dealer_caller", "my_dora_0", "my_dora_2plus")
        pct = lambda v: f"{int(v + 0.5)}%"
        want = [[pct(hot["one"][k]["pct"]), f'{hot["one"][k]["spots"]:,}', pct(hot["far"][k]["pct"]), f'{hot["far"][k]["spots"]:,}']
                for k in keys]
        self.assertEqual(want[0], ["14%", "1,082", "30%", "336"])
        for path in figure.PAGES.values():
            with self.subTest(page=path.name):
                cells = table_cells(chapter(path.read_text(encoding="utf-8")), 2)  # after the first table and the chart's own
                self.assertEqual([row[1:] for row in cells], want)

    def test_the_value_model(self):
        model = DATA["model"]["one"]
        odds = lambda k: math.exp(model[k]["beta"])
        self.assertEqual(round(odds("dora_pon"), 1), 3.6)
        self.assertTrue(1.55 < odds("dealer_caller") < 1.7)
        self.assertTrue(0.7 < odds("my_dora") < 0.8)
        self.assertEqual(round(odds("own_turn")), 5)
        self.assertEqual({k: (round(v["beta"], 2), round(v["se"], 2)) for k, v in model.items() if k in ("dora_pon", "dealer_caller", "my_dora", "own_turn")},
                         {"dora_pon": (1.28, 0.26), "dealer_caller": (0.49, 0.17), "my_dora": (-0.26, 0.09), "own_turn": (1.61, 0.29)})

    def test_your_games(self):
        yours = DATA["yours"]
        self.assertEqual([(yours[h]["broke"], round(yours[h]["expected"])) for h in ("one", "far", "tenpai")], [(33, 26), (23, 17), (4, 7)])
        low = yours["one"]["low_threat"]["safe"] + yours["far"]["low_threat"]["safe"]
        low_expected = yours["one"]["low_threat_expected"] + yours["far"]["low_threat_expected"]
        self.assertEqual((low, round(low_expected)), (24, 12))
        p = KINDS["LuckyJ"]["one riichi"]["tenpai"]["costly"]["pct"] / 100
        mine = KINDS["You"]["one riichi"]["tenpai"]["costly"]
        gap = (mine["pct"] / 100 - p) / math.sqrt(p * (1 - p) / mine["spots"])
        self.assertTrue(2.8 < gap < 3.3)

    def test_mortal_and_the_price(self):
        mortal = DATA["mortal"]
        under = [mortal[f"{h} under 40"]["safe_weight"] for h in ("tenpai", "one", "far")]
        self.assertTrue(2 <= min(under) and max(under) <= 4)
        self.assertEqual((round(mortal["one 40+"]["safe_weight"]), round(mortal["far 40+"]["safe_weight"])), (10, 15))
        self.assertEqual(sum(v["spots"] for v in mortal.values()), 864)
        self.assertEqual((DATA["ron_paid"]["open"]["average"], DATA["ron_paid"]["riichi"]["average"]), (4525, 6683))

    def test_the_example_squares(self):
        # the three turns' squares: one caller at 35% and 78%; two callers at 32% and 41%, either of them 60%
        data = json.loads(miner.grid.DATA.read_text())
        square = lambda calls, run, d: miner.square(calls, run, d, data)
        self.assertEqual(round(square(1, 0, 13)), 35)
        self.assertEqual(round(square(3, 1, 8)), 78)
        self.assertEqual(round(100 * (1 - (1 - square(1, 0, 11) / 100) * (1 - square(1, 3, 10) / 100))), 60)


if __name__ == "__main__":
    unittest.main()
