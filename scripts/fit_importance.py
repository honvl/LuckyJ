#!/usr/bin/env python3
"""An importance weighting of our own for Mortal-S42's game rating: does it say more about the place?

``mine_importance.py`` keeps each seat-game's decisions apart by situation (turn, shanten, threat, kind, stage). A
weighting gives every situation a weight w; the game's rating is then the weighted mean of what the player gave up,

    rating = - sum(w * loss) / sum(w * decisions)

for one of three measures of loss: Q loss, minus ln p at T 0.6, or a miss (not Mortal's first choice). With w = 1
everywhere this is the flat rating the ladder comparison uses.

Each measure comes three ways (``add_adjusted``): raw; ``adj``, the loss beyond what the situation usually costs,
which is the part that is the player's doing; and ``usual``, the situations alone with no decision in them, which
shows how much of a weighting's gain is only the luck of having been in easy situations.

Weightings tried:

- ``flat``                    every decision the same;
- ``later turns``             w = the discard number (the plain guess that later moves matter more);
- ``Wind-Up Bird, turn+shanten`` and ``..., +threat``: the formula that reproduces Wind-Up Bird's own importance
  (fitted on its cached reviews, ``describe`` below), with a riichi standing in for its tenpai read;
- ``fitted``                  w = exp(theta . features), theta chosen to make the rating track the place, found on
  four fifths of the games and scored on the fifth it did not see (games, not seats, are split).

Every weighting is scored by the Spearman correlation of the rating with the place in the same game, and by its
difference to the flat rating with a bootstrap interval over games. For the Houou regulars it is also scored across
games (``skill``): a rating from half of a player's games against the mean place in the other half, which is the
test that matters for ranking players because the luck of one deal cannot carry over.

    .venv/bin/python scripts/fit_importance.py describe            # what Wind-Up Bird's importance is made of
    .venv/bin/python scripts/fit_importance.py score ROWS.jsonl ... [--name NAME] [--fit]
    .venv/bin/python scripts/fit_importance.py all OUT.json
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
TURNS, SHANTEN, THREAT, KIND, STAGE = 9, 4, 3, 2, 3
CELLS = [(t, s, th, k, st) for t in range(TURNS) for s in range(SHANTEN) for th in range(THREAT)
         for k in range(KIND) for st in range(STAGE)]
CELL_INDEX = {".".join(map(str, c)): i for i, c in enumerate(CELLS)}
MEASURES = ("Q loss", "ln p", "miss")
FEATURES = ("turn", "tenpai", "1 away", "2 away", "open melds", "riichi", "answer", "South 1-3", "South 4+")
# Wind-Up Bird's importance, ln(weight), fitted on its own reviews (7,839 discards of 63 games, see describe()):
# turn and shanten explain 89% of it, and its tenpai read for the opponents brings that to 94%.
WUB_TURN_SHANTEN = {"turn": 0.086, "tenpai": 1.465, "1 away": 1.065, "2 away": 0.560}
WUB_THREAT = {"turn": 0.040, "tenpai": 1.569, "1 away": 1.112, "2 away": 0.588}
WUB_TENPAI_READ = 0.816                          # per unit of the top opponent's tenpai chance
ASSUMED_TENPAI = {0: 0.1, 1: 0.3, 2: 1.0}        # our threat levels as that chance: none, open melds, riichi


def turn_mid(t: int) -> float:
    return 2 * t + 1.5


def features() -> np.ndarray:
    """One row per situation: the numbers a log-linear weighting multiplies."""
    z = np.zeros((len(CELLS), len(FEATURES)))
    for i, (t, s, th, k, st) in enumerate(CELLS):
        z[i] = [turn_mid(t), s == 0, s == 1, s == 2, th == 1, th == 2, k == 1, st == 1, st == 2]
    return z


Z = features()


def theta_of(named: dict) -> np.ndarray:
    return np.array([named.get(f, 0.0) for f in FEATURES])


def weightings() -> dict[str, np.ndarray]:
    wub_threat = Z @ theta_of(WUB_THREAT) + WUB_TENPAI_READ * np.array([ASSUMED_TENPAI[c[2]] for c in CELLS])
    return {
        "flat": np.ones(len(CELLS)),
        "later turns": Z[:, 0].copy(),
        "Wind-Up Bird, turn+shanten": np.exp(Z @ theta_of(WUB_TURN_SHANTEN)),
        "Wind-Up Bird, +threat": np.exp(wub_threat),
    }


def load(paths: list[Path], min_decisions: int = 20) -> dict:
    """Rows as arrays: counts and the three losses per situation, the place, the game and the player."""
    n, q, lp, miss, place, game, name, seat = [], [], [], [], [], [], [], []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if "error" in r or r.get("n", 0) < min_decisions:
                    continue
                a = np.zeros((4, len(CELLS)))
                for key, v in r["b"].items():
                    i = CELL_INDEX[key]
                    a[0, i], a[1, i], a[2, i], a[3, i] = v[0], v[1], -v[2], v[0] - v[3]
                n.append(a[0]); q.append(a[1]); lp.append(a[2]); miss.append(a[3])
                place.append(r["place"]); game.append(r["file"]); name.append(r.get("name")); seat.append(r["seat"])
    return add_adjusted({"n": np.array(n), "Q loss": np.array(q), "ln p": np.array(lp), "miss": np.array(miss),
                         "place": np.array(place, dtype=float), "game": np.array(game), "name": np.array(name),
                         "seat": np.array(seat)})


def rating(data: dict, measure: str, w: np.ndarray, rows=slice(None)) -> np.ndarray:
    """Higher is better play: minus the weighted mean loss."""
    den = data["n"][rows] @ w
    return -(data[measure][rows] @ w) / np.where(den > 0, den, 1.0)


def add_adjusted(data: dict) -> dict:
    """Add each measure's loss beyond what its situation usually costs, and the usual cost itself.

    A weighted mean of raw loss rewards a seat for the situations it was in: tenpai decisions are easy (93% match
    Mortal), so a seat that was tenpai often rates well under any weighting that leans on tenpai, and it also
    places well, for the same lucky hands. ``X adj`` takes the situation's mean loss out of every decision, so only
    doing better or worse than usual there counts; ``X usual`` keeps only the situations, with no decisions in it.
    """
    for measure in MEASURES:
        total_n = data["n"].sum(axis=0)
        mu = np.where(total_n > 0, data[measure].sum(axis=0) / np.where(total_n > 0, total_n, 1.0), 0.0)
        data[measure + " usual"] = data["n"] * mu
        data[measure + " adj"] = data[measure] - data["n"] * mu
    return data


def ranks(a) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    order = np.argsort(a, kind="stable")
    s = a[order]
    out = np.empty(len(a))
    start = np.flatnonzero(np.r_[True, s[1:] != s[:-1]])
    end = np.r_[start[1:], len(a)]
    for i, j in zip(start, end):
        out[order[i:j]] = (i + j - 1) / 2
    return out


def corr(x, y) -> float:
    x, y = x - x.mean(), y - y.mean()
    den = math.sqrt(float(x @ x) * float(y @ y))
    return float(x @ y) / den if den > 0 else float("nan")


def spearman(x, y) -> float:
    return corr(ranks(x), ranks(y))


def game_groups(data: dict) -> list[np.ndarray]:
    order = np.argsort(data["game"], kind="stable")
    cuts = np.flatnonzero(np.r_[True, data["game"][order][1:] != data["game"][order][:-1]])
    return np.split(order, cuts[1:])


def compare_to_flat(data: dict, measure: str, w: np.ndarray, boot: int = 1000, seed: int = 3,
                    rows: np.ndarray | None = None) -> dict:
    """The weighting's correlation with the place, and its difference to the flat rating (bootstrap over games)."""
    idx = np.arange(len(data["place"])) if rows is None else rows
    place = ranks(data["place"][idx])
    new, flat = ranks(rating(data, measure, w, idx)), ranks(rating(data, measure, np.ones(len(CELLS)), idx))
    games = data["game"][idx]
    _, inv = np.unique(games, return_inverse=True)
    members = [np.flatnonzero(inv == g) for g in range(inv.max() + 1)]
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(boot):
        pick = np.concatenate([members[g] for g in rng.integers(0, len(members), len(members))])
        diffs.append(corr(new[pick], place[pick]) - corr(flat[pick], place[pick]))
    return {"r": round(corr(new, place), 4), "flat": round(corr(flat, place), 4),
            "diff": round(corr(new, place) - corr(flat, place), 4),
            "lo": round(float(np.percentile(diffs, 2.5)), 4), "hi": round(float(np.percentile(diffs, 97.5)), 4)}


