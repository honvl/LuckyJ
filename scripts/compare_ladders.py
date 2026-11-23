#!/usr/bin/env python3
"""Is Saint 3 -> Celestial (Jade) harder than 7 -> 8 dan, or 8 -> 9 dan, in Houou? One Mortal scale for both rooms.

Inputs: two ``mine_ladder_skill.py`` outputs (the user's Jade games and a sample of recent Houou hanchan, every seat)
and a large Jade room sample from amae-koromo (rank level and final score of every seat, no logs).

1. Skill = mean ln p(taken action) under the local Mortal policy, pooled over a group's decisions. Groups: Jade
   opponents by rank, the user, the Jade field (all opponents), Houou seats by dan, the Houou field. Bootstrapped SEs.
2. Places per unit of skill (beta), measured in each room: (a) Jade: the room sample's places per rank step
   (within table, every seat) over the Mortal skill per rank step at the user's tables; (b) Houou: players seen 4+
   times, place against their skill in their other games, shrunk by its reliability, clustered by player. The two
   differ (Mortal agreement separates Houou regulars less than it separates Masters from Saints), so the main result
   gives each room its own beta; ``one_beta`` repeats everything with their inverse-variance mean. The
   Saint-minus-Master ratio and the Houou dan ratio are reported only.
3. A Thurstone placement model: performance = k * skill + N(0, 1); k is set so a skill gap moves the expected place
   by beta. First-to-fourth rates for any player against a room's field follow.
4. One attempt at each climb as a random walk: Houou 7-dan 1,400 -> 2,800 (+90/+45/0/-120), 8-dan 1,600 -> 3,200
   (-135 for 4th; below 0 drops to 7-dan), the chain 7 -> 9 with that drop, Jade Saint 3 4,500 -> 9,000
   (+144/+65/-9/-272, the user's measured Saint 3 Jade South averages). Per climb: the even-odds skill, the odds of
   the user, of the room's average player and of a Houou-average player; then the even-odds skills across one shared
   beta and the beta at which Celestial stops being the harder one.

    .venv/bin/python scripts/compare_ladders.py JADE.jsonl HOUOU.jsonl ROOM_SAMPLE.json OUT.json [--discards]
        [--metric KEY]

``--metric KEY`` reads another per-seat sum as the skill statistic (its discard version is ``KEY_d``): rows scored with
a value-head model (``mine_ladder_skill.py --qmodel``) carry ``lp06``, ln p of the taken action at the project's
softmax temperature.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict

import numpy as np

USER = "Honver"
HOUOU_7DAN = {"start": 1400, "goal": 2800, "pts": [90, 45, 0, -135]}  # corrected 23 Nov 2026 (was -120, the 6-dan cost)
HOUOU_8DAN = {"start": 1600, "goal": 3200, "pts": [90, 45, 0, -150]}  # corrected 23 Nov 2026 (was -135)
JADE_S3 = {"start": 4500, "goal": 9000, "pts": [144, 65, -9, -272]}
LEVEL_STEP = {10401: 0, 10402: 1, 10403: 2, 10501: 3, 10502: 4, 10503: 5}  # amae-koromo level ids
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


def climb(rates, levels, walkers=40_000, max_games=30_000):
    """One attempt up a chain of levels. Falling below 0 on the first level ends the attempt; on a later level it
    sends the walker to the start of the level below (Tenhou's demotion from 8-dan to 7-dan)."""
    p = np.array(rates) / sum(rates)
    pts = np.array([lv["pts"] for lv in levels], float)
    starts = np.array([lv["start"] for lv in levels], float)
    goals = np.array([lv["goal"] for lv in levels], float)
    pos = np.full(walkers, starts[0])
    lvl = np.zeros(walkers, int)
    done = np.zeros(walkers, int)  # 1 promoted past the last level, -1 out
    games = np.zeros(walkers, int)
    for _ in range(max_games):
        live = np.flatnonzero(done == 0)
        if not len(live):
            break
        pos[live] += pts[lvl[live], RNG.choice(4, size=len(live), p=p)]
        games[live] += 1
        up = live[pos[live] >= goals[lvl[live]]]
        top = up[lvl[up] == len(levels) - 1]
        done[top] = 1
        mid = up[lvl[up] < len(levels) - 1]
        lvl[mid] += 1
        pos[mid] = starts[lvl[mid]]
        down = live[(pos[live] < 0) & (done[live] == 0)]
        out = down[lvl[down] == 0]
        done[out] = -1
        back = down[lvl[down] > 0]
        lvl[back] -= 1
        pos[back] = starts[lvl[back]]
    win = done == 1
    return {"p_promote": round(float(win.mean()), 3),
            "median_games_if_promoted": int(np.median(games[win])) if win.any() else None,
            "ev_per_game": [round(float(p @ np.array(lv["pts"], float)), 2) for lv in levels]}


LADDERS = {  # name: (room, levels)
    "houou_7to8": ("houou", [HOUOU_7DAN]),
    "houou_8to9": ("houou", [HOUOU_8DAN]),
    "houou_7to9": ("houou", [HOUOU_7DAN, HOUOU_8DAN]),
    "jade_s3_to_celestial": ("jade", [JADE_S3]),
}


def mean_place(rates):
    return sum((i + 1) * x for i, x in enumerate(rates))


def even_odds_skill(k, field, levels, iters=14):
    lo, hi = field - 0.4, field + 0.6
    for _ in range(iters):
        mid = (lo + hi) / 2
        p = climb(place_rates(k, mid, [field] * 3, n=100_000), levels, walkers=6_000)["p_promote"]
        lo, hi = (mid, hi) if p < 0.5 else (lo, mid)
    return (lo + hi) / 2


def break_even(k, field, pts):
    lo, hi = field - 0.6, field + 0.6
    for _ in range(25):
        mid = (lo + hi) / 2
        ev = float(np.dot(place_rates(k, mid, [field] * 3, n=200_000), pts))
        lo, hi = (mid, hi) if ev < 0 else (lo, mid)
    r = place_rates(k, mid, [field] * 3)
    return {"skill": round(mid, 4), "mean_place": round(mean_place(r), 3), "fourth": round(r[3], 3)}


def room_sample_beta(path, skill_per_step, skill_per_step_se, sm_gap, sm_gap_se):
    """Places per rank step and Saint-minus-Master places in a large Jade sample (amae-koromo, every seat), each
    divided by the matching Mortal skill gap from the user's tables."""
    games = json.load(open(path))["games"]
    x, y, tid = [], [], []
    sm = []
    for t, (_, seats) in enumerate(games):
        lv = [LEVEL_STEP.get(s[0]) for s in seats]
        if any(v is None for v in lv):
            continue
        order = sorted(range(4), key=lambda i: (-seats[i][1], i))
        place = [order.index(i) + 1 for i in range(4)]
        ml = np.mean(lv)
        for i in range(4):
            x.append(lv[i] - ml)
            y.append(place[i] - 2.5)
            tid.append(t)
        s = [place[i] for i in range(4) if lv[i] >= 3]
        m = [place[i] for i in range(4) if lv[i] < 3]
        if s and m:
            sm.append(np.mean(s) - np.mean(m))
    x, y, tid = np.array(x), np.array(y), np.array(tid)
    b = float(x @ y / (x @ x))
    e = y - b * x
    # clustered by table
    u = np.bincount(tid, weights=x * e)
    se = float(np.sqrt(np.sum(u ** 2)) / (x @ x))
    sm = np.array(sm)
    smd, smse = float(sm.mean()), float(sm.std(ddof=1) / np.sqrt(len(sm)))
    beta_step = -b / skill_per_step
    beta_step_se = abs(beta_step) * math.hypot(se / b, skill_per_step_se / skill_per_step)
    beta_sm = -smd / sm_gap
    beta_sm_se = abs(beta_sm) * math.hypot(smse / smd, sm_gap_se / sm_gap)
    return {"tables": int(len(set(tid.tolist()))), "place_per_rank_step": round(b, 4), "place_per_rank_step_se": round(se, 4),
            "mixed_tables": len(sm), "saint_minus_master_place": round(smd, 4), "saint_minus_master_place_se": round(smse, 4),
            "beta_per_step": round(beta_step, 3), "beta_per_step_se": round(beta_step_se, 3),
            "beta_saint_master": round(beta_sm, 3), "beta_saint_master_se": round(beta_sm_se, 3)}


def main():
    global METRIC
    key = "logp"
    if "--metric" in sys.argv:
        i = sys.argv.index("--metric")
        key = sys.argv[i + 1]
        del sys.argv[i:i + 2]
    METRIC = (key, "n")
    if "--discards" in sys.argv:
        sys.argv.remove("--discards")
        METRIC = (key + "_d", "nd")
    jade, jbad = load(sys.argv[1])
    hou, hbad = load(sys.argv[2])
    room_path = sys.argv[3]
    out_path = sys.argv[4]
    out = {"inputs": {"jade_seats": len(jade), "jade_skipped": jbad, "houou_seats": len(hou), "houou_skipped": hbad,
                      "jade_games": len(by_game(jade)), "houou_games": len(by_game(hou)), "room_sample": room_path}}

    groups = []
    for t in ["Master 1", "Master 2", "Master 3", "Saint 1", "Saint 2", "Saint 3"]:
        if any(jade_tier(r) == t for r in jade):
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
    def step_fit(rows):
        opp = [r for r in rows if jade_tier(r) not in (None, "user")]
        xs = np.array([ladder_step(jade_tier(r)) for r in opp], float)
        ys = np.array([r[METRIC[0]] / r[METRIC[1]] for r in opp])
        ws = np.array([r[METRIC[1]] for r in opp], float)
        X = np.column_stack([np.ones_like(xs), xs])
        return np.linalg.solve((X * ws[:, None]).T @ X, (X * ws[:, None]).T @ ys)
    a0, a1 = step_fit(jade)
    a1_se = boot(by_game(jade), lambda rs: float(step_fit(rs)[1]))
    steps = lambda s: round(float((s - a0) / a1), 2)  # noqa: E731
    out["msoul_skill_per_rank_step"] = round(float(a1), 4)
    out["msoul_skill_per_rank_step_se"] = round(a1_se, 4)
    out["houou_field_in_msoul_steps"] = steps(G["Houou field"]["skill"])
    out["user_in_msoul_steps"] = steps(G["You (Jade)"]["skill"])
    out["jade_field_in_msoul_steps"] = steps(G["Jade field (your opponents)"]["skill"])

    # beta: places per unit of skill
    gap = saint_master_gap(jade)
    gap_se = boot(by_game(jade), saint_master_gap)
    place_per_dan, place_per_dan_se = houou_within_table(hou)
    spd = skill_per_dan(hou)
    room = room_sample_beta(room_path, a1, a1_se, gap, gap_se)
    players = houou_player_beta(hou)
    # pooled: the Jade room (per rank step) and the Houou players share no data
    ests = [(room["beta_per_step"], room["beta_per_step_se"]), (players["beta"], players["beta_se"])]
    w = [1 / se ** 2 for _, se in ests]
    beta = sum(b * wi for (b, _), wi in zip(ests, w)) / sum(w)
    beta_se = 1 / math.sqrt(sum(w))
    out["calibration"] = {
        "saint_minus_master_skill": round(gap, 4), "saint_minus_master_skill_se": round(gap_se, 4),
        "jade_room_sample": room, "houou_players": players,
        "houou_dan_ratio": {"place_per_dan_step": round(place_per_dan, 4), "se": round(place_per_dan_se, 4),
                            "skill_per_dan_step": round(spd, 4), "beta": round(-place_per_dan / spd, 3),
                            "note": "not used: dans differ in placement more than in Mortal agreement"},
        "beta_pooled": round(beta, 3), "beta_pooled_se": round(beta_se, 3)}

    fields = {"houou": G["Houou field"]["skill"], "jade": G["Jade field (your opponents)"]["skill"]}
    out["field_gap_houou_minus_jade"] = round(fields["houou"] - fields["jade"], 4)

    su, actual = G["You (Jade)"]["skill"], G["You (Jade)"]["place"]

    def scenario(betas):
        """Everything that follows from a places-per-skill figure for each room."""
        k = {r: k_for_beta(betas[r], f) for r, f in fields.items()}
        res = {"beta": {r: round(v, 3) for r, v in betas.items()}, "k": {r: round(v, 3) for r, v in k.items()}}
        res["break_even"] = {
            "houou_7dan": break_even(k["houou"], fields["houou"], HOUOU_7DAN["pts"]),
            "houou_8dan": break_even(k["houou"], fields["houou"], HOUOU_8DAN["pts"]),
            "jade_saint3": break_even(k["jade"], fields["jade"], JADE_S3["pts"])}
        # the skill that reproduces the user's measured Jade place, as a second reading beside the Mortal one
        lo, hi = fields["jade"] - 1, fields["jade"] + 1
        for _ in range(60):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if expected_place(k["jade"], mid, [fields["jade"]] * 3) > actual else (lo, mid)
        s_res = (lo + hi) / 2
        res["you"] = {"predicted_jade_place_from_mortal": round(expected_place(k["jade"], su, [fields["jade"]] * 3), 3),
                      "actual_jade_place": actual, "skill_mortal": su, "skill_from_results": round(s_res, 4)}
        res["even_odds"], res["field_player"], res["houou_average_player"] = {}, {}, {}
        for name, (rm, levels) in LADDERS.items():
            for tag, s in (("mortal", su), ("results", s_res)):
                rates = place_rates(k[rm], s, [fields[rm]] * 3)
                res["you"][f"{tag}:{name}"] = {"rates": [round(x, 3) for x in rates],
                                               "mean_place": round(mean_place(rates), 3), **climb(rates, levels)}
            t = even_odds_skill(k[rm], fields[rm], levels)
            res["even_odds"][name] = {"skill": round(t, 4), "msoul_steps": steps(t)}
            # a player exactly at the room's own average, and one at the Houou average, in this room
            res["field_player"][name] = climb(place_rates(k[rm], fields[rm], [fields[rm]] * 3), levels)
            rates = place_rates(k[rm], fields["houou"], [fields[rm]] * 3)
            res["houou_average_player"][name] = {"mean_place": round(mean_place(rates), 3), **climb(rates, levels)}
        return res

    # main: each room on its own beta (Houou from its repeat players, Jade from the room sample)
    out["main"] = scenario({"houou": players["beta"], "jade": room["beta_per_step"]})
    # for comparison: one pooled beta for both rooms
    out["one_beta"] = scenario({"houou": beta, "jade": beta})

    # sensitivity: even-odds skill for each ladder across beta, and where Celestial crosses each Houou step
    sens = []
    for b in np.round(np.arange(0.4, 1.81, 0.1), 2):
        kk = {r: k_for_beta(float(b), f) for r, f in fields.items()}
        row = {"beta": float(b)}
        for name, (rm, levels) in LADDERS.items():
            row[name] = round(even_odds_skill(kk[rm], fields[rm], levels, iters=12), 4)
        sens.append(row)
    out["sensitivity"] = sens
    flips = {}
    for name in ("houou_7to8", "houou_8to9", "houou_7to9"):
        d = [r["jade_s3_to_celestial"] - r[name] for r in sens]
        flips[name] = next((round(sens[i - 1]["beta"] + d[i - 1] / (d[i - 1] - d[i]) * 0.1, 2)
                            for i in range(1, len(d)) if d[i - 1] > 0 >= d[i]), None)
    out["beta_where_celestial_stops_being_harder"] = flips

    json.dump(out, open(out_path, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("groups",)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
