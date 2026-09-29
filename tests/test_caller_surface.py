"""Chapter 18's caller grid: the page shows the data, and the figures the prose cites hold."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_caller_surface as build  # noqa: E402
import mine_caller_surface as surface  # noqa: E402

DATA = json.loads(build.DATA.read_text())


def square(calls, run, discard, key="can_win"):
    return round(build.value(DATA["grid"][key][f"{calls}-{run}"]["cells"][str(discard)], DATA["min_readings"]))


class CallerGridTests(unittest.TestCase):
    def test_the_page_draws_the_data(self):
        page = build.PAGE.read_text(encoding="utf-8")
        start, end = page.index(build.START), page.index(build.END) + len(build.END)
        self.assertEqual(page[start:end], build.render(DATA))

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

    def test_buckets_and_colours(self):
        self.assertEqual([surface.run_bucket(r) for r in (0, 1, 2, 3, 7)], [0, 1, 2, 3, 3])
        self.assertEqual([surface.calls_bucket(c) for c in (1, 2, 3, 4)], [1, 2, 3, 3])
        self.assertEqual(build.shade(0), "#f4f0e6")
        self.assertEqual(build.shade(50), "#f5a583")
        self.assertEqual(build.shade(100), "#8e2a15")


if __name__ == "__main__":
    unittest.main()
