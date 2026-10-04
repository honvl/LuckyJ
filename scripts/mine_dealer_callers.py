#!/usr/bin/env python3
"""What moves LuckyJ's fold line against a single caller: the dealer, the run of tiles from the wall, a river
that avoids a suit.

Reads the cut rows of ``scripts/contrast/vs_callers.py`` and the acceptance rows of
``scripts/contrast/choices.py --callers``, for LuckyJ's Tokujou games and for your games, the same inputs as
``mine_caller_fold_line.py``, whose real choices it keeps: a safe tile (danger 1 or less) keeps the best shanten,
and so does a live tile with at least as much acceptance. LuckyJ folded when it threw the safe tile.

- curves: against a caller with one call, LuckyJ's share of live cuts at each of the caller's discards, fitted
  with ``fit_series`` over the discards with at least 25 turns, once against the dealer and once against anyone
  else, for a hand two-shanten or worse and for one-shanten; the line is the first discard whose fit is below half.
- effects: a logistic regression of the live cut on a three-knot discard curve plus the dealer, the run (0 to 3)
  and their product, for LuckyJ and for you, and for LuckyJ from the 9th discard on.
- you_vs_lj: your live share against LuckyJ's fitted curve at the same discards.
- suit: every seat's live cuts against a single caller in LuckyJ's games, from the caller's 6th discard. A river
  avoids a suit when it has none of it after six or more discards and the calls are in that suit or honors.
  Hit means the tile was on the caller's wait. Fitted by discard for the avoided suit, the other suits, honors
  and callers whose river shows every suit, plus the odds ratio of the avoided suit against the other suits.
- live_ties: LuckyJ's live cuts against such a river when two live number tiles kept its shanten with as many tiles,
  one in the avoided suit and one not, through the caller's 8th discard and after: which suit it threw.
- tenpai: at tenpai against a single caller (any number of calls), how often LuckyJ threw a safe tile when only
  safe tiles kept the tenpai, and when every safe tile broke it (chapter 19's counts).
- cost: what a ron into a single caller with one call paid the caller, dealer or not.
- squares: chapter 18's "could win" squares for one call, from ``analysis/caller-surface-2026-09-29.json``.
- spot: your 3p in East 4, one honba, of the 3 October 23:38 game.

usage: mine_dealer_callers.py LJ_CUTS LJ_CHOICES YOU_CUTS YOU_CHOICES OUT.json
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mine_caller_fold_line as fl  # noqa: E402
import mine_safe_tile_timing as timing  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SURFACE = ROOT / "analysis" / "caller-surface-2026-09-29.json"
MAX_DISCARD = 18
MIN_SPOTS = 25
SUIT_MIN = 80  # live cuts a discard needs to join a suit curve
KNOTS = [0.0, 1 / 3, 2 / 3, 1.0]
HANDS = {"far": lambda sh: sh >= 2, "one": lambda sh: sh == 1}
SPOT = {"g": "261004-663f0de9-cfe1-4fa3-b8b2-48153236dc62", "li": 5, "t": 7}
# the East 4 dealer's river: (discard, run) after each of their discards from the call on, and two what-ifs
SQUARES = ((3, 1), (4, 0), (5, 0), (6, 1), (7, 2), (8, 3), (8, 0), (10, 0), (10, 3), (12, 0), (12, 3))


def avoided_suit(r: dict) -> int | None:
    """The suit a caller's river avoids: none of it in six or more discards, every call in it or in honors."""
    if r["q_turn"] < 6:
        return None
    empty = [k for k in (1, 2, 3) if r["q_river"][k - 1] == 0]
    if len(empty) != 1 or not set(r["q_meld_suits"]) <= {empty[0], 4}:
        return None
    return empty[0]


def acceptance(path: str) -> dict:
    out = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            out[(r["g"], r["li"], r["t"])] = {c["b"]: (c["sh"], c["uk"]) for c in r["cands"]}
    return out


def cut_rows(path: str, who: str | None, accept: dict | None = None) -> list[dict]:
    """Discards against a single caller, with the real-choice kind when acceptance is given."""
    rows = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if (who and r["who"] != who) or r["n_callers"] != 1 or not 1 <= r["q_turn"] <= MAX_DISCARD:
                continue
            r["avoided"] = avoided_suit(r)
            r["live"] = int(r["danger"] >= 2)
            if accept is not None:
                cands = accept.get((r["g"], r["li"], r["t"]))
                if cands is None:
                    continue
                r["kind"] = fl.kind([(danger, sh, cands[b][1]) for b, danger, sh, _ in r["opts"]])
            rows.append(r)
    return rows


