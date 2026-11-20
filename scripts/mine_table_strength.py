#!/usr/bin/env python3
"""Are Saints harder to play against than Masters, and are there more of them at the user's tables than before?

From an amae-koromo export (every player of every game with the rank they held then; Master 1 = 0 ... Saint 3 = 5,
as in ``mine_matchmaking_streaks.ladder``):

1. Saints against Masters at the same table. Each Jade game has three opponents; their places are compared with
   each other (each opponent's place minus the mean place of the three), so the table, the user and the deal are the
   same for everyone compared. One rank step's worth in places, and Saints against Masters, overall and by year.
   An opponent who places better by d takes d places from the other three players, so from the user's seat one
   Master swapped for a Saint costs about d/3 of a place.
2. The user's own results by the number of Saints at the table (0 to 3): mean place, first and fourth rates, final
   score; and a fit of place on that number with controls for the month, the hour and the user's own rank.
3. The user's mean place by room (Gold 9, Jade 12, Throne 16) and year, where the rooms overlap in time.
4. The trend: opponents' mean rank and Saints per table for every Jade game against its date, one row per month
   with its count, a straight-line fit per year with a robust standard error, and whether the user's own rank
   moves the opponents (it would if matching looked at rank inside the room).

usage: mine_table_strength.py EXPORT.json [OUT.json]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mine_matchmaking_streaks import HERO, design, ladder, ols  # noqa: E402

ROOMS = {9: "gold", 12: "jade", 16: "throne"}


def load(path: Path) -> list[dict]:
    out = []
    for uuid, t0, t1, mode, players in json.loads(path.read_text(encoding="utf-8"))["records"]:
        if any(p[2] is None for p in players) or HERO not in [p[0] for p in players]:
            continue
        order = sorted(range(4), key=lambda i: -players[i][3])
        seats = [{"id": p[0], "lv": ladder(p[2]), "score": p[3], "place": order.index(i) + 1}
                 for i, p in enumerate(players)]
        hero = next(s for s in seats if s["id"] == HERO)
        opps = [s for s in seats if s["id"] != HERO]
        out.append({"uuid": uuid, "t0": t0, "dt": datetime.fromtimestamp(t0), "mode": mode, "hero": hero,
                    "opps": opps, "own": hero["lv"], "place": hero["place"], "score": hero["score"],
                    "opp": float(np.mean([o["lv"] for o in opps])), "saints": sum(o["lv"] >= 3 for o in opps)})
    out.sort(key=lambda g: g["t0"])
    return out


def within_table(games: list[dict]) -> dict:
    """Opponents' places against their ranks, each relative to the other two at the same table."""
    x, y, saint = [], [], []
    for g in games:
        mp = np.mean([o["place"] for o in g["opps"]])
        ml = np.mean([o["lv"] for o in g["opps"]])
        for o in g["opps"]:
            x.append(o["lv"] - ml)
            y.append(o["place"] - mp)
            saint.append(o["lv"] >= 3)
    x, y = np.array(x), np.array(y)
    b = float(x @ y / (x @ x))
    e = y - b * x
    se = float(np.sqrt(np.sum((x * e) ** 2)) / (x @ x))
    # Saint against Master, among tables with at least one of each
    diffs = []
    for g in games:
        s = [o["place"] for o in g["opps"] if o["lv"] >= 3]
        m = [o["place"] for o in g["opps"] if 0 <= o["lv"] < 3]
        if s and m:
            diffs.append(np.mean(s) - np.mean(m))
    diffs = np.array(diffs)
    return {"opponent_games": len(x), "place_per_rank_step": round(b, 4), "se": round(se, 4),
            "mixed_tables": len(diffs), "saint_minus_master_place": round(float(diffs.mean()), 4),
            "saint_minus_master_se": round(float(diffs.std(ddof=1) / np.sqrt(len(diffs))), 4)}


def by_saints(games: list[dict]) -> list[dict]:
    groups = defaultdict(list)
    for g in games:
        groups[g["saints"]].append(g)
    return [{"saints": k, "n": len(v), "place": round(float(np.mean([g["place"] for g in v])), 3),
             "place_se": round(float(np.std([g["place"] for g in v], ddof=1) / np.sqrt(len(v))), 3),
             "first": round(float(np.mean([g["place"] == 1 for g in v])), 3),
             "fourth": round(float(np.mean([g["place"] == 4 for g in v])), 3),
             "score": round(float(np.mean([g["score"] for g in v])))} for k, v in sorted(groups.items())]


def fit(rows, x, y):
    X, _ = design(rows, [x])
    beta, se = ols(X, np.array([r[y] for r in rows], float))
    return {"coef": round(float(beta[1]), 4), "se": round(float(se[1]), 4)}


def trend(games: list[dict]) -> dict:
    years = np.array([(g["t0"] - games[0]["t0"]) / (365.25 * 86400) for g in games])
    out = {}
    for key in ("opp", "saints"):
        y = np.array([g[key] for g in games], float)
        X = np.column_stack([np.ones_like(years), years])
        beta, se = ols(X, y)
        out[f"{key}_per_year"] = {"coef": round(float(beta[1]), 4), "se": round(float(se[1]), 4)}
    months = defaultdict(list)
    for g in games:
        months[g["dt"].strftime("%Y-%m")].append(g)
    out["by_month"] = [{"month": k, "n": len(v), "opp": round(float(np.mean([g["opp"] for g in v])), 3),
                        "saints": round(float(np.mean([g["saints"] for g in v])), 3),
                        "own": round(float(np.mean([g["own"] for g in v])), 2)} for k, v in sorted(months.items())]
    # does the user's own rank move the opponents, inside a month?
    X, names = design([{**g, "x": g["own"]} for g in games], ["x"], controls=False)
    mcols = []
    mlist = sorted(months)
    for mth in mlist[1:]:
        mcols.append(np.array([g["dt"].strftime("%Y-%m") == mth for g in games], float))
    X = np.column_stack([X] + mcols)
    beta, se = ols(X, np.array([g["opp"] for g in games]))
    out["own_rank_effect_within_month"] = {"coef": round(float(beta[1]), 4), "se": round(float(se[1]), 4)}
    return out


def main() -> None:
    src = Path(sys.argv[1])
    games = load(src)
    jade = [g for g in games if g["mode"] == 12]
    rooms = defaultdict(list)
    for g in games:
        if g["mode"] in ROOMS:
            rooms[(g["dt"].year, ROOMS[g["mode"]])].append(g["place"])
    report = {
        "jade_games": len(jade),
        "within_table": within_table(jade),
        "within_table_by_year": {str(y): within_table([g for g in jade if g["dt"].year == y])
                                 for y in sorted({g["dt"].year for g in jade})
                                 if sum(g["dt"].year == y for g in jade) >= 100},
        "hero_by_saints": by_saints(jade),
        "hero_place_on_saints": fit(jade, "saints", "place"),
        "hero_place_on_opp": fit(jade, "opp", "place"),
        "hero_place_by_room_year": {f"{y} {r}": {"n": len(v), "place": round(float(np.mean(v)), 3)}
                                    for (y, r), v in sorted(rooms.items())},
        "trend": trend(jade),
    }
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if len(sys.argv) > 2:
        Path(sys.argv[2]).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
