import pandas as pd, json, numpy as np
a = pd.DataFrame(json.load(open('riichi_lj.json'))); a['who'] = np.where(a.lj, 'LuckyJ', 'Tokujou')
b = pd.DataFrame(json.load(open('riichi_houou.json'))); b['who'] = 'Houou'
df = pd.concat([a, b], ignore_index=True)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 300)
SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}
df['safe_look'] = df.labels.map(lambda ls: any(l in SAFE for l in ls))
df['all_safe_look'] = df.labels.map(lambda ls: all(l in SAFE for l in ls))
df['honor_w'] = df.wcls.map(lambda c: 'honor' in c)
df['term_w'] = df.wcls.map(lambda c: any(x in ('honor','term') for x in c))
df['livebin'] = pd.cut(df.live, [-1,2,4,6,8,40], labels=['0-2','3-4','5-6','7-8','9+'])
df['early'] = pd.cut(df.t, [0,6,9,12,30], labels=['1-6','7-9','10-12','13+'])
df['ron'] = df.won & ~df.tsumo
order = ['Tokujou','Houou','LuckyJ']
g = df.groupby('who')
print(g.agg(n=('won','size'), won=('won','mean'), tsumo=('tsumo','mean'), ron=('ron','mean'), dealt=('dealt','mean'), live=('live','mean'), t=('t','mean'),
            opp_tenpai=('opp_tenpai','mean'), opp_1sh=('opp_1sh','mean'), opp_open=('opp_open','mean'), other_riichi=('other_riichi', lambda x: (x>0).mean()),
            safe_look=('safe_look','mean'), term_w=('term_w','mean'), pushes=('pushes','mean'), net=('net','mean')).T[order].round(3))
print('== win% by live x who (no other riichi)')
q = df[df.other_riichi==0]
print(q.groupby(['livebin','who'], observed=True).won.agg(['size','mean']).unstack().round(3))
print('== ron% by live x who (no other riichi)')
print(q.groupby(['livebin','who'], observed=True).ron.mean().unstack()[order].round(3))
print('== tsumo% by live x who')
print(q.groupby(['livebin','who'], observed=True).tsumo.mean().unstack()[order].round(3))
print('== thin waits (3-4 live): win% by safe-looking wait')
th = q[q.live.between(3,4)]
print(th.groupby(['safe_look','who']).won.agg(['size','mean']).unstack().round(3))
print(th.groupby(['term_w','who']).won.agg(['size','mean']).unstack().round(3))
print('== share of thin-wait riichis with a safe-looking or terminal/honor wait')
print(th.groupby('who')[['safe_look','term_w','honor_w']].mean().T[order].round(3))
print('== opponents already tenpai at declaration: win% ')
print(q.groupby(['opp_tenpai','who']).won.agg(['size','mean']).unstack().round(3))
print('== pushes per opponent discard after the declaration')
q = q.assign(push_rate = q.pushes / q.later.replace(0, np.nan))
print(q.groupby('who').push_rate.mean()[order].round(3))
print(q.groupby(['early','who'], observed=True).won.agg(['size','mean']).unstack().round(3))
print('=========== thin vs good waits: table state at declaration')
df['wait'] = np.where(df.live <= 4, 'thin<=4', 'good5+')
print(df.groupby(['wait','who']).agg(n=('won','size'), won=('won','mean'), opp_tenpai=('opp_tenpai','mean'), opp_open=('opp_open','mean'),
       other_riichi=('other_riichi', lambda x: (x>0).mean()), t=('t','mean'), left=('left','mean'), dl=('dl','mean')).round(3))
print('== thin waits, no other riichi: win% by opponents tenpai')
th = df[(df.live<=4) & (df.other_riichi==0)]
print(th.groupby(['opp_tenpai','who']).won.agg(['size','mean']).unstack().round(3))
print('== thin waits, no other riichi, win% by turn')
print(th.groupby(['early','who'], observed=True).won.agg(['size','mean']).unstack().round(3))
print('== thin waits, no other riichi, win% by opp_open')
print(th.groupby(['opp_open','who'], observed=True).won.agg(['size','mean']).unstack().round(3))
