#!/usr/bin/env python3
"""The first open call with a half flush in reach: kept, completed, dropped, and what it paid.

For every hand with an open call, the 14 tiles at the first call (hand plus melds) are sorted into
the main suit plus honors. The flush is still possible only when every meld is in that suit or is
an honor meld. A hand counts as

- dropped: after the call and before anyone declared riichi, the player cut a main-suit tile while
  still holding a number tile of another suit (cuts under a riichi are defence and not counted);
- completed: at some turn after the call the hand held only main-suit tiles and honors;
- a flush win: the hand won with honitsu or chinitsu.

Hands are split by the dora and red fives among the 14 tiles at the call: none, all of them in the
main suit or honors (the flush keeps the dora), or at least one in another suit (the flush would
cost it).

usage: mine_flush_calls.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_flush_calls.py report LABEL ROWS.json [ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FLUSH = {"混一色", "清一色"}


def flush_count(tiles: list) -> tuple[int, int | None]:
    """Tiles that fit one suit plus honors, and that suit (1 man, 2 pin, 3 sou; None if all honors)."""
    from tenhou_replay import base, is_honor

    suits: dict[int, int] = {}
    for t in tiles:
        if not is_honor(t):
            suits[base(t) // 10] = suits.get(base(t) // 10, 0) + 1
    honors = sum(1 for t in tiles if is_honor(t))
    if not suits:
        return honors, None
    main = max(suits, key=lambda k: (suits[k], -k))
    return suits[main] + honors, main


def compute(manifest: str, since: str | None, out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from tenhou_replay import base, is_honor, is_red

    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    rows = []
    for g in games:
        hero = g["hero_seat"]
        for log in tr.load_logs(g["file"]):
            game = tr.replay(log)
            p = game["players"][hero]
            dset = frozenset(ws.dora_from_indicator(t) for t in game["dora_indicators"][:1])
            isd = lambda t: base(t) in dset or is_red(t)
            evs = [e for e in game["events"] if e["seat"] == hero]
            first = next((e for e in evs if e["called"] is not None and e["called"]["kind"] != "a"), None)
            if first is None:
                continue
            tiles = list(first["hand_before"]) + list(first["meld_tiles"])
            fc, main = flush_count(tiles)
            feasible = main is not None and all(is_honor(t) or base(t) // 10 == main for t in first["meld_tiles"])
            dropped = completed = False
            for e in evs:
                if e["index"] < first["index"]:
                    continue
                off = [t for t in e["hand_before"] if not is_honor(t) and base(t) // 10 != main]
                if not off:
                    completed = True
                if any(v is not None for q, v in e["riichi_seats"].items() if q != hero):
                    break
                t = e["tile"]
                if off and not is_honor(t) and base(t) // 10 == main:
                    dropped = True
            blocks = tr.result_blocks(log[-1])
            win = next((d for _, d in blocks if d[0] == hero), None)
            loser = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            delta = tr.result_deltas(log[-1])[hero]
            rows.append(dict(
                game=g["uuid"], round=game["round_name"], hd=sum(1 for t in p["haipai"] if isd(t)),
                dora=sum(1 for t in tiles if isd(t)), fc=fc, feasible=feasible,
                dora_fits=all(is_honor(t) or base(t) // 10 == main for t in tiles if isd(t)),
                turn=first["turn"], honor_call=is_honor(first["called"]["tile"]), dropped=dropped, completed=completed,
                won=win is not None, value=delta - 1000 * tr.riichi_sticks_paid(log)[hero] if win else 0,
                flush_win=win is not None and bool(FLUSH & set(ws.yaku_names(win))),
                dealt=hero in loser, cost=-delta if hero in loser else 0))
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} hands with an open call")


def report(label: str, files: list[str]) -> None:
    rows, games = [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; games += d["games"]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    mean = lambda xs: sum(xs) / len(xs) if xs else 0
    print(f"== {label}: {games} games, {len(rows)} hands with an open call; flush still possible after the first call")
    for dn, ds in (("dora at the call, all of it fits the flush", lambda r: r["dora"] >= 1 and r["dora_fits"]),
                   ("dora at the call, some in another suit", lambda r: r["dora"] >= 1 and not r["dora_fits"]),
                   ("no dora at the call", lambda r: r["dora"] == 0)):
        print(f"-- {dn}")
        for lo, hi in ((10, 10), (11, 14), (11, 11), (12, 14)):
            rs = [r for r in rows if r["feasible"] and ds(r) and lo <= r["fc"] <= hi]
            if not rs:
                continue
            fw = [r for r in rs if r["flush_win"]]
            other = [r for r in rs if r["won"] and not r["flush_win"]]
            print(f"   {lo}-{hi} of 14 tiles fit  n {len(rs):4d}  first call on turn {mean([r['turn'] for r in rs]):4.1f}"
                  f"  dropped {pct(sum(r['dropped'] for r in rs), len(rs))}"
                  f"  completed {pct(sum(r['completed'] for r in rs), len(rs))}  won {pct(sum(r['won'] for r in rs), len(rs))}"
                  f"  flush wins {pct(len(fw), len(rs))} (value {mean([r['value'] for r in fw]):6.0f})"
                  f"  other wins value {mean([r['value'] for r in other]):6.0f}  dealt in {pct(sum(r['dealt'] for r in rs), len(rs))}"
                  f"  net per hand {mean([r['value'] - r['cost'] for r in rs]):6.0f}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        report(sys.argv[2], sys.argv[3:])
