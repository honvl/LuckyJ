#!/usr/bin/env python3
"""What Celestial in the Throne room would look like for the user.

1. ``--fetch OUT.json``: recent Throne South games (mode 16) from amae-koromo's game list, newest first, one request per
   ``AMAE_MIN_INTERVAL`` seconds with the user's key. Only start time, rank, score and rank-point change of each seat
   are kept (no names or ids).
2. The analysis of such a file: share of seats by rank group, each group's places and rank points per game, and
   head-to-head rates between groups at the same table.
3. A Celestial Lv1 walk: start at 10.0 (1000 in amae units), +0.5/+0.2/-0.2/-0.5 by place (twice that at an all-Celestial
   table, ``DOUBLE`` of the time), Lv2 at 20.0, demotion to Saint 3 below 0. The place distribution is Lv1 Celestials'
   own, tilted to a given average place. Reports the chance of demotion before Lv2 and the games it takes.

Celestial rules: game8.jp/jantama/631616 (levels start at 10, Lv1 below 0 demotes) and the rank-point changes of
the Celestials in the user's own 2022 Throne games (+50/+20/-20/-50).

usage: mine_throne_outlook.py --fetch OUT.json [--days 30] [--pages 60]
       mine_throne_outlook.py GAMES.json [REPORT.json]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

SEED = 20261119
DOUBLE = 0.3
STEP = np.array([50, 20, -20, -50])


def fetch(out: Path, days: int, pages: int) -> None:
    import fetch_majsoul_games as f
    tok = f.amae_token()
    end = int(time.time() * 1000)
    start = end - days * 86400 * 1000
    rows, seen = [], set()
    for _ in range(pages):
        t = time.time()
        url = f"{f.AMAE_API}/games/{end}/{start}?limit=100&descending=true&mode=16"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tok}", "User-Agent": "LuckyJ self-review"})
        page = json.loads(urllib.request.urlopen(req, timeout=30).read())
        for g in page:
            if g["uuid"] not in seen:
                seen.add(g["uuid"])
                rows.append([g["startTime"], [[p["level"], p["score"], p["gradingScore"]] for p in g["players"]]])
        if len(page) < 100:
            break
        end = min(g["startTime"] for g in page) * 1000 - 1
        time.sleep(max(0.0, f.AMAE_MIN_INTERVAL - (time.time() - t)))
    out.write_text(json.dumps(rows), encoding="utf-8")
    print(f"{len(rows)} games -> {out}")


def group(lv: int) -> str:
    if lv >= 10700:
        n = lv - 10700
        return "Cel1" if n == 1 else "Cel2-3" if n <= 3 else "Cel4-7" if n <= 7 else "Cel8+"
    return {10501: "S1", 10502: "S2", 10503: "S3"}.get(lv, "other")


def analyse(games: list) -> dict:
    seats, places, pts, pair = collections.Counter(), collections.defaultdict(list), collections.defaultdict(list), \
        collections.defaultdict(list)
    for _, ps in games:
        order = sorted(range(4), key=lambda i: -ps[i][1])
        place = [order.index(i) + 1 for i in range(4)]
        for i, p in enumerate(ps):
            g = group(p[0])
            seats[g] += 1
            places[g].append(place[i])
            pts[g].append(p[2])
            for j, q in enumerate(ps):
                if i != j:
                    pair[(g, group(q[0]))].append(place[i] < place[j])
    total = sum(seats.values())
    out = {"games": len(games), "from": min(g[0] for g in games), "to": max(g[0] for g in games),
           "all_celestial_tables": sum(all(p[0] >= 10700 for p in ps) for _, ps in games), "groups": {}, "pairs": {}}
    for g in ("S1", "S2", "S3", "Cel1", "Cel2-3", "Cel4-7", "Cel8+"):
        c = collections.Counter(places[g])
        k = len(places[g])
        out["groups"][g] = {"seat_share": round(seats[g] / total, 4), "n": k,
                            "place": round(float(np.mean(places[g])), 3),
                            "dist": [round(c[i] / k, 3) for i in (1, 2, 3, 4)],
                            "pts_per_game": round(float(np.mean(pts[g])), 2)}
    for a, b in (("Cel1", "S3"), ("Cel1", "S2"), ("Cel1", "S1"), ("S3", "S1"), ("Cel2-3", "Cel1"),
                 ("Cel4-7", "Cel1"), ("Cel8+", "Cel1")):
        v = pair[(a, b)]
        out["pairs"][f"{a} above {b}"] = {"n": len(v), "rate": round(float(np.mean(v)), 3)}
    return out


def walk(base: np.ndarray, target: float, rng, n=4000, games=1000) -> dict:
    lo, hi = -3.0, 3.0
    for _ in range(60):
        lam = (lo + hi) / 2
        p = base * np.exp(-lam * np.arange(1, 5))
        p /= p.sum()
        lo, hi = (lam, hi) if p @ np.arange(1, 5) > target else (lo, lam)
    down = up = 0
    took = []
    for _ in range(n):
        s = 1000
        pl = rng.choice(4, size=games, p=p)
        dbl = rng.random(games) < DOUBLE
        for k in range(games):
            s += STEP[pl[k]] * (2 if dbl[k] else 1)
            if s < 0 or s >= 2000:
                down += s < 0
                up += s >= 2000
                took.append(k + 1)
                break
    return {"avg_place": target, "dist": [round(float(x), 3) for x in p],
            "drift_per_game": round(float(p @ STEP) * (1 + DOUBLE) / 100, 4),
            "p_demote_before_lv2": round(down / n, 3), "p_lv2_first": round(up / n, 3),
            "median_games": int(np.median(took))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("games", type=Path, nargs="?")
    ap.add_argument("report", type=Path, nargs="?")
    ap.add_argument("--fetch", type=Path)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--pages", type=int, default=60)
    args = ap.parse_args()
    if args.fetch:
        fetch(args.fetch, args.days, args.pages)
        return
    games = json.loads(args.games.read_text(encoding="utf-8"))
    report = analyse(games)
    base = np.array(report["groups"]["Cel1"]["dist"], float)
    rng = np.random.default_rng(SEED)
    report["lv1_walk"] = [walk(base, t, rng) for t in (2.40, 2.45, 2.48, 2.50, 2.55)]
    text = json.dumps(report, indent=1)
    if args.report:
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
