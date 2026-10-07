#!/usr/bin/env python3
"""The figures behind guide chapter 29, "Another losing run: five choices cost 60,500 points".

The window is the user's ten newest games when the chapter was written, 3 October 14:11 to 7 October
15:27. It is compared with the 163 games before it, and with LuckyJ's 1,079 Tokujou games for the hand
columns. Mortal's ratings are the ones stored in ``site/replays/*.json``.

For each deal-in the rating is the probability Mortal gave the user's own choice: the discard that was
ronned, or, when the user was already in riichi, the riichi declaration that took the choice away (a
riichi turn shows Mortal's weight on ``riichi`` against cutting the tile).

Run it from the repo root with the project venv (it has ``mahjong`` and ``libriichi``)::

    .venv/bin/python scripts/mine_costly_run.py             # writes analysis/costly-run-2026-10-07.json
"""

from __future__ import annotations

import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import hands_all  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
REPLAYS = ROOT / "site/replays"
OUT = ROOT / "analysis/costly-run-2026-10-07.json"
WINDOW = 10
BIG = 7000
LOW = 0.25


def hand_rows(manifest: list[dict], grp: str) -> list[dict]:
    seen = {}
    for g in manifest:
        seen.setdefault(g["file"], dict(g, grp=grp, lj_seat=g["hero_seat"]))
    with Pool(8) as pool:
        res = pool.map(hands_all.work, list(seen.values()), chunksize=8)
    return [r for chunk in res for r in chunk]


def hero_rows(rows: list[dict], manifest: list[dict]) -> list[dict]:
    seat = {g["uuid"]: g["hero_seat"] for g in manifest}
    return [r for r in rows if r["seat"] == seat[r["game"]]]


def hand_summary(rows: list[dict]) -> dict:
    won = [r for r in rows if r["won"]]
    dealt = [r for r in rows if r["dealt_in"]]
    big = [r for r in dealt if r["deal_pts"] <= -BIG]
    n = len(rows)
    return {
        "hands": n, "won": len(won), "won_rate": len(won) / n,
        "avg_win": sum(r["win_pts"] for r in won) / len(won),
        "dealt_in": len(dealt), "deal_in_rate": len(dealt) / n,
        "avg_deal_in": sum(r["deal_pts"] for r in dealt) / len(dealt),
        "big_deal_ins": len(big), "big_deal_in_rate": len(big) / n,
        "points_a_hand": sum(r["net"] for r in rows) / n,
    }


def placements(games: list[dict]) -> dict:
    p = [g["placement"] for g in games]
    return {"games": len(p), "places": [p.count(i) for i in (1, 2, 3, 4)], "average": sum(p) / len(p),
            "fourth_rate": p.count(4) / len(p)}


def rate(replay_games: list[dict]) -> dict:
    return {
        "discards": sum(g["turns"] for g in replay_games),
        "matched": sum(g["turns_matched"] for g in replay_games),
        "calls": sum(g["calls"] for g in replay_games),
        "calls_matched": sum(g["calls_matched"] for g in replay_games),
    }


def deal_ins_and_riichis(replay_games: list[dict]) -> tuple[list[dict], list[dict]]:
    deals, riichis = [], []
    for g in replay_games:
        d = json.loads((REPLAYS / f"{g['id']}.json").read_text(encoding="utf-8"))
        hero = d["hero"]
        for h in d["hands"]:
            ev = h["ev"]
            ais = {a["i"]: a for a in h["ai"]}
            for i, x in enumerate(ev):
                if x[0] == "r" and x[1] == hero:
                    a = ais.get(i - 1)
                    riichis.append({"game": g["id"], "round": h["round"], "riichi": dict(a["p"]).get("riichi", 0.0)})
            end = h["end"]
            if end["kind"] != "win":
                continue
            for w in end["wins"]:
                if w["seat"] == hero or w["from"] != hero:
                    continue
                last = max(i for i, x in enumerate(ev) if x[0] == "d" and x[1] == hero)
                declared = [i for i, x in enumerate(ev) if x[0] == "r" and x[1] == hero and i < last]
                if declared and (declared[-1] >= last - 1 or not any(j in ais for j in (last - 1, last))):
                    a, kind = ais.get(declared[-1] - 1), "riichi"
                else:
                    a, kind = ais.get(last - 1) or ais.get(last), "cut"
                deals.append({
                    "game": g["id"], "date": g["date"], "round": h["round"], "kind": kind, "tile": ev[last][2],
                    "paid": -w["deltas"][hero], "value": w["value"],
                    "mortal": dict(a["p"]).get(a["you"], 0.0) if a else None,
                })
    return deals, riichis


