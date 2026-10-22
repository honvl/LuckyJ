#!/usr/bin/env python3
"""The figures behind guide chapter 48: the ten games from 19 October 23:20 to 22 October, 7 firsts and +866 rank points.

The user said they had started winning again after folding harder with fewer defensive tiles. This compares those 10
games (103 hands) with the 217 before them, and with the 68 from the peak to the 19 October game that ended fourth:

- places, rank points and how far the run is from the user's own average;
- the hands: tenpai, wins by kind, tsumo wins, opens, riichis, deal-ins and their size, by what the other players were doing;
- speed: shanten removed by turns 6, 9 and 12 against the other three players at the same tables, tenpai by turn 10;
- the early game: Mortal's flags by turn, and the lone terminals and honors still in hand after the 3rd, 6th and 9th discards;
- folds: every discard into a lone riichi by a player who was not tenpai afterwards, by distance and by how many of their
  own discards had passed since the declaration, and the discards where the hand held a winning tile of the riichi;
- what luck can do: the chance of the run's firsts, fourths and tsumo wins at the user's usual rates.

usage: mine_recent_run.py OUT.json
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import mine_climb_check as cc  # noqa: E402
import mine_costly_run as mc  # noqa: E402

NEW_FROM = "2026-10-19 20:00"  # after the 19 October 19:05 game that ended fourth
PEAK_GAP = 68  # the games from the peak to the one before the run
REPLAYS = ROOT / "site" / "replays"
JUNK = set("ESWNPFC")
BUCKETS = (("1-3", 1, 3), ("4-6", 4, 6), ("7-9", 7, 9), ("10-12", 10, 12), ("13+", 13, 99))


def norm(tile: str) -> str:
    return tile[:-1] if tile.endswith("r") and len(tile) == 3 else tile


def two_prop_z(a: tuple[int, int], b: tuple[int, int]) -> float:
    p = (a[0] + b[0]) / (a[1] + b[1])
    se = math.sqrt(p * (1 - p) * (1 / a[1] + 1 / b[1]))
    return round((a[0] / a[1] - b[0] / b[1]) / se, 1) if se else 0.0


def binom_tail_ge(k: int, n: int, p: float) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def pct(a: int, n: int, digits: int = 1) -> float:
    return round(100 * a / n, digits) if n else 0.0


# --- per game, from the replays: decisions by situation, turn and hand ----------------------------------------------

def replay_stats(job) -> dict:
    uuid, = job
    d = json.loads((REPLAYS / f"{uuid}.json").read_text(encoding="utf-8"))
    hero = d["hero"]
    out = {"turn": defaultdict(lambda: [0, 0, 0]), "situation": defaultdict(lambda: [0, 0, 0]), "riichi_safe": [0, 0.0, 0], "caller_safe": [0, 0.0, 0],
           "junk": {k: [0, 0] for k in (3, 6, 9)}}
    for h in d["hands"]:
        ev = h["ev"]
        turns, t = {}, 0
        for i, e in enumerate(ev):
            if e[1] == hero and ((e[0] == "t" and not (len(e) > 3 and e[3])) or e[0] in ("c", "p", "m")):
                t += 1
            turns[i] = t
        riichi_at = {}
        for i, e in enumerate(ev):
            if e[0] == "r":
                riichi_at.setdefault(e[1], i)
        for a in h["ai"]:
            i = a["i"]
            e = ev[i]
            if e[0] != "t" or e[1] != hero:
                continue
            p_you = dict(a["p"]).get(a["you"], 0.0)
            matched, flagged = a["p"][0][0] == a["you"], p_you < 0.05
            tt = turns[i]
            bucket = next(b for b, lo, hi in BUCKETS if lo <= tt <= hi) if tt else "1-3"
            out["turn"][bucket][0] += 1
            out["turn"][bucket][1] += matched
            out["turn"][bucket][2] += flagged
            own = riichi_at.get(hero)
            others = [q for q, k in riichi_at.items() if q != hero and k < i]
            melds = Counter(x[1] for x in ev[:i] if x[0] in ("c", "p", "m") and x[1] != hero)
            sit = "own riichi" if own is not None and own < i else "riichi on the table" if others else "callers, no riichi" if melds else "quiet"
            out["situation"][sit][0] += 1
            out["situation"][sit][1] += matched
            out["situation"][sit][2] += flagged
            tiles = [(norm(x), p) for x, p in a["p"] if x not in ("riichi", "kan", "pass", "win", "draw")]
            if not tiles or a["you"] in ("riichi", "kan"):
                continue
            if sit == "riichi on the table" and len(others) == 1:
                q = others[0]
                safe = {norm(x[2]) for x in ev[:i] if x[0] == "d" and x[1] == q} | {norm(x[2]) for x in ev[riichi_at[q] + 1:i] if x[0] == "d"}
                if any(x in safe for x, _ in tiles):
                    out["riichi_safe"][0] += 1
                    out["riichi_safe"][1] += norm(a["you"]) in safe
                    out["riichi_safe"][2] += sum(p for x, p in tiles if x in safe)
            if sit == "callers, no riichi":
                safe = None
                for q in melds:
                    s = {norm(x[2]) for x in ev[:i] if x[0] == "d" and x[1] == q}
                    safe = s if safe is None else safe & s
                if any(x in safe for x, _ in tiles):
                    out["caller_safe"][0] += 1
                    out["caller_safe"][1] += norm(a["you"]) in safe
                    out["caller_safe"][2] += sum(p for x, p in tiles if x in safe)
        # lone terminals and honors in the closed hand after the 3rd, 6th and 9th discards
        hand = Counter(norm(x) for x in h["haipai"][hero])
        nd = 0
        for e in ev:
            if e[1] != hero:
                continue
            if e[0] == "t":
                hand[norm(e[2])] += 1
            elif e[0] in ("c", "p", "m"):
                for x in e[4]:
                    hand[norm(x)] -= 1
            elif e[0] == "d":
                hand[norm(e[2])] -= 1
                nd += 1
                if nd in out["junk"]:
                    out["junk"][nd][0] += sum(1 for x, c in hand.items() if c == 1 and (x in JUNK or x[0] in "19"))
                    out["junk"][nd][1] += 1
    return {"turn": {k: v for k, v in out["turn"].items()}, "situation": {k: v for k, v in out["situation"].items()}, "riichi_safe": out["riichi_safe"], "caller_safe": out["caller_safe"],
            "junk": out["junk"]}


# --- per game, from the logs: every discard into a lone riichi ------------------------------------------------------

def fold_rows(g) -> list[dict]:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, visible_counter  # noqa: F401
    from tenhou_replay import base, name

    hero, out = g["hero_seat"], []
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        events = game["events"]
        waits = {e["seat"]: {base(w) for w in tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])} for e in events if e["riichi"]}
        for e in events:
            if e["seat"] != hero or e.get("tile") is None:
                continue
            reached = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            if len(reached) != 1 or e["riichi_seats"][hero] is not None or not waits.get(reached[0]):
                continue
            q = reached[0]
            r = e["riichi_seats"][q]
            hb = e["hand_before"]
            after = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
            best = min(ws.hand_shanten(hb[:k] + hb[k + 1:], e["meld_tiles"], e["closed"]) for k in range(len(hb)))
            passed = {base(x["tile"]) for x in events[r + 1: e["index"]] if x.get("tile") is not None}
            ref = {base(x) for x in e["rivers"][q]} | passed
            thrown = base(e["tile"])
            held_winning = sorted({name(base(x)) for x in hb if base(x) in waits[q]})
            out.append({"game": g["uuid"].split("#")[0], "round": game["round_name"], "turn": e["turn"], "tenpai_after": after == 0, "best": best, "real_fold": after > best,
                        "safe": thrown in ref, "hit": thrown in waits[q], "had_genbutsu": any(base(x) in ref for x in hb), "since": sum(1 for x in events[r + 1: e["index"]] if x["seat"] == hero and x.get("tile") is not None),
                        "held_winning": held_winning, "thrown": name(e["tile"])})
    return out


def fold_summary(rows: list[dict]) -> dict:
    a = [r for r in rows if not r["tenpai_after"]]

    def line(s: list[dict]) -> dict:
        return {"n": len(s), "safe": sum(r["safe"] for r in s), "real_fold": sum(r["real_fold"] for r in s), "dealt_in": sum(r["hit"] for r in s)}

    return {"decisions": line(a), "far": line([r for r in a if r["best"] >= 2]), "far_first_discard": line([r for r in a if r["best"] >= 2 and r["since"] == 0]),
            "far_later": line([r for r in a if r["best"] >= 2 and r["since"] >= 1]), "one_shanten": line([r for r in a if r["best"] == 1]),
            "had_genbutsu": sum(r["had_genbutsu"] for r in a), "held_a_winning_tile": line([r for r in rows if r["held_winning"] and not r["hit"]])}


def main() -> None:
    out_path = sys.argv[1]
    manifest = sorted([g for g in json.loads(cc.MANIFEST.read_text(encoding="utf-8")) if g["date"] >= cc.SINCE], key=lambda g: g["start_time"])
    cut = datetime.datetime.strptime(NEW_FROM, "%Y-%m-%d %H:%M").timestamp()
    n = len(manifest)
    new_n = sum(1 for g in manifest if g["start_time"] >= cut)
    order = {g["uuid"].split("#")[0]: i for i, g in enumerate(manifest)}
    where = lambda game: "new" if order[game] >= n - new_n else "peak" if order[game] >= n - new_n - PEAK_GAP else "before"  # noqa: E731
    sd = float(np.std([next(p for p in r[4] if p[0] == cc.ACCOUNT)[4] for r in json.loads(cc.AMAE.read_text())["records"] if r[1] >= datetime.datetime(2026, 1, 1).timestamp()]))

    # --- results ----------------------------------------------------------------------------------------------
    recs = {r[0]: r for r in json.loads(cc.AMAE.read_text())["records"]}
    results = {}
    for name, sel in (("new", manifest[n - new_n:]), ("before", manifest[:n - new_n]), ("peak", manifest[n - new_n - PEAK_GAP: n - new_n])):
        pts = [next(p for p in recs[g["uuid"]][4] if p[0] == cc.ACCOUNT)[4] for g in sel]
        pl = [g["placement"] for g in sel]
        results[name] = {"games": len(sel), "places": [pl.count(i) for i in (1, 2, 3, 4)], "rank_points": sum(pts), "rank_points_a_game": round(sum(pts) / len(pts), 1),
                         "mean_score": round(sum(g["final_scores"][g["hero_seat"]] for g in sel) / len(sel))}
    mean_before = results["before"]["rank_points_a_game"]
    first_rate = results["before"]["places"][0] / results["before"]["games"]
    fourth_rate = results["before"]["places"][3] / results["before"]["games"]
    results["luck"] = {"sd_a_game": round(sd, 1), "sd_of_ten": round(sd / math.sqrt(new_n), 1), "z_vs_before": round((results["new"]["rank_points_a_game"] - mean_before) / (sd / math.sqrt(new_n)), 2),
                       "p_firsts_at_least": round(binom_tail_ge(results["new"]["places"][0], new_n, first_rate), 4), "first_rate_before": round(100 * first_rate, 1),
                       "p_fourths_at_most": round(1 - binom_tail_ge(results["new"]["places"][3] + 1, new_n, fourth_rate), 4), "fourth_rate_before": round(100 * fourth_rate, 1)}

    # --- hands ------------------------------------------------------------------------------------------------
    rows = mc.hand_rows(manifest, "me")
    hero = {g["uuid"].split("#")[0]: g["hero_seat"] for g in manifest}
    byhand = defaultdict(list)
    for r in rows:
        byhand[(r["game"], r["li"])].append(r)
    mine, other_rows = [], []
    for k, rs in byhand.items():
        me = dict(next(r for r in rs if r["seat"] == hero[k[0]]))
        oth = [r for r in rs if r["seat"] != hero[k[0]]]
        me["opp_riichi"] = min((r["riichi_turn"] for r in oth if r["riichi_turn"] is not None), default=None)
        me["opp_open"] = sum(1 for r in oth if r["open"])
        me["period"] = where(k[0])
        mine.append(me)
        other_rows += [dict(r, period=where(k[0])) for r in oth]
    by = lambda name: [r for r in mine if r["period"] == name]  # noqa: E731
    old = [r for r in mine if r["period"] != "new"]

    def hand_line(rs: list[dict]) -> dict:
        h = len(rs)
        w = [r for r in rs if r["won"]]
        d = [r for r in rs if r["dealt_in"]]
        return {"hands": h, "tenpai": sum(r["tenpai_turn"] is not None for r in rs), "won": len(w), "tsumo_wins": sum(1 for r in w if r["tsumo"]), "riichi": sum(r["riichi_turn"] is not None for r in rs),
                "open": sum(1 for r in rs if r["open"]), "open_wins": sum(1 for r in w if r["open"] and r["riichi_turn"] is None),
                "riichi_wins": sum(1 for r in w if r["riichi_turn"] is not None), "dama_wins": sum(1 for r in w if not r["open"] and r["riichi_turn"] is None),
                "dealt_in": len(d), "average_win": round(float(np.mean([r["win_pts"] for r in w]))) if w else None, "average_deal_in": round(-float(np.mean([r["deal_pts"] for r in d]))) if d else None,
                "big_deal_ins": sum(1 for r in d if -r["deal_pts"] >= mc.BIG), "points_a_hand": round(sum(r["net"] for r in rs) / h),
                "deal_ins_into": {k: sum(1 for r in d if r["deal_in_into"] == k) for k in ("riichi", "open hand", "dama")}}

    hands = {name: hand_line(by(name)) for name in ("new", "peak", "before")}
    hands["old"] = hand_line(old)
    z = {}
    for key in ("tenpai", "won", "tsumo_wins", "riichi", "open", "open_wins", "dama_wins", "dealt_in"):
        z[key] = two_prop_z((hands["new"][key], hands["new"]["hands"]), (hands["old"][key], hands["old"]["hands"]))
    hands["z_new_vs_old"] = z
    hands["tsumo_wins_expected"] = round(hands["new"]["hands"] * hands["old"]["tsumo_wins"] / hands["old"]["hands"], 1)
    hands["p_tsumo_wins_at_least"] = round(binom_tail_ge(hands["new"]["tsumo_wins"], hands["new"]["hands"], hands["old"]["tsumo_wins"] / hands["old"]["hands"]), 4)

    sit = {}
    for name, f in (("riichi by turn 8", lambda r: r["opp_riichi"] is not None and r["opp_riichi"] <= 8),
                    ("callers only", lambda r: r["opp_riichi"] is None and r["opp_open"] >= 1),
                    ("quiet", lambda r: r["opp_riichi"] is None and r["opp_open"] == 0)):
        sit[name] = {}
        for period in ("new", "peak", "old"):
            s = [r for r in (by(period) if period != "old" else old) if f(r)]
            sit[name][period] = {"hands": len(s), "tenpai_pct": pct(sum(r["tenpai_turn"] is not None for r in s), len(s)), "won_pct": pct(sum(r["won"] for r in s), len(s)),
                                 "open_pct": pct(sum(r["open"] for r in s), len(s)), "points_a_hand": round(sum(r["net"] for r in s) / len(s))}

    # --- speed -------------------------------------------------------------------------------------------------
    def removed(rs: list[dict], t: int) -> float:
        v = [r["haipai_shanten"] - r["shanten_by_turn"][min(t, len(r["shanten_by_turn"])) - 1] for r in rs if r["shanten_by_turn"] and r["haipai_shanten"] is not None]
        return round(float(np.mean(v)), 2)

    speed = {}
    for who, pool in (("you", mine), ("others", other_rows)):
        speed[who] = {}
        for period in ("new", "peak", "old"):
            s = [r for r in pool if (r["period"] == period if period != "old" else r["period"] != "new")]
            speed[who][period] = {"hands": len(s), "haipai_shanten": round(float(np.mean([r["haipai_shanten"] for r in s])), 2), "removed_by_turn_6": removed(s, 6), "removed_by_turn_9": removed(s, 9),
                                  "removed_by_turn_12": removed(s, 12), "tenpai_by_turn_10_pct": pct(sum(1 for r in s if r["tenpai_turn"] is not None and r["tenpai_turn"] <= 10), len(s))}

    # --- the replays: Mortal's flags by turn, folds against Mortal's rate, lone terminals and honors -------------------
    with Pool(10) as pool:
        stats = pool.map(replay_stats, [(g["uuid"],) for g in manifest], chunksize=6)
    agg = {p: {"turn": defaultdict(lambda: [0, 0, 0]), "situation": defaultdict(lambda: [0, 0, 0]), "riichi_safe": [0, 0.0, 0], "caller_safe": [0, 0.0, 0], "junk": {3: [0, 0], 6: [0, 0], 9: [0, 0]}, "games": 0} for p in ("new", "peak", "before")}
    for g, st in zip(manifest, stats):
        a = agg[where(g["uuid"].split("#")[0])]
        a["games"] += 1
        for key in ("turn", "situation"):
            for k, v in st[key].items():
                for j in range(3):
                    a[key][k][j] += v[j]
        for key in ("riichi_safe", "caller_safe"):
            for j in range(3):
                a[key][j] += st[key][j]
        for k in (3, 6, 9):
            a["junk"][k][0] += st["junk"][str(k)][0] if str(k) in st["junk"] else st["junk"][k][0]
            a["junk"][k][1] += st["junk"][str(k)][1] if str(k) in st["junk"] else st["junk"][k][1]
    for p in ("old",):
        agg[p] = {"turn": defaultdict(lambda: [0, 0, 0]), "situation": defaultdict(lambda: [0, 0, 0]), "riichi_safe": [0, 0.0, 0], "caller_safe": [0, 0.0, 0], "junk": {3: [0, 0], 6: [0, 0], 9: [0, 0]}, "games": 0}
        for q in ("peak", "before"):
            agg[p]["games"] += agg[q]["games"]
            for key in ("turn", "situation"):
                for k, v in agg[q][key].items():
                    for j in range(3):
                        agg[p][key][k][j] += v[j]
            for key in ("riichi_safe", "caller_safe"):
                for j in range(3):
                    agg[p][key][j] += agg[q][key][j]
            for k in (3, 6, 9):
                agg[p]["junk"][k][0] += agg[q]["junk"][k][0]
                agg[p]["junk"][k][1] += agg[q]["junk"][k][1]
    early = {}
    for p in ("new", "peak", "old"):
        a = agg[p]
        early[p] = {"games": a["games"], "by_turn": {b: {"decisions": a["turn"][b][0], "matched_pct": pct(a["turn"][b][1], a["turn"][b][0]), "flagged_a_game": round(a["turn"][b][2] / a["games"], 2)} for b, _, _ in BUCKETS},
                    "matched_pct": pct(sum(v[1] for v in a["turn"].values()), sum(v[0] for v in a["turn"].values())),
                    "flagged_a_game": round(sum(v[2] for v in a["turn"].values()) / a["games"], 2),
                    "flagged_turns_1_to_6_a_game": round((a["turn"]["1-3"][2] + a["turn"]["4-6"][2]) / a["games"], 2),
                    "lone_terminals_and_honors_after_discard": {str(k): round(a["junk"][k][0] / a["junk"][k][1], 2) for k in (3, 6, 9)},
                    "situations": {s: {"decisions": v[0], "matched_pct": pct(v[1], v[0]), "flagged_a_game": round(v[2] / a["games"], 2)} for s, v in a["situation"].items()},
                    "safe_tile_against_a_riichi": {"decisions": a["riichi_safe"][0], "you_pct": pct(a["riichi_safe"][1], a["riichi_safe"][0]), "mortal_pct": round(100 * a["riichi_safe"][2] / a["riichi_safe"][0], 1)},
                    "safe_tile_against_callers": {"decisions": a["caller_safe"][0], "you_pct": pct(a["caller_safe"][1], a["caller_safe"][0]), "mortal_pct": round(100 * a["caller_safe"][2] / a["caller_safe"][0], 1)}}
        early[p]["safe_tile_against_a_riichi"]["extra_per_100"] = round(early[p]["safe_tile_against_a_riichi"]["you_pct"] - early[p]["safe_tile_against_a_riichi"]["mortal_pct"], 1)
        early[p]["safe_tile_against_callers"]["extra_per_100"] = round(early[p]["safe_tile_against_callers"]["you_pct"] - early[p]["safe_tile_against_callers"]["mortal_pct"], 1)

    # --- folds -------------------------------------------------------------------------------------------------
    with Pool(10) as pool:
        fr = pool.map(fold_rows, manifest, chunksize=4)
    f_rows = [r | {"period": where(r["game"])} for c in fr for r in c]
    folds = {"new": fold_summary([r for r in f_rows if r["period"] == "new"]), "old": fold_summary([r for r in f_rows if r["period"] != "new"])}
    saved = [r for r in f_rows if r["period"] == "new" and r["held_winning"] and not r["hit"]]
    lone = {}
    for period in ("new", "peak", "before", "old"):
        hands_by = {}
        for r in f_rows:
            if (r["period"] == period) if period != "old" else (r["period"] != "new"):
                h = hands_by.setdefault((r["game"], r["round"]), {"held": False, "dealt": False})
                h["held"] = h["held"] or bool(r["held_winning"])
                h["dealt"] = h["dealt"] or r["hit"]
        held = [h for h in hands_by.values() if h["held"]]
        lone[period] = {"hands": len(hands_by), "dealt_in": sum(h["dealt"] for h in hands_by.values()), "held_a_winning_tile": len(held), "dealt_in_holding_one": sum(h["dealt"] for h in held)}
    rate = lone["old"]["dealt_in"] / lone["old"]["hands"]
    lone["expected_new_deal_ins"] = round(lone["new"]["hands"] * rate, 1)
    lone["p_no_deal_in"] = round((1 - rate) ** lone["new"]["hands"], 4)
    held_rate = lone["old"]["dealt_in_holding_one"] / lone["old"]["held_a_winning_tile"]
    lone["p_never_threw_it"] = round((1 - held_rate) ** lone["new"]["held_a_winning_tile"], 4)

    deal = {}
    for period in ("new", "peak", "old"):
        deal[period] = {}
        for label, pred in (("0-2", lambda r: r["haipai_shanten"] <= 2), ("3", lambda r: r["haipai_shanten"] == 3), ("4+", lambda r: r["haipai_shanten"] >= 4)):
            s = [r for r in (by(period) if period != "old" else old) if pred(r)]
            deal[period][label] = {"hands": len(s), "tenpai": sum(r["tenpai_turn"] is not None for r in s), "won": sum(r["won"] for r in s), "won_pct": pct(sum(r["won"] for r in s), len(s))}
    deal["z_4_plus_new_vs_old"] = two_prop_z((deal["new"]["4+"]["won"], deal["new"]["4+"]["hands"]), (deal["old"]["4+"]["won"], deal["old"]["4+"]["hands"]))
    deal["share_4_plus"] = {p: pct(deal[p]["4+"]["hands"], sum(v["hands"] for k, v in deal[p].items() if k in ("0-2", "3", "4+"))) for p in ("new", "peak", "old")}

    # --- the deal-ins ------------------------------------------------------------------------------------------
    replay_index = {g["id"]: g for g in json.loads((REPLAYS / "index.json").read_text())["games"]}
    deals = {}
    for name, sel in (("new", manifest[n - new_n:]), ("peak", manifest[n - new_n - PEAK_GAP: n - new_n]), ("before", manifest[:n - new_n - PEAK_GAP])):
        ds, _ = mc.deal_ins_and_riichis([replay_index[g["uuid"]] for g in sel])
        low = [d for d in ds if d["mortal"] is not None and d["mortal"] < mc.LOW]
        deals[name] = {"games": len(sel), "deal_ins": len(ds), "points_paid_a_game": round(sum(d["paid"] for d in ds) / len(sel)), "mortal_under_25": len(low), "points_on_those_a_game": round(sum(d["paid"] for d in low) / len(sel))}
    ds_old, _ = mc.deal_ins_and_riichis([replay_index[g["uuid"]] for g in manifest[:n - new_n]])
    low_old = [d for d in ds_old if d["mortal"] is not None and d["mortal"] < mc.LOW]
    deals["old"] = {"games": n - new_n, "deal_ins": len(ds_old), "points_paid_a_game": round(sum(d["paid"] for d in ds_old) / (n - new_n)), "mortal_under_25": len(low_old),
                    "points_on_those_a_game": round(sum(d["paid"] for d in low_old) / (n - new_n))}
    deals["list"] = [{"game": d["game"], "round": d["round"], "kind": d["kind"], "tile": d["tile"], "paid": d["paid"], "mortal": round(d["mortal"], 3)} for d in mc.deal_ins_and_riichis([replay_index[g["uuid"]] for g in manifest[n - new_n:]])[0]]

    out = {"from": NEW_FROM, "games": new_n, "results": results, "hands": hands, "situations": sit, "speed": speed, "early": early, "folds": folds,
           "lone_riichi": lone, "poor_deals": deal, "deal_ins": deals}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
