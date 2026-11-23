"""Chapter 53 of the personal guide: Saint 2 to Celestial beside the Houou dans, on one strength scale.

Every figure the chapter cites comes from ``analysis/tier-ranking-2026-11-20.json`` (``scripts/mine_tier_ranking.py``);
the two figures and the table are drawn by ``scripts/build_tier_ranking.py``.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_tier_ranking as build  # noqa: E402

DATA = json.loads((ROOT / "analysis" / "tier-ranking-2026-11-20.json").read_text(encoding="utf-8"))
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def place(a):
    return f"{2.5 - a:.2f}"


def section(lang):
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="tier-ladder">')
    return page[start:page.index("</section>", start)]


def prose(lang):
    text = section(lang)
    for part in build.PARTS:
        text = re.sub(rf"<!-- {part} -->.*?<!-- /{part} -->", "", text, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


class TierRankingTests(unittest.TestCase):
    def test_the_pages_draw_the_data(self):
        for lang, page in PAGES.items():
            html = page.read_text(encoding="utf-8")
            for part in build.PARTS:
                start, end = f"<!-- {part} -->", f"<!-- /{part} -->"
                self.assertEqual(html.count(start), 1)
                drawn = html.split(start, 1)[1].split(end, 1)[0]
                self.assertEqual(drawn, "\n" + build.render(DATA, part, lang) + "\n            ", f"{page.name} {part}")

    def test_the_bands_stack_in_order(self):
        for side in ("mahjong_soul", "tenhou"):
            edges = [seg["from"] for seg in DATA["bands"][side] if seg["from"] is not None]
            self.assertEqual(edges, sorted(edges))
            for lower, upper in zip(DATA["bands"][side], DATA["bands"][side][1:]):
                self.assertEqual(lower["to"], upper["from"])
        self.assertEqual([seg["rank"] for seg in DATA["bands"]["mahjong_soul"]], ["Saint 2", "Saint 3", "Celestial"])
        self.assertEqual([seg["rank"] for seg in DATA["bands"]["tenhou"]], ["七段", "八段", "九段", "十段", "天鳳"])

    def test_the_lines_the_prose_cites(self):
        ms, th = DATA["mahjong_soul"]["to_pass"], DATA["houou"]["to_pass"]
        lines = [place(ms[k]["a"]) for k in ("Saint 1", "Saint 2", "Saint 3")] + [place(th[k]["a"]) for k in ("七段", "八段", "九段", "十段")]
        # corrected 23 November: Houou's fourth-place costs are 135 / 150 / 165 / 180 for 7- to 10-dan
        self.assertEqual(th["七段"]["gap"], 0.0)
        self.assertEqual(lines, ["2.53", "2.51", "2.49", "2.48", "2.43", "2.39", "2.35"])
        # the Jade room is the easier road for every Saint tier, so the bands do not lean on the bridge between rooms
        self.assertTrue(all(ms[k]["easier"] == "jade" for k in ms))
        self.assertEqual([f"{ms[k]['jade']['mean_place_needed']:.3f}" for k in ("Saint 1", "Saint 2", "Saint 3")], ["2.424", "2.396", "2.377"])
        self.assertEqual([f"{th[k]['mean_place_needed']:.3f}" for k in ("七段", "八段", "九段", "十段")], ["2.500", "2.451", "2.408", "2.369"])
        # Celestial and 8-dan are level within the error; 9-dan asks clearly more
        gap = th["七段"]["a"] - ms["Saint 3"]["a"]
        error = (th["七段"]["se_link"] ** 2 + ms["Saint 3"]["se"] ** 2) ** 0.5
        self.assertLess(abs(gap), 1.96 * error)
        self.assertGreater(th["八段"]["a"] - ms["Saint 3"]["a"], 1.96 * error)
        for lang in PAGES:
            text = prose(lang)
            for number in lines + ["2.424", "2.396", "2.377", "2.500", "2.451", "2.408", "2.369", "0.123"]:
                self.assertIn(number, text, f"{lang}: {number}")

    def test_the_link_and_the_holders(self):
        link, tiers, you = DATA["link"], DATA["mahjong_soul"]["tiers"], DATA["you"]
        self.assertEqual((link["policy"]["places_per_skill"], link["policy"]["places_per_skill_se"]), (0.5571, 0.0402))
        self.assertEqual((place(link["policy"]["field_a"]), place(link["s42"]["field_a"])), ("2.48", "2.49"))
        self.assertEqual(place(tiers["Celestial"]["a"]), "2.52")
        self.assertEqual((place(tiers["Celestial"]["a"] + 1.96 * tiers["Celestial"]["se"]),
                          place(tiers["Celestial"]["a"] - 1.96 * tiers["Celestial"]["se"])), ("2.49", "2.54"))
        self.assertEqual([place(tiers[k]["a"]) for k in ("Master 1", "Master 2", "Master 3", "Saint 1", "Saint 2")],
                         ["2.67", "2.61", "2.56", "2.55", "2.52"])
        self.assertEqual((DATA["mahjong_soul"]["bridging_players"], DATA["mahjong_soul"]["tables"]),
                         (420, {"jade": 100000, "jade_of_bridging_players": 29177, "throne": 79867}))
        self.assertEqual((place(you["a_from_mortal"]), place(you["a_from_results"]), place(you["a_from_mortal_s42"])), ("2.47", "2.44", "2.52"))
        scale = DATA["tenhou_on_the_scale"]
        self.assertEqual([place(scale[k]["a_fit"]) for k in ("七段", "八段", "九段", "十段", "天鳳")], ["2.49", "2.47", "2.44", "2.42", "2.39"])
        for lang in PAGES:
            text = prose(lang)
            for number in ("0.557", "0.040", "2.46", "2.50", "420", "29,177", "16,741", "53,390", "79,867", "100,000", "15,929",
                           "2.324", "2.33", "2.55", "0.014", "0.005", "868", "74", "0.025", "0.006"):
                self.assertIn(number, text, f"{lang}: {number}")

    def test_luckyj_from_its_results(self):
        lj = DATA["luckyj"]
        self.assertEqual((lj["games"], lj["mean_place"], place(lj["a"]), place(lj["opponents_a"]), place(lj["a_from_mortal"])),
                         (1076, 2.259, "2.34", "2.58", "2.46"))
        self.assertEqual((place(lj["a"] + 1.96 * lj["se"]), place(lj["a"] - 1.96 * lj["se"])), ("2.27", "2.40"))
        self.assertEqual((lj["a_from_mortal_predicts_place"], lj["tokujou_10dan_place_needed"]), (2.387, 2.265))
        line = DATA["houou"]["to_pass"]  # 九段's entry passes 9-dan and reaches 10-dan; 十段's reaches Tenhou-i
        # past the 10-dan line, level with Tenhou-i within its range; agreement alone underrates it by four errors
        self.assertGreater(lj["a"], line["九段"]["a"])
        self.assertLess(abs(lj["a"] - line["十段"]["a"]), 1.96 * lj["se"])
        self.assertGreater(lj["a_from_mortal_predicts_place"] - lj["mean_place"], 3 * lj["mean_place_se"])
        for lang in PAGES:
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<mark id="add-53-luckyj" class="guide-changed">'), 1)
            self.assertIn('href="#add-53-luckyj"', page)
            self.assertEqual(section(lang).count('class="tier-lj"'), 1)
            text = prose(lang)
            for number in ("1,076", "2.58", "2.259", "2.34", "2.27", "2.40", "2.46", "2.39", "0.13", "2.265", "75", "180"):
                self.assertIn(number, text, f"{lang}: {number}")

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))
        self.assertLessEqual(len(re.findall(r"\bnot [a-z ]+, it is\b|\bis not [a-z ]+\. It is\b", prose("en"))), 1)
        for line in section("ja").splitlines():  # a line break inside Japanese prose shows as a space
            if line.strip().startswith(("<p>", "<p ")) and "timing-" not in line:
                self.assertTrue(line.rstrip().endswith("</p>"), line[:60])

    def test_the_notice_and_the_chain_of_links(self):
        for lang, latest in (("en", '<a href="#tier-ladder">Chapter 53 ranks Saint 2 to Celestial'), ("ja", '<a href="#tier-ladder">第53章は、雀聖2から魂天までを')):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            self.assertEqual(page.count(latest), 1)  # chapter 54 is the latest notice now (tests/test_throne_shift.py)
            self.assertEqual(page.count('<span class="contents-num">53</span>'), 1)
            self.assertIn('href="#tier-ladder"><span class="chapter-next-label">', page)
            self.assertIn("mine_tier_ranking.py", page)
            self.assertEqual(page.count('aria-label="After the chapters"') + page.count('aria-label="本編の後"'), 1)


if __name__ == "__main__":
    unittest.main()