def skill(data: dict, measure: str, w: np.ndarray, min_games: int = 20, splits: int = 20, boot: int = 300,
          seed: int = 9) -> dict:
    """Does a player's rating in half of their games say where they finish in the other half?

    The place in the same game mixes the player's skill with the luck of the deal. Across separate games the luck
    is gone, so this is the test that matters for ranking players. Players with ``min_games`` or more are split in
    two at random ``splits`` times; the rating pools the first half's decisions and is set against the mean place
    in the second half. The interval of the gain over the flat rating is a bootstrap over players.
    """
    names, inv = np.unique(np.where(data["name"] == None, "", data["name"]).astype(str), return_inverse=True)  # noqa: E711
    counts = np.bincount(inv)
    keep = np.flatnonzero((counts >= min_games) & (names != ""))
    rows = np.flatnonzero(np.isin(inv, keep))
    player = np.searchsorted(keep, inv[rows])
    k = len(keep)
    if k < 10:
        return {"players": int(k), "note": "too few players with enough games"}
    flat_w = np.ones(len(CELLS))
    num = {"new": data[measure][rows] @ w, "flat": data[measure][rows] @ flat_w}
    den = {"new": data["n"][rows] @ w, "flat": data["n"][rows] @ flat_w}
    place = data["place"][rows]
    rng = np.random.default_rng(seed)
    rs, flats, diffs, slopes = [], [], [], []
    for _ in range(splits):
        half = rng.random(len(rows)) < 0.5
        b_games = np.bincount(player[~half], minlength=k)
        a_games = np.bincount(player[half], minlength=k)
        ok = (a_games >= 5) & (b_games >= 5)
        place_b = ranks((np.bincount(player[~half], weights=place[~half], minlength=k) / np.maximum(b_games, 1))[ok])
        rated = {}
        for key in ("new", "flat"):
            a_num = np.bincount(player[half], weights=num[key][half], minlength=k)
            a_den = np.bincount(player[half], weights=den[key][half], minlength=k)
            rated[key] = ranks((-a_num / np.where(a_den > 0, a_den, 1.0))[ok])
        rs.append(corr(rated["new"], place_b))
        flats.append(corr(rated["flat"], place_b))
        raw_b = (np.bincount(player[~half], weights=place[~half], minlength=k) / np.maximum(b_games, 1))[ok]
        z = (rated["new"] - rated["new"].mean()) / rated["new"].std()
        slopes.append(float(np.polyfit(z, raw_b, 1)[0]))
        for _ in range(boot // splits):
            i = rng.integers(0, int(ok.sum()), int(ok.sum()))
            diffs.append(corr(rated["new"][i], place_b[i]) - corr(rated["flat"][i], place_b[i]))
    return {"players": int(k), "r": round(float(np.mean(rs)), 4), "flat": round(float(np.mean(flats)), 4),
            "diff": round(float(np.mean(rs) - np.mean(flats)), 4),
            "lo": round(float(np.percentile(diffs, 2.5)), 4), "hi": round(float(np.percentile(diffs, 97.5)), 4),
            "places_per_sd": round(float(np.mean(slopes)), 4)}


def skill_table(data: dict, kinds=("", " adj", " usual")) -> dict:
    out = {}
    for measure in [m + k for m in MEASURES for k in kinds]:
        out[measure] = {name: skill(data, measure, w) for name, w in weightings().items()}
    return out


def show_skill(title: str, table: dict) -> None:
    first = next(iter(next(iter(table.values())).values()))
    print(f"\n{title}: a half's rating against the other half's mean place ({first['players']} players)")
    if "note" in first:
        print(f"  {first['note']}")
        return
    for measure, block in table.items():
        print(f"  {measure}")
        for name, v in block.items():
            gain = "" if name == "flat" else f"   gain {v['diff']:+.3f}  [{v['lo']:+.3f}, {v['hi']:+.3f}]"
            print(f"    {name:28} {v['r']:+.3f}  ({v['places_per_sd']:+.4f} places per SD){gain}")


def fit_theta(data: dict, measure: str, rows: np.ndarray, rounds: int = 6, ridge: float = 0.02) -> np.ndarray:
    """theta that makes the weighted rating track the place on ``rows``: a shrinking search one feature at a time.

    The score is the correlation with the place (ranks) less a small pull toward zero, so a feature the data say
    nothing about keeps a weight of one.
    """
    place = ranks(data["place"][rows])
    sub = {"n": data["n"][rows], measure: data[measure][rows]}

    def score(theta):
        r = corr(ranks(rating(sub, measure, np.exp(Z @ theta))), place)
        return r + ridge * float(np.sum((theta * SCALE) ** 2))  # r is negative when good: minimise

    theta = np.zeros(len(FEATURES))
    best = score(theta)
    step = STEP.copy()
    for _ in range(rounds):
        for j in range(len(FEATURES)):
            for d in (step[j], -step[j]):
                trial = theta.copy()
                trial[j] += d
                s = score(trial)
                if s < best - 1e-6:
                    theta, best = trial, s
                    break
        step = step / 2
    return theta


# a step of the turn weight is per discard; the others are whole switches
STEP = np.array([0.08] + [0.8] * (len(FEATURES) - 1))
SCALE = np.array([10.0] + [1.0] * (len(FEATURES) - 1))


def cross_validated(data: dict, measure: str, folds: int = 5, seed: int = 1) -> dict:
    """Fit on four fifths of the games, rate the fifth with those weights, and score all held-out ratings together."""
    groups = game_groups(data)
    rng = np.random.default_rng(seed)
    fold_of = rng.permutation(len(groups)) % folds
    held = np.empty(len(data["place"]))
    flat = np.empty(len(data["place"]))
    thetas = []
    for k in range(folds):
        test = np.concatenate([g for g, f in zip(groups, fold_of) if f == k])
        train = np.concatenate([g for g, f in zip(groups, fold_of) if f != k])
        theta = fit_theta(data, measure, train)
        thetas.append(theta)
        # ratings from different folds use different weights, so each fold is put on ranks before pooling
        held[test] = ranks(rating(data, measure, np.exp(Z @ theta), test)) / len(test)
        flat[test] = ranks(rating(data, measure, np.ones(len(CELLS)), test)) / len(test)
    place = ranks(data["place"])
    _, inv = np.unique(data["game"], return_inverse=True)
    members = [np.flatnonzero(inv == g) for g in range(inv.max() + 1)]
    rng = np.random.default_rng(seed + 1)
    diffs = []
    for _ in range(1000):
        pick = np.concatenate([members[g] for g in rng.integers(0, len(members), len(members))])
        diffs.append(corr(held[pick], place[pick]) - corr(flat[pick], place[pick]))
    full = fit_theta(data, measure, np.arange(len(place)))
    return {"r": round(corr(held, place), 4), "flat": round(corr(flat, place), 4),
            "diff": round(corr(held, place) - corr(flat, place), 4),
            "lo": round(float(np.percentile(diffs, 2.5)), 4), "hi": round(float(np.percentile(diffs, 97.5)), 4),
            "theta": {f: round(float(v), 3) for f, v in zip(FEATURES, full)},
            "theta_spread": {f: round(float(v), 3) for f, v in zip(FEATURES, np.std(thetas, axis=0))}}


def score(data: dict, fit: bool = True, rows: np.ndarray | None = None, kinds=("", " adj", " usual")) -> dict:
    out = {"seat_games": int(len(data["place"]) if rows is None else len(rows)), "measures": {}}
    for measure in [m + k for m in MEASURES for k in kinds]:
        block = {name: compare_to_flat(data, measure, w, rows=rows) for name, w in weightings().items()
                 if name != "flat"}
        if fit and rows is None and not measure.endswith("usual"):
            block["fitted (held out)"] = cross_validated(data, measure)
        out["measures"][measure] = block
    return out


def show(title: str, result: dict) -> None:
    print(f"\n{title} ({result['seat_games']} seat-games)")
    for measure, block in result["measures"].items():
        flat = next(iter(block.values()))["flat"]
        print(f"  {measure}: flat {flat:+.3f}")
        for name, v in block.items():
            print(f"    {name:28} {v['r']:+.3f}   gain {v['diff']:+.3f}  [{v['lo']:+.3f}, {v['hi']:+.3f}]")
            if "theta" in v:
                print("      ln weight: " + ", ".join(f"{k} {x:+.2f}" for k, x in v["theta"].items() if x))


# ---------------------------------------------------------------- what Wind-Up Bird's importance is made of

def describe(cache: Path | None = None) -> dict:
    """How much of Wind-Up Bird's importance the turn, the hand's shanten and its tenpai read explain."""
    import fetch_neji_reviews as fetch
    X, y, games = [], [], 0
    for path in fetch.cached(cache or fetch.CACHE):
        doc = fetch.load(path)
        review, seat = doc["review"], doc["seat"]
        games += 1
        for hand in review.get("annotations") or []:
            turn = 0
            for a in hand or []:
                if not a or a.get("actor") != seat or a.get("phase") != "DISCARD" or not a.get("review"):
                    continue
                turn += 1
                rv = a["review"]
                osp = ((a.get("predictions") or [{}])[0]).get("opponent_shanten_probabilities")
                if not rv.get("weight") or not osp or rv.get("best_shanten") is None:
                    continue
                s = min(rv["best_shanten"], 3)
                X.append([1, turn, s == 0, s == 1, s == 2, max(o[0] for o in osp)])
                y.append(math.log(rv["weight"]))
    X, y = np.array(X, dtype=float), np.array(y)
    out = {"games": games, "discards": int(len(y)), "fits": {}}
    if len(y) < 200:
        return out
    for name, cols in (("turn", [0, 1]), ("shanten", [0, 2, 3, 4]), ("opponents' tenpai read", [0, 5]),
                       ("turn + shanten", [0, 1, 2, 3, 4]), ("turn + shanten + tenpai read", [0, 1, 2, 3, 4, 5])):
        beta, *_ = np.linalg.lstsq(X[:, cols], y, rcond=None)
        r2 = 1 - float(np.var(y - X[:, cols] @ beta)) / float(np.var(y))
        labels = ["base", "turn", "tenpai", "1 away", "2 away", "tenpai read"]
        out["fits"][name] = {"r2": round(r2, 3), "coef": {labels[c]: round(float(b), 3) for c, b in zip(cols, beta)}}
    return out


def main(argv: list[str]) -> int:
    cmd = argv[0] if argv else "all"
    result = {}
    if cmd in ("describe", "all"):
        result["wind_up_bird_importance"] = d = describe()
        print(f"Wind-Up Bird's ln(importance) on {d['discards']} discards of {d['games']} games")
        for name, v in d["fits"].items():
            print(f"  {name:30} R2 {v['r2']:.3f}  " + ", ".join(f"{k} {x:+.3f}" for k, x in v["coef"].items()))
    if cmd == "score":
        fit = "--fit" in argv
        paths = [Path(a) for a in argv[1:] if not a.startswith("--")]
        show(" + ".join(p.name for p in paths), score(load(paths), fit=fit))
    if cmd == "all":
        for label, name in (("Jade, every seat", "jade_importance.jsonl"), ("Houou, every seat", "houou_importance.jsonl")):
            path = LADDER / name
            if not path.exists():
                continue
            data = load([path])
            result[label] = score(data)
            show(label, result[label])
            if label.startswith("Jade"):
                mine = np.flatnonzero(data["name"] == "Honver")
                result["Jade, your seat"] = score(data, fit=False, rows=mine)
                show("Jade, your seat", result["Jade, your seat"])
            else:
                result["Houou regulars, across games"] = skill_table(data)
                show_skill("Houou regulars", result["Houou regulars, across games"])
        if len(argv) > 1:
            Path(argv[1]).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"\nwrote {argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
