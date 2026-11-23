#!/usr/bin/env python3
"""Mahjong Soul's top tiers and Tenhou's Houou dans on one strength scale (guide chapter 53).

Strength is measured in places a game. A player of strength ``a`` at a table whose other three seats average
``b`` expects to finish at 2.5 - (a - b), so a player 0.05 above an average Saint 3 averages 2.45 against three
average Saint 3s. Saint 3 as met in the Jade room is zero.

Inside each site the strengths come from results alone, one least-squares fit over every seat of every table:

    place - 2.5 = -(a[own tier] - mean of a[the other three tiers])        standard errors clustered by table

- Mahjong Soul: 100,000 Jade South tables (three days) and every Throne South table since 20 July 2026
  (amae-koromo; rank, final score and account id per seat, ``data/ladder_skill/room_samples_ids*.json``, kept
  local). Jade seats are Master 1 to Saint 3 and Throne seats are Saint 1 to Celestial, so the two rooms only meet
  through Saints, and a Saint who plays Throne is not the average Saint. So the Jade games of the Saints most active
  in Throne are added (``throne_saints_jade_games.json``) and each of those players gets one strength of their own,
  the same in both rooms. They tie the rooms together.
- A rank's band starts at the strength that passes the rank below: where that rank's points (their average by
  finishing place, ``service/.state/room-sample.json``; Tenhou's are fixed) come to zero, given how the four
  finishing shares move with strength at that site's tables.
- Tenhou: every Houou hanchan of 6 Oct to 5 Nov 2026 (``data/ladder_skill/houou.jsonl``), tiers 七段 to 天鳳位, plus a
  straight line through the dans because 十段 and 天鳳位 have few games.

LuckyJ is placed from its own results: its 1,076 Tokujou hanchan (``data/local_sources/luckyj_tenhou``), every seat scored
with the same earlier policy model (``data/ladder_skill/luckyj_tokujou.jsonl``). Mortal places its opponents and the
gap to them comes from LuckyJ's placements; Mortal agreement alone underrates LuckyJ and is reported only as a check.

Across the sites the only link is Mortal: the six Jade tiers give six points, results strength against mean ln p
under the earlier policy model (the user's 361 Jade games, ``data/ladder_skill/jade.jsonl``), and the line through
them is read at the Houou field's mean ln p. The same
link with Mortal-S42 is reported as a check: S42 was trained on Houou and Celestial games, so it is not a neutral
yardstick for this comparison.

    .venv/bin/python scripts/mine_tier_ranking.py [OUT.json]
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import compare_ladders as cl  # noqa: E402

DATA = ROOT / "data" / "ladder_skill"
OUT = ROOT / "analysis" / "tier-ranking-2026-11-20.json"
JADE, THRONE = "12", "16"
MASTER = {10401: "Master 1", 10402: "Master 2", 10403: "Master 3"}
SAINT = {10501: "Saint 1", 10502: "Saint 2", 10503: "Saint 3"}
STEP = {"Master 1": 0, "Master 2": 1, "Master 3": 2, "Saint 1": 3, "Saint 2": 4, "Saint 3": 5}
DANS = ["七段", "八段", "九段", "十段", "天鳳"]
RNG = np.random.default_rng(20261120)


def places(scores):
    order = sorted(range(4), key=lambda i: (-scores[i], i))
    return [order.index(i) + 1 for i in range(4)]


def fit(tables, ref):
    """``tables``: [(levels of the four seats, their places)]. Strengths with ``ref`` at zero and their covariance.

    Built from the normal equations table by table, so a level per bridging player stays cheap; the covariance is
    the sandwich with tables as clusters."""
    levels = sorted({l for t in tables for l in t[0]}, key=str)
    keep = [l for l in levels if l != ref]
    ix = {l: i for i, l in enumerate(keep)}
    k = len(keep)
    xtx, xty = np.zeros((k, k)), np.zeros(k)
    rows = []
    for lv, pl in tables:
        cols = sorted({ix[l] for l in lv if l in ix})
        x = np.zeros((4, len(cols)))
        pos = {c: n for n, c in enumerate(cols)}
        for i in range(4):
            if lv[i] in ix:
                x[i, pos[ix[lv[i]]]] -= 1
            for j in range(4):
                if j != i and lv[j] in ix:
                    x[i, pos[ix[lv[j]]]] += 1 / 3
        y = np.array(pl, float) - 2.5
        c = np.array(cols, int)
        xtx[np.ix_(c, c)] += x.T @ x
        xty[c] += x.T @ y
        rows.append((c, x, y))
    inv = np.linalg.pinv(xtx)
    b = inv @ xty
    meat = np.zeros((k, k))
    for c, x, y in rows:
        g = x.T @ (y - x @ b[c])
        meat[np.ix_(c, c)] += np.outer(g, g)
    return keep, b, inv @ meat @ inv


def combo(keep, b, cov, weights):
    """A weighted sum of strengths (the reference level counts as zero) and its standard error."""
    w = np.zeros(len(keep))
    for level, x in weights.items():
        if level in keep:
            w[keep.index(level)] += x
    return float(w @ b), float(np.sqrt(max(w @ cov @ w, 0.0)))


def shares(tables, level):
    c = Counter(p for lv, pl in tables for l, p in zip(lv, pl) if l == level)
    n = sum(c.values())
    return {"seats": n, "mean_place": round(sum(k * v for k, v in c.items()) / n, 4),
            "shares": [round(c[k] / n, 4) for k in (1, 2, 3, 4)]}


def share_slopes(tables, strength):
    """How the four finishing shares move with a seat's strength over its table: share = 1/4 + c * gap."""
    gap, ind = [], []
    for lv, pl in tables:
        a = [strength[l] for l in lv]
        for i in range(4):
            gap.append(a[i] - (sum(a) - a[i]) / 3)
            ind.append([float(pl[i] == k) for k in (1, 2, 3, 4)])
    gap, ind = np.array(gap), np.array(ind)
    return [round(float((gap * (ind[:, k] - 0.25)).sum() / (gap ** 2).sum()), 4) for k in range(4)]


