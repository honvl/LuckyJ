import pandas as pd, json, numpy as np
pd.set_option('display.width', 250); pd.set_option('display.max_rows', 200)
def base_of(p):
    if p[0].isdigit(): return {'m': 10, 'p': 20, 's': 30}[p[1]] + int(p[0])
    return 41 + "ESWNPFC".index(p)
mc = []
with open('mortal_lj.jsonl') as f:
    for line in f:
        r = json.loads(line)
        if r['kind'] != 'call': continue
        p = {int(k): v for k, v in r['p'].items()}
        call_p = sum(v for a, v in p.items() if a in (38, 39, 40, 41, 42))
        mc.append({'g': r['g'], 'li': r['li'], 'Y': r['s'], 'X': r['from'], 'tile': base_of(r['pai']), 'm_call': call_p,
                   'm_pass': p.get(45, 0.0), 'm_ron': p.get(43, 0.0), 'm_took': r['took']})
mc = pd.DataFrame(mc)
mc['occ'] = mc.groupby(['g','li','Y','X','tile']).cumcount()
rows = [json.loads(l) for l in open('calls_lj.jsonl')]
c = pd.DataFrame(rows); c['who'] = np.where(c.lj, 'LuckyJ', 'Tokujou')
c['occ'] = c.groupby(['g','li','Y','X','tile']).cumcount()
j = c.merge(mc, on=['g','li','Y','X','tile','occ'], how='inner')
print('call chances matched', len(j), 'games', j.g.nunique())
print('sanity: took vs mortal took', pd.crosstab(j.took, j.m_took.notna()))
def pick(r):
    opts = r['opts']
    if r['took'] and r['took_used'] is not None:
        for o in opts:
            if o['used'] == r['took_used']: return o
    imp = [o for o in opts if o['s2'] < r['sh']]
    if not imp: return None
    imp.sort(key=lambda o: (not (o['yak'] or o['route'] == 'yakuhai pon'), o['s2']))
    return imp[0]
j['o'] = j.apply(pick, axis=1); j = j[j.o.notna()]
j['route'] = j.o.map(lambda o: o['route']); j['s2'] = j.o.map(lambda o: o['s2']); j['yak'] = j.o.map(lambda o: o['yak'])
def legal(r):
    if r['route'] == 'yakuhai pon': return True
    if r['s2'] <= 1: return bool(r['yak'])
    return r['route'] in ('tanyao', 'flush')
f = j[j.closed & (j.nr == 0) & (j.s2 < j.sh)]
f = f[f.apply(legal, axis=1)]
f = f.assign(hdb=f.hd.clip(upper=2), shb=f.sh.clip(upper=3),
             accb=pd.cut(f.acc, [-1,11,19,200], labels=['<12','12-19','20+']))
nf = f[f.route != 'yakuhai pon']
print('== 1-shanten non-yakuhai: call rate (player) vs Mortal call prob, by closed acceptance')
print(nf[nf.shb == 1].groupby(['accb','who'], observed=True).agg(n=('took','size'), player=('took','mean'), mortal=('m_call','mean')).round(3))
f2 = nf[nf.shb == 2].assign(accb2=pd.cut(nf[nf.shb == 2].acc, [-1,23,39,200], labels=['<24','24-39','40+']))
print('== 2-shanten non-yakuhai by acceptance')
print(f2.groupby(['accb2','who'], observed=True).agg(n=('took','size'), player=('took','mean'), mortal=('m_call','mean')).round(3))
print('== 2-shanten non-yakuhai by dora held')
print(nf[nf.shb == 2].groupby(['hdb','who']).agg(n=('took','size'), player=('took','mean'), mortal=('m_call','mean')).round(3))
print('== yakuhai pon')
yh = f[f.route == 'yakuhai pon']
print(yh.groupby(['shb','who']).agg(n=('took','size'), player=('took','mean'), mortal=('m_call','mean')).round(3))
