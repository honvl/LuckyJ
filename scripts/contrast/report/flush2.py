import pandas as pd, json, glob, numpy as np
pd.set_option('display.width', 250)
def load(grp, who):
    rows = []
    for f in sorted(glob.glob(f'rows/mine_shape_plans__{grp}_[0-9]*.json')):
        rows += json.load(open(f))['rows']
    d = pd.DataFrame(rows); d['who'] = who; return d
df = pd.concat([load('lj','LuckyJ'), load('opp','Tokujou'), load('hou','Houou')], ignore_index=True)
df['net'] = df.value - df.cost
df['fast'] = df.first3_off >= 2
for fit in (9, 10):
    s = df[df.fit >= fit] if fit == 10 else df[df.fit == 9]
    print('fit', fit if fit == 9 else '10+')
    print(s.groupby(['who','value_pair']).fast.agg(['size','mean']).unstack().round(3))
    h = s[s.who != 'LuckyJ']
    for vp in (False, True):
        x = h[h.value_pair == vp]; a, b = x[x.fast].net, x[~x.fast].net
        print('  value pair', vp, 'humans fast - slow net', round(a.mean()-b.mean()), '+-', round(np.sqrt(a.var()/len(a)+b.var()/len(b))), len(a), len(b),
              'won', round(x[x.fast].won.mean(),3), round(x[~x.fast].won.mean(),3))
