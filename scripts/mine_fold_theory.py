#!/usr/bin/env python3
"""Guide chapter 38: why the user should fold a little more than LuckyJ against a riichi, and what makes the gap.

A push pays when the player's own chances of winning and of dealing in, weighed by what each does to the game, beat
what folding costs. Three things could make the user's numbers differ from LuckyJ's, and each is measured:

- the point system: chapter 37's 15 played-out folds (``mortal_whatif.py`` runs) rescored under Tenhou's Tokujou and
  Houou dan points at 10-dan (placement only) and under the Saint 3 Jade values (placement and score), and the
  Jade values split into their placement and score parts;
- the opponents: every riichi declared by the other three players at the user's tables and at LuckyJ's
  (``contrast/tenpai.py`` rows): how often it won, its live tiles, its value from the declarer's seat, its turn;
- the read: on every push-or-fold spot of ``mine_thin_pushes.py``, deal-ins on the tile pushed against LuckyJ's rate
  for a tile of the same kind, kind by kind; wins after pushing by live tiles; what a deal-in on the push and a push
  that does not deal in each do to the expected rank points (``mine_push_ev.Model``); and pushes of a tile one or two
  ranks from a riichi declaration tile of the same suit.

It also lists, by hand value and live tiles, how often each side pushed and the rank points of its pushes and folds.

usage: mine_fold_theory.py RUNS_DIR TENPAI_YOU TENPAI_LJ THIN_YOU THIN_LJ OUT.json
"""

from __future__ import annotations

import glob
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mine_push_ev as pe  # noqa: E402
from mine_thin_pushes import kind  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
SYSTEMS = {
    "jade": lambda s, p: math.ceil((s - 30000) / 1000 + (130, 65, 0, -250)[p]),
    "tenhou_tokujou_10dan": lambda s, p: (75, 30, 0, -180)[p],
    "tenhou_houou_10dan": lambda s, p: (90, 45, 0, -180)[p],
    "jade_placement": lambda s, p: (130, 65, 0, -250)[p],
    "jade_score": lambda s, p: (s - 30000) / 1000,
}
RANGE = {"jade": 380, "tenhou_tokujou_10dan": 255, "tenhou_houou_10dan": 270}


def pct(k: float, n: int, digits: int = 1) -> float | None:
    return round(100 * k / n, digits) if n else None


def mean_se(xs: list[float]) -> tuple[float | None, float | None]:
    if len(xs) < 2:
        return (round(float(np.mean(xs)), 1) if xs else None), None
    x = np.array(xs, dtype=float)
    return round(float(x.mean()), 1), round(float(x.std(ddof=1) / math.sqrt(len(x))), 1)


def systems(runs_dir: str) -> dict:
    gains = {k: [] for k in SYSTEMS}
    for f in sorted(glob.glob(str(Path(runs_dir) / "*.json"))):
        d = json.loads(Path(f).read_text())
        hero, rows = d["hero"], d["samples"]
        for k, u in SYSTEMS.items():
            diff = [u(r[d["other"]]["scores"][hero], r[d["other"]]["places"][hero])
                    - u(r[d["played"]]["scores"][hero], r[d["played"]]["places"][hero]) for r in rows]
            gains[k].append(sum(diff) / len(diff))
    out = {}
    for k, v in gains.items():
        m, se = mean_se(v)
        out[k] = {"folds": len(v), "push_gain": m, "se": se}
        if k in RANGE:
            out[k]["share_of_range"] = round(100 * m / RANGE[k], 2)
    return out


def opponents(path: str) -> dict:
    rows = [r for line in open(path) if not (r := json.loads(line))["lj"] and r["riichi"]]
    live = [o["live"] for r in rows if (o := next((o for o in r["opts"] if o["b"] == r["cut"]), None))]
    won = [r for r in rows if r["won"]]
    return {"riichis": len(rows), "won": pct(len(won), len(rows)), "live": round(sum(live) / len(live), 2),
            "points": round(sum(r["net"] for r in rows) / len(rows)), "turn": round(sum(r["t"] for r in rows) / len(rows), 1)}


def on_push(r: dict) -> bool:
    return bool(r["deal"] and r["deal"]["on_decision"])


