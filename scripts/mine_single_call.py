"""How a player handles a lone single-meld caller (no riichi on the table).

Safety and acceptance use the table as it stood at that turn (build_personal_guide.safety
and visible_counter), with a called tile counted once.

usage: mine_single_call.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_single_call.py report LABEL ROWS.json [ROWS.json ...] [dump]
Each hero discard while exactly one opponent has exactly one open meld and nobody
has declared riichi is classified by what it cost (nothing / acceptance / shanten)
and whether that cost bought safety against the caller.
"""
import json, os, sys, datetime
from collections import Counter, defaultdict

DANGER = {'genbutsu': 0, 'dead': 0, 'suji': 1, 'quiet-honor': 1, 'live-honor': 2, 'live-terminal': 2, 'live-outer': 3, 'live-middle': 4}
SAFE = 1


def bucket_sh(s): return '0' if s == 0 else '1' if s == 1 else '2' if s == 2 else '3+'
def bucket_turn(t): return '<=8' if t <= 8 else '9-12' if t <= 12 else '13+'
def pct(n, d, w=5): return f"{100 * n / d:{w}.1f}%" if d else ' ' * w + ' -'


def compute(manifest, since, out):
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
    import review_win_speed as ws, tenhou_replay as tr
    from build_personal_guide import DANGER as GDANGER, meld_snapshots, safety, visible_counter
    from tenhou_replay import base, name, names, is_honor
    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, '%Y-%m-%dT%H:%M' if 'T' in since else '%Y-%m-%d').timestamp()
        games = [g for g in games if g['start_time'] >= cutoff]
    rows = []; hands = 0
    for gi, g in enumerate(sorted(games, key=lambda g: g['start_time']), 1):
        hero = g['hero_seat']; tag = f"G{gi} {g['date'][-5:]}"
        for log in tr.load_logs(g['file']):
            hands += 1
            game = tr.replay(log); players = game['players']; kyoku = game['kyoku']
            yk = tr.yakuhai_for(hero, kyoku)
            indicators = game['dora_indicators'][:1]; dora_set = frozenset(ws.dora_from_indicator(t) for t in indicators)
            blocks = tr.result_blocks(log[-1])
            loser_of = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            hero_events = [e for e in game['events'] if e['seat'] == hero]
            last_hero = hero_events[-1]['index'] if hero_events else None
            dealt_to = loser_of.get(hero)
            cost_total = -tr.result_deltas(log[-1])[hero]
            melds_now = {s: [] for s in range(4)}
            call_ev = {}
            seat_events = defaultdict(list)
            for e in game['events']:
                melds_now[e['seat']] = e['melds']
                seat_events[e['seat']].append(e)
                if e['called'] is not None and e['seat'] not in call_ev:
                    call_ev[e['seat']] = e
                if e['seat'] != hero:
                    continue
                if e['riichi_seats'][hero] is not None:
                    continue
                if any(v is not None for q, v in e['riichi_seats'].items() if q != hero):
                    continue

                def open_melds(q):
                    return [m for m in players[q]['melds'][:e['meld_counts'][q]] if m['kind'] != 'a']
                callers = [q for q in range(4) if q != hero and open_melds(q)]
                if len(callers) != 1 or len(open_melds(callers[0])) != 1:
                    continue
                caller = callers[0]
                m = open_melds(caller)[0]
                meld_yaku = m['kind'] != 'c' and is_honor(m['called']) and base(m['called']) in tr.yakuhai_for(caller, kyoku)
                dora_pon = m['kind'] != 'c' and base(m['called']) in dora_set
                ce = call_ev.get(caller)
                after = [x for x in seat_events[caller] if ce is not None and x['index'] > ce['index']]
                ted = sum(1 for x in after if not x['tsumogiri'])
                inside = any(not x['tsumogiri'] and not is_honor(x['tile']) and 3 <= base(x['tile']) % 10 <= 7 for x in after)
                since_call = e['turn'] - (ce['turn'] if ce else e['turn'])

                snap = meld_snapshots(game, e['index'] - 1)
                snap[hero] = e['melds']
                visible = visible_counter(e['hand_before'], e, players, snap, indicators)
                best = ws.best_discard(e['hand_before'], e['meld_tiles'], e['closed'], visible, yk, dora_set)
                best_s, best_u = best['shanten'], best['ukeire']
                cands = {}
                for t in {base(x): x for x in e['hand_before']}.values():
                    rest = list(e['hand_before']); rest.remove(t)
                    s, u, _ = best['by_tile'][base(t)]
                    seen = visible.copy()
                    seen[base(t)] -= 1
                    d = GDANGER[safety(t, caller, e, game, seen)]
                    cands[base(t)] = (s, u, d, t)
                a_s, a_u, a_d, _ = cands[base(e['tile'])]
                eff = [c for c in cands.values() if c[0] == best_s and c[1] == best_u]
                keep = [c for c in cands.values() if c[0] == best_s]
                min_eff_d = min(c[2] for c in eff)
                min_keep_d = min(c[2] for c in keep)
                safe_zero = any(c[2] <= SAFE for c in eff)
                safe_keep = [c for c in keep if c[2] <= SAFE]
                safe_any = [c for c in cands.values() if c[2] <= SAFE]
                if a_s == best_s and a_u == best_u:
                    cls = 'eff-safe' if a_d <= SAFE else 'eff-live'
                elif a_s == best_s:
                    cls = 'paid-ukeire' if a_d < min_eff_d else 'loss-other'
                else:
                    cls = 'dropped-shanten' if a_d < min_keep_d else 'loss-other'
                cat = 'free' if safe_zero else 'costs-ukeire' if safe_keep else 'costs-shanten' if safe_any else 'none'
                cheapest_keep = min((best_u - c[1] for c in safe_keep), default=None)
                cheapest_any = min((c[0] - best_s for c in safe_any), default=None)
                dealt_here = dealt_to is not None and e['index'] == last_hero
                hero_dora = sum(1 for t in list(e['hand_before']) + list(e['meld_tiles']) if base(t) in dora_set or tr.is_red(t))
                rows.append(dict(
                    tag=tag, rnd=game['round_name'], turn=e['turn'], sh=best_s, a_s=a_s, a_u=a_u, best_u=best_u, a_d=a_d,
                    cls=cls, cat=cat, took_safe=a_d <= SAFE, cheapest_keep=cheapest_keep, cheapest_any=cheapest_any,
                    ted=ted, inside=inside, meld_yaku=meld_yaku, dora_pon=dora_pon, since_call=since_call,
                    hero_open=bool(open_melds(hero)), dora=hero_dora, dealt_here=dealt_here,
                    into_caller=dealt_here and dealt_to == caller, cost=cost_total if dealt_here else 0,
                    tile=name(e['tile']), hand=names(e['hand_before']),
                    hero_melds=' / '.join(names(x) for x in e['melds']),
                    caller_meld=names(m['tiles']), caller_river=names(e['rivers'][caller]),
                    safe_opts=', '.join(f"{name(c[3])}(-{c[0]-best_s}sh/-{best_u-c[1]}acc)" for c in safe_any),
                    eff_tiles=', '.join(f"{name(c[3])}(d{c[2]})" for c in eff)))
    json.dump({'games': len(games), 'hands': hands, 'rows': rows}, open(out + '.tmp', 'w'))
    os.replace(out + '.tmp', out)
    print(f"{out}: {len(games)} games, {hands} hands, {len(rows)} rows")


