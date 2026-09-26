import pandas as pd, json, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 300)
def load(src, who=None):
    rows = [json.loads(l) for l in open(src)]
    d = pd.DataFrame(rows)
    d['who'] = np.where(d.lj, 'LuckyJ', 'Tokujou') if who is None else who
    return d
df = pd.concat([load('tenpai_lj.jsonl'), load('tenpai_hou.jsonl', 'Houou')], ignore_index=True)
def chosen(r):
    for o in r['opts']:
        if o['b'] == r['cut']:
            return o
df['ch'] = df.apply(chosen, axis=1)
t = df[df.first & df.kept & (df.nr == 0)].copy()
for k in ('live','dama_max','dama_min','fur'):
    t[k] = t.ch.map(lambda o: o[k])
t = t[~t.fur]
t['yaku'] = np.where(t.dama_min > 0, 'all', np.where(t.dama_max > 0, 'some', 'none'))
t['han'] = t.dama_max.clip(upper=5)
t['lb'] = pd.cut(t.live, [-1,3,6,40], labels=['<=3','4-6','7+'])
t['tb'] = pd.cut(t.t, [0,9,12,30], labels=['1-9','10-12','13+'])
order = ['Tokujou','Houou','LuckyJ']
print('== declare rate at first closed tenpai (quiet table), child, by han')
c = t[~t.dl]
print(c.groupby(['han','who']).riichi.mean().unstack()[order].round(3))
print(c.groupby(['han','who']).size().unstack()[order])
print('== child, yaku on every wait, 1-2 han, by live')
cc = c[(c.yaku == 'all') & c.dama_max.isin([1,2])]
print(cc.groupby(['lb','who'], observed=True).riichi.mean().unstack()[order].round(3))
print(cc.groupby(['tb','who'], observed=True).riichi.mean().unstack()[order].round(3))
print('== dealer, by han'); d = t[t.dl]
print(d.groupby(['han','who']).riichi.mean().unstack()[order].round(3))
print('== outcomes (net per hand), child cheap yaku hands, by choice')
print(cc.groupby(['who','riichi']).agg(n=('net','size'), net=('net','mean'), won=('won','mean'), dealt=('dealt','mean')).round(3))
print(cc.groupby(['who','lb','riichi'], observed=True).agg(n=('net','size'), net=('net','mean')).unstack().round(0))
# SE of the difference for humans pooled (Tokujou+Houou)
h = cc[cc.who != 'LuckyJ']
for lb in ['<=3','4-6','7+']:
    x = h[(h.lb == lb)]
    a, b = x[x.riichi].net, x[~x.riichi].net
    se = np.sqrt(a.var()/len(a) + b.var()/len(b))
    print(lb, 'humans riichi - dama', round(a.mean()-b.mean()), '+-', round(se), 'n', len(a), len(b))
