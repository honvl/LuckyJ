"""Where the han in each player's wins come from, and what happens to dora tiles.  usage: mine_win_value.py MANIFEST SINCE|- LABEL"""
import json, re, sys, datetime
from collections import Counter
sys.path.insert(0, 'scripts')
import review_win_speed as ws, tenhou_replay as tr
from tenhou_replay import base, is_red, is_honor

manifest, since, label = sys.argv[1], (sys.argv[2] if sys.argv[2] != '-' else None), sys.argv[3]
games = json.load(open(manifest))
if since:
    games = [g for g in games if g['start_time'] >= datetime.datetime.strptime(since, '%Y-%m-%d').timestamp()]
FU_RE = re.compile(r"(\d+)符"); HAN_RE = ws.HAN_RE


def yname(entry):
    n = entry.split('(')[0].strip()
    if n.startswith('yaku') and n[4:].isdigit():
        n = ws.TENHOU_YAKU.get(int(n[4:]), n)
    return n


def cat(n):
    if n == 'ドラ': return 'dora'
    if n == '赤ドラ': return 'aka'
    if n == '裏ドラ': return 'ura'
    if n in ('立直', 'ダブル立直'): return 'riichi'
    if n == '一発': return 'ippatsu'
    if n == '門前清自摸和': return 'tsumo'
    if n.startswith('役牌'): return 'yakuhai'
    return 'shape'


wins = []; hands = 0; D = Counter(); riichi_hands = 0; riichi_guaranteed = []
for g in games:
    hero = g['hero_seat']
    for log in tr.load_logs(g['file']):
        hands += 1
        game = tr.replay(log); p = game['players'][hero]
        dset = frozenset(ws.dora_from_indicator(t) for t in game['dora_indicators'][:1])
        isd = lambda t: base(t) in dset or is_red(t)
        entered = sum(1 for t in p['haipai'] if isd(t)) + sum(1 for t in p['draws'] if isinstance(t, int) and isd(t))
        entered += sum(1 for m in p['melds'] if m['kind'] in ('c', 'p', 'm') and isd(m['called']))
        hero_ev = [e for e in game['events'] if e['seat'] == hero]
        D['entered'] += entered; D['hands_with_dora'] += entered > 0
        for e in hero_ev:
            if not isd(e['tile']):
                continue
            threat = any(v is not None for q, v in e['riichi_seats'].items() if q != hero)
            D['cut'] += 1
            if threat:
                D['cut_under_riichi'] += 1
                continue
            sh = ws.hand_shanten(e['hand_after'], e['meld_tiles'], e['closed'])
            D['cut_quiet'] += 1
            D['cut_quiet_turn<=6' if e['turn'] <= 6 else 'cut_quiet_turn>6'] += 1
            D[f'cut_quiet_sh{min(sh, 3)}'] += 1
            D['cut_quiet_aka'] += is_red(e['tile'])
            D['cut_quiet_honor_dora'] += is_honor(e['tile'])
        blocks = tr.result_blocks(log[-1])
        for blk, d in blocks:
            if d[0] != hero:
                continue
            head = d[3] if len(d) > 3 else ''
            fu = int(FU_RE.search(head).group(1)) if FU_RE.search(head) else None
            han = Counter(); names = []
            for entry in d[4:]:
                m = HAN_RE.search(entry); n = yname(entry)
                h = int(m.group(1)) if m else (13 if '役満' in entry else 0)
                if h == 0:
                    continue
                han[cat(n)] += h; names.append(n)
            total = sum(han.values())
            if total == 0:
                m = HAN_RE.search(head)
                total = int(m.group(1)) if m else next((v for k, v in ws.LIMIT_HAN.items() if k in head), 0)
                han['shape'] = total
            open_ = any(m['kind'] != 'a' for m in p['melds'])
            typ = 'riichi' if p['riichi_event'] is not None else 'open' if open_ else 'dama'
            value = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero]
            first = next((m for m in p['melds'] if m['kind'] != 'a'), None)
            fc = None
            if first:
                fc = 'yakuhai pon' if first['kind'] != 'c' and is_honor(first['called']) and base(first['called']) in tr.yakuhai_for(hero, game['kyoku']) else 'chi' if first['kind'] == 'c' else 'other pon'
            # Mahjong Soul writes a 4-han 40-fu mangan as "満貫8000点" with no fu or han in the head.
            mangan = total >= 5 or any(k in head for k in ws.LIMIT_HAN) or (total == 4 and (fu or 30) >= 40) or (total == 3 and (fu or 30) >= 70)
            wins.append(dict(typ=typ, han=han, total=total, fu=fu, tsumo=d[0] == d[1], value=value, names=names, fc=fc, mangan=mangan,
                             haipai_dora=sum(1 for t in p['haipai'] if isd(t)), entered=entered))

