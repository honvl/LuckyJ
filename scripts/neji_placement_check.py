#!/usr/bin/env python3
"""Does a game's review grade say where the player finished? Wind-Up Bird's importance grade against Mortal's ratings.

Three reviewers rate one seat of one game:

- the earlier local Mortal policy model (``data/ladder_skill/jade.jsonl``, ``houou.jsonl``): the probability it gave
  to each action taken;
- Mortal-S42 (``jade_s42.jsonl``, ``houou_s42_merged.jsonl``): what each action gave up in Q-values;
- Wind-Up Bird (``data/neji_reviews``, from ``fetch_neji_reviews.py``): severity times importance for each decision.

``baseline`` asks how well each Mortal statistic of a game tracks the place in that same game, over every seat of
your Jade games, your own seat alone, and the Houou games. It needs no Wind-Up Bird review.

``compare`` takes the games that have a cached Wind-Up Bird review and puts its statistics beside the two Mortal
models' on those same games: the correlation of each with the place, a bootstrap interval, and the interval of the
difference to the best Mortal statistic, and what each says about the place once the other is known (a partial
correlation). The grade with importance (``score``) sits beside the same model's grade
without it (``flat severity``, ``match rate``), which is the part importance adds.

``power`` says how many reviewed games a difference of a given size needs.

Correlations are Spearman's, signed so that a better grade with a better place is negative (1st is place 1).

    .venv/bin/python scripts/neji_placement_check.py baseline
    .venv/bin/python scripts/neji_placement_check.py compare
    .venv/bin/python scripts/neji_placement_check.py power
    .venv/bin/python scripts/neji_placement_check.py all OUT.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

LADDER = ROOT / "data" / "ladder_skill"
ROWS = {
    "Mortal policy": {"Jade": LADDER / "jade.jsonl", "Houou": LADDER / "houou.jsonl"},
    "Mortal-S42": {"Jade": LADDER / "jade_s42.jsonl", "Houou": LADDER / "houou_s42_merged.jsonl"},
}
HERO = "Honver"
MIN_DECISIONS = 20

# Each statistic is signed so that higher means better play.
STATS = {
    "Mortal policy": {
        "match rate": lambda r: r["top"] / r["n"],
        "mean ln p": lambda r: r["logp"] / r["n"],
        "under 10% rate": lambda r: -r["low"] / r["n"],
        "under 10% count": lambda r: -r["low"],
    },
    "Mortal-S42": {
        "match rate": lambda r: r["top"] / r["n"],
        "mean ln p (T 0.6)": lambda r: r["lp06"] / r["n"],
        "mean Q loss": lambda r: -r["qloss"] / r["n"],
        "total Q loss": lambda r: -r["qloss"],
        "Q loss over 1 count": lambda r: -r["big1"],
    },
}


def ranks(a) -> np.ndarray:
    """Average ranks (ties share the mean rank)."""
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="stable")
    out = np.empty(len(a))
    s = a[order]
    i = 0
    while i < len(a):
        j = i
        while j + 1 < len(a) and s[j + 1] == s[i]:
            j += 1
        out[order[i:j + 1]] = (i + j) / 2
        i = j + 1
    return out


def spearman(x, y) -> float:
    x, y = ranks(x), ranks(y)
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def partial(x, y, z) -> float:
    """Spearman correlation of x with y after the part of each that z explains is taken out."""
    rxy, rxz, ryz = spearman(x, y), spearman(x, z), spearman(y, z)
    den = math.sqrt(max(0.0, (1 - rxz * rxz) * (1 - ryz * ryz)))
    return (rxy - rxz * ryz) / den if den > 0 else float("nan")


def fisher_interval(r: float, n: int) -> tuple[float, float]:
    """A 95% interval for a correlation from n pairs (Fisher's z)."""
    if n < 4 or not math.isfinite(r) or abs(r) >= 1:
        return (float("nan"), float("nan"))
    z, se = math.atanh(r), 1 / math.sqrt(n - 3)
    return (math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se))


def load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if "error" not in r and r.get("n", 0) >= MIN_DECISIONS:
                rows.append(r)
    return rows


def game_id(row: dict) -> str:
    return Path(row["file"]).stem


def table(rows: list[dict], stats: dict) -> dict:
    places = [r["place"] for r in rows]
    out = {}
    for name, fn in stats.items():
        try:
            r = spearman([fn(x) for x in rows], places)
        except KeyError:
            continue
        lo, hi = fisher_interval(r, len(rows))
        out[name] = {"r": round(r, 4), "lo": round(lo, 4), "hi": round(hi, 4)}
    return out


