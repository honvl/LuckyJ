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


def open_wins(out: str) -> None:
    """Every win at the mined seats: open or closed, how many calls, what it was paid, its han and dora."""
    import re
    import tenhou_replay as tr

    han_re = re.compile(r"\((\d+)飜\)")
    rows = []
    for g in games():
        for log in tr.load_logs(str(ROOT / g["file"])):
            game = tr.replay(log)
            for deltas, det in tr.result_blocks(log[-1]):
                w, frm = det[0], det[1]
                if w != g["hero_seat"]:
                    continue
                melds = [m for m in game["players"][w]["melds"] if m.get("kind") != "ankan"]
                yaku = [y for y in det[4:] if isinstance(y, str)]
                limit = any("役満" in y for y in yaku) or "役満" in str(det[3])
                rows.append({"room": g.get("mode"), "open": bool(melds), "calls": len(melds),
                             "paid": -deltas[frm] if frm != w else -sum(d for d in deltas if d < 0),
                             "han": 13 if limit else sum(int(h) for y in yaku for h in han_re.findall(y)),
                             "dora": sum(int(h) for y in yaku for h in han_re.findall(y) if "ドラ" in y and "裏" not in y),
                             "ron": frm != w})
    Path(out).write_text(json.dumps(rows))
    print(out, len(rows), "wins")


def callers(out: str) -> None:
    """Every call by the seats being mined: which call of the hand it was, the turn, and whether the caller was tenpai
    right after the discard that followed it (and, if not, how many of its own turns later it got there)."""
    import review_win_speed as ws
    import tenhou_replay as tr

    rows = []
    for g in games():
        seat = g["hero_seat"]
        for log in tr.load_logs(str(ROOT / g["file"])):
            game = tr.replay(log)
            mine = [e for e in game["events"] if e["seat"] == seat]
            calls = 0
            for i, e in enumerate(mine):
                if not e["called"]:
                    continue
                calls += 1
                sh = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
                later = next((x["turn"] - e["turn"] for x in mine[i:] if
                              ws.hand_shanten(x["hand_after"], x["meld_tiles"], x["closed"]) == 0), None)
                others_riichi = any(x["riichi"] and x["index"] < e["index"] for x in game["events"] if x["seat"] != seat)
                rows.append({"room": g.get("mode"), "call": calls, "turn": e["turn"], "shanten": sh,
                             "turns_to_tenpai": later, "riichi_out": others_riichi})
    Path(out).write_text(json.dumps(rows))
    print(out, len(rows), "calls")


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


DATA = ROOT / "data" / "ladder_skill" / "throne_strategy"
FIELD = ROOT / "data" / "ladder_skill" / "throne_field_stats_big.json"
REPORT = ROOT / "analysis" / "throne-strategy-2026-11-23.json"
STATS = {"和了巡数": "win_turn", "立直巡目": "riichi_turn", "立直率": "riichi", "副露率": "call", "默听率": "dama",
         "和牌率": "win", "放铳率": "deal_in", "立直后和牌率": "riichi_win", "流局率": "draw", "流听率": "tenpai_at_draw",
         "自摸率": "tsumo_share"}
CELLS = [("1-2 han, 4+ live", lambda r: r["han"] <= 2 and r["live"] >= 4),
         ("1-2 han, 3 or fewer live", lambda r: r["han"] <= 2 and r["live"] <= 3),
         ("3 han, 4+ live", lambda r: r["han"] == 3 and r["live"] >= 4),
         ("3 han, 3 or fewer live", lambda r: r["han"] == 3 and r["live"] <= 3),
         ("4+ han, 4+ live", lambda r: r["han"] >= 4 and r["live"] >= 4),
         ("4+ han, 3 or fewer live", lambda r: r["han"] >= 4 and r["live"] <= 3)]
EXAMPLE = ("261103-82cf8c27-9a05-4d52-b545-507700652102", "South 3-2", 16)


def rate(xs) -> dict:
    import numpy as np
    a = np.array([float(x) for x in xs])
    if not len(a):
        return {"n": 0, "pct": None, "se": None}
    return {"n": int(len(a)), "pct": round(float(a.mean() * 100), 1), "se": round(float(np.sqrt(a.mean() * (1 - a.mean()) / len(a)) * 100), 1)}


FOLD_EXAMPLE = ("261123-47e5a817-2d01-4e44-bf2a-35cbd556a801", "South 4-0", 15)


