"""Silent closed opponents: is a run of tsumogiri a dama tenpai tell, and does the player answer it?

usage: dama_tell.py MANIFEST LABEL (writes dama_LABEL.json). Used for chapter 14 of the personal guide.
"""
import json, sys
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tenhou_replay as tr, review_win_speed as ws
from tenhou_replay import base
from build_personal_guide import DANGER, meld_snapshots, safety, visible_counter
def work(g):
    out = []
    d = json.load(open(g['file'])); hero = g['hero_seat']
    for li, log in enumerate(d['log']):
        game = tr.replay(log); players = game['players']; inds = game['dora_indicators'][:1]
        blocks = tr.result_blocks(log[-1])
        ron_by = {}
        for _, dd in blocks:
            if dd[0] != dd[1]:
                ron_by.setdefault(dd[1], set()).add(dd[0])
        last = len(game['events']) - 1
        seat_events = {q: [] for q in range(4)}
        for e in game['events']:
            s = e['seat']; i = e['index']
            if s == hero and not any(v is not None for v in e['riichi_seats'].values()) and not e['riichi']:
                others_open = any(any(m['kind'] != 'a' for m in players[q]['melds'][:e['meld_counts'][q]]) for q in range(4) if q != s)
                cand = None
                for q in range(4):
                    if q == s or not seat_events[q] or len(seat_events[q]) < 6: continue
                    if any(m['kind'] != 'a' for m in players[q]['melds'][:e['meld_counts'][q]]): continue
                    qe = seat_events[q]
                    run = 0
                    for x in reversed(qe):
                        if x['tsumogiri']: run += 1
                        else: break
                    ql = qe[-1]
                    tenpai = ws.hand_shanten(ql['hand_after'], ql['meld_tiles'], ql['closed']) == 0
                    snap = None
                    out_row = {'q_turn': len(qe), 'run': run, 'tenpai': tenpai, 'q_dealer': q == game['dealer'], 'others_open': others_open}
                    if cand is None:
                        snap = meld_snapshots(game, i - 1); snap[s] = e['melds']
                        vis = visible_counter(e['hand_before'], e, players, snap, inds)
                        opts = {}
                        for t in {base(x): x for x in e['hand_before']}.values():
                            rest = list(e['hand_before']); rest.remove(t)
                            opts[base(t)] = (t, ws.hand_shanten(rest, e['meld_tiles'], e['closed']))
                        best = min(o[1] for o in opts.values())
                        cand = (vis, opts, best)
                    vis, opts, best = cand
                    dng = {}
                    for b, (t, sh) in opts.items():
                        sn = vis.copy(); sn[b] -= 1
                        dng[b] = DANGER[safety(t, q, e, game, sn)]
                    keep_safe = min(dng[b] for b, (t, sh) in opts.items() if sh == best)
                    cut = base(e['tile'])
                    out_row.update({'best_sh': best, 'keep_safe': keep_safe, 'danger': dng[cut], 'cut_keeps': opts[cut][1] == best,
                                    'dealt': i == last and q in ron_by.get(s, set())})
                    out.append(out_row)
            seat_events[s].append(e)
    return out
if __name__ == '__main__':
    man, label = sys.argv[1], sys.argv[2]
    games = list({g['file']: g for g in json.load(open(man))}.values())
    with Pool(14) as p:
        rows = [r for rs in p.imap_unordered(work, games, chunksize=2) for r in rs]
    json.dump(rows, open(f'dama_{label}.json', 'w'))
    print(label, len(rows))
