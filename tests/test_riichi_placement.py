"""Chapter 25: the grid is the data, and every figure the prose cites holds."""

import json
import re
import sys
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_riichi_placement_figure as figure  # noqa: E402

DATA = json.loads(figure.DATA.read_text())


def half_up(v):
    return int(v + 0.5)


def chapter(name="honver.html"):
    page = (ROOT / "site" / name).read_text(encoding="utf-8")
    start = page.index('<section class="point" id="riichi-place">')
    text = page[start:page.index("</section>", start)]
    text = re.sub(r"<figure.*?</figure>", " ", text, flags=re.S)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text)))


def cell(cls, rank, stage, turn):
    return DATA["grid"][f"{cls}|{rank} {stage}"].get(str(turn))


def share(key):
    k, n = DATA["luckyj_by_place"][key]
    return 100 * k / n


class GridTests(unittest.TestCase):
    def test_both_editions_draw_the_data(self):
        for lang, path in figure.PAGES.items():
            page = path.read_text(encoding="utf-8")
            start, end = page.index(figure.START), page.index(figure.END) + len(figure.END)
            with self.subTest(lang=lang):
                self.assertEqual(page[start:end], figure.render(DATA, lang))

    def test_one_table_per_stage_with_a_switch(self):
        page = figure.render(DATA, "en")
        self.assertEqual(re.findall(r'data-stage="([^"]+)"', page), ["East", "South", "All-last"])
        self.assertEqual(len(re.findall(r'name="rp-stage"', page)), 3)
        css = (ROOT / "site" / "honver.css").read_text(encoding="utf-8")
        for stage in ("east", "south", "all-last"):
            self.assertIn(f"#rp-stage-{stage}:checked", css)


class ProseTests(unittest.TestCase):
    def test_luckyj_by_place_and_stage(self):
        self.assertEqual([half_up(share(f"{r} East")) for r in (1, 2, 3, 4)], [79, 81, 81, 83])
        self.assertEqual([half_up(share(f"{r} South")) for r in (1, 2, 3, 4)], [72, 71, 73, 87])
        self.assertEqual([half_up(share(f"{r} All-last")) for r in (1, 2, 3, 4)], [10, 47, 60, 87])
        text = chapter()
        for phrase in ("79 to 83%", "71 to 73%", "10% from 1st, 47% from 2nd, 60% from 3rd and 87% from 4th"):
            self.assertIn(phrase, text)

    def test_the_grid_squares_cited(self):
        self.assertEqual([half_up(cell("4", r, "East", 10)) for r in (1, 4)], [51, 62])
        self.assertEqual([half_up(cell("4", r, "South", 10)) for r in (1, 2, 3, 4)], [36, 34, 47, 72])
        self.assertEqual([half_up(cell("4", r, "All-last", 10)) for r in (1, 4)], [1, 71])
        self.assertEqual([half_up(cell("1-2", r, "All-last", 9)) for r in (1, 4)], [8, 94])

    def test_the_rule(self):
        for rank in (1, 2):
            self.assertGreater(cell("4", rank, "South", 7), 50)
            self.assertLess(cell("4", rank, "South", 8), 50)
            self.assertTrue(all(v < 50 for v in DATA["grid"][f"5+|{rank} South"].values()))
        self.assertGreater(cell("4", 4, "South", 13), 50)
        self.assertLess(cell("4", 4, "South", 14), 50)
        self.assertGreater(cell("5+", 4, "South", 8), 50)
        self.assertLess(cell("5+", 4, "South", 9), 50)
        self.assertLess(max(v for c in figure.CLASSES for v in DATA["grid"][f"{c}|1 All-last"].values()), 25)
        # all-last 4th plays like 4th from South 1
        a, b = DATA["places"]["4 All-last"], DATA["places"]["4 South"]
        self.assertLess(abs(a[0] - b[0]), a[1])

    def test_model_terms(self):
        self.assertEqual(DATA["luckyj_hands"], 2177)
        self.assertEqual(DATA["placement_by_value"], {"chi2": 10.99, "df": 11})
        self.assertEqual([round(x, 2) for x in DATA["lead"]["East"]], [-0.44, 0.16])
        self.assertEqual([round(x, 2) for x in DATA["lead"]["South"]], [0.17, 0.18])
        self.assertGreater(DATA["dealer"][0] / DATA["dealer"][1], 2)
        self.assertEqual(sum(DATA["luckyj_by_place"][f"{r} All-last"][1] for r in (1, 2, 3, 4)), 205)
        self.assertIn("All-last counts 205 of LuckyJ’s tenpais, 12 of them West hands", chapter())

    def test_your_games(self):
        you = DATA["you"]
        east = [you["by_place"][f"{r} East"] for r in (1, 2, 3, 4)]
        self.assertEqual(sum(c["declared"] for c in east), 130)
        self.assertEqual(sum(c["hands"] for c in east), 155)
        self.assertEqual(half_up(sum(c["luckyj_expects"] for c in east)), 130)
        first, fourth = you["outside_east"]["1"], you["outside_east"]["4"]
        self.assertEqual((first["declared"], first["hands"], half_up(first["luckyj_expects"])), (22, 31, 18))
        self.assertEqual((fourth["declared"], fourth["hands"], half_up(fourth["luckyj_expects"])), (22, 30, 25))
        for c in (first, fourth):
            self.assertAlmostEqual(abs(c["declared"] - c["luckyj_expects"]) / c["sd"], 2, delta=0.2)
        self.assertEqual(DATA["your_hands"], 287)
        spots = {(r["g"][:15], r["t"]): r for r in you["south_first_and_fourth"]}
        self.assertEqual(half_up(100 * spots[("260930-f5119e21", 11)]["luckyj"]), 31)
        self.assertEqual(half_up(100 * spots[("260921-6faea687", 6)]["luckyj"]), 96)
        self.assertEqual(half_up(100 * spots[("260919-bd7daa16", 10)]["luckyj"]), 96)

    def test_voice_rules(self):
        for name in ("honver.html", "honver-ja.html"):
            words = chapter(name)
            with self.subTest(page=name):
                self.assertNotRegex(words, r"[—–]")
                self.assertNotRegex(words, r"(?i)\bof course\b|もちろん|のである")
                if name == "honver-ja.html":
                    self.assertLessEqual(len(re.findall(r"ではなく", words)), 1)


if __name__ == "__main__":
    unittest.main()
