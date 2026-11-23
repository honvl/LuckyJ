"""Chapter 56 of the personal guide: where a player's edge lands among the four places, and what that does to each
rank's line.

Every figure the chapter cites comes from ``analysis/edge-split-2026-11-23.json`` (``scripts/mine_edge_split.py``),
which builds on chapter 53's ``analysis/tier-ranking-2026-11-20.json``; the two figures and the table are drawn by
``scripts/build_edge_split.py``.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_edge_split as build  # noqa: E402
import mine_tier_ranking as tr  # noqa: E402

DATA = json.loads((ROOT / "analysis" / "edge-split-2026-11-23.json").read_text(encoding="utf-8"))
LADDER = json.loads((ROOT / "analysis" / "tier-ranking-2026-11-20.json").read_text(encoding="utf-8"))
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang):
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="edge-split">')
    return page[start:page.index("</section>", start)]


def prose(lang):
    text = section(lang)
    for part in build.PARTS:
        text = re.sub(rf"<!-- {part} -->.*?<!-- /{part} -->", "", text, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).replace("&#8722;", "−").replace("&#8217;", "’")


class EdgeSplitTests(unittest.TestCase):
    def test_the_pages_draw_the_data(self):
        for lang, page in PAGES.items():
            html = page.read_text(encoding="utf-8")
            for part in build.PARTS:
                start, end = f"<!-- {part} -->", f"<!-- /{part} -->"
                self.assertEqual(html.count(start), 1)
                drawn = html.split(start, 1)[1].split(end, 1)[0]
                self.assertEqual(drawn, "\n" + build.render(DATA, part, lang) + "\n            ", f"{page.name} {part}")

    def test_the_splits(self):
        sp = DATA["splits"]
        self.assertEqual(sp["jade"], LADDER["mahjong_soul"]["share_slopes"]["jade"])
        self.assertEqual(sp["houou"], LADDER["houou"]["share_slopes"])
        self.assertEqual(sp["fourths_per_first"], {"jade": 1.98, "houou": 1.0, "throne": 1.15})
        # every split moves the average place by one place per place of strength
        for c in (sp["jade"], sp["houou"], sp["throne"]):
            self.assertAlmostEqual(sum(c), 0, places=2)
            self.assertAlmostEqual(-sum(k * v for k, v in zip((1, 2, 3, 4), c)), 1, delta=0.05)  # fitted slopes: 0.96, 1.00 and 0.97
        for lang in PAGES:
            text = prose(lang)
            for number in ("+2.0", "+1.5", "+0.5", "−4.0", "+3.0", "+1.0", "−0.9", "−3.0", "+2.5", "+1.8", "−1.4", "−2.9",
                           "1.98", "1.15"):
                self.assertIn(number, text, f"{lang}: {number}")

    def test_what_saint_3_charges(self):
        ln, worth = DATA["lines"], DATA["worth"]
        self.assertEqual(ln["Saint 3"]["points_sum"], -73.0)
        self.assertEqual((worth["Saint 3"]["fee"], worth["Saint 3"]["jade_split"], worth["Saint 3"]["houou_split"]), (18.25, 148.5, 133.0))
        self.assertEqual((ln["Saint 3"]["jade_split"]["mean_place_needed"], ln["Saint 3"]["houou_split"]["mean_place_needed"]), (2.377, 2.363))
        # the jade-split line is chapter 53's Celestial line
        self.assertEqual(ln["Saint 3"]["jade_split"]["a"], LADDER["mahjong_soul"]["to_pass"]["Saint 3"]["jade"]["a"])
        self.assertEqual((f'{2.5 - ln["Saint 3"]["jade_split"]["a"]:.2f}', f'{2.5 - ln["Saint 3"]["houou_split"]["a"]:.2f}'), ("2.49", "2.47"))
        # Tenhou: Houou's own split is chapter 53's line; the Jade split asks less from 8-dan up
        for d in ("七段", "八段", "九段", "十段"):
            self.assertEqual(ln[d]["houou_split"]["a"], LADDER["houou"]["to_pass"][d]["a"])
            self.assertLessEqual(ln[d]["jade_split"]["a"], ln[d]["houou_split"]["a"])
        self.assertEqual((worth["Celestial"]["jade_split"], worth["Celestial"]["houou_split"], worth["八段"]["fee"]), (32.2, 34.0, 3.75))
        self.assertAlmostEqual(tr.break_even_gap([50, 20, -20, -50], DATA["splits"]["jade"]), 0)
        for lang in PAGES:
            text = prose(lang)
            for number in ("+144", "+66", "−10", "−273", "−73", "18", "148.5", "133.0", "2.377", "2.363", "2.49", "2.47",
                           "2.396", "2.386", "2.362", "2.347", "3.75", "32.2", "34.0", "0.014"):
                self.assertIn(number, text, f"{lang}: {number}")

    def test_the_pace(self):
        pace = {r["scale"]: r for r in DATA["saint3_pace"]}
        self.assertEqual((pace[2.47]["jade_split"], pace[2.47]["houou_split"]), (2.63, 0.45))
        self.assertEqual((pace[2.47]["jade_split_games_per_1000"], pace[2.47]["houou_split_games_per_1000"]), (381, 2244))
        self.assertEqual((pace[2.44]["jade_split"], pace[2.44]["houou_split"]), (7.08, 4.43))
        self.assertEqual(f'{2.5 - DATA["eight_dan_holder_a"]:.2f}', "2.47")
        self.assertEqual(DATA["you_scale"]["results"], 2.438)
        for lang in PAGES:
            text = prose(lang)
            for number in ("2.6", "380", "0.45", "2,200", "160", "2.44", "7.1", "4.4"):
                self.assertIn(number, text, f"{lang}: {number}")

    def test_your_split_and_luckyjs(self):
        you, lj = DATA["you"], DATA["luckyj"]
        self.assertEqual((you["games"], you["shares"]), (370, [0.3027, 0.2649, 0.2514, 0.1811]))
        self.assertEqual((you["lambda"], you["lambda_95"]), (0.487, [-1.667, 1.742]))
        self.assertEqual((lj["games"], lj["shares"]), (1079, [0.317, 0.2753, 0.2391, 0.1687]))
        self.assertEqual((lj["lambda"], lj["lambda_95"]), (0.69, [0.036, 1.223]))
        self.assertEqual((lj["if_jade_split"][3], lj["if_houou_split"][3]), (0.1529, 0.1774))
        # the average Jade Saint 3 sits near the Jade split, as it should
        self.assertLess(abs(DATA["average_saint3"]["lambda"]), 0.3)
        for lang in PAGES:
            text = prose(lang)
            for number in ("30.3%", "26.5%", "25.1%", "18.1%", "28.9", "27.8", "26.0", "17.4", "30.7", "26.8", "23.2", "19.3",
                           "0.49", "−1.67", "1.74", "31.7%", "27.5%", "23.9%", "16.9%", "15.3%", "17.7%", "0.69", "0.04", "1.22"):
                self.assertIn(number, text, f"{lang}: {number}")

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
        for lang, latest in (("en", '<a href="#edge-split">Chapter 56 asks where an edge lands</a>'),
                             ("ja", '<a href="#edge-split">第56章は強さがどの順位に出るかを問う</a>')):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            first = page.index('<li class="is-latest">')
            self.assertIn(latest, page[first:first + 300])
            self.assertEqual(page.count('<span class="contents-num">56</span>'), 1)
            self.assertIn('href="#edge-split"><span class="chapter-next-label">', page)
            self.assertIn("mine_edge_split.py", page)
            self.assertEqual(page.count('aria-label="After the chapters"') + page.count('aria-label="本編の後"'), 1)
            self.assertGreater(page.index('aria-label="After the chapters"' if lang == "en" else 'aria-label="本編の後"'),
                               page.index('id="edge-split"'))
        self.assertIn("Fifty-six chapters", PAGES["en"].read_text(encoding="utf-8"))
        self.assertIn("56の章", PAGES["ja"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
