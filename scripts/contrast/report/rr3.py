import pandas as pd, json
df = pd.DataFrame(json.load(open('riichi_response.json')))
pd.set_option('display.width', 250)
h = df[~df.lj_X & (df.other_riichi == 0)]
print('== human responders: deal-in into the declarer, by who declared')
print(h.groupby('lj_R').agg(n=('into_R','size'), into=('into_R','mean'), won=('x_won','mean')).round(4))
h = h.assign(sh=h.x_shanten.clip(upper=3))
print(h.groupby(['sh','lj_R']).agg(n=('into_R','size'), into=('into_R','mean')).unstack().round(4))
print(h.groupby(['x_open','lj_R']).agg(n=('into_R','size'), into=('into_R','mean')).unstack().round(4))
