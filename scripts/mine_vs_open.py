"""How a player builds when opponents open.  usage: mine_vs_open.py compute MANIFEST SINCE|- OUT.json / report LABEL OUT.json..."""
import json, os, sys, datetime
from collections import Counter, defaultdict

DANGER = {'genbutsu': 0, 'dead': 0, 'suji': 1, 'quiet-honor': 1, 'live-honor': 2, 'live-terminal': 2, 'live-outer': 3, 'live-middle': 4}


def dcls(d): return '0' if d == 0 else '1' if d == 1 else '2+'
def scls(s): return '0' if s == 0 else '1' if s == 1 else '2+'
def mcls(m): return '1' if m == 1 else '2' if m == 2 else '3+'
def pct(n, d, w=5): return f"{100 * n / d:{w}.1f}%" if d else ' ' * w + ' -'


def compute(manifest, since, out):
    sys.path.insert(0, 'scripts')
    import review_win_speed as ws, tenhou_replay as tr
    from build_personal_guide import DANGER as GDANGER, meld_snapshots, safety, visible_counter
    from tenhou_replay import base, is_red, is_honor
    games = json.load(open(manifest))
    if since:
        games = [g for g in games if g['start_time'] >= datetime.datetime.strptime(since, '%Y-%m-%d').timestamp()]
    hands = []; discs = []
    for g in games:
        hero = g['hero_seat']
        for log in tr.load_logs(g['file']):
            game = tr.replay(log); players = game['players']; p = players[hero]
            dset = frozenset(ws.dora_from_indicator(t) for t in game['dora_indicators'][:1])
            isd = lambda t: base(t) in dset or is_red(t)
            hd = sum(1 for t in p['haipai'] if isd(t))
            blocks = tr.result_blocks(log[-1])
            won = any(d[0] == hero for _, d in blocks)
            loser_of = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            dealt_to = loser_of.get(hero)
            value = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero] if won else 0
            hero_ev = [e for e in game['events'] if e['seat'] == hero]
            last_hero = hero_ev[-1]['index'] if hero_ev else None

            def open_count(q, e):
                return sum(1 for m in players[q]['melds'][:e['meld_counts'][q]] if m['kind'] != 'a')
            # opponents' first open call turns (in hero-turn units: the hero's turn count at that moment)
            opp_first = {}
            hero_turn = 0
            for e in game['events']:
                if e['seat'] == hero:
                    hero_turn = e['turn']
                elif e['called'] is not None and e['seat'] not in opp_first:
                    opp_first[e['seat']] = hero_turn
            pressure8 = sum(1 for q, t in opp_first.items() if t <= 8)
            first_open_turn = min(opp_first.values()) if opp_first else None
            hero_first = next((e for e in hero_ev if e['called'] is not None), None)
            hero_call_turn = hero_first['turn'] if hero_first else None
            hero_call_after = hero_first is not None and first_open_turn is not None and first_open_turn < hero_first['turn']
            sh_after_call = ws.hand_shanten(hero_first['hand_after'], hero_first['meld_tiles'], False) if hero_first else None
            kind = None
            if hero_first:
                fm = next(m for m in p['melds'] if m['kind'] != 'a')
                kind = 'chi' if fm['kind'] == 'c' else 'yakuhai pon' if is_honor(fm['called']) and base(fm['called']) in tr.yakuhai_for(hero, game['kyoku']) else 'dora pon' if isd(fm['called']) else 'other pon'
            opened = any(m['kind'] != 'a' for m in p['melds'])
            riichi = p['riichi_event'] is not None
            tenpai = any(ws.hand_shanten(e['hand_after'], e['meld_tiles'], e['closed']) == 0 for e in hero_ev)
            hands.append(dict(hd=hd, pressure8=pressure8, first_open=first_open_turn, opened=opened, call_turn=hero_call_turn,
                              call_after=hero_call_after, sh_call=sh_after_call, kind=kind, riichi=riichi, tenpai=tenpai, won=won,
                              dealt=dealt_to is not None, value=value, hands=1))
            # per-discard pushes against opened opponents, no riichi anywhere
            for e in hero_ev:
                if e['riichi_seats'][hero] is not None or any(v is not None for q, v in e['riichi_seats'].items() if q != hero):
                    continue
                counts = {q: open_count(q, e) for q in range(4) if q != hero}
                mx = max(counts.values())
                if mx == 0:
                    continue
                threats = [q for q, c in counts.items() if c == mx]
                cands = {}
                for t in {base(x): x for x in e['hand_before']}.values():
                    rest = list(e['hand_before']); rest.remove(t)
                    cands[base(t)] = ws.hand_shanten(rest, e['meld_tiles'], e['closed'])
                best_s = min(cands.values()); a_s = cands[base(e['tile'])]
                snap = meld_snapshots(game, e['index'] - 1)
                snap[hero] = e['melds']
                visible = visible_counter(e['hand_before'], e, players, snap, game['dora_indicators'][:1])

                def danger_of(t):
                    seen = visible.copy()
                    seen[base(t)] -= 1
                    return max(GDANGER[safety(t, q, e, game, seen)] for q in threats)
                danger = danger_of(e['tile'])
                # a safe tile that keeps the best shanten?
                safe_keep = any(cands[base(t)] == best_s and danger_of(t) <= 1 for t in {base(x): x for x in e['hand_before']}.values())
                dora_now = sum(1 for t in list(e['hand_before']) + list(e['meld_tiles']) if isd(t))
                dealt_here = dealt_to is not None and e['index'] == last_hero
                discs.append(dict(turn=e['turn'], mx=mx, a_s=a_s, best_s=best_s, danger=danger, safe_keep=safe_keep, dora=dora_now,
                                  hero_open=not e['closed'], dealt=dealt_here, into=dealt_here and dealt_to in threats))
    json.dump({'games': len(games), 'hands': hands, 'discs': discs}, open(out + '.tmp', 'w'))
    os.replace(out + '.tmp', out)
    print(f"{out}: {len(games)} games, {len(hands)} hands, {len(discs)} discards vs opened opponents")


