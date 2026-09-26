"""Per-discard feature rows for every seat in LuckyJ's games.

usage: discards.py MANIFEST OUT.jsonl [--limit N]
"""
import json, sys
from pathlib import Path
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
import review_win_speed as ws
from build_personal_guide import safety, meld_snapshots, visible_counter, draws_so_far, DANGER
from tenhou_replay import base, is_red, is_honor, is_terminal

CLASS_OF = {"genbutsu": 0, "dead": 0, "honor, 2 seen": 1, "suji": 2, "nakasuji": 2, "virtual nakasuji": 3,
            "live honor": 3, "live terminal": 4, "half suji": 5, "live 2-3-7-8": 6, "live 4-5-6": 7}
# empirical deal-in per 100 cuts into a single riichi (pooled table-mates, riichi_folds report)
RISK = {"genbutsu": 0.0, "dead": 0.0, "honor, 2 seen": 0.3, "suji": 3.3, "nakasuji": 2.9, "virtual nakasuji": 4.0,
        "live honor": 2.8, "live terminal": 6.5, "half suji": 8.5, "live 2-3-7-8": 8.0, "live 4-5-6": 10.0}


def tclass(b, yak):
    if b >= 41:
        return 'value' if b in yak else 'guest'
    n = b % 10
    if n in (1, 9):
        return 'term'
    if n in (2, 8):
        return '28'
    return 'mid'


def isolated(b, counts):
    if counts[b] != 1:
        return False
    if b >= 41:
        return True
    suit = b // 10
    for d in (-2, -1, 1, 2):
        nb = b + d
        if nb // 10 == suit and 1 <= nb % 10 <= 9 and counts[nb]:
            return False
    return True


EARLY_ONLY = '--early' in sys.argv


def rank_of(scores, s):
    order = sorted(range(4), key=lambda q: (-scores[q], q))
    return order.index(s) + 1


