#!/usr/bin/env python3
"""The figures behind guide chapter 50: fifteen more games after chapter 48's ten, and what held up.

Chapter 48 looked at the ten games from 19 October 23:20 (7 firsts). This takes the 15 games after them (22 October 17:02
to 23 October 18:31) as a test on games it had not seen: places and rank points, the hands dealt 4-shanten or worse, speed,
how often a lone riichi was dealt into, and the deal-ins with Mortal's ratings and the user's turn.

usage: mine_run_update.py OUT.json
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import mine_climb_check as cc  # noqa: E402
import mine_costly_run as mc  # noqa: E402
import mine_recent_run as rr  # noqa: E402

FIRST_FROM = "2026-10-19 20:00"
SECOND_FROM = "2026-10-22 12:00"  # after the 22 October 03:29 game, before the 17:02 one
REPLAYS = ROOT / "site" / "replays"


def deal_in_rows(games: list[dict]) -> list[dict]:
    """Every deal-in with Mortal's rating of the tile (or of the riichi) and the user's turn number in the replay."""
    out = []
    replay_index = {g["id"]: g for g in json.loads((REPLAYS / "index.json").read_text())["games"]}
    deals, _ = mc.deal_ins_and_riichis([replay_index[g["uuid"]] for g in games])
    for d in deals:
        replay = json.loads((REPLAYS / f"{d['game']}.json").read_text())
        hero = replay["hero"]
        hand = next(h for h in replay["hands"] if h["round"] == d["round"])
        ev = hand["ev"]
        turns, t = {}, 0
        for i, e in enumerate(ev):
            if e[1] == hero and ((e[0] == "t" and not (len(e) > 3 and e[3])) or e[0] in ("c", "p", "m")):
                t += 1
            turns[i] = t
        last = max(i for i, x in enumerate(ev) if x[0] == "d" and x[1] == hero)
        riichi = [i for i, x in enumerate(ev) if x[0] == "r" and x[1] == hero and i < last]
        turn = turns[riichi[-1]] if d["kind"] == "riichi" and riichi else turns[last]
        out.append({"game": d["game"], "round": d["round"], "kind": d["kind"], "tile": d["tile"], "turn": turn, "paid": d["paid"], "mortal": round(d["mortal"], 3) if d["mortal"] is not None else None})
    return out


def game_summary(g: dict, rows: list[dict]) -> dict:
    mine = [r for r in rows if r["game"] == g["uuid"].split("#")[0]]
    return {"game": g["uuid"], "place": g["placement"], "final": g["final_scores"][g["hero_seat"]], "wins": sum(r["won"] for r in mine), "win_points": sum(r["win_pts"] for r in mine),
            "deal_in_points": -sum(r["deal_pts"] for r in mine), "tsumo_paid": -sum(r["tsumo_pts"] for r in mine), "biggest_hand_loss": -min(min(r["net"] for r in mine), 0)}


def main() -> None:
    out_path = sys.argv[1]
    manifest = sorted([g for g in json.loads(cc.MANIFEST.read_text(encoding="utf-8")) if g["date"] >= cc.SINCE], key=lambda g: g["start_time"])
    n = len(manifest)
    t1 = datetime.datetime.strptime(FIRST_FROM, "%Y-%m-%d %H:%M").timestamp()
    t2 = datetime.datetime.strptime(SECOND_FROM, "%Y-%m-%d %H:%M").timestamp()
    n_first = sum(1 for g in manifest if t1 <= g["start_time"] < t2)
    n_second = sum(1 for g in manifest if g["start_time"] >= t2)
    order = {g["uuid"].split("#")[0]: i for i, g in enumerate(manifest)}
    window = lambda game: "second" if order[game] >= n - n_second else "first" if order[game] >= n - n_second - n_first else "before"  # noqa: E731

    recs = {r[0]: r for r in json.loads(cc.AMAE.read_text())["records"]}
    results = {}
    parts = {"before": manifest[:n - n_second - n_first], "first": manifest[n - n_second - n_first: n - n_second], "second": manifest[n - n_second:], "run": manifest[n - n_second - n_first:]}
    for name, sel in parts.items():
        pts = [next(p for p in recs[g["uuid"]][4] if p[0] == cc.ACCOUNT)[4] for g in sel]
        pl = [g["placement"] for g in sel]
        results[name] = {"games": len(sel), "places": [pl.count(i) for i in (1, 2, 3, 4)], "rank_points": sum(pts), "rank_points_a_game": round(sum(pts) / len(pts), 1)}
    peak = datetime.datetime(2026, 10, 1, 22, 21).timestamp()
    since = [next(p for p in recs[g["uuid"]][4] if p[0] == cc.ACCOUNT)[4] for g in manifest if g["start_time"] > peak]
    results["since_the_peak"] = {"games": len(since), "rank_points": sum(since), "rank_points_a_game": round(sum(since) / len(since), 1)}

    rows = mc.hand_rows(manifest, "me")
    hero = {g["uuid"].split("#")[0]: g["hero_seat"] for g in manifest}
    mine = [dict(r, period=window(r["game"])) for r in rows if r["seat"] == hero[r["game"]]]
    others = [dict(r, period=window(r["game"])) for r in rows if r["seat"] != hero[r["game"]]]

    def pick(rs: list[dict], name: str) -> list[dict]:
        return [r for r in rs if (r["period"] in ("first", "second") if name == "run" else r["period"] == name)]

    hands, poor, speed = {}, {}, {}
    for name in ("before", "first", "second", "run"):
        rs = pick(mine, name)
        h = len(rs)
        w = [r for r in rs if r["won"]]
        d = [r for r in rs if r["dealt_in"]]
        hands[name] = {"hands": h, "tenpai_pct": rr.pct(sum(r["tenpai_turn"] is not None for r in rs), h), "won_pct": rr.pct(len(w), h), "tsumo_wins": sum(1 for r in w if r["tsumo"]),
                       "open_pct": rr.pct(sum(1 for r in rs if r["open"]), h), "riichi_pct": rr.pct(sum(r["riichi_turn"] is not None for r in rs), h), "dealt_in": len(d),
                       "dealt_in_pct": rr.pct(len(d), h), "big_deal_ins": sum(1 for r in d if -r["deal_pts"] >= mc.BIG), "big_per_100": round(100 * sum(1 for r in d if -r["deal_pts"] >= mc.BIG) / h, 1),
                       "points_a_hand": round(sum(r["net"] for r in rs) / h), "average_win": round(float(np.mean([r["win_pts"] for r in w]))),
                       "tenpai_by_turn_10_pct": rr.pct(sum(1 for r in rs if r["tenpai_turn"] is not None and r["tenpai_turn"] <= 10), h)}
        p4 = [r for r in rs if r["haipai_shanten"] >= 4]
        poor[name] = {"hands": len(p4), "won": sum(r["won"] for r in p4), "won_pct": rr.pct(sum(r["won"] for r in p4), len(p4)), "share_pct": rr.pct(len(p4), h)}
        o = pick(others, name)

        def removed(s: list[dict], t: int) -> float:
            v = [r["haipai_shanten"] - r["shanten_by_turn"][min(t, len(r["shanten_by_turn"])) - 1] for r in s if r["shanten_by_turn"] and r["haipai_shanten"] is not None]
            return round(float(np.mean(v)), 2)

        speed[name] = {"you_removed_by_turn_9": removed(rs, 9), "others_removed_by_turn_9": removed(o, 9)}
    for name in ("first", "second", "run"):
        poor[name]["z_vs_before"] = rr.two_prop_z((poor[name]["won"], poor[name]["hands"]), (poor["before"]["won"], poor["before"]["hands"]))
        hands[name]["z_won_vs_before"] = rr.two_prop_z((round(hands[name]["won_pct"] * hands[name]["hands"] / 100), hands[name]["hands"]), (round(hands["before"]["won_pct"] * hands["before"]["hands"] / 100), hands["before"]["hands"]))

    # --- lone riichi -------------------------------------------------------------------------------------------------
    with Pool(10) as pool:
        fr = pool.map(rr.fold_rows, manifest, chunksize=4)
    lone = {}
    for name in ("before", "first", "second", "run"):
        hs = {}
        for g, c in zip(manifest, fr):
            if (window(g["uuid"].split("#")[0]) in ("first", "second")) if name == "run" else window(g["uuid"].split("#")[0]) == name:
                for r in c:
                    h = hs.setdefault((r["game"], r["round"]), {"dealt": False})
                    h["dealt"] = h["dealt"] or r["hit"]
        lone[name] = {"hands": len(hs), "dealt_in": sum(h["dealt"] for h in hs.values())}
    rate = lone["before"]["dealt_in"] / lone["before"]["hands"]
    lone["usual_pct"] = round(100 * rate, 1)
    for name in ("first", "second", "run"):
        k, m = lone[name]["dealt_in"], lone[name]["hands"]
        lone[name]["expected"] = round(m * rate, 1)
        lone[name]["p_at_most"] = round(sum(math.comb(m, i) * rate ** i * (1 - rate) ** (m - i) for i in range(k + 1)), 3)

    # --- deal-ins and the two latest fourths -------------------------------------------------------------------------------
    second = parts["second"]
    deals = deal_in_rows(second)
    low = [d for d in deals if d["mortal"] is not None and d["mortal"] < mc.LOW]
    fourths = [game_summary(g, mine) for g in second if g["placement"] == 4]
    index = {g["id"]: g for g in json.loads((REPLAYS / "index.json").read_text())["games"]}
    mortal = {name: {"matched_pct": rr.pct(sum(index[g["uuid"]]["turns_matched"] for g in sel), sum(index[g["uuid"]]["turns"] for g in sel)),
                     "flagged_a_game": round(sum(index[g["uuid"]]["flagged"] for g in sel) / len(sel), 2)} for name, sel in (("before", parts["before"]), ("first", parts["first"]), ("second", parts["second"]))}

    out = {"first_from": FIRST_FROM, "second_from": SECOND_FROM, "results": results, "hands": hands, "poor_deals": poor, "speed": speed, "lone_riichi": lone, "mortal": mortal,
           "deal_ins": {"count": len(deals), "mortal_under_25": len(low), "list": deals, "low": low}, "fourths": fourths}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
