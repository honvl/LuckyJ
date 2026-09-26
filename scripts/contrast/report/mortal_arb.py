import pandas as pd, json, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
m = pd.read_parquet('mortal_disc.parquet')
df = pd.read_parquet('disc_lj.parquet')
j = df.merge(m, on=['g','li','s','t'], how='inner')
games = j.g.nunique()
print('games with Mortal', games)
j['md'] = j.m_dist.map(lambda s: {int(k): v for k, v in json.loads(s).items()})
j['m_top'] = j.md.map(lambda d: max(d, key=d.get))
j['m_top_honor'] = j.m_top >= 41
j['m_agree'] = j.m_top == j.tb
# (a) early honor vs number spots
q = j[j.closed & (j.nr == 0) & (j.bs >= 1) & (j.mo == 0) & (j.t <= 6)]
has_h = (q.iso_value_keep + q.iso_guest_keep) > 0
has_n = (q.iso_term_keep + q['iso_28_keep'] + q.iso_mid_keep) > 0
s = q[has_h & has_n & q.iso_c.notna()].copy()
s['cut_h'] = s.iso_c.isin(['value','guest'])
print('== (a) early: isolated honor vs isolated number both keep best shanten')
print(s.groupby('who').agg(n=('cut_h','size'), player_cut_honor=('cut_h','mean'), mortal_top_honor=('m_top_honor','mean'), mortal_agree=('m_agree','mean')).round(3))
print('Mortal agreement split by what the player did:')
print(s.groupby(['who','cut_h']).m_agree.agg(['size','mean']).round(3))
# mortal mass on the actual cut when player cut honor vs number
s['m_p_actual'] = [d.get(b, 0) for d, b in zip(s.md, s.tb)]
print(s.groupby(['who','cut_h']).m_p_actual.mean().round(3))
