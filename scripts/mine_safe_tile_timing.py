#!/usr/bin/env python3
"""Turn-by-turn safe-tile retention for Point 14.

Replays every cached NAGA report in kyoku where LuckyJ is not dealer. At each LuckyJ
discard decision it records, by LuckyJ's own turn number (1 = first discard):

- how many held tile classes already sit in at least one opponent's river ("safe tiles");
- the per-tile discard rate of safe tiles versus non-safe tiles, split by tile kind;
- the share of turns where LuckyJ cut a non-safe tile while holding at least one safe tile.

Split by table state: quiet (no opponent riichi, no opponent at 2+ melds) versus threat.

It also records, at each turn where the hand held two floaters of the same kind (guest winds,
terminals or isolated middle tiles), one already in an opponent's river and one in none, which one
LuckyJ cut and which one NAGA's Nishiki head picked. The same-kind restriction removes tile-type
composition: early safe floaters are mostly guest winds, which LuckyJ cuts first regardless.

Outputs analysis/safe-tile-timing-<date>.json. "summary_turns" holds the per-discard counts and the
fitted curves the book's charts draw; "summary_bands" pools the same counts into turn bands for the
method report. Rebuild both from an existing file with --summarize PATH.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_luckyj as base  # noqa: E402
import mine_rx2_defense as rx2  # noqa: E402

OUT = Path(f"analysis/safe-tile-timing-{date.today().isoformat()}.json")
HURO_TYPES = base.HURO_TYPES
MAX_TURN = 18


def pct(num: float, den: float) -> float | None:
    return round(100.0 * num / den, 1) if den else None


def ci95(num: int, den: int) -> float | None:
    if not den:
        return None
    p = num / den
    return round(196.0 * math.sqrt(p * (1 - p) / den), 2)


def tile_class(tile: str) -> str:
    return tile.replace("r", "")


def tile_kind(tile: str) -> str:
    t = tile_class(tile)
    if len(t) == 1:
        return "honor"
    return "terminal" if int(t[0]) in (1, 9) else "middle"


SUIT_ORDER = "mps"
WIND_SEATS = ["E", "S", "W", "N"]


def floater_classes(hand: list[str], own_wind: str, round_wind: str) -> set[str]:
    """Held tile classes with no pair and no same-suit neighbor within two ranks.

    Value honors (dragons, own seat wind, round wind) are excluded because LuckyJ keeps
    them for yaku, which would look like defensive retention.
    """
    counts: dict[str, int] = {}
    for t in hand:
        c = tile_class(t)
        counts[c] = counts.get(c, 0) + 1
    out = set()
    for c, n in counts.items():
        if n != 1:
            continue
        if len(c) == 1:
            if c in ("P", "F", "C") or c == own_wind or c == round_wind:
                continue
            out.add(c)
            continue
        rank, suit = int(c[0]), c[1]
        if any(f"{r}{suit}" in counts for r in range(rank - 2, rank + 3) if r != rank and 1 <= r <= 9):
            continue
        out.add(c)
    return out


class Rate:
    def __init__(self) -> None:
        self.n = 0
        self.hit = 0

    def add(self, hit: bool) -> None:
        self.n += 1
        self.hit += 1 if hit else 0

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "hits": self.hit, "rate_pct": pct(self.hit, self.n), "ci95_half_width_pp": ci95(self.hit, self.n)}


class Mean:
    def __init__(self) -> None:
        self.n = 0
        self.total = 0.0

    def add(self, v: float) -> None:
        self.n += 1
        self.total += v

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "mean": round(self.total / self.n, 2) if self.n else None}


def new_turn_table() -> dict[str, Any]:
    return {
        "states": 0,
        "safe_classes_held": Mean(),
        "holds_any_safe": Rate(),
        "kept_safe_cut_live": Rate(),
        "floater_choice": {
            "turns_with_both": 0,
            "safe_share_of_floaters": Mean(),
            "picked_safe_floater": Rate(),
            "picked_live_floater": Rate(),
            "naga_picked_safe_floater": Rate(),
            "naga_picked_live_floater": Rate(),
            "by_kind": {
                kind: {
                    "safe_share": Mean(),
                    "picked_safe": Rate(),
                    "picked_live": Rate(),
                    "naga_picked_safe": Rate(),
                    "naga_picked_live": Rate(),
                }
                for kind in ("honor", "terminal", "middle")
            },
        },
        "discard_rate": {
            status: {kind: Rate() for kind in ("honor", "terminal", "middle", "all")}
            for status in ("safe", "not_safe")
        },
    }


BANDS = ((1, 2), (3, 5), (6, 8), (9, 12), (13, 18))
KINDS = ("honor", "terminal", "middle")


def band_label(lo: int, hi: int) -> str:
    return f"{lo}-{hi}"


def summarize(out: dict[str, Any]) -> dict[str, Any]:
    """Pool the per-turn same-kind floater choices into turn bands.

    For each band the figure is the share of cuts (of either floater) that went to the live one:
    live / (safe + live). Above 50 means the safe tile was kept; below 50 means it went first.
    """
    by_turn = out["by_turn"]

    def pooled(split: str, kind: str, who: str, lo: int, hi: int) -> dict[str, Any]:
        safe_key = "picked_safe" if who == "LuckyJ" else "naga_picked_safe"
        live_key = "picked_live" if who == "LuckyJ" else "naga_picked_live"
        spots = safe = live = 0
        for turn in range(lo, hi + 1):
            fc = by_turn[split][str(turn)]["floater_choice"]
            if kind == "any":
                block = {
                    "picked_safe": fc["picked_safe_floater"], "picked_live": fc["picked_live_floater"],
                    "naga_picked_safe": fc["naga_picked_safe_floater"], "naga_picked_live": fc["naga_picked_live_floater"],
                }
            else:
                block = fc["by_kind"][kind]
            spots += block[safe_key]["n"]
            safe += block[safe_key]["hits"]
            live += block[live_key]["hits"]
        cuts = safe + live
        return {"spots": spots, "cuts": cuts, "live_cuts": live, "live_share_pct": pct(live, cuts)}

    bands = {}
    for split in ("quiet", "threat"):
        bands[split] = {}
        for kind in KINDS + ("any",):
            bands[split][kind] = {
                band_label(lo, hi): {who: pooled(split, kind, who, lo, hi) for who in ("LuckyJ", "NAGA")}
                for lo, hi in BANDS
            }
    threat_share = {}
    for turn in range(1, MAX_TURN + 1):
        quiet = by_turn["quiet"][str(turn)]["states"]
        threat = by_turn["threat"][str(turn)]["states"]
        threat_share[str(turn)] = {"states": quiet + threat, "threat_pct": pct(threat, quiet + threat)}
    return {
        "definition": "same-kind floater pairs, one safe and one live; live_share_pct = share of cuts of either tile that went to the live one",
        "bands": bands,
        "threat_share_by_turn": threat_share,
    }



# ----------------------------------------------------------------------------- per-discard fit
#
# The book's charts plot one point per discard and a fitted curve through them, so noisy late
# discards do not decide the shape. The fit is a binomial logistic regression of "kept the safe
# leftover" on a natural cubic spline of the discard number (Hastie, Tibshirani and Friedman, The
# Elements of Statistical Learning, eq. 5.4), with 1, 2 or 3 degrees of freedom chosen by AIC. It
# runs over the longest run of discards that each have at least FIT_MIN_CHOICES choices. The 95%
# band scales the covariance by the Pearson dispersion when it exceeds 1. Plain Python: the data is
# at most 18 points per series.

FIT_MIN_CHOICES = 10
FIT_DFS = (1, 2, 3)
PANEL_KEYS = (("quiet", "honor"), ("quiet", "terminal"), ("quiet", "middle"), ("threat", "any"))


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(a)
    m = [list(map(float, row)) + [float(b[i])] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError("singular system")
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def _inverse(a: list[list[float]]) -> list[list[float]]:
    n = len(a)
    cols = [_solve(a, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def _expit(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _ns_row(x: float, knots: list[float]) -> list[float]:
    """Intercept plus a natural cubic spline basis in x: linear beyond the boundary knots."""
    row = [1.0, x]
    if len(knots) > 2:
        last = knots[-1]

        def d(k: int) -> float:
            return (max(x - knots[k], 0.0) ** 3 - max(x - last, 0.0) ** 3) / (last - knots[k])

        tail = d(len(knots) - 2)
        row += [d(k) - tail for k in range(len(knots) - 2)]
    return row


def _logit_fit(rows: list[list[float]], k: list[int], n: list[int]) -> dict[str, Any]:
    p = len(rows[0])
    pooled = min(max(sum(k) / sum(n), 1e-3), 1 - 1e-3)
    beta = [math.log(pooled / (1 - pooled))] + [0.0] * (p - 1)
    for _ in range(200):
        eta = [sum(r[j] * beta[j] for j in range(p)) for r in rows]
        mu = [min(max(_expit(e), 1e-9), 1 - 1e-9) for e in eta]
        w = [ni * m * (1 - m) for ni, m in zip(n, mu)]
        z = [e + (ki / ni - m) / (m * (1 - m)) for e, ki, ni, m in zip(eta, k, n, mu)]
        xtwx = [[sum(w[i] * rows[i][a] * rows[i][b] for i in range(len(rows))) for b in range(p)] for a in range(p)]
        xtwz = [sum(w[i] * rows[i][a] * z[i] for i in range(len(rows))) for a in range(p)]
        new = _solve(xtwx, xtwz)
        done = max(abs(x - y) for x, y in zip(new, beta)) < 1e-10
        beta = new
        if done:
            break
    eta = [sum(r[j] * beta[j] for j in range(p)) for r in rows]
    mu = [min(max(_expit(e), 1e-9), 1 - 1e-9) for e in eta]
    w = [ni * m * (1 - m) for ni, m in zip(n, mu)]
    xtwx = [[sum(w[i] * rows[i][a] * rows[i][b] for i in range(len(rows))) for b in range(p)] for a in range(p)]
    deviance = 0.0
    pearson = 0.0
    for ki, ni, m in zip(k, n, mu):
        if ki:
            deviance += 2 * ki * math.log(ki / (ni * m))
        if ni - ki:
            deviance += 2 * (ni - ki) * math.log((ni - ki) / (ni * (1 - m)))
        pearson += (ki - ni * m) ** 2 / (ni * m * (1 - m))
    return {"beta": beta, "xtwx": xtwx, "deviance": deviance, "pearson": pearson, "aic": deviance + 2 * p}


def _longest_run(turns: list[int], n_by_turn: dict[int, int], minimum: int) -> tuple[int, int] | None:
    best, run = None, []
    for t in turns:
        if n_by_turn.get(t, 0) >= minimum:
            run.append(t)
            if best is None or len(run) > best[1] - best[0] + 1:
                best = (run[0], run[-1])
        else:
            run = []
    return best


def fit_series(turn_rows: list[dict[str, int]], key: str, lo: int, hi: int) -> dict[str, Any]:
    """Fit one series (LuckyJ or NAGA) over discards lo..hi; key is "lj" or "naga"."""
    pts = [r for r in turn_rows if lo <= r["turn"] <= hi and r[f"{key}_n"] > 0]
    span = hi - lo
    xs = [(r["turn"] - lo) / span for r in pts]
    k = [r[f"{key}_k"] for r in pts]
    n = [r[f"{key}_n"] for r in pts]
    unique = sorted(set(xs))
    fits = {}
    for df in FIT_DFS:
        if len(pts) - (df + 1) < 2:
            continue
        interior = [unique[round(q * (len(unique) - 1))] for q in [(i + 1) / df for i in range(df - 1)]]
        interior = sorted({x for x in interior if 0.0 < x < 1.0})
        if len(interior) != df - 1:
            continue
        knots = [0.0] + interior + [1.0]
        rows = [_ns_row(x, knots) for x in xs]
        try:
            fit = _logit_fit(rows, k, n)
        except ValueError:
            continue
        fit["knots"] = knots
        fits[df] = fit
    df = min(fits, key=lambda d: fits[d]["aic"])
    fit = fits[df]
    p = len(fit["beta"])
    dispersion = max(1.0, fit["pearson"] / (len(pts) - p))
    cov = [[dispersion * v for v in row] for row in _inverse(fit["xtwx"])]

    def at(turn: float) -> tuple[float, float]:
        row = _ns_row((turn - lo) / span, fit["knots"])
        eta = sum(row[j] * fit["beta"][j] for j in range(p))
        var = sum(row[a] * cov[a][b] * row[b] for a in range(p) for b in range(p))
        return eta, math.sqrt(max(var, 0.0))

    grid = []
    steps = int(round(span * 10))
    for i in range(steps + 1):
        turn = lo + i / 10
        eta, se = at(turn)
        grid.append([round(turn, 1), round(100 * _expit(eta), 2), round(100 * _expit(eta - 1.96 * se), 2), round(100 * _expit(eta + 1.96 * se), 2)])
    crossings = []
    previous = at(lo)[0]
    for i in range(1, span * 100 + 1):
        turn = lo + i / 100
        eta = at(turn)[0]
        if (previous < 0) != (eta < 0):
            crossings.append({"turn": round(turn, 2), "direction": "up" if eta > previous else "down"})
        previous = eta
    return {
        "df": df,
        "knots_turn": [round(lo + x * span, 3) for x in fit["knots"]],
        "aic_by_df": {str(d): round(f["aic"], 3) for d, f in fits.items()},
        "dispersion": round(dispersion, 3),
        "points": len(pts),
        "crossings_50": crossings,
        "grid": grid,
    }


def summarize_turns(out: dict[str, Any]) -> dict[str, Any]:
    by_turn = out["by_turn"]
    panels = {}
    for split, kind in PANEL_KEYS:
        rows = []
        for turn in range(1, MAX_TURN + 1):
            fc = by_turn[split][str(turn)]["floater_choice"]
            if kind == "any":
                safe, live = fc["picked_safe_floater"]["hits"], fc["picked_live_floater"]["hits"]
                nsafe, nlive = fc["naga_picked_safe_floater"]["hits"], fc["naga_picked_live_floater"]["hits"]
            else:
                block = fc["by_kind"][kind]
                safe, live = block["picked_safe"]["hits"], block["picked_live"]["hits"]
                nsafe, nlive = block["naga_picked_safe"]["hits"], block["naga_picked_live"]["hits"]
            rows.append({"turn": turn, "lj_k": live, "lj_n": safe + live, "naga_k": nlive, "naga_n": nsafe + nlive})
        span = _longest_run(list(range(1, MAX_TURN + 1)), {r["turn"]: r["lj_n"] for r in rows}, FIT_MIN_CHOICES)
        lo, hi = span
        panels[f"{split}-{kind}"] = {
            "turns": rows,
            "range": [lo, hi],
            "fits": {"LuckyJ": fit_series(rows, "lj", lo, hi), "NAGA": fit_series(rows, "naga", lo, hi)},
        }
    return {
        "definition": "per discard: k = choices where the live leftover was thrown (the safe one kept), n = choices of either leftover; percentages are 100 k / n",
        "method": "binomial logistic regression on a natural cubic spline of the discard number, 1 to 3 degrees of freedom chosen by AIC, fitted over the longest run of discards with at least 10 choices each; the 95% band uses the covariance scaled by max(1, Pearson dispersion)",
        "min_choices": FIT_MIN_CHOICES,
        "panels": panels,
    }


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--summarize":
        path = Path(sys.argv[2])
        out = json.loads(path.read_text())
        out["summary_bands"] = summarize(out)
        out["summary_turns"] = summarize_turns(out)
        path.write_text(json.dumps(out, indent=2))
        print("summarized", path)
        return

    raw_rows = base.parse_rows()
    rows, seen = [], set()
    for row in raw_rows:
        rid = row.get("report_id")
        if rid in seen:
            continue
        seen.add(rid)
        rows.append(row)

    tables: dict[str, dict[int, dict[str, Any]]] = {
        "quiet": defaultdict(new_turn_table),
        "threat": defaultdict(new_turn_table),
    }
    summary = {"reports": 0, "child_kyoku": 0, "dealer_kyoku_skipped": 0, "errors": []}

    for i, row in enumerate(rows, 1):
        if i % 200 == 0:
            print(f"{i}/{len(rows)}", flush=True)
        target = row.get("actor")
        if target is None or not (0 <= target < 4):
            continue
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
            summary["reports"] += 1
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(repr(exc))
            continue

        for kyoku in data.get("pred") or []:
            try:
                start = (kyoku[0].get("info", {}).get("msg", {}) if kyoku else {}) or {}
                oya = start.get("oya")
                if oya is None:
                    continue
                if int(oya) == target:
                    summary["dealer_kyoku_skipped"] += 1
                    continue
                summary["child_kyoku"] += 1
                opponents = [s for s in range(4) if s != target]
                own_wind = WIND_SEATS[(target - int(oya)) % 4]
                round_wind = start.get("bakaze") or "E"

                start_hands = start.get("tehais") or [[], [], [], []]
                hand = list(start_hands[target]) if target < len(start_hands) else []
                discards: list[list[str]] = [[], [], [], []]
                open_melds = [0, 0, 0, 0]
                reached = [False, False, False, False]
                own_turn = 0

                for state in kyoku:
                    msg = state.get("info", {}).get("msg", {}) or {}
                    actor = msg.get("actor")
                    mtype = msg.get("type")

                    if mtype == "tsumo":
                        if actor == target and msg.get("pai"):
                            hand.append(msg["pai"])
                        actual = msg.get("real_dahai")
                        is_decision = actor == target and actual not in (None, "?") and "dahai_pred" in state
                        if is_decision:
                            own_turn += 1
                            if own_turn <= MAX_TURN and not reached[target]:
                                any_riichi = any(reached[s] for s in opponents)
                                max_open = max(open_melds[s] for s in opponents)
                                split = "quiet" if (not any_riichi and max_open <= 1) else "threat"
                                table = tables[split][own_turn]
                                table["states"] += 1
                                rivers = set()
                                for s in opponents:
                                    rivers.update(tile_class(t) for t in discards[s])
                                held = {tile_class(t) for t in hand}
                                safe = held & rivers
                                a_cls = tile_class(actual)
                                table["safe_classes_held"].add(len(safe))
                                table["holds_any_safe"].add(bool(safe))
                                if safe:
                                    table["kept_safe_cut_live"].add(a_cls not in rivers)
                                floaters = floater_classes(hand, own_wind, round_wind)
                                safe_fl = floaters & rivers
                                live_fl = floaters - rivers
                                if safe_fl and live_fl:
                                    fc = table["floater_choice"]
                                    fc["turns_with_both"] += 1
                                    fc["safe_share_of_floaters"].add(len(safe_fl) / len(floaters))
                                    fc["picked_safe_floater"].add(a_cls in safe_fl)
                                    fc["picked_live_floater"].add(a_cls in live_fl)
                                    naga_cls = None
                                    preds = state.get("dahai_pred") or []
                                    if preds and len(preds[0]) >= 34:
                                        naga_cls = tile_class(base.top_tile(preds[0])[0])
                                        fc["naga_picked_safe_floater"].add(naga_cls in safe_fl)
                                        fc["naga_picked_live_floater"].add(naga_cls in live_fl)
                                    for kind in ("honor", "terminal", "middle"):
                                        ks = {c for c in safe_fl if tile_kind(c) == kind}
                                        kl = {c for c in live_fl if tile_kind(c) == kind}
                                        if not (ks and kl):
                                            continue
                                        bk = fc["by_kind"][kind]
                                        bk["safe_share"].add(len(ks) / (len(ks) + len(kl)))
                                        bk["picked_safe"].add(a_cls in ks)
                                        bk["picked_live"].add(a_cls in kl)
                                        if naga_cls is not None:
                                            bk["naga_picked_safe"].add(naga_cls in ks)
                                            bk["naga_picked_live"].add(naga_cls in kl)
                                for cls in held:
                                    status = "safe" if cls in rivers else "not_safe"
                                    kind = tile_kind(cls)
                                    hit = cls == a_cls
                                    table["discard_rate"][status][kind].add(hit)
                                    table["discard_rate"][status]["all"].add(hit)
                        if actor == target and actual not in (None, "?"):
                            rx2.remove_tile(hand, actual)

                    elif mtype in HURO_TYPES:
                        if actor is not None:
                            open_melds[actor] += 1
                            if actor == target:
                                for t in msg.get("consumed") or []:
                                    rx2.remove_tile(hand, t)
                                d = msg.get("real_dahai")
                                if d and d != "?":
                                    rx2.remove_tile(hand, d)
                                    own_turn += 1

                    elif mtype == "ankan":
                        if actor is not None:
                            open_melds[actor] += 1
                            if actor == target:
                                for t in msg.get("consumed") or []:
                                    rx2.remove_tile(hand, t)

                    elif mtype == "kakan":
                        if actor == target and msg.get("pai"):
                            rx2.remove_tile(hand, msg["pai"])

                    elif mtype == "reach":
                        if actor is not None:
                            reached[actor] = True

                    elif mtype == "dahai":
                        tile = msg.get("pai")
                        if actor is not None and tile:
                            discards[actor].append(tile)
            except Exception as exc:  # noqa: BLE001
                if len(summary["errors"]) < 20:
                    summary["errors"].append(repr(exc))

    def dump(table: dict[str, Any]) -> dict[str, Any]:
        return {
            "states": table["states"],
            "safe_classes_held": table["safe_classes_held"].to_dict(),
            "holds_any_safe": table["holds_any_safe"].to_dict(),
            "kept_safe_cut_live": table["kept_safe_cut_live"].to_dict(),
            "floater_choice": {
                "turns_with_both": table["floater_choice"]["turns_with_both"],
                "safe_share_of_floaters": table["floater_choice"]["safe_share_of_floaters"].to_dict(),
                "picked_safe_floater": table["floater_choice"]["picked_safe_floater"].to_dict(),
                "picked_live_floater": table["floater_choice"]["picked_live_floater"].to_dict(),
                "naga_picked_safe_floater": table["floater_choice"]["naga_picked_safe_floater"].to_dict(),
                "naga_picked_live_floater": table["floater_choice"]["naga_picked_live_floater"].to_dict(),
                "by_kind": {
                    kind: {name: stat.to_dict() for name, stat in stats.items()}
                    for kind, stats in table["floater_choice"]["by_kind"].items()
                },
            },
            "discard_rate": {
                status: {kind: r.to_dict() for kind, r in kinds.items()}
                for status, kinds in table["discard_rate"].items()
            },
        }

    out = {
        "scope": "kyoku where LuckyJ is not dealer; LuckyJ's own discard number 1..18; own-riichi states excluded",
        "definitions": {
            "safe": "held tile class already present in at least one opponent's river at decision time",
            "quiet": "no opponent riichi and no opponent with 2+ melds",
            "kept_safe_cut_live": "among turns holding at least one safe class, share where the discard was not in any opponent river",
            "floater": "held singleton with no same-suit neighbor within two ranks; dragons, own seat wind and round wind excluded",
            "naga": "Nishiki head top pick, dahai_pred[0], at the same decision",
            "by_kind": "same comparison restricted to turns holding a safe and a live floater of the same kind (honor, terminal, middle), which removes tile-type composition",
            "floater_choice": "turns holding at least one safe floater and one live floater: which kind LuckyJ discarded, against the safe share of floaters as the indifference baseline",
        },
        "summary": summary,
        "by_turn": {
            split: {str(turn): dump(tables[split][turn]) for turn in range(1, MAX_TURN + 1)}
            for split in ("quiet", "threat")
        },
    }
    out["summary_bands"] = summarize(out)
    out["summary_turns"] = summarize_turns(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