def break_even_gap(points, slopes):
    """The strength over the table at which a rank's points average zero."""
    return -0.25 * sum(points) / sum(c * p for c, p in zip(slopes, points))


def load_rooms():
    """Random Jade tables, every Throne table since 20 July, and the Jade games of Saints who also play Throne."""
    rooms = {JADE: [], THRONE: []}
    for name in ("room_samples_ids.json", "room_samples_ids_more.json"):
        path = DATA / name
        if path.exists():
            games = json.loads(path.read_text())["games"]
            for room in rooms:
                rooms[room] += games.get(room, [])
    bridge = {}
    path = DATA / "throne_saints_jade_games.json"
    if path.exists():
        for acct, games in json.loads(path.read_text())["players"].items():
            if games:
                bridge[int(acct)] = games
    return rooms, bridge


def rank_points():
    """Average rank points by finishing place for each Saint tier in each room (the tutor's room sample)."""
    path = ROOT / "service" / ".state" / "room-sample.json"
    acc = defaultdict(lambda: defaultdict(list))
    for _, mode, seats in json.loads(path.read_text())["games"]:
        for s, p in zip(seats, places([x[1] for x in seats])):
            if s[0] in SAINT:
                acc[(str(mode), SAINT[s[0]])][p].append(s[2])
    return {room: {tier: [round(float(np.mean(acc[(room, tier)][p])), 1) for p in (1, 2, 3, 4)] for tier in SAINT.values()}
            for room in (JADE, THRONE)}


