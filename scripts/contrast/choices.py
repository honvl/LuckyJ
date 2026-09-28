"""Every discard decision of the manifest's hero, with the features of each tile it could have cut.

usage: choices.py MANIFEST OUT.jsonl [--procs P]

One row per discard (after a draw or a call), keyed (g, li, t) like the guide's turns. Each candidate tile
carries the shanten and acceptance it leaves, its class (value or guest honor, terminal, 2/8, middle), dora and
red flags, whether it is isolated, and its safety against the riichi players (worst label) or, with no riichi,
against the opponents with the most calls; ``pond`` is how many tiles the most advanced of those threats has
discarded. Joined to the local Mortal policy's probabilities, these rows sort
disagreements with Mortal into kinds, for the hero and for LuckyJ alike.
"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import tenhou_replay as tr  # noqa: E402
import review_win_speed as ws  # noqa: E402
from build_personal_guide import draws_so_far, meld_snapshots, safety, visible_counter  # noqa: E402
from discards import CLASS_OF, isolated, rank_of, tclass  # noqa: E402
from tenhou_replay import base, is_red  # noqa: E402


def work(g):
    rows = []
    d = json.load(open(g["file"]))
    uuid = g["uuid"].split("#")[0]
    hero = g["hero_seat"]
    for li, log in enumerate(d["log"]):
        game = tr.replay(log)
        players, kyoku, scores = game["players"], game["kyoku"], log[1]
        inds = game["dora_indicators"][:1]
        dset = frozenset(ws.dora_from_indicator(t) for t in inds)
        yak = tr.yakuhai_for(hero, kyoku)
        for e in game["events"]:
            s, i = e["seat"], e["index"]
            if s != hero or (e["riichi_seats"][s] is not None and e["riichi_seats"][s] < i):
                continue
            snap = meld_snapshots(game, i - 1)
            snap[s] = e["melds"]
            vis = visible_counter(e["hand_before"], e, players, snap, inds)
            hb = e["hand_before"]
            counts = Counter(base(t) for t in hb)
            rseats = [q for q in range(4) if q != s and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < i]
            opens = {q: sum(1 for m in players[q]["melds"][:e["meld_counts"][q]] if m["kind"] != "a")
                     for q in range(4) if q != s}
            mo = max(opens.values())
            threats = rseats or ([q for q, v in opens.items() if v == mo] if mo else [])
            # how far along the threat is: the most discards any of them has made (their pond, called tiles included)
            pond = max((sum(1 for x in game["events"] if x["seat"] == q and x["index"] < i) for q in threats), default=0)
            cands = []
            for t in {base(x): x for x in hb}.values():
                b = base(t)
                rest = list(hb)
                rest.remove(t)
                sh, uk, _ = ws.acceptance(rest, e["meld_tiles"], e["closed"], vis)
                seen = vis.copy()
                seen[b] -= 1
                labs = [safety(t, q, e, game, seen) for q in threats]
                cands.append({"b": b, "sh": sh, "uk": uk, "tc": tclass(b, yak), "dora": b in dset,
                              "red": any(is_red(x) and base(x) == b for x in hb), "n": counts[b],
                              "iso": isolated(b, counts),
                              "safe": max((CLASS_OF[x] for x in labs), default=None)})
            best_s = min(c["sh"] for c in cands)
            rows.append({
                "g": uuid, "li": li, "t": e["turn"], "i": i, "k": kyoku, "dl": hero == game["dealer"],
                "rk": rank_of(scores, s), "sc": scores[s], "left": 70 - draws_so_far(game, i),
                "closed": e["closed"], "nm": len(e["melds"]), "called": e["called"]["kind"] if e["called"] else None,
                "bs": best_s, "hd": sum(1 for t in list(hb) + list(e["meld_tiles"]) if base(t) in dset or is_red(t)),
                "nr": len(rseats), "rdealer": any(q == game["dealer"] for q in rseats), "mo": mo,
                "no": sum(1 for v in opens.values() if v), "pond": pond, "cut": base(e["tile"]), "tg": e["tsumogiri"],
                "rd": e["riichi"], "cands": cands,
            })
    return rows


if __name__ == "__main__":
    manifest = json.load(open(sys.argv[1]))
    procs = int(sys.argv[sys.argv.index("--procs") + 1]) if "--procs" in sys.argv else 12
    with Pool(procs) as pool, open(sys.argv[2], "w") as out:
        n = 0
        for rows in pool.imap_unordered(work, manifest, chunksize=2):
            for r in rows:
                out.write(json.dumps(r) + "\n")
                n += 1
    print(sys.argv[2], n)
