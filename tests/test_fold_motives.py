"""Chapter 22: what your extra folds follow. The page shows the data, and the figures the prose cites hold."""

import html
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_fold_motives_figure as figure  # noqa: E402
import mine_fold_motives as miner  # noqa: E402

DATA = json.loads(figure.DATA.read_text())
TESTS = DATA["tests"]["riichi"]


def chapter(page: str) -> str:
    text = page[page.index('<section class="point" id="own-hand">'):]
    return text[: text.index("</section>")]


def plain(fragment: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", fragment, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text)


def table_cells(fragment: str, index: int) -> list[list[str]]:
    body = re.findall(r"<tbody>(.*?)</tbody>", fragment, flags=re.S)[index]
    return [[re.sub(r"<[^>]+>", "", c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row)] for row in re.findall(r"<tr>(.*?)</tr>", body)]


def whole(v: float) -> int:
    """Half away from zero, as the prose rounds (Python's round() takes 74.5 to 74)."""
    return int(abs(v) + 0.5) * (1 if v >= 0 else -1)


round = whole  # noqa: A001  every rounding in these tests is the prose's


PAGES = {lang: chapter(path.read_text(encoding="utf-8")) for lang, path in figure.PAGES.items()}


class TurnTests(unittest.TestCase):
    def cand(self, b, sh, safe, uk=10):
        return {"b": b, "sh": sh, "uk": uk, "safe": safe}

    def row(self, cands, cut, best, **kw):
        base = {"g": "g", "li": 0, "t": 9, "nr": 1, "rd": False, "called": None, "bs": best, "hd": 0, "dl": False,
                "rdealer": False, "cands": cands, "cut": cut}
        return base | kw

    def test_a_costly_turn_against_a_riichi(self):
        # the live 5p keeps 1-shanten; the only safe tile (genbutsu 9s) goes back to 2-shanten
        cands = [self.cand(25, 1, 7), self.cand(39, 2, 0)]
        turn = miner.riichi_turn(self.row(cands, 39, 1))
        self.assertEqual((turn["hand"], turn["folded"], turn["safe"]), ("one", True, [39]))
        self.assertFalse(miner.riichi_turn(self.row(cands, 25, 1))["folded"])

    def test_free_and_open_turns_do_not_count(self):
        # a suji tile keeps the best hand: free, not costly
        self.assertIsNone(miner.riichi_turn(self.row([self.cand(25, 1, 7), self.cand(33, 1, 2)], 25, 1)))
        # no safe tile at all
        self.assertIsNone(miner.riichi_turn(self.row([self.cand(25, 1, 7), self.cand(26, 2, 6)], 25, 1)))
        # two riichi, a declaration, a turn that starts with a call
        cands = [self.cand(25, 1, 7), self.cand(39, 2, 0)]
        for kw in ({"nr": 2}, {"rd": True}, {"called": "pon"}):
            self.assertIsNone(miner.riichi_turn(self.row(cands, 39, 1, **kw)))

    def test_a_costly_turn_against_callers_takes_the_worst_danger(self):
        # 5m is genbutsu to one caller and live to the other: not safe; 9p is safe to both but costs the shanten
        rows = [{"g": "g", "li": 0, "t": 8, "prev_sh": 1, "best_sh": 1, "my_dora": 2, "me_dealer": False, "q_dealer": q == 1,
                 "tile": 29, "opts": [[15, d, 1, False], [29, 0, 2, False]]} for q, d in ((1, 0), (2, 3))]
        turn = miner.caller_turns(rows)
        self.assertEqual((turn["folded"], turn["safe"], turn["threat_dealer"], turn["dora"]), (True, [29], True, 2))
        rows[0]["prev_sh"] = None  # a turn that starts with a call
        self.assertIsNone(miner.caller_turns(rows))

    def test_mortal_is_read_at_your_draw(self):
        # the third example: Mortal's entry at your 13th turn is the draw decision, with the tile you threw
        g, li, t = miner.EXAMPLES[2]
        game = miner.replay(g)
        a = miner.decision(game["hands"][li], game["hero"], t)
        self.assertEqual(a["you"], "2p")
        self.assertEqual(a["p"][0][0], "3m")

    def test_the_numbers_join(self):
        self.assertEqual(DATA["joined"]["You"], [1273, 1274])
        self.assertEqual(DATA["joined"]["LuckyJ"], [10997, 10997])
        self.assertGreaterEqual(DATA["mortal_cut_match"]["You"], 99.9)
        self.assertEqual(DATA["mortal_cut_match"]["LuckyJ"], 100.0)
        self.assertEqual(DATA["games"], {"You": 123, "LuckyJ": 1079})


class FigureTests(unittest.TestCase):
    def test_the_pages_draw_the_data(self):
        for lang, path in figure.PAGES.items():
            with self.subTest(page=path.name):
                page = path.read_text(encoding="utf-8")
                start, end = page.index(figure.START), page.index(figure.END) + len(figure.END)
                self.assertEqual(page[start:end], figure.render(DATA, lang))
                self.assertIn(figure.START, PAGES[lang])

    def test_every_dot_is_on_the_scale(self):
        lo, hi = figure.SCALE
        for key in figure.TESTS:
            for who in ("You", "LuckyJ"):
                for side in ("a", "b"):
                    self.assertTrue(lo <= TESTS[key][who][side]["extra"] <= hi, (key, who, side))

    def test_whole_numbers_round_half_away_from_zero(self):
        self.assertEqual([figure.whole(v) for v in (7.5, -3.6, -0.1, 0.4, 11.3)], ["+8", "&#8722;4", "0", "0", "+11"])


class ProseTests(unittest.TestCase):
    def test_the_first_table(self):
        hands = ("tenpai", "one", "far")
        by = DATA["by_hand"]["riichi"]
        want = [[f'{by[h][who][key]:.1f}%' for h in hands] for who, key in (("You", "folded"), ("You", "mortal"), ("LuckyJ", "folded"), ("LuckyJ", "mortal"))]
        self.assertEqual(want, [["28.4%", "64.7%", "83.1%"], ["19.0%", "58.1%", "74.9%"], ["18.3%", "53.4%", "79.5%"], ["20.1%", "57.7%", "75.3%"]])
        for lang, text in PAGES.items():
            with self.subTest(page=lang):
                self.assertEqual([row[1:] for row in table_cells(text, 0)], want)

    def test_how_much(self):
        o = DATA["overall"]
        self.assertEqual((round(o["riichi"]["You"]["folded"]), round(o["riichi"]["You"]["mortal"]), whole(o["riichi"]["You"]["extra"])), (54, 46, 8))
        self.assertEqual(whole(o["riichi"]["LuckyJ"]["extra"]), -2)
        self.assertEqual((round(o["callers"]["You"]["folded"]), round(o["callers"]["You"]["mortal"])), (7, 5))
        en = plain(PAGES["en"])
        self.assertIn("you fold 54% of your costly turns where Mortal, on the same turns, folds 46%: about 8 extra folds in every 100", en)
        self.assertIn("LuckyJ folds 2 fewer than Mortal", en)
        self.assertIn("7% against Mortal’s 5%", en)
        # every distance from tenpai: the extra is at least 6 at each
        self.assertTrue(all(DATA["by_hand"]["riichi"][h]["You"]["extra"] > 6 for h in ("tenpai", "one", "far")))

    def test_not_fear_of_the_riichi(self):
        dealer, prev = TESTS["threat_dealer"], TESTS["prev_dealt"]
        self.assertEqual((whole(dealer["You"]["contrast"]), whole(dealer["LuckyJ"]["contrast"])), (2, 6))
        self.assertLess(dealer["You"]["contrast"], dealer["LuckyJ"]["contrast"])
        self.assertEqual((prev["You"]["a"]["turns"], whole(prev["LuckyJ"]["contrast"])), (41, 5))
        self.assertLess(abs(prev["You"]["contrast"]), 1)
        en = plain(PAGES["en"])
        self.assertIn("It adds 2 extra folds per 100 for you and 6 for LuckyJ", en)
        self.assertIn("LuckyJ folds 5 more. That split has only 41 of your turns", en)

    def test_the_round(self):
        south = TESTS["south"]
        self.assertEqual((whole(south["You"]["b"]["extra"]), whole(south["You"]["a"]["extra"])), (5, 11))
        self.assertEqual((whole(south["LuckyJ"]["b"]["extra"]), whole(south["LuckyJ"]["a"]["extra"])), (0, -4))
        r = DATA["riichi_or_dama"]
        cells = [round(r[who][rd][k]) for who in ("You", "LuckyJ") for rd in ("East", "South") for k in ("declared", "mortal")]
        self.assertEqual(cells[:4], [81, 75, 62, 64])
        self.assertGreater(r["LuckyJ"]["East"]["declared"], r["LuckyJ"]["East"]["mortal"])
        self.assertGreater(r["LuckyJ"]["South"]["declared"], r["LuckyJ"]["South"]["mortal"])
        # each gap against LuckyJ's is more than two standard errors
        self.assertGreater(south["difference"] / south["difference_se"], 2)
        self.assertLess(r["south_test"]["difference"] / r["south_test"]["difference_se"], -2)
        en = plain(PAGES["en"])
        self.assertIn("In the East you fold 5 extra times per 100, in the South 11", en)
        self.assertIn("from 0 to 4 fewer than Mortal", en)
        self.assertIn("declare 81% of your first closed tenpais, where Mortal on the same tenpais would declare 75%", en)
        self.assertIn("in the South you declare 62% against Mortal’s 64%", en)

    def test_your_own_hand(self):
        dora, seat = TESTS["dora"], TESTS["me_dealer"]
        self.assertEqual((whole(dora["You"]["b"]["extra"]), whole(dora["You"]["a"]["extra"])), (5, 11))
        self.assertTrue(all(abs(dora["LuckyJ"][s]["extra"]) < 3 for s in ("a", "b")))
        one = DATA["one_shanten"]
        pcts = lambda who, key: [round(one[who]["by_dora"][d][key]) for d in ("0", "1", "2+")]
        self.assertEqual((pcts("You", "folded"), pcts("LuckyJ", "folded"), pcts("You", "mortal")), ([65, 67, 63], [57, 57, 44], [61, 63, 53]))
        self.assertEqual(whole(seat["LuckyJ"]["contrast"]), -5)
        self.assertLess(abs(seat["You"]["contrast"]), 0.5)
        for test in (dora, seat):
            self.assertTrue(1 <= test["difference"] / test["difference_se"] <= 1.6)
        en = plain(PAGES["en"])
        self.assertIn("your extra folds rise from 5 to 11 per 100", en)
        self.assertIn("you fold it 65%, 67% and 63% of the time; LuckyJ 57%, 57% and 44%; Mortal on your own turns 61%, 63% and 53%", en)
        self.assertIn("As dealer, LuckyJ folds 5 fewer per 100", en)

    def test_before_the_reviews(self):
        b = DATA["before_after"]["riichi"]
        self.assertEqual((whole(b["before"]["extra"]), whole(b["since"]["extra"])), (11, 6))
        self.assertIn("11 extra folds per 100 before 20 September, 6 since", plain(PAGES["en"]))

    def test_the_rule_and_the_exception(self):
        two = DATA["one_shanten"]["LuckyJ"]["two_dora_by_turn"]
        self.assertEqual([round(two[b]["folded"]) for b in ("1-9", "10-12", "13+")], [33, 40, 60])
        fourth = DATA["south_by_rank"]
        for rd in ("East", "South"):
            self.assertLess(abs(fourth["You"]["4"][rd]["extra"] - fourth["LuckyJ"]["4"][rd]["extra"]), 3)
            self.assertGreater(fourth["LuckyJ"]["4"][rd]["extra"], 5)
        en = plain(PAGES["en"])
        self.assertIn("LuckyJ folds it 33% of the time up to its 9th turn and 40% on its 10th to 12th", en)
        self.assertIn("even with dora: LuckyJ 60%", en)

    def test_the_evidence_counts(self):
        o = DATA["overall"]
        counts = [o["riichi"]["You"]["turns"], o["callers"]["You"]["turns"], o["riichi"]["LuckyJ"]["turns"], o["callers"]["LuckyJ"]["turns"],
                  DATA["riichi_or_dama"]["You"]["all"]["tenpais"], DATA["riichi_or_dama"]["LuckyJ"]["all"]["tenpais"]]
        self.assertEqual(counts, [383, 890, 3565, 7432, 321, 2661])
        en = plain(PAGES["en"])
        for text in ("383 turns, and 890 against callers", "3,565 and 7,432 in its 1,079 Tokujou games", "321 yours, 2,661 LuckyJ’s", "99.9% of your turns"):
            self.assertIn(text, en)
        ja = plain(PAGES["ja"])
        for text in ("383巡目", "890巡目", "3,565と7,432", "あなたが321、LuckyJが2,661", "99.9%"):
            self.assertIn(text, ja)


class ExampleTests(unittest.TestCase):
    def test_the_examples_table(self):
        ex = DATA["examples"]
        self.assertEqual([(e["round"], e["t"], e["rank"], e["dealer"], e["riichi_from"], e["riichi_on_discard"]) for e in ex],
                         [("South 3-0", 4, 1, False, "toimen", 3), ("South 3-2", 7, 2, True, "toimen", 6), ("South 2-0", 13, 2, True, "toimen", 11)])
        self.assertEqual([(e["hand"], e["dora"], e["you_threw"], e["mortal_top"], round(e["mortal_top_weight"])) for e in ex],
                         [("one", 3, "8s", "3s", 89), ("one", 2, "3p", "9s", 79), ("tenpai", 2, "2p", "3m", 98)])
        gaps = [sorted(e["scores"], reverse=True) for e in ex]
        self.assertEqual([gaps[0][0] - gaps[0][1], gaps[1][1] - gaps[1][2], gaps[2][1] - gaps[2][2]], [16300, 1100, 7600])
        for lang, text in PAGES.items():
            with self.subTest(page=lang):
                cells = table_cells(text, 2)  # after the first table and the figure's own
                self.assertEqual([re.findall(r"\[\[(\w+)\]\]", row[2]) for row in cells], [["8s"], ["3p"], ["2p"]])
                self.assertEqual([re.findall(r"\[\[(\w+)\]\]", row[3]) for row in cells], [["3s"], ["9s"], ["3m"]])
                self.assertEqual([re.search(r"(\d+)%", row[3]).group(1) for row in cells], ["89", "79", "98"])

    def test_the_links_open_the_example_turns(self):
        for lang, text in PAGES.items():
            links = re.findall(r'href="replay\.html\?g=([^&]+)&amp;r=([^&]+)&amp;t=(\d+)"[^>]*data-you="(\w+)"', text)
            with self.subTest(page=lang):
                self.assertEqual([(g, int(t), you) for g, _, t, you in links],
                                 [(g, t, e["you_threw"]) for (g, _, t), e in zip(miner.EXAMPLES, DATA["examples"])])
                self.assertEqual([r.replace("+", " ") for _, r, _, _ in links], [e["round"] for e in DATA["examples"]])


class PageTests(unittest.TestCase):
    def test_kicker_notice_and_list(self):
        for lang, path in figure.PAGES.items():
            page = path.read_text(encoding="utf-8")
            with self.subTest(page=path.name):
                self.assertIn("Chapter twenty-two" if lang == "en" else "第22章", PAGES[lang])
                latest = page[page.index('<li class="is-latest">'):]
                latest = latest[: latest.index("</li>")]
                self.assertIn('href="#own-hand"', latest)
                self.assertIn('href="#own-hand"><span class="contents-num">22</span>', page)
                self.assertIn("honver.css?v=20260929-fold-motives", page)

    def test_voice_rules(self):
        for lang, text in PAGES.items():
            words = plain(text)
            with self.subTest(page=lang):
                self.assertNotRegex(words, r"[—–]")
                self.assertNotRegex(words, r"(?i)\bof course\b|もちろん|のである")
                self.assertNotRegex(words, r"\bis not [^.;:]{1,40}[.;] It(?:'s| is)\b")
                if lang == "ja":
                    self.assertLessEqual(len(re.findall(r"ではなく", words)), 1)


if __name__ == "__main__":
    unittest.main()
