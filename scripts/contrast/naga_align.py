"""NAGA's three heads' discard probabilities for every discard decision of every seat, keyed (g, li, s, t)."""
import json, gzip, sys
from pathlib import Path
from multiprocessing import Pool
TILES = ["1m","2m","3m","4m","5m","6m","7m","8m","9m","1p","2p","3p","4p","5p","6p","7p","8p","9p",
         "1s","2s","3s","4s","5s","6s","7s","8s","9s","E","S","W","N","P","F","C"]
IDX = {t: i for i, t in enumerate(TILES)}; IDX.update({"5mr": 4, "5pr": 13, "5sr": 22})
def code_of(i):
    if i >= 27: return 41 + i - 27
    return (i // 9 + 1) * 10 + i % 9 + 1

def work(g):
    uuid = g['uuid'].split('#')[0]
    j = json.loads(gzip.open(str(Path(__file__).resolve().parents[2] / 'data' / 'report_cache' / f'{uuid}.json.gz')).read())
    out = []
    kk = [k for k in j['pred'] if k and k[0]['info']['msg'].get('type') == 'start_kyoku']
    for li, k in enumerate(kk):
        count = [0, 0, 0, 0]
        msgs = [ev['info']['msg'] for ev in k]
        for n, ev in enumerate(k):
            msg = ev['info']['msg']
            if msg.get('type') not in ('tsumo', 'chi', 'pon') or 'real_dahai' not in msg:
                continue
            a = msg['actor']
            # the actor's next action must be a discard for this to be a discard decision
            nxt = next((m for m in msgs[n + 1:] if m.get('actor') == a and m.get('type') in ('dahai', 'ankan', 'kakan', 'hora', 'reach')), None)
            if nxt is None or nxt['type'] in ('ankan', 'kakan', 'hora'):
                continue
            count[a] += 1
            dp = ev.get('dahai_pred')
            if not dp:
                continue
            # probability of each tile code under each head, in [0,1]
            probs = [[x / 10000 for x in head] for head in dp]
            out.append({'g': uuid, 'li': li, 's': a, 't': count[a], 'real': IDX[msg['real_dahai']],
                        'p': [[round(p, 4) for p in head] for head in probs]})
    return out

if __name__ == '__main__':
    m = json.load(open('man/lj_all.json'))
    with Pool(12) as p:
        res = p.map(work, m, chunksize=4)
    rows = [r for c in res for r in c]
    with open('naga_pred.jsonl', 'w') as f:
        for r in rows: f.write(json.dumps(r) + '\n')
    print(len(rows))
