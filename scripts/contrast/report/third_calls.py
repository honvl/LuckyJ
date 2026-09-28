"""Chances for a third call (two open melds already) and how three-call hands end.

usage: third_calls.py MANIFEST LABEL (writes third_LABEL.json). Used for chapter 14 of the personal guide.
"""
import json, sys
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tenhou_replay as tr, review_win_speed as ws
from tenhou_replay import base, is_red
from build_personal_guide import meld_snapshots, visible_counter, DANGER, safety
from mine_call_chances import call_options, kuikae
from mine_open_tenpai_push import ron_value
def work(g):
    chances, hands = [], []
    d = json.load(open(g['file'])); hero = g['hero_seat']; left = (hero + 3) % 4
    for li, log in enumerate(d['log']):
        game = tr.replay(log); players = game['players']; kyoku = game['kyoku']
        inds = game['dora_indicators'][:1]; dset = frozenset(ws.dora_from_indicator(t) for t in inds)
        blocks = tr.result_blocks(log[-1])
        won = any(dd[0] == hero for _, dd in blocks)
        dealt = any(len(dd) > 1 and dd[1] == hero and dd[0] != hero for _, dd in blocks)
        net = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero]
        events = game['events']
        n_open = sum(1 for m in players[hero]['melds'] if m['kind'] != 'a')
        mine = [x for x in events if x['seat'] == hero]
        tenpai_end = bool(mine) and ws.hand_shanten(mine[-1]['hand_after'], mine[-1]['meld_tiles'], mine[-1]['closed']) == 0
        third_turn = None
        opened = 0
        for x in mine:
            if x['called'] is not None and x['called']['kind'] in ('c', 'p', 'm'):
                opened += 1
                if opened == 3:
                    third_turn = x['turn']
        hands.append({'n_open': n_open, 'won': won, 'dealt': dealt, 'net': net, 'tenpai_end': tenpai_end, 'third_turn': third_turn,
                      'riichi_seen': any(players[q]['riichi_event'] is not None for q in range(4) if q != hero)})
        for i, e in enumerate(events):
            if e['seat'] == hero or i + 1 >= len(events):
                continue
            prev = [x for x in events[:i] if x['seat'] == hero]
            if not prev:
                continue
            me = prev[-1]
            if me['riichi_seats'][hero] is not None:
                continue
            my_melds = [m for m in players[hero]['melds'][:e['meld_counts'][hero]]]
            if sum(1 for m in my_melds if m['kind'] != 'a') != 2:
                continue
            hand = list(me['hand_after'])
            t = e['tile']; nxt = events[i + 1]
            if nxt['called'] is not None and nxt['seat'] != hero and nxt['called']['src'] == e['seat']:
                continue
            took = nxt['seat'] == hero and nxt['called'] is not None and nxt['called']['src'] == e['seat'] and nxt['called']['kind'] in ('c', 'p', 'm')
            opts = call_options(hand, t, e['seat'] == left)
            if not opts:
                continue
            sh = ws.hand_shanten(hand, me['meld_tiles'], False)
            snap = meld_snapshots(game, i)
            melds_now = [{'kind': m['kind'], 'tiles': list(st), 'called': m['called']} for m, st in zip(my_melds, snap[hero])]
            best = None
            for kind, used in opts:
                rest = list(hand)
                for x in used:
                    rest.remove(x)
                mtiles = sorted(used + [t], key=base)
                bad = kuikae(kind, t, used)
                for dcut in {base(x): x for x in rest}.values():
                    if base(dcut) in bad:
                        continue
                    r4 = list(rest); r4.remove(dcut)
                    s_after = ws.hand_shanten(r4, list(me['meld_tiles']) + mtiles, False)
                    if s_after >= sh:
                        continue
                    han = 0; live = 0
                    if s_after == 0:
                        new = melds_now + [{'kind': kind, 'tiles': mtiles, 'called': t}]
                        waits = tr.waits(r4, list(me['meld_tiles']) + mtiles, False)
                        sn = dict(snap); vis = visible_counter(r4 + [dcut], e, players, sn, inds)
                        live = sum(max(0, 4 - vis[base(w)]) for w in waits)
                        hans = [ron_value(r4, new, w, hero, kyoku, dset) for w in waits]
                        han = max((h for h in hans if h is not None), default=0)
                    cand = (-s_after, han, live)
                    best = max(best, cand) if best else cand
            if best is None:
                continue
            riichi_out = any(e['riichi_seats'][q] is not None and e['riichi_seats'][q] <= i for q in range(4) if q != hero)
            chances.append({'sh': sh, 'sh_after': -best[0], 'han': best[1], 'live': best[2], 'took': took, 'riichi_out': riichi_out,
                            'turn': len(prev) + 1, 'won': won, 'dealt': dealt, 'net': net})
    return chances, hands
if __name__ == '__main__':
    man, label = sys.argv[1], sys.argv[2]
    games = list({g['file']: g for g in json.load(open(man))}.values())
    ch, hs = [], []
    with Pool(14) as p:
        for c, h in p.imap_unordered(work, games, chunksize=2):
            ch += c; hs += h
    json.dump({'chances': ch, 'hands': hs}, open(f'third_{label}.json', 'w'))
    print(label, len(games), 'games', len(ch), 'third-call chances', len(hs), 'hands')
