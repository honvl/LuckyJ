"""The site's own replays (site/replays/, scripts/build_replays.py, site/replay.js) hold together.

Each event stream must replay tile by tile, the scores must carry from hand to hand, every Mortal
decision must include the choice you made, and every "Replay this hand" link in the guide must land
on the turn its card discusses, with the tile the card says you cut.
"""

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_replays as br  # noqa: E402

SITE = ROOT / "site"
REPLAYS = SITE / "replays"
FIXTURES = ROOT / "tests" / "fixtures"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def games():
    index = load(REPLAYS / "index.json")
    return [(entry, load(REPLAYS / f"{entry['id']}.json")) for entry in index["games"]]


def fixture_hand(name):
    log = load(FIXTURES / f"{name}.json")["log"]
    return log[0] if isinstance(log[0][0], list) else log


def hero_turns(hand, hero):
    """Your turn number at each event, counted as replay.js and the guide count it."""
    turns, turn = [], 0
    for e in hand["ev"]:
        if e[1] == hero and ((e[0] == "t" and len(e) < 4) or e[0] in ("c", "p", "m")):
            turn += 1
        turns.append(turn)
    return turns


class ConverterTests(unittest.TestCase):
    def test_open_kan_turns_its_dora_after_the_discard(self):
        log = fixture_hand("daiminkan-hand")
        events = br.linearise(log)
        kan = next(i for i, e in enumerate(events) if e[0] == "m")
        self.assertEqual(events[kan][1:4], [0, 1, "P"])
        self.assertEqual(events[kan + 1][:2], ["t", 0])
        self.assertEqual(events[kan + 1][3], 1)  # the replacement draw
        self.assertEqual(events[kan + 2][:2], ["d", 0])
        self.assertEqual(events[kan + 3], ["dora", br.site_tile(log[2][1])])

    def test_pon_takes_the_tile_over_a_pending_chi(self):
        events = br.linearise(fixture_hand("pon-over-chi-hand"))
        calls = [e for e in events if e[0] in ("c", "p")]
        self.assertEqual(calls[0], ["p", 3, 0, "5m", ["5mr", "5m"]])
        self.assertEqual(calls[1][:4], ["c", 1, 0, "5m"])

    def test_ronned_declaration_puts_no_stick_down(self):
        log = fixture_hand("riichi_ronned-hand")
        events = br.linearise(log)
        end = br.hand_end(log, events)
        br.drop_ronned_declaration(events, end)
        self.assertIn(["r", 2], events)
        self.assertNotIn(["ra", 2], events)
        self.assertIn(["ra", 0], events)

    def test_point_text(self):
        self.assertEqual(br.points_text("30符3飜3900点∀"), "30 fu 3 han, 3,900 all")
        self.assertEqual(br.points_text("満貫2000-4000点"), "mangan, 2,000/4,000")
        self.assertEqual(br.points_text("跳満18000点"), "haneman, 18,000")

    def test_chi_kind(self):
        self.assertEqual(br.chi_kind("3m", ["4m", "5m"]), "chi-low")
        self.assertEqual(br.chi_kind("5pr", ["4p", "6p"]), "chi-mid")
        self.assertEqual(br.chi_kind("7s", ["5s", "6s"]), "chi-high")


class ReplayFileTests(unittest.TestCase):
    def test_index_lists_every_file(self):
        listed = {entry["id"] for entry in load(REPLAYS / "index.json")["games"]}
        files = {p.stem for p in REPLAYS.glob("*.json") if p.name != "index.json"}
        self.assertEqual(listed, files)
        self.assertGreater(len(files), 100)

    def test_opponents_are_unnamed(self):
        for entry, game in games():
            with self.subTest(game=entry["id"]):
                names = [p["name"] for p in game["players"]]
                self.assertEqual(names[game["hero"]], "Honver")
                self.assertEqual([n for s, n in enumerate(names) if s != game["hero"]], [None, None, None])

    def test_events_replay_tile_by_tile(self):
        # The same bookkeeping as replay.js's apply(): every tile that leaves a hand must be in it.
        for entry, game in games():
            for hand in game["hands"]:
                with self.subTest(game=entry["id"], hand=hand["round"]):
                    tiles = [Counter(h) for h in hand["haipai"]]
                    melds = [0, 0, 0, 0]

                    def take(seat, tile):
                        self.assertGreater(tiles[seat][tile], 0, f"{tile} not in seat {seat}'s hand")
                        tiles[seat][tile] -= 1

                    for e in hand["ev"]:
                        kind, seat = e[0], e[1]
                        if kind == "t":
                            tiles[seat][e[2]] += 1
                        elif kind == "d":
                            take(seat, e[2])
                        elif kind in ("c", "p", "m"):
                            for t in e[4]:
                                take(seat, t)
                            melds[seat] += 1
                        elif kind == "a":
                            for t in e[2]:
                                take(seat, t)
                            melds[seat] += 1
                        elif kind == "k":
                            take(seat, e[2])
                    for seat in range(4):
                        self.assertIn(sum(tiles[seat].values()) + 3 * melds[seat], (13, 14))

    def test_scores_carry_from_hand_to_hand(self):
        for entry, game in games():
            with self.subTest(game=entry["id"]):
                for a, b in zip(game["hands"], game["hands"][1:]):
                    self.assertEqual(a["after"], b["scores"], a["round"])
                # Riichi sticks left on the table at the end go to first place.
                last = game["hands"][-1]
                left = last["sticks"] + sum(1 for e in last["ev"] if e[0] == "ra")
                if last["end"]["kind"] == "win":
                    left = 0
                self.assertEqual(sum(game["final"]), sum(last["after"]) + 1000 * left)

    def test_decisions_include_your_choice(self):
        for entry, game in games():
            for hand in game["hands"]:
                for d in hand["ai"]:
                    with self.subTest(game=entry["id"], hand=hand["round"], event=d["i"]):
                        actions = [a for a, _ in d["p"]]
                        self.assertIn(d["you"], actions)
                        probs = [p for _, p in d["p"]]
                        self.assertEqual(probs, sorted(probs, reverse=True))
                        self.assertTrue(0 <= d["i"] < len(hand["ev"]))

    def test_index_counts_match_the_files(self):
        for entry, game in games():
            with self.subTest(game=entry["id"]):
                self.assertEqual(entry, br.summarise(game))

    def test_flag_threshold_matches_the_viewer(self):
        script = (SITE / "replay.js").read_text(encoding="utf-8")
        match = re.search(r"const FLAG_BELOW = ([0-9.]+);", script)
        self.assertEqual(float(match.group(1)), br.FLAG_BELOW)


