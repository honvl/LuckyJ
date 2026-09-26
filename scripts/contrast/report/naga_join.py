import pandas as pd, json, numpy as np
rows = [json.loads(l) for l in open('naga_pred.jsonl')]
nd = pd.DataFrame({'g': [r['g'] for r in rows], 'li': [r['li'] for r in rows], 's': [r['s'] for r in rows], 't': [r['t'] for r in rows],
                   'real': [r['real'] for r in rows]})
P = np.array([r['p'] for r in rows], dtype=np.float32)  # n x 3 x 34
np.save('naga_P.npy', P)
nd['row'] = np.arange(len(nd))
nd.to_parquet('naga_keys.parquet')
df = pd.read_parquet('disc_lj.parquet')
TO34 = lambda b: (b // 10 - 1) * 9 + b % 10 - 1 if b < 41 else 27 + b - 41
df['tb34'] = df.tb.map(TO34)
m = df.merge(nd, on=['g','li','s','t'], how='left')
print('joined', m.row.notna().mean(), 'real matches', (m.real == m.tb34).mean())
print(m[m.row.notna() & (m.real != m.tb34)][['g','li','s','t','tb','real']].head())