def mahjong_soul():
    raw, bridge_games = load_rooms()
    bridge = set(bridge_games)  # accounts whose Jade games were fetched because they play Throne as Saints

    def level(seat, room):
        rank, _, acct = seat
        if acct in bridge and rank in SAINT:
            return f"P{acct}"  # one strength for the player, the same in both rooms
        if rank in MASTER:
            return MASTER[rank]
        if rank in SAINT:
            return SAINT[rank] + (" jade" if room == JADE else " throne")
        return "Celestial 1" if rank == 10701 else "Celestial 2+"

    def tier_of(seat):
        rank = seat[0]
        return MASTER.get(rank) or SAINT.get(rank) or "Celestial"

    random_jade = [(t[1], JADE) for t in raw[JADE]]
    seen = {(t[0], tuple(sorted(s[2] for s in t[1]))) for t in raw[JADE]}
    extra_jade = []
    for games in bridge_games.values():
        for _, start, seats in games:
            key = (start, tuple(sorted(s[2] for s in seats)))
            if key not in seen and all(s[0] in MASTER or s[0] in SAINT for s in seats):
                seen.add(key)
                extra_jade.append((seats, JADE))
    throne = [(t[1], THRONE) for t in raw[THRONE]]
    every = random_jade + extra_jade + throne
    tabs = [([level(s, room) for s in seats], places([s[1] for s in seats])) for seats, room in every]
    keep, b, cov = fit(tabs, "Saint 3 jade")

    def weights(sample, pick):  # the seats of one tier in one sample of tables, as weights over fitted levels
        c = Counter(level(s, room) for seats, room in sample for s in seats if pick(s))
        n = sum(c.values())
        return {k: v / n for k, v in c.items()}, n

    zero, _ = weights(random_jade, lambda s: s[0] == 10503)  # Saint 3 as met in the Jade room is the zero

    def rel(w):
        w = dict(w)
        for k, v in zero.items():
            w[k] = w.get(k, 0) - v
        est, se = combo(keep, b, cov, w)
        return {"a": round(est, 4), "se": round(se, 4)}

    rank_id = {v: k for k, v in {**MASTER, **SAINT}.items()}
    tiers = {}
    for name in list(MASTER.values()) + list(SAINT.values()):
        w, n = weights(random_jade, lambda s, r=rank_id[name]: s[0] == r)
        tiers[name] = {**rel(w), "seats": n}
    for name in SAINT.values():
        w, n = weights(throne, lambda s, r=rank_id[name]: s[0] == r)
        tiers[name + ", in the Throne room"] = {**rel(w), "seats": n}
    w, n = weights(throne, lambda s: s[0] > 10700)
    tiers["Celestial"] = {**rel(w), "seats": n}
    for name, pick in (("Celestial 1", lambda s: s[0] == 10701), ("Celestial 2+", lambda s: s[0] > 10701)):
        w, n = weights(throne, pick)
        tiers[name] = {**rel(w), "seats": n}
    bridged = Counter()
    for sample, room in ((random_jade + extra_jade, "jade"), (throne, "throne")):
        for seats, _ in sample:
            for s in seats:
                if s[2] in bridge and s[0] in SAINT:
                    bridged[room] += 1
    out = {"tables": {"jade": len(random_jade), "jade_of_bridging_players": len(extra_jade), "throne": len(throne)},
           "bridging_players": len(bridge), "bridging_seats": dict(bridged), "tiers": tiers}
    est, se = combo(keep, b, cov, {"Celestial 2+": 1, "Celestial 1": -1})
    out["celestial_2plus_minus_1"] = {"a": round(est, 4), "se": round(se, 4)}

    # the naive bridge, for the record: every Saint tier one level whatever room it plays in
    naive = [([tier_of(s) if s[0] < 10700 else ("Celestial 1" if s[0] == 10701 else "Celestial 2+") for s in seats],
              places([s[1] for s in seats])) for seats, _ in random_jade + throne]
    k2, b2, c2 = fit(naive, "Saint 3")
    cel, _ = weights(throne, lambda s: s[0] > 10700)
    est, se = combo(k2, b2, c2, cel)
    out["naive_celestial"] = {"a": round(est, 4), "se": round(se, 4),
                              "note": "treats a Saint tier as equally strong in both rooms"}

    # one point per Celestial level, and a line through them (Throne room alone, against level 1)
    lv_tabs = [([f"Celestial L{s[0] - 10700}" if s[0] > 10700 else SAINT[s[0]] for s in seats], places([s[1] for s in seats]))
               for seats, _ in throne]
    k4, b4, c4 = fit(lv_tabs, "Celestial L1")
    lv_seats = Counter(l for lv, _ in lv_tabs for l in lv if l.startswith("Celestial"))
    points = [{"level": 1, "vs_level_1": 0.0, "se": 0.0, "seats": lv_seats["Celestial L1"]}]
    for l in sorted((l for l in lv_seats if l != "Celestial L1"), key=lambda v: int(v.split("L")[1])):
        est, se = combo(k4, b4, c4, {l: 1})
        points.append({"level": int(l.split("L")[1]), "vs_level_1": round(est, 4), "se": round(se, 4), "seats": lv_seats[l]})
    x = np.array([p["level"] for p in points[1:]], float)
    yv = np.array([p["vs_level_1"] for p in points[1:]])
    wt = 1 / np.array([p["se"] for p in points[1:]]) ** 2
    out["celestial_levels"] = {"points": points, "per_level": round(float((wt * (x - 1) * yv).sum() / (wt * (x - 1) ** 2).sum()), 5),
                               "per_level_se": round(float(np.sqrt(1 / (wt * (x - 1) ** 2).sum())), 5)}

    # results line through the six Jade tiers, by rank step (for turning a rank step into places)
    names = list(STEP)
    ya = np.array([tiers[n]["a"] for n in names])
    wa = np.array([tiers[n]["seats"] for n in names], float)
    Xa = np.column_stack([np.ones(6), np.arange(6)])
    ca = np.linalg.solve(Xa.T @ np.diag(wa) @ Xa, Xa.T @ np.diag(wa) @ ya)
    out["places_per_rank_step"] = {"intercept": round(float(ca[0]), 4), "slope": round(float(ca[1]), 4)}

    # what it takes to pass each Saint tier: the strength at which its rank points average zero
    jade_naive = [([tier_of(s) for s in seats], places([s[1] for s in seats])) for seats, _ in random_jade]
    strength = {n: tiers[n]["a"] for n in names}
    slopes = share_slopes(jade_naive, strength)
    # the Throne room splits an edge differently (chapter 56), so its break-evens use its own slopes
    throne_tiers = {"Saint 1": tiers["Saint 1, in the Throne room"]["a"], "Saint 2": tiers["Saint 2, in the Throne room"]["a"],
                    "Saint 3": tiers["Saint 3, in the Throne room"]["a"], "Celestial": tiers["Celestial"]["a"]}
    throne_tabs = [([SAINT.get(s[0]) or "Celestial" for s in seats], places([s[1] for s in seats])) for seats, _ in throne]
    room_slopes = {JADE: slopes, THRONE: share_slopes(throne_tabs, throne_tiers)}
    pts = rank_points()
    out["share_slopes"] = {"jade": slopes, "throne": room_slopes[THRONE],
                           "note": "change in the share of 1st, 2nd, 3rd, 4th per place of strength over the table"}
    out["rank_points"] = pts
    passes = {}
    for name in SAINT.values():
        row = {}
        for room, sample in ((JADE, random_jade), (THRONE, throne)):
            # the other three seats at this tier's tables, as weights over fitted levels
            c, n = Counter(), 0
            for seats, r in sample:
                for i, s in enumerate(seats):
                    if s[0] == rank_id[name]:
                        n += 1
                        for j, o in enumerate(seats):
                            if j != i:
                                c[level(o, r)] += 1 / 3
            opp = rel({k: v / n for k, v in c.items()})
            gap = break_even_gap(pts[room][name], room_slopes[room])
            row["jade" if room == JADE else "throne"] = {"opponents": opp["a"], "opponents_se": opp["se"], "gap": round(gap, 4),
                                                          "a": round(opp["a"] + gap, 4), "se": opp["se"],
                                                          "mean_place_needed": round(2.5 - gap, 3)}
        row["easier"] = min(("jade", "throne"), key=lambda r: row[r]["a"])
        row["a"], row["se"] = row[row["easier"]]["a"], row[row["easier"]]["se"]
        passes[name] = row
    out["to_pass"] = passes

    throne_naive = [([tier_of(s) for s in seats], places([s[1] for s in seats])) for seats, _ in throne]
    out["observed"] = {"Saint 2, Jade room": shares(jade_naive, "Saint 2"), "Saint 3, Jade room": shares(jade_naive, "Saint 3"),
                       "Saint 3, Throne room": shares(throne_naive, "Saint 3"),
                       "Celestial, Throne room": shares(throne_naive, "Celestial")}
    return out


