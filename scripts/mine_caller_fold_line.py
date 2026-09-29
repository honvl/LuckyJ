#!/usr/bin/env python3
"""Where LuckyJ stops cutting live tiles against a caller, on the axes of chapter 18's caller grid.

Reads the cut rows that ``scripts/contrast/vs_callers.py`` writes for LuckyJ's Tokujou games and keeps
the main book's fold-line spots (its "Open callers" section): LuckyJ's own discards against a single
caller while nobody is in riichi, holding a safe tile (danger 1 or less) that keeps its best shanten. A
cut is live when its danger is 2 or more. From two-shanten or worse, the share of live cuts is fitted
over the caller's discards with ``fit_series`` (``scripts/mine_safe_tile_timing.py``), once against one
call and once against two or more, over the discards with at least 40 spots. The line is the first
discard whose fitted share is below half.

It also asks whether the caller's run of tiles from the wall moves that share: a logistic regression of
the live cut on the same kind of discard curve plus the run, for each block and for LuckyJ's own
shanten. Everything is written as JSON.

usage: mine_caller_fold_line.py CUTS.jsonl OUT.json
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mine_safe_tile_timing as timing  # noqa: E402

MAX_DISCARD = 18
MIN_SPOTS = 40  # a discard needs this many spots to join a block's fit, as in the grid
BLOCKS = {"1": (1,), "2+": (2, 3, 4)}
SHANTEN = {"far": lambda sh: sh >= 2, "one": lambda sh: sh == 1, "tenpai": lambda sh: sh == 0}


def honors_and_terminals(tiles: list[int]) -> bool:
    return all(t >= 41 or t % 10 in (1, 9) for t in tiles)


def load(path: str) -> list[dict]:
    spots = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["who"] != "LuckyJ" or r["n_callers"] != 1 or r["keep_safe"] > 1:
                continue
            if not 1 <= r["q_turn"] <= MAX_DISCARD:
                continue
            spots.append({"calls": r["n_melds"], "discard": r["q_turn"], "run": r["ts_run"], "run_tiles": r["run_tiles"],
                          "shanten": r["best_sh"], "live": int(r["danger"] >= 2)})
    return spots


def block_of(calls: int) -> str:
    return "1" if calls == 1 else "2+"


def fold_curve(spots: list[dict]) -> dict:
    points = []
    for d in range(1, MAX_DISCARD + 1):
        c = [s for s in spots if s["discard"] == d]
        points.append({"turn": d, "lj_k": sum(s["live"] for s in c), "lj_n": len(c), "naga_k": 0, "naga_n": 0})
    span = timing._longest_run(list(range(1, MAX_DISCARD + 1)), {p["turn"]: p["lj_n"] for p in points}, MIN_SPOTS)
    fit = timing.fit_series(points, "lj", span[0], span[1])
    cells = {p["turn"]: {"n": p["lj_n"], "raw": round(100 * p["lj_k"] / p["lj_n"], 1) if p["lj_n"] else None} for p in points}
    for t, p, lo, hi in fit["grid"]:
        if abs(t - round(t)) < 1e-6:
            cells[int(round(t))].update({"fit": p, "lo": lo, "hi": hi})
    down = [c["turn"] for c in fit["crossings_50"] if c["direction"] == "down"]
    line = math.ceil(down[0]) if down else None
    return {"spots": len(spots), "range": list(span), "df": fit["df"], "crossings_50": fit["crossings_50"], "line": line,
            "cells": cells}


def run_slope(spots: list[dict]) -> dict:
    """Log-odds change in the live cut per tile of the run, on top of a three-knot discard curve."""
    cells = defaultdict(lambda: [0, 0])
    for s in spots:
        key = (s["discard"], min(s["run"], 3))
        cells[key][0] += s["live"]
        cells[key][1] += 1
    keys = sorted(cells)
    lo, hi = min(k[0] for k in keys), max(k[0] for k in keys)
    knots = [0.0, 1 / 3, 2 / 3, 1.0]
    k = [cells[x][0] for x in keys]
    n = [cells[x][1] for x in keys]
    base = timing._logit_fit([timing._ns_row((d - lo) / (hi - lo), knots) for d, _ in keys], k, n)
    full = timing._logit_fit([timing._ns_row((d - lo) / (hi - lo), knots) + [run] for d, run in keys], k, n)
    se = math.sqrt(timing._inverse(full["xtwx"])[-1][-1])
    return {"spots": sum(n), "slope": round(full["beta"][-1], 3), "se": round(se, 3),
            "deviance_drop": round(base["deviance"] - full["deviance"], 2)}


def against_curve(spots: list[dict], curve: dict, select) -> dict:
    """Live cuts in a subset against what the block's discard curve predicts for the same discards."""
    chosen = [s for s in spots if select(s) and "fit" in curve["cells"][s["discard"]]]
    expected = sum(curve["cells"][s["discard"]]["fit"] for s in chosen) / 100
    return {"spots": len(chosen), "live": round(100 * sum(s["live"] for s in chosen) / len(chosen), 1),
            "curve": round(100 * expected / len(chosen), 1)}


