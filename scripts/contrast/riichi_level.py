"""One row per riichi declaration: the wait, how it looks to the table, the table's state, and the result.

usage: riichi_level.py MANIFEST GROUP OUT.json
"""
import json, sys
from pathlib import Path
from collections import Counter
from multiprocessing import Pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
import review_win_speed as ws
from build_personal_guide import safety, meld_snapshots, concealed_hands, visible_counter, draws_so_far
from tenhou_replay import base, is_red

SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}


def work(g):
    out = []
    d = json.load(open(g['file']))
    uuid = g['uuid'].split('#')[0]
    for li, log in enumerate(d['log']):
        game = tr.replay(log)
        ev = game['events']; players = game['players']
        inds = game['dora_indicators'][:1]
        blocks = tr.result_blocks(log[-1]); deltas = tr.result_deltas(log[-1]); paid = tr.riichi_sticks_paid(log)
        win_from = {det[0]: det[1] for _, det in blocks}
        for e in ev:
            if not e['riichi']:
                continue
            R = e['seat']; idx = e['index']
            hand = e['hand_after']
            waits = tr.waits(hand, e['meld_tiles'], True)
            snap = meld_snapshots(game, idx)
            rivers = {s: list(e['rivers'][s]) for s in range(4)}
            rivers[R] = rivers[R] + [e['tile']]
            rseats = dict(e['riichi_seats']); rseats[R] = idx
            pe = {'rivers': rivers, 'riichi_seats': rseats, 'index': idx + 1}
            vis_R = visible_counter(hand, pe, players, snap, inds)
            live = sum(max(0, 4 - vis_R[base(w)]) for w in waits)
            # how each wait tile looks to an opponent: label from the public information only
            pub = Counter()
            for s in range(4):
                for t in rivers[s]:
                    pub[base(t)] += 1
                for tiles in snap[s]:
                    for t in tiles:
                        pub[base(t)] += 1
            for t in inds:
                pub[base(t)] += 1
            labels = [safety(w, R, pe, game, pub) for w in waits]
            wcls = []
            for w in waits:
                b = base(w)
                wcls.append('honor' if b >= 41 else 'term' if b % 10 in (1, 9) else '28' if b % 10 in (2, 8) else 'mid')
            hands = concealed_hands(game, idx + 1)
            opp_sh = []
            opp_open = 0
            for X in range(4):
                if X == R:
                    continue
                mt = [t for m in snap[X] for t in m[:3]]
                closed = all(m['kind'] == 'a' for m in players[X]['melds'][:len(snap[X])])
                opp_sh.append(ws.hand_shanten(hands[X], mt, closed))
                opp_open += (not closed)
            # opponents' discards after the declaration: how many were unsafe against R
            pushes = 0; later = 0
            for q in ev[idx + 1:]:
                if q['seat'] == R:
                    continue
                later += 1
                sn = meld_snapshots(game, q['index'] - 1); sn[q['seat']] = q['melds']
                vv = visible_counter(q['hand_before'], q, players, sn, inds)
                seen = vv.copy(); seen[base(q['tile'])] -= 1
                if safety(q['tile'], R, q, game, seen) not in SAFE:
                    pushes += 1
            won = R in win_from
            out.append({
                'g': uuid, 'li': li, 'grp': g['grp'], 'lj': g['grp'] == 'lj' and R == g['lj_seat'],
                'R': R, 'dl': R == game['dealer'], 't': e['turn'], 'left': 70 - draws_so_far(game, idx),
                'live': live, 'kinds': len({base(w) for w in waits}), 'labels': labels, 'wcls': wcls,
                'decl_label': None,
                'opp_tenpai': sum(1 for x in opp_sh if x == 0), 'opp_1sh': sum(1 for x in opp_sh if x == 1),
                'opp_open': opp_open, 'other_riichi': sum(1 for s in range(4) if s != R and e['riichi_seats'][s] is not None),
                'won': won, 'tsumo': won and win_from[R] == R, 'ron_from_lj': won and g['grp'] == 'lj' and win_from[R] == g['lj_seat'],
                'dealt': any(det[1] == R and det[0] != R for _, det in blocks), 'kind': log[-1][0],
                'net': deltas[R] - 1000 * paid[R], 'pushes': pushes, 'later': later,
                'hd': sum(1 for t in hand if base(t) in {ws.dora_from_indicator(x) for x in inds} or is_red(t)),
            })
    return out


if __name__ == '__main__':
    manifest, grp, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    m = json.load(open(manifest))
    seen = {}
    for g in m:
        if g['file'] not in seen:
            seen[g['file']] = dict(g, grp=grp, lj_seat=g['hero_seat'])
    games = list(seen.values())
    procs = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    with Pool(procs) as p:
        res = p.map(work, games, chunksize=4)
    rows = [r for c in res for r in c]
    json.dump(rows, open(outp, 'w'))
    print(outp, len(games), len(rows))