def houou():
    rows, _ = cl.load(DATA / "houou.jsonl")
    games = defaultdict(dict)
    for line in open(DATA / "houou.jsonl"):
        r = json.loads(line)
        if "error" not in r:
            games[r["file"]][r["seat"]] = (r["dan"], r["place"])
    tabs = [([v[s][0] for s in range(4)], [v[s][1] for s in range(4)]) for v in games.values()
            if len(v) == 4 and all(v[s][0] in DANS for s in range(4))]
    seats = Counter(l for lv, _ in tabs for l in lv)
    total = sum(seats.values())
    keep, b, cov = fit(tabs, "七段")
    field = {d: seats[d] / total for d in DANS}
    out = {"tables": len(tabs), "dans": {}}
    for d in DANS:
        w = {d: 1.0}
        for k, v in field.items():
            w[k] = w.get(k, 0) - v
        est, se = combo(keep, b, cov, w)
        out["dans"][d] = {"vs_field": round(est, 4), "se": round(se, 4), **shares(tabs, d)}
    # a straight line through the dans (七段 = 7 ... 天鳳位 = 11), each weighted by its seats
    x = np.array([7, 8, 9, 10, 11], float)
    yv = np.array([out["dans"][d]["vs_field"] for d in DANS])
    wt = np.array([seats[d] for d in DANS], float)
    A = np.column_stack([np.ones(5), x - 7])
    idx = [keep.index(d) if d in keep else None for d in DANS]
    cc = np.zeros((5, 5))
    for i, a in enumerate(idx):
        for j, c in enumerate(idx):
            if a is not None and c is not None:
                cc[i, j] = cov[a, c]
    P = np.linalg.solve(A.T @ np.diag(wt) @ A, A.T @ np.diag(wt))
    coef = P @ yv
    cv = P @ cc @ P.T
    strength = {d: out["dans"][d]["vs_field"] for d in DANS}
    out["share_slopes"] = share_slopes(tabs, strength)
    opp, cnt = Counter(), Counter()
    for lv, _ in tabs:
        for i in range(4):
            cnt[lv[i]] += 1
            opp[lv[i]] += (sum(strength[l] for l in lv) - strength[lv[i]]) / 3
    out["opponents_vs_field"] = {d: round(opp[d] / cnt[d], 4) for d in DANS}
    out["rank_points"] = {d: [90, 45, 0, p] for d, p in zip(DANS[:4], (-135, -150, -165, -180))}
    out["line"] = {"at_7dan": round(float(coef[0]), 4), "per_dan": round(float(coef[1]), 4),
                   "per_dan_se": round(float(np.sqrt(cv[1, 1])), 4),
                   "fitted": {d: {"vs_field": round(float(coef[0] + coef[1] * (k - 7)), 4),
                                  "se": round(float(np.sqrt(np.array([1, k - 7]) @ cv @ np.array([1, k - 7]))), 4)}
                              for d, k in zip(DANS, x)}}
    return out


