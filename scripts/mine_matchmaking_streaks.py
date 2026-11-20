#!/usr/bin/env python3
"""Does Mahjong Soul seat stronger opponents after a run of good results, and weaker ones after a bad run?

Every ranked game in an amae-koromo export lists all four players with their rank at the time of the game. For
each of the user's games this takes:

- the opponents' strength: the mean of their three ranks on one ladder (Master 1 = 0, Master 2 = 1, ... Saint 3 = 5;
  Expert and Celestial continue the same scale), and the number of Saints among them;
- the user's form going in: the place in the previous game, the signed streak (+n after n top-two finishes in a row,
  -n after n bottom-two finishes in a row), first places in a row, and the rank points of the previous five games.

It then measures how the opponents' strength moves with the form, three ways:

1. one row per streak value with the mean opponent rank and its count;
2. a least-squares fit of opponent rank on form with controls for the hour of day, the month and the user's own rank
   (the player pool changes with all three), with robust standard errors;
3. a permutation test: the opponents of each game are held fixed and the form sequence is shuffled within each month,
   so the null keeps the month-to-month drift but breaks any link to the games just before.

As a check that the strength measure means something, it also fits the user's place on the opponents' strength.

The one thing that moves the opponents is a fourth place in the game just before (``prev4``), so that gets its own
fits: alone, beside the rank points already banked inside the current rank (``score_lvl``, the running sum of rank
points since the last promotion or demotion), and year by year.

The recent corpus export covers only games since August 2025. For the whole history, pull every record into a
separate file (the corpus export stays as it is): ``fetch_majsoul_games.amae_api_refresh(120182062, None, token,
Path("<scratch>/amae-full.json"))``, about 50 requests.

usage: mine_matchmaking_streaks.py EXPORT.json [OUT.json] [--mode 12] [--since YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

SEED = 20261119
PERMS = 5000


def ladder(level: int) -> float:
    """Rank id 10xyz (tier y, step z) on one scale: Master 1 = 0 ... Saint 3 = 5 (Expert is -3)."""
    tier, step = (level // 100) % 10, level % 100
    return (tier - 4) * 3 + (step - 1)


def hero_of(records: list) -> int:
    """The export's own player: the one account in every record."""
    seen = Counter(p[0] for r in records for p in r[4])
    account, n = seen.most_common(1)[0]
    if n != len(records):
        raise SystemExit(f"no account appears in all {len(records)} records (best: {n})")
    return account


def games(path: Path, mode: int | None, since: str | None) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    hero = hero_of(data["records"])
    start = datetime.strptime(since, "%Y-%m-%d").timestamp() if since else 0
    out = []
    for uuid, t0, t1, mode_id, players in data["records"]:
        if mode is not None and mode_id != mode or t0 < start:
            continue
        ids = [p[0] for p in players]
        if hero not in ids or any(p[2] is None for p in players):
            continue
        order = sorted(range(4), key=lambda i: -players[i][3])  # seat order breaks ties
        place = {i: order.index(i) + 1 for i in range(4)}
        h = ids.index(hero)
        opp = [ladder(players[i][2]) for i in range(4) if i != h]
        out.append({
            "uuid": uuid, "t0": t0, "t1": t1, "place": place[h], "pt": players[h][4] or 0,
            "own": ladder(players[h][2]), "opp": float(np.mean(opp)), "saints": sum(o >= 3 for o in opp),
            "dt": datetime.fromtimestamp(t0),
        })
    out.sort(key=lambda g: g["t0"])
    level, banked = None, 0
    for g in out:
        if g["own"] != level:
            level, banked = g["own"], 0
        g["score_lvl"] = banked
        banked += g["pt"]
    return out


def add_form(gs: list[dict]) -> list[dict]:
    """Form going into each game, from the games before it (the first five games are dropped)."""
    rows = []
    for k in range(5, len(gs)):
        prev = gs[:k]
        streak = 0
        top = prev[-1]["place"] <= 2
        for g in reversed(prev):
            if (g["place"] <= 2) != top:
                break
            streak += 1
        firsts = 0
        for g in reversed(prev):
            if g["place"] != 1:
                break
            firsts += 1
        gap_h = (gs[k]["t0"] - prev[-1]["t1"]) / 3600
        rows.append({**gs[k], "prev_place": prev[-1]["place"], "streak": streak if top else -streak,
                     "firsts": firsts, "pt5": sum(g["pt"] for g in prev[-5:]),
                     "top3": sum(g["place"] <= 2 for g in prev[-3:]), "same_session": gap_h < 1.0,
                     "prev4": float(prev[-1]["place"] == 4), "gap_min": round(gap_h * 60, 1)})
    return rows


