"""Closed tenpai decisions made under threat: which tenpai each discard keeps, how dangerous it is, and riichi or dama.

usage: riichi_danger.py MANIFEST GROUP OUT.jsonl [--procs N] [--limit N]

GROUP is "lj" for LuckyJ's games (the hero seat is LuckyJ, the other seats its Tokujou tablemates) or
anything else for a four-seat human baseline such as the Houou manifest.

One row per discard by a closed hand that is not yet in riichi, holds a tenpai option and faces a threat
(an opponent in riichi, or an opponent with an open meld). Each tenpai option records the discard, its
live winning tiles, furiten, the han of a ron with and without riichi, and the discard's danger label
against the riichi players and against the callers (``build_personal_guide.safety``, which treats tiles
passed after a riichi as genbutsu), plus whether the discard really was on a threat's wait.
"""
import json
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
import review_win_speed as ws
from build_personal_guide import DANGER, draws_so_far, meld_snapshots, safety, visible_counter
from mine_caller_tells import caller_tells
from mine_open_tenpai_push import ron_value
from tenhou_replay import base


def rank_of(scores, s):
    order = sorted(range(4), key=lambda q: (-scores[q], q))
    return order.index(s) + 1


def threat_waits(qe):
    """The winning tiles of a seat from its latest discard, or an empty set when it is not tenpai."""
    last = qe[-1]
    if ws.hand_shanten(last['hand_after'], last['meld_tiles'], last['closed']) != 0:
        return set()
    return {base(w) for w in tr.waits(last['hand_after'], last['meld_tiles'], last['closed'])}


def work(g):
    rows = []
    d = json.load(open(g['file']))
    uuid = g['uuid'].split('#')[0]
    hero = g['hero_seat'] if g.get('grp') == 'lj' else None
    for li, log in enumerate(d['log']):
        game = tr.replay(log)
        players = game['players']
        kyoku = game['kyoku']
        inds = game['dora_indicators'][:1]
        dset = frozenset(ws.dora_from_indicator(t) for t in inds)
        blocks = tr.result_blocks(log[-1])
        deltas = tr.result_deltas(log[-1])
        paid = tr.riichi_sticks_paid(log)
        winners = {det[0]: det[1] for _, det in blocks}
        losers = {det[1]: det[0] for _, det in blocks if det[0] != det[1]}
        seat_events = {q: [] for q in range(4)}
        for e in game['events']:
            s = e['seat']
            i = e['index']
            row = None
            if not (e['riichi_seats'][s] is not None and e['riichi_seats'][s] < i):
                row = decision(g, uuid, hero, li, log, game, e, seat_events, dset, inds, winners, losers, deltas, paid)
            if row:
                rows.append(row)
            seat_events[s].append(e)
    return rows


