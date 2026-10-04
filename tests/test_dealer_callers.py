"""Chapter 28 of the personal guide: the dealer's one call, the run from the wall, and the suit a river avoids.

Every figure the chapter cites comes from ``analysis/dealer-callers-2026-10-04.json``
(``scripts/mine_dealer_callers.py``); the chart is drawn from it by ``scripts/build_dealer_caller_figure.py``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "analysis" / "dealer-callers-2026-10-04.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def half_up(v: float) -> int:
    return int(v + 0.5)


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="dealer-call">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    """The chapter's words and tables, without the drawn chart."""
    text = section(lang)
    a, b = text.index("<!-- dealer-figure -->"), text.index("<!-- /dealer-figure -->")
    text = text[:a] + text[b:]
    text = re.sub(r'href="[^"]*"', "", text)
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"&#\d+;", " ", text)


class TheDealerTests(unittest.TestCase):
    def fit(self, hand: str, who: str, turn: int) -> int:
        return half_up(DATA["curves"][hand][who]["at"][str(turn)][0])

    def test_the_lines(self):
        curves = DATA["curves"]
        self.assertEqual((curves["far"]["dealer"]["spots"], curves["far"]["other"]["spots"]), (1335, 3165))
        self.assertEqual((curves["one"]["dealer"]["spots"], curves["one"]["other"]["spots"]), (816, 2067))
        # a far hand: half at the dealer's 10th, 65% live at anyone else's 10th and half at their 13th
        self.assertEqual(self.fit("far", "dealer", 10), 50)
        self.assertEqual([round(c["turn"]) for c in curves["far"]["dealer"]["crossings_50"]], [10])
        self.assertEqual((self.fit("far", "other", 10), self.fit("far", "other", 13)), (65, 50))
        # one-shanten: from the dealer's 12th, still 64% live at anyone else's 14th
        self.assertEqual(curves["one"]["dealer"]["line"], 12)
        self.assertEqual(self.fit("one", "other", 14), 64)
        self.assertIsNone(curves["one"]["other"]["line"])
        # ties: the 9th and the 10th against the dealer; 62% at their 5th and 53% at their 8th from one-shanten
        self.assertEqual((DATA["ties"]["far"]["dealer"]["line"], DATA["ties"]["one"]["dealer"]["line"]), (9, 10))
        at = DATA["ties"]["one"]["dealer"]["at"]
        self.assertEqual((half_up(at["5"][0]), half_up(at["8"][0])), (62, 53))
        # early on LuckyJ pushes against the dealer as hard as against anyone; from about the 6th it folds sooner
        for hand in ("far", "one"):
            for turn in range(6, 13):
                self.assertLess(self.fit(hand, "dealer", turn), self.fit(hand, "other", turn), (hand, turn))
        self.assertGreaterEqual(self.fit("far", "dealer", 4), self.fit("far", "other", 4))
        self.assertGreater(self.fit("one", "dealer", 4), self.fit("one", "other", 4))

    def test_the_run_does_not_move_luckyj(self):
        for hand in ("far", "one"):
            effects = DATA["effects"]["LuckyJ"][hand]
            for name in ("run", "dealer_x_run"):
                self.assertLess(abs(effects[name]["beta"]), 2 * effects[name]["se"], (hand, name))
            late = DATA["effects"]["LuckyJ_from_9"][hand]
            self.assertLess(abs(late["run"]["beta"]), 2 * late["run"]["se"], hand)
            self.assertLess(late["dealer"]["beta"], -2 * late["dealer"]["se"], hand)

    def test_the_squares(self):
        squares = {k: half_up(v) for k, v in DATA["squares"].items()}
        self.assertEqual([squares[k] for k in ("3-1", "4-0", "5-0", "6-1", "7-2", "8-3")], [3, 4, 7, 12, 18, 24])
        self.assertEqual([squares[k] for k in ("8-0", "10-3", "10-0", "12-3", "12-0")], [21, 41, 30, 55, 34])

    def test_the_cost_the_suits_and_you(self):
        self.assertEqual((DATA["cost"]["dealer"]["average"], DATA["cost"]["other"]["average"]), (5949, 3759))
        at8 = {name: DATA["suit"][name]["at"]["8"][0] for name in DATA["suit"] if "8" in DATA["suit"][name]["at"]}
        self.assertEqual({k: round(v, 1) for k, v in at8.items()},
                         {"avoided suit": 1.4, "other suits": 1.0, "honors": 0.7, "every suit shown": 2.2})
        self.assertEqual(sum(DATA["suit"][k]["cuts"] for k in ("avoided suit", "other suits", "honors")), 14200)
        self.assertEqual(DATA["suit"]["every suit shown"]["cuts"], 28129)
        ties = DATA["live_ties"]
        self.assertEqual((half_up(ties["through 8"]["other_share"]), half_up(ties["after 8"]["other_share"])), (45, 55))
        self.assertEqual((ties["through 8"]["avoided"] + ties["through 8"]["other"], ties["after 8"]["avoided"] + ties["after 8"]["other"]), (216, 64))
        tenpai = DATA["tenpai"]
        self.assertEqual((tenpai["only safe tiles keep shanten"]["safe"], tenpai["only safe tiles keep shanten"]["turns"]), (98.8, 1089))
        self.assertEqual((tenpai["safe tile costs shanten"]["safe"], tenpai["safe tile costs shanten"]["turns"]), (3.5, 1521))
        you = DATA["you_vs_lj"]
        self.assertEqual([(half_up(you[h][w]["live"]), half_up(you[h][w]["luckyj"])) for h in ("far", "one") for w in ("dealer", "other")],
                         [(74, 77), (77, 82), (67, 66), (72, 71)])
        self.assertEqual((DATA["effects"]["You"]["far"]["spots"], DATA["effects"]["You"]["one"]["spots"]), (657, 410))

    def test_the_spot(self):
        spot = DATA["spot"]
        self.assertEqual((spot["q_turn"], spot["ts_run"], spot["q_dealer"], spot["kind"], spot["avoided"], spot["best_sh"]),
                         (8, 3, True, "tie", 2, 1))
        self.assertTrue(spot["on_wait"])


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("from 21% to 24%", "62% at the dealer", "53% at their 8th", "96 to 99%", "24% after three in a row",
                       "41% against 30%", "55% against 34%", "5,949", "3,759", "65% of the time at another caller",
                       "64% of the time at the 14th", "the 9th discard for a far hand and the 10th", "1.0 times per 100",
                       "honor 0.7", "1.4 times", "2.2 of a live", "45% of the time", "55% after", "98.8%", "3.5%",
                       "74% of those turns", "77% at the same discards", "82%", "67% against 66%", "72% against 71%",
                       "4,500", "1,335", "2,883", "816", "657", "410", "14,200", "28,129", "1,089", "1,521", "216", "64 after"):
            self.assertIn(phrase, " ".join(text.split()), phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_chart_matches_the_data(self):
        done = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_dealer_caller_figure.py"), "--check"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_the_replay_links_name_your_tiles(self):
        for lang in PAGES:
            links = re.findall(r'r=(East\+\d-\d)&amp;t=(\d+)" target="_blank" rel="noopener" data-you="([^"]+)"', section(lang))
            self.assertEqual(links, [("East+4-1", "4", "2p"), ("East+4-1", "7", "3p"), ("East+3-0", "13", "3s")], lang)


if __name__ == "__main__":
    unittest.main()
