#!/usr/bin/env python3
"""The figures behind guide chapter 45: why the rank points fall.

The user's 216 Jade games since 1 January, split before the climb, the climb and since the peak (chapter 33's
boundaries, ``mine_climb_check.rank_path``), beside the other three players at those tables, LuckyJ's 1,079 Tokujou
games and the humans at its tables.

- places, final scores and the rank points a game of the Saint 3 Jade south formula for every seat, the spread of one
  game and what it does to a stretch of 67;
- where a game's points come from (wins, deal-ins by what the winner held, tsumo paid, draws, sticks), the user's edge
  over the other players at their tables and LuckyJ's over the humans at its tables, with the standard error of yours;
- the size of the wins: how often, how much, by riichi, dama and open hands;
- the deal-ins of 7,000 or more per 100 hands by stretch, the hands the other players won at those tables, and the
  cases of the stretch since the peak (Mortal's rating of the tile thrown, the riichis declared into an open hand);
- tilt and the end of the game: a game after a fourth, the place in a session, Mortal's agreement by stretch, the last
  hand from third and from fourth.

usage: mine_rank_drain.py OUT.json
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import mine_climb_check as cc  # noqa: E402
import mine_costly_run as mc  # noqa: E402

REPLAYS = ROOT / "site" / "replays"
THIN = ROOT / "analysis" / "thin-riichi-2026-10-19.json"
PERIODS = ("before", "climb", "since")
GROUPS = ("you", "jade_human", "luckyj", "tokujou_human")
BASE = (130, 65, 0, -250)  # Saint 3 Jade south: first, second, third, fourth
COMPONENTS = ("win", "deal_riichi", "deal_dama", "deal_open", "tsumo_paid", "draw", "sticks")
BIG = 7000
LOW = 0.25
SESSION_GAP = 90 * 60


def rank_points(score: int, place: int) -> int:
    return math.ceil((score - 30000) / 1000 + BASE[place - 1])


def places_of(scores: list[int]) -> list[int]:
    """Place of each seat; equal scores go to the seat that sat earlier."""
    order = sorted(range(4), key=lambda s: (-scores[s], s))
    return [order.index(s) + 1 for s in range(4)]


def seat_games(rows: list[dict], hero_seat: dict[str, int]) -> dict:
    """(game, seat) -> the points of the game by source, plus the hero flag."""
    out: dict = {}
    for r in rows:
        key = (r["game"], r["seat"])
        c = out.setdefault(key, {**dict.fromkeys(COMPONENTS, 0), "hero": r["seat"] == hero_seat[r["game"]], "hands": 0, "net": 0})
        c["win"] += r["win_pts"]
        kind = r["deal_in_into"]
        c["deal_riichi" if kind == "riichi" else "deal_open" if kind == "open hand" else "deal_dama"] += r["deal_pts"]
        c["tsumo_paid"] += r["tsumo_pts"]
        c["draw"] += r["draw_pts"]
        c["sticks"] -= 1000 * r["stick"]
        c["hands"] += 1
        c["net"] += r["net"]
    return out


def mean_and_se(values: list[float]) -> tuple[float, float]:
    a = np.array(values, dtype=float)
    return float(a.mean()), float(a.std(ddof=1) / math.sqrt(len(a)))


def components(games: dict, pick) -> dict:
    sel = [c for k, c in games.items() if pick(k, c)]
    out = {"games": len(sel)}
    for name in COMPONENTS + ("net",):
        m, se = mean_and_se([c[name] for c in sel])
        out[name] = round(m)
        out[name + "_se"] = round(se)
    out["deal_ins"] = out["deal_riichi"] + out["deal_dama"] + out["deal_open"]
    out["other"] = out["draw"] + out["sticks"]
    out["hands"] = round(sum(c["hands"] for c in sel) / len(sel), 2)
    return out


def edge(mine: dict, theirs: dict, per_1000: float) -> dict:
    """The difference per game, in points and rank points, with the standard error of the difference."""
    se = lambda name, a, b: math.sqrt(a[name + "_se"] ** 2 + b[name + "_se"] ** 2)
    out = {}
    for name in ("win", "deal_ins", "tsumo_paid", "other", "net"):
        a, b = mine[name], theirs[name]
        if name == "deal_ins":
            s = math.sqrt(sum(mine[k + "_se"] ** 2 for k in ("deal_riichi", "deal_dama", "deal_open")) + sum(theirs[k + "_se"] ** 2 for k in ("deal_riichi", "deal_dama", "deal_open")))
        elif name == "other":
            s = math.sqrt(sum(x[k + "_se"] ** 2 for x in (mine, theirs) for k in ("draw", "sticks")))
        else:
            s = se(name, mine, theirs)
        out[name] = {"points": a - b, "rank_points": round((a - b) * per_1000 / 1000, 1), "se": round(s)}
    return out


def win_sizes(rows: list[dict]) -> dict:
    n = len(rows)
    games = len({(r["game"], r["seat"]) for r in rows})
    wins = [r for r in rows if r["won"]]
    kind = lambda r: "riichi" if r["riichi_turn"] is not None else "open" if r["open"] else "dama"
    out = {"hands": n, "games": games, "wins": len(wins), "wins_per_100": round(100 * len(wins) / n, 1),
           "average": round(float(np.mean([r["win_pts"] for r in wins]))), "average_se": round(float(np.std([r["win_pts"] for r in wins], ddof=1) / math.sqrt(len(wins)))),
           "points_a_hand": round(sum(r["win_pts"] for r in rows) / n),
           "mangan_or_more_pct": round(100 * sum(r["win_pts"] >= 8000 for r in wins) / len(wins)),
           "under_3000_pct": round(100 * sum(r["win_pts"] < 3000 for r in wins) / len(wins))}
    for k in ("riichi", "dama", "open"):
        w = [r for r in wins if kind(r) == k]
        out[k] = {"wins": len(w), "per_100": round(100 * len(w) / n, 1), "average": round(float(np.mean([r["win_pts"] for r in w]))),
                  "average_se": round(float(np.std([r["win_pts"] for r in w], ddof=1) / math.sqrt(len(w)))), "points_a_hand": round(sum(r["win_pts"] for r in w) / n)}
    op = [r for r in rows if r["open"] and r["riichi_turn"] is None]
    four = [r for r in wins if kind(r) == "open"]
    out["open_hands"] = {"hands": len(op), "share_of_hands": round(100 * len(op) / n, 1), "won_pct": round(100 * sum(r["won"] for r in op) / len(op), 1),
                         "dealt_pct": round(100 * sum(r["dealt_in"] for r in op) / len(op), 1), "net_a_hand": round(sum(r["net"] for r in op) / len(op)),
                         "four_han_or_more_pct": round(100 * sum((r["win_han"] or 0) >= 4 for r in four) / len(four))}
    return out


def big_tail(rows: list[dict]) -> dict:
    n = len(rows)
    games = len({(r["game"], r["seat"]) for r in rows})
    big = [r for r in rows if r["dealt_in"] and -r["deal_pts"] >= BIG]
    return {"games": games, "hands": n, "big": len(big), "per_100": round(100 * len(big) / n, 2),
            "points_a_game": round(-sum(r["deal_pts"] for r in big) / games),
            "average": round(-sum(r["deal_pts"] for r in big) / len(big)) if big else None}


def turn_map(h: dict, hero: int) -> dict[int, int]:
    turn, tmap = 0, {}
    for i, e in enumerate(h["ev"]):
        if e[1] == hero and ((e[0] == "t" and not (len(e) > 3 and e[3])) or e[0] in ("c", "p", "m")):
            turn += 1
        tmap[i] = turn
    return tmap


def deal_in_cases(manifest: list[dict], per: dict[str, str]) -> list[dict]:
    """Every deal-in of 7,000 or more in the replays: the tile, Mortal's rating of it, and the hand that won."""
    cases = []
    for g in manifest:
        d = json.loads((REPLAYS / f"{g['uuid']}.json").read_text(encoding="utf-8"))
        hero = d["hero"]
        for h in d["hands"]:
            end = h["end"]
            if end["kind"] != "win":
                continue
            ev = h["ev"]
            ais = {a["i"]: a for a in h["ai"]}
            tmap = turn_map(h, hero)
            for w in end["wins"]:
                paid = -w["deltas"][hero]
                if w["seat"] == hero or w["from"] != hero or paid < BIG:
                    continue
                last = max(i for i, x in enumerate(ev) if x[0] == "d" and x[1] == hero)
                declared = [i for i, x in enumerate(ev) if x[0] == "r" and x[1] == hero and i < last]
                in_riichi = bool(declared)
                if in_riichi and (declared[-1] >= last - 1 or not any(j in ais for j in (last - 1, last))):
                    a, kind, at = ais.get(declared[-1] - 1), "riichi", declared[-1]
                else:
                    a, kind, at = ais.get(last - 1) or ais.get(last), "cut", last
                winner = w["seat"]
                calls = lambda stop: sum(1 for x in ev[:stop] if x[0] in ("c", "p", "m") and x[1] == winner)
                yaku = [y[0] for y in w["yaku"]]
                cases.append({
                    "game": g["uuid"], "date": g["date"], "period": per[g["uuid"]], "round": h["round"], "kind": kind, "tile": ev[last][2],
                    "turn": tmap[at] if kind == "riichi" else tmap[last], "dealt_turn": tmap[last], "paid": paid, "value": w["value"],
                    "mortal": round(dict(a["p"]).get(a["you"], 0.0), 3) if a else None, "mortal_riichi": round(dict(a["p"]).get("riichi", 0.0), 3) if a and kind == "riichi" else None,
                    "own_riichi": in_riichi, "winner_open": calls(len(ev)) > 0 and "riichi" not in yaku, "winner_calls_at_riichi": calls(declared[-1]) if declared else None,
                })
    return cases


