"""Chapter 55 of the personal guide: the Throne room measured, and the push-or-fold strategy for it.

Every figure the chapter cites comes from ``analysis/throne-strategy-2026-11-23.json`` (``scripts/mine_throne_strategy.py
report``); the two figures and the table are drawn by ``scripts/build_throne_strategy.py``. The chapter also carries a
marked correction to chapter 54's field statistics.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_throne_strategy as build  # noqa: E402

DATA = json.loads((ROOT / "analysis" / "throne-strategy-2026-11-23.json").read_text(encoding="utf-8"))
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang):
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="throne-strategy">')
    return page[start:page.index("</section>", start)]


def prose(lang):
    text = section(lang)
    for part in build.PARTS:
        text = re.sub(rf"<!-- {part} -->.*?<!-- /{part} -->", "", text, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


class ThroneStrategyTests(unittest.TestCase):
    def test_the_pages_draw_the_data(self):
        for lang, page in PAGES.items():
            html = page.read_text(encoding="utf-8")
            for part in build.PARTS:
                start, end = f"<!-- {part} -->", f"<!-- /{part} -->"
                self.assertEqual(html.count(start), 1)
                drawn = html.split(start, 1)[1].split(end, 1)[0]
                self.assertEqual(drawn, "\n" + build.render(DATA, part, lang) + "\n            ", f"{page.name} {part}")

    def test_the_room(self):
        sp, ca, ow = DATA["speed"], DATA["callers"], DATA["open_wins"]
        self.assertEqual(DATA["sources"], {"throne_games": 42, "your_games": 379,
                                           "spots": {"you": 500, "jade_field": 1322, "throne": 215, "you_throne": 6}})
        self.assertEqual((sp["jade_field"]["tenpai_turn"], sp["throne"]["tenpai_turn"]), (9.66, 9.48))
        self.assertEqual((sp["jade_field"]["first_riichi_discard"], sp["throne"]["first_riichi_discard"]), (33.3, 32.5))
        self.assertEqual([ca["throne"][f"call {k}"]["pct"] for k in (1, 2, 3)], [20.4, 46.9, 82.1])
        self.assertEqual([ca["jade_field"][f"call {k}"]["pct"] for k in (1, 2, 3)], [19.0, 45.2, 82.7])
        self.assertEqual((ow["throne"]["open_paid"], ow["jade_field"]["open_paid"]), (4336, 4792))
        # the callers' tenpai rates do not differ: every gap is inside two standard errors
        for k in (1, 2, 3):
            a, b = ca["throne"][f"call {k}"], ca["jade_field"][f"call {k}"]
            self.assertLess(abs(a["pct"] - b["pct"]), 2 * (a["se"] ** 2 + b["se"] ** 2) ** 0.5)
        self.assertEqual(DATA["draw_tenpai_opponents"], {"jade_saint3": 1.3, "celestial": 1.42})
        for lang in PAGES:
            text = prose(lang)
            for number in ("9.48", "9.66", "32.5", "33.3", "20.4%", "19.0%", "46.9%", "45.2%", "4,336", "4,792", "1.42", "1.30",
                           "47.2%", "43.3%", "48.5%", "51.9%", "2.44", "2.26", "2.31", "0.29"):
                self.assertIn(number, text, f"{lang}: {number}")

    def test_the_pushes(self):
        pu, pl = DATA["pushes"], DATA["places"]
        self.assertEqual((pu["throne"]["push"]["pct"], pu["jade_field"]["push"]["pct"], pu["you"]["push"]["pct"], pu["s42"]),
                         (81.9, 80.6, 74.2, 77.7))
        self.assertEqual((pl["3"]["you"]["pct"], pl["3"]["s42"], pl["3"]["celestials"]["pct"]), (62.9, 75.8, 86.0))
        third = DATA["third_big"]
        self.assertEqual((third["spots"], third["you"]["pct"], third["s42"], third["push_ev"]), (61, 73.8, 86.8, 2.52))
        cells = {c["cell"]: c for c in DATA["cells"]}
        self.assertEqual([cells[k]["you"]["pct"] for k in ("4+ han, 4+ live", "3 han, 4+ live", "1-2 han, 3 or fewer live")],
                         [94.2, 90.8, 38.5])
        self.assertEqual((DATA["late_thin_pushes"]["won"]["pct"], DATA["late_thin_pushes"]["dealt"]["pct"]), (14.6, 25.1))
        for lang in PAGES:
            text = prose(lang)
            for number in ("81.9%", "80.6%", "74.2%", "77.7%", "62.9%", "75.8%", "86.0%", "73.8%", "86.8%", "+2.5", "14.6%", "25.1%",
                           "94.2%", "90.8%", "38.5%"):
                self.assertIn(number, text, f"{lang}: {number}")

    def test_the_two_hands(self):
        ex, fx = DATA["example"], DATA["fold_example"]
        self.assertEqual((ex["round"], ex["turn"], ex["place"], ex["han"], ex["live"]), ("South 3-2", 16, 3, 4, 6))
        self.assertGreater(ex["s42_push"], 0.95)
        self.assertEqual((fx["round"], fx["turn"], fx["place"], fx["cut"], fx["keep"]), ("South 4-0", 15, 2, "8s", ["2m"]))
        # 2m was every opponent's winning tile, and the hand was 1 or 2 han
        self.assertTrue(all(o["tenpai"] and "2m" in o["waits"] for o in fx["opponents"]))
        self.assertEqual(fx["hand"]["han"], [2, 1])
        for lang in PAGES:
            sec = section(lang)
            self.assertEqual(sec.count('data-you="4m"'), 1)
            self.assertEqual(sec.count('data-you="8s"'), 1)

    def test_the_correction_to_chapter_54(self):
        for lang in PAGES:
            page = PAGES[lang].read_text(encoding="utf-8")
            for mark in ("fix-54-field", "fix-54-people", "fix-54-stay", "fix-54-draw"):
                self.assertEqual(page.count(f'<mark id="{mark}" class="guide-changed">'), 1, f"{lang}: {mark}")
            self.assertIn('href="#fix-54-field"', page)
            self.assertIn('href="#fix-54-stay"', page)
            self.assertEqual(page.count('<li class="is-correction"><span class="guide-news-date">23 Nov</span>')
                             + page.count('<li class="is-correction"><span class="guide-news-date">11月23日</span>'), 2)  # chapters 53 and 54

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))
        self.assertLessEqual(len(re.findall(r"\bnot [a-z ]+, it is\b|\bis not [a-z ]+\. It is\b", prose("en"))), 1)
        for line in section("ja").splitlines():
            if line.strip().startswith(("<p>", "<p ")) and "timing-" not in line:
                self.assertTrue(line.rstrip().endswith("</p>"), line[:60])

    def test_the_notice_and_the_chain_of_links(self):
        for lang, latest in (("en", '<a href="#throne-strategy">Chapter 55 measures the Throne room</a>'),
                             ("ja", '<a href="#throne-strategy">第55章は王座の間を測る</a>')):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            first = page.index('<li class="is-latest">')
            self.assertIn(latest, page[first:first + 300])
            self.assertEqual(page.count('<span class="contents-num">55</span>'), 1)
            self.assertIn('href="#throne-strategy"><span class="chapter-next-label">', page)
            self.assertIn("mine_throne_strategy.py", page)
            self.assertEqual(page.count('aria-label="After the chapters"') + page.count('aria-label="本編の後"'), 1)
        self.assertIn("Fifty-five chapters", PAGES["en"].read_text(encoding="utf-8"))
        self.assertIn("55の章", PAGES["ja"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
