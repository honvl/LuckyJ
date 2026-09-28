"""Three open melds, a riichi on the table and a tenpai available: does the player keep it? Prints LuckyJ
(man/lj_all.json) and the personal games (self/all115.json), run from the scratch working directory. Chapter 14.
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
        won = any(dd[0] == hero for _, dd in blocks)
        dealt_final = any(len(dd) > 1 and dd[1] == hero and dd[0] != hero for _, dd in blocks)
        net = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero]
        first = True
        for e in game['events']:
            s = e['seat']; i = e['index']
            if s != hero: continue
            if sum(1 for m in players[hero]['melds'][:e['meld_counts'][hero]] if m['kind'] != 'a') != 3: continue
            rseats = [q for q in range(4) if q != s and e['riichi_seats'][q] is not None and e['riichi_seats'][q] < i]
            if not rseats: continue
            snap = meld_snapshots(game, i - 1); snap[s] = e['melds']
            vis = visible_counter(e['hand_before'], e, players, snap, inds)
            opts = {}
            for t in {base(x): x for x in e['hand_before']}.values():
                rest = list(e['hand_before']); rest.remove(t)
                sn = vis.copy(); sn[base(t)] -= 1
                opts[base(t)] = (ws.hand_shanten(rest, e['meld_tiles'], False), max(DANGER[safety(t, q, e, game, sn)] for q in rseats))
            if min(o[0] for o in opts.values()) != 0: continue
            keep = {b: o for b, o in opts.items() if o[0] == 0}
            c = opts[base(e['tile'])]
            out.append({'first': first, 'kept': c[0] == 0, 'keep_min_danger': min(o[1] for o in keep.values()), 'cut_danger': c[1],
                        'won': won, 'dealt_final': dealt_final, 'net': net})
            first = False
    return out
if __name__ == '__main__':
    for man, label in (('man/lj_all.json', 'LuckyJ'), ('self/all115.json', 'you')):
        games = list({g['file']: g for g in json.load(open(man))}.values())
        with Pool(14) as p:
            rows = [r for rs in p.imap_unordered(work, games, chunksize=2) for r in rs]
        f = rows
        kept = sum(r['kept'] for r in f)
        safe_keep = [r for r in f if r['keep_min_danger'] <= 1]
        live_keep = [r for r in f if r['keep_min_danger'] >= 2]
        print(f"{label}: every turn with three calls, tenpai available, facing a riichi: {len(f)}; kept tenpai {kept} ({100*kept/max(1,len(f)):.0f}%)")
        print(f"   a safe tile kept the tenpai: {len(safe_keep)}, kept {sum(r['kept'] for r in safe_keep)}; only live tiles kept it: {len(live_keep)}, kept {sum(r['kept'] for r in live_keep)}")
        k = [r for r in f if r['kept']]; b = [r for r in f if not r['kept']]
        for name, grp in (('kept', k), ('broke', b)):
            if grp:
                print(f"   {name}: won {100*sum(r['won'] for r in grp)/len(grp):.0f}%, dealt in {100*sum(r['dealt_final'] for r in grp)/len(grp):.0f}%, net {sum(r['net'] for r in grp)/len(grp):+.0f} (n {len(grp)})")
