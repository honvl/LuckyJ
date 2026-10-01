#!/usr/bin/env python3
"""Chapter 25: how your place in the game moves LuckyJ's riichi, by hand value and turn.

The decisions are chapter 24's: first closed tenpais with riichi legal, a wait that is not furiten and nobody
else in riichi (``scripts/contrast/tenpai.py`` rows). Each hand is put in a value class: no yaku, a yaku on only
some winning tiles, 1-2 han, a two-sided 3-han pinfu (3,900 by ron), a two-sided 3-han hand at 40 fu or more, 3
han or more on any other wait, two-sided 4 han, and two-sided 5 han or more.

One logistic model fits LuckyJ's riichi over all 2,177 of them: each value class has its own intercept and its
own turn curve (a quadratic in the turn for the three largest classes, a straight line for the rest), the dealer
adds one term, and the place at the start of the hand shifts the log-odds by one term for each stage of the game:
the East, South 1 to 3, and the last hand (South 4, with any West hands, where a win can end the game). 4th in the
East is the base. ``placement_by_value`` tests whether that shift differs for hands of 3 han or
more on a poor wait or 4 han or more; ``lead`` whether the size of a lead adds to being 1st.

- ``grid``: the fitted share of riichi for a non-dealer in each value class, place, stage and turn, over the turns
  where the class has its middle 90% of hands.
- ``raw``: the counts behind it, by class, stage and place; ``luckyj_by_place`` the same for all classes.
- ``you``: your first tenpais (games since 1 January) by stage and place, against what the model expects of
  LuckyJ on the same hands; outside the East, your 1st and 4th places against the model with its binomial
  spread (a fit of your own place terms diverges on cells of six hands).

usage: mine_riichi_placement.py YOUR_TENPAI LJ_TENPAI OUT.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mine_dama_value import ron_points  # noqa: E402

CLASSES = ["no yaku", "some waits", "1-2", "3 pinfu", "3 at 40 fu", "3+ poor wait", "4", "5+"]
QUADRATIC = {"no yaku", "1-2", "3 pinfu"}
GRID_CLASSES = ["no yaku", "1-2", "3 pinfu", "4", "5+"]
BIG = {"3 at 40 fu", "3+ poor wait", "4", "5+"}
STAGES = ("East", "South", "All-last")
PLACES = [(rank, stage) for stage in STAGES for rank in (1, 2, 3, 4) if (rank, stage) != (4, "East")]
TWO_SIDED = ("ryanmen", "multi")


def place_key(rank: int, stage: str) -> str:
    return f"{rank} {stage}"


def stage_of(kyoku: int) -> str:
    return "East" if kyoku < 4 else "South" if kyoku < 7 else "All-last"


def load(path: str, hero_only: bool = True) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if hero_only and not r["lj"]:
                continue
            if not (r["first"] and r["kept"] and r["left"] >= 4 and r["score"] >= 1000 and r["nr"] == 0):
                continue
            opt = next((o for o in r["opts"] if o["b"] == r["cut"]), None)
            if opt is None or opt["fur"]:
                continue
            scores, me = r["sc"], r["sc"][r["s"]]
            top_other = max(scores[q] for q in range(4) if q != r["s"])
            row = {"g": r["g"], "li": r["li"], "t": r["t"], "riichi": float(r["riichi"]), "dealer": float(r["dl"]),
                   "rank": r["rk"], "stage": stage_of(r["k"]), "lead": me - top_other, "v": opt["dama_min"],
                   "vmax": opt["dama_max"], "two": opt["shape"] in TWO_SIDED, "cut": r["cut"],
                   "points": min(ron_points(h, f) for h, f in zip(opt["dama_han"], opt["dama_fu"]))}
            row["class"] = value_class(row)
            rows.append(row)
    return rows


def value_class(r: dict) -> str:
    if r["v"] == 0:
        return "some waits" if r["vmax"] > 0 else "no yaku"
    if r["v"] <= 2:
        return "1-2"
    if not r["two"]:
        return "3+ poor wait"
    if r["v"] == 3:
        return "3 pinfu" if r["points"] < 5200 else "3 at 40 fu"
    return "4" if r["v"] == 4 else "5+"


def _turn(t: float) -> float:
    return (t - 9.0) / 4


def hand_terms(r: dict) -> list[float]:
    row = []
    for c in CLASSES:
        on = float(r["class"] == c)
        row += [on, on * _turn(r["t"])]
        if c in QUADRATIC:
            row.append(on * _turn(r["t"]) ** 2)
    row.append(r["dealer"])
    return row


def place_terms(r: dict) -> list[float]:
    return [float(r["rank"] == rank and r["stage"] == stage) for rank, stage in PLACES]


def fit(x: np.ndarray, y: np.ndarray, offset: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, float]:
    off = np.zeros(len(y)) if offset is None else offset
    beta = np.zeros(x.shape[1])
    for _ in range(100):
        mu = 1 / (1 + np.exp(-(off + x @ beta)))
        w = mu * (1 - mu)
        step = np.linalg.solve((x.T * w) @ x + 1e-9 * np.eye(x.shape[1]), x.T @ (y - mu))
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    mu = np.clip(1 / (1 + np.exp(-(off + x @ beta))), 1e-12, 1 - 1e-12)
    w = mu * (1 - mu)
    se = np.sqrt(np.diag(np.linalg.inv((x.T * w) @ x + 1e-9 * np.eye(x.shape[1]))))
    return beta, se, float(np.sum(y * np.log(mu) + (1 - y) * np.log(1 - mu)))


def turn_range(rows: list[dict], cls: str) -> list[int]:
    turns = sorted(r["t"] for r in rows if r["class"] == cls)
    return [turns[int(0.05 * (len(turns) - 1))], turns[int(math.ceil(0.95 * (len(turns) - 1)))]]


def main() -> None:
    your_path, lj_path, out_path = sys.argv[1:4]
    lj = load(lj_path)
    x = np.array([hand_terms(r) + place_terms(r) for r in lj])
    y = np.array([r["riichi"] for r in lj])
    beta, se, ll = fit(x, y)
    n_hand = len(hand_terms(lj[0]))
    places = {place_key(*p): [round(float(beta[n_hand + i]), 3), round(float(se[n_hand + i]), 3)] for i, p in enumerate(PLACES)}

    # does the shift differ for big hands?
    big = np.array([[float(r["class"] in BIG) * t for t in place_terms(r)] for r in lj])
    _, _, ll_big = fit(np.column_stack([x, big]), y)
    # does the size of a lead add to being 1st?
    lead = {}
    for stage in STAGES:
        extra = np.array([[float(r["rank"] == 1 and r["stage"] == stage) * r["lead"] / 10000] for r in lj])
        b2, s2, _ = fit(np.column_stack([x, extra]), y)
        lead[stage] = [round(float(b2[-1]), 3), round(float(s2[-1]), 3)]

    grid = {}
    for cls in GRID_CLASSES:
        lo, hi = turn_range(lj, cls)
        for rank, stage in [(rank, stage) for stage in STAGES for rank in (1, 2, 3, 4)]:
            cells = {}
            for t in range(lo, hi + 1):
                r = {"class": cls, "t": t, "dealer": 0.0, "rank": rank, "stage": stage}
                eta = float(np.array(hand_terms(r) + place_terms(r)) @ beta)
                cells[str(t)] = round(100 / (1 + math.exp(-eta)), 1)
            grid[f"{cls}|{place_key(rank, stage)}"] = cells
    raw = {}
    for cls in CLASSES:
        for rank, stage in [(rank, stage) for stage in STAGES for rank in (1, 2, 3, 4)]:
            sel = [r for r in lj if r["class"] == cls and r["rank"] == rank and r["stage"] == stage]
            raw[f"{cls}|{place_key(rank, stage)}"] = [int(sum(r["riichi"] for r in sel)), len(sel)]
    by_stage = {}
    for rank, stage in [(rank, stage) for stage in STAGES for rank in (1, 2, 3, 4)]:
        sel = [r for r in lj if r["rank"] == rank and r["stage"] == stage]
        by_stage[place_key(rank, stage)] = [int(sum(r["riichi"] for r in sel)), len(sel)]

    you = load(your_path)
    xy = np.array([hand_terms(r) + place_terms(r) for r in you])
    expect = 1 / (1 + np.exp(-(xy @ beta)))
    by_place = {}
    for rank, stage in [(rank, stage) for stage in STAGES for rank in (1, 2, 3, 4)]:
        idx = [i for i, r in enumerate(you) if r["rank"] == rank and r["stage"] == stage]
        by_place[place_key(rank, stage)] = {"hands": len(idx), "declared": int(sum(you[i]["riichi"] for i in idx)),
                                            "luckyj_expects": round(float(sum(expect[i] for i in idx)), 2)}
    # outside the East, in 1st and in 4th: your declarations against the model, with the binomial spread
    spread = {}
    for rank in (1, 4):
        idx = [i for i, r in enumerate(you) if r["stage"] != "East" and r["rank"] == rank]
        exp = [float(expect[i]) for i in idx]
        spread[str(rank)] = {"hands": len(idx), "declared": int(sum(you[i]["riichi"] for i in idx)),
                             "luckyj_expects": round(sum(exp), 2), "sd": round(math.sqrt(sum(p * (1 - p) for p in exp)), 2)}
    south4 = [{"g": r["g"], "li": r["li"], "t": r["t"], "stage": r["stage"], "rank": r["rank"], "class": r["class"],
               "riichi": bool(r["riichi"]), "cut": r["cut"], "luckyj": round(float(expect[i]), 3)}
              for i, r in enumerate(you) if r["stage"] != "East" and r["rank"] in (1, 4)]

    out = {
        "luckyj_hands": len(lj),
        "your_hands": len(you),
        "places": places,
        "dealer": [round(float(beta[n_hand - 1]), 3), round(float(se[n_hand - 1]), 3)],
        "placement_by_value": {"chi2": round(2 * (ll_big - ll), 2), "df": len(PLACES)},
        "lead": lead,
        "ranges": {cls: turn_range(lj, cls) for cls in GRID_CLASSES},
        "grid": grid,
        "raw": raw,
        "luckyj_by_place": by_stage,
        "you": {"by_place": by_place, "outside_east": spread, "south_first_and_fourth": south4},
    }
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("places", "dealer", "placement_by_value", "lead", "ranges")}, indent=1))
    print(json.dumps(out["you"]["by_place"]), json.dumps(out["you"]["outside_east"]))


if __name__ == "__main__":
    main()
