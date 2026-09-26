"""Every closed decision where a tenpai is available: the tenpai options, riichi or dama, and the outcome.

usage: tenpai.py MANIFEST OUT.jsonl
"""
import json, sys
from pathlib import Path
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
import review_win_speed as ws
from build_personal_guide import meld_snapshots, visible_counter, draws_so_far
from mine_open_tenpai_push import ron_value
from tenhou_replay import base, is_red, is_honor, is_terminal


def rank_of(scores, s):
    order = sorted(range(4), key=lambda q: (-scores[q], q))
    return order.index(s) + 1


def wait_shape(hand13, waits):
    """Rough wait label from the winning tiles."""
    bs = sorted({base(w) for w in waits})
    if len(bs) >= 3:
        return 'multi'
    if len(bs) == 2:
        a, b = bs
        if a // 10 == b // 10 and b - a == 3 and a < 41:
            return 'ryanmen'
        return 'shanpon'  # or other two-kind waits
    b = bs[0]
    c = Counter(base(x) for x in hand13)
    if c[b] == 1 and (b >= 41 or True):
        # tanki if the lone copy is the wait and it is isolated as a pair candidate
        pass
    if b >= 41:
        return 'tanki-honor'
    n = b % 10
    suit = b // 10 * 10
    if c[suit + n - 1] and c[suit + n + 1]:
        return 'kanchan'
    if (n == 3 and c[suit + 1] and c[suit + 2]) or (n == 7 and c[suit + 8] and c[suit + 9]):
        return 'penchan'
    return 'tanki'


def work(g):
    rows = []
    d = json.load(open(g['file']))
    uuid = g['uuid'].split('#')[0]
    hero = g['hero_seat']
    for li, log in enumerate(d['log']):
        game = tr.replay(log)
        players = game['players']
        kyoku = game['kyoku']
        inds = game['dora_indicators'][:1]
        dset = frozenset(ws.dora_from_indicator(t) for t in inds)
        blocks = tr.result_blocks(log[-1])
        deltas = tr.result_deltas(log[-1]); paid = tr.riichi_sticks_paid(log)
        winners = {det[0]: det[1] for _, det in blocks}
        losers = {det[1]: det[0] for _, det in blocks if det[0] != det[1]}
        seen_first = set()
        for e in game['events']:
            s = e['seat']; i = e['index']
            if e['riichi_seats'][s] is not None and e['riichi_seats'][s] < i:
                continue
            closed = all(m['kind'] == 'a' for m in players[s]['melds'][:len(e['melds'])])
            if not closed:
                continue
            hb = e['hand_before']
            opts = {}
            for t in {base(x): x for x in hb}.values():
                rest = list(hb); rest.remove(t)
                if ws.hand_shanten(rest, e['meld_tiles'], True) == 0:
                    opts[base(t)] = rest
            if not opts:
                continue
            snap = meld_snapshots(game, i - 1); snap[s] = e['melds']
            vis = visible_counter(hb, e, players, snap, inds)
            river = {base(x) for x in e['rivers'][s]}
            my_melds = [{'kind': pm['kind'], 'tiles': list(st), 'called': pm['called']} for pm, st in zip(players[s]['melds'], e['melds'])]
            out_opts = []
            for b, rest in opts.items():
                waits = tr.waits(rest, e['meld_tiles'], True)
                live = sum(max(0, 4 - vis[base(w)]) for w in waits)
                fur = any(base(w) in river or base(w) == b for w in waits)
                dama = [ron_value(rest, my_melds, w, s, kyoku, dset, riichi=False) or 0 for w in waits]
                rich = [ron_value(rest, my_melds, w, s, kyoku, dset, riichi=True) or 0 for w in waits]
                out_opts.append({'b': b, 'live': live, 'kinds': len({base(w) for w in waits}), 'fur': fur,
                                 'dama_max': max(dama) if dama else 0, 'dama_min': min(dama) if dama else 0,
                                 'riichi_max': max(rich) if rich else 0, 'shape': wait_shape(rest, waits),
                                 'waits': sorted({base(w) for w in waits})})
            cb = base(e['tile'])
            rseats = [q for q in range(4) if q != s and e['riichi_seats'][q] is not None and e['riichi_seats'][q] < i]
            opens = {q: sum(1 for m in players[q]['melds'][:e['meld_counts'][q]] if m['kind'] != 'a') for q in range(4) if q != s}
            first = s not in seen_first
            seen_first.add(s)
            rows.append({
                'g': uuid, 'li': li, 'k': kyoku, 'h': game['honba'], 's': s, 'lj': s == hero, 'dl': s == game['dealer'],
                't': e['turn'], 'left': 70 - draws_so_far(game, i), 'sc': log[1], 'rk': rank_of(log[1], s),
                'first': first, 'opts': out_opts, 'cut': cb, 'kept': cb in opts, 'riichi': e['riichi'],
                'nr': len(rseats), 'mo': max(opens.values()), 'no': sum(1 for v in opens.values() if v),
                'hd': sum(1 for t in list(hb) + list(e['meld_tiles']) if base(t) in dset or is_red(t)),
                'score': players[s]['haipai'] and log[1][s],
                'won': s in winners, 'tsumo': winners.get(s) == s, 'dealt': s in losers,
                'net': deltas[s] - 1000 * paid[s], 'later_riichi': players[s]['riichi_event'] is not None and players[s]['riichi_event'] > i,
            })
    return rows


if __name__ == '__main__':
    manifest, out = sys.argv[1], sys.argv[2]
    m = json.load(open(manifest))
    if '--limit' in sys.argv:
        m = m[:int(sys.argv[sys.argv.index('--limit') + 1])]
    procs = int(sys.argv[sys.argv.index('--procs') + 1]) if '--procs' in sys.argv else 14
    with Pool(procs) as p, open(out, 'w') as f:
        n = 0
        for rows in p.imap_unordered(work, m, chunksize=2):
            for r in rows:
                f.write(json.dumps(r) + '\n')
                n += 1
    print(out, n)
