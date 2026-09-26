import pandas as pd, json, numpy as np
a = pd.DataFrame(json.load(open('riichi_lj.json'))); a['who'] = np.where(a.lj, 'LuckyJ', 'Tokujou')
b = pd.DataFrame(json.load(open('riichi_houou.json'))); b['who'] = 'Houou'
df = pd.concat([a, b], ignore_index=True)
w = pd.concat([pd.DataFrame(json.load(open('rw_lj.json'))), pd.DataFrame(json.load(open('rw_houou.json')))], ignore_index=True)
df = df.merge(w[['g','li','R','held','held_max','drawn_later']], on=['g','li','R'])
pd.set_option('display.width', 250)
df['livebin'] = pd.cut(df.live, [-1,2,4,6,8,40], labels=['0-2','3-4','5-6','7-8','9+'])
df['held_share'] = df.held / df.live.replace(0, np.nan)
q = df[df.other_riichi==0]
print(q.groupby(['livebin','who'], observed=True).agg(n=('won','size'), won=('won','mean'), held=('held','mean'), held_share=('held_share','mean'), wall=('live', 'mean')).unstack().round(3))
th = q[q.live<=4]
print(th.groupby(['held','who']).won.agg(['size','mean']).unstack().round(3))
print(th.groupby('who').held.value_counts(normalize=True).unstack().round(3))
