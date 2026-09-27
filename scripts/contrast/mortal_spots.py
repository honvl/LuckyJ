"""Ask the local Mortal policy about chosen tenpai spots: riichi or not, and which tile it would declare with.

usage: mortal_spots.py SPOTS.json OUT.jsonl [--procs P]

SPOTS.json is a list of {"g", "file", "li", "s", "t"}: the tenhou.net/6 game file, the hand index, the
seat and that seat's discard number in the hand (as tenhou_replay counts it). For each spot the seat's
Mortal bot replays the game's mjai log without acting up to that draw or call, answers it (the discard
probabilities, with riichi as action 37 when legal), and then, when riichi is legal, answers an injected
riichi declaration, which gives the tile it would declare with. Probabilities are keyed by base tile
code (red fives folded into fives) plus "reach".
"""
import gzip
import json
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mortal_run import MJAI_DIR, init, probs_of  # noqa: E402

TILES = ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
         "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "E", "S", "W", "N", "P", "F", "C", "5mr", "5pr", "5sr"]


def base_code(a):
    t = TILES[a].rstrip("r")
    if t[0].isdigit():
        return {"m": 10, "p": 20, "s": 30}[t[1]] + int(t[0])
    return 41 + "ESWNPFC".index(t)


def by_tile(p):
    out = {}
    for a, v in p.items():
        if a <= 36:
            out[base_code(a)] = round(out.get(base_code(a), 0) + v, 5)
    if 37 in p:
        out["reach"] = p[37]
    return out


def ask(spot):
    import mortal_run
    from libriichi.mjai import Bot

    log_id = json.load(open(spot["file"]))["title"][1]
    path = os.path.join(MJAI_DIR, log_id + ".json.gz")
    if not os.path.exists(path):
        return None
    events = [json.loads(line) for line in gzip.open(path, "rt") if line.strip()]
    seat = spot["s"]
    bot = Bot(mortal_run.ENGINE, seat)
    li = -1
    ndis = 0
    for idx, ev in enumerate(events):
        if ev["type"] == "start_kyoku":
            li += 1
            ndis = 0
        target = False
        if ev.get("actor") == seat and ev["type"] in ("tsumo", "chi", "pon"):
            nxt = next((e for e in events[idx + 1:] if e.get("actor") == seat), None)
            if not (ev["type"] == "tsumo" and nxt is not None and nxt["type"] in ("ankan", "kakan", "hora")):
                ndis += 1
                target = li == spot["li"] and ndis == spot["t"]
        raw = bot.react(json.dumps(ev, ensure_ascii=False), can_act=target)
        if not target:
            continue
        act = probs_of(json.loads(raw)) if raw else {}
        row = {k: spot[k] for k in ("g", "li", "s", "t")}
        row["act"] = by_tile(act)
        row["real_pai"] = next((e.get("pai") for e in events[idx + 1:] if e.get("actor") == seat and e["type"] == "dahai"), None)
        if 37 in act:
            raw2 = bot.react(json.dumps({"type": "reach", "actor": seat}), can_act=True)
            row["reach_tile"] = by_tile(probs_of(json.loads(raw2))) if raw2 else None
        return row
    return None


if __name__ == "__main__":
    spots_path, outp = sys.argv[1], sys.argv[2]
    spots = json.load(open(spots_path))
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 8
    n = 0
    with Pool(procs, initializer=init) as pool, open(outp, "w") as f:
        for row in pool.imap_unordered(ask, spots, chunksize=4):
            if row:
                f.write(json.dumps(row) + "\n")
                n += 1
    print(outp, len(spots), "spots", n, "answered")
