import json, sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
m = json.load(open('man/lj_all.json'))
ron = Counter(); tsumo = Counter(); hands = 0; ron_pts = Counter()
for g in m:
    hero = g['hero_seat']
    d = json.load(open(g['file']))
    for log in d['log']:
        hands += 1
        for dl, det in tr.result_blocks(log[-1]):
            w, l = det[0], det[1]
            wt = 'LJ' if w == hero else 'H'
            if w == l:
                tsumo[wt] += 1
            else:
                lt = 'LJ' if l == hero else 'H'
                ron[(wt, lt)] += 1; ron_pts[(wt, lt)] += dl[w]
# ordered pairs per hand: (LJ winner, H loser): 3 pairs; (H, H): 6 pairs; (H, LJ): 3 pairs
pairs = {('LJ','H'): 3, ('H','H'): 6, ('H','LJ'): 3}
for k, npairs in pairs.items():
    print(k, 'rons', ron[k], 'per pair per 100 hands', round(100*ron[k]/(hands*npairs), 3), 'avg', round(ron_pts[k]/max(ron[k],1)))
print('tsumo per 100 hands: LJ', round(100*tsumo['LJ']/hands,2), ' H', round(100*tsumo['H']/(hands*3),2))
print('hands', hands)
