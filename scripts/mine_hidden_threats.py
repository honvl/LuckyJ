#!/usr/bin/env python3
"""Dama and one-call hands: how often they hit the user, what they cost, and what gives them away.

``deals``: every deal-in of the user since 1 January (Jade and Throne): the winner's hand as riichi, closed without
riichi (dama) or open with one call or more, what it cost, the turn, and whether the user was tenpai at the time.

``tells``: for every opponent who has not declared riichi, after each of their discards: are they tenpai? by how many
calls they have, the turn, how many discards in a row came straight from the draw (tsumogiri), and, for a caller,
the turn of the first call and whether it was a pon of a value tile (dragon, seat or round wind) or of dora. Seats are
the user's opponents in the user's Jade games and every seat of the 42 Throne games. Also what dama, open and
riichi wins were paid by ron.

    .venv/bin/python scripts/mine_hidden_threats.py OUT.json
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mine_throne_strategy as mts  # noqa: E402

DRAGONS = {45, 46, 47}  # 5z 6z 7z in tenhou6 numbering (41-47 = E S W N P F C)


def kind(game: dict, seat: int, riichi: bool) -> str:
    melds = [m for m in game["players"][seat]["melds"] if m.get("kind") not in ("a", "ankan")]
    if riichi:
        return "riichi"
    if not melds:
        return "dama"
    return "one call" if len(melds) == 1 else "two calls or more"


def dora_of(indicator: int) -> int:
    """The dora a tenhou6 indicator points to (11-19, 21-29, 31-39 suits; 41-44 winds, 45-47 dragons)."""
    t = norm(indicator)
    suit, n = divmod(t, 10)
    if suit < 4:
        return suit * 10 + n % 9 + 1
    return 41 + n % 4 if n <= 4 else 45 + (n - 4) % 3


def norm(t: int) -> int:
    return {51: 15, 52: 25, 53: 35}.get(t, t)


def walk(seats: list[dict]):
    """Yield (seat row, game, events) for every hand."""
    import tenhou_replay as tr
    for g in seats:
        for log in tr.load_logs(str(ROOT / g["file"])):
            yield g, log, tr.replay(log)


def deals(rows_out: list) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    for g, log, game in walk(mts.games()):
        hero = g["hero_seat"]
        riichi_now = set()
        last = {}
        for e in game["events"]:
            if e["riichi"]:
                riichi_now.add(e["seat"])
            if e["seat"] == hero:
                last = e
        for deltas, det in tr.result_blocks(log[-1]):
            w, frm = det[0], det[1]
            if frm != hero or w == hero:
                continue
            k = kind(game, w, w in riichi_now)
            tenpai = bool(last) and ws.hand_shanten(last["hand_after"], last["meld_tiles"], last["closed"]) == 0
            rows_out.append({"room": g.get("mode"), "kind": k, "paid": -deltas[hero], "turn": last.get("turn"),
                             "you_tenpai": tenpai, "round": game["round_name"]})


def tells(states: list, wins: list) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    for g, log, game in walk(mts.seat_rows("jade") + mts.seat_rows("throne")):
        seat = g["hero_seat"]
        dora = {dora_of(norm(i)) for i in game["dora_indicators"][:1]}
        round_wind = 41 + game["kyoku"] // 4
        seat_wind = 41 + ((seat - game["dealer"]) % 4)
        value = DRAGONS | {round_wind, seat_wind}
        streak, first_call, value_pon, riichi = 0, None, False, False
        closed_tenpai = None  # (turn, declared riichi at some point after)
        for e in game["events"]:
            if e["seat"] != seat:
                continue
            if e["riichi"]:
                riichi = True
                if closed_tenpai is None:
                    closed_tenpai = e["turn"]
            if riichi:
                break
            if closed_tenpai is None and e["closed"] and ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) == 0:
                closed_tenpai = e["turn"]
            if e["called"] and first_call is None:
                first_call = e["turn"]
                melds = game["players"][seat]["melds"]
                m = next((m for m in melds if m.get("kind") not in ("a", "ankan")), None)
                if m:
                    tiles = {norm(t) for t in m.get("tiles", [])}
                    value_pon = m.get("kind") != "c" and bool(tiles & (value | dora))
            streak = streak + 1 if e["tsumogiri"] else 0
            calls = e["meld_counts"].get(seat, 0) if isinstance(e.get("meld_counts"), dict) else len(e["melds"])
            states.append({"room": g["mode"], "turn": e["turn"], "calls": calls, "streak": streak,
                           "first_call": first_call, "value_pon": value_pon,
                           "tenpai": ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) == 0})
        won = None
        for deltas, det in tr.result_blocks(log[-1]):
            w, frm = det[0], det[1]
            if w == seat:
                won = "ron" if frm != w else "tsumo"
            if w == seat and frm != w:
                wins.append({"room": g["mode"], "kind": kind(game, w, riichi), "paid": -deltas[frm]})
        if closed_tenpai is not None:
            stayed_closed = not any(m.get("kind") not in ("a", "ankan") for m in game["players"][seat]["melds"])
            states.append({"room": g["mode"], "closed_tenpai_turn": closed_tenpai, "riichi": riichi,
                           "stayed_closed": stayed_closed, "won": won})


def rate(xs) -> dict:
    xs = list(xs)
    n = len(xs)
    p = sum(xs) / n if n else 0
    return {"n": n, "pct": round(100 * p, 1), "se": round(100 * (p * (1 - p) / n) ** 0.5, 1) if n else None}


def main(out: str) -> None:
    d, states, wins = [], [], []
    deals(d)
    tells(states, wins)
    choices = [s for s in states if "closed_tenpai_turn" in s]
    states = [s for s in states if "turn" in s]
    res_rooms = {}
    for room in ("jade-field", "throne-field"):
        ch = [c for c in choices if c["room"] == room]
        st = [s for s in states if s["room"] == room and s["calls"] == 0]
        wr = [w for w in wins if w["room"] == room]
        n = len(wr)

        def tb(t):
            return "1-6" if t <= 6 else "7-9" if t <= 9 else "10-12" if t <= 12 else "13+"
        res_rooms[room] = {
            "closed_tenpai_hands": len(ch),
            "stayed_dama_pct": rate(not c["riichi"] for c in ch),
            "stayed_dama_by_tenpai_turn": {b: rate(not c["riichi"] for c in ch if tb(c["closed_tenpai_turn"]) == b)
                                           for b in ("1-6", "7-9", "10-12", "13+")},
            "dama_hands_won_pct": rate(c["won"] is not None for c in ch if not c["riichi"]),
            "riichi_hands_won_pct": rate(c["won"] is not None for c in ch if c["riichi"]),
            "rons": n,
            "rons_by_kind": {k: {"share_pct": round(100 * sum(w["kind"] == k for w in wr) / max(1, n), 1),
                                 "avg_paid": round(float(np.mean([w["paid"] for w in wr if w["kind"] == k]))) if any(w["kind"] == k for w in wr) else None,
                                 "share_7700_plus_pct": round(100 * sum(w["paid"] >= 7700 for w in wr if w["kind"] == k) / max(1, sum(w["kind"] == k for w in wr)), 1)}
                             for k in ("riichi", "dama", "one call", "two calls or more")},
            "closed_no_riichi_tenpai_by_turn": {b: rate(x["tenpai"] for x in st if tb(x["turn"]) == b) for b in ("1-6", "7-9", "10-12", "13+")},
            "closed_turn_10_plus_by_streak": {str(k): rate(x["tenpai"] for x in st if x["turn"] >= 10 and min(x["streak"], 2) == k) for k in (0, 1, 2)},
        }
    res = {"deals": {}, "wins_by_ron": {}, "tenpai": {}, "by_room": res_rooms}
    for room in ("jade-south", "throne-south"):
        rows = [r for r in d if r["room"] == room]
        res["deals"][room] = {k: {"n": sum(1 for r in rows if r["kind"] == k),
                                  "share_pct": round(100 * sum(1 for r in rows if r["kind"] == k) / max(1, len(rows)), 1),
                                  "avg_paid": round(float(np.mean([r["paid"] for r in rows if r["kind"] == k])))
                                  if any(r["kind"] == k for r in rows) else None,
                                  "you_tenpai_pct": rate(r["you_tenpai"] for r in rows if r["kind"] == k)["pct"]}
                              for k in ("riichi", "dama", "one call", "two calls or more")}
        res["deals"][room]["total"] = len(rows)
    for k in ("riichi", "dama", "one call", "two calls or more"):
        x = [w["paid"] for w in wins if w["kind"] == k]
        res["wins_by_ron"][k] = {"n": len(x), "avg_paid": round(float(np.mean(x))) if x else None,
                                 "share_7700_plus_pct": round(100 * sum(v >= 7700 for v in x) / len(x), 1) if x else None}

    def bucket(t):
        return "1-6" if t <= 6 else "7-9" if t <= 9 else "10-12" if t <= 12 else "13+"

    closed = [s for s in states if s["calls"] == 0]
    one = [s for s in states if s["calls"] == 1]
    res["tenpai"]["closed, by turn"] = {b: rate(s["tenpai"] for s in closed if bucket(s["turn"]) == b) for b in ("1-6", "7-9", "10-12", "13+")}
    res["tenpai"]["closed, turn 10+, by tsumogiri streak"] = {
        str(k): rate(s["tenpai"] for s in closed if s["turn"] >= 10 and min(s["streak"], 3) == k) for k in (0, 1, 2, 3)}
    res["tenpai"]["one call, by turn"] = {b: rate(s["tenpai"] for s in one if bucket(s["turn"]) == b) for b in ("1-6", "7-9", "10-12", "13+")}
    res["tenpai"]["one call, turn 7+, value or dora pon vs other"] = {
        "value or dora pon": rate(s["tenpai"] for s in one if s["turn"] >= 7 and s["value_pon"]),
        "other call": rate(s["tenpai"] for s in one if s["turn"] >= 7 and not s["value_pon"])}
    res["tenpai"]["one call, turn 7+, by tsumogiri streak"] = {
        str(k): rate(s["tenpai"] for s in one if s["turn"] >= 7 and min(s["streak"], 3) == k) for k in (0, 1, 2, 3)}
    res["tenpai"]["one call, by turns since the call"] = {
        str(k): rate(s["tenpai"] for s in one if s["first_call"] is not None and min(s["turn"] - s["first_call"], 4) == k)
        for k in (0, 1, 2, 3, 4)}
    Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