def curve(spots: list[dict], key: str = "live", minimum: int = MIN_SPOTS, lo_turn: int = 1) -> dict:
    turns = list(range(lo_turn, MAX_DISCARD + 1))
    k = [sum(s[key] for s in spots if s["q_turn"] == t) for t in range(1, MAX_DISCARD + 1)]
    n = [sum(1 for s in spots if s["q_turn"] == t) for t in range(1, MAX_DISCARD + 1)]
    points = [{"turn": t, "lj_k": k[t - 1], "lj_n": n[t - 1], "naga_k": 0, "naga_n": 0} for t in turns]
    span = timing._longest_run(turns, {p["turn"]: p["lj_n"] for p in points}, minimum)
    out = {"spots": len(spots), "k": k, "n": n, "range": None, "df": None, "crossings_50": [], "line": None,
           "grid": [], "at": {}}
    if not span or span[1] - span[0] < 3:
        return out
    fit = timing.fit_series(points, "lj", span[0], span[1])
    grid = [[round(t, 2), round(p, 2), round(lo, 2), round(hi, 2)] for t, p, lo, hi in fit["grid"]]
    down = [c["turn"] for c in fit["crossings_50"] if c["direction"] == "down"]
    out.update(range=list(span), df=fit["df"], crossings_50=[{"turn": round(c["turn"], 2), "direction": c["direction"]}
                                                           for c in fit["crossings_50"]],
               line=math.ceil(down[0]) if down and grid[0][1] >= 50 else None, grid=grid,
               at={str(int(round(g[0]))): g[1:] for g in grid if abs(g[0] - round(g[0])) < 1e-6})
    return out


def logit(spots: list[dict], extras: dict) -> dict:
    """Coefficients (log-odds of the live cut) of each extra on top of a three-knot discard curve."""
    rows = [timing._ns_row((s["q_turn"] - 1) / (MAX_DISCARD - 1), KNOTS) + [f(s) for f in extras.values()] for s in spots]
    fit = timing._logit_fit(rows, [s["live"] for s in spots], [1] * len(spots))
    cov = timing._inverse(fit["xtwx"])
    first = len(fit["beta"]) - len(extras)
    return {"spots": len(spots), **{name: {"beta": round(fit["beta"][first + i], 3),
                                           "se": round(math.sqrt(cov[first + i][first + i]), 3)}
                                    for i, name in enumerate(extras)}}


EXTRAS = {
    "dealer": lambda s: int(s["q_dealer"]),
    "run": lambda s: min(s["ts_run"], 3),
    "dealer_x_run": lambda s: int(s["q_dealer"]) * min(s["ts_run"], 3),
}


def against(spots: list[dict], fitted: dict) -> dict:
    """Live share of these turns against what a fitted curve predicts at the same discards."""
    chosen = [s for s in spots if str(s["q_turn"]) in fitted["at"]]
    if not chosen:
        return {"spots": 0}
    expected = sum(fitted["at"][str(s["q_turn"])][0] for s in chosen) / len(chosen)
    return {"spots": len(chosen), "live": round(100 * sum(s["live"] for s in chosen) / len(chosen), 1),
            "luckyj": round(expected, 1)}


def real_choices(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["kind"] in fl.CHOICE and r["n_melds"] == 1]


