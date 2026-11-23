#!/usr/bin/env python3
"""How the Throne room should change the user's play: speed of the field, and tenpai pushes against a riichi.

``speed``: for every hand of the user's games, from the opponents' side: the turn of the first riichi or first call by
anyone else, the user's own first tenpai, and whether someone declared before the user was tenpai. Jade games and
Throne games are reported apart.

``spots``: the decisions of ``mine_tenpai_push.py`` (the user tenpai, someone else in riichi, every tile that keeps the
tenpai unsafe), with the tiles that keep the tenpai, the round and the scores, so each can be valued in Celestial
points and joined to Mortal's weights.

``mortal``: each spot's weight on pushing (every tile that keeps the tenpai, plus a riichi) under the two Mortals, read
from replay files built with each model (``build_replays.py --out DIR``): ``--policy DIR`` for the earlier policy
model, ``--s42 DIR`` for Mortal-S42.

    .venv/bin/python scripts/mine_throne_strategy.py speed OUT.json
    .venv/bin/python scripts/mine_throne_strategy.py spots OUT.json
    .venv/bin/python scripts/mine_throne_strategy.py mortal SPOTS.json --policy DIR --s42 DIR OUT.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

MANIFEST = ROOT / "data" / "self_games" / "majsoul" / "index.json"
SINCE = "2026-01-01"
SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}


SEATS = None  # set by --seats: a JSON list of {"file", "uuid", "mode", "hero_seat"} to mine instead of the user's games


def games():
    if SEATS is not None:
        return SEATS
    rows = [g for g in json.loads(MANIFEST.read_text()) if g["date"] >= SINCE]
    return sorted(rows, key=lambda g: g["start_time"])


def seat_rows(kind: str) -> list[dict]:
    """Every seat but the user's in the user's Jade games (``jade``), or every seat of the downloaded Throne games
    (``throne``, ``data/ladder_skill/throne_logs``)."""
    if kind == "jade":
        own = [g for g in json.loads(MANIFEST.read_text()) if g["date"] >= SINCE and g.get("mode") == "jade-south"]
        return [{"file": g["file"], "uuid": g["uuid"], "mode": "jade-field", "hero_seat": s}
                for g in own for s in range(4) if s != g["hero_seat"]]
    folder = ROOT / "data" / "ladder_skill" / "throne_logs"
    return [{"file": str(p), "uuid": p.stem, "mode": "throne-field", "hero_seat": s}
            for p in sorted(folder.glob("*.json")) for s in range(4)]


def speed(out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr

    hands = []
    for g in games():
        hero = g["hero_seat"]
        for log in tr.load_logs(str(ROOT / g["file"])):
            game = tr.replay(log)
            first_riichi = first_call = my_tenpai = None
            riichi_before_tenpai = False
            n = 0
            for e in game["events"]:
                n += 1  # discards so far at this table
                if e["seat"] != hero:
                    if e["riichi"] and first_riichi is None:
                        first_riichi = n
                        if my_tenpai is None:
                            riichi_before_tenpai = True
                    if e["called"] and first_call is None:
                        first_call = n
                    continue
                if my_tenpai is None and ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) == 0:
                    my_tenpai = e["turn"]
            hands.append({"game": g["uuid"], "room": g.get("mode"), "round": game["round_name"],
                          "first_riichi_discard": first_riichi, "first_call_discard": first_call,
                          "my_tenpai_turn": my_tenpai, "riichi_before_my_tenpai": riichi_before_tenpai,
                          "discards": n})
    Path(out).write_text(json.dumps(hands))
    print(out, len(hands), "hands")


def spots(out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import DANGER, meld_snapshots, safety, visible_counter
    from mine_open_tenpai_push import ron_value
    from tenhou_replay import base

    rows = []
    for g in games():
        hero = g["hero_seat"]
        for log in tr.load_logs(str(ROOT / g["file"])):
            game = tr.replay(log)
            p = game["players"][hero]
            indicators = game["dora_indicators"][:1]
            dset = frozenset(ws.dora_from_indicator(t) for t in indicators)
            blocks = tr.result_blocks(log[-1])
            riichi_turn = {q: next((x["turn"] for x in game["events"] if x["seat"] == q and x["riichi"]), None) for q in range(4)}
            for e in game["events"]:
                if e["seat"] != hero or e["riichi_seats"][hero] is not None:
                    continue
                reached = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
                if not reached:
                    continue
                keep = {}
                for t in {base(x): x for x in e["hand_before"]}.values():
                    rest = list(e["hand_before"])
                    rest.remove(t)
                    if ws.hand_shanten(rest, e["meld_tiles"], e["closed"]) == 0:
                        keep[base(t)] = (t, rest)
                if not keep:
                    continue
                snap = meld_snapshots(game, e["index"] - 1)
                snap[hero] = e["melds"]
                visible = visible_counter(e["hand_before"], e, game["players"], snap, indicators)

                def labels(t):
                    seen = visible.copy()
                    seen[base(t)] -= 1
                    return [safety(t, q, e, game, seen) for q in reached]

                if any(all(lab in SAFE for lab in labels(t)) for t, _ in keep.values()):
                    continue
                my_melds = p["melds"][: len(e["melds"])]
                best = (-1, -1)
                for t, rest in keep.values():
                    waits = tr.waits(rest, e["meld_tiles"], e["closed"])
                    live = sum(max(0, 4 - visible[base(w)]) for w in waits)
                    hans = [ron_value(rest, my_melds, w, hero, game["kyoku"], dset, riichi=e["closed"]) for w in waits]
                    han = max((h for h in hans if h is not None), default=0)
                    best = max(best, (live, han))
                start = log[1]
                rows.append({
                    "game": g["uuid"], "room": g.get("mode"), "round": game["round_name"], "kyoku": log[0][0],
                    "honba": log[0][1], "scores": list(start), "hero": hero, "closed": e["closed"], "turn": e["turn"],
                    "riichi_ago": e["turn"] - min(riichi_turn[q] or e["turn"] for q in reached), "riichis": len(reached),
                    "riichi_seats": reached, "keep": sorted(keep), "live": best[0], "han": best[1],
                    "pushed": ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) == 0,
                    "chased": bool(e["riichi"]), "cut": base(e["tile"]),
                    "danger": max(DANGER[lab] for lab in labels(e["tile"])),
                    "won": any(d[0] == hero for _, d in blocks),
                    "dealt": any(d[1] == hero and d[0] != hero for _, d in blocks),
                    "delta": tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero],
                    "place": sorted(range(4), key=lambda s: (-start[s], s)).index(hero) + 1,
                })
                break
    Path(out).write_text(json.dumps(rows))
    print(out, len(rows), "spots")


def hero_turns(hand, hero):
    turns, turn = [], 0
    for e in hand["ev"]:
        if e[1] == hero and ((e[0] == "t" and len(e) < 4) or e[0] in ("c", "p", "m")):
            turn += 1
        turns.append(turn)
    return turns


HONOR = {"E": 41, "S": 42, "W": 43, "N": 44, "P": 45, "F": 46, "C": 47}


def tile_code(a: str) -> int | None:
    """A replay tile name (5mr, 7p, E) as tenhou_replay's base code (15, 27, 41); None for an action."""
    if a in HONOR:
        return HONOR[a]
    if len(a) >= 2 and a[0].isdigit() and a[1] in "mps":
        return {"m": 10, "p": 20, "s": 30}[a[1]] + int(a[0])
    return None


