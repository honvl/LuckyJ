"""Standard errors and n for the headline rates cited in the write-up."""
import pandas as pd, json, glob, numpy as np
def load_rf(grp):
    rows = []
    for f in sorted(glob.glob(f'rows/mine_riichi_folds__{grp}_[0-9]*.json')):
        rows += json.load(open(f))['rows']
    return pd.DataFrame(rows)
out = {}
for grp, who in (('lj','LuckyJ'), ('opp','Tokujou'), ('hou','Houou')):
    d = load_rf(grp)
    d['sb'] = d.best.clip(upper=3)
    for s in (0, 1, 2, 3):
        x = d[d.sb == s]
        p = x.push.mean(); n = len(x)
        di = x.dealt.mean()
        out[(who, f'push_{s}')] = (round(100*p, 1), round(100*np.sqrt(p*(1-p)/n), 1), n)
        out[(who, f'dealin100_{s}')] = (round(100*di, 2), round(100*np.sqrt(di*(1-di)/n), 2), n)
    far = d[(d.best >= 2)]
    early = far[far.turn <= 8]
    p = early.push.mean(); out[(who, 'push_far_early')] = (round(100*p,1), round(100*np.sqrt(p*(1-p)/len(early)),1), len(early))
    ks = far[far.keep_safe]
    p = ks.push.mean(); out[(who, 'push_far_free_fold')] = (round(100*p,1), round(100*np.sqrt(p*(1-p)/len(ks)),1), len(ks))
for k, v in sorted(out.items()):
    print(k, v)