def mortal_link(jade_file, houou_file, key, strengths, reps=2000):
    """Mortal agreement turned into places: a line of results strength against mean ln p through the six Jade tiers,
    read at the Houou field's mean ln p (and at the user's). The error is a bootstrap over the Jade games."""
    jade, _ = cl.load(DATA / jade_file)
    hou, _ = cl.load(DATA / houou_file)
    field = sum(r[key] for r in hou) / sum(r["n"] for r in hou)
    mine = [r for r in jade if r["name"] == cl.USER]
    you = sum(r[key] for r in mine) / sum(r["n"] for r in mine)
    games = defaultdict(list)
    for r in jade:
        tier = cl.jade_tier(r)
        if tier in STEP:
            games[r["file"]].append((STEP[tier], r[key], r["n"]))
    a = np.array([strengths[n] for n in STEP])

    def line(gs):
        num, den, cnt = np.zeros(6), np.zeros(6), np.zeros(6)
        for g in gs:
            for st, lp, n in g:
                num[st] += lp
                den[st] += n
                cnt[st] += 1
        skill = num / den
        X = np.column_stack([np.ones(6), skill])
        W = np.diag(cnt)
        return np.linalg.solve(X.T @ W @ X, X.T @ W @ a), skill, cnt

    G = list(games.values())
    coef, skills, cnt = line(G)
    boots = np.array([line([G[i] for i in RNG.integers(0, len(G), len(G))])[0] for _ in range(reps)])
    at = lambda c, s: c[..., 0] + c[..., 1] * s  # noqa: E731
    return {"field_skill": round(field, 4), "your_skill": round(you, 4),
            "tier_skill": {n: round(float(v), 4) for n, v in zip(STEP, skills)},
            "tier_seats": {n: int(c) for n, c in zip(STEP, cnt)},
            "places_per_skill": round(float(coef[1]), 4), "places_per_skill_se": round(float(boots[:, 1].std(ddof=1)), 4),
            "tier_on_line": {n: round(float(at(coef, v)), 4) for n, v in zip(STEP, skills)},
            "field_a": round(float(at(coef, field)), 4), "field_a_se": round(float(at(boots, field).std(ddof=1)), 4),
            "you_a": round(float(at(coef, you)), 4), "you_a_se": round(float(at(boots, you).std(ddof=1)), 4)}