def push_weight(replay_dir: Path, spot: dict) -> float | None:
    """The model's weight on keeping the tenpai at the spot: a riichi, or any tile in ``keep``."""
    path = replay_dir / f"{spot['game']}.json"
    if not path.exists():
        return None
    game = json.loads(path.read_text())
    hand = next((h for h in game["hands"] if h["round"] == spot["round"]), None)
    if hand is None:
        return None
    turns = hero_turns(hand, game["hero"])
    for d in hand.get("ai", []):
        if turns[d["i"]] != spot["turn"]:
            continue
        probs = dict(d["p"])
        if not any(a == "riichi" or tile_code(a) is not None for a in probs):
            continue  # a call decision on someone else's tile
        keep = set(spot["keep"])
        return min(1.0, probs.get("riichi", 0.0) + sum(v for a, v in probs.items() if tile_code(a) in keep))
    return None


def mortal(spots_path: str, policy_dir: str, s42_dir: str, out: str) -> None:
    rows = json.loads(Path(spots_path).read_text())
    for r in rows:
        r["policy_push"] = push_weight(Path(policy_dir), r)
        r["s42_push"] = push_weight(Path(s42_dir), r)
    Path(out).write_text(json.dumps(rows))
    print(out, sum(r["policy_push"] is not None for r in rows), sum(r["s42_push"] is not None for r in rows), "of", len(rows))


