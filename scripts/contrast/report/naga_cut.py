import pandas as pd, json, numpy as np
df = pd.read_parquet('disc_lj.parquet')
nd = pd.read_parquet('naga_keys.parquet'); P = np.load('naga_P.npy')
df = df.merge(nd[['g','li','s','t','row']], on=['g','li','s','t'], how='left')
TO34 = lambda b: (b // 10 - 1) * 9 + b % 10 - 1 if b < 41 else 27 + b - 41
pd.set_option('display.width', 250)
q = df[df.closed & (df.nr == 0) & (df.bs >= 1) & (df.mo == 0) & (df.t <= 6)].copy()
# need the actual isolated tiles per class: recompute from hand is not stored; use NAGA mass on class via chosen tile only.
# Approach: for decisions where the actor cut an isolated tile of class A while class B was also available, ask NAGA (mean of heads)
# how much probability it puts on the chosen tile vs the 'best' alternative is unknown without tiles; so instead measure NAGA's top choice class.
Pm = P.mean(axis=1)  # n x 34
top = Pm.argmax(axis=1)
def cls34(i, yak):
    if i >= 27:
        return None
    n = i % 9 + 1
    return 'term' if n in (1, 9) else '28' if n in (2, 8) else 'mid'
q['naga_top'] = [top[int(r)] for r in q.row]
q['naga_agree'] = q.naga_top == q.tb.map(TO34)
q['naga_top_honor'] = q.naga_top >= 27
has_h = (q.iso_value_keep + q.iso_guest_keep) > 0
has_n = (q.iso_term_keep + q['iso_28_keep'] + q.iso_mid_keep) > 0
s = q[has_h & has_n & q.iso_c.notna()].copy()
s['cut_h'] = s.iso_c.isin(['value','guest'])
print('== honor vs number (both isolated, both keep best shanten), turns 1-6 quiet')
print(s.groupby('who').agg(n=('cut_h','size'), player_cut_honor=('cut_h','mean'), naga_top_honor=('naga_top_honor','mean'), naga_agree=('naga_agree','mean')).round(3))
print('NAGA agreement when the player cut the honor vs the number tile:')
print(s.groupby(['who','cut_h']).naga_agree.agg(['size','mean']).round(3))
