"""Join Mortal policy rows to the discard table; check alignment."""
import pandas as pd, json, numpy as np
TILES = ["1m","2m","3m","4m","5m","6m","7m","8m","9m","1p","2p","3p","4p","5p","6p","7p","8p","9p",
         "1s","2s","3s","4s","5s","6s","7s","8s","9s","E","S","W","N","P","F","C","5mr","5pr","5sr"]
def to_base_code(a):
    t = TILES[a]
    if t.endswith('r'): t = t[:2]
    if t[0].isdigit():
        return {'m': 10, 'p': 20, 's': 30}[t[1]] + int(t[0])
    return 41 + "ESWNPFC".index(t)
rows = []
with open('mortal_lj.jsonl') as f:
    for line in f:
        r = json.loads(line)
        if r['kind'] != 'discard':
            continue
        p = {int(k): v for k, v in r['p'].items()}
        # collapse to base tile codes (red and plain five together); keep reach prob
        dist = {}
        for a, v in p.items():
            if a <= 36:
                b = to_base_code(a); dist[b] = dist.get(b, 0) + v
        rows.append({'g': r['g'], 'li': r['li'], 's': r['s'], 't': r['n'], 'm_dist': json.dumps(dist), 'm_reach': p.get(37, 0.0),
                     'm_next': r['next'], 'm_next_pai': r['next_pai']})
m = pd.DataFrame(rows)
m.to_parquet('mortal_disc.parquet')
df = pd.read_parquet('disc_lj.parquet')
j = df.merge(m, on=['g','li','s','t'], how='inner')
print('joined rows', len(j), 'of mortal', len(m))
# check: actual tile should be a legal action with nonzero mass (sanity), and next_pai matches
def base_of(p):
    if not isinstance(p, str): return None
    if p[0].isdigit(): return {'m': 10, 'p': 20, 's': 30}[p[1]] + int(p[0])
    return 41 + "ESWNPFC".index(p)
j['np'] = j.m_next_pai.map(base_of)
ok = j[j.m_next == 'dahai']
print('next_pai matches tile:', (ok.np == ok.tb).mean())
