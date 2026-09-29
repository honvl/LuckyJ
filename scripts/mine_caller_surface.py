#!/usr/bin/env python3
"""How often an open caller is tenpai, by their discards, their calls and their run of drawn-and-thrown tiles.

Every seat with at least one chi, pon or open kan is read once after each of their own discards, while
nobody is in riichi: how many tiles they have discarded (their turn number, the same count as the
replays and ``tenhou_replay``), how many open calls they have, and how many of their latest discards in
a row were the tile they had just drawn (tsumogiri), counted since their last call. The truth is the
caller's real hand after that discard: tenpai, and tenpai with a yaku on at least one wait, which is a
hand that can win off a discard.

``surface`` pools the rows and fits, for each calls-and-run row of the grid, a logistic curve over the
discard number the way the book's safe-tile section fits its rates (``fit_series`` in
``scripts/mine_safe_tile_timing.py``: a natural cubic spline, one to three degrees of freedom chosen by
AIC, fitted where each discard has enough readings). It writes the grid as JSON.

usage: mine_caller_surface.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_caller_surface.py surface OUT.json ROWS.json [ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MAX_DISCARD = 18
RUNS = (0, 1, 2, 3)  # 3 means three or more
CALLS = (1, 2, 3)  # 3 means three or four
MIN_READINGS = 40  # a discard needs this many readings to join a row's fit


def run_bucket(run: int) -> int:
    return min(run, 3)


def calls_bucket(calls: int) -> int:
    return min(calls, 3)


def _work(g: dict) -> list:
    import review_win_speed as ws
    import tenhou_replay as tr
    from mine_open_tenpai_push import ron_value

    rows = []
    for log in tr.load_logs(g["file"]):
        game = tr.replay(log)
        dset = frozenset(ws.dora_from_indicator(t) for t in game["dora_indicators"][:1])
        discards = [0, 0, 0, 0]
        run = [0, 0, 0, 0]
        for e in game["events"]:
            s = e["seat"]
            discards[s] += 1
            if e["called"] is not None:
                run[s] = 0
            elif e["tsumogiri"]:
                run[s] += 1
            else:
                run[s] = 0
            if any(v is not None and v <= e["index"] for v in e["riichi_seats"].values()) or e["riichi"]:
                continue
            melds = game["players"][s]["melds"][: len(e["melds"])]
            calls = sum(1 for m in melds if m["kind"] != "a")
            if not calls or discards[s] > MAX_DISCARD:
                continue
            tenpai = ws.hand_shanten(e["hand_after"], e["meld_tiles"], False) == 0
            can_win = False
            if tenpai:
                for w in tr.waits(e["hand_after"], e["meld_tiles"], False):
                    if ron_value(e["hand_after"], melds, w, s, game["kyoku"], dset):
                        can_win = True
                        break
            rows.append([discards[s], calls, run[s], int(tenpai), int(can_win), int(s == g["hero_seat"])])
    return rows


def compute(manifest: str, since: str | None, out: str) -> None:
    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    with Pool(8) as pool:
        rows = [r for chunk in pool.map(_work, games, chunksize=4) for r in chunk]
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "fields": ["discards", "calls", "run", "tenpai", "can_win", "hero"], "rows": rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} caller readings")


def fit_row(rows: list, truth: int) -> dict:
    """One grid row: per discard, the readings, the raw rate and the fitted rate with its 95% band."""
    import mine_safe_tile_timing as timing

    points = []
    for d in range(1, MAX_DISCARD + 1):
        c = [r for r in rows if r[0] == d]
        points.append({"turn": d, "lj_k": sum(r[truth] for r in c), "lj_n": len(c), "naga_k": 0, "naga_n": 0})
    span = timing._longest_run(list(range(1, MAX_DISCARD + 1)), {p["turn"]: p["lj_n"] for p in points}, MIN_READINGS)
    cells = {p["turn"]: {"n": p["lj_n"], "raw": round(100 * p["lj_k"] / p["lj_n"], 1) if p["lj_n"] else None} for p in points}
    fit_info = None
    if span and span[1] - span[0] >= 3:
        fit = timing.fit_series(points, "lj", span[0], span[1])
        fit_info = {"range": list(span), "df": fit["df"], "crossings_50": fit["crossings_50"]}
        for t, p, lo, hi in fit["grid"]:
            if abs(t - round(t)) < 1e-6:
                cells[int(round(t))].update({"fit": p, "lo": lo, "hi": hi})
    return {"cells": cells, "fit": fit_info}


def surface(out: str, files: list[str]) -> None:
    rows, games = [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]
        games += d["games"]
    grid = {}
    for truth, key in ((3, "tenpai"), (4, "can_win")):
        grid[key] = {}
        for c in CALLS:
            for r in RUNS:
                sel = [x for x in rows if calls_bucket(x[1]) == c and run_bucket(x[2]) == r]
                grid[key][f"{c}-{r}"] = fit_row(sel, truth)
    result = {"games": games, "readings": len(rows), "min_readings": MIN_READINGS,
              "definition": "a caller read once after each of their own discards while nobody is in riichi; rows are calls (1, 2, 3+) and the run of tsumogiri since their last call (0, 1, 2, 3+)",
              "grid": grid}
    Path(out).write_text(json.dumps(result, indent=1))
    print(f"{out}: {games} games, {len(rows)} readings")
    for key in ("tenpai", "can_win"):
        print(f"== {key}")
        for c in CALLS:
            for r in RUNS:
                cells = grid[key][f"{c}-{r}"]["cells"]
                line = " ".join(f"{cells[d].get('fit', cells[d]['raw'] if cells[d]['n'] >= MIN_READINGS else float('nan')):4.0f}" for d in range(1, MAX_DISCARD + 1))
                print(f"  {c} call{'s' if c > 1 else ' '} run {r}{'+' if r == 3 else ' '}: {line}   n {sum(v['n'] for v in cells.values())}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        surface(sys.argv[2], sys.argv[3:])