def tilt(manifest: list[dict], per: dict[str, str], replay_index: dict) -> dict:
    recs = {r[0]: r for r in json.loads(cc.AMAE.read_text())["records"]}
    games = sorted(manifest, key=lambda g: g["start_time"])
    rows, prev_end, pos, session = [], None, 0, 0
    for g in games:
        r = recs[g["uuid"]]
        if prev_end is not None and r[1] - prev_end > SESSION_GAP:
            session, pos = session + 1, 0
        rows.append({"game": g["uuid"], "session": session, "pos": pos, "fourth": g["placement"] == 4,
                     "points": next(p for p in r[4] if p[0] == cc.ACCOUNT)[4]})
        pos, prev_end = pos + 1, r[2]
    after4, other = [], []
    for a, b in zip(rows, rows[1:]):
        if a["session"] == b["session"]:
            (after4 if a["fourth"] else other).append(b)
    line = lambda rs: {"games": len(rs), "fourths": sum(x["fourth"] for x in rs), "fourth_pct": round(100 * sum(x["fourth"] for x in rs) / len(rs), 1),
                       "points_a_game": round(sum(x["points"] for x in rs) / len(rs), 1)}
    place = {}
    for k in range(5):
        rs = [x for x in rows if (x["pos"] == k if k < 4 else x["pos"] >= 4)]
        place[str(k + 1)] = line(rs)
    mortal = {}
    for p in PERIODS:
        gs = [replay_index[g["uuid"]] for g in games if per[g["uuid"]] == p]
        mortal[p] = {"games": len(gs), "discards": sum(x["turns"] for x in gs), "matched_pct": round(100 * sum(x["turns_matched"] for x in gs) / sum(x["turns"] for x in gs), 1)}
    sessions = max(x["session"] for x in rows) + 1
    return {"sessions": sessions, "games_a_session": round(len(rows) / sessions, 1), "after_a_fourth": line(after4), "after_a_first_to_third": line(other),
            "by_place_in_session": place, "mortal_agreement": mortal}


