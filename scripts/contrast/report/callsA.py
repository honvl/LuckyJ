import pandas as pd, json, numpy as np
rows = [json.loads(l) for l in open('calls_lj.jsonl')]
df = pd.DataFrame(rows)
df['who'] = np.where(df.lj, 'LuckyJ', 'Tokujou')
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 300)
# one option per chance: the option actually taken if called, else the best improving option
def pick(r):
    opts = r['opts']
    if r['took'] and r['took_used'] is not None:
        for o in opts:
            if o['used'] == r['took_used']:
                return o
    imp = [o for o in opts if o['s2'] < r['sh']]
    if not imp:
        return None
    # prefer yaku-legal, then lowest s2
    imp.sort(key=lambda o: (not (o['yak'] or o['route'] == 'yakuhai pon'), o['s2']))
    return imp[0]
df['o'] = df.apply(pick, axis=1)
df = df[df.o.notna()]
df['bt'] = df.o.map(lambda o: o['bt']); df['route'] = df.o.map(lambda o: o['route']); df['s2'] = df.o.map(lambda o: o['s2']); df['yak'] = df.o.map(lambda o: o['yak'])
first = df[df.closed & (df.nr == 0) & (df.s2 < df.sh)]
print('closed, improving chances', first.groupby('who').size().to_dict())
first = first.assign(accb=pd.cut(first.acc, [-1,11,19,29,39,200], labels=['<12','12-19','20-29','30-39','40+']),
                     shb=first.sh.clip(upper=3), tb=pd.cut(first.t, [0,6,12,30], labels=['row1','row2','row3']))
# restrict to chances where the called hand has a yaku path: 1-sh -> tenpai with yaku; 2-sh -> yaku reachable; 3+: yakuhai/tanyao/flush route
def legal(r):
    if r['route'] == 'yakuhai pon': return True
    if r['s2'] == 0: return bool(r['yak'])
    if r['s2'] == 1: return bool(r['yak'])
    return r['route'] in ('tanyao', 'flush')
first = first[first.apply(legal, axis=1)]
print('with a yaku path', first.groupby('who').size().to_dict())
nonyh = first[first.route != 'yakuhai pon']
print('== non-yakuhai calls: call rate by block the call completes, by shanten before')
print(nonyh.groupby(['shb','bt','who']).took.agg(['size','mean']).unstack().round(3))
print('== non-yakuhai calls from 1-2 shanten: by block x closed acceptance')
print(nonyh[nonyh.shb.isin([1,2])].groupby(['shb','accb','bt','who'], observed=True).took.agg(['size','mean']).unstack().round(3))
print('== yakuhai pon by shanten and threat (mo=max opponent melds)')
yh = first[first.route == 'yakuhai pon']
print(yh.groupby(['shb','who']).took.agg(['size','mean']).unstack().round(3))