# Ron payments by han for a non-dealer winner at typical fu (30 fu below mangan, 40 fu for 1 han); a dealer is paid 1.5x.
RON = {0: 1000, 1: 1300, 2: 2000, 3: 3900, 4: 7700, 5: 8000, 6: 12000, 7: 12000, 8: 16000, 9: 16000, 10: 16000, 11: 24000,
       12: 24000}
DEAL_IN = 6000  # the mean payment of the user's 92 deal-ins from these spots; 1.5x into a dealer riichi
MODEL = None


def init_model():
    global MODEL
    import mine_push_ev as pe
    import mine_throne_shift as ts
    manifest = [g for g in json.loads(pe.MANIFEST.read_text()) if g["date"] >= pe.SINCE and g.get("mode") == "jade-south"]
    rel, keep = pe.pool(manifest)
    MODEL = ts.Finisher(rel, keep, sims=3000)


def value_spot(r: dict) -> dict:
    """Gain of winning the hand's value by ron from the riichi seat (plus its stick), and cost of dealing the mean
    deal-in into it, from the spot's position, under Saint 3 points and Celestial points."""
    import numpy as np
    k, hero, start = r["kyoku"], r["hero"], r["scores"]
    dealer = k % 4
    rs = min(r["riichi_seats"], key=lambda q: q != dealer)  # the dealer's riichi when there are two
    sticks = [1000 if q in r["riichi_seats"] else 0 for q in range(4)]
    now = [start[q] - sticks[q] for q in range(4)]
    base = MODEL.dist(k, now, hero)
    win = min(int(RON.get(min(r["han"], 12), 24000) * (1.5 if hero == dealer else 1)), 48000)
    s = list(now)
    s[hero] += win + sum(sticks)
    s[rs] -= win
    after_win = MODEL.after(k, s, hero == dealer, hero)
    pay = int(DEAL_IN * (1.5 if rs == dealer else 1))
    s = list(now)
    s[hero] -= pay
    s[rs] += pay + sum(sticks)
    after_deal = MODEL.after(k, s, rs == dealer, hero)
    out = {"win_points": win, "deal_points": pay}
    for name, col in (("saint3", 0), ("celestial", 1)):
        out[name] = {"gain": round(float(after_win[col] - base[col]), 2), "cost": round(float(base[col] - after_deal[col]), 2)}
    return out


def values(spots_path: str, out: str, procs: int = 12) -> None:
    from multiprocessing import Pool
    rows = json.loads(Path(spots_path).read_text())
    with Pool(procs, initializer=init_model) as pool:
        vals = pool.map(value_spot, rows, chunksize=4)
    for r, v in zip(rows, vals):
        r["value"] = v
    Path(out).write_text(json.dumps(rows))
    print(out, len(rows))


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if "--seats" in args:
        i = args.index("--seats")
        SEATS = seat_rows(args[i + 1])
        del args[i:i + 2]
    if cmd == "speed":
        speed(args[0])
    elif cmd == "spots":
        spots(args[0])
    elif cmd == "values":
        values(args[0], args[1])
    elif cmd == "mortal":
        i, j = args.index("--policy"), args.index("--s42")
        mortal(args[0], args[i + 1], args[j + 1], args[-1])
