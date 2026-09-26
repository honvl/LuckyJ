import json, glob
import pandas as pd
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40); pd.set_option('display.max_rows', 200)
def load(grp):
    rows = []
    for f in sorted(glob.glob(f'rows/mine_riichi_folds__{grp}_[0-9]*.json')):
        rows += json.load(open(f))['rows']
    df = pd.DataFrame(rows); df['grp'] = grp
    return df
df = pd.concat([load('lj'), load('opp')])
df['sb'] = df.best.clip(upper=3)
RISK = {"genbutsu": 0.0, "honor 2 seen": 0.3, "suji": 3.3, "nakasuji": 2.9, "virtual nakasuji": 4.0,
        "live honor": 2.8, "live terminal": 6.5, "half suji": 8.5, "live 2-8": 8.5}
df['risk'] = df.cut_class.map(RISK)
df['risk_keep'] = df.best_keep_class.map(RISK)
one = df[df.riichis == 1]
print('== mean risk of cut (expected deal-ins per 100 cuts) vs safest same-shanten tile, single riichi')
print(one.groupby(['sb','grp']).agg(n=('risk','size'), risk=('risk','mean'), risk_keep=('risk_keep','mean'), dealt=('into_riichi', lambda x: 100*x.mean()), nosafe=('any_safe', lambda x: 100*(1-x.mean()))).round(2))
print('== far hands (2+), when a safe tile kept the shanten: what was cut')
far = one[(one.best >= 2) & one.keep_safe]
print((far.groupby(['grp','cut_class']).size() / far.groupby('grp').size()).unstack().mul(100).round(1))
print('== far hands (2+) with no safe tile at all: what was cut')
far2 = one[(one.best >= 2) & ~one.any_safe]
print(far2.groupby('grp').size())
print((far2.groupby(['grp','cut_class']).size() / far2.groupby('grp').size()).unstack().mul(100).round(1))
print('== share of far-hand discards with no safe tile available, by turns since riichi unknown; by turn')
one['tb'] = pd.cut(one.turn, [0,8,12,30])
print(one[one.best>=2].groupby(['tb','grp'], observed=True).agg(n=('any_safe','size'), nosafe=('any_safe', lambda x: 100*(1-x.mean())), push=('push', lambda x: 100*x.mean()), risk=('risk','mean'), dealt=('into_riichi', lambda x: 100*x.mean())).round(2))
print('== dealt-in per 100 far discards split: had safe keep vs not')
print(one[one.best>=2].groupby(['keep_safe','any_safe','grp']).agg(n=('risk','size'), risk=('risk','mean'), dealt=('into_riichi', lambda x: 100*x.mean())).round(2))
