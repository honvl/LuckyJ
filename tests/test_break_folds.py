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
    def test_a_safe_draw_thrown_back_never_breaks_the_hand(self):
        # 1-shanten before the draw; the drawn tile is safe and thrown back: the hand stays at 1-shanten
        self.assertEqual(miner.kind_of(1, 1, [1, 2]), "free")
        # the draw would reach tenpai, but only a live tile keeps it; the safe draw thrown back passes up the step
        self.assertEqual(miner.kind_of(1, 0, [1]), "step")
        # every safe tile leaves the hand further back than it stood before the draw
        self.assertEqual(miner.kind_of(1, 1, [2, 3]), "break")
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
        self.assertEqual([DATA["curves"][h]["spots"] for h in ("tenpai", "one", "far")], [1362, 2572, 1380])


class ProseFigureTests(unittest.TestCase):
    def test_the_first_table(self):
        order = [("LuckyJ", "one riichi"), ("You", "one riichi"), ("LuckyJ", "one caller"), ("You", "one caller"),
                 ("LuckyJ", "two or more callers"), ("You", "two or more callers")]
        want = [[f"{KINDS[who][threat][hand]['break']['pct']:.1f}%" for hand in ("tenpai", "one", "far")] for who, threat in order]
        self.assertEqual(want[0], ["13.9%", "48.5%", "75.9%"])
        self.assertEqual(want[2], ["1.1%", "4.5%", "4.2%"])
        for path in figure.PAGES.values():
            with self.subTest(page=path.name):
                cells = table_cells(chapter(path.read_text(encoding="utf-8")), 0)
                self.assertEqual([row[2:] for row in cells], want)

    def test_the_turn_counts_the_evidence_cites(self):
        one, two = KINDS["LuckyJ"]["one caller"], KINDS["LuckyJ"]["two or more callers"]
        self.assertEqual([(one[h]["break"]["spots"], two[h]["break"]["spots"]) for h in ("tenpai", "one", "far")],
                         [(975, 427), (1830, 771), (1085, 310)])
        self.assertEqual([KINDS["LuckyJ"]["one riichi"][h]["break"]["spots"] for h in ("tenpai", "one", "far")], [966, 1070, 432])
        free = lambda h: round(100 * one[h]["free"]["spots"] / sum(v["spots"] for v in one[h].values()))
        self.assertEqual((free("one"), free("far")), (67, 72))
        self.assertEqual(round(KINDS["You"]["one riichi"]["tenpai"]["break"]["spots"]), 107)

    def test_the_curves_the_prose_reads(self):
        at = lambda h, x: DATA["curves"][h]["at"][str(x)][0]
        self.assertEqual([round(at("one", x)) for x in (10, 50, 80)], [1, 7, 15])
        self.assertEqual([round(at("far", x)) for x in (20, 50)], [3, 22])
        self.assertTrue(all(abs(at("far", x) - 31) < 1.5 for x in range(70, DATA["curves"]["far"]["range"][1] + 1)))
        self.assertLess(max(g[1] for g in DATA["curves"]["tenpai"]["grid"]), 4)

    def test_passing_up_a_step(self):
        step = lambda threat, h: round(KINDS["LuckyJ"][threat][h]["step"]["pct"])
        self.assertEqual([step("one caller", "one"), step("one caller", "far"), step("one riichi", "one"), step("one riichi", "far")],
                         [10, 5, 31, 71])

    def test_the_value_table(self):
        hot = DATA["hot"]
        keys = ("all", "dora_pon", "dealer_caller", "my_dora_0", "my_dora_2plus")
        pct = lambda v: f"{int(v + 0.5)}%"
        want = [[pct(hot["one"][k]["pct"]), str(hot["one"][k]["spots"]), pct(hot["far"][k]["pct"]), str(hot["far"][k]["spots"])]
                for k in keys]
        self.assertEqual(want[0], ["12%", "889", "27%", "240"])
        for path in figure.PAGES.values():
            with self.subTest(page=path.name):
                cells = table_cells(chapter(path.read_text(encoding="utf-8")), 2)  # after the first table and the chart's own
                self.assertEqual([row[1:] for row in cells], want)

    def test_the_value_model(self):
        model = DATA["model"]["one"]
        odds = lambda k: math.exp(model[k]["beta"])
        self.assertEqual(round(odds("dora_pon")), 4)
        self.assertTrue(1.7 < odds("dealer_caller") < 2)
        self.assertTrue(0.7 < odds("my_dora") < 0.8)
        self.assertTrue(2.7 < odds("own_turn") < 3)
        self.assertEqual({k: (round(v["beta"], 2), round(v["se"], 2)) for k, v in model.items() if k in ("dora_pon", "dealer_caller", "my_dora", "own_turn")},
                         {"dora_pon": (1.4, 0.3), "dealer_caller": (0.61, 0.21), "my_dora": (-0.3, 0.11), "own_turn": (1.07, 0.35)})

    def test_your_games(self):
        yours = DATA["yours"]
        self.assertEqual([(yours[h]["broke"], round(yours[h]["expected"])) for h in ("one", "far")], [(20, 17), (15, 11)])
        self.assertEqual(yours["tenpai"]["broke"], 0)
        self.assertTrue(2 <= yours["tenpai"]["expected"] <= 3)
        low = yours["one"]["low_threat"]["safe"] + yours["far"]["low_threat"]["safe"]
        low_expected = yours["one"]["low_threat_expected"] + yours["far"]["low_threat_expected"]
        self.assertEqual((low, round(low_expected)), (12, 8))
        p = KINDS["LuckyJ"]["one riichi"]["tenpai"]["break"]["pct"] / 100
        mine = KINDS["You"]["one riichi"]["tenpai"]["break"]
        gap = (mine["pct"] / 100 - p) / math.sqrt(p * (1 - p) / mine["spots"])
        self.assertTrue(2.5 < gap < 3)

    def test_mortal_and_the_price(self):
        mortal = DATA["mortal"]
        under = [mortal[f"{h} under 40"]["safe_weight"] for h in ("tenpai", "one", "far")]
        self.assertTrue(1 <= min(under) and max(under) <= 4)
        self.assertEqual((round(mortal["one 40+"]["safe_weight"]), round(mortal["far 40+"]["safe_weight"])), (9, 16))
        self.assertEqual(sum(v["spots"] for v in mortal.values()), 625)
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
