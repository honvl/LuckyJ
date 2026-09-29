#!/usr/bin/env python3
"""When LuckyJ breaks its hand to fold: a safe tile that leaves the hand further from tenpai than it stood.

A fold only breaks the hand when it goes backward. On a draw turn, throwing the drawn tile back leaves the
hand exactly as it stood before the draw, so the shanten of that hand (``prev_sh`` in the cut rows of
``scripts/contrast/vs_callers.py``, ``prev`` in the rows of ``scripts/mine_riichi_folds.py``) is the mark.
Each draw turn facing a threat falls into one of four kinds:

- free: a safe tile (danger 1 or less: genbutsu, a full suji, an honor with two showing) keeps the hand
  where it stood, and it also reaches the best shanten the draw allows. Throwing back a safe draw is one;
- step: a safe tile keeps the hand where it stood, but only a live tile takes the step forward the draw
  offers. Throwing the safe tile passes up the step; it does not go backward;
- break: every safe tile leaves the hand further from tenpai than it stood. Throwing one breaks the hand;
- none: no safe tile at all.

Against callers a tile is safe only when it is safe against every caller at the table, and the threat is
read from chapter 18's grid (``analysis/caller-surface-2026-09-29.json``): each caller's square is the share
of callers in that spot who could win off a discard, and with two or more callers the threat is the chance
that at least one of them can. From the break spots of each of LuckyJ's hands (tenpai, one-shanten,
two-shanten or worse), the share it broke is fitted over that threat, one point per whole percent, with
``fit_series`` (``scripts/mine_safe_tile_timing.py``) between the 2nd and 98th percentiles of the
threat. The same spots in your games are set against that
curve. Riichi spots give the reference, and a regression adds what the hands are worth.

Your break spots are also read against Mortal's policy in the site's replays (``site/replays``), and
with LuckyJ's manifest the script adds what a ron cost the discarder, by the winner's hand (run it from
the directory the manifest's paths start from; without the manifest it keeps the values OUT.json has).

usage: mine_break_folds.py LJ_CUTS.jsonl YOUR_CUTS.jsonl LJ_RIICHI.json YOUR_RIICHI.json OUT.json [LJ_MANIFEST.json]
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_caller_surface as grid  # noqa: E402
import mine_safe_tile_timing as timing  # noqa: E402

HANDS = {"tenpai": 0, "one": 1, "far": 2}
KINDS = ("free", "step", "break", "none")
EDGE = 2  # each hand's fit spans the threats between these percentiles of its spots, where the data lies


def hand_of(shanten: int) -> str:
    return "tenpai" if shanten == 0 else "one" if shanten == 1 else "far"


def kind_of(prev: int, best: int, safe_shanten: list[int]) -> str:
    if not safe_shanten:
        return "none"
    if min(safe_shanten) > prev:
        return "break"
    return "step" if best < prev and min(safe_shanten) > best else "free"


def square(calls: int, run: int, discard: int, data: dict) -> float | None:
    if not 1 <= discard <= grid.MAX_DISCARD:
        return None
    cell = data["grid"]["can_win"][f"{min(calls, 3)}-{min(run, 3)}"]["cells"][str(discard)]
    return grid.value(cell, data["min_readings"])


def caller_spots(path: str, who: str, data: dict) -> list[dict]:
    """One spot per draw-turn discard against callers, with every tile's worst danger over the callers."""
    turns = defaultdict(list)
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["who"] == who and r["prev_sh"] is not None:
                turns[(r["g"], r["li"], r["s"], r["t"])].append(r)
    spots = []
    for key, rows in turns.items():
        first = rows[0]
        danger, after = defaultdict(int), {}
        for r in rows:
            for tile, d, sh, _ in r["opts"]:
                danger[tile] = max(danger[tile], d)
                after[tile] = sh
        prev, best = first["prev_sh"], first["best_sh"]
        kind = kind_of(prev, best, [after[t] for t in after if danger[t] <= 1])
        squares = [square(r["n_melds"], r["ts_run"], r["q_turn"], data) for r in rows]
        threat = None
        if all(v is not None for v in squares):
            threat = 100 * (1 - math.prod(1 - v / 100 for v in squares))
        main = max(rows, key=lambda r: (r["n_melds"], r["q_turn"]))
        spots.append({
            "g": key[0], "li": key[1], "t": key[3], "hand": hand_of(prev), "kind": kind,
            "safe": danger[first["tile"]] <= 1, "went_back": first["my_sh"] > prev, "callers": len(rows),
            "threat": threat, "calls": main["n_melds"], "discard": main["q_turn"],
            "dora_pon": any(r["q_meld_dora"] >= 3 for r in rows), "dealer_caller": any(r["q_dealer"] for r in rows),
            "my_dora": first["my_dora"], "me_dealer": first["me_dealer"], "closed": first["closed"],
            "tile": first["tile"], "kyoku": first["kyoku"],
        })
    return spots


