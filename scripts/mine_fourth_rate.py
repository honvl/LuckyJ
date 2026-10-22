#!/usr/bin/env python3
"""The figures behind guide chapter 49: a high net win efficiency and still a fourth in about 22% of games.

Amae-koromo's net win efficiency is the win rate times the average win, minus the deal-in rate times the average
deal-in, in points a hand. For the user's last 100 Jade games, all of 2026, the other players at the user's tables and
LuckyJ's Tokujou games:

- the efficiency and what it leaves out: the points other players tsumo off the user, the draws and the riichi sticks;
- the places of the last 100 games and what each place's games looked like: points won, deal-ins, tsumo payments, a
  deal-in of 7,000 or more;
- how many fourths turn on their single biggest deal-in (that hand's points handed back from the winner to the user);
- the fourth rate at which the Saint 3 Jade formula breaks even for the user;
- what avoiding a share of the 7,000-point deal-ins would do to the last 100 games, hand by hand from the replays.

usage: mine_fourth_rate.py OUT.json
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import mine_climb_check as cc  # noqa: E402
import mine_costly_run as mc  # noqa: E402
import mine_rank_drain as rd  # noqa: E402

LAST = 100
BIG = 7000


def efficiency(rows: list[dict]) -> dict:
    h = len(rows)
    wins = [r for r in rows if r["won"]]
    deals = [r for r in rows if r["dealt_in"]]
    win = sum(r["win_pts"] for r in rows) / h
    loss = -sum(r["deal_pts"] for r in rows) / h
    return {"hands": h, "win_rate_pct": round(100 * len(wins) / h, 1), "average_win": round(float(np.mean([r["win_pts"] for r in wins]))), "win_efficiency": round(win),
            "deal_in_rate_pct": round(100 * len(deals) / h, 1), "average_deal_in": round(-float(np.mean([r["deal_pts"] for r in deals]))), "deal_in_loss": round(loss),
            "net_win_efficiency": round(win - loss), "tsumo_paid": round(sum(r["tsumo_pts"] for r in rows) / h),
            "draws_and_sticks": round(sum(r["draw_pts"] for r in rows) / h - sum(1000 * r["stick"] for r in rows) / h), "real_points_a_hand": round(sum(r["net"] for r in rows) / h)}


def places_of(scores: list[int]) -> list[int]:
    return rd.places_of(scores)


def main() -> None:
    out_path = sys.argv[1]
    manifest = sorted([g for g in json.loads(cc.MANIFEST.read_text(encoding="utf-8")) if g["date"] >= cc.SINCE], key=lambda g: g["start_time"])
    n = len(manifest)
    lj_manifest = [g for g in json.loads(cc.LJ_MANIFEST.read_text(encoding="utf-8")) if g["mode"] == "tenhou-tokujou"]
    hero = {g["uuid"].split("#")[0]: g["hero_seat"] for g in manifest}
    order = {g["uuid"].split("#")[0]: i for i, g in enumerate(manifest)}
    hero_lj = {g["uuid"].split("#")[0]: g["hero_seat"] for g in lj_manifest}
    rows = mc.hand_rows(manifest, "me")
    rows_lj = mc.hand_rows(lj_manifest, "lj")
    mine = [r for r in rows if r["seat"] == hero[r["game"]]]
    last = [r for r in mine if order[r["game"]] >= n - LAST]
    amae = json.loads(cc.AMAE.read_text())["stats"][-1]["body"]

    eff = {"last_100": efficiency(last), "all_2026": efficiency(mine), "jade_human": efficiency([r for r in rows if r["seat"] != hero[r["game"]]]),
           "luckyj": efficiency([r for r in rows_lj if r["seat"] == hero_lj[r["game"]]]),
           "amae_career": {"win_efficiency": amae["打点效率"], "deal_in_loss": amae["铳点损失"], "net_win_efficiency": amae["净打点效率"], "hands": amae["count"]}}

    # --- places -----------------------------------------------------------------------------------------------
    recs = {r[0]: r for r in json.loads(cc.AMAE.read_text())["records"]}
    last_games = manifest[n - LAST:]
    pl = [g["placement"] for g in last_games]
    rank_points = [next(p for p in recs[g["uuid"]][4] if p[0] == cc.ACCOUNT)[4] for g in last_games]
    places = {"last_100": {"places": [pl.count(i) for i in (1, 2, 3, 4)], "rank_points": sum(rank_points), "rank_points_a_game": round(sum(rank_points) / LAST, 1),
                           "mean_score": round(float(np.mean([g["final_scores"][g["hero_seat"]] for g in last_games])))}}
    all_pl = [g["placement"] for g in manifest]
    places["all_2026"] = {"games": n, "fourth_pct": round(100 * all_pl.count(4) / n, 1)}
    pace = json.loads((ROOT / "analysis" / "rank-drain-2026-10-19.json").read_text())["pace"]
    places["jade_human_fourth_pct"] = pace["jade_human"]["fourth_pct"]
    places["luckyj_fourth_pct"] = pace["luckyj"]["fourth_pct"]
    places["tokujou_human_fourth_pct"] = pace["tokujou_human"]["fourth_pct"]

    # --- what each place's games looked like --------------------------------------------------------------------
    by_game: dict[str, dict] = {}
    for r in last:
        c = by_game.setdefault(r["game"], {"won": 0, "dealt": 0, "tsumo": 0, "big": 0})
        c["won"] += r["win_pts"]
        c["dealt"] += -r["deal_pts"]
        c["tsumo"] += -r["tsumo_pts"]
        c["big"] = max(c["big"], -r["deal_pts"] if r["dealt_in"] else 0)
    placement = {g["uuid"].split("#")[0]: g["placement"] for g in manifest}
    table = {}
    for p in (1, 2, 3, 4):
        gs = [c for u, c in by_game.items() if placement[u] == p]
        table[str(p)] = {"games": len(gs), "points_won": round(float(np.mean([c["won"] for c in gs]))), "deal_ins": round(float(np.mean([c["dealt"] for c in gs]))),
                         "tsumo_paid": round(float(np.mean([c["tsumo"] for c in gs]))), "with_a_big_deal_in": sum(1 for c in gs if c["big"] >= BIG),
                         "with_a_big_deal_in_pct": round(100 * sum(1 for c in gs if c["big"] >= BIG) / len(gs))}
    with_big = [u for u, c in by_game.items() if c["big"] >= BIG]
    big_games = {"games_with_one": len(with_big), "fourths_among_them": sum(1 for u in with_big if placement[u] == 4),
                 "games_without": LAST - len(with_big), "fourths_among_those": sum(1 for u, c in by_game.items() if c["big"] < BIG and placement[u] == 4)}

    # --- fourths that turn on one deal-in, and the simulation --------------------------------------------------------
    games_data, flips = [], []
    for g in last_games:
        d = json.loads((ROOT / "site" / "replays" / f"{g['uuid']}.json").read_text())
        h_seat = d["hero"]
        deal_ins = []
        for hand in d["hands"]:
            if hand["end"]["kind"] != "win":
                continue
            for w in hand["end"]["wins"]:
                if w["from"] == h_seat and w["seat"] != h_seat:
                    deal_ins.append((-w["deltas"][h_seat], w["seat"], hand["round"]))
        games_data.append((list(g["final_scores"]), h_seat, [x for x in deal_ins if x[0] >= BIG], g["uuid"]))
        if g["placement"] == 4:
            if not deal_ins:
                flips.append({"game": g["uuid"], "round": None, "paid": 0, "place_without": 4})
                continue
            paid, winner, rnd = max(deal_ins)
            adj = list(g["final_scores"])
            adj[h_seat] += paid
            adj[winner] -= paid
            flips.append({"game": g["uuid"], "round": rnd, "paid": paid, "place_without": places_of(adj)[h_seat]})
    fourths = {"count": len(flips), "no_deal_in": sum(1 for f in flips if f["round"] is None), "not_fourth_without_the_biggest": sum(1 for f in flips if f["place_without"] < 4),
               "with_a_big_deal_in": sum(1 for f in flips if f["paid"] >= BIG), "list": flips}

    random.seed(1)
    sim = {"big_deal_ins": sum(len(g[2]) for g in games_data), "games_with_one": sum(1 for g in games_data if g[2])}
    for share in (0.0, 0.25, 0.5):
        f = r_sum = 0
        sims = 400
        for _ in range(sims):
            for scores, h_seat, big, _u in games_data:
                s = list(scores)
                for paid, winner, _rnd in big:
                    if random.random() < share:
                        s[h_seat] += paid
                        s[winner] -= paid
                place = places_of(s)[h_seat]
                f += place == 4
                r_sum += rd.rank_points(s[h_seat], place)
        sim[f"avoid_{int(share * 100)}"] = {"fourths_of_100": round(f / sims, 1), "rank_points_a_game": round(r_sum / sims / LAST, 1)}

    # --- the fourth rate that breaks even -------------------------------------------------------------------------
    rp_by_place = {p: [] for p in (1, 2, 3, 4)}
    for g in manifest:
        rp_by_place[g["placement"]].append(next(p for p in recs[g["uuid"]][4] if p[0] == cc.ACCOUNT)[4])
    avg = {p: float(np.mean(v)) for p, v in rp_by_place.items()}
    shares = {p: len(rp_by_place[p]) / (n - len(rp_by_place[4])) for p in (1, 2, 3)}
    a = sum(shares[p] * avg[p] for p in (1, 2, 3))
    break_even = round(100 * a / (a - avg[4]), 1)
    formula = {"rank_points_by_place": {str(p): round(avg[p]) for p in (1, 2, 3, 4)}, "break_even_fourth_pct": break_even}

    out = {"last": LAST, "efficiency": eff, "places": places, "by_place": table, "big_deal_in_games": big_games, "fourths": fourths, "simulation": sim, "formula": formula}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