def stake_gain(rows: list[dict], boot: int = 1000, seed: int = 5) -> dict:
    """Within Mortal-S42: the stake-weighted statistic (mean Q loss) against the flat one (match rate).

    Q loss is already weighted by what a decision is worth, so this is what weighting by stakes adds when the model
    stays the same. The interval is a bootstrap over seat-games, on ranks taken once.
    """
    place = ranks([r["place"] for r in rows])
    flat = ranks([STATS["Mortal-S42"]["match rate"](r) for r in rows])
    staked = ranks([STATS["Mortal-S42"]["mean Q loss"](r) for r in rows])
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(boot):
        i = rng.integers(0, len(rows), len(rows))
        diffs.append(np.corrcoef(staked[i], place[i])[0, 1] - np.corrcoef(flat[i], place[i])[0, 1])
    d = float(np.corrcoef(staked, place)[0, 1] - np.corrcoef(flat, place)[0, 1])
    return {"diff": round(d, 4), "lo": round(float(np.percentile(diffs, 2.5)), 4),
            "hi": round(float(np.percentile(diffs, 97.5)), 4),
            "between": round(float(np.corrcoef(staked, flat)[0, 1]), 3)}


def baseline() -> dict:
    out = {}
    for model, files in ROWS.items():
        for room, path in files.items():
            rows = load_rows(path)
            need = "qloss" if model == "Mortal-S42" else "logp"
            rows = [r for r in rows if need in r]
            if not rows:
                continue
            out[f"{model} | {room}, every seat"] = {"n": len(rows), "stats": table(rows, STATS[model])}
            if model == "Mortal-S42":
                out[f"{model} | {room}, every seat"]["stake_gain"] = stake_gain(rows)
            if room == "Jade":
                mine = [r for r in rows if r.get("name") == HERO]
                out[f"{model} | {room}, your seat"] = {"n": len(mine), "stats": table(mine, STATS[model])}
                if model == "Mortal-S42":
                    out[f"{model} | {room}, your seat"]["stake_gain"] = stake_gain(mine)
    return out


# ---------------------------------------------------------------- Wind-Up Bird reviews

def review_stats(doc: dict) -> dict | None:
    """One cached review as game statistics, each signed so that higher means better play."""
    review, seat = doc["review"], doc["seat"]
    grade = review["grades"][seat]
    if not grade.get("graded"):
        return None
    severities, weights, ev_loss = [], [], 0.0
    for hand in review.get("annotations") or []:
        for a in hand or []:
            rv = (a or {}).get("review")
            if not rv or a.get("actor") != seat or not rv.get("weight"):
                continue
            severities.append(rv.get("penalty", 0.0) / rv["weight"])
            weights.append(rv["weight"])
            ev_loss += max(0.0, ((rv.get("ev") or {}).get("loss") or 0.0))
    stats = {
        "score (severity x importance)": grade["score"],
        "match rate": grade["matched"] / grade["graded"],
        "total penalty": -grade["penalty"],
    }
    if severities:
        stats["flat severity (no importance)"] = -float(np.mean(severities))
        stats["total EV loss"] = -ev_loss
        stats["_importance"] = float(np.sum(weights))
    return stats


def joined(cache: Path | None = None) -> list[dict]:
    """Games with a cached review, each with the two Mortal models' rows for the same seat where they exist."""
    import fetch_neji_reviews as fetch
    by = {}
    for model, files in ROWS.items():
        for r in load_rows(files["Jade"]):
            by[(model, game_id(r), r["seat"])] = r
    out = []
    for path in fetch.cached(cache or fetch.CACHE):
        doc = fetch.load(path)
        stats = review_stats(doc)
        if stats is None:
            continue
        row = {"id": doc["game_id"], "seat": doc["seat"], "place": doc["placement"], "Wind-Up Bird": stats}
        for model in ROWS:
            r = by.get((model, doc["game_id"], doc["seat"]))
            if r is not None:
                row[model] = {name: fn(r) for name, fn in STATS[model].items()}
        out.append(row)
    return out


def compare(games: list[dict], boot: int = 4000, seed: int = 7) -> dict:
    """Correlation of every statistic with the place on the games all three reviewers rated."""
    full = [g for g in games if all(m in g for m in ("Mortal policy", "Mortal-S42", "Wind-Up Bird"))]
    out = {"reviewed": len(games), "n": len(full), "stats": {}}
    if len(full) < 8:
        out["note"] = "too few games for a correlation"
        return out
    places = np.array([g["place"] for g in full], dtype=float)
    cols = {}
    for model in ("Wind-Up Bird", "Mortal-S42", "Mortal policy"):
        for name in full[0][model]:
            if name.startswith("_"):
                continue
            cols[f"{model}: {name}"] = np.array([g[model][name] for g in full], dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(full), size=(boot, len(full)))
    draws = {}
    for key, x in cols.items():
        r = spearman(x, places)
        d = np.array([spearman(x[i], places[i]) for i in idx])
        d = d[np.isfinite(d)]
        draws[key] = np.array([spearman(x[i], places[i]) for i in idx])
        out["stats"][key] = {"r": round(r, 3), "lo": round(float(np.percentile(d, 2.5)), 3),
                             "hi": round(float(np.percentile(d, 97.5)), 3)}
    # the headline: the importance grade against the best Mortal statistic, and against its own flat version
    head = "Wind-Up Bird: score (severity x importance)"
    mortal = {k: v["r"] for k, v in out["stats"].items() if k.startswith("Mortal")}
    best = min(mortal, key=mortal.get)
    out["best_mortal"] = best
    out["differences"] = {}
    for other in (best, "Wind-Up Bird: flat severity (no importance)", "Wind-Up Bird: match rate"):
        if other not in draws:
            continue
        d = draws[head] - draws[other]
        d = d[np.isfinite(d)]
        out["differences"][f"{head} minus {other}"] = {
            "diff": round(out["stats"][head]["r"] - out["stats"][other]["r"], 3),
            "lo": round(float(np.percentile(d, 2.5)), 3), "hi": round(float(np.percentile(d, 97.5)), 3)}
    out["between"] = {f"{head} with {best}": round(spearman(cols[head], cols[best]), 3)}
    # what each grade says about the place once the other is known (partial rank correlation)
    out["partial"] = {}
    for a, b in ((head, best), (best, head)):
        r = partial(cols[a], places, cols[b])
        d = np.array([partial(cols[a][i], places[i], cols[b][i]) for i in idx[:1000]])
        d = d[np.isfinite(d)]
        out["partial"][f"{a}, given {b}"] = {"r": round(r, 3), "lo": round(float(np.percentile(d, 2.5)), 3),
                                              "hi": round(float(np.percentile(d, 97.5)), 3)}
    return out


