"""Pons that keep an open hand's shanten: how many tiles would give tenpai with and without the pon.

usage: idle_pons.py MANIFEST OUT.jsonl

One row per chance for the manifest's hero to pon a number tile, with one call already made and nobody in
riichi, where the pon would leave the shanten where it is. For each side it records the shanten and the
unseen tiles that would lower it: passing (the hand as it is) and ponning (the best discard after the pon).
Used for the correction to chapter 15 of the personal guide.
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tenhou_replay as tr  # noqa: E402
import review_win_speed as ws  # noqa: E402
from build_personal_guide import concealed_hands, meld_snapshots, visible_counter  # noqa: E402
from tenhou_replay import base, is_red  # noqa: E402


def work(g):
    rows = []
    d = json.load(open(g["file"]))
    hero = g["hero_seat"]
    for li, log in enumerate(d["log"]):
        game = tr.replay(log)
        events, players = game["events"], game["players"]
        inds = game["dora_indicators"][:1]
        dset = frozenset(ws.dora_from_indicator(t) for t in inds)
        blocks = tr.result_blocks(log[-1])
        won = any(det[0] == hero for _, det in blocks)
        dealt = any(det[1] == hero and det[0] != hero for _, det in blocks)
        net = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero]
        for i, e in enumerate(events):
            X, t = e["seat"], e["tile"]
            if X == hero or base(t) > 40 or i + 1 >= len(events):
                continue
            if any(e["riichi_seats"][q] is not None for q in range(4) if q != hero) or e["riichi"]:
                continue
            snap = meld_snapshots(game, i)
            if len(snap[hero]) != 1:
                continue
            h13 = concealed_hands(game, i + 1)[hero]
            if sum(1 for x in h13 if base(x) == base(t)) < 2:
                continue
            meld_tiles = [x for m in snap[hero] for x in m[:3]]
            vis = visible_counter(h13, e, players, snap, inds)
            s_pass, acc_pass, _ = ws.acceptance(h13, meld_tiles, False, vis)
            used = [x for x in h13 if base(x) == base(t)][:2]
            rest = list(h13)
            for x in used:
                rest.remove(x)
            best = None
            for dd in {base(x): x for x in rest}.values():
                if base(dd) == base(t):
                    continue
                r = list(rest)
                r.remove(dd)
                s2, acc2, _ = ws.acceptance(r, meld_tiles + used + [t], False, vis)
                if best is None or (s2, -acc2) < (best[0], -best[1]):
                    best = (s2, acc2)
            if best is None or best[0] != s_pass:
                continue
            nxt = events[i + 1]
            took = nxt["seat"] == hero and nxt["called"] is not None and nxt["called"]["kind"] == "p" \
                and nxt["called"]["src"] == X
            rows.append({"g": g["uuid"], "li": li, "t": sum(1 for q in events[:i + 1] if q["seat"] == hero) + 1,
                         "sh": s_pass, "acc_pass": acc_pass, "acc_pon": best[1],
                         "dora_in_hand": sum(1 for x in h13 + meld_tiles if base(x) in dset or is_red(x)),
                         "took": took, "won": won, "dealt": dealt, "net": net})
    return rows


if __name__ == "__main__":
    manifest = json.load(open(sys.argv[1]))
    with Pool(12) as pool, open(sys.argv[2], "w") as out:
        n = 0
        for rows in pool.imap_unordered(work, manifest, chunksize=2):
            for r in rows:
                out.write(json.dumps(r) + "\n")
                n += 1
    print(sys.argv[2], n)
