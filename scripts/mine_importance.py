#!/usr/bin/env python3
"""Score every decision of every seat with Mortal-S42 and keep the sums by situation, for an importance weighting.

``mine_ladder_skill.py`` adds a game's decisions up as if each counted the same. Here the same replay keeps them
apart by the situation the decision was made in, so that any weighting by situation can be tried afterwards without
replaying a game (``fit_importance.py``).

A situation is five things, read at the moment of the decision:

    turn     the seat's own discard number, in pairs: 0 = discards 1-2, 1 = 3-4 ... 8 = 17 and later
    shanten  the hand's shanten, 0 (tenpai) to 3 (three or more away), from libriichi's own count
    threat   2 if another player has declared riichi, else 1 if another player has two or more open melds, else 0
    kind     0 a decision on the seat's own turn (discard, riichi, kan, tsumo), 1 an answer to someone else's tile
    stage    0 East, 1 South 1-3, 2 South 4 and anything after

One output row per seat and game:

    {"file", "group", "seat", "name", "dan", "rate", "score", "place", "n",
     "b": {"turn.shanten.threat.kind.stage": [decisions, Q loss, ln p at T 0.6, first choices], ...}}

Q loss is max Q minus Q(taken) in Mortal's final-placement points (2 a place); ln p is the log of the softmax of Q
at the project's temperature (``mortal_engines.TEMPERATURE``).

    .venv/bin/python scripts/mine_importance.py GROUP OUT.jsonl FILE...|@LIST [--procs P]
"""

from __future__ import annotations

import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mine_ladder_skill as base  # noqa: E402  probs_of, own_action, call_action, places

ENGINE = None
TEMP = 0.6
TURN_BINS, SHANTEN_MAX = 9, 3


def init():
    global ENGINE, TEMP
    import mortal_engines
    ENGINE = mortal_engines.q_engine(mortal_engines.S42_WEIGHTS)
    TEMP = mortal_engines.TEMPERATURE


def stage_of(start: dict) -> int:
    if start["bakaze"] == "E":
        return 0
    if start["bakaze"] == "S" and start["kyoku"] < 4:
        return 1
    return 2


def bucket(turn: int, shanten: int, threat: int, kind: int, stage: int) -> str:
    return f"{min((max(turn, 1) - 1) // 2, TURN_BINS - 1)}.{min(max(shanten, 0), SHANTEN_MAX)}.{threat}.{kind}.{stage}"


def work(job):
    from libriichi.mjai import Bot
    from libriichi.state import PlayerState
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
    pl = base.places(final)
    rows = []
    for seat in range(4):
        bot, state = Bot(ENGINE, seat), PlayerState(seat)
        acc: dict[str, list[float]] = {}
        n = 0
        stage = discards = 0
        riichi, melds = set(), [0, 0, 0, 0]
        try:
            for idx, ev in enumerate(events):
                line = json.dumps(ev, ensure_ascii=False)
                raw = bot.react(line, can_act=True)
                state.update(line)
                typ, actor = ev["type"], ev.get("actor")
                if typ == "start_kyoku":
                    stage, discards, riichi, melds = stage_of(ev), 0, set(), [0, 0, 0, 0]
                elif typ == "reach":
                    riichi.add(actor)
                elif typ in ("chi", "pon", "daiminkan"):
                    melds[actor] += 1
                if not raw:
                    if typ == "dahai" and actor == seat:
                        discards += 1
                    continue
                p = base.probs_of(raw)
                took = None
                if len(p) >= 2:
                    if actor == seat and typ in ("tsumo", "chi", "pon", "reach"):
                        nxt = next((e for e in events[idx + 1:] if e.get("actor") == seat), None)
                        if nxt is not None:
                            took, kind = base.own_action(nxt), 0
                    elif actor != seat and typ in ("dahai", "kakan", "ankan"):
                        took, kind = base.call_action(ev, events[idx + 1] if idx + 1 < len(events) else None, seat), 1
                        if took == 45:  # a ron by someone else can sit before ours in the event list
                            for e in events[idx + 1:idx + 4]:
                                if e["type"] != "hora":
                                    break
                                if e.get("actor") == seat:
                                    took = 43
                if took is not None and took in p:
                    best = max(p.values())
                    loss = best - p[took]
                    lp = -loss / TEMP - math.log(sum(math.exp((q - best) / TEMP) for q in p.values()))
                    threat = 2 if riichi - {seat} else (1 if any(m >= 2 for s, m in enumerate(melds) if s != seat) else 0)
                    cell = acc.setdefault(bucket(discards + 1, state.shanten, threat, kind, stage), [0, 0.0, 0.0, 0])
                    cell[0] += 1
                    cell[1] += loss
                    cell[2] += lp
                    cell[3] += int(loss == 0)
                    n += 1
                if typ == "dahai" and actor == seat:
                    discards += 1
        except Exception as e:  # noqa: BLE001
            rows.append({"file": path, "seat": seat, "error": f"replay: {e}"})
            continue
        rows.append({"file": path, "group": group, "seat": seat,
                     "name": (game.get("name") or [None] * 4)[seat],
                     "dan": (game.get("dan") or [None] * 4)[seat],
                     "rate": (game.get("rate") or [None] * 4)[seat],
                     "score": final[seat], "place": pl[seat], "n": n,
                     "b": {k: [v[0], round(v[1], 5), round(v[2], 5), v[3]] for k, v in acc.items()}})
    return rows


if __name__ == "__main__":
    import os
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
