import pandas as pd, json
df = pd.DataFrame(json.load(open('riichi_response.json')))
pd.set_option('display.width', 250)
df = df[(df.other_riichi==0) & (~df.x_open)]
df['sh'] = df.x_shanten.clip(upper=3)
df['early'] = pd.cut(df.r_turn, [0,6,9,12,30])
g = df.groupby(['sh','lj_X'])
print(g.agg(n=('x_won','size'), won=('x_won', lambda x: 100*x.mean()), into_R=('into_R', lambda x: 100*x.mean()), dealt=('dealt_any', lambda x: 100*x.mean()), net=('x_net','mean')).round(1))
print(df.groupby(['early','sh','lj_X'], observed=True).agg(n=('x_won','size'), won=('x_won', lambda x: 100*x.mean()), into_R=('into_R', lambda x: 100*x.mean()), net=('x_net','mean')).round(1))
