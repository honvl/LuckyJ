#!/usr/bin/env python3
"""How LuckyJ picks the tile it folds with: danger models of every tile a player could throw into a lone riichi.

At every discard into a lone riichi by a player not in riichi, at the user's tables and LuckyJ's, each tile the player
holds that is not genbutsu and not dead becomes one row, described from that player's seat:

- its neighbourhood in its suit, four ranks either side: copies visible, genbutsu (the riichi's river and the tiles
  passed since the declaration), the riichi player's own discards there before the declaration (early or late, from
  the hand or the draw, the declaration tile itself), and the dora;
- the suit as a whole: the riichi player's discards in it and in the other suits, and how many of their last three
  hand-discards before the declaration were in it;
- an honor's kind (dragon, the round wind, the riichi player's seat wind) and copies visible;
- the timing (the declaration turn, the turns since) and the tile's safety label (``build_personal_guide.safety``);
- the ways it can still be a winning tile that is not furiten, counted from the unseen copies: two-sided
  (ryanmen), closed (kanchan), edge (penchan), pair (shanpon) and single (tanki); and the copies the player holds;

with whether it was one of the riichi's winning tiles (from the declarer's real hand), whether it was the tile thrown,
the decision it belongs to, who held it (LuckyJ, a human at its tables, the user, a human at the user's tables),
whether the riichi was LuckyJ's or the user's, and two kinds of fold: no genbutsu in hand and not tenpai after the
discard (``fold_no_genbutsu``, which also takes in 1-shanten pushes), and of those the real folds, where the discard
left the hand further from tenpai than the best discard would have (``real_fold``).

Three models, each cross-fitted by game (every fifth of the games scored by a model trained on the other four):
``net`` a small network (PyTorch), ``gbm`` LightGBM, ``tabpfn`` TabPFN-3.5 on a CUDA host. ``report`` compares each
side's thrown tile with each model's safest tile, by side and kind of tile, checks a checklist of readable cues (a
logistic over them, the same folds), and tabulates the cues' danger over every candidate.

usage: mine_fold_model.py compute YOUR_MANIFEST.json OUT.npz
       mine_fold_model.py net DATA.npz PRED.npz
       mine_fold_model.py gbm DATA.npz PRED.npz                                      (needs lightgbm)
       mine_fold_model.py tabpfn DATA.npz PRED.npz [CONTEXT BAGS ESTIMATORS BATCH]   (TabPFN-3.5, CUDA)
       mine_fold_model.py report DATA.npz OUT.json NAME=PRED.npz ...                 (the first NAME is the reference)
"""

from __future__ import annotations

import json
import os
import sys
import zlib
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
LABELS = ("suji", "nakasuji", "virtual nakasuji", "honor, 2 seen", "live honor", "live terminal", "half suji",
          "live 2-3-7-8", "live 4-5-6")
OFFSETS = tuple(range(-4, 5))
EARLY = 6
SHAPES = ("ryanmen", "kanchan", "penchan", "shanpon", "tanki")
GROUPS = {
    "label": [f"label {l}" for l in LABELS],
    "rank and honor kind": [f"rank {n}" for n in range(1, 10)] + ["honor", "dragon", "round wind", "riichi seat wind"],
    "copies and walls": [f"{o:+d} visible" for o in OFFSETS],
    "genbutsu around it": [f"{o:+d} genbutsu" for o in OFFSETS],
    "riichi player's discards around it": [f"{o:+d} {p}" for o in OFFSETS for p in ("early hand", "early draw", "late hand", "late draw", "declaration")],
    "dora": [f"{o:+d} dora" for o in OFFSETS],
    "the suit as a whole": ["suit discards", "other suits min", "other suits max", "honor discards", "last three hand in suit"],
    "timing": ["riichi turn", "turns since riichi", "riichi river length"],
}
BASE = [n for g in GROUPS.values() for n in g] + [f"{o:+d} valid" for o in OFFSETS]
FEATURES = BASE + [f"{s} ways" for s in SHAPES] + ["all ways", "copies in hand"]
INDEX = {n: i for i, n in enumerate(FEATURES)}
WHO = ("luckyj", "tokujou_human", "you", "jade_human")
SIDES = {"luckyj": (0,), "tokujou_humans": (1,), "jade_humans": (3,), "humans": (1, 3), "you": (2,)}
NAMES = {41: "East", 42: "South", 43: "West", 44: "North", 45: "Haku", 46: "Hatsu", 47: "Chun"}


