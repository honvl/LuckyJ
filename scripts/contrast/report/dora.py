import pandas as pd, json, numpy as np
rows = [json.loads(l) for l in open('calls_lj.jsonl')]
df = pd.DataFrame(rows); df['who'] = np.where(df.lj, 'LuckyJ', 'Tokujou')
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
def pick(r):
    opts = r['opts']
    if r['took'] and r['took_used'] is not None:
        for o in opts:
            if o['used'] == r['took_used']:
                return o
    imp = [o for o in opts if o['s2'] < r['sh']]
    if not imp: return None
    imp.sort(key=lambda o: (not (o['yak'] or o['route'] == 'yakuhai pon'), o['s2']))
    return imp[0]
df['o'] = df.apply(pick, axis=1); df = df[df.o.notna()]
df['route'] = df.o.map(lambda o: o['route']); df['s2'] = df.o.map(lambda o: o['s2']); df['yak'] = df.o.map(lambda o: o['yak'])
def legal(r):
    if r['route'] == 'yakuhai pon': return True
    if r['s2'] <= 1: return bool(r['yak'])
    return r['route'] in ('tanyao', 'flush')
f = df[df.closed & (df.nr == 0) & (df.s2 < df.sh)]
f = f[f.apply(legal, axis=1)]
f = f.assign(hdb=f.hd.clip(upper=3), shb=f.sh.clip(upper=3), accb=pd.cut(f.acc, [-1,11,19,29,39,200], labels=['<12','12-19','20-29','30-39','40+']))
nf = f[f.route != 'yakuhai pon']
print('== non-yakuhai first calls: call rate by dora held x shanten')
print(nf.groupby(['shb','hdb','who']).took.agg(['size','mean']).unstack().round(3))
print('== by route (tanyao/flush/other) x dora, from 2-shanten')
print(nf[nf.shb == 2].groupby(['route','hdb','who']).took.agg(['size','mean']).unstack().round(3))
