"""Chapters 18 and 19's caller grid: the page shows the data, and the figures the prose cites hold."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_caller_surface as build  # noqa: E402
import mine_caller_surface as surface  # noqa: E402

DATA = json.loads(build.DATA.read_text())
FOLD = json.loads(build.FOLD.read_text())
PATTERNS = json.loads((ROOT / "analysis" / "caller-patterns-2026-09-29.json").read_text())
YOURS = json.loads((ROOT / "analysis" / "caller-patterns-honver-2026-09-29.json").read_text())


def square(calls, run, discard, key="can_win"):
    return round(build.value(DATA["grid"][key][f"{calls}-{run}"]["cells"][str(discard)], DATA["min_readings"]))


class CallerGridTests(unittest.TestCase):
    def test_the_page_draws_the_data(self):
        for lang, path in build.PAGES.items():
            with self.subTest(page=path.name):
                page = path.read_text(encoding="utf-8")
                start, end = page.index(build.START), page.index(build.END) + len(build.END)
                self.assertEqual(page[start:end], build.render(DATA, FOLD, lang))

    def test_the_landmarks_the_prose_cites(self):
        self.assertLessEqual(max(square(1, r, d) for r in (0, 1, 2, 3) for d in range(1, 7)
                                 if build.value(DATA["grid"]["can_win"][f"1-{r}"]["cells"][str(d)], DATA["min_readings"]) is not None), 12)
        self.assertEqual(square(1, 0, 12), 34)
        self.assertEqual(square(1, 3, 12), 55)
        self.assertGreaterEqual(square(2, 0, 10), 50)
        self.assertLess(square(2, 0, 9), 50)
        self.assertGreaterEqual(min(square(2, 2, 9), square(2, 3, 9)), 50)
        self.assertEqual(square(3, 0, 5), 57)
        self.assertEqual(square(1, 0, 18, "tenpai"), 46)
        self.assertEqual(square(1, 0, 18), 28)
        self.assertEqual(DATA["readings"], 88588)

    def test_the_fold_line(self):
        # real choices only: a safe tile keeps the shanten and so does a live tile with at least as much acceptance
        self.assertEqual(build.fold_lines(FOLD), {1: 12, 2: 9, 3: 9})
        one, more = FOLD["shanten"]["far"]["blocks"]["1"], FOLD["shanten"]["far"]["blocks"]["2+"]
        fit = lambda block, d: round(block["cells"][str(d)]["fit"])
        self.assertEqual((one["spots"], more["spots"]), (4500, 1591))
        self.assertEqual((min(fit(one, d) for d in range(1, 7)), max(fit(one, d) for d in range(1, 7))), (80, 94))
        self.assertEqual([fit(one, d) for d in (9, 11, 12)], [66, 53, 47])
        self.assertEqual([fit(more, d) for d in (6, 8, 9)], [67, 53, 48])
        # chapters 13 and 14's tenth and seventh discards are the ties' line
        ties = FOLD["shanten"]["far"]["ties"]
        self.assertEqual((ties["1"]["line"], ties["2+"]["line"], ties["1"]["spots"] + ties["2+"]["spots"]), (10, 7, 2798))
        kinds = FOLD["kinds"]["far"]
        self.assertEqual((kinds["safe tile is the best tile"]["spots"], kinds["only safe tiles keep shanten"]["spots"]), (4454, 88))
        # the run does not move the line against one call, and does against two or more
        far = FOLD["run_slope"]["far"]
        self.assertLess(abs(far["1"]["slope"]), 2 * far["1"]["se"])
        self.assertLess(far["2+"]["slope"], -2 * far["2+"]["se"])
        self.assertEqual({b: (round(v["slope"], 2), round(v["se"], 2)) for b, v in far.items()}, {"1": (-0.02, 0.05), "2+": (-0.15, 0.06)})
        # about 4 points of folding a tile from the wall, near half: 0.25 of the log-odds slope
        self.assertEqual(round(-25 * far["2+"]["slope"]), 4)
        self.assertEqual(FOLD["shanten"]["tenpai"]["folded"]["spots"], 248)

    def test_the_fold_views(self):
        # from one-shanten LuckyJ folds later than from a far hand, and at tenpai there are too few real choices
        self.assertEqual(build.fold_lines(FOLD, "one"), {1: 14, 2: 12, 3: 12})
        hands = FOLD["shanten"]
        self.assertEqual([(hands[h]["folded"]["spots"], hands[h]["costly"]["spots"]) for h in ("far", "one", "tenpai")],
                         [(6091, 1682), (4310, 2663), (248, 1521)])
        self.assertEqual([hands[h]["costly"]["folded"] for h in ("far", "one", "tenpai")], [4.0, 4.8, 3.5])
        self.assertEqual(round(hands["tenpai"]["folded"]["folded"]), 55)
        self.assertNotIn("tenpai", build.HANDS)
        square = lambda hand, row, d: build.fold_value(hands[hand]["grid"][row]["cells"][str(d)], FOLD["grid_max_half_band"])
        for d in range(9, 14):
            self.assertLess(square("one", "1-0", d), square("far", "1-0", d))
        # the one-shanten view starts higher because its early ties go to the safe tile more often
        folded_ties = lambda hand, d: 100 - hands[hand]["ties"]["1"]["cells"][str(d)]["fit"]
        for d in range(4, 9):
            self.assertLess(folded_ties("far", d), folded_ties("one", d))
        # a square is drawn only where its band is tight
        for hand in build.HANDS:
            for row in hands[hand]["grid"].values():
                for cell in row["cells"].values():
                    if build.fold_value(cell, FOLD["grid_max_half_band"]) is not None:
                        self.assertLessEqual(cell["hi"] - cell["lo"], 2 * FOLD["grid_max_half_band"])
        self.assertEqual(build.blank_blocks(FOLD, "far"), [3])
        self.assertEqual(build.blank_blocks(FOLD, "one"), [3])

    def test_the_switches_show_one_view_at_a_time(self):
        views = ["win"] + [f"fold-{h}" for h in build.HANDS]
        for path in build.PAGES.values():
            with self.subTest(page=path.name):
                page = path.read_text(encoding="utf-8")
                figure = page[page.index(build.START):page.index(build.END)]
                self.assertEqual(re.findall(r'<table class="cs-grid" data-view="([^"]+)"', figure), views)
                self.assertEqual(re.findall(r'<span data-view="([^"]+)"', figure), views)
                self.assertEqual(re.findall(r'<input class="cs-switch-input" type="radio" name="[^"]+" id="([^"]+)"', figure),
                                 ["cs-view-win", "cs-view-fold"] + [f"cs-hand-{h}" for h in build.HANDS])
                self.assertEqual(re.findall(r'<label for="([^"]+)"', figure),
                                 ["cs-view-win", "cs-view-fold"] + [f"cs-hand-{h}" for h in build.HANDS])
        css = re.sub(r"\s+", " ", (ROOT / "site" / "honver.css").read_text(encoding="utf-8"))
        hides = ['#cs-view-win:checked ~ .cs-hands', '#cs-view-win:checked ~ * [data-view^="fold"]', '#cs-view-fold:checked ~ * [data-view="win"]']
        hides += [f'#cs-hand-{h}:checked ~ * [data-view="fold-{o}"]' for h in build.HANDS for o in build.HANDS if o != h]
        for selector in hides:
            self.assertIn(selector, css)

    def test_chapter_19_tables_show_the_patterns(self):
        for path in build.PAGES.values():
            with self.subTest(page=path.name):
                self.check_chapter_19_tables(path.read_text(encoding="utf-8"))

    def check_chapter_19_tables(self, page):
        chapter = page[page.index('<section class="point" id="fold-line">'):]
        chapter = chapter[: chapter.index("</section>")]
        tables = re.findall(r"<tbody>(.*?)</tbody>", chapter, flags=re.S)  # the worked river comes first; the two pattern tables close the chapter
        cells = [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row)] for row in re.findall(r"<tr>(.*?)</tr>", tables[-2])]
        pct = lambda v: f"{round(v)}%"
        before = ["call", "hand_after_three", "hand_after_two", "hand_after_one", "hand_after_hand"]
        self.assertEqual([c[1:] for c in cells], [[pct(PATTERNS["patterns"][k]["rows"]["could_win"])] + [pct(v) for v in PATTERNS["patterns"][k]["rows"]["by_run"][:2]] for k in before])
        self.assertEqual([PATTERNS["patterns"][k]["rows"]["n"] for k in before], [14033, 1722, 2120, 4793, 11874])
        cells = [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row)] for row in re.findall(r"<tr>(.*?)</tr>", tables[-1])]
        kinds = ["one_value_honor", "one_guest_wind", "one_terminal", "one_two_or_eight", "one_middle", "two_honors_terminals",
                 "two_with_number", "three_honors_terminals", "three_with_number"]
        self.assertEqual([c[1:] for c in cells], [[pct(PATTERNS["patterns"][k]["own"]["could_win"]), pct(PATTERNS["patterns"][k]["own"]["square"])] for k in kinds])

    def test_the_patterns_the_prose_cites(self):
        own = lambda k: (round(PATTERNS["patterns"][k]["own"]["could_win"]), round(PATTERNS["patterns"][k]["own"]["square"]))
        self.assertEqual(own("alternating_wall"), (35, 36))
        self.assertEqual(own("alternating_hand"), (29, 31))
        # three or more honors and terminals read like the second row, a single tile from the wall
        self.assertEqual(round(PATTERNS["patterns"]["three_honors_terminals"]["rows"]["could_win"]), 40)
        self.assertEqual(round(PATTERNS["patterns"]["three_honors_terminals"]["rows"]["by_run"][1]), 41)
        self.assertEqual(round(PATTERNS["three_or_more_all_honors_terminals"]), 5)
        counts = PATTERNS["counts"]
        self.assertEqual(round(counts["grid"]["log_likelihood"] - counts["skip_guests_terminals"]["log_likelihood"]), 25)
        self.assertGreater(counts["call_as_wall"]["log_likelihood"], counts["grid"]["log_likelihood"])
        self.assertEqual(PATTERNS["readings"], 88588)
        rows = lambda k: YOURS["patterns"][k]["rows"]
        self.assertEqual(YOURS["readings"], 6472)
        self.assertEqual((round(rows("call")["could_win"]), round(rows("call")["by_run"][0])), (35, 29))
        self.assertEqual((round(rows("hand_after_three")["could_win"]), round(rows("hand_after_three")["by_run"][0])), (42, 38))

    def test_chapter_14_rule_uses_the_corrected_line(self):
        # real choices fold from the 12th and 9th (two-shanten or worse) and the 14th and 12th (one-shanten);
        # the 10th and 7th are the line only when the safe tile leaves the same hand
        self.assertEqual(build.fold_lines(FOLD, "far"), {1: 12, 2: 9, 3: 9})
        self.assertEqual(build.fold_lines(FOLD, "one"), {1: 14, 2: 12, 3: 12})
        ties = FOLD["shanten"]["far"]["ties"]
        self.assertEqual((ties["1"]["line"], ties["2+"]["line"]), (10, 7))
        want = {"honver.html": ["(their 12th discard)", "(their 9th)", "(14th)", "(12th)", "(10th)", "(7th)"],
                "honver-ja.html": ["（12打目）", "（9打目）", "（14打目）", "（12打目）", "（10打目）", "（7打目）"]}
        for path in build.PAGES.values():
            with self.subTest(page=path.name):
                page = path.read_text(encoding="utf-8")
                chapter = page[page.index('<section class="point" id="three-calls">'):]
                rule = chapter[chapter.index('<mark id="fix-14-rule"'):]
                rule = rule[: rule.index("</mark>")]
                at = -1
                for word in want[path.name]:  # each figure in order, the next found after the last
                    at = rule.index(word, at + 1)

    def test_buckets_and_colours(self):
        self.assertEqual([surface.run_bucket(r) for r in (0, 1, 2, 3, 7)], [0, 1, 2, 3, 3])
        self.assertEqual([surface.calls_bucket(c) for c in (1, 2, 3, 4)], [1, 2, 3, 3])
        self.assertEqual(build.shade(0), "#f4f0e6")
        self.assertEqual(build.shade(50), "#f5a583")
        self.assertEqual(build.shade(100), "#8e2a15")
        # the fold views shade in jade, so a folded square never reads as a caller's tenpai
        self.assertEqual([build.shade(p, "fold") for p in (0, 50, 100)], ["#f4f0e6", "#8edbb8", "#0c2f22"])
        for path in build.PAGES.values():
            page = path.read_text(encoding="utf-8")
            figure = page[page.index(build.START):page.index(build.END)]
            for view, ramp in (("win", "win"), ("fold-far", "fold"), ("fold-one", "fold")):
                table = re.search(rf'<table class="cs-grid" data-view="{view}".*?</table>', figure, flags=re.S).group(0)
                shown = re.findall(r'background:(#[0-9a-f]{6});color:[^"]*">(\d+)<', table)
                self.assertTrue(shown)
                # every square sits on its own ramp, within a rounding step of its printed value
                for colour, printed in shown:
                    self.assertIn(colour, {build.shade(int(printed) + d / 100, ramp) for d in range(-50, 51)})
            self.assertEqual(len(re.findall(r'<span class="cs-legend">', figure)), 1 + len(build.HANDS))


if __name__ == "__main__":
    unittest.main()
