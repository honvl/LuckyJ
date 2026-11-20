#!/usr/bin/env python3
"""Rank Mortal checkpoints by play: each challenger takes one seat against three copies of a common champion.

libriichi's ``OneVsThree`` arena deals every seed four times, the challenger in each seat, under Tenhou hanchan rules.
All challengers meet the same champion on the same seeds, so the difference between two challengers is paired by deal.
Work is cut into chunks of seeds; each chunk and challenger is one row of OUT.jsonl:

    {"challenger", "champion", "seed", "seeds", "rankings": [firsts, seconds, thirds, fourths]}

A challenger as strong as the champion averages rank 2.5. Rerunning continues where the file stops.

    .venv/bin/python scripts/mortal_duel.py OUT.jsonl --champion policy --challenger NAME=CHECKPOINT ... \\
        [--seeds 2000] [--chunk 10] [--procs 12]
    .venv/bin/python scripts/mortal_duel.py OUT.jsonl --report

``policy`` in place of a checkpoint path is the local policy model. Engines are built in ``mortal_engines.py``.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

SEED_START = 10_000
SEED_KEY = 0x4C75636B794A  # fixed, so every run and every challenger sees the same deals
ENGINES = {}
SPECS = {}
PTS = np.array([90, 45, 0, -135])


def init(specs):
    global SPECS
    SPECS = specs


def engine_for(name):
    if name not in ENGINES:
        import mortal_engines
        ENGINES[name] = mortal_engines.engine(SPECS[name], name=name, quick_eval=True)
    return ENGINES[name]


def work(job):
    import libriichi
    challenger, champion, seed, count = job
    env = libriichi.arena.OneVsThree(disable_progress_bar=True, log_dir=None)
    rankings = env.py_vs_py(challenger=engine_for(challenger), champion=engine_for("champion:" + champion),
                            seed_start=(seed, SEED_KEY), seed_count=count)
    return {"challenger": challenger, "champion": champion, "seed": seed, "seeds": count,
            "rankings": [int(x) for x in rankings]}


def report(path):
    rows = [json.loads(l) for l in open(path) if l.strip()]
    by = defaultdict(dict)
    for r in rows:
        by[r["challenger"]][r["seed"]] = np.array(r["rankings"], float)
    rng = np.random.default_rng(0)

    def stats(mat):  # mat: chunks x 4 counts
        tot = mat.sum(0)
        return tot @ np.arange(1, 5) / tot.sum(), tot @ PTS / tot.sum()

    def ci(mats, fn, reps=2000):  # bootstrap over seed chunks
        n = len(mats[0])
        draws = [fn(*[m[idx] for m in mats]) for idx in (rng.integers(0, n, n) for _ in range(reps))]
        return np.percentile(draws, [2.5, 97.5])

    out = {"champion": rows[0]["champion"] if rows else None, "challengers": {}, "paired": []}
    for name, d in by.items():
        mat = np.array([d[s] for s in sorted(d)])
        rank, pt = stats(mat)
        lo, hi = ci([mat], lambda m: stats(m)[0])
        plo, phi = ci([mat], lambda m: stats(m)[1])
        out["challengers"][name] = {"hanchan": int(mat.sum()), "rates": [round(float(x), 4) for x in mat.sum(0) / mat.sum()],
                                    "avg_rank": round(float(rank), 4), "avg_rank_ci": [round(float(lo), 4), round(float(hi), 4)],
                                    "avg_pt": round(float(pt), 2), "avg_pt_ci": [round(float(plo), 2), round(float(phi), 2)]}
    names = sorted(by)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            common = sorted(set(by[a]) & set(by[b]))
            if len(common) < 5:
                continue
            ma, mb = np.array([by[a][s] for s in common]), np.array([by[b][s] for s in common])
            diff = lambda x, y: stats(x)[0] - stats(y)[0]  # noqa: E731
            lo, hi = ci([ma, mb], diff)
            out["paired"].append({"a": a, "b": b, "hanchan_each": int(ma.sum()),
                                  "avg_rank_a_minus_b": round(float(diff(ma, mb)), 4),
                                  "ci": [round(float(lo), 4), round(float(hi), 4)]})
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    out_path = args.pop(0)
    if "--report" in args:
        report(out_path)
        sys.exit()
    opt = {"--seeds": 2000, "--chunk": 10, "--procs": 12}
    champion, challengers = "policy", {}
    i = 0
    while i < len(args):
        if args[i] in opt:
            opt[args[i]] = int(args[i + 1])
        elif args[i] == "--champion":
            champion = args[i + 1]
        elif args[i] == "--challenger":
            name, spec = args[i + 1].split("=", 1)
            challengers[name] = spec
        i += 2
    specs = {**challengers, "champion:" + champion: champion}
    done = set()
    if os.path.exists(out_path):
        done = {(r["challenger"], r["seed"]) for r in map(json.loads, open(out_path))}
    # chunk by chunk, every challenger on the same seeds before moving on
    jobs = [(name, champion, seed, opt["--chunk"])
            for seed in range(SEED_START, SEED_START + opt["--seeds"], opt["--chunk"])
            for name in challengers if (name, seed) not in done]
    n = 0
    with Pool(opt["--procs"], initializer=init, initargs=(specs,)) as pool, open(out_path, "a") as f:
        for row in pool.imap(work, jobs, chunksize=1):
            f.write(json.dumps(row) + "\n")
            f.flush()
            n += 1
            if n % 20 == 0:
                print(n, "of", len(jobs), "chunks", flush=True)
    print(out_path, n, "chunks")