def work(g):
    rows = []
    d = json.load(open(g['file']))
    uuid = g['uuid'].split('#')[0]
    hero = g['hero_seat']
    for li, log in enumerate(d['log']):
        game = tr.replay(log)
        players = game['players']
        kyoku = game['kyoku']
        scores = log[1]
        inds = game['dora_indicators'][:1]
        dset = frozenset(ws.dora_from_indicator(t) for t in inds)
        yak = {s: tr.yakuhai_for(s, kyoku) for s in range(4)}
        for e in game['events']:
            s = e['seat']; i = e['index']
            locked = e['riichi_seats'][s] is not None and e['riichi_seats'][s] < i
            if locked:
                continue
            if EARLY_ONLY and (e['turn'] > 9 or not e['closed'] or any(e['riichi_seats'][q] is not None and e['riichi_seats'][q] < i for q in range(4) if q != s)):
                continue
            snap = meld_snapshots(game, i - 1)
            snap[s] = e['melds']
            vis = visible_counter(e['hand_before'], e, players, snap, inds)
            hb = e['hand_before']
            counts = Counter(base(t) for t in hb)
            cands = {}
            for t in {base(x): x for x in hb}.values():
                rest = list(hb); rest.remove(t)
                sh, uk, kinds = ws.acceptance(rest, e['meld_tiles'], e['closed'], vis)
                cands[base(t)] = (sh, uk)
            best_s = min(v[0] for v in cands.values())
            best_u = max(v[1] for v in cands.values() if v[0] == best_s)
            cb = base(e['tile'])
            a_s, a_u = cands[cb]
            rseats = [q for q in range(4) if q != s and e['riichi_seats'][q] is not None and e['riichi_seats'][q] < i]
            opens = {q: sum(1 for m in players[q]['melds'][:e['meld_counts'][q]] if m['kind'] != 'a') for q in range(4) if q != s}
            # isolated singles by class, and the cheapest (in acceptance) isolated tile of each class
            iso = {}
            for b in cands:
                if isolated(b, counts):
                    c = tclass(b, yak[s])
                    iso.setdefault(c, []).append(b)
            iso_info = {}
            for c, bs in iso.items():
                keepers = [b for b in bs if cands[b][0] == best_s]
                iso_info[c] = {'n': len(bs), 'keep_best': len(keepers),
                               'loss': (min(best_u - cands[b][1] for b in keepers) if keepers else None)}
            row = {
                'g': uuid, 'li': li, 'k': kyoku, 'h': game['honba'], 's': s, 'lj': s == hero, 'dl': s == game['dealer'],
                't': e['turn'], 'i': i, 'left': 70 - draws_so_far(game, i),
                'sc': scores[s], 'rk': rank_of(scores, s), 'closed': e['closed'], 'nm': len(e['melds']),
                'bs': best_s, 'bu': best_u, 'as': a_s, 'au': a_u,
                'tile': e['tile'], 'tb': cb, 'tc': tclass(cb, yak[s]), 'red': is_red(e['tile']), 'dora': cb in dset,
                'iso_c': (tclass(cb, yak[s]) if isolated(cb, counts) else None),
                'tg': e['tsumogiri'], 'rd': e['riichi'], 'called': e['called']['kind'] if e['called'] else None,
                'hd': sum(1 for t in list(hb) + list(e['meld_tiles']) if base(t) in dset or is_red(t)),
                'ypair': any(counts[t] >= 2 for t in yak[s]),
                'nr': len(rseats), 'rdealer': any(q == game['dealer'] for q in rseats),
                'mo': max(opens.values()), 'no': sum(1 for v in opens.values() if v > 0),
                'iso': iso_info,
            }
            if rseats:
                labs = {}
                for b, t in {base(x): x for x in hb}.items():
                    seen = vis.copy(); seen[b] -= 1
                    ll = [safety(t, q, e, game, seen) for q in rseats]
                    labs[b] = max(ll, key=lambda l: CLASS_OF[l])
                row['rs_a'] = labs[cb]
                row['rs_min_best'] = min((labs[b] for b in cands if cands[b][0] == best_s), key=lambda l: CLASS_OF[l])
                row['rs_min_all'] = min(labs.values(), key=lambda l: CLASS_OF[l])
                row['risk_a'] = RISK[labs[cb]]
                row['risk_min_best'] = min(RISK[labs[b]] for b in cands if cands[b][0] == best_s)
                row['risk_min_all'] = min(RISK[l] for l in labs.values())
                row['n_gen'] = sum(1 for t in hb if labs[base(t)] in ('genbutsu', 'dead'))
                # shanten cost of the safest tile
                safest = min(CLASS_OF[l] for l in labs.values())
                row['sh_safest'] = min(cands[b][0] for b in cands if CLASS_OF[labs[b]] == safest)
            elif max(opens.values()) > 0:
                mx = max(opens.values())
                threats = [q for q, v in opens.items() if v == mx]
                labs = {}
                for b, t in {base(x): x for x in hb}.items():
                    seen = vis.copy(); seen[b] -= 1
                    ll = [safety(t, q, e, game, seen) for q in threats]
                    labs[b] = max(ll, key=lambda l: CLASS_OF[l])
                row['os_a'] = labs[cb]
                row['os_min_best'] = min((labs[b] for b in cands if cands[b][0] == best_s), key=lambda l: CLASS_OF[l])
                row['os_min_all'] = min(labs.values(), key=lambda l: CLASS_OF[l])
            rows.append(row)
    return rows


if __name__ == '__main__':
    manifest, out = sys.argv[1], sys.argv[2]
    m = json.load(open(manifest))
    if '--limit' in sys.argv:
        m = m[:int(sys.argv[sys.argv.index('--limit') + 1])]
    with Pool(int(sys.argv[sys.argv.index('--procs') + 1]) if '--procs' in sys.argv else 14) as p, open(out, 'w') as f:
        n = 0
        for rows in p.imap_unordered(work, m, chunksize=2):
            for r in rows:
                f.write(json.dumps(r) + '\n')
                n += 1
    print(out, n)
