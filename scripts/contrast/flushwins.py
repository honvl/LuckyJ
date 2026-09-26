import json, sys
from pathlib import Path
from collections import Counter
from multiprocessing import Pool
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tenhou_replay as tr
from tenhou_replay import base
def work(g):
    out = Counter()
    d = json.load(open(g['file']))
    for log in d['log']:
        game = tr.replay(log)
        for s in range(4):
            key = 'LuckyJ' if (g['grp'] == 'lj' and s == g['lj_seat']) else ('Tokujou' if g['grp'] == 'lj' else 'Houou')
            out[(key, 'hands')] += 1
        for dl, det in tr.result_blocks(log[-1]):
            w = det[0]
            p = game['players'][w]
            tiles = [base(t) for t in p['hand']] + [base(t) for m in p['melds'] for t in m['tiles']]
            suits = {t // 10 for t in tiles if t < 41}
            key = 'LuckyJ' if (g['grp'] == 'lj' and w == g['lj_seat']) else ('Tokujou' if g['grp'] == 'lj' else 'Houou')
            out[(key, 'wins')] += 1
            if len(suits) == 1:
                out[(key, 'flush')] += 1
                out[(key, 'flush_open' if any(m['kind'] != 'a' for m in p['melds']) else 'flush_closed')] += 1
    return out
if __name__ == '__main__':
    games = []
    for man, grp in (('man/lj_all.json', 'lj'), ('man/houou_games.json', 'houou')):
        for g in json.load(open(man)):
            games.append(dict(g, grp=grp, lj_seat=g['hero_seat']))
    tot = Counter()
    with Pool(4) as p:
        for c in p.imap_unordered(work, games, chunksize=8):
            tot.update(c)
    for k in ('Tokujou', 'Houou', 'LuckyJ'):
        h = tot[(k, 'hands')]
        print(k, 'hands', h, 'wins/100', round(100 * tot[(k, 'wins')] / h, 2), 'flush wins/100', round(100 * tot[(k, 'flush')] / h, 2),
              'open', round(100 * tot[(k, 'flush_open')] / h, 2), 'closed', round(100 * tot[(k, 'flush_closed')] / h, 2))
