#!/usr/bin/env python3
"""How the user does against Saints (and Masters) at the same Jade table, over time.

For every opponent in every Jade South game: did the user finish above them? 50% is an even match. Reported by
year and by the user's own rank, against each Saint step, with a logistic fit of the head-to-head rate on the date
(linear and quadratic in years) whose band comes from resampling whole games (``SEED``, ``BOOT``). As a yardstick,
the same rate for opponent Saints against opponent Masters at the same table.

usage: mine_vs_saints.py EXPORT.json [OUT.json]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mine_table_strength import load  # noqa: E402

SEED = 20261119
BOOT = 1000


def kind(lv: float) -> str:
    return "saint" if lv >= 3 else "master" if lv >= 0 else "other"


def logit_fit(t, y, deg=2, iters=25):
    X = np.column_stack([t**k for k in range(deg + 1)])
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        W = p * (1 - p) + 1e-9
        b += np.linalg.solve(X.T @ (X * W[:, None]), X.T @ (y - p))
    return b


def curve(b, grid):
    X = np.column_stack([grid**k for k in range(len(b))])
    return 1 / (1 + np.exp(-X @ b))


def main() -> None:
    games = [g for g in load(Path(sys.argv[1])) if g["mode"] == 12]
    t0 = games[0]["t0"]
    pairs = []  # (game index, years since start, kind, beat, own, opp level)
    yard = []   # opponent Saint above opponent Master at the same table
    for i, g in enumerate(games):
        yrs = (g["t0"] - t0) / (365.25 * 86400)
        for o in g["opps"]:
            pairs.append((i, yrs, kind(o["lv"]), float(g["place"] < o["place"]), g["own"], o["lv"], g["dt"]))
        for a in g["opps"]:
            for b in g["opps"]:
                if kind(a["lv"]) == "saint" and kind(b["lv"]) == "master":
                    yard.append(float(a["place"] < b["place"]))

    def rate(sel):
        v = [p[3] for p in sel]
        games_ = defaultdict(list)
        for p in sel:
            games_[p[0]].append(p[3])
        # standard error with whole games resampled analytically (cluster by game)
        m = np.mean(v)
        resid = [sum(x - m for x in xs) for xs in games_.values()]
        se = float(np.sqrt(np.sum(np.square(resid))) / len(v))
        return {"n": len(v), "rate": round(float(m), 4), "se": round(se, 4)}

    report = {"games": len(games), "from": games[0]["dt"].date().isoformat(), "to": games[-1]["dt"].date().isoformat(),
              "yardstick_saint_beats_master": round(float(np.mean(yard)), 4), "yardstick_n": len(yard)}
    for k in ("saint", "master"):
        sel = [p for p in pairs if p[2] == k]
        report[k] = {
            "all": rate(sel),
            "by_year": {str(y): rate([p for p in sel if p[6].year == y]) for y in sorted({p[6].year for p in sel})},
            "while_user_master": rate([p for p in sel if p[4] < 3]),
            "while_user_saint": rate([p for p in sel if p[4] >= 3]),
            "since_2026": rate([p for p in sel if p[6] >= datetime(2026, 1, 1)]),
        }
        if k == "saint":
            report[k]["by_saint_step"] = {f"Saint {lv - 2:.0f}": rate([p for p in sel if p[5] == lv]) for lv in (3, 4, 5)}
        # fits: linear slope per year with game-resampled band, quadratic curve
        t = np.array([p[1] for p in sel])
        y = np.array([p[3] for p in sel])
        gi = np.array([p[0] for p in sel])
        span = t.max()
        grid = np.linspace(0, span, 25)
        b1, b2 = logit_fit(t / span, y, 1), logit_fit(t / span, y, 2)
        rng = np.random.default_rng(SEED)
        uniq = np.unique(gi)
        idx_by_game = defaultdict(list)
        for j, g in enumerate(gi):
            idx_by_game[g].append(j)
        boot_curves, boot_slopes = [], []
        for _ in range(BOOT):
            pick = np.concatenate([idx_by_game[g] for g in rng.choice(uniq, len(uniq))])
            bb2 = logit_fit(t[pick] / span, y[pick], 2)
            bb1 = logit_fit(t[pick] / span, y[pick], 1)
            boot_curves.append(curve(bb2, grid / span))
            boot_slopes.append((curve(bb1, np.array([1.0])) - curve(bb1, np.array([0.0])))[0] / span)
        lo, hi = np.percentile(boot_curves, [5, 95], axis=0)
        fit = curve(b2, grid / span)
        slope = (curve(b1, np.array([1.0])) - curve(b1, np.array([0.0])))[0] / span
        report[k]["linear_change_per_year"] = {"est": round(float(slope), 4),
                                               "p5": round(float(np.percentile(boot_slopes, 5)), 4),
                                               "p95": round(float(np.percentile(boot_slopes, 95)), 4)}
        report[k]["curve"] = [{"date": datetime.fromtimestamp(t0 + g * 365.25 * 86400).date().isoformat(),
                               "fit": round(float(f), 4), "p5": round(float(a), 4), "p95": round(float(b), 4)}
                              for g, f, a, b in zip(grid, fit, lo, hi)]
    text = json.dumps(report, indent=1)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
