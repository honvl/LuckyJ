import pandas as pd, numpy as np, sys
files = sys.argv[1:] or ['disc_lj.parquet']
df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 300)
order = [w for w in ['Tokujou','Houou','LuckyJ'] if w in df.who.unique()]
q = df[df.closed & (df.nr == 0) & (df.bs >= 1)]
print('== ukeire loss (au < bu at best shanten) share and mean loss, closed quiet, by turn')
q = q.assign(tb=pd.cut(q.t, [0,3,6,9,12,30], labels=['1-3','4-6','7-9','10-12','13+']))
kept = q[q['as'] == q.bs]
print(kept.groupby(['tb','who'], observed=True).apply(lambda x: pd.Series({'n': len(x), 'loss%': 100*(x.au < x.bu).mean(), 'mean loss': (x.bu - x.au).mean(), 'shanten drop%': np.nan})).unstack().round(2))
print('shanten back% by turn'); print(q.groupby(['tb','who'], observed=True).apply(lambda x: 100*(x['as'] > x.bs).mean()).unstack()[order].round(2))
classes = ['value','guest','term','28','mid']
early = q[(q.t <= 6) & (q.mo == 0)]
print('== pairwise: when isolated tiles of class A and B both keep the best shanten, and the cut was one of them: share cutting A')
res = []
for i, A in enumerate(classes):
    for B in classes[i+1:]:
        s = early[(early[f'iso_{A}_keep'] > 0) & (early[f'iso_{B}_keep'] > 0) & early.iso_c.isin([A, B])]
        if len(s) < 200: continue
        r = s.groupby('who').apply(lambda x: pd.Series({'n': len(x), f'cut {A}': 100*(x.iso_c == A).mean()}))
        row = {'pair': f'{A} vs {B}'}
        for w in order:
            if w in r.index:
                row[w] = round(r.loc[w, f'cut {A}'], 1); row[w + ' n'] = int(r.loc[w, 'n'])
        res.append(row)
print(pd.DataFrame(res).to_string(index=False))
