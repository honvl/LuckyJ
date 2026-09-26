import pandas as pd, numpy as np
df = pd.read_parquet('disc_lj.parquet')
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}
q = df[(df.nr == 0) & (df.mo > 0) & df.os_a.notna()].copy()
q['live'] = ~q.os_a.isin(SAFE)
q['safe_avail'] = q.os_min_best.isin(SAFE)
q['shb'] = q['as'].clip(upper=2).map({0: 'tenpai', 1: '1-sh', 2: '2+'})
q['tb'] = pd.cut(q.t, [0, 6, 9, 12, 30], labels=['1-6', '7-9', '10-12', '13+'])
s = q[q.safe_avail]
print('== live cut rate when a safe tile kept the same shanten, by max opponent melds x own state')
print(s.groupby(['mo', 'shb', 'who']).live.agg(['size', 'mean']).unstack().round(3))
print('== by turn x state (vs 2+ melds)')
print(s[s.mo >= 2].groupby(['tb', 'shb', 'who'], observed=True).live.mean().unstack().round(3))
# what class of live tile, when cutting live
lv = q[q.live]
lv = lv.assign(cls=lv.tc.map(lambda c: 'honor' if c in ('value', 'guest') else c))
print('== class of the live tile cut against callers (share)')
print((lv.groupby(['who', 'cls']).size() / lv.groupby('who').size()).unstack().round(3))
print(lv.groupby(['who', 'os_a']).size().unstack(0).div(lv.groupby('who').size()).round(3))
