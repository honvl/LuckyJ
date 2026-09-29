#!/usr/bin/env python3
"""How often an open caller is tenpai, by their discards, their calls and their run of drawn-and-thrown tiles.

Every seat with at least one chi, pon or open kan is read once after each of their own discards, while
nobody is in riichi: how many tiles they have discarded (their turn number, the same count as the
replays and ``tenhou_replay``), how many open calls they have, and how many of their latest discards in
a row were the tile they had just drawn (tsumogiri), counted since their last call. The truth is the
caller's real hand after that discard: tenpai, and tenpai with a yaku on at least one wait, which is a
hand that can win off a discard.

Each reading also keeps the caller's discards since their last call, as a pattern of ``H`` (from hand)
and ``T`` (tsumogiri) with one letter per tile for its kind: ``v`` a value honor for the caller, ``g``
a guest wind, ``t`` a terminal, ``e`` a 2 or 8, ``m`` a 3 to 7. ``patterns`` compares the readings
that share a pattern (a hand discard right after a run from the wall, runs of honors and terminals
only, hand and wall discards taking turns) with what the grid predicts for their squares, and compares
ways of counting the run by how well a grid fitted with each predicts the real hands; ``--opponents``
leaves out the hero's own readings.

``surface`` pools the rows and fits, for each calls-and-run row of the grid, a logistic curve over the
discard number the way the book's safe-tile section fits its rates (``fit_series`` in
``scripts/mine_safe_tile_timing.py``: a natural cubic spline, one to three degrees of freedom chosen by
AIC, fitted where each discard has enough readings). It writes the grid as JSON.

usage: mine_caller_surface.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_caller_surface.py surface OUT.json ROWS.json [ROWS.json ...]
       mine_caller_surface.py patterns OUT.json GRID.json ROWS.json [ROWS.json ...] [--opponents]
"""

from __future__ import annotations

import datetime
import json
import math
import os
import re
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


HONORS_AND_TERMINALS = set("vgt")
GUESTS_AND_TERMINALS = set("gt")


def _run_kinds(row: list) -> str:
    return row[7][len(row[7]) - row[2]:] if row[2] else ""


# a reading's discards since the call are row[6] (H from hand, T from the wall) and their kinds row[7]
PATTERNS = {
    "call": ("the discard right after the call", lambda r: r[6] == ""),
    "hand_after_hand": ("from hand, after another from hand or the call's own discard",
                        lambda r: r[2] == 0 and (r[6] == "H" or r[6].endswith("HH"))),
    "hand_after_one": ("from hand, after exactly one from the wall", lambda r: r[2] == 0 and re.search(r"(^|H)TH$", r[6])),
    "hand_after_two": ("from hand, after exactly two from the wall", lambda r: r[2] == 0 and re.search(r"(^|H)TTH$", r[6])),
    "hand_after_three": ("from hand, after three or more from the wall", lambda r: r[2] == 0 and r[6].endswith("TTTH")),
    "alternating_hand": ("the last four alternated, the last from hand", lambda r: r[6].endswith("THTH")),
    "alternating_wall": ("the last four alternated, the last from the wall", lambda r: r[6].endswith("HTHT")),
    "one_value_honor": ("one from the wall, a value honor", lambda r: r[2] == 1 and r[7][-1] == "v"),
    "one_guest_wind": ("one from the wall, a guest wind", lambda r: r[2] == 1 and r[7][-1] == "g"),
    "one_terminal": ("one from the wall, a terminal", lambda r: r[2] == 1 and r[7][-1] == "t"),
    "one_two_or_eight": ("one from the wall, a 2 or 8", lambda r: r[2] == 1 and r[7][-1] == "e"),
    "one_middle": ("one from the wall, a 3 to 7", lambda r: r[2] == 1 and r[7][-1] == "m"),
    "two_honors_terminals": ("two from the wall, both honors or terminals",
                             lambda r: r[2] == 2 and set(_run_kinds(r)) <= HONORS_AND_TERMINALS),
    "two_with_number": ("two from the wall, with a 2 to 8", lambda r: r[2] == 2 and not set(_run_kinds(r)) <= HONORS_AND_TERMINALS),
    "three_honors_terminals": ("three or more from the wall, all honors or terminals",
                               lambda r: r[2] >= 3 and set(_run_kinds(r)) <= HONORS_AND_TERMINALS),
    "three_guests_terminals": ("three or more from the wall, all guest winds or terminals",
                               lambda r: r[2] >= 3 and set(_run_kinds(r)) <= GUESTS_AND_TERMINALS),
    "three_with_number": ("three or more from the wall, with a 2 to 8",
                          lambda r: r[2] >= 3 and not set(_run_kinds(r)) <= HONORS_AND_TERMINALS),
}


def _skip_guests_and_terminals(r: list) -> int:
    run = 0
    for how, kind in zip(reversed(r[6]), reversed(r[7])):
        if how == "H":
            break
        run += kind not in GUESTS_AND_TERMINALS
    return run


def _call_as_wall(r: list) -> int:
    return len(r[6]) + 1 if "H" not in r[6] else r[2]


# ways to count the run, compared by how well a grid fitted with each predicts the real hands
COUNTS = {
    "grid": ("every tile from the wall since the last call, in a row (the grid)", lambda r: r[2]),
    "skip_guests_terminals": ("the same, passing over guest winds and terminals", _skip_guests_and_terminals),
    "last_four": ("tiles from the wall among the last four since the call", lambda r: r[6][-4:].count("T")),
    "call_as_wall": ("the call itself counted as one tile from the wall", _call_as_wall),
    "call_and_streak": ("that, and a hand discard ending three or more from the wall read as one",
                        lambda r: 1 if r[2] == 0 and r[6].endswith("TTTH") else _call_as_wall(r)),
}


