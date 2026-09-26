import pandas as pd, json, glob, numpy as np
pd.set_option('display.width', 250)
def load(grp, who):
    rows = []
    for f in sorted(glob.glob(f'rows/mine_call_chances__{grp}_[0-9]*.json')):
        rows += json.load(open(f))['rows']
    d = pd.DataFrame(rows); d['who'] = who; return d
df = pd.concat([load('lj','LuckyJ'), load('opp','Tokujou'), load('hou','Houou')], ignore_index=True)
q = df[(df['from'] == 1) & ~df.riichi_out]
q = q.assign(accb=pd.cut(q.acc, [-1,11,19,200], labels=['<12','12-19','20+']), hanb=q.open_han.clip(upper=3))
print(q.groupby(['accb','hanb','who'], observed=True).took.agg(['size','mean']).unstack().round(3))
# outcomes by called vs passed for 1-shanten <12 (first chance) pooled humans
f = q[q['first']]
print(f.groupby(['accb','who','took'], observed=True).agg(n=('net','size'), net=('net','mean'), won=('won','mean'), dealt=('dealt','mean')).round(3))
h = f[f.who != 'LuckyJ']
for a in ['<12','12-19','20+']:
    x = h[h.accb == a]; c, p = x[x.took].net, x[~x.took].net
    print(a, 'humans call - pass net', round(c.mean()-p.mean()), '+-', round(np.sqrt(c.var()/len(c)+p.var()/len(p))), len(c), len(p))
q2 = df[(df['from'] == 2) & ~df.riichi_out & (df.route == 'tanyao')]
q2 = q2.assign(db=q2.dora.clip(upper=2))
print(q2.groupby(['db','who']).took.agg(['size','mean']).unstack().round(3))
f2 = q2[q2['first']]
h2 = f2[f2.who != 'LuckyJ']
for dd in (0, 1, 2):
    x = h2[h2.db == dd]; c, p = x[x.took].net, x[~x.took].net
    print('tanyao 2sh dora', dd, 'humans call - pass net', round(c.mean()-p.mean()), '+-', round(np.sqrt(c.var()/len(c)+p.var()/len(p))), len(c), len(p))
