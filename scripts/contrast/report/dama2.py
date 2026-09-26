import pandas as pd, json, numpy as np, sys
src = sys.argv[1] if len(sys.argv) > 1 else 'tenpai_lj.jsonl'
rows = [json.loads(l) for l in open(src)]
df = pd.DataFrame(rows)
df['who'] = np.where(df.lj, 'LuckyJ', 'Tokujou') if 'lj' in src else 'Houou'
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
def chosen(r):
    for o in r['opts']:
        if o['b'] == r['cut']:
            return o
df['ch'] = df.apply(chosen, axis=1)
t = df[df.first & df.kept & (df.nr == 0)].copy()
for k in ('live','dama_max','dama_min','fur','shape'):
    t[k] = t.ch.map(lambda o: o[k])
t = t[~t.fur & ~t.dl & (t.dama_min > 0) & t.dama_max.isin([1, 2])]
# what the dama hands became
t['path'] = np.where(t.riichi, 'riichi now', np.where(t.later_riichi, 'riichi later', 'stayed dama'))
print(t.groupby(['who','path']).agg(n=('net','size'), won=('won','mean'), tsumo=('tsumo','mean'), dealt=('dealt','mean'), net=('net','mean')).round(3))
t['lb'] = pd.cut(t.live, [-1,3,6,40], labels=['<=3','4-6','7+'])
t['tb'] = pd.cut(t.t, [0,9,12,30], labels=['1-9','10-12','13+'])
print(t.groupby(['who','lb','riichi'], observed=True).agg(n=('net','size'), won=('won','mean'), dealt=('dealt','mean'), net=('net','mean')).round(3))
print(t.groupby(['who','tb','riichi'], observed=True).agg(n=('net','size'), won=('won','mean'), dealt=('dealt','mean'), net=('net','mean')).round(3))