def luckyj(base, slopes, reps=2000):
    """LuckyJ on the scale: its Tokujou opponents placed by Mortal on the policy link, plus what its placements say
    about the gap to them. The error is a bootstrap over games plus the link's own uncertainty."""
    path = DATA / "luckyj_tokujou.jsonl"
    if not path.exists():
        return None
    rows, _ = cl.load(path)
    games = defaultdict(list)
    for r in rows:
        games[r["file"]].append(r)
    G = [g for g in games.values() if len(g) == 4 and sum("LuckyJ" in r["name"] for r in g) == 1]
    at = lambda s: base["field_a"] + base["places_per_skill"] * (s - base["field_skill"])  # noqa: E731

    def read(gs):
        lj = [r for g in gs for r in g if "LuckyJ" in r["name"]]
        op = [r for g in gs for r in g if "LuckyJ" not in r["name"]]
        s_lj = sum(r["logp"] for r in lj) / sum(r["n"] for r in lj)
        s_op = sum(r["logp"] for r in op) / sum(r["n"] for r in op)
        place = float(np.mean([r["place"] for r in lj]))
        return s_lj, s_op, place, at(s_op) + 2.5 - place

    s_lj, s_op, place, a = read(G)
    boots = np.array([read([G[i] for i in RNG.integers(0, len(G), len(G))]) for _ in range(reps)])
    link_se = float(np.hypot(base["field_a_se"], (s_op - base["field_skill"]) * base["places_per_skill_se"]))
    tokujou = [75, 30, 0, -180]  # a Tokujou 10-dan's points (tenhou.net/man), with the share slopes measured in Houou
    return {"games": len(G), "mean_place": round(place, 3), "mean_place_se": round(float(boots[:, 2].std(ddof=1)), 3),
            "opponents_a": round(at(s_op), 4), "a_from_mortal": round(at(s_lj), 4),
            "a_from_mortal_predicts_place": round(2.5 - (at(s_lj) - at(s_op)), 3),
            "a": round(a, 4), "se": round(float(np.hypot(boots[:, 3].std(ddof=1), link_se)), 4),
            "tokujou_10dan_place_needed": round(2.5 - break_even_gap(tokujou, slopes), 3)}


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    ms = mahjong_soul()
    th = houou()
    strengths = {n: ms["tiers"][n]["a"] for n in STEP}
    link = {"policy": mortal_link("jade.jsonl", "houou.jsonl", "logp", strengths),
            "s42": mortal_link("jade_s42.jsonl", "houou_s42_merged.jsonl", "lp06", strengths)}
    # the user's own Jade results, as a second reading of where they sit
    jade_rows, _ = cl.load(DATA / "jade.jsonl")
    mine = [r["place"] for r in jade_rows if r["name"] == cl.USER]
    s3 = ms["observed"]["Saint 3, Jade room"]["mean_place"]
    you = {"games": len(mine), "mean_place": round(float(np.mean(mine)), 3),
           "a_from_results": round(s3 - float(np.mean(mine)), 4),
           "a_from_results_se": round(float(np.std(mine, ddof=1) / np.sqrt(len(mine))), 4),
           "a_from_mortal": link["policy"]["you_a"], "a_from_mortal_se": link["policy"]["you_a_se"],
           "a_from_mortal_s42": link["s42"]["you_a"]}
    base = link["policy"]
    ladder = {}
    for d in DANS:
        own = th["dans"][d]
        fitted = th["line"]["fitted"][d]
        ladder[d] = {"a": round(base["field_a"] + own["vs_field"], 4), "se_own": own["se"],
                     "a_fit": round(base["field_a"] + fitted["vs_field"], 4), "se_fit": fitted["se"],
                     "se_link": base["field_a_se"], "seats": own["seats"],
                     "a_s42_link": round(link["s42"]["field_a"] + own["vs_field"], 4)}
    # what it takes to pass each dan in the Houou room, with the finishing-share slopes measured in that room
    slopes = th["share_slopes"]
    th["to_pass"] = {}
    for d in DANS[:4]:
        gap = break_even_gap(th["rank_points"][d], slopes)
        th["to_pass"][d] = {"gap": round(gap, 4), "mean_place_needed": round(2.5 - gap, 3),
                            "vs_field": round(th["opponents_vs_field"][d] + gap, 4),
                            "a": round(base["field_a"] + th["opponents_vs_field"][d] + gap, 4),
                            "a_s42_link": round(link["s42"]["field_a"] + th["opponents_vs_field"][d] + gap, 4),
                            "se_link": base["field_a_se"]}
    p_ms, p_th = ms["to_pass"], th["to_pass"]
    bands = {
        "mahjong_soul": [{"rank": "Saint 2", "from": p_ms["Saint 1"]["a"], "to": p_ms["Saint 2"]["a"]},
                         {"rank": "Saint 3", "from": p_ms["Saint 2"]["a"], "to": p_ms["Saint 3"]["a"]},
                         {"rank": "Celestial", "from": p_ms["Saint 3"]["a"], "to": None}],
        "tenhou": [{"rank": "七段", "from": None, "to": p_th["七段"]["a"]},
                   {"rank": "八段", "from": p_th["七段"]["a"], "to": p_th["八段"]["a"]},
                   {"rank": "九段", "from": p_th["八段"]["a"], "to": p_th["九段"]["a"]},
                   {"rank": "十段", "from": p_th["九段"]["a"], "to": p_th["十段"]["a"]},
                   {"rank": "天鳳", "from": p_th["十段"]["a"], "to": None}],
        "note": "a band is the strength that gains points at the rank below and not at this rank",
    }
    lj = luckyj(base, slopes)
    out = {"unit": "places a game against three average Jade-room Saint 3s (positive is better)", "bands": bands, "you": you,
           "luckyj": lj,
           "mahjong_soul": ms, "houou": th, "link": link, "tenhou_on_the_scale": ladder}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
