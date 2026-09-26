"""At every riichi declaration, what each other seat holds: shanten, safe tiles against the declarer, and how the hand ends."""
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
    for li, log in enumerate(d['log']):
        game = tr.replay(log)
        ev = game['events']; players = game['players']
        blocks = tr.result_blocks(log[-1])
        deltas = tr.result_deltas(log[-1]); paid = tr.riichi_sticks_paid(log)
        winners = {}
        for dl, det in blocks:
            winners[det[0]] = det[1]
        loser_to = {det[1]: det[0] for dl, det in blocks if det[0] != det[1]}
        dset = frozenset(ws.dora_from_indicator(t) for t in game['dora_indicators'][:1])
        for e in ev:
            if not e['riichi']:
                continue
            R = e['seat']; idx = e['index']
            hands = concealed_hands(game, idx + 1)
            snap = meld_snapshots(game, idx)
            rivers = {s: list(e['rivers'][s]) for s in range(4)}
            rivers[R] = rivers[R] + [e['tile']]
            rseats = dict(e['riichi_seats']); rseats[R] = idx
            pe = {'rivers': rivers, 'riichi_seats': rseats, 'index': idx + 1}
            left = 70 - draws_so_far(game, idx)
            for X in range(4):
                if X == R:
                    continue
                if rseats[X] is not None and rseats[X] < idx:
                    continue  # already in riichi
                hand = hands[X]
                if len(hand) + len(snap[X]) * 3 < 13 - 0:
                    pass
                meld_tiles = [t for m in snap[X] for t in m[:3]]
                closed = not snap[X] or all(len(m) == 4 and False for m in snap[X])
                closed = len(players[X]['melds'][:len(snap[X])]) == 0 or all(m['kind'] == 'a' for m in players[X]['melds'][:len(snap[X])])
                sh = ws.hand_shanten(hand, meld_tiles, closed)
                vis = visible_counter(hand, pe, players, snap, game['dora_indicators'][:1])
                labels = []
                for t in hand:
                    seen = vis.copy(); seen[base(t)] -= 1
                    labels.append(safety(t, R, pe, game, seen))
                c = Counter(labels)
                # outcome
                x_events = [q for q in ev if q['seat'] == X and q['index'] > idx]
                dealt = loser_to.get(X)
                into_R = dealt == R
                dealt_state = None
                if dealt is not None and x_events:
                    last = x_events[-1]
                    dealt_state = ws.hand_shanten(last['hand_after'], last['meld_tiles'], last['closed'])
                # first reply
                first = x_events[0] if x_events else None
                first_lab = None
                if first is not None:
                    snap1 = meld_snapshots(game, first['index'] - 1); snap1[X] = first['melds']
                    vis1 = visible_counter(first['hand_before'], first, players, snap1, game['dora_indicators'][:1])
                    seen1 = vis1.copy(); seen1[base(first['tile'])] -= 1
                    first_lab = safety(first['tile'], R, first, game, seen1)
                out.append({
                    'game': g['uuid'].split('#')[0], 'li': li, 'kyoku': game['kyoku'], 'X': X, 'R': R,
                    'lj_X': X == g['hero_seat'], 'lj_R': R == g['hero_seat'],
                    'x_dealer': X == game['dealer'], 'r_dealer': R == game['dealer'],
                    'r_turn': e['turn'], 'left': left, 'x_turn': sum(1 for q in ev[:idx+1] if q['seat'] == X),
                    'x_open': not closed, 'x_melds': len(snap[X]), 'x_shanten': sh,
                    'x_dora': sum(1 for t in list(hand) + meld_tiles if base(t) in dset or is_red(t)),
                    'n_gen': c['genbutsu'] + c['dead'], 'n_safe': sum(v for k, v in c.items() if k in SAFE),
                    'n_honor2': c['honor, 2 seen'], 'n_suji': c['suji'] + c['nakasuji'],
                    'other_riichi': sum(1 for s in range(4) if s not in (X, R) and rseats[s] is not None and rseats[s] < idx),
                    'x_riichi_later': players[X]['riichi_event'] is not None,
                    'dealt_any': dealt is not None, 'into_R': into_R, 'dealt_state': dealt_state,
                    'x_won': X in winners, 'r_won': R in winners, 'kind': log[-1][0],
                    'x_net': deltas[X] - 1000 * paid[X], 'first_lab': first_lab,
                    'first_tsumogiri': first['tsumogiri'] if first else None,
                })
    return out

if __name__ == '__main__':
    m = json.load(open('man/lj_all.json'))
    with Pool(8) as p:
        res = p.map(work, m, chunksize=4)
    rows = [r for c in res for r in c]
    json.dump(rows, open('riichi_response.json', 'w'))
    print(len(rows))
