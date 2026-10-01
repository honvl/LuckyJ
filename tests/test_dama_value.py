"""Chapter 24: the chart is the data, and every figure the prose and the cards cite holds."""

import json
import re
import sys
import unittest
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_dama_value_figure as figure  # noqa: E402

DATA = json.loads(figure.DATA.read_text())
SPOTS = json.loads((ROOT / "data" / "personal_guide_spots.json").read_text(encoding="utf-8"))["spots"]


def half_up(v):
    # Python's round() sends 74.5 to 74; the chapter rounds halves up.
    return int(v + 0.5)


def chapter(name="honver.html"):
    page = (ROOT / "site" / name).read_text(encoding="utf-8")
    start = page.index('<section class="point" id="big-hands">')
    text = page[start:page.index("</section>", start)]
    text = re.sub(r"<figure.*?</figure>", " ", text, flags=re.S)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text)))


def share(cell):
    return 100 * cell["declared"] / cell["n"]


def fitted(key, turn):
    return DATA["curves"][key]["at"][str(turn)][0]


def spot(spot_id):
    return next(s for s in SPOTS if s["id"] == spot_id)


def example(rnd):
    return next(e for e in DATA["examples"] if e["round"] == rnd)


class ChartTests(unittest.TestCase):
    def test_both_editions_draw_the_data(self):
        for lang, path in figure.PAGES.items():
            page = path.read_text(encoding="utf-8")
            start, end = page.index(figure.START), page.index(figure.END) + len(figure.END)
            with self.subTest(lang=lang):
                self.assertEqual(page[start:end], figure.render(DATA, lang))

    def test_thin_series_are_straight_lines(self):
        for key, curve in DATA["curves"].items():
            with self.subTest(key=key):
                if curve["hands"] < 100:
                    self.assertEqual(curve["df"], 1)


class ProseTests(unittest.TestCase):
    def test_your_big_hands(self):
        big = DATA["you"]["big"]
        self.assertEqual((big["recent"]["hands"], big["recent"]["declared"]), (7, 5))
        self.assertEqual(half_up(big["recent"]["luckyj_expects"]), 3)
        self.assertEqual(half_up(big["recent"]["mortal_expects"]), 2)
        self.assertEqual((big["before"]["hands"], big["before"]["declared"]), (53, 25))
        self.assertEqual(half_up(big["before"]["luckyj_expects"]), 27)
        text = chapter()
        for phrase in ("5 of your 7 first tenpais", "about 3 and Mortal", "25 declared out of 53, against 27 expected"):
            self.assertIn(phrase, text)

    def test_how_often_you_declare(self):
        per = DATA["you"]["per_100"]
        self.assertEqual([half_up(per[k]["riichis_per_100"]) for k in ("newest", "recent", "before", "luckyj")], [30, 23, 19, 19])
        self.assertEqual([half_up(per[k]["first_tenpais_per_100"]) for k in ("newest", "before")], [28, 25])
        newest = per["newest"]
        self.assertEqual(newest["first_tenpais"], 13)
        self.assertEqual(round(newest["first_tenpais"] * newest["first_declared_pct"] / 100), 12)
        self.assertEqual(half_up(newest["first_mortal_pct"]), 87)
        riichis = DATA["you"]["newest_riichis"]
        self.assertEqual((riichis["riichis"], riichis["won"], riichis["dealt"], riichis["neither"]), (14, 4, 3, 7))
        self.assertEqual(sum(w >= 0.99 for w in riichis["dealt_mortal"]), 2)
        self.assertEqual(half_up(100 - per["luckyj"]["riichis_won_pct"]), 48)

    def test_luckyj_by_value(self):
        cells = DATA["cells"]
        expected = {"no yaku": 85, "some waits": 91, "1-2": 83, "3 two-sided": 84, "3 other": 26, "4 other": 27, "5+ other": 12}
        self.assertEqual({k: half_up(share(cells[k])) for k in expected}, expected)
        self.assertEqual(DATA["luckyj_first_tenpais_quiet"], 2177)

    def test_where_the_curves_cross_half(self):
        self.assertGreaterEqual(min(fitted("3", t) for t in range(5, 13)), 80)
        self.assertEqual(half_up(fitted("3", 7)), 90)
        self.assertEqual([half_up(fitted("4", t)) for t in (4, 12)], [86, 41])
        four = [c["turn"] for c in DATA["curves"]["4"]["crossings_50"] if c["direction"] == "down"]
        self.assertTrue(len(four) == 1 and 10 < four[0] < 11, four)
        self.assertEqual([half_up(fitted("5", t)) for t in (6, 11)], [75, 18])
        five = [c["turn"] for c in DATA["curves"]["5"]["crossings_50"] if c["direction"] == "down"]
        self.assertTrue(len(five) == 1 and 8 < five[0] < 9, five)
        # the rule: declare through the 10th and the 7th, either way on the 8th, dama from the 11th and the 9th
        self.assertGreater(fitted("4", 10), 50)
        self.assertLess(fitted("4", 11), 50)
        self.assertGreater(fitted("5", 7), 50)
        self.assertLess(fitted("5", 9), 50)
        self.assertLess(abs(fitted("5", 8) - 50), 5)

    def test_the_trade_at_the_eleventh_turn(self):
        trade = DATA["trade"]
        self.assertEqual((trade["turn"], trade["live"]), (11, 6))
        main = trade["dama 4+"]
        dama, riichi = main["dama"], main["riichi"]
        self.assertEqual([half_up(100 * x) for x in (dama["ron"], riichi["ron"], dama["tsumo"], riichi["tsumo"])], [46, 28, 16, 21])
        self.assertEqual([round(x, -1) for x in (dama["lost"], riichi["lost"])], [-2180, -2630])
        self.assertEqual(half_up(100 * (dama["ron"] + dama["tsumo"])), 62)
        self.assertEqual(half_up(100 * (riichi["ron"] + riichi["tsumo"])), 49)
        self.assertAlmostEqual(1 - riichi["ron"] / dama["ron"], 0.4, delta=0.05)  # "two in five of your rons"
        five, four = main["hands"]["5"], main["hands"]["4"]
        self.assertEqual([round(five["values"][k], -2) for k in ("riichi_ron", "riichi_tsumo")], [12500, 13900])
        self.assertEqual([round(x, -1) for x in (five["dama"], five["riichi"], four["dama"], four["riichi"])], [4830, 5020, 4040, 4000])
        self.assertLessEqual(max(abs(five["difference"]), abs(four["difference"])), 200)
        self.assertTrue(-1150 <= min(five["band"][0], four["band"][0]) <= -900)
        self.assertTrue(1400 <= max(five["band"][1], four["band"][1]) <= 1600)
        self.assertEqual((main["riichi_hands"], main["dama_hands"]), (2289, 208))
        wider = trade["dama 3+"]["hands"]
        self.assertLessEqual(max(wider[h]["difference"] for h in ("4", "5")), 750)
        self.assertTrue(all(wider[h]["band"][0] < 0 < wider[h]["band"][1] for h in ("4", "5")))
        extra = DATA["extra_han"]
        self.assertEqual(half_up(100 * (1 - extra["ron"][0])), 44)
        self.assertEqual(extra["ron_wins"] + extra["tsumo_wins"], 4126)
        text = chapter()
        for phrase in ("4,830", "5,020", "4,040", "4,000", "about 12,500", "about 13,900", "62% against 49%", "within 200 points",
                       "44% of riichi rons", "two in five of your rons"):
            self.assertIn(phrase, text)

    def test_chasing_a_riichi(self):
        chase = DATA["chase"]
        self.assertEqual(half_up(share(chase["1-2"])), 26)
        self.assertEqual((chase["3"]["declared"], chase["3"]["n"]), (2, 23))
        self.assertEqual((chase["4+"]["declared"], chase["4+"]["n"]), (4, 36))
        self.assertEqual(half_up(share(chase["no yaku"])), 56)
        self.assertEqual(sum(c["n"] for c in chase.values()), 147)

    def test_chapter_23_counted_the_best_tile(self):
        ch23 = DATA["chapter23_definitions"]
        self.assertEqual((ch23["best tile 5+"]["declared"], ch23["best tile 5+"]["n"]), (13, 39))
        self.assertEqual((ch23["every tile 5+"]["declared"], ch23["every tile 5+"]["n"]), (2, 23))
        self.assertIn("13 of 39", chapter())


