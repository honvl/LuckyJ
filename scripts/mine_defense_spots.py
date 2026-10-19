#!/usr/bin/env python3
"""The figures behind guide chapter 46: why Mortal threw the 1p and the 2s in chapter 45's first two cuts.

- the 1p hand (South 3, 1 honba of the 16 October game): every tile the user could throw against the lone riichi, with the
  guide's own safety label, the copies the user could see, and the ways each tile could be the riichi player's winning
  tile (two-sided, closed, edge, pair and single waits, counted from the copies nobody has shown); and Mortal's answer
  with and without the riichi;
- the 7p hand (South 2 of the 7 October game): the user's three 7p and the fourth in the dealer's river;
- the 2s hand (South 1, 1 honba of the 3 October game, two riichis): the same table, and Mortal's answer with each riichi
  alone, with neither, and with one early discard of the riichi players changed;
- every discard into a lone riichi where the discarder was not tenpai afterwards, at the user's tables and LuckyJ's:
  how often a tile with all four copies visible was in the hand and how often it was thrown.

usage: mine_defense_spots.py OUT.json
"""

from __future__ import annotations

import copy
import glob
import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
REPLAYS = ROOT / "site" / "replays"
SPOTS = {"one_pin": ("261017-c062d7a5", "South 3-1"), "seven_pin": ("261008-6c28a9cb", "South 2-0"), "two_sou": ("261004-3d4685b3", "South 1-1")}


