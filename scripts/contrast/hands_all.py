"""Per hand, per seat records (hand_records + outcome) for every game in a manifest (deduplicated by file)."""
import json, sys
from pathlib import Path
from multiprocessing import Pool
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
import review_win_speed as ws

KEEP = ['seat','dealer','round','haipai_shanten','shanten_by_turn','tenpai_turn','first_1sh_turn','riichi_turn','riichi_live',
        'riichi_kinds','riichi_at_first_tenpai','first_call_turn','open','won','tsumo','win_turn','win_value','win_han',
        'dealt_in','deal_in_turn','result_kind','draw_tenpai','turns','tenpai_live','tenpai_kinds','first_closed_tenpai','first_call',
        'haipai_yaochuu','haipai_dora','yakuhai_pair_at_deal','deal_in_into','tenpai_after_riichi','final_shanten','tenpai_first',
        'opponents_tenpai_before']

def work(g):
    out = []
    d = json.load(open(g['file']))
    uuid = g['uuid'].split('#')[0]
    for li, log in enumerate(d['log']):
        recs = ws.hand_records(log, set())
        blocks = tr.result_blocks(log[-1]); paid = tr.riichi_sticks_paid(log); deltas = tr.result_deltas(log[-1])
        for r in recs:
            s = r['seat']
            o = {k: r.get(k) for k in KEEP}
            o.update(game=uuid, li=li, grp=g['grp'], lj=(g['grp'] == 'lj' and s == g['lj_seat']),
                     kyoku=log[0][0], honba=log[0][1], start=log[1][s], net=deltas[s] - 1000 * paid[s], stick=paid[s])
            wp = dp = tp = 0
            for dl, det in blocks:
                if det[0] == s: wp += dl[s]
                elif det[1] == s: dp += dl[s]
                elif det[0] == det[1]: tp += dl[s]
            o.update(win_pts=wp, deal_pts=dp, tsumo_pts=tp, draw_pts=(deltas[s] if not blocks else 0))
            out.append(o)
    return out

if __name__ == '__main__':
    manifest, grp, outp = sys.argv[1], sys.argv[2], sys.argv[3]
    m = json.load(open(manifest))
    seen = {}
    for g in m:
        if g['file'] not in seen:
            seen[g['file']] = dict(g, grp=grp, lj_seat=g['hero_seat'])
    games = list(seen.values())
    with Pool(int(sys.argv[4]) if len(sys.argv) > 4 else 6) as p:
        res = p.map(work, games, chunksize=8)
    rows = [r for c in res for r in c]
    json.dump(rows, open(outp, 'w'))
    print(outp, len(games), len(rows))
