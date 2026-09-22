"""Do the outcomes follow the hand's value?  usage: mine_value_choice.py MANIFEST SINCE|- LABEL"""
import json, re, sys, datetime
from collections import Counter, defaultdict
sys.path.insert(0, 'scripts')
import review_win_speed as ws, tenhou_replay as tr
from tenhou_replay import base, is_red, is_honor

manifest, since, label = sys.argv[1], (sys.argv[2] if sys.argv[2] != '-' else None), sys.argv[3]
games = json.load(open(manifest))
if since:
    games = [g for g in games if g['start_time'] >= datetime.datetime.strptime(since, '%Y-%m-%d').timestamp()]
FU_RE = re.compile(r"(\d+)符"); HAN_RE = ws.HAN_RE
LIMIT = ('満貫', '跳満', '倍満', '三倍満', '役満')


def yname(entry):
    n = entry.split('(')[0].strip()
    if n.startswith('yaku') and n[4:].isdigit():
        n = ws.TENHOU_YAKU.get(int(n[4:]), n)
    return n


rows = []; heads4 = Counter()
for g in games:
    hero = g['hero_seat']
    for log in tr.load_logs(g['file']):
        game = tr.replay(log); p = game['players'][hero]
        dset = frozenset(ws.dora_from_indicator(t) for t in game['dora_indicators'][:1])
        isd = lambda t: base(t) in dset or is_red(t)
        haipai_dora = sum(1 for t in p['haipai'] if isd(t))
        draws = [t for t in p['draws'] if isinstance(t, int)]
        dora6 = haipai_dora + sum(1 for t in draws[:6] if isd(t))
        counts = Counter(base(t) for t in p['haipai'])
        honors = sum(v for k, v in counts.items() if k >= 41)
        suit_max = max(sum(v for k, v in counts.items() if s <= k < s + 10) for s in (10, 20, 30))
        honitsu_shape = suit_max + honors >= 9
        hero_ev = [e for e in game['events'] if e['seat'] == hero]
        opened = any(m['kind'] != 'a' for m in p['melds'])
        riichi = p['riichi_event'] is not None
        tenpai = any(ws.hand_shanten(e['hand_after'], e['meld_tiles'], e['closed']) == 0 for e in hero_ev)
        blocks = tr.result_blocks(log[-1])
        won = any(d[0] == hero for _, d in blocks)
        dealt = any(d[1] == hero and d[0] != hero for _, d in blocks)
        value = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero] if won else 0
        total = 0; fu = None; names = []; mangan = False
        if won:
            d = next(d for _, d in blocks if d[0] == hero); head = d[3] if len(d) > 3 else ''
            fu = int(FU_RE.search(head).group(1)) if FU_RE.search(head) else None
            for entry in d[4:]:
                m = HAN_RE.search(entry); h = int(m.group(1)) if m else 0
                if h:
                    total += h; names.append(yname(entry))
            if total == 0:
                m = HAN_RE.search(head); total = int(m.group(1)) if m else next((v for k, v in ws.LIMIT_HAN.items() if k in head), 0)
            mangan = total >= 5 or any(k in head for k in LIMIT) or (total == 4 and (fu or 0) >= 40) or (total == 3 and (fu or 0) >= 70)
            if total == 4:
                heads4[head] += 1
        # first call = yakuhai pon: dora in hand at the pon
        first = next((m for m in p['melds'] if m['kind'] != 'a'), None)
        ypon = None
        if first and first['kind'] != 'c' and is_honor(first['called']) and base(first['called']) in tr.yakuhai_for(hero, game['kyoku']):
            ce = next((e for e in hero_ev if e['called'] is not None), None)
            if ce:
                ypon = sum(1 for t in list(ce['hand_after']) + list(ce['meld_tiles']) if isd(t))
        rows.append(dict(hd=haipai_dora, d6=dora6, hon=honitsu_shape, opened=opened, riichi=riichi, tenpai=tenpai, won=won, dealt=dealt,
                         value=value, total=total, mangan=mangan, honitsu=any(x in ('混一色', '清一色') for x in names), ypon=ypon,
                         tanyao='断幺九' in names))