def ways(b: int, vis, ref: set[int]) -> dict[str, int]:
    """The combinations of tiles nobody has shown that could make ``b`` a riichi player's winning tile.

    ``vis`` counts the copies of each tile the discarder can see, the hand and the tile in question included; ``ref`` is
    the riichi player's genbutsu (their river and the tiles passed since the declaration). A tile in ``ref`` would be
    furiten for them. A two-sided wait is dropped when its other end is in ``ref``.
    """
    if b in ref:
        return {}
    u = lambda x: max(0, 4 - vis[x])  # noqa: E731
    if b >= 41:
        return {"pair": u(b) * (u(b) - 1) // 2, "single": u(b)}
    n = b % 10
    two_sided = 0
    if n <= 6 and b + 3 not in ref:
        two_sided += u(b + 1) * u(b + 2)
    if n >= 4 and b - 3 not in ref:
        two_sided += u(b - 2) * u(b - 1)
    return {"two-sided": two_sided, "closed": u(b - 1) * u(b + 1) if 2 <= n <= 8 else 0,
            "edge": (u(b - 2) * u(b - 1) if n == 3 else 0) + (u(b + 1) * u(b + 2) if n == 7 else 0),
            "pair": u(b) * (u(b) - 1) // 2, "single": u(b)}


def tile_names(codes) -> list[str]:
    from tenhou_replay import base, name

    return [name(c) for c in sorted(codes, key=lambda x: (base(x) // 10, base(x)))]


def spot_table(prefix: str, round_name: str) -> dict:
    """Every tile the user could throw at the decision that dealt in, against each riichi on the table."""
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, safety, visible_counter
    from tenhou_replay import base, name

    path = glob.glob(str(ROOT / "data/self_games/majsoul" / f"{prefix}-*.json"))[0]
    game_meta = next(g for g in json.loads(MANIFEST.read_text()) if g["file"].endswith(Path(path).name))
    hero = game_meta["hero_seat"]
    for log in tr.load_logs(path):
        game = tr.replay(log)
        if game["round_name"] != round_name:
            continue
        events = game["events"]
        e = [x for x in events if x["seat"] == hero and x.get("tile") is not None][-1]
        waits = {ev["seat"]: {base(w) for w in tr.waits(ev["hand_after"], ev["meld_tiles"], ev["closed"])} for ev in events if ev["riichi"]}
        reached = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
        snap = meld_snapshots(game, e["index"] - 1)
        snap[hero] = e["melds"]
        vis = visible_counter(e["hand_before"], e, game["players"], snap, game["dora_indicators"][:1])
        riichi = {}
        for q in reached:
            r = e["riichi_seats"][q]
            passed = {base(x["tile"]) for x in events[r + 1: e["index"]] if x.get("tile") is not None}
            riichi[q] = {"river": [name(x) for x in e["rivers"][q]], "wait": sorted(name(w) for w in waits.get(q, ())), "passed": sorted(name(x) for x in passed),
                         "ref": {base(x) for x in e["rivers"][q]} | passed}
        rows = []
        for b in sorted({base(x) for x in e["hand_before"]}):
            per, labels, total, hit = [], [], 0, False
            for q in reached:
                seen = vis.copy()
                seen[b] -= 1
                labels.append(safety(b, q, e, game, seen))
                w = ways(b, vis, riichi[q]["ref"])
                per.append(w)
                total += sum(w.values())
                hit = hit or b in waits.get(q, set())
            rows.append({"tile": name(b), "copies_seen": vis[b], "labels": labels, "ways": per, "total_ways": total, "furiten_against": [b in riichi[q]["ref"] for q in reached],
                         "winning_tile": hit, "thrown": b == base(e["tile"])})
        return {"round": round_name, "turn": e["turn"], "hero_seat": hero, "riichi_seats": reached, "thrown": name(e["tile"]),
                "hand": tile_names(e["hand_before"]), "riichi": {str(q): {k: v for k, v in r.items() if k != "ref"} for q, r in riichi.items()},
                "dora_indicator": [name(x) for x in game["dora_indicators"][:1]], "candidates": sorted(rows, key=lambda r: (r["total_ways"], r["tile"]))}
    raise ValueError((prefix, round_name))


# --- Mortal -------------------------------------------------------------------------------------------------------

_ENGINE = None


def mortal_at(game: dict, hand_idx: int, target: int, drop=(), edits=()) -> list[list]:
    """Mortal's probabilities for the hero at the decision after event ``target`` of a replay hand, with the given seats'
    riichi removed and the given discards (event index, tile) changed."""
    global _ENGINE
    import build_replays as br

    if _ENGINE is None:
        _ENGINE = br.load_engine()  # puts libriichi on the path
    from libriichi.mjai import Bot

    g = copy.deepcopy(game)
    h = g["hands"][hand_idx]
    for idx, tile in edits:
        assert h["ev"][idx][0] == "d", h["ev"][idx]
        h["ev"][idx][2] = tile
    kept = [(k, e) for k, e in enumerate(h["ev"]) if not (e[0] in ("r", "ra") and e[1] in drop)]
    h["ev"] = [e for _, e in kept]
    idx = [k for k, _ in kept].index(target)
    bot = Bot(_ENGINE, g["hero"])
    for hh, i, ev in br.mjai_events(g):
        if hh is not None and hh != hand_idx:
            continue
        if hh == hand_idx and i is None and ev["type"] in ("hora", "ryukyoku", "end_kyoku"):
            break
        raw = bot.react(json.dumps(ev, ensure_ascii=False), can_act=True)
        if hh == hand_idx and i == idx:
            return br.decode(json.loads(raw))
    raise ValueError("decision not reached")


def declared(h: dict, seat: int) -> int:
    """The index of the discard that carries a seat's riichi declaration."""
    return next(i for i, e in enumerate(h["ev"]) if e[0] == "r" and e[1] == seat) + 1


def two_sou_probes() -> dict:
    prefix, round_name = SPOTS["two_sou"]
    game = json.loads(Path(glob.glob(str(REPLAYS / f"{prefix}-*.json"))[0]).read_text())
    hero = game["hero"]
    hi = next(i for i, h in enumerate(game["hands"]) if h["round"] == round_name)
    h = game["hands"][hi]
    last = max(i for i, x in enumerate(h["ev"]) if x[0] == "d" and x[1] == hero)
    d3, d0 = declared(h, 3), declared(h, 0)
    third_sou = next(i for i, e in enumerate(h["ev"]) if e[0] == "d" and e[1] == 3 and e[2] == "3s")
    variants = [("both riichis, as played", (), []), ("only the dealer (seat 0) in riichi", (3,), []), ("only seat 3 in riichi", (0,), []), ("no riichi", (0, 3), []),
                ("seat 3 never threw the 3s on turn 3", (), [(third_sou, "N")]), ("the dealer declared on a 5s, not the 1s", (), [(d0, "5s")]),
                ("the dealer declared on a 9m, not the 1s", (), [(d0, "9m")]), ("seat 3 declared on a 9m, not the 3m", (), [(d3, "9m")])]
    out = {}
    for label, drop, edits in variants:
        res = mortal_at(game, hi, last - 1, drop=drop, edits=edits)
        out[label] = [[a, round(p, 3)] for a, p in res[:4]]
    return out


def one_pin_probes() -> dict:
    prefix, round_name = SPOTS["one_pin"]
    game = json.loads(Path(glob.glob(str(REPLAYS / f"{prefix}-*.json"))[0]).read_text())
    hero = game["hero"]
    hi = next(i for i, h in enumerate(game["hands"]) if h["round"] == round_name)
    h = game["hands"][hi]
    last = max(i for i, x in enumerate(h["ev"]) if x[0] == "d" and x[1] == hero)
    out = {}
    for label, drop in (("the riichi, as played", ()), ("no riichi", (2,))):
        out[label] = [[a, round(p, 3)] for a, p in mortal_at(game, hi, last - 1, drop=drop)[:4]]
    return out


def seven_pin_spot() -> dict:
    """South 2 of the 7 October game: no riichi, the dealer has called. Copies visible of the tiles in the hand, and Mortal's answer."""
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, visible_counter
    from tenhou_replay import base, name

    prefix, round_name = SPOTS["seven_pin"]
    path = glob.glob(str(ROOT / "data/self_games/majsoul" / f"{prefix}-*.json"))[0]
    meta = next(g for g in json.loads(MANIFEST.read_text()) if g["file"].endswith(Path(path).name))
    hero = meta["hero_seat"]
    for log in tr.load_logs(path):
        game = tr.replay(log)
        if game["round_name"] != round_name:
            continue
        e = [x for x in game["events"] if x["seat"] == hero and x.get("tile") is not None][-1]
        snap = meld_snapshots(game, e["index"] - 1)
        snap[hero] = e["melds"]
        vis = visible_counter(e["hand_before"], e, game["players"], snap, game["dora_indicators"][:1])
        tiles = sorted({base(x) for x in e["hand_before"]})
        rep = json.loads(Path(glob.glob(str(REPLAYS / f"{prefix}-*.json"))[0]).read_text())
        h = next(x for x in rep["hands"] if x["round"] == round_name)
        last = max(i for i, x in enumerate(h["ev"]) if x[0] == "d" and x[1] == rep["hero"])
        ai = next(a for a in h["ai"] if a["i"] == last - 1)
        return {"round": round_name, "turn": e["turn"], "thrown": name(e["tile"]), "hand": tile_names(e["hand_before"]),
                "copies_seen": {name(b): vis[b] for b in tiles}, "mortal": [[a, p] for a, p in ai["p"][:4]]}
    raise ValueError((prefix, round_name))


# --- the scan -----------------------------------------------------------------------------------------------------

def scan_game(job) -> list[dict]:
    g, table = job
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, visible_counter
    from tenhou_replay import base

    out, hero = [], g["hero_seat"]
    for log in tr.load_logs(str(ROOT / g["file"])):
        game = tr.replay(log)
        events = game["events"]
        indicators = game["dora_indicators"][:1]
        waits = {e["seat"]: {base(w) for w in tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])} for e in events if e["riichi"]}
        for e in events:
            s = e["seat"]
            reached = [q for q in range(4) if q != s and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            if len(reached) != 1 or e["riichi_seats"][s] is not None or e.get("tile") is None or not waits.get(reached[0]):
                continue
            if ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) == 0:
                continue  # a push with a tenpai is not a fold
            q = reached[0]
            r = e["riichi_seats"][q]
            snap = meld_snapshots(game, e["index"] - 1)
            snap[s] = e["melds"]
            vis = visible_counter(e["hand_before"], e, game["players"], snap, indicators)
            passed = {base(x["tile"]) for x in events[r + 1: e["index"]] if x.get("tile") is not None}
            ref = {base(x) for x in e["rivers"][q]} | passed
            tiles = {base(x) for x in e["hand_before"]}
            dead = [b for b in tiles if b not in ref and vis[b] >= 4]
            thrown = base(e["tile"])
            who = ("luckyj" if s == hero else "tokujou_human") if table == "tenhou" else ("you" if s == hero else "jade_human")
            out.append({"who": who, "genbutsu": any(b in ref for b in tiles), "dead": bool(dead), "thrown_genbutsu": thrown in ref, "thrown_dead": thrown in dead,
                        "hit": thrown in waits[q]})
    return out


def dead_tile_scan() -> dict:
    you = json.loads(MANIFEST.read_text())
    lj, files = [], set()
    for g in json.loads(LJ_MANIFEST.read_text()):
        if g["mode"] == "tenhou-tokujou" and g["file"] not in files:
            files.add(g["file"])
            lj.append(g)
    with Pool(12) as pool:
        res = pool.map(scan_game, [(g, "jade") for g in you] + [(g, "tenhou") for g in lj], chunksize=4)
    rows = [r for chunk in res for r in chunk]
    out = {"games": {"you": len(you), "luckyj": len(lj)}}
    for who in ("you", "jade_human", "luckyj", "tokujou_human"):
        rs = [r for r in rows if r["who"] == who]
        only = [r for r in rs if r["dead"] and not r["genbutsu"]]
        both = [r for r in rs if r["dead"] and r["genbutsu"]]
        out[who] = {"decisions": len(rs), "dead_no_genbutsu": len(only), "threw_dead": sum(r["thrown_dead"] for r in only),
                    "dealt_in_when_dead_no_genbutsu": sum(r["hit"] for r in only), "dead_and_genbutsu": len(both),
                    "threw_genbutsu_when_both": sum(r["thrown_genbutsu"] for r in both), "threw_dead_when_both": sum(r["thrown_dead"] for r in both)}
    return out


def main() -> None:
    out_path = sys.argv[1]
    out = {"one_pin": {**spot_table(*SPOTS["one_pin"]), "mortal": one_pin_probes()},
           "seven_pin": seven_pin_spot(),
           "two_sou": {**spot_table(*SPOTS["two_sou"]), "mortal": two_sou_probes()},
           "dead_tiles": dead_tile_scan()}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
