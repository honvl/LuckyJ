"""Discards made against open callers (nobody in riichi): what each caller really held, and the tenpai dilemmas.

usage: vs_callers.py MANIFEST GROUP OUT_PREFIX [--procs N] [--limit N]

GROUP is "lj" for LuckyJ's games (the hero seat is LuckyJ, the other seats are its Tokujou tablemates),
"self" for your Mahjong Soul games (the hero seat is You, the others Jade), or anything else for a
four-seat human baseline such as the Houou manifest.

Writes OUT_PREFIX.cuts.jsonl    one row per (discard, caller) pair: the tile's safety label against that
                                caller, whether it was on the caller's wait, the caller's calls, discards
                                and tsumogiri run (with the H/T pattern of their discards since their
                                last call and the tiles of the run), the discarder's shanten before
                                this turn's draw (``prev_sh``: the hand with the drawn tile thrown
                                back) and the tile drawn, visible dora, the tiles the caller
                                passed since their last discard, and every candidate tile as [tile,
                                danger against that caller, shanten after, passed]
       OUT_PREFIX.tenpai.jsonl  one row per tenpai decision against callers; ``dilemma`` marks the spots
                                where every widest-wait discard is a live tile and a safe discard keeps a
                                narrower tenpai
"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
import review_win_speed as ws
from build_personal_guide import DANGER, meld_snapshots, safety, visible_counter
from mine_caller_tells import caller_tells
from mine_open_tenpai_push import ron_value
from tenhou_replay import base, is_red, is_honor, is_terminal


def wait_shape(hand13, waits):
    bs = sorted({base(w) for w in waits})
    c = Counter(base(x) for x in hand13)
    if len(bs) >= 3:
        return 'multi'
    if len(bs) == 2:
        a, b = bs
        if a < 41 and a // 10 == b // 10 and b - a == 3:
            return 'ryanmen'
        if c[a] >= 2 and c[b] >= 2:
            return 'shanpon'
        return 'other2'
    b = bs[0]
    if c[b] >= 1 and b >= 41:
        return 'tanki'
    if b < 41:
        n = b % 10; s = b - n
        if c.get(s + n - 1) and c.get(s + n + 1):
            return 'kanchan'
        if (n == 3 and c.get(s + 1) and c.get(s + 2)) or (n == 7 and c.get(s + 8) and c.get(s + 9)):
            return 'penchan'
    return 'tanki'


def caller_profile(q, melds, kyoku):
    """What the caller's open melds show."""
    yak = tr.yakuhai_for(q, kyoku)
    tiles = [base(t) for m in melds for t in m['tiles']]
    kinds = [m['kind'] for m in melds]
    suits = {t // 10 for t in tiles if t < 41}
    yakuhai_pon = any(m['kind'] in ('p', 'm', 'k') and base(m['called']) in yak for m in melds)
    simples = all(t < 41 and t % 10 not in (1, 9) for t in tiles)
    return {
        'yakuhai_pon': yakuhai_pon,
        'all_simples': simples,
        'one_suit': len(suits) <= 1 and not (not suits and yakuhai_pon and False),
        'suit': (next(iter(suits)) if len(suits) == 1 else None),
        'pons': sum(1 for k in kinds if k in ('p', 'm', 'k')),
    }


def work(g):
    cuts, tenpai_rows = [], []
    d = json.load(open(g['file']))
    uuid = g['uuid'].split('#')[0]
    hero = g['hero_seat'] if g.get('grp') in ('lj', 'self') else None
    names = {'lj': ('LuckyJ', 'Tokujou'), 'self': ('You', 'Jade')}.get(g.get('grp'))
    for li, log in enumerate(d['log']):
        game = tr.replay(log)
        players = game['players']; events = game['events']; kyoku = game['kyoku']
        inds = game['dora_indicators'][:1]
        dset = frozenset(ws.dora_from_indicator(t) for t in inds)
        blocks = tr.result_blocks(log[-1])
        ron_by = {}
        for _, det in blocks:
            if det[0] != det[1]:
                ron_by.setdefault(det[1], set()).add(det[0])
        last = len(events) - 1
        deltas = tr.result_deltas(log[-1]); paid = tr.riichi_sticks_paid(log)
        winners = {det[0] for _, det in blocks}
        seat_events = {q: [] for q in range(4)}
        for e in events:
            s = e['seat']; i = e['index']
            riichi_out = any(v is not None for v in e['riichi_seats'].values())
            if not riichi_out:
                melds = {q: [m for m in players[q]['melds'][:e['meld_counts'][q]] if m['kind'] != 'a'] for q in range(4) if q != s}
                callers = [q for q, v in melds.items() if v and seat_events[q]]
                if callers:
                    snap = meld_snapshots(game, i - 1); snap[s] = e['melds']
                    vis = visible_counter(e['hand_before'], e, players, snap, inds)
                    mx = max(len(melds[q]) for q in callers)
                    who = (names[0] if s == hero else names[1]) if names else 'Houou'
                    my_sh = ws.hand_shanten(e['hand_after'], e['meld_tiles'], e['closed'])
                    my_dora = sum(1 for t in list(e['hand_before']) + list(e['meld_tiles']) if base(t) in dset or is_red(t))
                    cinfo = {}
                    for q in callers:
                        qe = seat_events[q]
                        tells = caller_tells(qe, len(melds[q]))
                        last_call = max(x['turn'] for x in qe if x['called'] is not None) if any(x['called'] for x in qe) else None
                        since = [x for x in qe if last_call is not None and x['turn'] > last_call]
                        ts_run = 0
                        for x in reversed(since):
                            if x['tsumogiri']:
                                ts_run += 1
                            else:
                                break
                        pattern = ''.join('T' if x['tsumogiri'] else 'H' for x in since)
                        run_tiles = [base(x['tile']) for x in since[len(since) - ts_run:]]
                        qlast = qe[-1]
                        q_tenpai = ws.hand_shanten(qlast['hand_after'], qlast['meld_tiles'], qlast['closed']) == 0
                        waits = tr.waits(qlast['hand_after'], qlast['meld_tiles'], qlast['closed']) if q_tenpai else []
                        prof = caller_profile(q, melds[q], kyoku)
                        passed = {base(ev['tile']) for ev in events[qe[-1]['index'] + 1: i] if ev['seat'] != q}
                        meld_dora = sum(1 for m in melds[q] for tt in m['tiles'] if base(tt) in dset or is_red(tt))
                        cinfo[q] = dict(tells=tells, last_call=last_call, since=len(since), ts_run=ts_run, q_turn=len(qe),
                                        pattern=pattern, run_tiles=run_tiles,
                                        passed=passed, meld_dora=meld_dora,
                                        tenpai=q_tenpai, waits={base(w) for w in waits},
                                        shape=(wait_shape(qlast['hand_after'], waits) if q_tenpai else None), prof=prof,
                                        n_melds=len(melds[q]), q_dealer=q == game['dealer'])
                    # one row per caller for the tile actually cut
                    t = e['tile']; b = base(t)
                    seen = vis.copy(); seen[b] -= 1
                    cand_sh = {}
                    for tt in {base(x): x for x in e['hand_before']}.values():
                        rest = list(e['hand_before']); rest.remove(tt)
                        cand_sh[base(tt)] = ws.hand_shanten(rest, e['meld_tiles'], e['closed'])
                    best_sh = min(cand_sh.values())
                    # on a draw turn, throwing the drawn tile back leaves the hand as it stood before the draw
                    drew = base(e['drawn']) if e['drawn'] is not None and e['called'] is None else None
                    prev_sh = cand_sh[drew] if drew is not None else None
                    safe_info = {}
                    per_tile = {}
                    for q in callers:
                        dmin_all = dmin_keep = 9
                        per_tile[q] = {}
                        for tt in {base(x): x for x in e['hand_before']}.values():
                            sn = vis.copy(); sn[base(tt)] -= 1
                            dg = DANGER[safety(tt, q, e, game, sn)]
                            per_tile[q][base(tt)] = dg
                            dmin_all = min(dmin_all, dg)
                            if cand_sh[base(tt)] == best_sh:
                                dmin_keep = min(dmin_keep, dg)
                        safe_info[q] = (dmin_all, dmin_keep)
                    # the cut rows describe discards made with nobody in riichi, so a riichi declaration is left
                    # out of them; it stays in the tenpai rows, where declaring is one of the answers
                    for q in (callers if not e['riichi'] else []):
                        ci = cinfo[q]
                        lab = safety(t, q, e, game, seen)
                        cuts.append({
                            'g': uuid, 'li': li, 's': s, 'q': q, 'who': who, 't': e['turn'], 'main': len(melds[q]) == mx,
                            'label': lab, 'danger': DANGER[lab], 'tile': b,
                            'tclass': ('honor' if b >= 41 else 'term' if b % 10 in (1, 9) else '28' if b % 10 in (2, 8) else 'mid'),
                            'yakuhai_for_q': b in tr.yakuhai_for(q, kyoku), 'dora': b in dset,
                            'near_dora': b < 41 and any(x < 41 and x // 10 == b // 10 and abs(x - b) <= 2 for x in dset),
                            'in_q_suit': b < 41 and ci['prof']['suit'] is not None and b // 10 == ci['prof']['suit'],
                            'n_melds': ci['n_melds'], 'last_call': ci['last_call'], 'since': ci['since'], 'ts_run': ci['ts_run'],
                            'q_pattern': ci['pattern'], 'run_tiles': ci['run_tiles'],
                            'q_turn': ci['q_turn'], 'late_call': ci['tells']['late_call'], 'two_calls': ci['tells']['two_calls'],
                            'tsumogiri2': ci['tells']['tsumogiri2'], 'q_tenpai': ci['tenpai'], 'on_wait': b in ci['waits'],
                            'shape': ci['shape'], 'yakuhai_pon': ci['prof']['yakuhai_pon'], 'all_simples': ci['prof']['all_simples'],
                            'one_suit': ci['prof']['suit'] is not None, 'pons': ci['prof']['pons'],
                            'dealt': i == last and q in ron_by.get(s, set()), 'my_sh': my_sh, 'my_dora': my_dora,
                            'best_sh': best_sh, 'held_safe': safe_info[q][0], 'keep_safe': safe_info[q][1],
                            'drew': drew, 'prev_sh': prev_sh, 'tsumogiri': e['tsumogiri'], 'call_turn': e['called'] is not None,
                            'closed': e['closed'],
                            'q_dealer': ci['q_dealer'], 'me_dealer': s == game['dealer'], 'q_meld_dora': ci['meld_dora'],
                            'passed': b in ci['passed'] and DANGER[lab] > 0,
                            'n_callers': len(callers), 'q_ron_value': None, 'q_won': q in winners, 'q_gain': deltas[q], 'my_net': deltas[s] - 1000 * paid[s],
                            'opts': [[k, per_tile[q][k], cand_sh[k], k in ci['passed']] for k in sorted(per_tile[q])],
                            'kyoku': kyoku, 'scores': log[1],
                        })
                    # tenpai dilemmas: can the discarder keep tenpai, and at what price in safety
                    locked = e['riichi_seats'][s] is not None
                    if not locked:
                        opts = {}
                        for tt in {base(x): x for x in e['hand_before']}.values():
                            rest = list(e['hand_before']); rest.remove(tt)
                            if ws.hand_shanten(rest, e['meld_tiles'], e['closed']) == 0:
                                wts = tr.waits(rest, e['meld_tiles'], e['closed'])
                                live = sum(max(0, 4 - vis[base(w)]) for w in wts)
                                sn = vis.copy(); sn[base(tt)] -= 1
                                labs = {q: safety(tt, q, e, game, sn) for q in callers}
                                opts[base(tt)] = {'live': live, 'kinds': len({base(w) for w in wts}),
                                                  'danger': max(DANGER[l] for l in labs.values()),
                                                  'label': max(labs.values(), key=lambda l: DANGER[l]),
                                                  'on_wait_any': any(base(tt) in cinfo[q]['waits'] for q in callers),
                                                  'rest': rest, 'wts': wts}
                        if opts:
                            widest = max(o['live'] for o in opts.values())
                            wide = [k for k, o in opts.items() if o['live'] == widest]
                            safe_opts = [k for k, o in opts.items() if o['danger'] <= 1]
                            chosen = base(e['tile'])
                            my_melds = [{'kind': pm['kind'] if not (pm['kind'] == 'k' and len(st) == 3) else 'p', 'tiles': list(st), 'called': pm['called']}
                                        for pm, st in zip(players[s]['melds'], e['melds'])]

                            def han(k):
                                o = opts[k]
                                hs = [ron_value(o['rest'], my_melds, w, s, kyoku, dset) for w in o['wts']]
                                return max((h or 0) for h in hs) if hs else 0
                            dilemma = all(opts[k]['danger'] >= 2 for k in wide) and any(opts[k]['live'] < widest for k in safe_opts)
                            best_safe = max(safe_opts, key=lambda k: opts[k]['live']) if safe_opts else None
                            row = {
                                'g': uuid, 'li': li, 's': s, 'who': who, 't': e['turn'], 'closed': e['closed'],
                                'widest': widest, 'wide_danger': min(opts[k]['danger'] for k in wide),
                                'wide_label': opts[wide[0]]['label'], 'best_safe_live': opts[best_safe]['live'] if best_safe else None,
                                'dilemma': dilemma, 'n_opts': len(opts), 'wide_tiles': wide, 'safe_tiles': safe_opts, 'chosen_tile': chosen,
                                'chose': ('wide' if chosen in wide else 'safe' if chosen in safe_opts else 'other-tenpai' if chosen in opts else 'broke'),
                                'chosen_live': opts[chosen]['live'] if chosen in opts else None,
                                'wide_on_wait': any(opts[k]['on_wait_any'] for k in wide),
                                'max_melds': mx, 'tells_main': max(sum(bool(cinfo[q]['tells'][k]) for k in ('late_call', 'two_calls', 'tsumogiri2')) for q in callers if len(melds[q]) == mx),
                                'any_caller_tenpai': any(cinfo[q]['tenpai'] for q in callers),
                                'me_dealer': s == game['dealer'],
                                'q_dealer_main': any(cinfo[q]['q_dealer'] for q in callers if len(melds[q]) == mx),
                                'q_turn_main': max(cinfo[q]['q_turn'] for q in callers if len(melds[q]) == mx),
                                'q_meld_dora_main': max(cinfo[q]['meld_dora'] for q in callers if len(melds[q]) == mx),
                                'ts_run_main': max(cinfo[q]['ts_run'] for q in callers if len(melds[q]) == mx),
                                'main_tenpai': any(cinfo[q]['tenpai'] for q in callers if len(melds[q]) == mx),
                                'opts_live': {str(k): [o['live'], o['danger']] for k, o in opts.items()},
                                'riichi': e['riichi'], 'won': s in winners, 'dealt': s in ron_by, 'net': deltas[s] - 1000 * paid[s],
                            }
                            if dilemma:
                                row['wide_han'] = max(han(k) for k in wide)
                                row['safe_han'] = han(best_safe)
                            tenpai_rows.append(row)
            seat_events[s].append(e)
    return cuts, tenpai_rows


if __name__ == '__main__':
    manifest, grp, prefix = sys.argv[1], sys.argv[2], sys.argv[3]
    m = json.load(open(manifest))
    seen = {}
    for g in m:
        if g['file'] not in seen:
            seen[g['file']] = dict(g, grp=grp)
    games = list(seen.values())
    if '--limit' in sys.argv:
        games = games[:int(sys.argv[sys.argv.index('--limit') + 1])]
    procs = int(sys.argv[sys.argv.index('--procs') + 1]) if '--procs' in sys.argv else 14
    nc = nt = 0
    with Pool(procs) as p, open(prefix + '.cuts.jsonl', 'w') as fc, open(prefix + '.tenpai.jsonl', 'w') as ft:
        for cuts, ten in p.imap_unordered(work, games, chunksize=2):
            for r in cuts:
                fc.write(json.dumps(r) + '\n'); nc += 1
            for r in ten:
                ft.write(json.dumps(r) + '\n'); nt += 1
    print(prefix, len(games), 'games', nc, 'cuts', nt, 'tenpai decisions')