def main(cuts: str, out: str) -> None:
    spots = load(cuts)
    far = [s for s in spots if s["shanten"] >= 2]
    result = {
        "definition": "LuckyJ's discards against a single caller with nobody in riichi, holding a safe tile (danger 1 "
                      "or less) that keeps its best shanten; a cut is live at danger 2 or more. The fold curve is "
                      "from two-shanten or worse; the line is the first caller discard whose fitted share is below half",
        "min_spots": MIN_SPOTS,
        "blocks": {},
        "run_slope": {},
        "tenpai_by_run": {},
        "far_by_run_tiles": {},
    }
    for name, calls in BLOCKS.items():
        block = [s for s in far if s["calls"] in calls]
        curve = fold_curve(block)
        result["blocks"][name] = curve
        result["far_by_run_tiles"][name] = {
            "honors_and_terminals_only": against_curve(block, curve, lambda s: s["run"] >= 1 and honors_and_terminals(s["run_tiles"])),
            "with_a_number_tile": against_curve(block, curve, lambda s: s["run"] >= 1 and not honors_and_terminals(s["run_tiles"])),
        }
        for shanten, keep in SHANTEN.items():
            result["run_slope"].setdefault(shanten, {})[name] = run_slope([s for s in spots if s["calls"] in calls and keep(s["shanten"])])
    for run in (0, 1, 2, 3):
        c = [s for s in spots if s["calls"] == 1 and s["shanten"] == 0 and min(s["run"], 3) == run]
        result["tenpai_by_run"][str(run)] = {"spots": len(c), "live": round(100 * sum(s["live"] for s in c) / len(c), 1)}
    Path(out).write_text(json.dumps(result, indent=1))
    print(f"{out}: {len(spots)} spots, {len(far)} from two-shanten or worse")
    for name, curve in result["blocks"].items():
        cells = curve["cells"]
        print(f"  {name} call(s): {curve['spots']} spots, line at discard {curve['line']} (crossing {curve['crossings_50']})")
        print("    " + " ".join(f"{d}:{cells[d]['fit']:.0f}" for d in range(1, MAX_DISCARD + 1) if "fit" in cells[d]))
    for shanten, blocks in result["run_slope"].items():
        print(f"  run slope, {shanten}: " + "  ".join(f"{b} {v['slope']:+.3f}+-{v['se']:.3f} (n {v['spots']})" for b, v in blocks.items()))
    print("  tenpai against one call, live cut by run: " + "  ".join(f"{r}: {v['live']}% of {v['spots']}" for r, v in result["tenpai_by_run"].items()))
    for name, kinds in result["far_by_run_tiles"].items():
        print(f"  far, {name}: " + "  ".join(f"{k} {v['live']}% vs curve {v['curve']}% (n {v['spots']})" for k, v in kinds.items()))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
