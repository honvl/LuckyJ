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
        self.assertEqual(build.fold_lines(FOLD), {1: 9, 2: 7, 3: 7})
        one, more = FOLD["blocks"]["1"], FOLD["blocks"]["2+"]
        fit = lambda block, d: round(block["cells"][str(d)]["fit"])
        self.assertEqual((one["spots"], more["spots"]), (7821, 2812))
        self.assertEqual((min(fit(one, d) for d in range(1, 7)), max(fit(one, d) for d in range(1, 7))), (72, 80))
        self.assertEqual([fit(one, d) for d in (8, 9, 10)], [57, 48, 40])
        self.assertEqual([fit(more, d) for d in (6, 7, 8)], [56, 47, 40])
        # the run does not move the far-hand line; it does move LuckyJ's choice at tenpai against one call
        for block in ("1", "2+"):
            far = FOLD["run_slope"]["far"][block]
            self.assertLess(abs(far["slope"]), 2 * far["se"])
        self.assertEqual({b: (round(v["slope"], 2), round(v["se"], 2)) for b, v in FOLD["run_slope"]["far"].items()},
                         {"1": (0.03, 0.03), "2+": (-0.06, 0.04)})
        tenpai = FOLD["run_slope"]["tenpai"]["1"]
        self.assertEqual((round(tenpai["slope"], 2), round(tenpai["se"], 2), tenpai["spots"]), (-0.36, 0.11, 939))
        self.assertEqual([round(FOLD["tenpai_by_run"][r]["live"]) for r in "0123"], [17, 11, 5, 7])

    def test_chapter_19_tables_show_the_patterns(self):
        for path in build.PAGES.values():
            with self.subTest(page=path.name):
                self.check_chapter_19_tables(path.read_text(encoding="utf-8"))

    def check_chapter_19_tables(self, page):
        chapter = page[page.index('<section class="point" id="fold-line">'):]
        chapter = chapter[: chapter.index("</section>")]
        tables = re.findall(r"<tbody>(.*?)</tbody>", chapter, flags=re.S)
        cells = [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row)] for row in re.findall(r"<tr>(.*?)</tr>", tables[0])]
        pct = lambda v: f"{round(v)}%"
        before = ["call", "hand_after_three", "hand_after_two", "hand_after_one", "hand_after_hand"]
        self.assertEqual([c[1:] for c in cells], [[pct(PATTERNS["patterns"][k]["rows"]["could_win"])] + [pct(v) for v in PATTERNS["patterns"][k]["rows"]["by_run"][:2]] for k in before])
        self.assertEqual([PATTERNS["patterns"][k]["rows"]["n"] for k in before], [14033, 1722, 2120, 4793, 11874])
        cells = [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row)] for row in re.findall(r"<tr>(.*?)</tr>", tables[1])]
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

    def test_buckets_and_colours(self):
        self.assertEqual([surface.run_bucket(r) for r in (0, 1, 2, 3, 7)], [0, 1, 2, 3, 3])
        self.assertEqual([surface.calls_bucket(c) for c in (1, 2, 3, 4)], [1, 2, 3, 3])
        self.assertEqual(build.shade(0), "#f4f0e6")
        self.assertEqual(build.shade(50), "#f5a583")
        self.assertEqual(build.shade(100), "#8e2a15")


if __name__ == "__main__":
    unittest.main()
