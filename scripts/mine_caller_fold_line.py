#!/usr/bin/env python3
"""Where LuckyJ stops cutting live tiles against a caller, on the axes of chapter 18's caller grid.

Reads the cut rows that ``scripts/contrast/vs_callers.py`` writes for LuckyJ's Tokujou games and keeps
the main book's fold-line spots (its "Open callers" section): LuckyJ's own discards against a single
caller while nobody is in riichi, holding a safe tile (danger 1 or less) that keeps its best shanten. A
cut is live when its danger is 2 or more; LuckyJ folded when it threw the safe tile instead.

For each of LuckyJ's hands (two-shanten or worse, one-shanten, tenpai) the share of live cuts is fitted
over the caller's discards with ``fit_series`` (``scripts/mine_safe_tile_timing.py``), once against one
call and once against two or more, over the discards with at least 40 spots. The line is the first
discard whose fitted share is below half; the far hand's line is the one chapter 18's grid draws on its
first view. Each hand also gets a grid in the shape of chapter 18's: for every calls-and-run row, the
share of turns LuckyJ folded, fitted over the discards with at least 10 spots; the guide shows a square
only where its 95% band lies within 12 points of the fit.

It also asks whether the caller's run of tiles from the wall moves the live share (a logistic regression
of the live cut on the same kind of discard curve plus the run, for each block and each hand), and how
often LuckyJ threw a safe tile when that cost it shanten. Everything is written as JSON.

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
GRID_MIN_SPOTS = 10  # and this many to join a row of the fold grid,
GRID_MAX_HALF_BAND = 12  # whose squares are shown only where the 95% band is this tight
BLOCKS = {"1": (1,), "2+": (2, 3, 4)}
SHANTEN = {"far": lambda sh: sh >= 2, "one": lambda sh: sh == 1, "tenpai": lambda sh: sh == 0}


def honors_and_terminals(tiles: list[int]) -> bool:
    return all(t >= 41 or t % 10 in (1, 9) for t in tiles)


def load(path: str) -> list[dict]:
    """Every discard LuckyJ made against a single caller, with what its safest tiles would have cost."""
    spots = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["who"] != "LuckyJ" or r["n_callers"] != 1 or not 1 <= r["q_turn"] <= MAX_DISCARD:
                continue
            spots.append({"calls": r["n_melds"], "discard": r["q_turn"], "run": r["ts_run"], "run_tiles": r["run_tiles"],
                          "shanten": r["best_sh"], "live": int(r["danger"] >= 2), "free": r["keep_safe"] <= 1,
                          "held": r["held_safe"] <= 1})
    return spots


def _points(spots: list[dict], folded: bool) -> list[dict]:
    points = []
    for d in range(1, MAX_DISCARD + 1):
        c = [s for s in spots if s["discard"] == d]
        k = sum((1 - s["live"]) if folded else s["live"] for s in c)
        points.append({"turn": d, "lj_k": k, "lj_n": len(c), "naga_k": 0, "naga_n": 0})
    return points


def _fitted(points: list[dict], minimum: int) -> tuple[dict, dict | None]:
    span = timing._longest_run(list(range(1, MAX_DISCARD + 1)), {p["turn"]: p["lj_n"] for p in points}, minimum)
    cells = {p["turn"]: {"n": p["lj_n"], "raw": round(100 * p["lj_k"] / p["lj_n"], 1) if p["lj_n"] else None} for p in points}
    if not span or span[1] - span[0] < 3:
        return cells, None
    fit = timing.fit_series(points, "lj", span[0], span[1])
    for t, p, lo, hi in fit["grid"]:
        if abs(t - round(t)) < 1e-6:
            cells[int(round(t))].update({"fit": p, "lo": lo, "hi": hi})
    return cells, {"range": list(span), "df": fit["df"], "crossings_50": fit["crossings_50"]}


def fold_curve(spots: list[dict]) -> dict:
    """The share of live cuts by the caller's discards, and the first discard where it is below half."""
    cells, fit = _fitted(_points(spots, folded=False), MIN_SPOTS)
    line = None
    if fit:
        down = [c["turn"] for c in fit["crossings_50"] if c["direction"] == "down"]
        first = cells[fit["range"][0]]["fit"]
        # a curve that starts below half has no line to draw: LuckyJ threw the safe tile first from the start
        line = math.ceil(down[0]) if down and first >= 50 else None
    return {"spots": len(spots), "range": fit["range"] if fit else None, "df": fit["df"] if fit else None,
            "crossings_50": fit["crossings_50"] if fit else [], "line": line, "cells": cells}


