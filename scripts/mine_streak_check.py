#!/usr/bin/env python3
"""The figures behind guide chapter 34: three fourths in a row, from riichis LuckyJ declares.

The window is the user's three newest games, 11 October 20:27 to 21:33 (the first started before chapter 33 went up,
the other two after it). Every riichi of the window is set against the riichi rows of ``contrast/tenpai.py``:

- the window's games: place, final score, rank points (amae-koromo, anchored as in chapter 27), and how often your
  discards and calls were Mortal's top choice there and in your games before (``site/replays/index.json``);
- every riichi: turn, wait, live tiles, value, whether another player was in riichi, Mortal's weight on declaring
  (``site/replays``), LuckyJ's rate for the same first tenpai (chapter 33's fit, ``mine_climb_check``) when nobody
  was in riichi, and the hand's result;
- every deal-in, with Mortal's top choices at the discard that was ronned;
- where the window's points went, from the scores before and after each hand (riichi sticks included): hands with
  your riichi, deal-ins without one, other players' tsumo, draws, and your wins without a riichi;
- the user's riichis since January before the window against LuckyJ's 2,171 Tokujou riichis: won, dealt in, the
  hand's points from your seat, and the share that lost points;
- how often LuckyJ's own riichis give what the window's gave: resampling 8 of its riichis, the chance of 3 deal-ins
  or more and of losing at least as many points (``SEED``);
- LuckyJ's runs of three fourths in a row in its 1,255 games, and the chance that a player who places as LuckyJ
  does has one somewhere in 199 games;
- LuckyJ's chase riichis (first tenpai with someone already in riichi) by value and live tiles.

usage: mine_streak_check.py TENPAI_YOU TENPAI_LJ OUT.json
  TENPAI_YOU: ``contrast/tenpai.py`` over your games since 1 January; TENPAI_LJ: over LuckyJ's Tokujou games.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mine_climb_check as cc  # noqa: E402
import mine_dama_value as dv  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
REPLAYS = ROOT / "site/replays"
WINDOW = ("261012-4c37163a", "261012-5dae20fd", "261012-1d8ad962")
SEED, DRAWS, RUN_SIMS = 1, 200000, 20000
REL = ("you", "shimocha", "toimen", "kamicha")


def pct(k: float, n: int, digits: int = 1) -> float | None:
    return round(100 * k / n, digits) if n else None


def round_name(r: dict) -> str:
    return f"{'East' if r['k'] < 4 else 'South'} {r['k'] % 4 + 1}-{r['h']}"


def rank_points() -> dict[str, dict]:
    """Rank points before and after each game (chapter 27's anchor), with the place, by game id."""
    recs = sorted(json.loads(cc.AMAE.read_text())["records"], key=lambda r: r[1])
    deltas = [next(p for p in r[4] if p[0] == cc.ACCOUNT)[4] for r in recs]
    anchor = next(k for k, r in enumerate(recs) if r[0].startswith(cc.ANCHOR_GAME))
    before = [0] * len(recs)
    before[anchor] = cc.ANCHOR
    for k in range(anchor + 1, len(recs)):
        before[k] = before[k - 1] + deltas[k - 1]
    for k in range(anchor - 1, -1, -1):
        before[k] = before[k + 1] - deltas[k]
    out = {}
    for k, r in enumerate(recs):
        me = next(p for p in r[4] if p[0] == cc.ACCOUNT)
        out[r[0]] = {"place": sorted(r[4], key=lambda p: -p[3]).index(me) + 1, "score": me[3],
                     "before": before[k], "after": before[k] + deltas[k]}
    return out


def replay(game: str) -> dict:
    return json.loads((REPLAYS / f"{game}.json").read_text(encoding="utf-8"))


def mortal_riichi(game: str, rnd: str) -> list[float]:
    """Mortal's weight on declaring, for each riichi the user declared in the hand, in order."""
    d = replay(game)
    h = next(h for h in d["hands"] if h["round"] == rnd)
    ais = {a["i"]: a for a in h["ai"]}
    return [dict(ais[i - 1]["p"]).get("riichi", 0.0) for i, x in enumerate(h["ev"]) if x[0] == "r" and x[1] == d["hero"]]


def hands_and_deal_ins(game: str) -> tuple[list[dict], list[dict]]:
    d = replay(game)
    hero = d["hero"]
    hands, deals = [], []
    for h in d["hands"]:
        ev, end = h["ev"], h["end"]
        ais = {a["i"]: a for a in h["ai"]}
        declared = any(x[0] == "r" and x[1] == hero for x in ev)
        delta = h["after"][hero] - h["scores"][hero]  # riichi sticks included
        if end["kind"] == "win":
            won = any(w["seat"] == hero for w in end["wins"])
            dealt = [w for w in end["wins"] if w["from"] == hero and w["seat"] != hero]
            tsumo = [w for w in end["wins"] if w["from"] == w["seat"] and w["seat"] != hero]
        else:
            won, dealt, tsumo = False, [], []
        if declared:
            kind = "your riichi"
        elif won:
            kind = "your win"
        elif dealt:
            kind = "deal-in"
        elif tsumo:
            kind = "tsumo against you"
        elif end["kind"] != "win":
            kind = "draw"
        else:
            kind = "others"
        hands.append({"round": h["round"], "kind": kind, "delta": delta})
        for w in dealt:
            last = max(i for i, x in enumerate(ev) if x[0] == "d" and x[1] == hero)
            a = ais.get(last - 1) or ais.get(last)
            deals.append({"game": game, "round": h["round"], "tile": ev[last][2], "paid": -w["deltas"][hero],
                          "value": w["value"], "winner": REL[(w["seat"] - hero) % 4], "in_riichi": declared,
                          "mortal_top": [[t, round(p, 3)] for t, p in sorted(a["p"], key=lambda x: -x[1])[:3]] if a else []})
    return hands, deals


def summary(rows: list[dict]) -> dict:
    n = len(rows)
    return {"riichis": n, "won": pct(sum(r["won"] for r in rows), n), "dealt": pct(sum(r["dealt"] for r in rows), n),
            "points": round(sum(r["net"] for r in rows) / n), "lost_points": pct(sum(r["net"] < 0 for r in rows), n)}


def runs_of_fourths(places: list[int], k: int = 3) -> list[int]:
    """Lengths of every run of k or more fourths in a row."""
    out, run = [], 0
    for p in places + [0]:
        if p == 4:
            run += 1
            continue
        if run >= k:
            out.append(run)
        run = 0
    return out


def main() -> None:
    tenpai_you, tenpai_lj, out_path = sys.argv[1:4]
    manifest = {g["uuid"]: g for g in json.loads(MANIFEST.read_text(encoding="utf-8"))}
    window = [next(u for u in manifest if u.startswith(w)) for w in WINDOW]
    points = rank_points()
    games = [{"game": u, "date": manifest[u]["date"], **points[u]} for u in window]

    lj_first = [r for r in cc.first_tenpais(tenpai_lj) if r["nr"] == 0]
    beta, _ = cc.fit(lj_first)
    rate = lambda r: float(1 / (1 + np.exp(-np.dot(cc.features(r), beta))))
    firsts = {(r["g"], r["li"], r["t"]): r for r in cc.first_tenpais(tenpai_you)}

    you_rows = [json.loads(line) for line in open(tenpai_you)]
    you_riichis = [r for r in you_rows if r["lj"] and r["riichi"]]
    riichis = []
    weights = {}
    for r in sorted((r for r in you_riichis if r["g"] in window), key=lambda r: (window.index(r["g"]), r["li"], r["t"])):
        rnd = round_name(r)
        key = (r["g"], rnd)
        weights.setdefault(key, mortal_riichi(r["g"], rnd))
        opt = next(o for o in r["opts"] if o["b"] == r["cut"])
        first = firsts.get((r["g"], r["li"], r["t"]))
        riichis.append({"game": r["g"], "round": rnd, "turn": r["t"], "wait": opt["shape"], "live": opt["live"],
                        "han": opt["dama_min"], "into_a_riichi": r["nr"] >= 1, "dealer": bool(r["dl"]),
                        "mortal": round(weights[key].pop(0), 3),
                        "luckyj": round(rate(first), 3) if first and r["nr"] == 0 else None,
                        "won": r["won"], "dealt": r["dealt"], "net": r["net"]})

    hands, deals = [], []
    for u in window:
        h, d = hands_and_deal_ins(u)
        hands += h
        deals += d
    where = {}
    for h in hands:
        w = where.setdefault(h["kind"], {"hands": 0, "points": 0})
        w["hands"] += 1
        w["points"] += h["delta"]

    lj_rows = [json.loads(line) for line in open(tenpai_lj)]
    lj_riichis = [r for r in lj_rows if r["lj"] and r["riichi"]]
    before = [r for r in you_riichis if r["g"] not in window]
    long_run = {"you": summary(before), "luckyj": summary(lj_riichis),
                "you_first": summary([r for r in before if r["first"] and r["nr"] == 0]),
                "luckyj_first": summary([r for r in lj_riichis if r["first"] and r["nr"] == 0]),
                "window": summary([r for r in you_riichis if r["g"] in window])}

    n, lost = len(riichis), sum(r["net"] for r in riichis)
    dealt = sum(r["dealt"] for r in riichis)
    rng = random.Random(SEED)
    hits_dealt = hits_lost = 0
    for _ in range(DRAWS):
        pick = [rng.choice(lj_riichis) for _ in range(n)]
        hits_dealt += sum(r["dealt"] for r in pick) >= dealt
        hits_lost += sum(r["net"] for r in pick) <= lost
    luck = {"riichis": n, "dealt": dealt, "points": lost, "p_dealt": pct(hits_dealt, DRAWS), "p_points": pct(hits_lost, DRAWS)}

    lj_games = sorted(json.loads(LJ_MANIFEST.read_text(encoding="utf-8")), key=lambda g: g["start_time"])
    places = [g["placement"] for g in lj_games]
    rng = random.Random(SEED)
    sims = sum(1 for _ in range(RUN_SIMS) if runs_of_fourths([rng.choice(places) for _ in range(199)]))
    streaks = {"games": len(places), "fourth_rate": pct(places.count(4), len(places)), "runs": runs_of_fourths(places),
               "chance_in_199": pct(sims, RUN_SIMS)}

    chase_rows = [r for r in dv.first_tenpais(tenpai_lj) if r["nr"] >= 1]
    chase = {}
    for value, keep_v in (("no yaku", lambda r: r["v"] == 0), ("1-2 han", lambda r: 1 <= r["v"] <= 2), ("3+ han", lambda r: r["v"] >= 3)):
        for live, keep_l in (("3 or fewer", lambda r: r["live"] <= 3), ("4-5", lambda r: 4 <= r["live"] <= 5),
                             ("6 or more", lambda r: r["live"] >= 6)):
            s = [r for r in chase_rows if keep_v(r) and keep_l(r)]
            chase[f"{value}, {live} live"] = {"tenpais": len(s), "declared": sum(r["riichi"] for r in s),
                                              "declared_pct": pct(sum(r["riichi"] for r in s), len(s))}
    s = [r for r in chase_rows if 1 <= r["v"] <= 2 and 4 <= r["live"] <= 5 and r["two"] and 10 <= r["t"] <= 12]
    chase["1-2 han, 4-5 live, two-sided, turns 10-12"] = {"tenpais": len(s), "declared": sum(r["riichi"] for r in s),
                                                          "declared_pct": pct(sum(r["riichi"] for r in s), len(s))}

    index = [g for g in json.loads((REPLAYS / "index.json").read_text(encoding="utf-8"))["games"] if g["date"] >= "2026-01-01"]
    agreement = {}
    for name, keep in (("window", lambda g: g["id"] in window), ("before", lambda g: g["id"] not in window)):
        gs = [g for g in index if keep(g)]
        agreement[name] = {"games": len(gs), "discards": pct(sum(g["turns_matched"] for g in gs), sum(g["turns"] for g in gs)),
                           "calls": pct(sum(g["calls_matched"] for g in gs), sum(g["calls"] for g in gs))}

    out = {"games": games, "agreement": agreement, "riichis": riichis, "deal_ins": deals, "where": where, "long_run": long_run, "luck": luck,
           "streaks": streaks, "chase": chase}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
