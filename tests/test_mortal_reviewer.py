"""The AI Tutor's Mortal follows the player's rank: the earlier policy model below Celestial, Mortal-S42 for a Celestial
(guide chapter 56: the earlier model's reward prices a fourth like Saint 3 and Houou, S42's counts only the average
place, as Celestial points do). Outside a tutor sandbox the project's model stays S42."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mortal_engines as me  # noqa: E402


def folder(ranks, stats=None):
    d = tempfile.mkdtemp()
    Path(d, "index.json").write_text(json.dumps([{"hero_name": "Tester"}]))
    games = [[f"g{i}", 100 * i, 100 * i + 50, 12, [[1, "Tester", r, 30000, 0], [2, "X", 10503, 25000, 0],
                                                   [3, "Y", 10502, 25000, 0], [4, "Z", 10501, 20000, 0]]]
             for i, r in enumerate(ranks)]
    Path(d, "amae-koromo-records.json").write_text(json.dumps(games))
    if stats:
        Path(d, "amae-koromo-stats.json").write_text(json.dumps({"player_stats": {"level": {"id": stats}}}))
    return d


class ReviewerTests(unittest.TestCase):
    def pick(self, d, **env):
        with mock.patch.dict(os.environ, {"MORTAL_TUTOR_GAMES": d, **env}, clear=False):
            if "MORTAL_REVIEWER" not in env:
                os.environ.pop("MORTAL_REVIEWER", None)
            with mock.patch.object(me, "TUTOR_GAMES", d):
                return me.tutor_rank(), me.reviewer()

    def test_below_celestial_gets_the_earlier_model(self):
        self.assertEqual(self.pick(folder([10701, 10503])), (10503, "policy"))  # the newest game decides
        self.assertEqual(self.pick(folder([10402])), (10402, "policy"))

    def test_a_celestial_gets_s42(self):
        self.assertEqual(self.pick(folder([10503, 10701])), (10701, "s42"))
        self.assertEqual(self.pick(folder([10503, 10705])), (10705, "s42"))

    def test_stats_when_there_are_no_records(self):
        d = folder([], stats=10502)
        self.assertEqual(self.pick(d), (10502, "policy"))

    def test_the_override(self):
        self.assertEqual(self.pick(folder([10503]), MORTAL_REVIEWER="s42")[1], "s42")
        self.assertEqual(self.pick(folder([10701]), MORTAL_REVIEWER="policy")[1], "policy")

    def test_outside_a_sandbox_the_model_is_s42(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MORTAL_TUTOR_GAMES", None)
            os.environ.pop("MORTAL_REVIEWER", None)
            with mock.patch.object(me.os.path, "isdir", lambda p: False):
                self.assertIsNone(me.tutor_rank())
                self.assertEqual(me.reviewer(), "s42")


if __name__ == "__main__":
    unittest.main()
