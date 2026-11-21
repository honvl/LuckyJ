"""Replay games through the earlier policy model and Mortal-S42 side by side; one row per decision.

    .venv/bin/python scripts/mortal_two_models.py FILES.txt OUT.jsonl PROCS

FILES.txt lists tenhou.net/6 JSON games, one path per line. scripts/mortal_calibrate.py reads OUT.jsonl.
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mine_ladder_skill as m

ENG = {}

def init():
    import mortal_engines
    ENG["p"] = mortal_engines.policy_engine()
    ENG["q"] = mortal_engines.q_engine(mortal_engines.S42_WEIGHTS)

def work(path):
    from libriichi.mjai import Bot
    import tenhou6_to_mjai
    try:
        game = json.load(open(path)); events = tenhou6_to_mjai.convert(game)
    except Exception as e:
        return []
    out = []
    for seat in range(4):
        bp, bq = Bot(ENG["p"], seat), Bot(ENG["q"], seat)
        try:
            for idx, ev in enumerate(events):
                s = json.dumps(ev, ensure_ascii=False)
                rp, rq = bp.react(s, can_act=True), bq.react(s, can_act=True)
                if not rp or not rq:
                    continue
                p, q = m.probs_of(rp), m.probs_of(rq)
                if len(p) < 2 or set(p) != set(q):
                    continue
                actor, typ = ev.get("actor"), ev["type"]
                discard = False
                if actor == seat and typ in ("tsumo", "chi", "pon", "reach"):
                    nxt = next((e for e in events[idx + 1:] if e.get("actor") == seat), None)
                    if nxt is None: continue
                    a = m.own_action(nxt); discard = nxt["type"] == "dahai"
                elif actor != seat and typ in ("dahai", "kakan", "ankan"):
                    a = m.call_action(ev, events[idx + 1] if idx + 1 < len(events) else None, seat)
                    if a == 45:
                        for e in events[idx + 1:idx + 4]:
                            if e["type"] != "hora": break
                            if e.get("actor") == seat: a = 43
                else:
                    continue
                if a is None or a not in p: continue
                ks = sorted(p)
                out.append({"k": ks, "p": [round(p[k], 5) for k in ks], "q": [round(q[k], 4) for k in ks],
                            "a": a, "d": discard, "name": (game.get("name") or [None]*4)[seat]})
        except Exception as e:
            continue
    return out

if __name__ == "__main__":
    files = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    n = 0
    with Pool(int(sys.argv[3]), initializer=init) as pool, open(sys.argv[2], "w") as f:
        for rows in pool.imap_unordered(work, files, chunksize=1):
            for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
            if n % 20 == 0: print(n, flush=True)
    print("done", n)
