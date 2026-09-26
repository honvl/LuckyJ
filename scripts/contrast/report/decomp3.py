import pandas as pd, json, numpy as np
a = pd.DataFrame(json.load(open('hands_lj.json'))); a['who'] = np.where(a.lj, 'LuckyJ', 'Tokujou')
b = pd.DataFrame(json.load(open('hands_houou.json'))); b['who'] = 'Houou'
df = pd.concat([a, b], ignore_index=True)
pd.set_option('display.width', 250)
df['s_dealin'] = [ (sb[-1] if (d and sb) else None) for sb, d in zip(df.shanten_by_turn, df.dealt_in)]
df['state'] = df.s_dealin.map(lambda s: None if pd.isna(s) else ('tenpai' if s == 0 else '1-shanten' if s == 1 else '2+ shanten'))
order = ['Tokujou','Houou','LuckyJ']
n = df.groupby('who').size()
t = (df[df.dealt_in].groupby(['who','state','deal_in_into']).size() / n * 100).unstack(0)[order]
print('deal-ins per 100 hands by the dealer-in state x winner type'); print(t.round(2))
c = df[df.dealt_in].groupby(['who','state','deal_in_into']).deal_pts.mean().unstack(0)[order]
print('average cost'); print((-c).round(0))
print('points lost per hand'); print((df[df.dealt_in].groupby(['who','state','deal_in_into']).deal_pts.sum() / n).unstack(0)[order].round(1))
