import pandas as pd, json, sys
src, dst, grp = sys.argv[1], sys.argv[2], sys.argv[3]
rows = []
with open(src) as f:
    for line in f:
        r = json.loads(line)
        iso = r.pop('iso')
        for c in ('value','guest','term','28','mid'):
            v = iso.get(c)
            r[f'iso_{c}_n'] = v['n'] if v else 0
            r[f'iso_{c}_keep'] = v['keep_best'] if v else 0
            r[f'iso_{c}_loss'] = v['loss'] if v else None
        rows.append(r)
df = pd.DataFrame(rows)
df['grp'] = grp
if grp == 'lj':
    df['who'] = df['lj'].map({True: 'LuckyJ', False: 'Tokujou'})
else:
    df['who'] = 'Houou'
df.to_parquet(dst)
print(dst, df.shape)
