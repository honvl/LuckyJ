import pandas as pd, numpy as np, sys
files = sys.argv[1:] or ['disc_lj.parquet']
df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 300)
order = [w for w in ['Tokujou','Houou','LuckyJ'] if w in df.who.unique()]
q = df[df.closed & (df.nr == 0) & (df.bs >= 1) & (df.mo == 0)]
q = q.assign(speed=pd.cut(q.bs, [0,2,3,9], labels=['1-2 sh','3 sh','4+ sh']), tb=pd.cut(q.t, [0,3,6,9], labels=['1-3','4-6','7-9']))
def pair(A, B, by):
    s = q[(q[f'iso_{A}_keep'] > 0) & (q[f'iso_{B}_keep'] > 0) & q.iso_c.isin([A, B]) & (q.t <= 9)]
    t = s.groupby(by + ['who'], observed=True).apply(lambda x: pd.Series({'n': len(x), 'cutA': 100*(x.iso_c == A).mean()})).unstack()
    return t
honor_vs_num = lambda: None
# honor (value or guest) vs number (term/28/mid), by speed and turn
q['has_h'] = (q.iso_value_keep + q.iso_guest_keep) > 0
q['has_n'] = (q.iso_term_keep + q['iso_28_keep'] + q.iso_mid_keep) > 0
s = q[q.has_h & q.has_n & q.iso_c.notna() & (q.t <= 9)]
s = s.assign(cut_h=s.iso_c.isin(['value','guest']))
print('== isolated honor vs isolated number tile (both keep best shanten): % cutting the honor')
print(s.groupby(['speed','who'], observed=True).cut_h.agg(['size','mean']).unstack().round(3))
print(s.groupby(['tb','who'], observed=True).cut_h.agg(['size','mean']).unstack().round(3))
print(s.groupby(['speed','tb','who'], observed=True).cut_h.mean().unstack().round(3))
# by dora count
print(s.groupby(['hd','who'], observed=True).cut_h.agg(['size','mean']).unstack().round(3).head(4))
print('== guest vs term by speed'); print(pair('guest','term',['speed']).round(1))
print('== value vs 28 by speed'); print(pair('value','28',['speed']).round(1))
print('== guest vs mid by speed'); print(pair('guest','mid',['speed']).round(1))
