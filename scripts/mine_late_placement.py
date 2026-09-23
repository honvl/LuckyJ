#!/usr/bin/env python3
"""Late hands (South 3 and later): the player's place going in and what the hand did to it.

For every hand from South 3 on, the place at the start of the hand (score order, ties to the
seat closer to the first dealer) is compared with the place at its end, and the hand is marked
won, dealt in, and riichi. The game's final hand is also reported alone, since that is where a
deal-in can turn a third into a fourth with no hand left to recover.

usage: mine_late_placement.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_late_placement.py report LABEL ROWS.json [ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FIRST_LATE_KYOKU = 6  # South 3


def place(scores: list, seat: int) -> int:
    """Place by score; ties go to the seat closer to the first dealer (seat 0)."""
    order = sorted(range(4), key=lambda s: (-scores[s], s))
    return order.index(seat) + 1


def compute(manifest: str, since: str | None, out: str) -> None:
    import tenhou_replay as tr

    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    rows = []
    for g in games:
        hero = g["hero_seat"]
        logs = tr.load_logs(g["file"])
        for i, log in enumerate(logs):
            if log[0][0] < FIRST_LATE_KYOKU:
                continue
            start = log[1]
            deltas = tr.result_deltas(log[-1])
            end = [start[s] + deltas[s] for s in range(4)]
            blocks = tr.result_blocks(log[-1])
            loser = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            game = tr.replay(log)
            rows.append(dict(game=g["uuid"], final=i == len(logs) - 1, before=place(start, hero), after=place(end, hero),
                             won=any(d[0] == hero for _, d in blocks), dealt=hero in loser,
                             riichi=game["players"][hero]["riichi_event"] is not None))
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} late hands")


def report(label: str, files: list[str]) -> None:
    rows, games = [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; games += d["games"]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    print(f"== {label}: {games} games, {len(rows)} hands from South 3 on")
    for p in (1, 2, 3, 4):
        rs = [r for r in rows if r["before"] == p]
        print(f"   place {p} going in: n {len(rs):5d}  won {pct(sum(r['won'] for r in rs), len(rs))}  dealt in {pct(sum(r['dealt'] for r in rs), len(rs))}"
              f"  riichi {pct(sum(r['riichi'] for r in rs), len(rs))}  dropped a place {pct(sum(r['after'] > p for r in rs), len(rs))}"
              f"  dropped through own deal-in {pct(sum(r['after'] > p and r['dealt'] for r in rs), len(rs))}  climbed {pct(sum(r['after'] < p for r in rs), len(rs))}")
    final = [r for r in rows if r["final"]]
    print(f"-- the game's final hand: {len(final)}")
    for p in (1, 2, 3, 4):
        rs = [r for r in final if r["before"] == p]
        print(f"   place {p} going in: n {len(rs):5d}  finished fourth {pct(sum(r['after'] == 4 for r in rs), len(rs))}  dealt in {pct(sum(r['dealt'] for r in rs), len(rs))}"
              f"  riichi {pct(sum(r['riichi'] for r in rs), len(rs))}  dropped through own deal-in {pct(sum(r['after'] > p and r['dealt'] for r in rs), len(rs))}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        report(sys.argv[2], sys.argv[3:])
