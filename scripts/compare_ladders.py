#!/usr/bin/env python3
"""Is Saint 3 -> Celestial (Jade) harder than 7-dan -> 8-dan (Houou)? One Mortal scale for both rooms.

Inputs are two ``mine_ladder_skill.py`` outputs: the user's Jade games (every seat) and a sample of recent Houou
hanchan (every seat). Steps:

1. Skill = mean ln p(taken action) under the local Mortal policy, pooled over a group's decisions. Groups: Jade
   opponents by rank (Master 1-3, Saint 1-3), the user, the Jade field (all opponents), Houou seats by dan, the Houou
   field. Standard errors by bootstrapping games.
2. Places per unit of skill (beta). (a) Mahjong Soul: Saints place 0.1443 better than Masters at the same table
   (``mine_table_strength.py``, 1,729 mixed tables), divided by the Saint-minus-Master skill gap. (b) Tenhou: the
   within-table place difference per dan step in this sample, divided by the skill gap per dan step.
3. A Thurstone placement model: performance = k * skill + N(0, 1), places by performance. k is set so a skill gap
   moves the expected place by beta, then first-to-fourth rates for any player against any field follow.
4. The climbs as random walks, one attempt each: Houou 7-dan 1,400 -> 2,800 points, +90/+45/0/-120, demoted below 0;
   Jade Saint 3 4,500 -> 9,000, +144/+65/-9/-272 (the user's measured Saint 3 Jade South averages), demoted below 0.

    .venv/bin/python scripts/compare_ladders.py data/ladder_skill/jade.jsonl data/ladder_skill/houou.jsonl OUT.json
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict

import numpy as np

USER = "Honver"
SAINT_MINUS_MASTER_PLACE = -0.1443  # analysis/table-strength-2026-11-19.json, within_table
SAINT_MINUS_MASTER_SE = 0.0382
HOUOU_7DAN = {"start": 1400, "goal": 2800, "pts": [90, 45, 0, -120]}
JADE_S3 = {"start": 4500, "goal": 9000, "pts": [144, 65, -9, -272]}
DAN_STEP = {"七段": 7, "八段": 8, "九段": 9, "十段": 10, "天鳳": 11}
RNG = np.random.default_rng(20261120)


def load(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    ok = [r for r in rows if "error" not in r and r.get("n", 0) >= 20]
    bad = len(rows) - len(ok)
    return ok, bad


def jade_tier(r):
    if r["name"] == USER:
        return "user"
    m = re.match(r"雀(豪|聖)★(\d)", r["dan"] or "")
    if not m:
        return None
    return ("Master " if m.group(1) == "豪" else "Saint ") + m.group(2)


def ladder_step(tier):
    """Master 1 = 0 ... Saint 3 = 5, as in mine_matchmaking_streaks.ladder."""
    kind, n = tier.split()
    return (0 if kind == "Master" else 3) + int(n) - 1


METRIC = ("logp", "n")  # --discards switches to ("logp_d", "nd")


def pooled(rows, key=None, n=None):
    key, n = key or METRIC[0], n or METRIC[1]
    return sum(r[key] for r in rows) / sum(r[n] for r in rows)


def boot(rows_by_game, fn, reps=400):
    games = list(rows_by_game)
    vals = []
    for _ in range(reps):
        pick = RNG.integers(0, len(games), len(games))
        rs = [r for i in pick for r in rows_by_game[games[i]]]
        try:
            vals.append(fn(rs))
        except ZeroDivisionError:
            pass
    return float(np.std(vals, ddof=1))


def by_game(rows):
    g = defaultdict(list)
    for r in rows:
        g[r["file"]].append(r)
    return g


def group_stats(rows, select, label):
    sel = [r for r in rows if select(r)]
    return {"group": label, "seats": len(sel), "decisions": int(sum(r["n"] for r in sel)),
            "skill": round(pooled(sel), 4),
            "skill_se": round(boot(by_game(sel), pooled), 4),
            "top1": round(sum(r["top"] for r in sel) / sum(r["n"] for r in sel), 4),
            "under10": round(sum(r["low"] for r in sel) / sum(r["n"] for r in sel), 4),
            "place": round(float(np.mean([r["place"] for r in sel])), 3),
            "first": round(float(np.mean([r["place"] == 1 for r in sel])), 3),
            "fourth": round(float(np.mean([r["place"] == 4 for r in sel])), 3)}


def saint_master_gap(rows):
    opp = [r for r in rows if jade_tier(r) not in (None, "user")]
    s = [r for r in opp if jade_tier(r).startswith("Saint")]
    m = [r for r in opp if jade_tier(r).startswith("Master")]
    return pooled(s) - pooled(m)


def houou_within_table(rows):
    """Place relative to the table against dan relative to the table, and skill against dan."""
    x, y = [], []
    for g in by_game(rows).values():
        if len(g) != 4:
            continue
        d = [DAN_STEP.get(r["dan"], np.nan) for r in g]
        if any(np.isnan(d)):
            continue
        md, mp = np.mean(d), np.mean([r["place"] for r in g])
        for r, di in zip(g, d):
            x.append(di - md)
            y.append(r["place"] - mp)
    x, y = np.array(x), np.array(y)
    b = float(x @ y / (x @ x))
    e = y - b * x
    se = float(np.sqrt(np.sum((x * e) ** 2)) / (x @ x))
    return b, se


def skill_per_dan(rows):
    xs = np.array([DAN_STEP[r["dan"]] for r in rows if r["dan"] in DAN_STEP], float)
    ys = np.array([r[METRIC[0]] / r[METRIC[1]] for r in rows if r["dan"] in DAN_STEP])
    ws = np.array([r[METRIC[1]] for r in rows if r["dan"] in DAN_STEP], float)
    X = np.column_stack([np.ones_like(xs), xs])
    W = np.diag(ws) if len(ws) < 3000 else None
    if W is not None:
        beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ ys)
    else:
        beta = np.linalg.solve((X * ws[:, None]).T @ X, (X * ws[:, None]).T @ ys)
    return float(beta[1])


def houou_player_beta(rows, min_games=4):
    """Places per unit of skill from Houou players seen in several games: each seat's place against the player's
    skill in their other games, shrunk toward the field by its reliability (so the slope is not attenuated).
    With three random opponents E[place] = 2.5 - 0.75 * beta * (skill - field)."""
    by = defaultdict(list)
    for r in rows:
        by[r["name"]].append(r)
    x_all = np.array([r[METRIC[0]] / r[METRIC[1]] for r in rows])
    field = x_all.mean()
    multi = [v for v in by.values() if len(v) >= 2]
    sw2 = float(np.mean([np.var([r[METRIC[0]] / r[METRIC[1]] for r in v], ddof=1) for v in multi]))
    pm = np.array([np.mean([r[METRIC[0]] / r[METRIC[1]] for r in v]) for v in multi])
    pn = np.array([len(v) for v in multi])
    tau2 = float(np.var(pm, ddof=1) - np.mean(sw2 / pn))
    X, Y, P = [], [], []
    for name, v in by.items():
        if len(v) < min_games:
            continue
        vals = np.array([r[METRIC[0]] / r[METRIC[1]] for r in v])
        lam = tau2 / (tau2 + sw2 / (len(v) - 1))
        for i, r in enumerate(v):
            X.append(lam * ((vals.sum() - vals[i]) / (len(v) - 1) - field))
            Y.append(r["place"])
            P.append(name)
    X, Y = np.array(X), np.array(Y)
    A = np.column_stack([np.ones_like(X), X])
    b = np.linalg.lstsq(A, Y, rcond=None)[0]
    e = Y - A @ b
    # standard error clustered by player
    inv = np.linalg.inv(A.T @ A)
    meat = np.zeros((2, 2))
    groups = defaultdict(list)
    for i, name in enumerate(P):
        groups[name].append(i)
    for idx in groups.values():
        u = A[idx].T @ e[idx]
        meat += np.outer(u, u)
    se = float(np.sqrt((inv @ meat @ inv)[1, 1]))
    return {"players": len(groups), "seats": len(X), "per_game_sd": round(math.sqrt(sw2), 4),
            "between_player_sd": round(math.sqrt(max(tau2, 0)), 4),
            "beta": round(-float(b[1]) / 0.75, 3), "beta_se": round(se / 0.75, 3)}


# --- Thurstone placement model -------------------------------------------------------------------------------------

def phi_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def expected_place(k, s, others):
    return 1 + sum(phi_cdf(k * (o - s) / math.sqrt(2)) for o in others)


def k_for_beta(beta, field):
    """k such that two seats at one table, Delta apart in skill, are beta * Delta apart in expected place."""
    d = 0.01
    lo, hi = 1e-3, 500.0
    for _ in range(100):
        k = (lo + hi) / 2
        a = expected_place(k, field + d, [field - d, field, field])
        b = expected_place(k, field - d, [field + d, field, field])
        slope = (b - a) / (2 * d)
        if slope < beta:
            lo = k
        else:
            hi = k
    return (lo + hi) / 2


def place_rates(k, s, others, n=400_000):
    perf = np.column_stack([k * s + RNG.standard_normal(n)] + [k * o + RNG.standard_normal(n) for o in others])
    place = 1 + (perf[:, 1:] > perf[:, [0]]).sum(axis=1)
    return [float(np.mean(place == i)) for i in (1, 2, 3, 4)]


def climb(rates, rule, walkers=40_000, max_games=20_000):
    pts = np.array(rule["pts"], float)
    p = np.array(rates) / sum(rates)
    pos = np.full(walkers, float(rule["start"]))
    done = np.zeros(walkers, int)  # 1 promoted, -1 demoted
    games = np.zeros(walkers, int)
    for t in range(max_games):
        live = done == 0
        if not live.any():
            break
        pos[live] += pts[RNG.choice(4, size=live.sum(), p=p)]
        games[live] += 1
        done[live & (pos >= rule["goal"])] = 1
        done[live & (pos < 0)] = -1
    win = done == 1
    return {"p_promote": round(float(win.mean()), 3),
            "median_games_if_promoted": int(np.median(games[win])) if win.any() else None,
            "ev_per_game": round(float(p @ pts), 2)}


def main():
    global METRIC
    if "--discards" in sys.argv:
        sys.argv.remove("--discards")
        METRIC = ("logp_d", "nd")
    jade, jbad = load(sys.argv[1])
    hou, hbad = load(sys.argv[2])
    out = {"inputs": {"jade_seats": len(jade), "jade_skipped": jbad, "houou_seats": len(hou), "houou_skipped": hbad,
                      "jade_games": len(by_game(jade)), "houou_games": len(by_game(hou))}}

    groups = []
    for t in ["Master 1", "Master 2", "Master 3", "Saint 1", "Saint 2", "Saint 3"]:
        sel = [r for r in jade if jade_tier(r) == t]
        if sel:
            groups.append(group_stats(jade, lambda r, t=t: jade_tier(r) == t, f"Jade {t}"))
    groups.append(group_stats(jade, lambda r: jade_tier(r) not in (None, "user"), "Jade field (your opponents)"))
    groups.append(group_stats(jade, lambda r: jade_tier(r) == "user", "You (Jade)"))
    for d in DAN_STEP:
        if any(r["dan"] == d for r in hou):
            groups.append(group_stats(hou, lambda r, d=d: r["dan"] == d, f"Houou {d}"))
    groups.append(group_stats(hou, lambda r: True, "Houou field"))
    out["groups"] = groups
    G = {g["group"]: g for g in groups}

    # rank-step scale on Mahjong Soul: skill per Master1..Saint3 step, to name the Houou field in Mahjong Soul ranks
    opp = [r for r in jade if jade_tier(r) not in (None, "user")]
    xs = np.array([ladder_step(jade_tier(r)) for r in opp], float)
    ys = np.array([r[METRIC[0]] / r[METRIC[1]] for r in opp])
    ws = np.array([r[METRIC[1]] for r in opp], float)
    X = np.column_stack([np.ones_like(xs), xs])
    a0, a1 = np.linalg.solve((X * ws[:, None]).T @ X, (X * ws[:, None]).T @ ys)
    out["msoul_skill_per_rank_step"] = round(float(a1), 4)
    out["houou_field_in_msoul_steps"] = round(float((G["Houou field"]["skill"] - a0) / a1), 2)
    out["user_in_msoul_steps"] = round(float((G["You (Jade)"]["skill"] - a0) / a1), 2)
    out["jade_field_in_msoul_steps"] = round(float((G["Jade field (your opponents)"]["skill"] - a0) / a1), 2)

    # beta: places per unit of skill
    gap = saint_master_gap(jade)
    gap_se = boot(by_game(jade), saint_master_gap)
    beta_ms = -SAINT_MINUS_MASTER_PLACE / gap
    beta_ms_se = beta_ms * math.hypot(SAINT_MINUS_MASTER_SE / SAINT_MINUS_MASTER_PLACE, gap_se / gap)
    place_per_dan, place_per_dan_se = houou_within_table(hou)
    spd = skill_per_dan(hou)
    beta_th = -place_per_dan / spd if spd else float("nan")
    out["calibration"] = {
        "saint_minus_master_skill": round(gap, 4), "saint_minus_master_skill_se": round(gap_se, 4),
        "beta_msoul": round(beta_ms, 3), "beta_msoul_se": round(beta_ms_se, 3),
        "houou_place_per_dan_step": round(place_per_dan, 4), "houou_place_per_dan_step_se": round(place_per_dan_se, 4),
        "houou_skill_per_dan_step": round(spd, 4), "beta_tenhou": round(beta_th, 3),
        "beta_msoul_rank_steps": round(0.0527 / a1, 3),  # 0.0527 places per rank step, table-strength report
        "beta_houou_players": houou_player_beta(hou)}

    fields = {"houou": G["Houou field"]["skill"], "jade": G["Jade field (your opponents)"]["skill"]}
    out["field_gap_houou_minus_jade"] = round(fields["houou"] - fields["jade"], 4)
    rules = {"houou": HOUOU_7DAN, "jade": JADE_S3}
    scen = {}
    for bname, beta in [("msoul", beta_ms), ("tenhou", beta_th)]:
        if not (beta > 0):
            continue
        res = {}
        k = {room: k_for_beta(beta, f) for room, f in fields.items()}
        res["k"] = {room: round(v, 2) for room, v in k.items()}
        # the user, twice: skill as Mortal measures it, and the skill that would give the user's real Jade places
        su = G["You (Jade)"]["skill"]
        actual = G["You (Jade)"]["place"]
        lo, hi = fields["jade"] - 1, fields["jade"] + 1
        for _ in range(60):
            mid = (lo + hi) / 2
            if expected_place(k["jade"], mid, [fields["jade"]] * 3) > actual:
                lo = mid
            else:
                hi = mid
        s_res = (lo + hi) / 2
        res["you_predicted_jade_place_from_mortal"] = round(expected_place(k["jade"], su, [fields["jade"]] * 3), 3)
        res["you_actual_jade_place"] = actual
        res["you_skill_from_results"] = round(s_res, 4)
        for tag, s in (("mortal", su), ("results", s_res)):
            for room in ("houou", "jade"):
                rates = place_rates(k[room], s, [fields[room]] * 3)
                res[f"you_{tag}_in_{room}"] = {"rates": [round(x, 3) for x in rates],
                                               "mean_place": round(sum((i + 1) * x for i, x in enumerate(rates)), 3),
                                               **climb(rates, rules[room])}
        # a grid of skills: edge over the Jade field in skill units
        grid = []
        for edge in np.arange(-0.05, 0.4001, 0.025):
            s = fields["jade"] + edge
            row = {"skill": round(float(s), 4), "edge_over_jade_field": round(float(edge), 3)}
            for room in ("houou", "jade"):
                rates = place_rates(k[room], s, [fields[room]] * 3, n=200_000)
                row[room] = {"mean_place": round(sum((i + 1) * x for i, x in enumerate(rates)), 3),
                             **climb(rates, rules[room], walkers=8_000)}
            grid.append(row)
        res["grid"] = grid
        for room in ("houou", "jade"):
            xs = [r["skill"] for r in grid]
            ps = [r[room]["p_promote"] for r in grid]
            thr = next((xs[i - 1] + (0.5 - ps[i - 1]) * (xs[i] - xs[i - 1]) / (ps[i] - ps[i - 1])
                        for i in range(1, len(ps)) if ps[i - 1] < 0.5 <= ps[i]), None)
            res[f"skill_for_even_odds_{room}"] = round(thr, 4) if thr is not None else None
            res[f"skill_for_even_odds_{room}_msoul_steps"] = round((thr - a0) / a1, 2) if thr is not None else None
        scen[bname] = res
    out["scenarios"] = scen
    json.dump(out, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "scenarios"}, ensure_ascii=False, indent=1))
    for b, res in scen.items():
        print(f"\n== beta from {b}: k {res['k']}")
        print({k: v for k, v in res.items() if k.startswith("skill_for")})
        print("you:", json.dumps({k: v for k, v in res.items() if k.startswith('you')}, ensure_ascii=False))
        for row in res["grid"]:
            print(row["edge_over_jade_field"], row["skill"],
                  "houou", row["houou"]["mean_place"], row["houou"]["ev_per_game"], row["houou"]["p_promote"],
                  "| jade", row["jade"]["mean_place"], row["jade"]["ev_per_game"], row["jade"]["p_promote"])


if __name__ == "__main__":
    main()