def fold_row(spots: list[dict]) -> dict:
    """One row of a fold grid: per caller discard, LuckyJ's turns and the fitted share on which it folded."""
    cells, fit = _fitted(_points(spots, folded=True), GRID_MIN_SPOTS)
    return {"spots": len(spots), "fit": {"range": fit["range"], "df": fit["df"]} if fit else None, "cells": cells}


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


def share(spots: list[dict]) -> dict:
    return {"spots": len(spots), "folded": round(100 * sum(1 - s["live"] for s in spots) / len(spots), 1) if spots else None}


def main(cuts: str, out: str) -> None:
    every = load(cuts)
    spots = [s for s in every if s["free"]]
    result = {
        "definition": "LuckyJ's discards against a single caller with nobody in riichi, holding a safe tile (danger 1 "
                      "or less) that keeps its best shanten; a cut is live at danger 2 or more, and LuckyJ folded when "
                      "it threw a safe tile. Each block's line is the first caller discard whose fitted live share is "
                      "below half; each grid row is the fitted share of turns LuckyJ folded",
        "min_spots": MIN_SPOTS,
        "grid_min_spots": GRID_MIN_SPOTS,
        "grid_max_half_band": GRID_MAX_HALF_BAND,
        "shanten": {},
        "run_slope": {},
        "tenpai_by_run": {},
        "far_by_run_tiles": {},
    }
    for shanten, keep in SHANTEN.items():
        hand = [s for s in spots if keep(s["shanten"])]
        costly = [s for s in every if keep(s["shanten"]) and s["held"] and not s["free"]]
        entry = {"folded": share(hand), "costly": share(costly), "blocks": {}, "grid": {}}
        for name, calls in BLOCKS.items():
            block = [s for s in hand if s["calls"] in calls]
            entry["blocks"][name] = fold_curve(block)
            result["run_slope"].setdefault(shanten, {})[name] = run_slope(block)
        for c in (1, 2, 3):
            for run in (0, 1, 2, 3):
                entry["grid"][f"{c}-{run}"] = fold_row([s for s in hand if min(s["calls"], 3) == c and min(s["run"], 3) == run])
        result["shanten"][shanten] = entry
    far = [s for s in spots if s["shanten"] >= 2]
    for name, calls in BLOCKS.items():
        block = [s for s in far if s["calls"] in calls]
        curve = result["shanten"]["far"]["blocks"][name]
        result["far_by_run_tiles"][name] = {
            "honors_and_terminals_only": against_curve(block, curve, lambda s: s["run"] >= 1 and honors_and_terminals(s["run_tiles"])),
            "with_a_number_tile": against_curve(block, curve, lambda s: s["run"] >= 1 and not honors_and_terminals(s["run_tiles"])),
        }
    for run in (0, 1, 2, 3):
        c = [s for s in spots if s["calls"] == 1 and s["shanten"] == 0 and min(s["run"], 3) == run]
        result["tenpai_by_run"][str(run)] = {"spots": len(c), "live": round(100 * sum(s["live"] for s in c) / len(c), 1)}
    Path(out).write_text(json.dumps(result, indent=1))
    print(f"{out}: {len(spots)} spots with a safe tile that keeps the shanten")
    for shanten, entry in result["shanten"].items():
        print(f"== {shanten}: folded {entry['folded']['folded']}% of {entry['folded']['spots']};"
              f" when the safe tile cost shanten {entry['costly']['folded']}% of {entry['costly']['spots']}")
        for name, curve in entry["blocks"].items():
            cells = curve["cells"]
            print(f"  {name} call(s): {curve['spots']} spots, line at discard {curve['line']} (crossings {curve['crossings_50']})")
            print("    live " + " ".join(f"{d}:{cells[d]['fit']:.0f}" for d in range(1, MAX_DISCARD + 1) if "fit" in cells[d]))
        for key, row in entry["grid"].items():
            cells = row["cells"]
            print(f"  folded {key} ({row['spots']:5d}): " + " ".join(f"{cells[d]['fit']:4.0f}" if "fit" in cells[d] else "   ." for d in range(1, MAX_DISCARD + 1)))
    for shanten, blocks in result["run_slope"].items():
        print(f"  run slope, {shanten}: " + "  ".join(f"{b} {v['slope']:+.3f}+-{v['se']:.3f} (n {v['spots']})" for b, v in blocks.items()))
    print("  tenpai against one call, live cut by run: " + "  ".join(f"{r}: {v['live']}% of {v['spots']}" for r, v in result["tenpai_by_run"].items()))
    for name, kinds in result["far_by_run_tiles"].items():
        print(f"  far, {name}: " + "  ".join(f"{k} {v['live']}% vs curve {v['curve']}% (n {v['spots']})" for k, v in kinds.items()))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
