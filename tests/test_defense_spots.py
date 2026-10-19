"""Chapter 46 of the personal guide: why Mortal threw the 1p and the 2s.

Every figure the chapter cites comes from ``analysis/defense-spots-2026-10-19.json`` (``scripts/mine_defense_spots.py``).
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
DATA = json.loads((ROOT / "analysis" / "defense-spots-2026-10-19.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="count-copies">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


def by_tile(spot: dict) -> dict:
    return {c["tile"]: c for c in spot["candidates"]}


class TheOnePinTests(unittest.TestCase):
    def test_the_hand_and_the_riichi(self):
        s = DATA["one_pin"]
        self.assertEqual((s["round"], s["turn"], s["thrown"], s["riichi_seats"]), ("South 3-1", 15, "6m", [2]))
        self.assertEqual(s["riichi"]["2"]["wait"], ["3m", "6m"])
        self.assertEqual(s["hand"], ["6m", "6m", "1p", "1p", "1p", "5p", "5p", "6p", "6p", "6p", "3s", "3s", "4s", "6s"])

    def test_the_count_of_copies_and_ways(self):
        c = by_tile(DATA["one_pin"])
        self.assertEqual([(t, c[t]["copies_seen"], c[t]["total_ways"]) for t in ("1p", "5p", "3s", "4s", "6m", "6p", "6s")],
                         [("1p", 4, 3), ("5p", 2, 11), ("3s", 2, 13), ("4s", 2, 13), ("6m", 2, 15), ("6p", 3, 17), ("6s", 1, 18)])
        self.assertEqual(c["1p"]["ways"], [{"two-sided": 3, "closed": 0, "edge": 0, "pair": 0, "single": 0}])
        self.assertEqual(c["6m"]["ways"], [{"two-sided": 8, "closed": 4, "edge": 0, "pair": 1, "single": 2}])
        self.assertEqual([t for t, x in c.items() if x["winning_tile"]], ["6m"])
        self.assertEqual([c[t]["labels"][0] for t in ("1p", "5p", "3s", "4s", "6m", "6p", "6s")],
                         ["live terminal", "half suji", "live 2-3-7-8", "half suji", "live 4-5-6", "half suji", "half suji"])
        self.assertEqual(DATA["one_pin"]["candidates"][0]["tile"], "1p")  # the fewest ways is the tile Mortal throws

    def test_mortal_with_and_without_the_riichi(self):
        m = DATA["one_pin"]["mortal"]
        self.assertEqual(m["the riichi, as played"][:2], [["1p", 0.996], ["5p", 0.003]])
        self.assertEqual((m["no riichi"][0], m["no riichi"][2]), (["6s", 0.925], ["1p", 0.011]))

    def test_every_discard_leaves_one_shanten(self):
        # checked by hand for the chapter: the 1p breaks a triplet and leaves the hand 1-shanten like the 6m
        import json as _json
        import tenhou_replay as tr
        import review_win_speed as ws
        from tenhou_replay import base

        path = next((ROOT / "data/self_games/majsoul").glob("261017-c062d7a5-*.json"))
        meta = next(g for g in _json.loads((ROOT / "data/self_games/majsoul/index.json").read_text()) if g["file"].endswith(path.name))
        for log in tr.load_logs(str(path)):
            game = tr.replay(log)
            if game["round_name"] != "South 3-1":
                continue
            e = [x for x in game["events"] if x["seat"] == meta["hero_seat"] and x.get("tile") is not None][-1]
            hb = e["hand_before"]
            for t in {base(x) for x in hb}:
                k = next(i for i, x in enumerate(hb) if base(x) == t)
                self.assertEqual(ws.hand_shanten(hb[:k] + hb[k + 1:], e["meld_tiles"], e["closed"]), 1, t)


class TheSevenPinTests(unittest.TestCase):
    def test_all_four_copies_of_the_7p_and_the_n_are_in_view(self):
        s = DATA["seven_pin"]
        self.assertEqual((s["round"], s["turn"], s["thrown"]), ("South 2-0", 15, "7s"))
        self.assertEqual((s["copies_seen"]["7p"], s["copies_seen"]["N"], s["copies_seen"]["7s"]), (4, 4, 1))
        self.assertEqual(s["mortal"][:2], [["7p", 0.818], ["N", 0.119]])


class TheTwoSouTests(unittest.TestCase):
    def test_the_board(self):
        s = DATA["two_sou"]
        self.assertEqual((s["round"], s["turn"], s["thrown"], s["riichi_seats"]), ("South 1-1", 8, "9m", [0, 3]))
        self.assertEqual((s["riichi"]["0"]["wait"], s["riichi"]["3"]["wait"]), (["4s"], ["6m", "9m"]))
        self.assertEqual(s["hand"], ["4m", "5m", "7m", "7m", "9m", "3p", "4p", "2s", "3s", "6s", "6s"])

    def test_counting_prefers_the_9m_where_mortal_takes_the_2s(self):
        c = by_tile(DATA["two_sou"])
        self.assertEqual([(t, c[t]["total_ways"]) for t in ("9m", "3s", "3p", "2s")], [("9m", 24), ("3s", 25), ("3p", 31), ("2s", 34)])
        self.assertEqual([t for t, x in c.items() if x["winning_tile"]], ["9m"])
        self.assertEqual(c["3s"]["furiten_against"], [False, True])  # the right player had thrown a 3s

    def test_mortal_changes_with_the_board(self):
        m = DATA["two_sou"]["mortal"]
        self.assertEqual(m["both riichis, as played"][:3], [["2s", 0.923], ["9m", 0.051], ["3s", 0.022]])
        self.assertEqual(m["only the dealer (seat 0) in riichi"][0], ["9m", 0.999])
        self.assertEqual(m["only seat 3 in riichi"][0], ["3s", 0.984])
        self.assertEqual(m["no riichi"][0], ["9m", 0.974])
        self.assertEqual(m["seat 3 never threw the 3s on turn 3"][:2], [["9m", 0.981], ["3p", 0.006]])
        self.assertEqual(dict(map(tuple, m["seat 3 never threw the 3s on turn 3"]))["2s"], 0.004)
        self.assertEqual(m["the dealer declared on a 5s, not the 1s"][0], ["2s", 0.995])


class TheDeadTileTests(unittest.TestCase):
    def test_how_often_it_comes_up(self):
        d = DATA["dead_tiles"]
        self.assertEqual((d["games"]["you"], d["games"]["luckyj"]), (216, 1079))
        self.assertEqual([(d[g]["decisions"], d[g]["dead_no_genbutsu"], d[g]["threw_dead"]) for g in ("you", "jade_human", "luckyj", "tokujou_human")],
                         [(3295, 67, 18), (10410, 211, 71), (16224, 285, 126), (51145, 996, 342)])
        self.assertEqual([round(100 * d[g]["threw_dead"] / d[g]["dead_no_genbutsu"]) for g in ("you", "jade_human", "tokujou_human", "luckyj")], [27, 34, 34, 44])


class TheMinerTests(unittest.TestCase):
    def test_ways(self):
        from collections import Counter as C

        import mine_defense_spots as m

        vis = C({21: 4, 22: 3, 23: 1})  # all four 1p, three 2p and one 3p in view
        self.assertEqual(m.ways(21, vis, set()), {"two-sided": 3, "closed": 0, "edge": 0, "pair": 0, "single": 0})
        self.assertEqual(m.ways(21, vis, {24}), {"two-sided": 0, "closed": 0, "edge": 0, "pair": 0, "single": 0})  # a 4p the riichi player threw makes 2p-3p furiten
        self.assertEqual(m.ways(21, vis, {21}), {})  # genbutsu
        self.assertEqual(m.ways(45, C({45: 2}), set()), {"pair": 1, "single": 2})  # a haku with two in view


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("99.6%", "92.5%", "gives the 1.1%", "12,300", "1 3 is 3 ways", "has 15: 8 as a two-sided wait, 4 closed, 1 pair and 2 single", "11,600",
                       "81.8%", "11.9%", "67 of your 3,295", "285 of LuckyJ s 16,224", "18 times in 67 (27%)", "71 in 211 (34%)", "342 in 996 (34%)", "126 in 285 (44%)",
                       "92.3%", "5.1%", "2.2%", "99.9%", "98.4%", "97.4%", "98.1%", "0.4%", "99.5%", "fewest ways, 24", "with 25 and the", "with 34",
                       "2-shanten", "1-shanten", "16 October", "7 October", "3 October"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_the_turns(self):
        want = ["replay.html?g=261017-c062d7a5-938e-4e8f-8061-ca646da43a03&amp;r=South+3-1&amp;t=15",
                "replay.html?g=261008-6c28a9cb-7fd0-48ff-a4f0-18b3bcf51dde&amp;r=South+2-0&amp;t=15",
                "replay.html?g=261004-3d4685b3-96b5-421f-9f25-7f7459b95553&amp;r=South+1-1&amp;t=8"]
        for lang in PAGES:
            links = re.findall(r'href="(replay\.html\?[^"]+)"', section(lang))
            self.assertEqual(links, want)
            for link in links:
                self.assertTrue((ROOT / "site" / "replays" / f"{link.split('g=')[1].split('&')[0]}.json").exists(), link)

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))
        self.assertLessEqual(len(re.findall(r"\bnot [a-z ]+, it is\b|\bis not [a-z ]+\. It is\b", prose("en"))), 1)


if __name__ == "__main__":
    unittest.main()
