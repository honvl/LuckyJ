import pandas as pd, json, numpy as np
pd.set_option('display.width', 250)
d1 = pd.read_parquet('disc_lj.parquet'); d2 = pd.read_parquet('disc_hou_early.parquet')
df = pd.concat([d1, d2], ignore_index=True)
q = df[df.closed & (df.nr == 0) & (df.bs >= 1) & (df.mo == 0) & (df.t <= 6)]
has_h = (q.iso_value_keep + q.iso_guest_keep) > 0
has_n = (q.iso_term_keep + q['iso_28_keep'] + q.iso_mid_keep) > 0
s = q[has_h & has_n & q.iso_c.notna()].copy()
s['cut_h'] = s.iso_c.isin(['value','guest'])
first = s.sort_values('t').groupby(['g','li','s']).head(1)
hl = pd.DataFrame(json.load(open('hands_lj.json'))); hh = pd.DataFrame(json.load(open('hands_houou.json')))
hands = pd.concat([hl, hh], ignore_index=True)[['game','li','seat','net','won','dealt_in','win_pts','deal_pts']]
hands = hands.rename(columns={'game':'g','seat':'s'})
j = first.merge(hands, on=['g','li','s'], how='inner')
j['bsb'] = j.bs.clip(upper=4)
print(j.groupby(['who','cut_h']).agg(n=('net','size'), net=('net','mean'), won=('won','mean'), dealt=('dealt_in','mean')).round(3))
h = j[j.who != 'LuckyJ']
# stratify by speed and dora to reduce confounding
res = []
for (bsb, hd), x in h.groupby(['bsb', h.hd.clip(upper=2)]):
    a, b = x[x.cut_h].net, x[~x.cut_h].net
    if len(a) > 200 and len(b) > 200:
        res.append((bsb, hd, len(a), len(b), a.mean() - b.mean(), np.sqrt(a.var()/len(a) + b.var()/len(b)),
                    x[x.cut_h].dealt_in.mean() - x[~x.cut_h].dealt_in.mean()))
r = pd.DataFrame(res, columns=['shanten','dora','n_honor','n_number','net diff (honor-number)','se','dealin diff'])
print(r.round(3))
w = r['n_honor'] + r['n_number']
print('weighted net diff', round((r['net diff (honor-number)'] * w).sum() / w.sum()), '+-', round(np.sqrt(((r.se * w) ** 2).sum()) / w.sum()))
