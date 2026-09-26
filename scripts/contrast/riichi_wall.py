"""For each riichi, where the winning tiles really are: in the live wall, in opponents' hands, or in the dead wall."""
import json, sys
from pathlib import Path
from collections import Counter
from multiprocessing import Pool
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
from build_personal_guide import concealed_hands, meld_snapshots, draws_so_far
from tenhou_replay import base

def work(g):
    out = []
    d = json.load(open(g['file']))
    uuid = g['uuid'].split('#')[0]
    for li, log in enumerate(d['log']):
        game = tr.replay(log)
        ev = game['events']
        # remaining live wall order: all future draws from the event stream (tiles drawn after idx)
        for e in ev:
            if not e['riichi']:
                continue
            R = e['seat']; idx = e['index']
            waits = {base(w) for w in tr.waits(e['hand_after'], e['meld_tiles'], True)}
            hands = concealed_hands(game, idx + 1)
            held = {X: sum(1 for t in hands[X] if base(t) in waits) for X in range(4) if X != R}
            # tiles drawn by anyone after the declaration (the part of the wall actually reached)
            future = [q['drawn'] for q in ev[idx + 1:] if q['drawn'] is not None]
            reached = sum(1 for t in future if base(t) in waits)
            out.append({'g': uuid, 'li': li, 'R': R, 'lj': g['grp'] == 'lj' and R == g['lj_seat'], 'grp': g['grp'],
                        'held': sum(held.values()), 'held_max': max(held.values()), 'drawn_later': reached})
    return out

if __name__ == '__main__':
    manifest, grp, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    m = json.load(open(manifest)); seen = {}
    for g in m:
        if g['file'] not in seen:
            seen[g['file']] = dict(g, grp=grp, lj_seat=g['hero_seat'])
    with Pool(3) as p:
        res = p.map(work, list(seen.values()), chunksize=4)
    json.dump([r for c in res for r in c], open(outp, 'w'))
