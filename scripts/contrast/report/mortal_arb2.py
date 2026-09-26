import pandas as pd, json, numpy as np
pd.set_option('display.width', 250)
m = pd.read_parquet('mortal_disc.parquet')
rows = [json.loads(l) for l in open('tenpai_lj.jsonl')]
t = pd.DataFrame(rows); t['who'] = np.where(t.lj, 'LuckyJ', 'Tokujou')
def chosen(r):
    for o in r['opts']:
        if o['b'] == r['cut']:
            return o
t['ch'] = t.apply(chosen, axis=1)
t = t[t.first & t.kept & (t.nr == 0)].copy()
for k in ('live','dama_max','dama_min','fur'):
    t[k] = t.ch.map(lambda o: o[k])
t = t[~t.fur]
j = t.merge(m[['g','li','s','t','m_reach']], on=['g','li','s','t'], how='inner')
print('tenpai spots with Mortal', len(j))
j['cheap'] = (j.dama_min > 0) & j.dama_max.isin([1,2])
j['yakuless'] = j.dama_max == 0
j['big'] = j.dama_max >= 4
for name, sub in [('cheap 1-2 han with yaku', j[j.cheap]), ('yakuless', j[j.yakuless]), ('4+ han', j[j.big])]:
    print('==', name)
    print(sub.groupby(['who']).agg(n=('riichi','size'), player_riichi=('riichi','mean'), mortal_reach=('m_reach','mean'), mortal_reach_gt_half=('m_reach', lambda x: (x > 0.5).mean())).round(3))
    print(sub.groupby(['who','riichi']).m_reach.agg(['size','mean']).round(3))
