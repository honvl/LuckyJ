"""Discards against a single caller with nobody in riichi: the danger and acceptance of every tile that keeps the best shanten.

usage: early_ties.py MANIFEST OUT.jsonl (a manifest in the fetch_majsoul_games shape; the hero seat is the player measured)

Used for chapter 13 of the personal guide: when a safe tile and a live tile tie for the best acceptance while the
caller is still early (under 30% likely to be tenpai by calls and discards), which one does the player cut?
"""
import json, sys
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tenhou_replay as tr, review_win_speed as ws
from build_personal_guide import DANGER, meld_snapshots, safety, visible_counter
from tenhou_replay import base
ODDS = json.load(open(Path(__file__).resolve().parents[3] / 'analysis/open-callers-2026-09-27.json'))['fold_line']['caller_tenpai_pct']
def band(t): return 0 if t <= 6 else 1 if t <= 9 else 2 if t <= 12 else 3
def work(g):
    out = []
    d = json.load(open(g['file'])); hero = g['hero_seat']
    for li, log in enumerate(d['log']):
        game = tr.replay(log); players = game['players']; inds = game['dora_indicators'][:1]
        seat_events = {q: [] for q in range(4)}
        for e in game['events']:
            s = e['seat']; i = e['index']
            if s == hero and not any(v is not None for v in e['riichi_seats'].values()) and not e['riichi']:
                melds = {q: [m for m in players[q]['melds'][:e['meld_counts'][q]] if m['kind'] != 'a'] for q in range(4) if q != s}
                callers = [q for q, v in melds.items() if v and seat_events[q]]
                if len(callers) == 1:
                    q = callers[0]
                    odds = ODDS[str(min(len(melds[q]), 3))][band(len(seat_events[q]))]
                    snap = meld_snapshots(game, i - 1); snap[s] = e['melds']
                    vis = visible_counter(e['hand_before'], e, players, snap, inds)
                    opts = {}
                    for t in {base(x): x for x in e['hand_before']}.values():
                        rest = list(e['hand_before']); rest.remove(t)
                        sh = ws.hand_shanten(rest, e['meld_tiles'], e['closed'])
                        sn = vis.copy(); sn[base(t)] -= 1
                        opts[base(t)] = [sh, DANGER[safety(t, q, e, game, sn)], t, rest]
                    best = min(o[0] for o in opts.values())
                    if best >= 1:
                        keep = {b: o for b, o in opts.items() if o[0] == best}
                        acc = {b: ws.acceptance(o[3], e['meld_tiles'], e['closed'], vis)[1] for b, o in keep.items()}
                        out.append({'g': g['uuid'][:15], 'li': li, 't': e['turn'], 'odds': odds, 'best': best, 'cut': base(e['tile']),
                                    'keep': {str(b): [o[1], acc[b]] for b, o in keep.items()}, 'cut_sh': opts[base(e['tile'])][0]})
            seat_events[s].append(e)
    return out
if __name__ == '__main__':
    man, outp = sys.argv[1], sys.argv[2]
    games = json.load(open(man))
    seen = {}
    for g in games:
        seen.setdefault(g['file'], g)
    with Pool(14) as p, open(outp, 'w') as f:
        n = 0
        for rows in p.imap_unordered(work, list(seen.values()), chunksize=2):
            for r in rows:
                f.write(json.dumps(r) + '\n'); n += 1
    print(outp, n)