def tile_name(b: int) -> str:
    return NAMES.get(int(b)) or f"{int(b) % 10}{'mps'[int(b) // 10 - 1]}"


def game_rows(job) -> tuple[list[tuple], list[tuple]]:
    g, table = job
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, safety, visible_counter
    from tenhou_replay import base

    hero, out, meta = g["hero_seat"], [], []
    game_id = zlib.crc32(g["uuid"].encode())
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        events = game["events"]
        indicators = game["dora_indicators"][:1]
        dora = {base(ws.dora_from_indicator(x)) for x in indicators}
        waits, rturn = {}, {}
        for e in events:
            if e["riichi"]:
                waits[e["seat"]] = {base(w) for w in tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])}
                rturn[e["seat"]] = e["turn"]
        round_wind = 41 + game["kyoku"] // 4 if game["kyoku"] < 16 else 41
        for e in events:
            s = e["seat"]
            reached = [q for q in range(4) if q != s and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            if len(reached) != 1 or e["riichi_seats"][s] is not None or e.get("tile") is None or not waits.get(reached[0]):
                continue
            q = reached[0]
            r = e["riichi_seats"][q]
            snap = meld_snapshots(game, e["index"] - 1)
            snap[s] = e["melds"]
            visible = visible_counter(e["hand_before"], e, game["players"], snap, indicators)
            passed = {base(x["tile"]) for x in events[r + 1: e["index"]] if x.get("tile") is not None}
            ref = {base(x) for x in e["rivers"][q]} | passed
            own = [x for x in events if x["seat"] == q and x["index"] <= r and x.get("tile") is not None]
            marks = {}
            for k, x in enumerate(own):
                b = base(x["tile"])
                kind = "declaration" if x["index"] == r else f"{'early' if k < EARLY else 'late'} {'draw' if x.get('tsumogiri') else 'hand'}"
                marks.setdefault(b, set()).add(kind)
            suit_count = [sum(1 for x in own if base(x["tile"]) // 10 == su and base(x["tile"]) < 40) for su in range(1, 4)]
            honor_count = sum(1 for x in own if base(x["tile"]) >= 40)
            last_hand = [base(x["tile"]) for x in own if not x.get("tsumogiri")][-3:]
            seat_wind = 41 + (q - game["kyoku"] % 4) % 4
            hb = e["hand_before"]
            after = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
            best = min(ws.hand_shanten(hb[:k] + hb[k + 1:], e["meld_tiles"], e["closed"]) for k in range(len(hb)))
            had_genbutsu = any(base(x) in ref for x in hb)
            held = Counter(base(x) for x in hb)
            who = ("luckyj" if s == hero else "tokujou_human") if table == "tenhou" else ("you" if s == hero else "jade_human")
            decision = zlib.crc32(f"{g['uuid']}|{li}|{e['index']}".encode())
            meta.append((decision, g["uuid"], game["round_name"], e["turn"]))
            thrown = base(e["tile"])
            for t in {base(x): x for x in hb}.values():
                b = base(t)
                if b in ref:
                    continue
                seen = visible.copy()
                seen[b] -= 1
                label = safety(t, q, e, game, seen)
                if label not in LABELS:
                    continue
                f = np.zeros(len(BASE), dtype=np.float32)
                f[INDEX[f"label {label}"]] = 1
                if b >= 40:
                    f[INDEX["honor"]] = 1
                    f[INDEX["dragon"]] = float(b >= 45)
                    f[INDEX["round wind"]] = float(b == round_wind)
                    f[INDEX["riichi seat wind"]] = float(b == seat_wind)
                    f[INDEX["+0 valid"]] = 1
                    f[INDEX["+0 visible"]] = seen[b] / 3
                    f[INDEX["+0 dora"]] = float(b in dora)
                else:
                    suit, n = divmod(b, 10)
                    f[INDEX[f"rank {n}"]] = 1
                    for o in OFFSETS:
                        if not 1 <= n + o <= 9:
                            continue
                        x = b + o
                        f[INDEX[f"{o:+d} valid"]] = 1
                        f[INDEX[f"{o:+d} visible"]] = (seen[x] if o == 0 else visible[x]) / 4
                        f[INDEX[f"{o:+d} genbutsu"]] = float(x in ref)
                        f[INDEX[f"{o:+d} dora"]] = float(x in dora)
                        for kind in marks.get(x, ()):
                            f[INDEX[f"{o:+d} {kind}"]] = 1
                    others = [c for su, c in enumerate(suit_count, start=1) if su != suit]
                    f[INDEX["suit discards"]] = suit_count[suit - 1] / 6
                    f[INDEX["other suits min"]] = min(others) / 6
                    f[INDEX["other suits max"]] = max(others) / 6
                    f[INDEX["last three hand in suit"]] = sum(1 for y in last_hand if y // 10 == suit and y < 40) / 3
                f[INDEX["honor discards"]] = honor_count / 6
                f[INDEX["riichi turn"]] = rturn[q] / 18
                f[INDEX["turns since riichi"]] = min(e["turn"] - rturn[q], 15) / 10
                f[INDEX["riichi river length"]] = len(own) / 18
                out.append((f, b in waits[q], b == thrown, decision, WHO.index(who), after > 0 and not had_genbutsu,
                            game_id % 5 == 0, game_id, b, after > 0 and not had_genbutsu and after > best, q == hero, held[b]))
    return out, meta


def ways(x: np.ndarray) -> dict[str, np.ndarray]:
    """For every row, the tile combinations of each wait shape that could be waiting on it and are not furiten."""
    col = lambda name: x[:, INDEX[name]]
    honor = col("honor") > 0
    rank = np.where(honor, 0, x[:, [INDEX[f"rank {n}"] for n in range(1, 10)]].argmax(1) + 1)
    u, g = {}, {}
    for o in OFFSETS:
        v = col(f"{o:+d} visible")
        # the candidate's own column counts the copies seen besides it, over 3 for an honor and 4 for a number
        raw = np.where(honor, 3 - 3 * v, 3 - 4 * v) if o == 0 else 4 - 4 * v
        u[o] = np.clip(np.round(raw), 0, 4) * col(f"{o:+d} valid")
        g[o] = col(f"{o:+d} genbutsu")
    num = rank > 0
    out = {"ryanmen": np.where(num & (rank + 3 <= 9) & (g[3] == 0), u[1] * u[2], 0)
                      + np.where(num & (rank - 3 >= 1) & (g[-3] == 0), u[-2] * u[-1], 0),
           "kanchan": np.where(num & (rank >= 2) & (rank <= 8), u[-1] * u[1], 0),
           "penchan": np.where(rank == 3, u[-2] * u[-1], 0) + np.where(rank == 7, u[1] * u[2], 0),
           "shanpon": u[0] * (u[0] - 1) / 2,
           "tanki": u[0].astype(float)}
    return out


def compute(your_manifest: str, out: str) -> None:
    os.chdir(ROOT)
    you = json.load(open(your_manifest))
    lj = json.loads(LJ_MANIFEST.read_text(encoding="utf-8"))
    jobs = [(g, "jade") for g in you] + [(g, "tenhou") for g in lj]
    with Pool(12) as pool:
        parts = list(pool.imap(game_rows, jobs, chunksize=4))
    rows = [r for p, _ in parts for r in p]
    meta = [m for _, p in parts for m in p]
    x = np.stack([r[0] for r in rows])
    w = ways(np.hstack([x, np.zeros((len(x), len(FEATURES) - len(BASE)), dtype=np.float32)]))
    held = np.array([r[11] for r in rows], dtype=np.float32)
    x = np.hstack([x, np.column_stack([w[s] for s in SHAPES] + [sum(w[s] for s in SHAPES), held]).astype(np.float32)])
    names = ("hit", "thrown", "decision", "who", "fold_no_genbutsu", "test", "game", "tile", "real_fold", "vs_hero")
    cols = {k: np.array([r[i] for r in rows]) for i, k in enumerate(names, start=1)}
    np.savez_compressed(out, x=x, features=np.array(FEATURES), **cols,
                        meta_decision=np.array([m[0] for m in meta]), meta_uuid=np.array([m[1] for m in meta]),
                        meta_round=np.array([m[2] for m in meta]), meta_turn=np.array([m[3] for m in meta]))
    print(f"wrote {out}: {len(rows)} candidate tiles, {len(set(cols['decision'].tolist()))} decisions, {cols['hit'].mean():.3%} winning tiles")


def predict(net, x: np.ndarray) -> np.ndarray:
    import torch

    net.eval()
    with torch.no_grad():
        return torch.sigmoid(net(torch.tensor(x)).squeeze(1)).numpy()


def auc(p: np.ndarray, y: np.ndarray) -> float:
    order = np.argsort(p)
    ranks = np.empty(len(p))
    ranks[order] = np.arange(1, len(p) + 1)
    pos = y > 0.5
    return float((ranks[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def fit_net(x: np.ndarray, y: np.ndarray, epochs: int = 3, seed: int = 1):
    import torch

    torch.manual_seed(seed)
    xt, yt = torch.tensor(x), torch.tensor(y.astype(np.float32))
    net = torch.nn.Sequential(torch.nn.Linear(x.shape[1], 64), torch.nn.ReLU(), torch.nn.Dropout(0.2),
                              torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Linear(32, 1))
    opt = torch.optim.Adam(net.parameters(), lr=1e-3, weight_decay=1e-4)
    loss = torch.nn.BCEWithLogitsLoss()
    for _ in range(epochs):
        net.train()
        perm = torch.randperm(len(yt))
        for i in range(0, len(yt), 2048):
            idx = perm[i:i + 2048]
            opt.zero_grad()
            loss(net(xt[idx]).squeeze(1), yt[idx]).backward()
            opt.step()
    return net


def net(data: str, out: str) -> None:
    """Out-of-fold danger from five small networks, each scoring the fifth of the games it was not trained on."""
    d = np.load(data)
    x, y, folds = d["x"], d["hit"], d["game"] % 5
    x = (x - x.mean(0)) / (x.std(0) + 1e-6)
    p = np.zeros(len(y))
    for k in range(5):
        p[folds == k] = predict(fit_net(x[folds != k], y[folds != k]), x[folds == k])
    np.savez_compressed(out, p=p)
    print(f"wrote {out}")


def gbm(data: str, out: str) -> None:
    """Out-of-fold danger from LightGBM, the same fifths; the rounds stop early on a fifth of the training games."""
    import lightgbm as lgb

    d = np.load(data)
    x, y, folds = d["x"], d["hit"].astype(int), d["game"] % 5
    p = np.zeros(len(y))
    for k in range(5):
        tr = folds != k
        inner = (d["game"][tr] // 5) % 5 == 0
        params = dict(objective="binary", learning_rate=0.03, num_leaves=63, min_child_samples=300, feature_fraction=0.7,
                      bagging_fraction=0.8, bagging_freq=1, lambda_l2=10, verbose=-1, num_threads=12, seed=k)
        m = lgb.train(params, lgb.Dataset(x[tr][~inner], y[tr][~inner]), 3000, valid_sets=[lgb.Dataset(x[tr][inner], y[tr][inner])],
                      callbacks=[lgb.early_stopping(100, verbose=False)])
        p[~tr] = m.predict(x[~tr], num_iteration=m.best_iteration)
        print(f"fold {k}: {m.best_iteration} rounds", flush=True)
    np.savez_compressed(out, p=p)
    print(f"wrote {out}")


def tabpfn(data: str, out: str, context: int = 50000, bags: int = 4, estimators: int = 4, batch: int = 1024) -> None:
    """Out-of-fold danger from TabPFN-3.5 (run on a CUDA host): for each fifth of the games, ``bags`` contexts of
    ``context`` candidates drawn from the other four fifths, each scoring the fifth's candidates in folds with no
    genbutsu; the bags are averaged. Each fifth is saved as it finishes (``OUT.k.npy``), and a rerun skips it."""
    import time

    from tabpfn import TabPFNClassifier
    from tabpfn.constants import ModelVersion

    d = np.load(data)
    x, y, folds = d["x"], d["hit"].astype(np.int32), d["game"] % 5
    scored = d["fold_no_genbutsu"].astype(bool)
    p = np.full(len(y), np.nan)
    for k in range(5):
        part = Path(f"{out}.{k}.npy")
        pool, target = np.flatnonzero(folds != k), np.flatnonzero((folds == k) & scored)
        if part.exists():
            p[target] = np.load(part)
            continue
        total = np.zeros(len(target))
        for b in range(bags):
            t0 = time.time()
            ctx = np.random.default_rng([k, b]).choice(pool, context, replace=False)
            m = TabPFNClassifier.create_default_for_version(ModelVersion("v3.5"), n_estimators=estimators, random_state=100 * k + b,
                                                            device="cuda", ignore_pretraining_limits=True, memory_saving_mode=True)
            m.fit(x[ctx], y[ctx])
            total += np.concatenate([m.predict_proba(x[target[i:i + batch]])[:, 1] for i in range(0, len(target), batch)])
            print(f"fold {k} bag {b}: {len(target)} scored in {time.time() - t0:.0f}s", flush=True)
        np.save(part, total / bags)
        p[target] = total / bags
    np.savez_compressed(out, p=p)
    print(f"wrote {out}")


def logistic_cv(X: np.ndarray, y: np.ndarray, folds: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Cross-fitted logistic danger on readable columns; returns the out-of-fold danger and the odds multipliers of
    one unit of each column, fitted on every row."""
    import torch

    def fit(rows):
        mu, sd = X[rows].mean(0), X[rows].std(0) + 1e-9
        xt, yt = torch.tensor((X[rows] - mu) / sd), torch.tensor(y[rows].astype(np.float64))
        w = torch.zeros(X.shape[1], dtype=torch.float64, requires_grad=True)
        b = torch.zeros(1, dtype=torch.float64, requires_grad=True)
        opt = torch.optim.LBFGS([w, b], max_iter=2000, tolerance_grad=1e-10, tolerance_change=1e-12, line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            l = torch.nn.functional.binary_cross_entropy_with_logits(xt @ w + b, yt) + 1e-7 * (w ** 2).sum()
            l.backward()
            return l

        for _ in range(3):
            opt.step(closure)
        return lambda z: torch.sigmoid(torch.tensor((z - mu) / sd) @ w + b).detach().numpy(), np.exp(w.detach().numpy() / sd)

    p = np.zeros(len(y))
    for k in range(5):
        p[folds == k] = fit(folds != k)[0](X[folds == k])
    return p, fit(np.ones(len(y), dtype=bool))[1]


def readable(d) -> dict[str, np.ndarray]:
    """The checklist's columns: the kind of tile, copies seen, the declaration tile's suji, early neighbours, dora."""
    x = d["x"]
    col = lambda name: x[:, INDEX[name]]
    lab = x[:, [INDEX[f"label {l}"] for l in LABELS]].argmax(1)
    L = {l: (lab == i).astype(float) for i, l in enumerate(LABELS)}
    honor = col("honor")
    num = 1 - honor
    seen = np.round(np.where(honor > 0, 3 * col("+0 visible"), 4 * col("+0 visible")))
    rank = np.where(honor > 0, 0, x[:, [INDEX[f"rank {n}"] for n in range(1, 10)]].argmax(1) + 1)

    def anyof(offsets, kinds):
        return np.max([col(f"{o:+d} {k}") for o in offsets for k in kinds], axis=0)

    return {**{f"kind: {l}": L[l] for l in LABELS[1:]},
            "copies seen besides yours (honor)": honor * seen,
            "copies seen besides yours (suji)": L["suji"] * seen,
            "copies seen besides yours (nakasuji, half suji)": (L["nakasuji"] + L["half suji"]) * seen,
            "copies seen besides yours (live number)": (1 - L["suji"] - L["nakasuji"] - L["half suji"] - L["virtual nakasuji"]) * num * seen,
            "suji made by the declaration tile": L["suji"] * anyof((-3, 3), ("declaration",)),
            "half suji made by the declaration tile": L["half suji"] * anyof((-3, 3), ("declaration",)),
            "the riichi threw a tile 1-2 ranks away early": num * anyof((-2, -1, 1, 2), ("early hand", "early draw")),
            "dora": col("+0 dora"),
            "dora 1-2 ranks away": num * anyof((-2, -1, 1, 2), ("dora",)),
            "dragon": col("dragon"),
            "1 or 9": ((rank == 1) | (rank == 9)).astype(float)}


def pct(v: float, digits: int = 2) -> float:
    return round(100 * float(v), digits)


def report(data: str, out: str, *preds: str) -> None:
    d = dict(np.load(data))
    y, x, folds = d["hit"].astype(float), d["x"], d["game"] % 5
    lab = x[:, [INDEX[f"label {l}"] for l in LABELS]].argmax(1)
    models = {}
    for spec in preds:
        name, path = spec.split("=")
        models[name] = np.load(path)["p"]
    ref = next(iter(models))
    cues = readable(d)
    kinds = np.column_stack([v for k, v in cues.items() if k.startswith("kind")])
    models["kind only"] = logistic_cv(kinds, y, folds)[0]
    models["checklist"], odds = logistic_cv(np.column_stack(list(cues.values())), y, folds)

    fold = d["fold_no_genbutsu"].astype(bool)
    order = np.flatnonzero(fold)[np.argsort(d["decision"][fold], kind="stable")]
    bounds = np.flatnonzero(np.diff(d["decision"][order])) + 1
    decisions = [g for g in np.split(order, bounds) if d["thrown"][g].any() and len(g) >= 2]
    thrown_of = {int(d["decision"][g[0]]): g[d["thrown"][g]][0] for g in decisions}

    def side(gs):
        thr = np.array([g[d["thrown"][g]][0] for g in gs])
        res = {"n": len(gs), "thrown": pct(y[thr].mean()), "hits": int(y[thr].sum()), "random": pct(np.mean([y[g].mean() for g in gs]))}
        for name, p in models.items():
            q = np.nan_to_num(p, nan=1.0)
            res[f"{name} pick"] = pct(np.mean([y[g[q[g] <= q[g].min() + 1e-12]].mean() for g in gs]))
            if name not in ("kind only", "checklist"):
                res[f"{name} predicted"] = pct(np.nanmean(p[thr]))
        res["kinds"] = {LABELS[l]: [int((lab[thr] == l).sum()), pct(y[thr][lab[thr] == l].mean(), 1)]
                        for l in range(len(LABELS)) if (lab[thr] == l).sum()}
        return res

    result = {"candidates": int(len(y)), "decisions": int(len(set(d["decision"].tolist()))), "winning_share": pct(y.mean()),
              "games": {"jade": int(len(set(d["game"][d["who"] >= 2].tolist()))), "tenhou": int(len(set(d["game"][d["who"] <= 1].tolist())))},
              "auc": {name: round(auc(np.nan_to_num(p[fold], nan=0.5), y[fold]), 3) for name, p in models.items()},
              "sides": {}, "checklist_odds": {k: round(float(v), 2) for k, v in zip(cues, odds)}}
    for s, ws in SIDES.items():
        mine = [g for g in decisions if d["who"][g[0]] in ws]
        result["sides"][s] = {"no_genbutsu": side(mine), "real_folds": side([g for g in mine if d["real_fold"][g[0]]])}
    toku = [g for g in decisions if d["who"][g[0]] == 1]
    result["tokujou_humans_by_riichi"] = {name: side([g for g in toku if bool(d["vs_hero"][g[0]]) == hero])
                                          for name, hero in (("against LuckyJ", True), ("against the others", False))}

    # within the same reference danger, thrown against kept, in the no-genbutsu folds
    p = models[ref]
    result["same_danger"] = {}
    for s in ("luckyj", "humans", "you"):
        gs = [g for g in decisions if d["who"][g[0]] in SIDES[s]]
        thr = np.array([g[d["thrown"][g]][0] for g in gs])
        kept = np.concatenate([g[~d["thrown"][g]] for g in gs])
        cells = []
        for lo, hi in ((0, .02), (.02, .04), (.04, .07), (.07, .12), (.12, 1.01)):
            a, b = (p[thr] >= lo) & (p[thr] < hi), (p[kept] >= lo) & (p[kept] < hi)
            cells.append({"model": [pct(lo, 0), pct(hi, 0)], "thrown": [int(a.sum()), pct(y[thr][a].mean()) if a.any() else None],
                          "kept": [int(b.sum()), pct(y[kept][b].mean()) if b.any() else None]})
        result["same_danger"][s] = cells

    # the cues' danger over every candidate
    honor = x[:, INDEX["honor"]] > 0
    seen = np.round(np.where(honor, 3 * x[:, INDEX["+0 visible"]], 4 * x[:, INDEX["+0 visible"]])).astype(int)
    rank = np.where(honor, 0, x[:, [INDEX[f"rank {n}"] for n in range(1, 10)]].argmax(1) + 1)
    honor_kind = np.where(x[:, INDEX["dragon"]] > 0, "dragon",
                          np.where(np.maximum(x[:, INDEX["round wind"]], x[:, INDEX["riichi seat wind"]]) > 0, "value wind", "guest wind"))

    def table(mask, key):
        cell = {}
        for k in sorted(set(key[mask].tolist()), key=str):
            m = mask & (key == k)
            cell[str(k)] = [int(m.sum()), pct(y[m].mean(), 1)]
        return cell

    suji = lab == LABELS.index("suji")
    rank_class = np.array(["", "1/9", "2/8", "3/7", "", "", "", "3/7", "2/8", "1/9"])[rank]
    decl = cues["suji made by the declaration tile"] > 0
    early = cues["the riichi threw a tile 1-2 ranks away early"] > 0
    result["cues"] = {
        "honors: copies seen besides yours": table(honor, np.char.add(np.char.add(seen.astype(str), " seen, "), honor_kind)),
        "suji: rank, made by the declaration tile": table(suji, np.char.add(rank_class, np.where(decl, ", declaration tile", ""))),
        "suji: copies seen besides yours": table(suji, seen),
        "live terminal: the riichi threw a tile 1-2 ranks away early": table(lab == LABELS.index("live terminal"), early.astype(int)),
        "live 2-3-7-8: the riichi threw a tile 1-2 ranks away early": table(lab == LABELS.index("live 2-3-7-8"), early.astype(int)),
        "every candidate by kind": table(np.ones(len(y), dtype=bool), np.array(LABELS)[lab]),
    }

    # the user's no-genbutsu folds that dealt in, beside the reference model's safest tile
    where = {int(k): (u, r, t) for k, u, r, t in zip(d["meta_decision"], d["meta_uuid"], d["meta_round"], d["meta_turn"])}
    yours = []
    for g in decisions:
        if d["who"][g[0]] != 2:
            continue
        t = g[d["thrown"][g]][0]
        if not y[t]:
            continue
        safest = g[np.argmin(np.nan_to_num(p[g], nan=1.0))]
        listed = g[np.argmin(models["checklist"][g])]
        u, r, turn = where[int(d["decision"][g[0]])]
        yours.append({"game": str(u), "round": str(r), "turn": int(turn), "real_fold": bool(d["real_fold"][t]),
                      "thrown": [tile_name(d["tile"][t]), LABELS[lab[t]], pct(p[t], 1)],
                      "safest": [tile_name(d["tile"][safest]), LABELS[lab[safest]], pct(p[safest], 1)],
                      "checklist": [tile_name(d["tile"][listed]), LABELS[lab[listed]], pct(models["checklist"][listed], 1), bool(y[listed])],
                      "thrown_rank": int((p[g] < p[t]).sum()) + 1, "candidates": len(g)})
    result["your_deal_ins"] = sorted(yours, key=lambda r: r["game"])
    Path(out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: result[k] for k in ("candidates", "auc")}, indent=1))
    for s, v in result["sides"].items():
        print(s, {k: v["real_folds"][k] for k in v["real_folds"] if k != "kinds"})


if __name__ == "__main__":
    command, args = sys.argv[1], sys.argv[2:]
    if command == "compute":
        compute(*args[:2])
    elif command == "net":
        net(*args[:2])
    elif command == "gbm":
        gbm(*args[:2])
    elif command == "tabpfn":
        tabpfn(args[0], args[1], *map(int, args[2:6]))
    else:
        report(args[0], args[1], *args[2:])