def broken_tenpai(uuid: str, rnd: str, turn: int) -> dict:
    """One of the user's turns where the user broke a tenpai: the hand kept, the tiles that kept it, and every
    opponent's real hand at that moment (tenpai or not, its waits and their han)."""
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, site_tile, visible_counter
    from mine_open_tenpai_push import ron_value
    from tenhou_replay import base

    g = next(x for x in json.loads(MANIFEST.read_text()) if x["uuid"] == uuid)
    hero = g["hero_seat"]
    log = next(l for l in tr.load_logs(str(ROOT / g["file"])) if tr.replay(l)["round_name"] == rnd)
    game = tr.replay(log)
    dset = frozenset(ws.dora_from_indicator(t) for t in game["dora_indicators"][:1])
    e = next(x for x in game["events"] if x["seat"] == hero and x["turn"] == turn)
    snap = meld_snapshots(game, e["index"] - 1)
    snap[hero] = e["melds"]
    vis = visible_counter(e["hand_before"], e, game["players"], snap, game["dora_indicators"][:1])
    keep, hand = [], {}
    for t in {base(x): x for x in e["hand_before"]}.values():
        rest = list(e["hand_before"])
        rest.remove(t)
        if ws.hand_shanten(rest, e["meld_tiles"], e["closed"]) == 0:
            keep.append(site_tile(t))
            waits = tr.waits(rest, e["meld_tiles"], e["closed"])
            hand = {"waits": [site_tile(w) for w in waits], "live": sum(max(0, 4 - vis[base(w)]) for w in waits),
                    "han": [ron_value(rest, game["players"][hero]["melds"][:len(e["melds"])], w, hero, game["kyoku"], dset,
                                      riichi=False) for w in waits]}
    opponents = []
    for q in range(4):
        if q == hero:
            continue
        last = [x for x in game["events"] if x["seat"] == q and x["index"] < e["index"]][-1]
        riichi = e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]
        row = {"seat": q, "kind": "riichi" if riichi else "open" if last["melds"] else "closed",
               "tenpai": ws.hand_shanten(last["hand_after"], last["meld_tiles"], last["closed"]) == 0}
        if row["tenpai"]:
            row["waits"] = {site_tile(w): ron_value(last["hand_after"], game["players"][q]["melds"][:len(last["melds"])], w, q,
                                                    game["kyoku"], dset, riichi=riichi)
                            for w in tr.waits(last["hand_after"], last["meld_tiles"], last["closed"])}
        opponents.append(row)
    start = log[1]
    return {"game": uuid, "date": g["date"], "round": rnd, "turn": turn, "scores": list(start), "hero": hero,
            "place": sorted(range(4), key=lambda s: (-start[s], s)).index(hero) + 1, "cut": site_tile(e["tile"]),
            "keep": keep, "hand": hand, "opponents": opponents}