class GuideLinkTests(unittest.TestCase):
    """Every guide card links to replay.html?g=<uuid>&r=<round>&t=<turn>, plus at=call for a call frame
    (site/honver.js replayHref)."""

    def test_guide_links_land_on_the_turn_they_discuss(self):
        guide = load(SITE / "honver-guide.json")
        for chapter, examples in guide["chapters"].items():
            for example in examples:
                path = REPLAYS / f"{example['game']['uuid']}.json"
                self.assertTrue(path.exists(), example["id"])
                game = load(path)
                hero = game["hero"]
                hand = next((h for h in game["hands"] if h["round"] == example["round"]), None)
                self.assertIsNotNone(hand, f"{example['id']}: no {example['round']}")
                turns = hero_turns(hand, hero)
                for frame in example["frames"]:
                    with self.subTest(example=example["id"], turn=frame["turn"]):
                        start = next(i for i, e in enumerate(hand["ev"])
                                     if turns[i] == frame["turn"] and e[1] == hero and e[0] in ("t", "c", "p", "m"))
                        start_kind = hand["ev"][start][0]
                        if frame["kind"] == "call":
                            self.assertIn(start_kind, ("c", "p", "m"))
                            self.assertEqual(hand["ev"][start][3].replace("r", ""), frame["you"]["tile"].replace("r", ""))
                            continue
                        # A turn opens on your draw, or on your call when the cut after it is the question.
                        self.assertIn(start_kind, ("t", "c", "p"))
                        cut = next(e for e in hand["ev"][start:] if e[0] == "d" and e[1] == hero)
                        self.assertEqual(cut[2], frame["you"]["tile"])

    def test_chapter_links_land_on_the_turn_they_name(self):
        """Links in the guide's prose: t= opens your turn (at=call on the discard you called), e= opens one
        event, and data-you is what you played there."""
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, urlsplit

        class Links(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.found = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "a" and attrs.get("href", "").startswith("replay.html?"):
                    self.found.append(attrs)

        parser = Links()
        parser.feed((SITE / "honver.html").read_text(encoding="utf-8"))
        self.assertGreater(len(parser.found), 20)
        for attrs in parser.found:
            href = attrs["href"]
            with self.subTest(href=href):
                q = {k: v[0] for k, v in parse_qs(urlsplit(href).query).items()}
                path = REPLAYS / f"{q['g']}.json"
                self.assertTrue(path.exists())
                game = load(path)
                hero = game["hero"]
                hand = next((h for h in game["hands"] if h["round"] == q["r"]), None)
                self.assertIsNotNone(hand)
                you = attrs.get("data-you")
                if "e" in q:
                    self.assertEqual(hand["ev"][int(q["e"])][0], "d")
                    continue
                if "t" not in q:
                    continue
                turns = hero_turns(hand, hero)
                start = next(i for i, e in enumerate(hand["ev"])
                             if turns[i] == int(q["t"]) and e[1] == hero and e[0] in ("t", "c", "p", "m"))
                if q.get("at") == "call":
                    self.assertIn(hand["ev"][start][0], ("c", "p", "m"))
                    if you:
                        self.assertEqual(hand["ev"][start][3].replace("r", ""), you)
                elif you:
                    cut = next(e for e in hand["ev"][start:] if e[0] == "d" and e[1] == hero)
                    self.assertEqual(cut[2], you)

    def test_guide_cards_link_to_the_replays(self):
        script = (SITE / "honver.js").read_text(encoding="utf-8")
        self.assertIn("replay.html?", script)
        self.assertNotIn("Open the game in Mahjong Soul", script)


if __name__ == "__main__":
    unittest.main()
