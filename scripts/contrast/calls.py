"""Every chance to chi or pon, for every seat, with the block the call would use.

usage: calls.py MANIFEST OUT.jsonl
"""
import json, sys
from pathlib import Path
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
import review_win_speed as ws
from build_personal_guide import meld_snapshots, visible_counter, draws_so_far, concealed_hands
from mine_call_chances import call_options, kuikae, route, yaku_reachable
from mine_open_tenpai_push import ron_value
from tenhou_replay import base, is_red, is_honor


def block_type(kind, tile, used):
    if kind == 'p':
        return 'pair'
    b = base(tile)
    u = sorted(base(x) for x in used)
    if u[0] < b < u[1]:
        return 'kanchan'
    lo = min(u[0], b); hi = max(u[1], b)
    # the partial that was in hand: used tiles; penchan when it is 1-2 (waiting 3) or 8-9 (waiting 7)
    if (u[0] % 10, u[1] % 10) in ((1, 2), (8, 9)):
        return 'penchan'
    return 'ryanmen'


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
        events = game['events']; players = game['players']
        kyoku = game['kyoku']
        inds = game['dora_indicators'][:1]
        dset = frozenset(ws.dora_from_indicator(t) for t in inds)
        isd = lambda t: base(t) in dset or is_red(t)
        blocks = tr.result_blocks(log[-1])
        ron_tiles = set()
        for dl, det in blocks:
            if det[0] != det[1]:
                ron_tiles.add(det[1])
        deltas = tr.result_deltas(log[-1]); paid = tr.riichi_sticks_paid(log)
        winners = {det[0] for _, det in blocks}
        losers = {det[1] for _, det in blocks if det[0] != det[1]}
        for i, e in enumerate(events):
            X = e['seat']; t = e['tile']
            if i + 1 >= len(events):
                continue  # last discard: ron or draw, no call decision recorded
            nxt = events[i + 1]
            hands = None
            for Y in range(4):
                if Y == X:
                    continue
                if e['riichi_seats'][Y] is not None:
                    continue
                # Y's concealed hand and melds right now
                if hands is None:
                    hands = concealed_hands(game, i + 1)
                    snap = meld_snapshots(game, i)
                h13 = hands[Y]
                opts = call_options(h13, t, (X + 1) % 4 == Y)
                if not opts:
                    continue
                other_call = nxt['called'] is not None and nxt['seat'] != Y and nxt['called']['src'] == X
                took = nxt['seat'] == Y and nxt['called'] is not None and nxt['called']['src'] == X and nxt['called']['kind'] in ('c', 'p', 'm')
                if other_call:
                    # a pon elsewhere pre-empts a chi; a chi elsewhere means Y passed a pon
                    if nxt['called']['kind'] != 'c' or not any(k == 'p' for k, _ in opts):
                        continue
                    opts = [o for o in opts if o[0] == 'p']
                my_melds = snap[Y]
                meld_tiles = [x for m in my_melds for x in m[:3]]
                closed = all(m['kind'] == 'a' for m in players[Y]['melds'][:len(my_melds)])
                sh = ws.hand_shanten(h13, meld_tiles, closed)
                vis = visible_counter(h13, e, players, snap, inds)
                acc = ws.acceptance(h13, meld_tiles, closed, vis)[1]
                my_turn = sum(1 for q in events[:i + 1] if q['seat'] == Y) + 1
                out_opts = []
                for kind, used in opts:
                    rest = list(h13)
                    for x in used:
                        rest.remove(x)
                    mt = sorted(used + [t], key=base)
                    bad = kuikae(kind, t, used)
                    best = None
                    for dd in {base(x): x for x in rest}.values():
                        if base(dd) in bad:
                            continue
                        r = list(rest); r.remove(dd)
                        s2 = ws.hand_shanten(r, meld_tiles + mt, False)
                        if best is None or s2 < best[0]:
                            best = (s2, r)
                    if best is None:
                        continue
                    s2, r = best
                    yak = None; han = None
                    if s2 == 0:
                        meld = {'kind': kind, 'tiles': mt, 'called': t}
                        prior = [{'kind': ('p' if (pm['kind'] == 'k' and len(st) == 3) else pm['kind']), 'tiles': list(st), 'called': pm['called']}
                                 for pm, st in zip(players[Y]['melds'], my_melds)]
                        hs = [ron_value(r, prior + [meld], w, Y, kyoku, dset) for w in tr.waits(r, meld_tiles + mt, False)]
                        han = max((h for h in hs if h is not None), default=0)
                        yak = han > 0
                    elif s2 == 1 and not my_melds:
                        yak = yaku_reachable(tuple(sorted(base(x) for x in r)), tuple(base(x) for x in mt), kind, Y, kyoku, dset)
                    out_opts.append({'k': kind, 'bt': block_type(kind, t, used), 's2': s2, 'yak': yak, 'han': han,
                                     'route': route(kind, t, mt, r, Y, kyoku),
                                     'used': sorted(base(x) for x in used)})
                if not out_opts:
                    continue
                took_used = None
                if took:
                    ct = players[Y]['melds'][len(my_melds)]
                    tl = list(ct['tiles']); tl.remove(ct['called'])
                    took_used = sorted(base(x) for x in tl)
                rows.append({
                    'g': uuid, 'li': li, 'k': kyoku, 'Y': Y, 'X': X, 'lj': Y == hero, 'dl': Y == game['dealer'],
                    't': my_turn, 'left': 70 - draws_so_far(game, i), 'rk': rank_of(log[1], Y),
                    'closed': closed, 'nm': len(my_melds), 'sh': sh, 'acc': acc,
                    'hd': sum(1 for x in list(h13) + meld_tiles if isd(x)), 'tile': base(t), 'tdora': isd(t),
                    'ypair': any(Counter(base(x) for x in h13)[yy] >= 2 for yy in tr.yakuhai_for(Y, kyoku)),
                    'nr': sum(1 for q in range(4) if q != Y and e['riichi_seats'][q] is not None or (q == X and e['riichi'])),
                    'mo': max(sum(1 for m in players[q]['melds'][:len(snap[q])] if m['kind'] != 'a') for q in range(4) if q != Y),
                    'opts': out_opts, 'took': took, 'took_used': took_used,
                    'won': Y in winners, 'dealt': Y in losers, 'net': deltas[Y] - 1000 * paid[Y],
                })
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
