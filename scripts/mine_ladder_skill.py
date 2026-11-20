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

With ``--qmodel CHECKPOINT`` a Mortal v4 checkpoint that carries a value head (``current_dqn``) scores the games
instead, and the row holds what the taken action gave up in that model's Q-values (final-placement points, 2 a place):

    "n", "qloss", "qloss2", "top", "big01", "big03", "big1",   # sum of max Q - Q(taken), its square, counts over a size
    "lp005", "lp01", "lp02", "lp05",                            # sum of ln softmax(Q / T)(taken), T = 0.05 ... 0.5
    and the same with a ``_d`` suffix for discards only ("nd" discards)

The engines are built in ``mortal_engines.py`` (checkpoints are read with ``weights_only=True``).

    .venv/bin/python scripts/mine_ladder_skill.py GROUP OUT.jsonl FILE...|@LIST [--procs P] [--qmodel CHECKPOINT]
"""

from __future__ import annotations

import json
import math
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ENGINE = None
QMODEL = None  # path of a checkpoint with a value head; None scores with the policy model
Q_TEMPS = (("lp005", 0.05), ("lp01", 0.1), ("lp02", 0.2), ("lp05", 0.5))

TILES = [f"{n}{s}" for s in "mps" for n in range(1, 10)] + list("ESWNPFC")
TILE_IDX = {t: i for i, t in enumerate(TILES)}
RED_IDX = {"5mr": 34, "5pr": 35, "5sr": 36}


def tile_action(pai: str) -> int:
    return RED_IDX.get(pai, TILE_IDX.get(pai, -1))


def init(qmodel=None):
    global ENGINE, QMODEL
    import mortal_engines
    QMODEL = qmodel  # workers are spawned, so the choice of model has to be handed over
    ENGINE = mortal_engines.policy_engine() if QMODEL is None else mortal_engines.q_engine(QMODEL)


def decision_stats(p: dict[int, float], a: int) -> dict[str, float]:
    """Per-decision numbers to add up: policy probabilities, or Q-values when a value model is scoring."""
    best = max(p.values())
    if QMODEL is None:
        pt = p[a]
        return {"logp": math.log(max(pt, 1e-4)), "p": pt, "top": float(pt == best), "low": float(pt < 0.1)}
    loss = best - p[a]
    out = {"qloss": loss, "qloss2": loss * loss, "top": float(loss == 0),
           "big01": float(loss > 0.1), "big03": float(loss > 0.3), "big1": float(loss > 1)}
    for key, t in Q_TEMPS:
        out[key] = -loss / t - math.log(sum(math.exp((q - best) / t) for q in p.values()))
    return out


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
        keys = ("logp", "p", "top", "low") if QMODEL is None else (
            "qloss", "qloss2", "top", "big01", "big03", "big1", *(k for k, _ in Q_TEMPS))
        acc = {"n": 0.0, **{k: 0.0 for k in keys}, "nd": 0.0, **{k + "_d": 0.0 for k in keys}}
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
                st = decision_stats(p, a)
                acc["n"] += 1
                for k, v in st.items():
                    acc[k] += v
                if discard:
                    acc["nd"] += 1
                    for k, v in st.items():
                        acc[k + "_d"] += v
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
    if "--qmodel" in args:
        i = args.index("--qmodel")
        QMODEL = os.path.expanduser(args[i + 1])
        del args[i:i + 2]
    group, outp, files = args[0], args[1], args[2:]
    if len(files) == 1 and files[0].startswith("@"):  # @LIST: one path per line
        files = [l.strip() for l in open(files[0][1:]) if l.strip()]
    done = set()
    if os.path.exists(outp):
        done = {json.loads(l)["file"] for l in open(outp) if l.strip()}
    jobs = [(f, group) for f in files if f not in done]
    n = 0
    with Pool(procs, initializer=init, initargs=(QMODEL,)) as pool, open(outp, "a") as f:
        for rows in pool.imap_unordered(work, jobs, chunksize=1):
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            n += 1
            if n % 100 == 0:
                print(n, "games", flush=True)
    print(outp, n, "games")
