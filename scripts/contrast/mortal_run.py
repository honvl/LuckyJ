"""Run the local Mortal policy for every seat of every LuckyJ game and record its action probabilities.

usage: mortal_run.py MANIFEST OUT.jsonl [--limit N] [--procs P]
Rows: one per decision the seat faced, keyed (g, li, s, kind, n) where kind is 'discard' (own tsumo or
after own call) or 'call' (another seat's discard), n counts that kind per seat per kyoku.
"""
import gzip, json, os, sys, importlib.util
from multiprocessing import Pool

MJAI_DIR = os.path.expanduser('~/Downloads/mjlog_combined_local_mjai')
MODEL = os.path.expanduser('~/Downloads/mortal_model_policy/model.py')
ENGINE = None


def load_engine():
    import libriichi
    for name in ["mjai", "consts", "dataset", "state", "arena", "stat"]:
        if hasattr(libriichi, name):
            sys.modules[f"libriichi.{name}"] = getattr(libriichi, name)
    spec = importlib.util.spec_from_file_location("mortal_policy_model", MODEL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.get_engine()


def init():
    global ENGINE
    import torch
    torch.set_num_threads(1)
    ENGINE = load_engine()


def probs_of(reaction):
    meta = (reaction or {}).get('meta') or {}
    q = meta.get('q_values') or []
    mask = int(meta.get('mask_bits') or 0)
    legal = [i for i in range(46) if (mask >> i) & 1]
    return {a: round(float(p), 5) for a, p in zip(legal, q)}


def work(g):
    from libriichi.mjai import Bot
    uuid = g['uuid'].split('#')[0]
    log_id = json.load(open(g['file']))['title'][1]
    path = os.path.join(MJAI_DIR, log_id + '.json.gz')
    if not os.path.exists(path):
        return []
    events = [json.loads(l) for l in gzip.open(path, 'rt') if l.strip()]
    out = []
    for seat in range(4):
        bot = Bot(ENGINE, seat)
        li = -1
        ndis = 0; ncall = 0
        for idx, ev in enumerate(events):
            if ev['type'] == 'start_kyoku':
                li += 1; ndis = 0; ncall = 0
            raw = bot.react(json.dumps(ev, ensure_ascii=False), can_act=True)
            if not raw:
                continue
            r = json.loads(raw)
            p = probs_of(r)
            if not p:
                continue
            typ, actor = ev['type'], ev.get('actor')
            if actor == seat and typ in ('tsumo', 'chi', 'pon', 'reach'):
                # a discard decision unless the seat then kans or wins
                nxt = next((e for e in events[idx + 1:] if e.get('actor') == seat), None)
                if typ == 'tsumo' and nxt is not None and nxt['type'] in ('ankan', 'kakan', 'hora'):
                    kind = 'draw_other'
                elif typ == 'reach':
                    kind = 'reach_discard'
                else:
                    kind = 'discard'
                if kind == 'discard':
                    ndis += 1
                out.append({'g': uuid, 'li': li, 's': seat, 'kind': kind, 'n': ndis, 'p': p,
                            'trig': typ, 'next': nxt['type'] if nxt else None,
                            'next_pai': nxt.get('pai') if nxt else None})
            elif typ == 'dahai' and actor != seat:
                ncall += 1
                nxt = events[idx + 1] if idx + 1 < len(events) else None
                took = nxt is not None and nxt.get('actor') == seat and nxt['type'] in ('chi', 'pon', 'daiminkan', 'hora')
                out.append({'g': uuid, 'li': li, 's': seat, 'kind': 'call', 'n': ncall, 'p': p, 'trig': typ,
                            'from': actor, 'pai': ev['pai'], 'took': nxt['type'] if took else None,
                            'consumed': nxt.get('consumed') if took else None})
    return out


if __name__ == '__main__':
    manifest, outp = sys.argv[1], sys.argv[2]
    m = json.load(open(manifest))
    if '--limit' in sys.argv:
        m = m[:int(sys.argv[sys.argv.index('--limit') + 1])]
    procs = int(sys.argv[sys.argv.index('--procs') + 1]) if '--procs' in sys.argv else 4
    n = 0
    with Pool(procs, initializer=init) as pool, open(outp, 'w') as f:
        for rows in pool.imap_unordered(work, m, chunksize=1):
            for r in rows:
                f.write(json.dumps(r) + '\n'); n += 1
    print(outp, n)