def tile_kind(tile: int, value_honors: set[int]) -> str:
    """One letter for a discarded tile: value honor, guest wind, terminal, 2 or 8, or 3 to 7."""
    import tenhou_replay as tr

    b = tr.base(tile)
    if b >= 41:
        return "v" if b in value_honors else "g"
    return "t" if b % 10 in (1, 9) else "e" if b % 10 in (2, 8) else "m"


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
        since = ["", "", "", ""]
        kinds = ["", "", "", ""]
        for e in game["events"]:
            s = e["seat"]
            discards[s] += 1
            if e["called"] is not None:
                run[s] = 0
                since[s] = kinds[s] = ""
            else:
                run[s] = run[s] + 1 if e["tsumogiri"] else 0
                since[s] += "T" if e["tsumogiri"] else "H"
                kinds[s] += tile_kind(e["tile"], tr.yakuhai_for(s, game["kyoku"]))
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
            rows.append([discards[s], calls, run[s], int(tenpai), int(can_win), int(s == g["hero_seat"]), since[s], kinds[s]])
    return rows


def compute(manifest: str, since: str | None, out: str) -> None:
    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    with Pool(8) as pool:
        rows = [r for chunk in pool.map(_work, games, chunksize=4) for r in chunk]
    fields = ["discards", "calls", "run", "tenpai", "can_win", "hero", "since_call", "since_call_kinds"]
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "fields": fields, "rows": rows}))
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


def _log_likelihood(rows: list, count) -> tuple[float, int]:
    total, params = 0.0, 0
    for c in CALLS:
        for r in RUNS:
            sel = [x for x in rows if calls_bucket(x[1]) == c and run_bucket(count(x)) == r]
            if not sel:
                continue
            fit = fit_row(sel, 4)
            params += fit["fit"]["df"] + 1 if fit["fit"] else 0
            for x in sel:
                cell = fit["cells"][x[0]]
                p = cell.get("fit", cell["raw"])
                p = min(max(p / 100, 1e-4), 1 - 1e-4)
                total += math.log(p if x[4] else 1 - p)
    return total, params


def patterns(grid_file: str, files: list[str], opponents: bool = False) -> dict:
    """Each pattern's readings against the grid: the share who could win and what their own squares say, and,
    where all four run rows can be read at the same squares, what each row says."""
    import build_caller_surface as build

    grid = json.loads(Path(grid_file).read_text())
    rows = [r for f in files for r in json.loads(Path(f).read_text())["rows"] if r[0] <= MAX_DISCARD and not (opponents and r[5])]

    def square(d: int, calls: int, run: int) -> float | None:
        v = build.value(grid["grid"]["can_win"][f"{calls_bucket(calls)}-{run_bucket(run)}"]["cells"][str(d)], grid["min_readings"])
        return None if v is None else v / 100

    result = {"readings": len(rows), "patterns": {}, "counts": {}}
    for key, (label, select) in PATTERNS.items():
        chosen = [r for r in rows if select(r)]
        own = [(r[4], square(r[0], r[1], r[2])) for r in chosen]
        own = [(w, e) for w, e in own if e is not None]
        both = [(r[4], [square(r[0], r[1], run) for run in RUNS]) for r in chosen]
        both = [(w, e) for w, e in both if None not in e]
        result["patterns"][key] = {
            "label": label,
            "own": {"n": len(own), "could_win": round(100 * sum(w for w, _ in own) / len(own), 1),
                    "square": round(100 * sum(e for _, e in own) / len(own), 1)},
            "rows": {"n": len(both), "could_win": round(100 * sum(w for w, _ in both) / len(both), 1),
                     "by_run": [round(100 * sum(e[i] for _, e in both) / len(both), 1) for i in range(len(RUNS))]},
        }
    runs3 = [r for r in rows if r[2] >= 3]
    result["three_or_more_all_honors_terminals"] = round(100 * sum(1 for r in runs3 if set(_run_kinds(r)) <= HONORS_AND_TERMINALS) / len(runs3), 1)
    for key, (label, count) in COUNTS.items():
        ll, k = _log_likelihood(rows, count)
        result["counts"][key] = {"label": label, "log_likelihood": round(ll, 1), "parameters": k}
    return result


def report_patterns(out: str, grid_file: str, files: list[str], opponents: bool = False) -> None:
    result = patterns(grid_file, files, opponents)
    Path(out).write_text(json.dumps(result, indent=1))
    print(f"{out}: {result['readings']} readings")
    for key, p in result["patterns"].items():
        own, both = p["own"], p["rows"]
        print(f"  {p['label']:<62} {own['n']:6d}  could win {own['could_win']:5.1f}%, its squares {own['square']:5.1f}%"
              f"   | {both['n']:6d}  {both['could_win']:5.1f}% vs rows " + " ".join(f"{v:5.1f}" for v in both["by_run"]))
    print(f"  runs of three or more made only of honors and terminals: {result['three_or_more_all_honors_terminals']}%")
    grid_ll = result["counts"]["grid"]["log_likelihood"]
    for key, c in result["counts"].items():
        print(f"  {c['label']:<75} log-likelihood {c['log_likelihood']:10.1f} ({c['log_likelihood'] - grid_ll:+7.1f}), {c['parameters']} parameters")


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
    elif sys.argv[1] == "patterns":
        report_patterns(sys.argv[2], sys.argv[3], [f for f in sys.argv[4:] if f != "--opponents"], "--opponents" in sys.argv)
    else:
        surface(sys.argv[2], sys.argv[3:])
