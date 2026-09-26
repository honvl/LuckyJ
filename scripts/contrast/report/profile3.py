import pandas as pd, json, numpy as np
a = pd.DataFrame(json.load(open('hands_lj.json')))
a['who'] = np.where(a.lj, 'LuckyJ', 'Tokujou')
b = pd.DataFrame(json.load(open('hands_houou.json'))); b['who'] = 'Houou'
df = pd.concat([a, b], ignore_index=True)
df['riichi'] = df.riichi_turn.notna()
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
def s_at(r):
    sb = r['shanten_by_turn']
    return sb[-1] if r['dealt_in'] and sb else None
df['s_dealin'] = df.apply(s_at, axis=1)
order = ['Tokujou','Houou','LuckyJ']
def summ(x):
    n = len(x)
    return pd.Series({
        'hands': n, 'net': x.net.mean(), 'win%': 100*x.won.mean(), 'avg win': x.loc[x.won,'win_pts'].mean(),
        'dealin%': 100*x.dealt_in.mean(), 'avg dealin': -x.loc[x.dealt_in,'deal_pts'].mean(),
        'dealin tenpai': 100*(x.dealt_in & (x.s_dealin==0)).mean(),
        'dealin 1sh': 100*(x.dealt_in & (x.s_dealin==1)).mean(),
        'dealin 2+': 100*(x.dealt_in & (x.s_dealin>=2)).mean(),
        'riichi%': 100*x.riichi.mean(), 'open%': 100*x.open.mean(),
        'ever tenpai%': 100*x.tenpai_turn.notna().mean(),
        'win|tenpai%': 100*x.loc[x.tenpai_turn.notna(),'won'].mean(),
        'riichi win%': 100*x.loc[x.riichi,'won'].mean(),
        'open win%': 100*x.loc[x.open,'won'].mean(),
        'open dealin%': 100*x.loc[x.open,'dealt_in'].mean(),
        'draw tenpai%': 100*x.loc[x.result_kind=='流局','draw_tenpai'].mean(),
    })
t = df.groupby('who').apply(summ).T[order]
print(t.round(2))
print(df.groupby(['dealer','who']).apply(summ).T.round(2))