def decision(g, uuid, hero, li, log, game, e, seat_events, dset, inds, winners, losers, deltas, paid):
    s = e['seat']
    i = e['index']
    players = game['players']
    kyoku = game['kyoku']
    if not all(m['kind'] == 'a' for m in players[s]['melds'][:len(e['melds'])]):
        return None
    rseats = [q for q in range(4) if q != s and e['riichi_seats'][q] is not None and e['riichi_seats'][q] < i]
    callers = [q for q in range(4) if q != s and q not in rseats and seat_events[q]
               and any(m['kind'] != 'a' for m in players[q]['melds'][:e['meld_counts'][q]])]
    if not rseats and not callers:
        return None
    hb = e['hand_before']
    opts = {}
    for t in {base(x): x for x in hb}.values():
        rest = list(hb)
        rest.remove(t)
        if ws.hand_shanten(rest, e['meld_tiles'], True) == 0:
            opts[base(t)] = (t, rest)
    if not opts:
        return None
    snap = meld_snapshots(game, i - 1)
    snap[s] = e['melds']
    vis = visible_counter(hb, e, players, snap, inds)
    river = {base(x) for x in e['rivers'][s]}
    my_melds = [{'kind': pm['kind'], 'tiles': list(st), 'called': pm['called']} for pm, st in zip(players[s]['melds'], e['melds'])]
    r_waits = set().union(*[threat_waits(seat_events[q]) for q in rseats]) if rseats else set()
    c_waits = set().union(*[threat_waits(seat_events[q]) for q in callers]) if callers else set()
    out = []
    for b, (t, rest) in opts.items():
        waits = tr.waits(rest, e['meld_tiles'], True)
        sn = vis.copy()
        sn[b] -= 1
        lab_r = [safety(t, q, e, game, sn) for q in rseats]
        lab_c = [safety(t, q, e, game, sn) for q in callers]
        dama = [ron_value(rest, my_melds, w, s, kyoku, dset, riichi=False) or 0 for w in waits]
        rich = [ron_value(rest, my_melds, w, s, kyoku, dset, riichi=True) or 0 for w in waits]
        out.append({
            'b': b, 'live': sum(max(0, 4 - vis[base(w)]) for w in waits), 'kinds': len({base(w) for w in waits}),
            'fur': any(base(w) in river or base(w) == b for w in waits),
            'dama_max': max(dama) if dama else 0, 'dama_min': min(dama) if dama else 0, 'riichi_max': max(rich) if rich else 0,
            'dr': max((DANGER[x] for x in lab_r), default=None), 'lr': max(lab_r, key=lambda x: DANGER[x]) if lab_r else None,
            'dc': max((DANGER[x] for x in lab_c), default=None),
            'on_r': b in r_waits, 'on_c': b in c_waits,
        })
    left = 70 - draws_so_far(game, i)
    main = None
    if callers:
        melds_of = {q: [m for m in players[q]['melds'][:e['meld_counts'][q]] if m['kind'] != 'a'] for q in callers}
        main = max(callers, key=lambda q: (len(melds_of[q]), len(seat_events[q])))
        tells = caller_tells(seat_events[main], len(melds_of[main]))
    return {
        'g': uuid, 'li': li, 'k': kyoku, 's': s,
        'who': ('LuckyJ' if s == hero else 'Tokujou') if g.get('grp') == 'lj' else 'Houou',
        'dl': s == game['dealer'], 't': e['turn'], 'left': left, 'sc': log[1], 'rk': rank_of(log[1], s),
        'nr': len(rseats), 'nc': len(callers),
        'r_turns': [seat_events[q][[x['index'] for x in seat_events[q]].index(e['riichi_seats'][q])]['turn'] for q in rseats],
        'r_dealer': any(q == game['dealer'] for q in rseats),
        'c_melds': max((sum(1 for m in players[q]['melds'][:e['meld_counts'][q]] if m['kind'] != 'a') for q in callers), default=0),
        'riichi_ok': log[1][s] >= 1000 and left >= 4,
        'c_turn': len(seat_events[main]) if main is not None else None,
        'c_main_melds': len(melds_of[main]) if main is not None else 0,
        'c_tells': sum(bool(tells[k]) for k in ('late_call', 'two_calls', 'tsumogiri2')) if main is not None else None,
        'c_dora': sum(1 for m in melds_of[main] for x in m['tiles'] if base(x) in dset or tr.is_red(x)) if main is not None else None,
        'c_tenpai': bool(threat_waits(seat_events[main])) if main is not None else None,
        'was_tenpai': bool(seat_events[s]) and ws.hand_shanten(seat_events[s][-1]['hand_after'], seat_events[s][-1]['meld_tiles'], True) == 0,
        'opts': out, 'cut': base(e['tile']), 'riichi': e['riichi'],
        'later_riichi': players[s]['riichi_event'] is not None and players[s]['riichi_event'] > i,
        'hd': sum(1 for x in list(hb) + list(e['meld_tiles']) if base(x) in dset or tr.is_red(x)),
        'won': s in winners, 'tsumo': winners.get(s) == s, 'dealt': s in losers,
        'dealt_r': losers.get(s) in rseats if s in losers else False,
        'net': deltas[s] - 1000 * paid[s],
    }


if __name__ == '__main__':
    manifest, grp, out = sys.argv[1], sys.argv[2], sys.argv[3]
    m = json.load(open(manifest))
    seen = {}
    for g in m:
        if g['file'] not in seen:
            seen[g['file']] = dict(g, grp=grp)
    games = list(seen.values())
    if '--limit' in sys.argv:
        games = games[:int(sys.argv[sys.argv.index('--limit') + 1])]
    procs = int(sys.argv[sys.argv.index('--procs') + 1]) if '--procs' in sys.argv else 14
    n = 0
    with Pool(procs) as p, open(out, 'w') as f:
        for rows in p.imap_unordered(work, games, chunksize=2):
            for r in rows:
                f.write(json.dumps(r) + '\n')
                n += 1
    print(out, len(games), 'games', n, 'decisions')