def last_hand(rows: list[dict], manifest: list[dict], pick) -> dict:
    """Place before the last hand against the final place; fourth by the gap to third."""
    final = {g["uuid"].split("#")[0]: g["final_scores"] for g in manifest}
    hero = {g["uuid"].split("#")[0]: g["hero_seat"] for g in manifest}
    last: dict = {}
    for r in rows:
        if r["game"] not in last or r["li"] > last[r["game"]][0]:
            last[r["game"]] = (r["li"], {})
        if r["li"] == last[r["game"]][0]:
            last[r["game"]][1][r["seat"]] = r["start"]
    third = {"to_fourth": [0, 0], "from_fourth": [0, 0]}
    by_gap = {"0-3k": [0, 0], "3-8k": [0, 0], "8k+": [0, 0]}
    for game, (_, start) in last.items():
        if len(start) != 4:
            continue
        sc = [start[s] for s in range(4)]
        before, after = places_of(sc), places_of(final[game])
        for s in range(4):
            if not pick(s == hero[game]):
                continue
            if before[s] == 3:
                third["to_fourth"][0] += 1
                third["to_fourth"][1] += after[s] == 4
            if before[s] == 4:
                third["from_fourth"][0] += 1
                third["from_fourth"][1] += after[s] == 4
                order = sorted(range(4), key=lambda q: (-sc[q], q))
                gap = sc[order[2]] - sc[s]
                b = by_gap["0-3k" if gap <= 3000 else "3-8k" if gap <= 8000 else "8k+"]
                b[0] += 1
                b[1] += after[s] < 4
    return {"third": {"n": third["to_fourth"][0], "fell": third["to_fourth"][1]},
            "fourth": {"n": third["from_fourth"][0], "stayed": third["from_fourth"][1]},
            "fourth_escaped_by_gap_to_third": {k: {"n": v[0], "escaped": v[1]} for k, v in by_gap.items()}}


