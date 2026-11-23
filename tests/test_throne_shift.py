"""Chapter 54 of the personal guide: what changes for a new Celestial in the Throne room.

Every figure the chapter cites comes from ``analysis/throne-shift-2026-11-21.json`` (``scripts/mine_throne_shift.py``);
the two figures and the table are drawn by ``scripts/build_throne_shift.py``.
"""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_throne_shift as build  # noqa: E402

DATA = json.loads((ROOT / "analysis" / "throne-shift-2026-11-21.json").read_text(encoding="utf-8"))
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang):
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="throne-room">')
    return page[start:page.index("</section>", start)]


def prose(lang):
    text = section(lang)
    for part in build.PARTS:
        text = re.sub(rf"<!-- {part} -->.*?<!-- /{part} -->", "", text, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text))


def ratio(size, key, system):
    return f"{DATA['swings'][size][key][system]['ratio']:.2f}"


class ThroneShiftTests(unittest.TestCase):
    def test_the_pages_draw_the_data(self):
        for lang, page in PAGES.items():
            html = page.read_text(encoding="utf-8")
            for part in build.PARTS:
                start, end = f"<!-- {part} -->", f"<!-- /{part} -->"
                self.assertEqual(html.count(start), 1)
                drawn = html.split(start, 1)[1].split(end, 1)[0]
                self.assertEqual(drawn, "\n" + build.render(DATA, part, lang) + "\n            ", f"{page.name} {part}")

    def test_the_points(self):
        pts = DATA["points"]
        self.assertEqual(pts["saint3"]["average"], [144.0, 65.6, -9.9, -272.7])
        self.assertEqual([round(v) for v in pts["saint3"]["step_share_pct"]], [19, 18, 63])
        self.assertEqual((pts["celestial"]["schedule"], pts["celestial"]["step_share_pct"]), ([50, 20, -20, -50], [30.0, 40.0, 30.0]))
        # every Celestial result in the sample is the schedule or its double
        self.assertAlmostEqual(pts["celestial"]["at_schedule_pct"] + pts["celestial"]["at_double_pct"], 100.0, places=1)
        self.assertEqual(round(pts["celestial"]["at_double_pct"]), 31)
        self.assertEqual(sum(g["points"] for g in DATA["you"]["throne_games"]), DATA["you"]["points"] - 1000)

    def test_what_a_deal_in_costs(self):
        self.assertEqual((DATA["positions"], DATA["finishes_each"]), (3765, 3000))
        big = [(ratio("8000", k, "saint3"), ratio("8000", k, "celestial")) for k in ("all", "1", "2", "3", "4")]
        self.assertEqual(big, [("1.16", "1.00"), ("1.46", "1.42"), ("1.33", "1.10"), ("1.23", "0.87"), ("0.81", "0.72")])
        small = [(ratio("3900", k, "saint3"), ratio("3900", k, "celestial")) for k in ("all", "1", "2", "3", "4")]
        self.assertEqual(small, [("1.05", "0.97"), ("0.99", "0.92"), ("1.04", "0.96"), ("1.08", "0.99"), ("1.06", "1.03")])
        late = DATA["swings"]["8000"]
        self.assertEqual([(late[k]["positions"], ratio("8000", k, "saint3"), ratio("8000", k, "celestial"))
                          for k in ("South 1-3, 1", "South 1-3, 3", "South 4, 1", "South 4, 3")],
                         [(381, "1.61", "1.62"), (380, "1.25", "0.85"), (87, "2.13", "2.57"), (86, "1.56", "0.73")])
        # third place is where the change is: the largest drop, and well outside its error
        drops = {k: late[k]["ratio_change"] for k in ("1", "2", "3", "4")}
        self.assertEqual(min(drops, key=drops.get), "3")
        self.assertLess(late["3"]["ratio_change"] + 5 * late["3"]["ratio_change_se"], 0)
        self.assertLess(abs(late["1"]["ratio_change"]), 0.05)
        for lang in PAGES:
            text = prose(lang)
            for a, b in big + small:
                self.assertIn(a, text, f"{lang}: {a}")
                self.assertIn(b, text, f"{lang}: {b}")
            for number in ("3,765", "3,000", "0.82", "1.14", "0.75", "0.91", "2.57", "2.13", "0.85", "0.73", "950", "417", "263"):
                self.assertIn(number, text, f"{lang}: {number}")

    def test_the_hand_and_the_field(self):
        hand = DATA["examples"][0]
        self.assertEqual((hand["round"], hand["turn"], hand["tile"], hand["place"], hand["your_score"]), ("South 3-0", 14, "2s", 3, 16500))
        self.assertEqual((hand["8000"]["saint3"]["ratio"], hand["8000"]["celestial"]["ratio"]), (1.02, 0.78))
        field = DATA["field"]
        # corrected on 23 November: 150 seats a room in place of 45; the deal-in difference was noise
        self.assertEqual((field["jade"]["players"], field["throne"]["players"]), (150, 146))
        self.assertEqual([f"{field[g]['deal_in']['mean'] * 100:.1f}" for g in ("jade", "throne")], ["12.7", "12.8"])
        self.assertEqual([f"{field[g]['draw']['mean'] * 100:.1f}" for g in ("jade", "throne")], ["13.1", "13.8"])
        self.assertGreater(field["throne"]["draw"]["mean"] - field["jade"]["draw"]["mean"],
                           2 * (field["throne"]["draw"]["se"] ** 2 + field["jade"]["draw"]["se"] ** 2) ** 0.5)
        self.assertEqual(DATA["model_rewards"], {"earlier_policy_model": [3.0, 1.5, 0.0, -4.5], "mortal_s42": [6.0, 4.0, 2.0, 0.0]})
        for lang in PAGES:
            text = prose(lang)
            for number in ("16,500", "2,300", "1.02", "0.78", "12.8%", "12.7%", "37.0%", "39.2%", "13.1%", "13.8%", "43.8%", "46.5%"):
                self.assertIn(number, text, f"{lang}: {number}")
            self.assertEqual(section(lang).count('data-you="2s"'), 1)

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
        for lang, latest in (("en", '<a href="#throne-room">Chapter 54 answers how to play now that you are Celestial'),
                             ("ja", '<a href="#throne-room">第54章は、魂天になった今の打ち方に答える')):
            page = PAGES[lang].read_text(encoding="utf-8")
            self.assertEqual(page.count('<li class="is-latest">'), 1)
            self.assertEqual(page.count(latest), 1)  # chapter 55 is the latest notice now (tests/test_throne_strategy.py)
            self.assertEqual(page.count('<span class="contents-num">54</span>'), 1)
            self.assertIn('href="#throne-room"><span class="chapter-next-label">', page)
            self.assertIn("mine_throne_shift.py", page)
            self.assertEqual(page.count('aria-label="After the chapters"') + page.count('aria-label="本編の後"'), 1)
        self.assertIn("Fifty-five chapters", PAGES["en"].read_text(encoding="utf-8"))
        self.assertIn("55の章", PAGES["ja"].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