class CardTests(unittest.TestCase):
    def test_the_cards_quote_mortal_and_luckyj(self):
        made = example("East 2-3")
        self.assertEqual(made["mortal_first"][0], "7p")
        self.assertEqual(half_up(100 * made["mortal_first"][1]), 94)
        self.assertEqual(made["mortal_riichi"], 0.055)
        self.assertIn("75% at its 6th turn and 18% at its 11th", spot("made-mangan-turn-eleven")["luckyj"])
        haneman = example("South 2-0")
        self.assertEqual((haneman["mortal_first"][0], half_up(100 * haneman["mortal_first"][1])), ("8p", 98))
        self.assertEqual(half_up(fitted("4", 11)), 48)
        self.assertIn("48%", spot("riichi-made-haneman")["luckyj"])
        shanpon = dict(example("South 4-0")["mortal_top"])
        self.assertEqual([half_up(100 * shanpon[k]) for k in ("5s", "3s")], [58, 34])
        self.assertEqual(half_up(100 * (1 - example("South 4-0")["mortal_riichi"])), 95)
        chase = example("East 1-0")
        self.assertEqual((chase["mortal_first"][0], half_up(100 * chase["mortal_first"][1])), ("7m", 97))
        self.assertEqual(half_up(100 * (1 - example("East 4-0")["mortal_riichi"])), 96)
        self.assertGreater(example("South 1-0")["mortal_riichi"], 0.95)

    def test_both_editions_name_the_same_turns(self):
        for name in ("honver.html", "honver-ja.html"):
            page = (ROOT / "site" / name).read_text(encoding="utf-8")
            start = page.index('<section class="point" id="big-hands">')
            section = page[start:page.index("</section>", start)]
            with self.subTest(page=name):
                self.assertIn('data-guide-examples="big-hands"', section)
                self.assertEqual(len(re.findall(r'href="replay\.html\?', section)), 2)


class VoiceTests(unittest.TestCase):
    def test_voice_rules(self):
        for name in ("honver.html", "honver-ja.html"):
            words = chapter(name)
            with self.subTest(page=name):
                self.assertNotRegex(words, r"[—–]")
                self.assertNotRegex(words, r"(?i)\bof course\b|もちろん|のである")
                if name == "honver-ja.html":
                    self.assertLessEqual(len(re.findall(r"ではなく", words)), 1)
                else:
                    self.assertLessEqual(len(re.findall(r"(?i)\brather than\b|, not the\b", words)), 1)


if __name__ == "__main__":
    unittest.main()