def main() -> None:
    out_path = sys.argv[1]
    per_1000 = json.loads(THIN.read_text())["cost"]["rank_points_per_1000_points"]
    manifest = sorted([g for g in json.loads(cc.MANIFEST.read_text(encoding="utf-8")) if g["date"] >= cc.SINCE], key=lambda g: g["start_time"])
    rank = cc.rank_path()
    per = cc.period_of(manifest, rank)
    lj_manifest = [g for g in json.loads(cc.LJ_MANIFEST.read_text(encoding="utf-8")) if g["mode"] == "tenhou-tokujou"]
    hero_you = {g["uuid"].split("#")[0]: g["hero_seat"] for g in manifest}
    hero_lj = {g["uuid"].split("#")[0]: g["hero_seat"] for g in lj_manifest}

    rows_you = mc.hand_rows(manifest, "me")
    rows_lj = mc.hand_rows(lj_manifest, "lj")
    sg_you, sg_lj = seat_games(rows_you, hero_you), seat_games(rows_lj, hero_lj)
    is_hero = lambda k, c: c["hero"]
    not_hero = lambda k, c: not c["hero"]
    in_period = lambda p: (lambda k, c: c["hero"] and per[k[0]] == p)

    # --- the pace: places and rank points a game ---------------------------------------------------------
    finals = {g["uuid"].split("#")[0]: g["final_scores"] for g in manifest}
    finals_lj = {g["uuid"].split("#")[0]: g["final_scores"] for g in lj_manifest}
    recs = {r[0]: r for r in json.loads(cc.AMAE.read_text())["records"]}
    checked = 0
    pace: dict = {}
    seat_rp: dict[str, list] = defaultdict(list)  # group -> [(place, score, rank points)]
    for g in manifest:
        u = g["uuid"]
        pl = places_of(finals[u])
        for s in range(4):
            rp = rank_points(finals[u][s], pl[s])
            if s == g["hero_seat"]:
                assert rp == next(p for p in recs[u][4] if p[0] == cc.ACCOUNT)[4], u
                checked += 1
                seat_rp["you"].append((g["placement"], finals[u][s], rp))
                seat_rp[per[u]].append((g["placement"], finals[u][s], rp))
            else:
                seat_rp["jade_human"].append((pl[s], finals[u][s], rp))
    for g in lj_manifest:
        u = g["uuid"].split("#")[0]
        pl = places_of(finals_lj[u])
        for s in range(4):
            seat_rp["luckyj" if s == g["hero_seat"] else "tokujou_human"].append((pl[s], finals_lj[u][s], rank_points(finals_lj[u][s], pl[s])))
    for name, rs in seat_rp.items():
        pls = [x[0] for x in rs]
        sc = np.array([x[1] for x in rs])
        pace[name] = {"games": len(rs), "places": [pls.count(i) for i in (1, 2, 3, 4)], "fourth_pct": round(100 * pls.count(4) / len(rs), 1),
                      "mean_score": round(float(sc.mean())), "score_sd": round(float(sc.std())), "rank_points": round(sum(x[2] for x in rs) / len(rs), 1)}
    mine = np.array([x[2] for x in seat_rp["you"]], dtype=float)
    sd = float(mine.std())
    career = json.loads(cc.AMAE.read_text())["stats"]
    body = [s["body"] for s in career if s["body"].get("rank_rates")][-1]
    p4 = body["rank_rates"][3]

    def z_fourths(period: str) -> dict:
        n = pace[period]["games"]
        k = pace[period]["places"][3]
        return {"games": n, "fourths": k, "expected": round(n * p4, 1), "sd": round((k - n * p4) / math.sqrt(n * p4 * (1 - p4)), 1)}

    spread = {"sd_a_game": round(sd, 1), "stretch_se": {p: round(sd / math.sqrt(pace[p]["games"]), 1) for p in PERIODS},
              "climb_vs_2026": round((pace["climb"]["rank_points"] - pace["you"]["rank_points"]) / (sd / math.sqrt(pace["climb"]["games"])), 1),
              "since_vs_2026": round((pace["since"]["rank_points"] - pace["you"]["rank_points"]) / (sd / math.sqrt(pace["since"]["games"])), 1),
              "since_vs_humans": round((pace["since"]["rank_points"] - pace["jade_human"]["rank_points"]) / (sd / math.sqrt(pace["since"]["games"])), 1),
              "career_games": body["count"], "career_fourth_pct": round(100 * p4, 1),
              "fourths": {p: z_fourths(p) for p in PERIODS}}

    # --- where a game's points come from -------------------------------------------------------------
    comp = {"you": components(sg_you, is_hero), "jade_human": components(sg_you, not_hero), "luckyj": components(sg_lj, is_hero),
            "tokujou_human": components(sg_lj, not_hero), **{p: components(sg_you, in_period(p)) for p in PERIODS}}
    edges = {"you": edge(comp["you"], comp["jade_human"], per_1000), "luckyj": edge(comp["luckyj"], comp["tokujou_human"], per_1000)}
    gap = {k: {"points": edges["luckyj"][k]["points"] - edges["you"][k]["points"],
               "rank_points": round((edges["luckyj"][k]["points"] - edges["you"][k]["points"]) * per_1000 / 1000, 1)} for k in ("win", "deal_ins", "tsumo_paid", "other", "net")}

    # --- the wins ------------------------------------------------------------------------------------------
    hero_rows = lambda rows, hero: [r for r in rows if r["seat"] == hero[r["game"]]]
    other_rows = lambda rows, hero: [r for r in rows if r["seat"] != hero[r["game"]]]
    r_you, r_ju = hero_rows(rows_you, hero_you), other_rows(rows_you, hero_you)
    r_lj, r_tk = hero_rows(rows_lj, hero_lj), other_rows(rows_lj, hero_lj)
    wins = {"you": win_sizes(r_you), "jade_human": win_sizes(r_ju), "luckyj": win_sizes(r_lj), "tokujou_human": win_sizes(r_tk),
            **{p: win_sizes([r for r in r_you if per[r["game"]] == p]) for p in PERIODS}}
    wy, wl = wins["you"], wins["luckyj"]
    frequency = (wy["wins_per_100"] - wl["wins_per_100"]) / 100 * wl["average"]
    size = wy["wins_per_100"] / 100 * (wy["average"] - wl["average"])
    wins["gap_to_luckyj"] = {"points_a_hand": wy["points_a_hand"] - wl["points_a_hand"], "from_how_often": round(frequency), "from_how_much": round(size),
                             "by_kind": {k: wy[k]["points_a_hand"] - wl[k]["points_a_hand"] for k in ("riichi", "dama", "open")},
                             "average_win": {"points": wy["average"] - wl["average"], "se": round(math.hypot(wy["average_se"], wl["average_se"]))},
                             "average_win_by_kind": {k: {"points": wy[k]["average"] - wl[k]["average"], "se": round(math.hypot(wy[k]["average_se"], wl[k]["average_se"]))} for k in ("riichi", "dama", "open")},
                             "wins_a_game": round(wy["wins"] / wy["games"], 2),
                             "rank_points_per_100_on_the_average_win": round(100 * wy["wins"] / wy["games"] * per_1000 / 1000, 1),
                             "rank_points_for_the_whole_gap": round((wl["average"] - wy["average"]) * wy["wins"] / wy["games"] * per_1000 / 1000, 1)}

    # --- the big deal-ins -------------------------------------------------------------------------------
    tail = {"you": big_tail(r_you), "jade_human": big_tail(r_ju), "luckyj": big_tail(r_lj), "tokujou_human": big_tail(r_tk),
            **{p: big_tail([r for r in r_you if per[r["game"]] == p]) for p in PERIODS}}
    early = [r for r in r_you if per[r["game"]] != "since"]
    late = [r for r in r_you if per[r["game"]] == "since"]
    k1, n1 = tail["before"]["big"] + tail["climb"]["big"], len(early)
    k2, n2 = tail["since"]["big"], len(late)
    pooled = (k1 + k2) / (n1 + n2)
    z = (k2 / n2 - k1 / n1) / math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    excess = k2 - k1 / n1 * n2
    tail["shift"] = {"before_the_peak_per_100": round(100 * k1 / n1, 2), "since_per_100": round(100 * k2 / n2, 2), "z": round(z, 1),
                     "expected_since_at_the_early_rate": round(k1 / n1 * n2, 1),
                     "points_a_game": round(excess * tail["since"]["average"] / tail["since"]["games"]),
                     "rank_points_a_game": round(excess * tail["since"]["average"] / tail["since"]["games"] * per_1000 / 1000, 1)}
    table = {}
    for p in PERIODS:
        o = [r for r in rows_you if r["seat"] != hero_you[r["game"]] and per[r["game"]] == p]
        table[p] = {"player_hands": len(o), "riichi_per_100": round(100 * sum(r["riichi_turn"] is not None for r in o) / len(o), 1),
                    "big_wins_per_100": round(100 * sum(1 for r in o if r["won"] and r["win_pts"] >= BIG) / len(o), 2)}

    # --- the cases since the peak ------------------------------------------------------------------------
    cases = deal_in_cases(manifest, per)
    since_cases = [c for c in cases if c["period"] == "since"]
    low = [c for c in since_cases if c["mortal"] is not None and c["mortal"] < LOW]
    into_open = [c for c in since_cases if c["own_riichi"] and c["winner_open"]]
    cause = {"since": len(since_cases), "mortal_under_25": len(low), "mortal_under_25_points": sum(c["paid"] for c in low),
             "own_riichi_into_open": {"count": len(into_open), "declared_at_99_percent": sum(1 for c in into_open if (c["mortal_riichi"] or 0) >= 0.99),
                                      "winner_not_yet_open": sum(1 for c in into_open if c["winner_calls_at_riichi"] == 0),
                                      "per_100_hands": round(100 * len(into_open) / tail["since"]["hands"], 2),
                                      "humans_per_100": round(100 * sum(1 for r in r_ju if r["dealt_in"] and -r["deal_pts"] >= BIG and r["deal_in_into"] == "open hand"
                                                                        and r["riichi_turn"] is not None and r["riichi_turn"] <= r["deal_in_turn"]) / len(r_ju), 2),
                                      "luckyj_per_100": round(100 * sum(1 for r in r_lj if r["dealt_in"] and -r["deal_pts"] >= BIG and r["deal_in_into"] == "open hand"
                                                                        and r["riichi_turn"] is not None and r["riichi_turn"] <= r["deal_in_turn"]) / len(r_lj), 2)},
             "low_cases": sorted(low, key=lambda c: -c["paid"]), "open_cases": into_open}

    replay_index = {g["id"]: g for g in json.loads((REPLAYS / "index.json").read_text())["games"]}
    by_period = {}
    for p in PERIODS:
        cs = [c for c in cases if c["period"] == p]
        flagged = [c for c in cs if c["mortal"] is not None and c["mortal"] < LOW]
        hands, games_p = tail[p]["hands"], tail[p]["games"]
        by_period[p] = {"big": len(cs), "flagged": len(flagged), "other": len(cs) - len(flagged), "flagged_per_100": round(100 * len(flagged) / hands, 2),
                        "other_per_100": round(100 * (len(cs) - len(flagged)) / hands, 2), "flagged_points_a_game": round(sum(c["paid"] for c in flagged) / games_p)}
    early_f = sum(by_period[p]["flagged"] for p in ("before", "climb")) / (tail["before"]["hands"] + tail["climb"]["hands"])
    early_o = sum(by_period[p]["other"] for p in ("before", "climb")) / (tail["before"]["hands"] + tail["climb"]["hands"])
    cause["by_period"] = by_period
    cause["excess_since"] = {"flagged": round(by_period["since"]["flagged"] - early_f * tail["since"]["hands"], 1), "other": round(by_period["since"]["other"] - early_o * tail["since"]["hands"], 1),
                             "flagged_per_100_early": round(100 * early_f, 2), "other_per_100_early": round(100 * early_o, 2)}
    out = {
        "games": len(manifest), "periods": {p: sum(1 for v in per.values() if v == p) for p in PERIODS},
        "rank_points_per_1000_points": per_1000, "formula_checked_against_the_records": checked,
        "pace": pace, "spread": spread, "components": comp, "edges": edges, "gap_to_luckyj": gap, "wins": wins,
        "big_deal_ins": tail, "tables": table, "cases": cause,
        "tilt": tilt(manifest, per, replay_index),
        "last_hand": {"you": last_hand(rows_you, manifest, lambda h: h), "jade_human": last_hand(rows_you, manifest, lambda h: not h),
                      "luckyj": last_hand(rows_lj, lj_manifest, lambda h: h), "tokujou_human": last_hand(rows_lj, lj_manifest, lambda h: not h)},
    }
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