def design(rows, xs, controls=True):
    cols = [np.ones(len(rows))] + [np.array([r[x] for r in rows], float) for x in xs]
    names = ["const"] + list(xs)
    if controls:
        for key, fmt in (("hour", lambda r: r["dt"].hour // 3), ("month", lambda r: r["dt"].strftime("%Y-%m")),
                         ("own", lambda r: r["own"])):
            levels = sorted({fmt(r) for r in rows})
            for lv in levels[1:]:
                cols.append(np.array([fmt(r) == lv for r in rows], float))
                names.append(f"{key}={lv}")
    return np.column_stack(cols), names


def ols(X, y):
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    e = y - X @ beta
    cov = XtX_inv @ (X.T * e**2) @ X @ XtX_inv  # HC0
    return beta, np.sqrt(np.diag(cov))


def fit(rows, x, y="opp", extra=()):
    X, names = design(rows, [x, *extra])
    beta, se = ols(X, np.array([r[y] for r in rows], float))
    return {"coef": round(float(beta[1]), 4), "se": round(float(se[1]), 4), "t": round(float(beta[1] / se[1]), 2)}


def permutation(rows, x, rng):
    """Shuffle the form column within months; two-sided p of the controlled slope."""
    X, _ = design(rows, [x])
    y = np.array([r["opp"] for r in rows], float)
    P = np.linalg.pinv(X.T @ X) @ X.T
    obs = (P @ y)[1]
    months = defaultdict(list)
    for i, r in enumerate(rows):
        months[r["dt"].strftime("%Y-%m")].append(i)
    col = X[:, 1].copy()
    hits = 0
    for _ in range(PERMS):
        shuffled = col.copy()
        for idx in months.values():
            shuffled[idx] = rng.permutation(col[idx])
        X[:, 1] = shuffled
        P = np.linalg.pinv(X.T @ X) @ X.T
        hits += abs((P @ y)[1]) >= abs(obs)
    X[:, 1] = col
    return round((hits + 1) / (PERMS + 1), 4)


def by_value(rows, key, lo=None, hi=None):
    groups = defaultdict(list)
    for r in rows:
        v = r[key]
        if lo is not None:
            v = max(lo, min(hi, v))
        groups[v].append(r)
    return [{key: v, "n": len(g), "opp": round(float(np.mean([r["opp"] for r in g])), 3),
             "saints": round(float(np.mean([r["saints"] for r in g])), 3),
             "next_top2": round(float(np.mean([r["place"] <= 2 for r in g])), 3)}
            for v, g in sorted(groups.items())]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", type=Path)
    ap.add_argument("out", type=Path, nargs="?")
    ap.add_argument("--mode", type=int, default=12)
    ap.add_argument("--since")
    args = ap.parse_args()

    gs = games(args.export, args.mode, args.since)
    rows = add_form(gs)
    rng = np.random.default_rng(SEED)
    report = {
        "games": len(gs), "rows": len(rows),
        "from": gs[0]["dt"].date().isoformat(), "to": gs[-1]["dt"].date().isoformat(),
        "own_rank_counts": {str(k): sum(g["own"] == k for g in gs) for k in sorted({g["own"] for g in gs})},
        "opp_mean": round(float(np.mean([r["opp"] for r in rows])), 3),
        "opp_sd": round(float(np.std([r["opp"] for r in rows])), 3),
        "by_streak": by_value(rows, "streak", -5, 5),
        "by_prev_place": by_value(rows, "prev_place"),
        "by_firsts": by_value(rows, "firsts", 0, 3),
        "fits": {}, "fits_same_session": {}, "place_on_opp": fit(rows, "opp", y="place"),
    }
    same = [r for r in rows if r["same_session"]]
    report["same_session_rows"] = len(same)
    for x in ("streak", "prev_place", "firsts", "pt5", "top3", "prev4"):
        report["fits"][x] = {**fit(rows, x), "perm_p": permutation(rows, x, rng)}
        report["fits_same_session"][x] = fit(same, x)
    report["prev4_checks"] = {
        "with_score_in_rank": fit(rows, "prev4", extra=("score_lvl",)),
        "with_streak": fit(rows, "prev4", extra=("streak",)),
        "after_break_1h_plus": fit([r for r in rows if r["gap_min"] >= 60], "prev4"),
        "requeued_within_10min": fit([r for r in rows if r["gap_min"] < 10], "prev4"),
        "median_gap_min_after_4th": float(np.median([r["gap_min"] for r in rows if r["prev4"]])),
        "median_gap_min_otherwise": float(np.median([r["gap_min"] for r in rows if not r["prev4"]])),
        "by_year": {str(y): {"n": len(q), **fit(q, "prev4")}
                    for y in sorted({r["dt"].year for r in rows})
                    if len(q := [r for r in rows if r["dt"].year == y]) >= 100},
    }
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