def read(you: list[dict], lj: list[dict]) -> dict:
    pushes, theirs = [r for r in you if r["pushed"]], [r for r in lj if r["pushed"]]
    rate = {k: sum(on_push(r) for r in theirs if kind(r) == k) / sum(1 for r in theirs if kind(r) == k)
            for k in {kind(r) for r in theirs}}
    expected = sum(rate.get(kind(r), 0) for r in pushes)
    seen = sum(on_push(r) for r in pushes)
    kinds = {}
    for k in ("live honor", "live terminal", "half suji", "live 2-3-7-8", "live 4-5-6"):
        mine = [r for r in pushes if kind(r) == k]
        kinds[k] = {"you": [sum(on_push(r) for r in mine), len(mine), pct(sum(on_push(r) for r in mine), len(mine))],
                    "luckyj": [sum(on_push(r) for r in theirs if kind(r) == k), sum(1 for r in theirs if kind(r) == k),
                               pct(100 * rate[k], 100)]}
    wins = {}
    for name, keep in (("3 or fewer", lambda r: r["live"] <= 3), ("4-7", lambda r: 4 <= r["live"] <= 7), ("8 or more", lambda r: r["live"] >= 8)):
        a, b = [r for r in pushes if keep(r)], [r for r in theirs if keep(r)]
        wins[name] = {"you": [sum(r["won"] for r in a), len(a), pct(sum(r["won"] for r in a), len(a))],
                      "luckyj": [sum(r["won"] for r in b), len(b), pct(sum(r["won"] for r in b), len(b))]}
    ev = lambda rs: round(float(np.mean([r["ev_change"] for r in rs])), 1)
    cost = {"deal_in_on_the_push": ev([r for r in pushes if on_push(r)]), "no_deal_in": ev([r for r in pushes if not r["deal"]]),
            "luckyj_deal_in_on_the_push": ev([r for r in theirs if on_push(r)]), "luckyj_no_deal_in": ev([r for r in theirs if not r["deal"]])}
    excess = (seen - expected) / len(pushes)
    cost["excess_points"] = round(100 * excess, 2)
    cost["per_push"] = round(excess * (cost["no_deal_in"] - cost["deal_in_on_the_push"]), 2)
    near = {}
    numbers = ("half suji", "live 2-3-7-8", "live 4-5-6", "live terminal")
    for who, rs in (("you", pushes), ("luckyj", theirs)):
        ns = [r for r in rs if kind(r) in numbers]
        block = {}
        for name, keep in (("1-2 ranks from the riichi tile", lambda r: r["near_riichi_tile"] is not None and 1 <= r["near_riichi_tile"] <= 2),
                           ("same suit, further", lambda r: r["near_riichi_tile"] is not None and not 1 <= r["near_riichi_tile"] <= 2),
                           ("another suit", lambda r: r["near_riichi_tile"] is None)):
            s = [r for r in ns if keep(r)]
            block[name] = {"pushes": len(s), "share": pct(len(s), len(ns)), "dealt": sum(on_push(r) for r in s),
                           "dealt_pct": pct(sum(on_push(r) for r in s), len(s))}
        near[who] = block
    return {"pushes": len(pushes), "on_push_deal_ins": seen, "luckyj_expects": round(expected, 1), "kinds": kinds,
            "wins_after_pushing": wins, "cost": cost, "near_riichi_tile": near}


def cells(you: list[dict], lj: list[dict]) -> dict:
    out = {}
    for value, keep_v in (("no yaku", lambda r: r["han"] <= 0), ("1-2 han", lambda r: 1 <= r["han"] <= 2), ("3+ han", lambda r: r["han"] >= 3)):
        for live, keep_l in (("3 or fewer", lambda r: r["live"] <= 3), ("4-7", lambda r: 4 <= r["live"] <= 7), ("8 or more", lambda r: r["live"] >= 8)):
            block = {}
            for who, rows in (("you", you), ("luckyj", lj)):
                s = [r for r in rows if keep_v(r) and keep_l(r)]
                p, f = [r["ev_change"] for r in s if r["pushed"]], [r["ev_change"] for r in s if not r["pushed"]]
                block[who] = {"spots": len(s), "pushed_pct": pct(len(p), len(s)), "push": mean_se(p), "fold": mean_se(f)}
            out[f"{value}, {live} live"] = block
    return out


def main() -> None:
    runs_dir, tenpai_you, tenpai_lj, thin_you, thin_lj, out = sys.argv[1:7]
    mine = [g for g in json.loads(MANIFEST.read_text(encoding="utf-8")) if g["date"] >= pe.SINCE]
    lj_manifest = json.loads(LJ_MANIFEST.read_text(encoding="utf-8"))
    rel, keep = pe.pool(mine)
    model = pe.Model(rel, keep)
    you = pe.spot_ev(json.load(open(thin_you))["rows"], {g["uuid"]: g for g in mine}, model)
    lj = pe.spot_ev(json.load(open(thin_lj))["rows"], {g["uuid"]: g for g in lj_manifest}, model)
    data = {"systems": systems(runs_dir), "opponents": {"you": opponents(tenpai_you), "luckyj": opponents(tenpai_lj)},
            "read": read(you, lj), "cells": cells(you, lj)}
    Path(out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