def report(out: Path = REPORT) -> None:
    import numpy as np
    load = lambda name: json.loads((DATA / name).read_text())  # noqa: E731
    you_all = load("spots_you.json")
    you = [r for r in you_all if r["room"] == "jade-south"]
    jade, throne = load("spots_jade_field.json"), load("spots_throne.json")

    # outcome rates of pushes by wait and turn, pooled over every seat, and of folds
    lb = lambda r: "3 or fewer" if r["live"] <= 3 else "4-6" if r["live"] <= 6 else "7+"  # noqa: E731
    tb = lambda r: "to turn 11" if r["turn"] <= 11 else "turn 12 on"  # noqa: E731
    pool = jade + throne + you
    rates = {}
    for key in sorted({(lb(r), tb(r)) for r in pool}):
        p = [r for r in pool if r["pushed"] and (lb(r), tb(r)) == key]
        rates[key] = (float(np.mean([r["won"] for r in p])), float(np.mean([r["dealt"] for r in p])), len(p))
    folds = [r for r in pool if not r["pushed"]]
    fw, fd = float(np.mean([r["won"] for r in folds])), float(np.mean([r["dealt"] for r in folds]))
    for r in you:
        w, d, _ = rates[(lb(r), tb(r))]
        v = r["value"]["celestial"]
        r["ev"] = (w - fw) * v["gain"] - (d - fd) * v["cost"]

    def side(rows, s42=False):
        return {"push": rate(r["pushed"] for r in rows),
                "push_won": rate(r["won"] for r in rows if r["pushed"]),
                "push_dealt": rate(r["dealt"] for r in rows if r["pushed"])}

    cells = []
    for name, sel in CELLS:
        x, t = [r for r in you if sel(r)], [r for r in throne if sel(r)]
        cells.append({"cell": name, "you": rate(r["pushed"] for r in x),
                      "s42": round(float(np.mean([r["s42_push"] for r in x if r["s42_push"] is not None])) * 100, 1),
                      "celestials": rate(r["pushed"] for r in t),
                      "push_right_pct": round(float(np.mean([r["ev"] > 0 for r in x])) * 100, 1),
                      "push_ev": round(float(np.mean([r["ev"] for r in x])), 2)})
    places = {}
    for p in (1, 2, 3, 4):
        x = [r for r in you if r["place"] == p]
        places[str(p)] = {"you": rate(r["pushed"] for r in x),
                          "s42": round(float(np.mean([r["s42_push"] for r in x if r["s42_push"] is not None])) * 100, 1),
                          "celestials": rate(r["pushed"] for r in throne if r["place"] == p),
                          "jade_field": rate(r["pushed"] for r in jade if r["place"] == p)}
    third_big = [r for r in you if r["place"] == 3 and r["han"] >= 3]
    late_thin = [r for r in pool if r["pushed"] and r["live"] <= 3 and r["turn"] >= 12]
    ex = next(r for r in you if r["game"] == EXAMPLE[0] and r["round"] == EXAMPLE[1] and r["turn"] == EXAMPLE[2])

    # the field: play statistics, seat speed and callers
    fs = json.loads(FIELD.read_text())
    field = {"players": {g: sum(1 for x in fs["groups"][g] if x.get("count", 0) >= 40) for g in fs["groups"]}}
    for key, name in STATS.items():
        block = {}
        for g in fs["groups"]:
            ok = [(x[key], x["count"]) for x in fs["groups"][g] if x.get(key) is not None and x.get("count", 0) >= 40]
            v, w = np.array([a for a, _ in ok], float), np.array([c for _, c in ok], float)
            block[g] = {"mean": round(float((v * w).sum() / w.sum()), 4), "se": round(float(v.std(ddof=1) / np.sqrt(len(v))), 4)}
        block["you_jade"] = fs["me"]["12"].get(key)
        block["you_throne"] = fs["me"]["16"].get(key)
        field[name] = block
    field["your_hands"] = {"jade": fs["me"]["12"]["count"], "throne": fs["me"]["16"]["count"]}

    def seat_speed(rows):
        fr = np.array([r["first_riichi_discard"] for r in rows if r["first_riichi_discard"]], float)
        mt = np.array([r["my_tenpai_turn"] for r in rows if r["my_tenpai_turn"]], float)
        rb = np.array([r["riichi_before_my_tenpai"] for r in rows], float)
        se = lambda a: round(float(a.std(ddof=1) / np.sqrt(len(a))), 2)  # noqa: E731
        return {"seat_hands": len(rows), "first_riichi_discard": round(float(fr.mean()), 1), "first_riichi_se": se(fr),
                "tenpai_share": rate(r["my_tenpai_turn"] is not None for r in rows),
                "tenpai_turn": round(float(mt.mean()), 2), "tenpai_turn_se": se(mt),
                "riichi_before_tenpai": rate(rb)}

    speed = {"jade_field": seat_speed(load("speed_jade_field.json")), "throne": seat_speed(load("speed_throne.json"))}
    mine = load("speed_you.json")
    speed["you_throne"] = seat_speed([r for r in mine if r["room"] == "throne-south"])

    def calls(rows):
        out = {}
        for k in (1, 2, 3):
            out[f"call {k}"] = rate(r["shanten"] == 0 for r in rows if r["call"] == k)
        first = [r for r in rows if r["call"] == 1]
        for name, sel in (("first call to turn 5", lambda r: r["turn"] <= 5), ("first call turns 6-9", lambda r: 6 <= r["turn"] <= 9),
                          ("first call turn 10 on", lambda r: r["turn"] >= 10)):
            y = [r for r in first if sel(r)]
            out[name] = rate(r["shanten"] == 0 for r in y)
            out[name]["median_turns_to_tenpai"] = float(np.median([r["turns_to_tenpai"] for r in y if r["turns_to_tenpai"] is not None]))
        return out

    callers_out = {"jade_field": calls(load("callers_jade.json")), "throne": calls(load("callers_throne.json"))}

    def wins(rows):
        o = [r for r in rows if r["open"]]
        paid = np.array([r["paid"] for r in o], float)
        return {"wins": len(rows), "open_share": rate(r["open"] for r in rows),
                "open_paid": round(float(paid.mean())), "open_paid_se": round(float(paid.std(ddof=1) / np.sqrt(len(paid)))),
                "open_mangan": rate(r["han"] >= 5 or r["paid"] >= 7700 for r in o),
                "open_dora": round(float(np.mean([r["dora"] for r in o])), 2),
                "closed_paid": round(float(np.mean([r["paid"] for r in rows if not r["open"]])))}

    open_out = {"jade_field": wins(load("wins_jade.json")), "throne": wins(load("wins_throne.json"))}
    # the user's results: Throne games so far, Jade over the last 60 days and since January (from the game files)
    own = [g for g in json.loads(MANIFEST.read_text()) if g["date"] >= SINCE]
    th_places = [g["placement"] for g in sorted(own, key=lambda g: g["start_time"]) if g.get("mode") == "throne-south"]
    jade_places = [g["placement"] for g in own if g.get("mode") == "jade-south"]
    newest = max(g["start_time"] for g in own)
    recent = [g["placement"] for g in own if g.get("mode") == "jade-south" and g["start_time"] >= newest - 60 * 86400]
    results = {"throne": {"games": len(th_places), "places": th_places, "mean": round(float(np.mean(th_places)), 2),
                          "se": round(float(np.std(th_places, ddof=1) / np.sqrt(len(th_places))), 2)},
               "jade_60_days": {"games": len(recent), "mean": round(float(np.mean(recent)), 2)},
               "jade_since_january": {"games": len(jade_places), "mean": round(float(np.mean(jade_places)), 2)},
               "forecast": [2.40, 2.44], "opponents_on_ch53_scale": {"jade": 2.61, "throne": 2.54}}
    throne_games = len(list((ROOT / "data" / "ladder_skill" / "throne_logs").glob("*.json")))
    rep = {
        "sources": {"throne_games": throne_games, "your_games": len(games()),
                    "spots": {"you": len(you), "jade_field": len(jade), "throne": len(throne), "you_throne": len(you_all) - len(you)}},
        "results": results, "field": field, "speed": speed, "callers": callers_out, "open_wins": open_out,
        "pushes": {"you": side(you), "jade_field": side(jade), "throne": side(throne),
                   "s42": round(float(np.mean([r["s42_push"] for r in you if r["s42_push"] is not None])) * 100, 1),
                   "earlier": round(float(np.mean([r["policy_push"] for r in you if r["policy_push"] is not None])) * 100, 1)},
        "cells": cells, "places": places,
        "third_big": {"spots": len(third_big), "you": rate(r["pushed"] for r in third_big),
                      "s42": round(float(np.mean([r["s42_push"] for r in third_big if r["s42_push"] is not None])) * 100, 1),
                      "push_right_pct": round(float(np.mean([r["ev"] > 0 for r in third_big])) * 100, 1),
                      "push_ev": round(float(np.mean([r["ev"] for r in third_big])), 2)},
        "late_thin_pushes": {"won": rate(r["won"] for r in late_thin), "dealt": rate(r["dealt"] for r in late_thin)},
        "rates": {f"{a} | {b}": {"won": round(w * 100, 1), "dealt": round(d * 100, 1), "pushes": n} for (a, b), (w, d, n) in rates.items()},
        "folds": {"won": round(fw * 100, 1), "dealt": round(fd * 100, 1), "n": len(folds)},
        "fold_example": broken_tenpai(*FOLD_EXAMPLE),
        "draw_tenpai_opponents": {g: round(3 * field["tenpai_at_draw"][g]["mean"], 2) for g in ("jade_saint3", "celestial")},
        "example": {k: ex[k] for k in ("game", "round", "turn", "place", "han", "live", "scores", "hero", "riichi_seats", "s42_push", "policy_push")}
        | {"ev": round(ex["ev"], 2), "gain": ex["value"]["celestial"]["gain"], "cost": ex["value"]["celestial"]["cost"]},
    }
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    if "--seats" in args:
        i = args.index("--seats")
        SEATS = seat_rows(args[i + 1])
        del args[i:i + 2]
    if cmd == "report":
        report()
        sys.exit()
    if cmd == "wins":
        open_wins(args[0])
    elif cmd == "callers":
        callers(args[0])
    elif cmd == "speed":
        speed(args[0])
    elif cmd == "spots":
        spots(args[0])
    elif cmd == "values":
        values(args[0], args[1])
    elif cmd == "mortal":
        i, j = args.index("--policy"), args.index("--s42")
        mortal(args[0], args[i + 1], args[j + 1], args[-1])