def riichi_outcomes(replay_games: list[dict]) -> dict:
    """Every riichi the user declared in the replays, split by Mortal's weight on declaring it, with the hand's result."""
    rows = []
    for g in replay_games:
        d = json.loads((REPLAYS / f"{g['id']}.json").read_text(encoding="utf-8"))
        hero = d["hero"]
        for h in d["hands"]:
            ais = {a["i"]: a for a in h["ai"]}
            for i, x in enumerate(h["ev"]):
                if x[0] != "r" or x[1] != hero:
                    continue
                weight = dict(ais[i - 1]["p"]).get("riichi", 0.0)
                end, result = h["end"], "draw"
                if end["kind"] == "win":
                    if any(w["seat"] == hero for w in end["wins"]):
                        result = "won"
                    elif any(w["from"] == hero for w in end["wins"]):
                        result = "dealt"
                    else:
                        result = "paid"
                other = any(y[0] == "r" and y[1] != hero for y in h["ev"][:i])
                turn = sum(1 for y in h["ev"][:i] if y[0] == "t" and y[1] == hero)
                rows.append((weight, result, other, turn))
    out = {}
    for name, rs in (("mortal_low", [r for r in rows if r[0] < LOW]), ("mortal_agreed", [r for r in rows if r[0] >= LOW])):
        out[name] = {"riichis": len(rs), "won": sum(1 for r in rs if r[1] == "won"),
                     "dealt": sum(1 for r in rs if r[1] == "dealt"), "into_a_riichi": sum(1 for r in rs if r[2]),
                     "average_turn": sum(r[3] for r in rs) / len(rs)}
    return out


def main() -> None:
    os.chdir(ROOT)
    manifest = sorted(json.loads(MANIFEST.read_text(encoding="utf-8")), key=lambda g: g["start_time"])
    recent, before = manifest[-WINDOW:], manifest[:-WINDOW]
    recent_ids = {g["uuid"] for g in recent}
    mine = hero_rows(hand_rows(manifest, "me"), manifest)
    lj_manifest = [g for g in json.loads(LJ_MANIFEST.read_text(encoding="utf-8")) if g["mode"] == "tenhou-tokujou"]
    lj = [r for r in hand_rows(lj_manifest, "lj") if r["lj"]]

    replays = sorted(json.loads((REPLAYS / "index.json").read_text(encoding="utf-8"))["games"], key=lambda g: g["date"])
    deals, riichis = deal_ins_and_riichis(replays[-WINDOW:])
    low = [d for d in deals if d["mortal"] is not None and d["mortal"] < LOW]
    big = [d for d in deals if d["paid"] >= BIG]
    out = {
        "window": {"first": recent[0]["date"], "last": recent[-1]["date"], "games": WINDOW},
        "places": {"before": placements(before), "recent": placements(recent)},
        "hands": {
            "before": hand_summary([r for r in mine if r["game"] not in recent_ids]),
            "recent": hand_summary([r for r in mine if r["game"] in recent_ids]),
            "luckyj": hand_summary(lj),
        },
        "mortal": {"before": rate(replays[:-WINDOW]), "recent": rate(replays[-WINDOW:])},
        "deal_ins": deals,
        "deal_in_summary": {
            "total": len(deals),
            "mortal_half": sum(1 for d in deals if d["mortal"] is not None and d["mortal"] >= 0.5),
            "mortal_low": len(low),
            "low_paid": sum(d["paid"] for d in low),
            "big": len(big),
            "big_mortal_half": sum(1 for d in big if d["mortal"] is not None and d["mortal"] >= 0.5),
            "big_mortal_low": sum(1 for d in big if d["mortal"] is not None and d["mortal"] < LOW),
            "big_low_paid": sum(d["paid"] for d in big if d["mortal"] is not None and d["mortal"] < LOW),
            "big_paid": sum(d["paid"] for d in big),
        },
        "riichi_outcomes_since_january": riichi_outcomes(replays),
        "riichis": {
            "count": len(riichis),
            "mortal_low": sum(1 for r in riichis if r["riichi"] < LOW),
            "lowest_agreed": min(r["riichi"] for r in riichis if r["riichi"] >= LOW),
        },
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    for k in ("places", "hands", "mortal", "deal_in_summary", "riichis", "riichi_outcomes_since_january"):
        print(k, json.dumps(out[k], ensure_ascii=False))


if __name__ == "__main__":
    main()