n = len(wins)
mean = lambda xs: sum(xs) / len(xs) if xs else 0
print(f"== {label}: {len(games)} games, {hands} hands, {n} wins ({100 * n / hands:.1f}% of hands), mangan+ {100 * sum(w['mangan'] for w in wins) / n:.1f}% of wins = {100 * sum(w['mangan'] for w in wins) / hands:.1f} per 100 hands")
print(f"  han per win {mean([w['total'] for w in wins]):.2f}; actual points per win {mean([w['value'] for w in wins]):.0f}")
print("  han distribution: " + "  ".join(f"{k}: {100 * sum(1 for w in wins if min(w['total'], 5) == k) / n:.1f}%" for k in (1, 2, 3, 4, 5)) + " (5 = 5 or more)")
cats = ['dora', 'aka', 'ura', 'riichi', 'ippatsu', 'tsumo', 'yakuhai', 'shape']
print("  han per win by source: " + "  ".join(f"{c} {mean([w['han'][c] for w in wins]):.2f}" for c in cats))
print("  share of wins carrying: " + "  ".join(f"{c} {100 * sum(1 for w in wins if w['han'][c]) / n:.0f}%" for c in cats))
print("  by hand type:")
for typ in ('riichi', 'dama', 'open'):
    ws_ = [w for w in wins if w['typ'] == typ]
    if not ws_: continue
    line = f"    {typ:<7} n {len(ws_):5d} ({100 * len(ws_) / n:4.1f}% of wins)  points {mean([w['value'] for w in ws_]):5.0f}  han {mean([w['total'] for w in ws_]):.2f}  dora+aka {mean([w['han']['dora'] + w['han']['aka'] for w in ws_]):.2f}  ura {mean([w['han']['ura'] for w in ws_]):.2f}  shape {mean([w['han']['shape'] for w in ws_]):.2f}  yakuhai {mean([w['han']['yakuhai'] for w in ws_]):.2f}  tsumo {100 * mean([w['tsumo'] for w in ws_]):.0f}%  mangan+ {100 * mean([w['mangan'] for w in ws_]):.0f}%"
    if typ == 'riichi':
        guaranteed = [w['total'] - w['han']['ura'] - w['han']['ippatsu'] - w['han']['tsumo'] for w in ws_]
        line += f"  | han sure at declaration {mean(guaranteed):.2f}, riichi-only {100 * sum(1 for x in guaranteed if x <= 1) / len(ws_):.0f}%, luck han after {mean([w['han']['ura'] + w['han']['ippatsu'] + w['han']['tsumo'] for w in ws_]):.2f}"
    print(line)
print("  open wins by first call:")
for fc in ('yakuhai pon', 'chi', 'other pon'):
    ws_ = [w for w in wins if w['fc'] == fc]
    if ws_:
        print(f"    {fc:<12} n {len(ws_):5d} ({100 * len(ws_) / max(1, sum(1 for w in wins if w['typ'] == 'open')):4.1f}% of open wins)  points {mean([w['value'] for w in ws_]):5.0f}  han {mean([w['total'] for w in ws_]):.2f}  dora+aka {mean([w['han']['dora'] + w['han']['aka'] for w in ws_]):.2f}  one-han {100 * sum(1 for w in ws_ if w['total'] == 1) / len(ws_):.0f}%  no dora {100 * sum(1 for w in ws_ if w['han']['dora'] + w['han']['aka'] == 0) / len(ws_):.0f}%")
sh_names = Counter(x for w in wins for x in set(w['names']) if cat(x) == 'shape')
print("  shape yaku, share of wins: " + "  ".join(f"{k} {100 * v / n:.1f}%" for k, v in sh_names.most_common(12)))
closed_ron = [w for w in wins if w['typ'] != 'open' and not w['tsumo'] and w['fu']]
fu_c = Counter(min(w['fu'], 50) for w in closed_ron)
print("  fu of closed ron wins: " + "  ".join(f"{k}: {100 * v / len(closed_ron):.0f}%" for k, v in sorted(fu_c.items())))
print(f"  dora at deal, wins: {mean([w['haipai_dora'] for w in wins]):.2f}; dora that entered the hand, wins: {mean([w['entered'] for w in wins]):.2f}; dora+aka han at win: {mean([w['han']['dora'] + w['han']['aka'] for w in wins]):.2f}")
print(f"  dora flow, all hands: entered {D['entered'] / hands:.2f} per hand; cut {D['cut'] / hands:.2f} per hand = {100 * D['cut'] / D['entered']:.1f}% of entered; of cuts: under a riichi {100 * D['cut_under_riichi'] / D['cut']:.0f}%, quiet table {100 * D['cut_quiet'] / D['cut']:.0f}%")
q = D['cut_quiet']
print(f"    quiet cuts per 100 hands {100 * q / hands:.1f}: turn<=6 {100 * D['cut_quiet_turn<=6'] / q:.0f}%  at tenpai {100 * D['cut_quiet_sh0'] / q:.0f}%  1-sh {100 * D['cut_quiet_sh1'] / q:.0f}%  2-sh {100 * D['cut_quiet_sh2'] / q:.0f}%  3+ {100 * D['cut_quiet_sh3'] / q:.0f}%  red fives {100 * D['cut_quiet_aka'] / q:.0f}%  honor dora {100 * D['cut_quiet_honor_dora'] / q:.0f}%")
print("DONE")
