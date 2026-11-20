#!/usr/bin/env python3
"""Score every seat of a set of games with the local Mortal policy, on one scale for Tenhou and Mahjong Soul.

Each game (a tenhou.net/6 JSON: a Tenhou log from mjlog2json.cgi or a tensoul Mahjong Soul game) is converted to
mjai with ``tenhou6_to_mjai.convert`` and replayed once per seat through libriichi's Bot. At every decision with two
or more legal actions the probability Mortal gave to the action the player really took is recorded. One output row
per seat and game:

    {"file", "group", "seat", "name", "dan", "rate", "score", "place",
     "n", "logp", "p", "top", "low",          # all decisions
     "nd", "logp_d", "p_d", "top_d", "low_d"}  # discard decisions only (own turn)

``logp`` is the sum of ln p(taken) (p floored at 1e-4), ``p`` the sum of p(taken), ``top`` how many times the taken
action was Mortal's first choice, ``low`` how many times Mortal gave it under 10%. Divide by ``n`` (or ``nd``).

    .venv/bin/python scripts/mine_ladder_skill.py GROUP OUT.jsonl FILE...|@LIST [--procs P]
"""

from __future__ import annotations

import importlib.util
import json
import math
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

MODEL = os.path.expanduser("~/Downloads/mortal_model_policy/model.py")
ENGINE = None

TILES = [f"{n}{s}" for s in "mps" for n in range(1, 10)] + list("ESWNPFC")
TILE_IDX = {t: i for i, t in enumerate(TILES)}
RED_IDX = {"5mr": 34, "5pr": 35, "5sr": 36}


def tile_action(pai: str) -> int:
    return RED_IDX.get(pai, TILE_IDX.get(pai, -1))


def init():
    global ENGINE
    import torch
    import libriichi
    torch.set_num_threads(1)
    for name in ["mjai", "consts", "dataset", "state", "arena", "stat"]:
        if hasattr(libriichi, name):
            sys.modules[f"libriichi.{name}"] = getattr(libriichi, name)
    spec = importlib.util.spec_from_file_location("mortal_policy_model", MODEL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ENGINE = mod.get_engine()


def probs_of(raw: str) -> dict[int, float]:
    meta = (json.loads(raw) or {}).get("meta") or {}
    q = meta.get("q_values") or []
    mask = int(meta.get("mask_bits") or 0)
    legal = [i for i in range(46) if (mask >> i) & 1]
    return dict(zip(legal, (float(p) for p in q)))


def own_action(ev: dict) -> int | None:
    t = ev["type"]
    if t == "dahai":
        return tile_action(ev["pai"])
    return {"reach": 37, "hora": 43, "ankan": 42, "kakan": 42, "ryukyoku": 44}.get(t)


def call_action(ev: dict, nxt: dict | None, seat: int) -> int:
    """What ``seat`` did with another player's tile (or kan): call, win or pass."""
    if nxt is None or nxt.get("actor") != seat:
        return 45
    t = nxt["type"]
    if t == "hora":
        return 43
    if t == "pon":
        return 41
    if t == "daiminkan":
        return 42
    if t == "chi":
        n = int(ev["pai"][0])
        others = sorted(int(c[0]) for c in nxt["consumed"])
        if others[0] > n:
            return 38
        if others[1] < n:
            return 40
        return 39
    return 45


def places(final: list[int]) -> list[int]:
    order = sorted(range(4), key=lambda i: (-final[i], i))
    return [order.index(i) + 1 for i in range(4)]


def work(job):
    from libriichi.mjai import Bot
    import tenhou6_to_mjai

    path, group = job
    try:
        game = json.load(open(path))
        events = tenhou6_to_mjai.convert(game)
    except Exception as e:  # noqa: BLE001
        return [{"file": path, "error": f"convert: {e}"}]
    sc = game.get("sc") or []
    final = [int(sc[2 * i]) for i in range(4)] if len(sc) >= 8 else None
    if final is None:
        return [{"file": path, "error": "no final scores"}]
    pl = places(final)
    rows = []
    for seat in range(4):
        bot = Bot(ENGINE, seat)
        acc = {k: 0.0 for k in ("n", "logp", "p", "top", "low", "nd", "logp_d", "p_d", "top_d", "low_d")}
        try:
            for idx, ev in enumerate(events):
                raw = bot.react(json.dumps(ev, ensure_ascii=False), can_act=True)
                if not raw:
                    continue
                p = probs_of(raw)
                if len(p) < 2:
                    continue
                actor, typ = ev.get("actor"), ev["type"]
                discard = False
                if actor == seat and typ in ("tsumo", "chi", "pon", "reach"):
                    nxt = next((e for e in events[idx + 1:] if e.get("actor") == seat), None)
                    if nxt is None:
                        continue
                    a = own_action(nxt)
                    discard = nxt["type"] == "dahai"
                elif actor != seat and typ in ("dahai", "kakan", "ankan"):
                    a = call_action(ev, events[idx + 1] if idx + 1 < len(events) else None, seat)
                    # a ron by someone else can sit before ours in the event list
                    if a == 45:
                        for e in events[idx + 1:idx + 4]:
                            if e["type"] != "hora":
                                break
                            if e.get("actor") == seat:
                                a = 43
                else:
                    continue
                if a is None or a not in p:
                    continue
                pt = p[a]
                lp = math.log(max(pt, 1e-4))
                top = float(a == max(p, key=p.get))
                low = float(pt < 0.1)
                acc["n"] += 1; acc["logp"] += lp; acc["p"] += pt; acc["top"] += top; acc["low"] += low
                if discard:
                    acc["nd"] += 1; acc["logp_d"] += lp; acc["p_d"] += pt; acc["top_d"] += top; acc["low_d"] += low
        except Exception as e:  # noqa: BLE001
            rows.append({"file": path, "seat": seat, "error": f"replay: {e}"})
            continue
        rows.append({"file": path, "group": group, "seat": seat,
                     "name": (game.get("name") or [None] * 4)[seat],
                     "dan": (game.get("dan") or [None] * 4)[seat],
                     "rate": (game.get("rate") or [None] * 4)[seat],
                     "score": final[seat], "place": pl[seat], **acc})
    return rows


if __name__ == "__main__":
    args = sys.argv[1:]
    procs = 4
    if "--procs" in args:
        i = args.index("--procs")
        procs = int(args[i + 1])
        del args[i:i + 2]
    group, outp, files = args[0], args[1], args[2:]
    if len(files) == 1 and files[0].startswith("@"):  # @LIST: one path per line
        files = [l.strip() for l in open(files[0][1:]) if l.strip()]
    done = set()
    if os.path.exists(outp):
        done = {json.loads(l)["file"] for l in open(outp) if l.strip()}
    jobs = [(f, group) for f in files if f not in done]
    n = 0
    with Pool(procs, initializer=init) as pool, open(outp, "a") as f:
        for rows in pool.imap_unordered(work, jobs, chunksize=1):
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
            if n % 100 == 0:
                print(n, "games", flush=True)
    print(outp, n, "games")
