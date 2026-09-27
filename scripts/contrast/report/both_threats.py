"""With a riichi and an open caller out at once: when a tile safe against both keeps the best shanten, how often does
the player cut one? Prints LuckyJ (man/lj_all.json) and the personal games (self/all.json), run from the scratch
working directory. Used for chapter 13 of the personal guide.
"""
import json, sys
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tenhou_replay as tr, review_win_speed as ws
from build_personal_guide import DANGER, meld_snapshots, safety, visible_counter
from tenhou_replay import base
def work(g):
    out = []
    d = json.load(open(g['file'])); hero = g['hero_seat']
    for log in d['log']:
        game = tr.replay(log); players = game['players']; inds = game['dora_indicators'][:1]
        seen_any = {q: False for q in range(4)}
        for e in game['events']:
            s = e['seat']; i = e['index']
            if s == hero and not (e['riichi_seats'][s] is not None and e['riichi_seats'][s] < i):
                rseats = [q for q in range(4) if q != s and e['riichi_seats'][q] is not None and e['riichi_seats'][q] < i]
                callers = [q for q in range(4) if q != s and q not in rseats and seen_any[q] and any(m['kind'] != 'a' for m in players[q]['melds'][:e['meld_counts'][q]])]
                if rseats and callers:
                    snap = meld_snapshots(game, i - 1); snap[s] = e['melds']
                    vis = visible_counter(e['hand_before'], e, players, snap, inds)
                    opts = {}
                    for t in {base(x): x for x in e['hand_before']}.values():
                        rest = list(e['hand_before']); rest.remove(t)
                        sn = vis.copy(); sn[base(t)] -= 1
                        dr = max(DANGER[safety(t, q, e, game, sn)] for q in rseats)
                        dc = max(DANGER[safety(t, q, e, game, sn)] for q in callers)
                        opts[base(t)] = (ws.hand_shanten(rest, e['meld_tiles'], e['closed']), dr, dc)
                    best = min(o[0] for o in opts.values())
                    both = [b for b, o in opts.items() if o[0] == best and o[1] <= 1 and o[2] <= 1]
                    split = [b for b, o in opts.items() if o[0] == best and ((o[1] <= 1) != (o[2] <= 1))]
                    if best >= 1 and both and split:
                        c = opts[base(e['tile'])]
                        out.append({'best': best, 'cut_both': c[1] <= 1 and c[2] <= 1, 'cut_split': (c[1] <= 1) != (c[2] <= 1)})
            seen_any[s] = True
    return out
if __name__ == '__main__':
    for man, label in (('man/lj_all.json', 'LuckyJ'), ('self/all.json', 'you')):
        games = {g['file']: g for g in json.load(open(man))}.values()
        with Pool(14) as p:
            rows = [r for rs in p.imap_unordered(work, list(games), chunksize=2) for r in rs]
        n = len(rows); both = sum(r['cut_both'] for r in rows); split = sum(r['cut_split'] for r in rows)
        far = [r for r in rows if r['best'] >= 2]
        print(label, 'spots', n, 'cut a tile safe against both', round(100 * both / n, 1), 'cut a tile safe against only one', round(100 * split / n, 1),
              '| far hands', len(far), round(100 * sum(r['cut_both'] for r in far) / max(1, len(far)), 1))