def games_needed(r_new: float, r_base: float, r_between: float, power: float = 0.8, sims: int = 3000,
                 seed: int = 11) -> int:
    """Reviewed games needed to tell a grade with correlation ``r_new`` to the place from one with ``r_base``.

    Both are rated on the same games and correlate ``r_between`` with each other. Found by simulation: the spread
    of the difference of two Pearson correlations at a trial size scales with 1 / sqrt(n).
    """
    cov = np.array([[1, r_new, r_base], [r_new, 1, r_between], [r_base, r_between, 1]], dtype=float)
    if np.linalg.eigvalsh(cov).min() <= 0:
        raise ValueError("these three correlations cannot hold together")
    rng = np.random.default_rng(seed)
    trial = 400
    data = rng.multivariate_normal(np.zeros(3), cov, size=(sims, trial))
    place, new, base = data[..., 0], data[..., 1], data[..., 2]

    def corr(a, b):
        a = a - a.mean(axis=1, keepdims=True)
        b = b - b.mean(axis=1, keepdims=True)
        return (a * b).sum(axis=1) / np.sqrt((a * a).sum(axis=1) * (b * b).sum(axis=1))

    sd_one = float(np.std(corr(new, place) - corr(base, place))) * math.sqrt(trial)  # spread at n = 1
    z = 1.96 + {0.8: 0.8416, 0.9: 1.2816}.get(power, 0.8416)
    return math.ceil((z * sd_one / abs(r_new - r_base)) ** 2)


def power_table(r_base: float = -0.15) -> list[dict]:
    rows = []
    for r_new in (-0.20, -0.25, -0.30, -0.40):
        for between in (0.5, 0.7):
            rows.append({"base": r_base, "new": r_new, "between": between,
                         "games": games_needed(r_new, r_base, between)})
    return rows


def show_table(title: str, n: int, stats: dict) -> None:
    print(f"\n{title} ({n} seat-games)")
    for name, v in stats.items():
        print(f"  {name:36} r {v['r']:+.3f}  [{v['lo']:+.3f}, {v['hi']:+.3f}]")


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    result = {}
    if cmd in ("baseline", "all"):
        result["baseline"] = baseline()
        for title, block in result["baseline"].items():
            show_table(title, block["n"], block["stats"])
            if "stake_gain" in block:
                g = block["stake_gain"]
                print(f"  mean Q loss minus match rate: {g['diff']:+.3f}  [{g['lo']:+.3f}, {g['hi']:+.3f}]"
                      f"  (the two correlate {g['between']:+.2f})")
    if cmd in ("compare", "all"):
        result["compare"] = c = compare(joined())
        print(f"\nWind-Up Bird reviews cached: {c['reviewed']}; rated by all three: {c['n']}")
        if c.get("stats"):
            show_table("Same games, all three reviewers", c["n"], c["stats"])
            for name, v in c["differences"].items():
                print(f"  {name}: {v['diff']:+.3f}  [{v['lo']:+.3f}, {v['hi']:+.3f}]")
            for name, v in c["between"].items():
                print(f"  correlation of {name}: {v:+.3f}")
            for name, v in c["partial"].items():
                print(f"  {name}: {v['r']:+.3f}  [{v['lo']:+.3f}, {v['hi']:+.3f}]")
        else:
            print(f"  {c.get('note')}")
    if cmd in ("power", "all"):
        result["power"] = power_table()
        print("\nReviewed games needed (80% power, 5% two-sided)")
        for row in result["power"]:
            print(f"  grade r {row['new']:+.2f} against Mortal r {row['base']:+.2f}, the two correlated "
                  f"{row['between']:.1f}: {row['games']} games")
    if cmd == "all" and len(argv) > 1:
        Path(argv[1]).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nwrote {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
