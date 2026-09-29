"""The book's example tables show each pond as it stood: a tile another player called keeps its place, marked."""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_point_examples as points  # noqa: E402

EXAMPLES = json.loads((ROOT / "site/point-examples.json").read_text(encoding="utf-8"))
SEATS = points.SEAT_NAMES


class PondTests(unittest.TestCase):
    # Seat 0 cuts 5m and seat 1 chis it, then seat 2 declares riichi on 1s and seat 3 pons it.
    KYOKU = [{"info": {"msg": msg}} for msg in (
        {"type": "start_kyoku"},
        {"type": "dahai", "actor": 0, "pai": "5m"},
        {"type": "chi", "actor": 1, "target": 0, "pai": "5m", "consumed": ["4m", "6m"]},
        {"type": "dahai", "actor": 1, "pai": "9p"},
        {"type": "reach", "actor": 2},
        {"type": "dahai", "actor": 2, "pai": "1s"},
        {"type": "reach_accepted", "actor": 2},
        {"type": "pon", "actor": 3, "target": 2, "pai": "1s", "consumed": ["1s", "1s"]},
    )]

    def test_a_call_marks_the_pond_tile_it_took(self):
        discards, called = points.ponds_before(self.KYOKU, len(self.KYOKU))
        self.assertEqual(discards, [["5m"], ["9p"], ["1s"], []])
        # the riichi tile is marked like any other
        self.assertEqual(called, [[0], [], [0], []])

    def test_the_tile_under_a_call_decision_is_still_live(self):
        # the frame of the chi stands before it
        self.assertEqual(points.ponds_before(self.KYOKU, 2), ([["5m"], [], [], []], [[], [], [], []]))


class ExampleTableTests(unittest.TestCase):
    def test_called_pond_tiles_match_the_calls(self):
        # Every tile called out of a pond is marked in that pond, and nothing else. A meld's called_from
        # is seen from its caller, so the pond sits that many seats on from the caller.
        for point, rows in EXAMPLES.items():
            for case in rows:
                players = case["table"]["players"]
                taken = {p["seat"]: [] for p in players}
                for caller in players:
                    for meld in caller["melds"]:
                        if meld["kind"] in ("chi", "pon", "daiminkan"):
                            source = SEATS[(SEATS.index(caller["seat"]) + SEATS.index(meld["called_from"])) % 4]
                            taken[source].append(meld["called_tile"])
                for player in players:
                    with self.subTest(point=point, game=case["game"], seat=player["seat"]):
                        marked = [player["discards"][i] for i in player["called_discard_indexes"]]
                        self.assertEqual(sorted(marked), sorted(taken[player["seat"]]))

    def test_a_call_decision_leaves_its_tile_in_the_pond(self):
        # The table stands before the call: the tile ends its pond, unmarked and in no meld yet.
        calls = [(point, case) for point, rows in EXAMPLES.items() for case in rows if case["kind"] == "call"]
        self.assertTrue(calls)
        for point, case in calls:
            source = next(p for p in case["table"]["players"] if p["seat"] == case["called_from"])
            with self.subTest(point=point, game=case["game"]):
                self.assertEqual(source["discards"][-1], case["called_tile"])
                self.assertNotIn(len(source["discards"]) - 1, source["called_discard_indexes"])

    def test_three_calls_mark_three_ponds(self):
        # Point 04, example 4: shimocha took toimen's 1m and kamicha's Chun, kamicha took shimocha's West,
        # and LuckyJ is deciding on shimocha's South.
        case = next(c for c in EXAMPLES["point-04"] if c["game"] == 210)
        players = {p["seat"]: p for p in case["table"]["players"]}
        marked = {seat: [p["discards"][i] for i in p["called_discard_indexes"]] for seat, p in players.items()}
        self.assertEqual(marked, {"self": [], "shimocha": ["W"], "toimen": ["1m"], "kamicha": ["C"]})
        self.assertEqual([(m["called_tile"], m["called_from"]) for m in players["shimocha"]["melds"]],
                         [("1m", "shimocha"), ("C", "toimen")])
        self.assertEqual((case["call"], case["called_tile"], players["shimocha"]["discards"][-1]), ("pon", "S", "S"))


if __name__ == "__main__":
    unittest.main()