def report(label, files, dump):
    rows = []; games = hands = 0
    for f in files:
        d = json.load(open(f)); rows += d['rows']; games += d['games']; hands += d['hands']
    print(f"== {label}: {games} games, {hands} hands; hero discards vs a lone single-meld caller, no riichi: {len(rows)}")
    SH = ['0', '1', '2', '3+']; TB = ['<=8', '9-12', '13+']

    def line(k, rs):
        n = len(rs)
        if not n:
            return
        c = Counter(r['cls'] for r in rs)
        din = [r['cost'] for r in rs if r['into_caller']]
        live = sum(r['a_d'] >= 2 for r in rs)
        print(f"  {k:<30} n {n:>5}  cut: full-efficiency {pct(c['eff-safe'] + c['eff-live'], n)} (safe tile {pct(c['eff-safe'], n)} live {pct(c['eff-live'], n)})"
              f"  paid acceptance {pct(c['paid-ukeire'], n)}  dropped shanten {pct(c['dropped-shanten'], n)}  other loss {pct(c['loss-other'], n)}"
              f"  live tile {pct(live, n)}  deal-in to caller/100 {100 * len(din) / n:4.2f}  avg cost {sum(din) / len(din) if din else 0:5.0f}")

    def section(title, keyfn, keys, rs=None):
        print(title)
        rs = rows if rs is None else rs
        for k in keys:
            line(k, [r for r in rs if keyfn(r) == k])

    sig = lambda r: f"{'yaku' if r['meld_yaku'] else 'no-yaku'} ted{min(r['ted'], 2)}{'+' if r['ted'] >= 2 else ''}"
    section("-- by hero shanten (best reachable)", lambda r: bucket_sh(r['sh']), SH)
    section("-- by turn", lambda r: bucket_turn(r['turn']), TB)
    section("-- by hero shanten x turn", lambda r: f"{bucket_sh(r['sh'])}-shanten turn {bucket_turn(r['turn'])}", [f"{s}-shanten turn {t}" for s in SH for t in TB])
    section("-- by caller's meld", lambda r: 'yakuhai pon' if r['meld_yaku'] else 'dora pon' if r['dora_pon'] else 'other meld', ['yakuhai pon', 'dora pon', 'other meld'])
    section("-- by caller's tedashi after the call", lambda r: f"tedashi {min(r['ted'], 2)}{'+' if r['ted'] >= 2 else ''}", ['tedashi 0', 'tedashi 1', 'tedashi 2+'])
    section("-- by inside tedashi (3-7 from hand after the call)", lambda r: 'inside tedashi' if r['inside'] else 'no inside tedashi', ['inside tedashi', 'no inside tedashi'])
    section("-- yakuhai pon x tedashi", sig, [f"{y} ted{t}" for y in ('yaku', 'no-yaku') for t in ('0', '1', '2+')])
    section("-- hero closed / open", lambda r: 'hero open' if r['hero_open'] else 'hero closed', ['hero closed', 'hero open'])
    section("-- hero dora", lambda r: f"dora {min(r['dora'], 2)}{'+' if r['dora'] >= 2 else ''}", ['dora 0', 'dora 1', 'dora 2+'])

    print("-- what a safe tile would cost, and whether it was taken")
    for cat in ('free', 'costs-ukeire', 'costs-shanten', 'none'):
        sub = [r for r in rows if r['cat'] == cat]
        n = len(sub)
        if not n:
            continue
        took = sum(r['took_safe'] for r in sub); din = sum(r['into_caller'] for r in sub)
        print(f"  {cat:<14} n {n:>5} ({pct(n, len(rows))})  took a safe tile {pct(took, n)}  deal-in to caller/100 {100 * din / n:4.2f}")
        for s in SH:
            ss = [r for r in sub if bucket_sh(r['sh']) == s]
            if ss:
                print(f"      {s}-shanten     n {len(ss):>5}  took safe {pct(sum(r['took_safe'] for r in ss), len(ss))}  by turn: " +
                      '  '.join(f"{t} {pct(sum(r['took_safe'] for r in ss if bucket_turn(r['turn']) == t), sum(1 for r in ss if bucket_turn(r['turn']) == t))}" for t in TB))
        for s in ('yaku ted0', 'yaku ted1', 'yaku ted2+', 'no-yaku ted0', 'no-yaku ted1', 'no-yaku ted2+'):
            ss = [r for r in sub if sig(r) == s]
            if ss:
                print(f"      {s:<14} n {len(ss):>5}  took safe {pct(sum(r['took_safe'] for r in ss), len(ss))}  deal-in/100 {100 * sum(r['into_caller'] for r in ss) / len(ss):4.2f}")
        for ins in (True, False):
            ss = [r for r in sub if r['inside'] == ins]
            if ss:
                print(f"      {'inside tedashi' if ins else 'no inside ted.':<14} n {len(ss):>5}  took safe {pct(sum(r['took_safe'] for r in ss), len(ss))}  by shanten: " +
                      '  '.join(f"{s} {pct(sum(r['took_safe'] for r in ss if bucket_sh(r['sh']) == s), sum(1 for r in ss if bucket_sh(r['sh']) == s))}" for s in SH))
        if cat == 'costs-ukeire':
            for lo, hi in ((1, 2), (3, 4), (5, 99)):
                ss = [r for r in sub if lo <= r['cheapest_keep'] <= hi]
                if ss:
                    print(f"      cheapest safe keep costs {lo}-{hi if hi < 99 else '+'} acceptance n {len(ss):>5}  took safe {pct(sum(r['took_safe'] for r in ss), len(ss))}")
        if cat == 'costs-shanten':
            for k in (1, 2):
                ss = [r for r in sub if (r['cheapest_any'] == k if k == 1 else r['cheapest_any'] >= k)]
                if ss:
                    print(f"      cheapest safe tile costs {k}{'+' if k == 2 else ''} shanten n {len(ss):>5}  took safe {pct(sum(r['took_safe'] for r in ss), len(ss))}")

    print("-- deal-in to the caller per 100 discards by tile class")
    for d, lab in ((0, 'genbutsu/dead'), (1, 'suji/quiet honor'), (2, 'live honor/terminal'), (3, 'live 2378'), (4, 'live 456')):
        ss = [r for r in rows if r['a_d'] == d]
        if ss:
            late = [r for r in ss if r['turn'] >= 13]
            print(f"  {lab:<20} n {len(ss):>5}  deal-in/100 {100 * sum(r['into_caller'] for r in ss) / len(ss):4.2f}   turn 13+: n {len(late):>4} deal-in/100 {100 * sum(r['into_caller'] for r in late) / max(1, len(late)):4.2f}"
                  f"   inside tedashi: n {sum(1 for r in ss if r['inside']):>4} deal-in/100 {100 * sum(r['into_caller'] for r in ss if r['inside']) / max(1, sum(1 for r in ss if r['inside'])):4.2f}")

    if dump:
        print("-- decisions worth a look")
        for r in rows:
            why = []
            if r['cls'] == 'dropped-shanten':
                why.append('DROPPED SHANTEN for safety')
            if r['a_d'] >= 3 and r['sh'] >= 2 and r['cat'] in ('free', 'costs-ukeire') and (r['ted'] >= 1 or r['turn'] >= 9):
                why.append('live tile at 2+ shanten with a cheap safe tile')
            if r['into_caller']:
                why.append(f"DEALT IN {r['cost']}")
            if why:
                print(f"  {r['tag']} {r['rnd']} T{r['turn']}: {' | '.join(why)}; cut {r['tile']} (danger {r['a_d']}, {r['cls']}), best {r['sh']}-shanten/{r['best_u']} acc, cut leaves {r['a_s']}-shanten/{r['a_u']}"
                      f"; caller meld {r['caller_meld']}{' (yakuhai)' if r['meld_yaku'] else ''}, tedashi after call {r['ted']}{', inside' if r['inside'] else ''}, river {r['caller_river']}")
                print(f"        hand {r['hand']}{'  melds ' + r['hero_melds'] if r['hero_melds'] else ''}; efficiency tiles {r['eff_tiles']}; safe tiles {r['safe_opts'] or 'none'}")


if __name__ == '__main__':
    if sys.argv[1] == 'compute':
        compute(sys.argv[2], None if sys.argv[3] == '-' else sys.argv[3], sys.argv[4])
    else:
        files = [a for a in sys.argv[3:] if a != 'dump']
        report(sys.argv[2], files, 'dump' in sys.argv[3:])
