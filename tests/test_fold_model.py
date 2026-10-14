"""Chapter 41 of the personal guide: how LuckyJ picks the tile it folds with.

Every figure the chapter cites comes from ``analysis/fold-model-2026-10-13.json`` (``scripts/mine_fold_model.py``).
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
DATA = json.loads((ROOT / "analysis" / "fold-model-2026-10-13.json").read_text())
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}


def section(lang: str) -> str:
    page = PAGES[lang].read_text(encoding="utf-8")
    start = page.index('<section class="point" id="fold-read">')
    return page[start:page.index("</section>", start)]


def prose(lang: str) -> str:
    text = re.sub(r'href="[^"]*"', "", section(lang))
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(re.sub(r"&#\d+;", " ", text).split())


class TheFoldsTests(unittest.TestCase):
    def test_the_counts(self):
        self.assertEqual((DATA["candidates"], DATA["decisions"], DATA["games"]["jade"]), (858565, 108201, 199))

    def test_the_real_folds(self):
        real = {g: DATA["sides"][g]["real_folds"] for g in ("luckyj", "humans", "you")}
        self.assertEqual([(r["n"], r["hits"], r["thrown"]) for r in real.values()], [(547, 7, 1.28), (1857, 76, 4.09), (111, 3, 2.7)])
        self.assertEqual([r["random"] for r in real.values()], [8.29, 8.91, 9.34])

    def test_the_kinds(self):
        kinds = {g: DATA["sides"][g]["real_folds"]["kinds"] for g in ("luckyj", "humans", "you")}
        rows = ("suji", "honor, 2 seen", "live honor", "live terminal", "live 2-3-7-8")
        self.assertEqual([kinds["luckyj"][k] for k in rows], [[146, 0.0], [90, 0.0], [112, 1.8], [74, 2.7], [54, 3.7]])
        self.assertEqual([kinds["humans"][k] for k in rows], [[503, 3.0], [240, 1.2], [309, 1.9], [306, 6.2], [262, 7.6]])
        self.assertEqual([kinds["you"][k] for k in rows], [[29, 3.4], [15, 0.0], [18, 0.0], [15, 0.0], [11, 9.1]])
        # a suji in 27% of the real folds, LuckyJ's and the humans'
        self.assertEqual([round(100 * kinds[g]["suji"][0] / DATA["sides"][g]["real_folds"]["n"]) for g in ("luckyj", "humans")], [27, 27])

    def test_the_models(self):
        real = {g: DATA["sides"][g]["real_folds"] for g in ("luckyj", "humans", "you")}
        picks = lambda name: [real[g][f"{name} pick"] for g in real]
        self.assertEqual(picks("net"), [1.46, 3.72, 1.8])
        self.assertEqual(picks("gbm"), [1.65, 3.07, 1.8])
        self.assertEqual(picks("tabpfn"), [1.65, 3.07, 1.8])
        self.assertEqual(picks("checklist"), [1.98, 3.13, 1.8])
        self.assertEqual(real["humans"]["kind only pick"], 3.77)
        self.assertEqual((real["luckyj"]["gbm predicted"], real["humans"]["gbm predicted"], real["luckyj"]["tabpfn predicted"]), (4.0, 4.67, 3.88))
        self.assertEqual((DATA["auc"]["gbm"], DATA["auc"]["tabpfn"], DATA["auc"]["checklist"]), (0.646, 0.648, 0.607))
        # the checklist closes a third of the humans' gap to LuckyJ
        h, l = real["humans"], real["luckyj"]
        self.assertEqual(round(3 * (h["thrown"] - h["checklist pick"]) / (h["thrown"] - l["thrown"])), 1)

    def test_luckyjs_riichis_are_not_easier(self):
        by = DATA["tokujou_humans_by_riichi"]
        self.assertEqual((by["against LuckyJ"]["thrown"], by["against the others"]["thrown"]), (4.15, 4.66))

    def test_the_cues(self):
        c = DATA["cues"]
        honors = c["honors: copies seen besides yours"]
        self.assertEqual([honors[f"0 seen, {k}"][1] for k in ("dragon", "value wind", "guest wind")], [5.7, 4.8, 3.8])
        self.assertEqual(sum(honors[f"0 seen, {k}"][0] for k in ("dragon", "value wind", "guest wind")), 19133)
        self.assertEqual(sum(honors[f"1 seen, {k}"][0] for k in ("dragon", "value wind", "guest wind")), 25651)
        self.assertEqual(sorted(honors[f"1 seen, {k}"][1] for k in ("dragon", "value wind", "guest wind")), [2.8, 2.9, 3.5])
        self.assertEqual(sum(honors[f"2 seen, {k}"][0] for k in ("dragon", "value wind", "guest wind")), 13911)
        self.assertEqual(sorted(honors[f"2 seen, {k}"][1] for k in ("dragon", "value wind", "guest wind")), [0.6, 0.7, 0.9])
        suji = c["suji: copies seen besides yours"]
        self.assertEqual((suji["0"], suji["2"]), ([34955, 6.0], [12056, 2.7]))
        made = c["suji: rank, made by the declaration tile"]
        self.assertEqual([made[k] for k in ("2/8, declaration tile", "2/8", "3/7, declaration tile", "3/7", "1/9", "1/9, declaration tile")],
                         [[5657, 9.9], [21133, 4.3], [6367, 8.2], [31720, 5.0], [12933, 2.7], [2309, 1.3]])
        self.assertEqual(c["live terminal: the riichi threw a tile 1-2 ranks away early"], {"0": [68453, 9.7], "1": [13504, 3.6]})
        self.assertEqual(c["live 2-3-7-8: the riichi threw a tile 1-2 ranks away early"], {"0": [192865, 11.1], "1": [103720, 8.8]})

    def test_your_three_real_fold_deal_ins(self):
        mine = [r for r in DATA["your_deal_ins"] if r["real_fold"]]
        self.assertEqual([(r["game"][:6], r["round"], r["turn"], r["thrown"][0]) for r in mine],
                         [("260920", "East 4-0", 11, "7s"), ("261004", "East 3-1", 7, "8m"), ("261010", "South 3-2", 9, "6p")])
        self.assertEqual([r["thrown_rank"] for r in mine[:2]], [1, 1])
        last = mine[2]
        self.assertEqual((last["thrown"], last["safest"][:2], last["checklist"][:2]),
                         (["6p", "half suji", 12.5], ["Haku", "live honor"], ["Haku", "live honor"]))


class TheRealFoldTests(unittest.TestCase):
    def test_a_real_fold_leaves_the_hand_further_from_tenpai(self):
        import review_win_speed as ws

        # five pairs, a Haku and three loose sou: the Haku keeps seven pairs at 1-shanten, a 6p breaks a pair
        hand = [19, 19, 23, 23, 26, 26, 32, 32, 33, 37, 38, 39, 39, 45]
        best = min(ws.hand_shanten(hand[:k] + hand[k + 1:], [], True) for k in range(len(hand)))
        self.assertEqual(best, 1)
        self.assertEqual(ws.hand_shanten([t for t in hand if t != 45], [], True), 1)
        broke = list(hand)
        broke.remove(26)
        self.assertEqual(ws.hand_shanten(broke, [], True), 2)

    def test_ways_count_the_unseen_copies(self):
        import mine_fold_model as fm

        x = np.zeros((1, len(fm.FEATURES)), dtype=np.float32)
        # a live 3: the 1, 2, 4 and 5 all unseen, so 4 x 4 two-sided (4-5), 4 x 4 closed (2-4), 4 x 4 edge (1-2)
        x[0, fm.INDEX["rank 3"]] = 1
        for o in range(-2, 5):
            x[0, fm.INDEX[f"{o:+d} valid"]] = 1
        x[0, fm.INDEX["+0 visible"]] = 0
        w = fm.ways(x)
        self.assertEqual([float(w[s][0]) for s in fm.SHAPES], [16.0, 16.0, 16.0, 3.0, 3.0])
        x[0, fm.INDEX["+3 genbutsu"]] = 1  # the 6 is safe: the 4-5 wait is furiten
        self.assertEqual(float(fm.ways(x)["ryanmen"][0]), 0.0)


class TheChapterTests(unittest.TestCase):
    def test_the_prose_carries_the_figures(self):
        text = prose("en")
        for phrase in ("547 real folds", "7 times, 1.28%", "4.09% of the time in 1,857", "3 times in 111", "27%",
                       "3.0% of the time", "2.7% against 6.2%", "3.7% against 7.6%", "858,565 tiles", "3.07% and 3.72%",
                       "1.46% and 1.65%", "4.00% dangerous and TabPFN 3.88%", "4.67%", "4.15% against 4.66%", "10,156", "25,651", "13,911",
                       "34,955", "12,056", "9.9%", "21,133", "8.2%", "31,720", "12,933", "2,309", "13,504", "68,453", "103,720", "192,865", "3.13%", "3.77%", "1.98%",
                       "17 May 2023", "12.5%", "5.3%", "199 games", "1,255 Tenhou games", "108,201", "65%", "61%"):
            self.assertIn(phrase, text, phrase)

    def test_the_japanese_keeps_every_number(self):
        number = re.compile(r"\d[\d,]*(?:\.\d+)?")
        figures = lambda text: Counter(n.replace(",", "") for n in number.findall(text))
        missing = figures(prose("en")) - figures(prose("ja"))
        self.assertFalse(missing, dict(missing))

    def test_the_replay_links_open_your_turns(self):
        for lang in PAGES:
            links = re.findall(r'href="(replay\.html\?[^"]+)"', section(lang))
            self.assertEqual(links, ["replay.html?g=260920-a3b39b2d-e995-4229-9a27-dc46d5286ce7&amp;r=East+4-0&amp;t=11",
                                     "replay.html?g=261004-0919202e-3037-4472-a90c-73fadb4a4cf6&amp;r=East+3-1&amp;t=7",
                                     "replay.html?g=261010-165003cb-bf9c-49f9-ae39-ac95a879ae5c&amp;r=South+3-2&amp;t=9"])
            for link in links:
                self.assertTrue((ROOT / "site" / "replays" / f"{link.split('g=')[1].split('&')[0]}.json").exists(), link)

    def test_the_voice(self):
        for lang in PAGES:
            self.assertNotIn("&#8212;", section(lang))
            self.assertNotIn("—", section(lang))
        self.assertNotIn("Of course", section("en"))


if __name__ == "__main__":
    unittest.main()
