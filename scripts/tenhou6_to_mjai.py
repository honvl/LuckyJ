#!/usr/bin/env python3
"""Convert a tenhou.net/6 game (such as the tensoul output of a Mahjong Soul game) to mjai events.

The Mortal policy (libriichi's Bot) reads mjai. The conversion is the one behind the site's replays:
``build_replays.build_hands`` linearises every hand (searching the readings of an ambiguous call token) and checks
it, and ``build_replays.mjai_events`` writes the events, so the guide's Mortal review and replay.html see the same
game.

    .venv/bin/python scripts/tenhou6_to_mjai.py GAME.json OUT.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_replays  # noqa: E402


def convert(game: dict, names: list[str] | None = None) -> list[dict]:
    hands = build_replays.build_hands(game)
    events = [ev for _, _, ev in build_replays.mjai_events({"hands": hands})]
    events[0] = {"type": "start_game", "names": names or game.get("name", ["A", "B", "C", "D"]), "kyoku_first": 0,
                 "aka_flag": True}
    return events


if __name__ == "__main__":
    game = json.load(open(sys.argv[1]))
    with open(sys.argv[2], "w") as f:
        for ev in convert(game):
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
