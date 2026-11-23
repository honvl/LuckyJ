#!/usr/bin/env python3
"""Where a player's edge lands among the four places, and what that does to each rank's line (guide chapter 56).

Chapter 53 measured, for each site, how the four finishing shares move with a seat's strength over its table
("share slopes", per place of strength): in the Jade room an edge turns mostly into fewer fourths, in the Houou room
it splits evenly between more firsts and fewer fourths. This script asks what that split is worth:

- every rank's break-even under its own room's split and under the other site's split (``break_even_gap`` of
  chapter 53, with the same rank points), and the line it gives on chapter 53's scale;
- what an edge is worth per place of strength under Saint 3's, 8-dan's and Celestial's points with each split, and
  how many games a player at a given strength needs for 1,000 Saint 3 points;
- the split in the Throne room, measured the same way on its tables;
- the user's split (370 Jade games) and LuckyJ's (1,079 Tokujou games), as a mix ``lambda`` between the Jade split
  (0) and the Houou split (1), with a bootstrap over games.

    .venv/bin/python scripts/mine_edge_split.py [OUT.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mine_tier_ranking as tr  # noqa: E402

LADDER = ROOT / "analysis" / "tier-ranking-2026-11-20.json"
OUT = ROOT / "analysis" / "edge-split-2026-11-23.json"
CELESTIAL = [50, 20, -20, -50]
RNG = np.random.default_rng(20261123)


def value(points, slopes):
    """Rank points a game gained per place of strength over the table."""
    return sum(p * c for p, c in zip(points, slopes))


def throne_slopes(ms):
    """The Throne room's split, from every Throne table, with chapter 53's strengths for its tiers."""
    raw, _ = tr.load_rooms()
    tiers = ms["tiers"]
    strength = {"Saint 1": tiers["Saint 1, in the Throne room"]["a"], "Saint 2": tiers["Saint 2, in the Throne room"]["a"],
                "Saint 3": tiers["Saint 3, in the Throne room"]["a"], "Celestial": tiers["Celestial"]["a"]}
    tables = []
    for _, seats in raw[tr.THRONE]:
        lv = [tr.SAINT.get(s[0]) or "Celestial" for s in seats]
        tables.append((lv, tr.places([s[1] for s in seats])))
    return tr.share_slopes(tables, strength), len(tables)


def mix(places, J, H, reps=2000):
    """The split of a player's edge as a mix between the Jade split (0) and the Houou split (1)."""
    places = np.asarray(places)

    def fit(p):
        g = 2.5 - p.mean()
        d = np.array([(p == k).mean() - 0.25 for k in (1, 2, 3, 4)])
        x = g * (H - J)
        return float(((d - g * J) * x).sum() / (x ** 2).sum()), g, d

    lam, g, d = fit(places)
    boots = np.array([fit(places[RNG.integers(0, len(places), len(places))])[0] for _ in range(reps)])
    return {"games": int(len(places)), "mean_place": round(float(places.mean()), 3), "edge": round(g, 4),
            "shares": [round(float((places == k).mean()), 4) for k in (1, 2, 3, 4)],
            "shares_se": [round(float(np.sqrt((places == k).mean() * (1 - (places == k).mean()) / len(places))), 4) for k in (1, 2, 3, 4)],
            "if_jade_split": [round(0.25 + g * c, 4) for c in J], "if_houou_split": [round(0.25 + g * c, 4) for c in H],
            "lambda": round(lam, 3), "lambda_se": round(float(boots.std(ddof=1)), 3),
            "lambda_95": [round(float(np.percentile(boots, 2.5)), 3), round(float(np.percentile(boots, 97.5)), 3)]}


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    ladder = json.loads(LADDER.read_text(encoding="utf-8"))
    ms, th, link = ladder["mahjong_soul"], ladder["houou"], ladder["link"]["policy"]
    J, H = np.array(ms["share_slopes"]["jade"]), np.array(th["share_slopes"])
    T, throne_tables = throne_slopes(ms)
    splits = {"jade": [round(float(c), 4) for c in J], "houou": [round(float(c), 4) for c in H], "throne": T,
              "throne_tables": throne_tables,
              "fourths_per_first": {"jade": round(float(-J[3] / J[0]), 2), "houou": round(float(-H[3] / H[0]), 2),
                                    "throne": round(-T[3] / T[0], 2)}}

    # each rank's line on chapter 53's scale, with its own room's split and with the other site's
    lines = {}
    for name in ("Saint 1", "Saint 2", "Saint 3"):
        row = ms["to_pass"][name]["jade"]
        pts = ms["rank_points"][tr.JADE][name]
        g_j, g_h = tr.break_even_gap(pts, J), tr.break_even_gap(pts, H)
        lines[name] = {"points": pts, "points_sum": round(sum(pts), 1),
                       "jade_split": {"mean_place_needed": round(2.5 - g_j, 3), "a": round(row["opponents"] + g_j, 4)},
                       "houou_split": {"mean_place_needed": round(2.5 - g_h, 3), "a": round(row["opponents"] + g_h, 4)}}
    for d in tr.DANS[:4]:
        pts = th["rank_points"][d]
        base = link["field_a"] + th["opponents_vs_field"][d]
        g_h, g_j = tr.break_even_gap(pts, H), tr.break_even_gap(pts, J)
        lines[d] = {"points": pts, "points_sum": sum(pts),
                    "houou_split": {"mean_place_needed": round(2.5 - g_h, 3), "a": round(base + g_h, 4)},
                    "jade_split": {"mean_place_needed": round(2.5 - g_j, 3), "a": round(base + g_j, 4)}}
    lines["Celestial"] = {"points": CELESTIAL, "points_sum": 0, "note": "points sum to zero: break-even at 2.50 under any split"}

    # what an edge is worth, per place of strength over the table
    worth = {}
    for key, pts in (("Saint 3", ms["rank_points"][tr.JADE]["Saint 3"]), ("八段", th["rank_points"]["八段"]),
                     ("Celestial", CELESTIAL)):
        worth[key] = {"jade_split": round(value(pts, J), 1), "houou_split": round(value(pts, H), 1),
                      "throne_split": round(value(pts, T), 1), "fee": round(-0.25 * sum(pts), 2)}

    # Saint 3 points a game for players at chapter 53 strengths, with each split, at Saint 3's Jade tables
    s3 = ms["rank_points"][tr.JADE]["Saint 3"]
    opp = ms["to_pass"]["Saint 3"]["jade"]["opponents"]
    pace = []
    for scale in (2.50, 2.49, 2.48, 2.47, 2.46, 2.44, 2.42, 2.40):
        g = (2.5 - scale) - opp
        row = {"scale": scale}
        for key, c in (("jade_split", J), ("houou_split", H)):
            per_game = 0.25 * sum(s3) + value(s3, c) * g
            row[key] = round(per_game, 2)
            row[key + "_games_per_1000"] = round(1000 / per_game) if per_game > 0 else None
        pace.append(row)

    # the user's and LuckyJ's own splits
    idx = json.loads((ROOT / "data" / "self_games" / "majsoul" / "index.json").read_text(encoding="utf-8"))
    yours = [g["placement"] for g in idx if g["mode"] == "jade-south"]
    lj_idx = json.loads((ROOT / "data" / "local_sources" / "luckyj_tenhou" / "index.json").read_text(encoding="utf-8"))
    lj = [g["placement"] for g in lj_idx if g["mode"] == "tenhou-tokujou"]
    obs = ms["observed"]["Saint 3, Jade room"]
    anchor = {"seats": obs["seats"], "mean_place": obs["mean_place"], "shares": obs["shares"]}
    g = 2.5 - obs["mean_place"]
    d = np.array(obs["shares"]) - 0.25
    x = g * (H - J)
    anchor["lambda"] = round(float(((d - g * J) * x).sum() / (x ** 2).sum()), 3)

    out = {"splits": splits, "lines": lines, "worth": worth, "saint3_pace": pace,
           "saint3_jade_opponents": opp, "average_saint3": anchor,
           "you": mix(yours, J, H), "luckyj": mix(lj, J, H),
           "eight_dan_holder_a": ladder["tenhou_on_the_scale"]["八段"]["a_fit"],
           "you_scale": {"mortal": round(2.5 - ladder["you"]["a_from_mortal"], 3),
                         "results": round(2.5 - ladder["you"]["a_from_results"], 3)}}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