def report(label, files):
    H = []; D = []; games = 0
    for f in files:
        d = json.load(open(f)); H += d['hands']; D += d['discs']; games += d['games']
    print(f"== {label}: {games} games, {len(H)} hands")
    mean = lambda xs: sum(xs) / len(xs) if xs else 0

    def hl(k, rs):
        if not rs: return
        w = [r for r in rs if r['won']]
        print(f"    {k:<26} n {len(rs):5d}  opened {pct(sum(r['opened'] for r in rs), len(rs))}  riichi {pct(sum(r['riichi'] for r in rs), len(rs))}  tenpai {pct(sum(r['tenpai'] for r in rs), len(rs))}  win {pct(len(w), len(rs))}  deal-in {pct(sum(r['dealt'] for r in rs), len(rs))}  win value {mean([r['value'] for r in w]):5.0f}")

    print("-- hands by pressure (opponents opened by your 8th discard) x dora in the deal")
    for pr, plab in ((0, 'nobody opened by T8'), (1, 'one opponent opened'), (2, 'two+ opponents opened')):
        for dc in ('0', '1', '2+'):
            hl(f"{plab}, dora {dc}", [r for r in H if min(r['pressure8'], 2) == pr and dcls(r['hd']) == dc])
    print("-- your own first call when an opponent has already opened vs quiet table, by dora in the deal")
    for dc in ('0', '1', '2+'):
        for lab, cond in (('opponent opened first', lambda r: r['opened'] and r['call_after']), ('you opened first / quiet', lambda r: r['opened'] and not r['call_after'])):
            rs = [r for r in H if dcls(r['hd']) == dc and cond(r)]
            if rs:
                print(f"    dora {dc:<3} {lab:<26} n {len(rs):5d}  call turn {mean([r['call_turn'] for r in rs]):4.1f}  shanten after call {mean([r['sh_call'] for r in rs]):.2f}  landed <=1-shanten {pct(sum(r['sh_call'] <= 1 for r in rs), len(rs))}  win {pct(sum(r['won'] for r in rs), len(rs))}  value {mean([r['value'] for r in rs if r['won']]):5.0f}")
    print("-- what the reaction call is (opponent opened first), by dora in the deal")
    for dc in ('0', '1', '2+'):
        rs = [r for r in H if dcls(r['hd']) == dc and r['opened'] and r['call_after']]
        if rs:
            c = Counter(r['kind'] for r in rs)
            print(f"    dora {dc:<3} n {len(rs):5d}  " + "  ".join(f"{k} {pct(c[k], len(rs))}" for k in ('yakuhai pon', 'chi', 'dora pon', 'other pon')) + f"  tenpai at the call {pct(sum(r['sh_call'] == 0 for r in rs), len(rs))}")
    # call rate given an opponent opened early and hero still closed at that point
    for dc in ('0', '1', '2+'):
        rs = [r for r in H if dcls(r['hd']) == dc and r['first_open'] is not None and r['first_open'] <= 6 and (r['call_turn'] is None or r['call_turn'] > r['first_open'])]
        if rs:
            print(f"    dora {dc:<3} closed when an opponent opened by T6: n {len(rs):5d}  then opened {pct(sum(r['opened'] for r in rs), len(rs))}  riichi {pct(sum(r['riichi'] for r in rs), len(rs))}  win {pct(sum(r['won'] for r in rs), len(rs))}  deal-in {pct(sum(r['dealt'] for r in rs), len(rs))}")
    print("-- discards against opened opponents (no riichi on the table): live tile / dropped shanten / deal-in to them per 100")
    for mc in ('1', '2', '3+'):
        for sc in ('0', '1', '2+'):
            line = f"    vs {mc:<2} meld{'s' if mc != '1' else ' '}, you {sc:<2}-shanten:"
            for dc in ('0', '1', '2+'):
                rs = [r for r in D if mcls(r['mx']) == mc and scls(r['best_s']) == sc and dcls(r['dora']) == dc]
                if rs:
                    live = sum(r['danger'] >= 2 for r in rs); drop = sum(r['a_s'] > r['best_s'] for r in rs); din = sum(r['into'] for r in rs)
                    line += f"  dora {dc}: n {len(rs):5d} live {pct(live, len(rs), 4)} drop {pct(drop, len(rs), 4)} in/100 {100 * din / len(rs):4.2f} |"
            print(line)
    print("-- same, late (turn 9+) and only when a safe tile kept the best shanten (the real choice)")
    for mc in ('1', '2', '3+'):
        for sc in ('0', '1', '2+'):
            line = f"    vs {mc:<2} meld{'s' if mc != '1' else ' '}, you {sc:<2}-shanten:"
            for dc in ('0', '1', '2+'):
                rs = [r for r in D if mcls(r['mx']) == mc and scls(r['best_s']) == sc and dcls(r['dora']) == dc and r['turn'] >= 9 and r['safe_keep']]
                if rs:
                    live = sum(r['danger'] >= 2 for r in rs)
                    line += f"  dora {dc}: n {len(rs):5d} live {pct(live, len(rs), 4)} |"
            print(line)


if __name__ == '__main__':
    if sys.argv[1] == 'compute':
        compute(sys.argv[2], None if sys.argv[3] == '-' else sys.argv[3], sys.argv[4])
    else:
        report(sys.argv[2], sys.argv[3:])
