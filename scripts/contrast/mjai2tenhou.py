"""Convert Tenhou mjai logs (one JSON event per line, gzipped) into tenhou.net/6 games.

usage: mjai2tenhou.py OUTDIR MANIFEST.json FILE [FILE ...]
Each game is replayed and its scores reconciled hand to hand before it is written.
The manifest lists every game four times, once per seat as hero.
"""
import gzip, json, sys, os
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from naga_to_tenhou import code, meld_token, verify, TSUMOGIRI, BAKAZE
import tenhou_replay as tr


def convert_game(events):
    logs = []
    names = None
    cur = None
    for ev in events:
        t = ev['type']
        if t == 'start_game':
            names = ev.get('names')
        elif t == 'start_kyoku':
            cur = {
                'header': [BAKAZE[ev['bakaze']] + ev['kyoku'] - 1, ev['honba'], ev['kyotaku']],
                'scores': list(ev['scores']), 'dora': [code(ev['dora_marker'])], 'ura': [],
                'haipai': [[code(x) for x in h] for h in ev['tehais']],
                'draws': [[] for _ in range(4)], 'discards': [[] for _ in range(4)],
                'reach': set(), 'result': None, 'drawn': 0,
            }
        elif cur is None:
            continue
        elif t == 'tsumo':
            cur['draws'][ev['actor']].append(code(ev['pai']))
            cur['drawn'] += 1
        elif t == 'dahai':
            a = ev['actor']
            tile = TSUMOGIRI if ev['tsumogiri'] else code(ev['pai'])
            if a in cur['reach']:
                cur['discards'][a].append(f'r{tile}')
                cur['reach'].discard(a)
            else:
                cur['discards'][a].append(tile)
        elif t == 'reach':
            cur['reach'].add(ev['actor'])
        elif t == 'chi':
            cur['draws'][ev['actor']].append(meld_token('c', ev['actor'], ev['target'], ev['pai'], ev['consumed']))
        elif t == 'pon':
            cur['draws'][ev['actor']].append(meld_token('p', ev['actor'], ev['target'], ev['pai'], ev['consumed']))
        elif t == 'daiminkan':
            cur['draws'][ev['actor']].append(meld_token('m', ev['actor'], ev['target'], ev['pai'], ev['consumed']))
            cur['discards'][ev['actor']].append(0)
        elif t == 'kakan':
            cur['discards'][ev['actor']].append(''.join(f'{code(x):02d}' for x in ev['consumed']) + 'k' + f"{code(ev['pai']):02d}")
        elif t == 'ankan':
            tiles = [f'{code(x):02d}' for x in ev['consumed']]
            cur['discards'][ev['actor']].append(''.join(tiles[:3]) + 'a' + tiles[3])
        elif t == 'dora':
            cur['dora'].append(code(ev['dora_marker']))
        elif t == 'hora':
            if cur['result'] is None:
                cur['result'] = ['和了']
            if ev.get('ura_markers') and not cur['ura']:
                cur['ura'] = [code(x) for x in ev['ura_markers']]
            cur['result'].extend([list(ev['deltas']), [ev['actor'], ev['target'], ev['actor'], '']])
        elif t == 'ryukyoku':
            label = '流局' if cur['drawn'] >= 70 - 0 else '途中流局'
            cur['result'] = [label, list(ev.get('deltas') or [0, 0, 0, 0])]
        elif t == 'end_kyoku':
            log = [cur['header'], cur['scores'], cur['dora'], cur['ura']]
            for s in range(4):
                log.extend([cur['haipai'][s], cur['draws'][s], cur['discards'][s]])
            log.append(cur['result'] or ['流局', [0, 0, 0, 0]])
            logs.append(log)
            cur = None
    return names, logs


def work(path):
    try:
        events = [json.loads(l) for l in gzip.open(path, 'rt')]
        names, logs = convert_game(events)
        if not logs:
            return None, 'no logs'
        err = verify(logs, None)
        if err:
            return None, err
        base = os.path.basename(path).replace('.json.gz', '')
        return {'id': base, 'names': names, 'logs': logs}, None
    except Exception as exc:
        return None, f'{type(exc).__name__}: {exc}'


if __name__ == '__main__':
    outdir, manifest_path = sys.argv[1], sys.argv[2]
    files = sys.argv[3:]
    os.makedirs(outdir, exist_ok=True)
    man, errs = [], []
    with Pool(14) as p:
        for res, err in p.imap_unordered(work, files, chunksize=4):
            if err:
                errs.append(err)
                continue
            fn = os.path.join(outdir, res['id'] + '.json')
            json.dump({'title': ['', res['id']], 'name': res['names'], 'rule': {'aka': 1}, 'log': res['logs']},
                      open(fn, 'w'), ensure_ascii=False)
            st = int(datetime.strptime(res['id'][:10], '%Y%m%d%H').timestamp())
            for s in range(4):
                man.append({'uuid': f"{res['id']}#s{s}", 'start_time': st, 'date': res['id'][:10], 'mode': 'tenhou-houou',
                            'hero_seat': s, 'hero_name': (res['names'] or ['?'] * 4)[s], 'names': res['names'], 'file': fn})
    json.dump(man, open(manifest_path, 'w'))
    print('games', len(man) // 4, 'errors', len(errs))
    from collections import Counter
    print(Counter(e.split(':')[0][:60] for e in errs).most_common(8))