def riichi_spots(path: str) -> list[dict]:
    """Draw turns facing exactly one riichi, from mine_riichi_folds.py rows."""
    spots = []
    for r in json.loads(Path(path).read_text())["rows"]:
        if r["prev"] is None or r["riichis"] != 1:
            continue
        safe_best = r["safe_best"]
        spots.append({"hand": hand_of(r["prev"]), "kind": kind_of(r["prev"], r["best"], [] if safe_best is None else [safe_best]),
                      "safe": not r["push"], "turn": r["turn"]})
    return spots


def rate(spots: list[dict]) -> dict:
    n = len(spots)
    k = sum(s["safe"] for s in spots)
    return {"spots": n, "safe": k, "pct": round(100 * k / n, 1) if n else None}


def kinds_table(spots: list[dict]) -> dict:
    out = {}
    for hand in HANDS:
        out[hand] = {kind: rate([s for s in spots if s["hand"] == hand and s["kind"] == kind]) for kind in KINDS}
    return out


def curve(spots: list[dict]) -> dict:
    """The share of break spots LuckyJ broke, one point per whole percent of threat, and its fitted curve."""
    points = []
    for x in range(0, 100):
        c = [s for s in spots if int(s["threat"]) == x]
        points.append({"turn": x, "lj_k": sum(s["safe"] for s in c), "lj_n": len(c), "naga_k": 0, "naga_n": 0})
    threats = sorted(s["threat"] for s in spots)
    span = (int(threats[len(threats) * EDGE // 100]), int(threats[len(threats) * (100 - EDGE) // 100 - 1]))
    fit = timing.fit_series(points, "lj", span[0], span[1])
    at = {round(t, 1): (p, lo, hi) for t, p, lo, hi in fit["grid"]}
    return {"spots": len(spots), "broke": sum(s["safe"] for s in spots), "range": list(span), "df": fit["df"],
            "points": [[p["turn"], p["lj_k"], p["lj_n"]] for p in points if p["lj_n"]],
            "grid": fit["grid"], "at": {str(x): at[float(x)] for x in range(span[0], span[1] + 1)}}


def fitted(c: dict, threat: float) -> float:
    lo, hi = c["range"]
    x = min(max(threat, lo), hi)
    grid_x = [g[0] for g in c["grid"]]
    i = min(range(len(grid_x)), key=lambda j: abs(grid_x[j] - x))
    return c["grid"][i][1] / 100


def logit_fit(x: list[list[float]], y: list[int]) -> dict:
    """Plain logistic regression by Newton steps; returns coefficients and standard errors."""
    beta = [0.0] * len(x[0])
    for _ in range(60):
        xtwx = [[0.0] * len(beta) for _ in beta]
        grad = [0.0] * len(beta)
        for row, yi in zip(x, y):
            p = 1 / (1 + math.exp(-sum(b * v for b, v in zip(beta, row))))
            w = p * (1 - p)
            for i, vi in enumerate(row):
                grad[i] += (yi - p) * vi
                for j, vj in enumerate(row):
                    xtwx[i][j] += w * vi * vj
        step = timing._solve(xtwx, grad)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-9:
            break
    cov = timing._inverse(xtwx)
    return {"beta": [round(b, 3) for b in beta], "se": [round(math.sqrt(cov[i][i]), 3) for i in range(len(beta))]}


VALUE_TERMS = ("threat", "own_turn", "dora_pon", "dealer_caller", "my_dora", "me_dealer")


def value_model(spots: list[dict]) -> dict:
    rows = [[1.0, s["threat"] / 100, s["t"] / 10, float(s["dora_pon"]), float(s["dealer_caller"]),
             float(min(s["my_dora"], 3)), float(s["me_dealer"])] for s in spots]
    fit = logit_fit(rows, [int(s["safe"]) for s in spots])
    return {name: {"beta": b, "se": se} for name, b, se in zip(("const",) + VALUE_TERMS, fit["beta"], fit["se"])}


def split_rates(spots: list[dict], hot: float) -> dict:
    hot_spots = [s for s in spots if s["threat"] >= hot]
    return {
        "all": rate(hot_spots),
        "dora_pon": rate([s for s in hot_spots if s["dora_pon"]]),
        "no_dora_pon": rate([s for s in hot_spots if not s["dora_pon"]]),
        "dealer_caller": rate([s for s in hot_spots if s["dealer_caller"]]),
        "my_dora_0": rate([s for s in hot_spots if s["my_dora"] == 0]),
        "my_dora_2plus": rate([s for s in hot_spots if s["my_dora"] >= 2]),
    }


TILE_NAMES = {41: "E", 42: "S", 43: "W", 44: "N", 45: "P", 46: "F", 47: "C"}


def replay_name(tile: int) -> str:
    return TILE_NAMES.get(tile) or f"{tile % 10}{'mps'[tile // 10 - 1]}"


def mortal_view(spots: list[dict], cuts: str) -> dict:
    """Mortal's policy at your break spots, from the site's replays: the weight it put on the safe tiles."""
    danger = defaultdict(lambda: defaultdict(int))
    with open(cuts) as f:
        for line in f:
            r = json.loads(line)
            if r["who"] == "You" and r["prev_sh"] is not None:
                for tile, d, _, _ in r["opts"]:
                    key = (r["g"], r["li"], r["t"])
                    danger[key][tile] = max(danger[key][tile], d)
    weights = defaultdict(list)
    for s in spots:
        if s["kind"] != "break" or s["threat"] is None:
            continue
        path = Path(__file__).resolve().parents[1] / "site" / "replays" / f"{s['g']}.json"
        if not path.exists():
            continue
        game = json.loads(path.read_text())
        hand, hero, turn, turns = game["hands"][s["li"]], game["hero"], 0, []
        for e in hand["ev"]:
            if e[1] == hero and ((e[0] == "t" and len(e) < 4) or e[0] in ("c", "p", "m")):
                turn += 1
            turns.append(turn)
        cuts_here = [a for a in hand["ai"] if turns[a["i"]] == s["t"] and a["p"][0][0] not in ("pass",)
                     and not a["p"][0][0].startswith(("chi", "pon", "kan", "riichi"))]
        if not cuts_here:
            continue
        safe = {replay_name(t) for t, d in danger[(s["g"], s["li"], s["t"])].items() if d <= 1}
        weight = sum(p for t, p in cuts_here[-1]["p"] if t.replace("r", "") in safe)
        weights[(s["hand"], s["threat"] >= 40)].append(weight)
    return {f"{hand} {'40+' if hot else 'under 40'}": {"spots": len(w), "safe_weight": round(100 * sum(w) / len(w), 1)}
            for (hand, hot), w in sorted(weights.items())}


def ron_values(manifest: str) -> dict:
    """What a ron cost the discarder in LuckyJ's games, by the winner's hand: riichi, open, or closed dama."""
    import tenhou_replay as tr

    paid = defaultdict(list)
    for g in json.loads(Path(manifest).read_text()):
        for log in tr.load_logs(g["file"]):
            game = tr.replay(log)
            for deltas, detail in tr.result_blocks(log[-1]):
                winner, loser = detail[0], detail[1]
                if winner == loser:
                    continue
                player = game["players"][winner]
                kind = ("riichi" if player["riichi_event"] is not None
                        else "open" if any(m["kind"] != "a" for m in player["melds"]) else "dama")
                paid[kind].append(-deltas[loser])
    return {kind: {"wins": len(v), "average": round(sum(v) / len(v))} for kind, v in paid.items()}


def main(lj_cuts: str, your_cuts: str, lj_riichi: str, your_riichi: str, out: str, lj_manifest: str | None = None) -> None:
    data = json.loads(grid.DATA.read_text())
    lj, you = caller_spots(lj_cuts, "LuckyJ", data), caller_spots(your_cuts, "You", data)
    lj_r, you_r = riichi_spots(lj_riichi), riichi_spots(your_riichi)
    result = {
        "definition": __doc__.split("\n\n")[1].strip(),
        "edge_percentile": EDGE,
        "kinds": {
            "LuckyJ": {"one riichi": kinds_table(lj_r), "one caller": kinds_table([s for s in lj if s["callers"] == 1]),
                       "two or more callers": kinds_table([s for s in lj if s["callers"] >= 2])},
            "You": {"one riichi": kinds_table(you_r), "one caller": kinds_table([s for s in you if s["callers"] == 1]),
                    "two or more callers": kinds_table([s for s in you if s["callers"] >= 2])},
        },
        "curves": {}, "yours": {}, "hot": {}, "model": {},
        "riichi_by_turn": {},
    }
    for hand in HANDS:
        breaks = [s for s in lj if s["hand"] == hand and s["kind"] == "break" and s["threat"] is not None]
        c = curve(breaks)
        result["curves"][hand] = c
        mine = [s for s in you if s["hand"] == hand and s["kind"] == "break" and s["threat"] is not None]
        result["yours"][hand] = {"spots": len(mine), "broke": sum(s["safe"] for s in mine),
                                 "expected": round(sum(fitted(c, s["threat"]) for s in mine), 1),
                                 "low_threat": rate([s for s in mine if s["threat"] < 40]),
                                 "low_threat_expected": round(sum(fitted(c, s["threat"]) for s in mine if s["threat"] < 40), 1)}
        if hand != "tenpai":
            result["hot"][hand] = split_rates(breaks, 50)
            result["model"][hand] = value_model(breaks)
        riichi = [s for s in lj_r if s["hand"] == hand and s["kind"] == "break"]
        by_turn = defaultdict(lambda: [0, 0])
        for s in riichi:
            by_turn[min(s["turn"], 18)][0] += s["safe"]
            by_turn[min(s["turn"], 18)][1] += 1
        result["riichi_by_turn"][hand] = {str(t): v for t, v in sorted(by_turn.items())}
    result["mortal"] = mortal_view(you, your_cuts)
    if lj_manifest:
        result["ron_paid"] = ron_values(lj_manifest)
    elif Path(out).exists():
        result["ron_paid"] = json.loads(Path(out).read_text()).get("ron_paid")
    # what was cut when LuckyJ kept a broken-spot hand: the kind of live tile
    result["kept_with"] = dict(Counter(
        ("honor" if s["tile"] >= 41 else "terminal" if s["tile"] % 10 in (1, 9) else "2 to 8")
        for s in lj if s["kind"] == "break" and not s["safe"] and s["hand"] != "tenpai"))
    Path(out).write_text(json.dumps(result, indent=1))
    report(result)


def report(result: dict) -> None:
    for who, tables in result["kinds"].items():
        print(f"== {who}")
        for threat, table in tables.items():
            cells = []
            for hand in HANDS:
                row = table[hand]
                cells.append(f"{hand}: free {row['free']['pct']}% of {row['free']['spots']}, step {row['step']['pct']}% of "
                             f"{row['step']['spots']}, break {row['break']['pct']}% of {row['break']['spots']}")
            print(f"  {threat:20s} " + " | ".join(cells))
    for hand, c in result["curves"].items():
        at = c["at"]
        marks = "  ".join(f"{x}%: {at[str(x)][0]:.1f}" for x in (10, 20, 30, 40, 50, 60, 70, 80, 90) if str(x) in at)
        yours = result["yours"][hand]
        print(f"  {hand:6s} broke {c['broke']} of {c['spots']} (range {c['range']}, df {c['df']}): {marks}")
        print(f"         you broke {yours['broke']} of {yours['spots']}, LuckyJ's curve expects {yours['expected']}; "
              f"below 40%: {yours['low_threat']['safe']} of {yours['low_threat']['spots']}, expects {yours['low_threat_expected']}")
    for hand, hot in result["hot"].items():
        print(f"  {hand} at 50%+: " + "  ".join(f"{k} {v['pct']}% of {v['spots']}" for k, v in hot.items()))
        print("         model: " + "  ".join(f"{k} {v['beta']:+.2f}±{v['se']:.2f}" for k, v in result["model"][hand].items()))
    print("  kept the hand with:", result["kept_with"])
    print("  Mortal's weight on the safe tiles at your break spots:", result["mortal"])
    print("  a ron cost the discarder:", result.get("ron_paid"))


if __name__ == "__main__":
    main(*sys.argv[1:7])