n = len(rows)
print(f"== {label}: {len(games)} games, {n} hands; wins {100 * sum(r['won'] for r in rows) / n:.1f}%, mangan+ {100 * sum(r['mangan'] for r in rows) / max(1, sum(r['won'] for r in rows)):.1f}% of wins = {100 * sum(r['mangan'] for r in rows) / n:.2f} per 100 hands")
print("  4-han win heads:", dict(heads4.most_common(6)))


def table(title, keyfn, keys):
    print(title)
    for k in keys:
        rs = [r for r in rows if keyfn(r) == k]
        if not rs: continue
        w = [r for r in rs if r['won']]
        print(f"    {k:<10} n {len(rs):5d} ({100 * len(rs) / n:4.1f}%)  tenpai {100 * sum(r['tenpai'] for r in rs) / len(rs):4.1f}%  riichi {100 * sum(r['riichi'] for r in rs) / len(rs):4.1f}%  opened {100 * sum(r['opened'] for r in rs) / len(rs):4.1f}%  win {100 * len(w) / len(rs):4.1f}%  deal-in {100 * sum(r['dealt'] for r in rs) / len(rs):4.1f}%  win value {sum(r['value'] for r in w) / max(1, len(w)):5.0f}  han {sum(r['total'] for r in w) / max(1, len(w)):.2f}  mangan+/100 hands {100 * sum(r['mangan'] for r in rs) / len(rs):.1f}  share of all wins {100 * len(w) / max(1, sum(r['won'] for r in rows)):4.1f}%")


table("  by dora at the deal (dora + red)", lambda r: str(min(r['hd'], 3)) + ('+' if r['hd'] >= 3 else ''), ['0', '1', '2', '3+'])
for lab, cond in (("no dora at the deal", lambda r: r['hd'] == 0), ("one or more dora at the deal", lambda r: r['hd'] >= 1)):
    rs_ = [r for r in rows if cond(r)]
    print(f"    {lab:<30} n {len(rs_):5d}  mangan+ wins {sum(r['mangan'] for r in rs_):4d} = {100 * sum(r['mangan'] for r in rs_) / max(1, len(rs_)):.2f} per 100 of these hands  win {100 * sum(r['won'] for r in rs_) / max(1, len(rs_)):.1f}%")
table("  by dora in hand by the 6th draw", lambda r: str(min(r['d6'], 3)) + ('+' if r['d6'] >= 3 else ''), ['0', '1', '2', '3+'])
table("  honitsu-shaped deal (one suit + honors >= 9 of 13)", lambda r: 'yes' if r['hon'] else 'no', ['yes', 'no'])
hon = [r for r in rows if r['hon']]
print(f"    honitsu-shaped deals won with honitsu/chinitsu: {100 * sum(r['honitsu'] for r in hon) / max(1, len(hon)):.1f}% of those deals; all honitsu wins per 100 hands {100 * sum(r['honitsu'] for r in rows) / n:.2f}; tanyao wins per 100 hands {100 * sum(r['tanyao'] for r in rows) / n:.2f}")
yp = [r for r in rows if r['ypon'] is not None]
print(f"  first call = yakuhai pon: {len(yp)} hands ({100 * len(yp) / n:.1f}% of hands)")
for k in ('0', '1', '2+'):
    rs = [r for r in yp if (str(r['ypon']) if r['ypon'] < 2 else '2+') == k]
    if rs:
        w = [r for r in rs if r['won']]
        print(f"    dora at the pon {k:<3} n {len(rs):5d} ({100 * len(rs) / len(yp):4.1f}%)  win {100 * len(w) / len(rs):4.1f}%  deal-in {100 * sum(r['dealt'] for r in rs) / len(rs):4.1f}%  win value {sum(r['value'] for r in w) / max(1, len(w)):5.0f}  han {sum(r['total'] for r in w) / max(1, len(w)):.2f}")
print("DONE")