def main(lj_cuts: str, lj_choices: str, you_cuts: str, you_choices: str, out: str) -> None:
    lj = real_choices(cut_rows(lj_cuts, "LuckyJ", acceptance(lj_choices)))
    you_rows = cut_rows(you_cuts, "You", acceptance(you_choices))
    you = real_choices(you_rows)
    result = {"definition": __doc__.split("\n\n")[1].replace("\n", " "), "min_spots": MIN_SPOTS, "curves": {},
              "ties": {}, "effects": {"LuckyJ": {}, "You": {}, "LuckyJ_from_9": {}}, "you_vs_lj": {}}
    for hand, keep in HANDS.items():
        mine = [s for s in lj if keep(s["best_sh"])]
        yours = [s for s in you if keep(s["best_sh"])]
        result["curves"][hand], result["ties"][hand], result["you_vs_lj"][hand] = {}, {}, {}
        for who, dealer in (("dealer", True), ("other", False)):
            side = [s for s in mine if s["q_dealer"] == dealer]
            result["curves"][hand][who] = curve(side)
            ties = curve([s for s in side if s["kind"] == "tie"])
            result["ties"][hand][who] = {k: ties[k] for k in ("spots", "range", "crossings_50", "line", "at")}
            result["you_vs_lj"][hand][who] = against([s for s in yours if s["q_dealer"] == dealer],
                                                     result["curves"][hand][who])
        result["effects"]["LuckyJ"][hand] = logit(mine, EXTRAS)
        result["effects"]["You"][hand] = logit(yours, EXTRAS)
        result["effects"]["LuckyJ_from_9"][hand] = logit([s for s in mine if s["q_turn"] >= 9],
                                                         {k: EXTRAS[k] for k in ("dealer", "run")})

    every = cut_rows(lj_cuts, None)
    live = [r for r in every if r["live"] and 6 <= r["q_turn"] <= MAX_DISCARD]
    groups = {
        "avoided suit": lambda r: r["avoided"] and r["tile"] < 41 and r["tile"] // 10 == r["avoided"],
        "other suits": lambda r: r["avoided"] and r["tile"] < 41 and r["tile"] // 10 != r["avoided"],
        "honors": lambda r: r["avoided"] and r["tile"] >= 41,
        "every suit shown": lambda r: r["avoided"] is None and r["tile"] < 41,
    }
    result["suit"] = {}
    for name, select in groups.items():
        chosen = [dict(r, hit=int(r["on_wait"])) for r in live if select(r)]
        fitted = curve(chosen, key="hit", minimum=SUIT_MIN, lo_turn=6)
        result["suit"][name] = {"cuts": len(chosen), "hits": sum(r["hit"] for r in chosen), "range": fitted["range"],
                                "at": {t: v for t, v in fitted["at"].items() if t in ("6", "8", "10", "12")}}
    numbers = [r for r in live if r["avoided"] and r["tile"] < 41]
    rows = [timing._ns_row((r["q_turn"] - 6) / 12, KNOTS) + [int(r["tile"] // 10 == r["avoided"])] for r in numbers]
    fit = timing._logit_fit(rows, [int(r["on_wait"]) for r in numbers], [1] * len(numbers))
    se = math.sqrt(timing._inverse(fit["xtwx"])[-1][-1])
    result["suit_odds"] = {"avoided_vs_other": {"beta": round(fit["beta"][-1], 3), "se": round(se, 3),
                                                "ratio": round(math.exp(fit["beta"][-1]), 2)}}
    pool = [r for r in live if r["tile"] < 41 and (r["avoided"] is None or r["tile"] // 10 == r["avoided"])]
    rows = [timing._ns_row((r["q_turn"] - 6) / 12, KNOTS) + [int(bool(r["avoided"]))] for r in pool]
    fit = timing._logit_fit(rows, [int(r["on_wait"]) for r in pool], [1] * len(pool))
    se = math.sqrt(timing._inverse(fit["xtwx"])[-1][-1])
    result["suit_odds"]["avoided_vs_every_suit_shown"] = {"beta": round(fit["beta"][-1], 3), "se": round(se, 3),
                                                          "ratio": round(math.exp(fit["beta"][-1]), 2)}

    accept = acceptance(lj_choices)
    ties = {"through 8": {"avoided": 0, "other": 0}, "after 8": {"avoided": 0, "other": 0}}
    for r in cut_rows(lj_cuts, "LuckyJ"):
        x = r["avoided"]
        cands = accept.get((r["g"], r["li"], r["t"]))
        if not x or not r["live"] or cands is None or r["tile"] >= 41:
            continue
        best = min(sh for _, _, sh, _ in r["opts"])
        live = [(b, cands[b][1]) for b, danger, sh, _ in r["opts"] if sh == best and danger >= 2 and b < 41]
        inside = [uk for b, uk in live if b // 10 == x]
        outside = [uk for b, uk in live if b // 10 != x]
        if not inside or not outside or max(inside) != max(outside) or r["tile"] not in [b for b, _ in live]:
            continue
        band = "through 8" if r["q_turn"] <= 8 else "after 8"
        ties[band]["avoided" if r["tile"] // 10 == x else "other"] += 1
    result["live_ties"] = {band: {**v, "other_share": round(100 * v["other"] / (v["avoided"] + v["other"]), 1)}
                           for band, v in ties.items()}
    tenpai = [r for r in cut_rows(lj_cuts, "LuckyJ", accept) if r["best_sh"] == 0]
    result["tenpai"] = {}
    for kind in ("only safe tiles keep shanten", "safe tile costs shanten"):
        chosen = [r for r in tenpai if r["kind"] == kind]
        result["tenpai"][kind] = {"turns": len(chosen), "safe": round(100 * sum(1 - r["live"] for r in chosen) / len(chosen), 1)}

    result["cost"] = {}
    for who, dealer in (("dealer", True), ("other", False)):
        hits = [r for r in every if r["dealt"] and r["on_wait"] and r["q_won"] and r["n_melds"] == 1 and r["q_dealer"] == dealer]
        result["cost"][who] = {"rons": len(hits), "average": round(sum(r["q_gain"] for r in hits) / len(hits))}

    surface = json.loads(SURFACE.read_text())["grid"]["can_win"]
    result["squares"] = {f"{d}-{run}": surface[f"1-{run}"]["cells"][str(d)]["fit"] for d, run in SQUARES}

    spot = next(r for r in you_rows if all(r[k] == v for k, v in SPOT.items()))
    result["spot"] = {k: spot[k] for k in ("q_turn", "ts_run", "q_pattern", "q_dealer", "q_tenpai", "on_wait", "best_sh",
                                           "kind", "avoided", "q_river", "label")}
    Path(out + ".tmp").write_text(json.dumps(result, indent=1) + "\n")
    os.replace(out + ".tmp", out)
    for hand in HANDS:
        for who in ("dealer", "other"):
            c = result["curves"][hand][who]
            print(f"{hand} vs {who}: {c['spots']} turns, range {c['range']}, line {c['line']}, crossings {c['crossings_50']}")
    print(json.dumps({k: result[k] for k in ("ties", "effects", "you_vs_lj", "suit", "suit_odds", "live_ties", "tenpai", "cost", "squares", "spot")},
                     indent=None)[:3000])


if __name__ == "__main__":
    main(*sys.argv[1:6])
