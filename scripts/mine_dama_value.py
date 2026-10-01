#!/usr/bin/env python3
"""Chapter 24: when a hand that already has value should stay dama, and what the riichi's boost is worth.

Every figure comes from first closed tenpais: the first turn of a hand where a closed hand could cut to
tenpai and did, with riichi legal (four or more tiles left in the wall, 1,000 points to put down) and a
wait that is not furiten. A hand's value is the han a ron pays without riichi on EVERY winning tile, dora
and red fives included (``dama_min`` in ``scripts/contrast/tenpai.py``); a hand whose yaku covers only some
of its winning tiles is counted apart. A two-sided wait is a ryanmen or a wait on three or more kinds. A
two-sided 3-han hand is also sorted by the points its cheapest ron pays as a non-dealer (``dama_han`` and
``dama_fu``): 3,900 is pinfu, 5,200 or 6,400 is 40 or 50 fu, already a mangan by tsumo. At 4 han the fu move only
the dama ron (7,700 or 8,000); the riichi adds the same 5 han and the same haneman tsumo either way, so 4-han
hands stay together (``turn_offsets`` checks that LuckyJ treats them alike).

- ``cells``: how often LuckyJ declared, with nobody in riichi, by value and wait.
- ``curves``: LuckyJ's riichi share for two-sided tenpais of 3 han pinfu, 4 han and 5 han or more, one
  point per turn of its own and a fitted curve (``fit_series``), with the turn where the fit crosses one half.
- ``you``: the same decisions in your games, split at 29 September 16:00 (``RECENT_FROM``), with what
  LuckyJ's rates and Mortal's weights (``site/replays``) expect from the same hands; your riichis per 100
  hands; and what became of the riichis in the five newest games.
- ``trade``: what a riichi does to a two-sided 5-han hand, a 4-han hand at 40 fu and a pinfu 4-han hand at
  one turn. Win rates by ron and by tsumo
  and the average result of a hand that does not win are fitted over all four seats of LuckyJ's games
  (riichi: every declared tenpai with a yaku; dama: tenpais worth 4 han or more kept dama), with the turn
  as a natural spline, the live tiles and the dealer as terms, and read at a non-dealer with six live
  tiles. Win values follow the non-dealer table, a riichi win adding its ura dora and ippatsu from their
  measured spread (``extra_han``). The band resamples whole games.
- ``chase``: first tenpais with an opponent already in riichi and three or fewer live tiles, by value.

usage: mine_dama_value.py YOUR_TENPAI LJ_TENPAI LJ_MANIFEST OUT.json

YOUR_TENPAI and LJ_TENPAI are ``scripts/contrast/tenpai.py`` on ``data/self_games/majsoul/index.json``
(games since 1 January) and on LuckyJ's Tokujou games (``data/local_sources/luckyj_tenhou/index.json``
filtered to ``mode == "tenhou-tokujou"``, which is LJ_MANIFEST). Run it from the main checkout, where the
manifests' log paths resolve.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mine_safe_tile_timing as timing  # noqa: E402
import tenhou_replay as tr  # noqa: E402
from mine_safe_tile_timing import _ns_row, fit_series  # noqa: E402
from review_win_speed import TENHOU_YAKU  # noqa: E402

YOUR_MANIFEST = ROOT / "data" / "self_games" / "majsoul" / "index.json"
REPLAYS = ROOT / "site" / "replays"
SINCE = "2026-01-01"
RECENT_FROM = "2026-09-29 16:00"  # the games after chapter 22's
NEWEST_FROM = "2026-09-30 18:00"  # the games after chapter 23 went up
TWO_SIDED = ("ryanmen", "multi")
TRADE_TURN = 11
TRADE_LIVE = 6
BOOT = 400
# A series this thin is fitted as a straight line on the logit scale: AIC alone lets 30 hands bend a
# three-knot spline from certain to never.
SPLINE_MIN_HANDS = 100
SEED = 24
HAN = re.compile(r"\((\d+)飜\)")
# The turns the chapter names: (game, round, your turn).
EXAMPLES = [
    ("261001-45a82545-fd6f-4c20-8bb0-63b7c10ec22b", "East 2-3", 11),
    ("260930-f5119e21-21f2-4600-9de2-d28bb0a16427", "South 2-0", 11),
    ("260930-ce150fc2-e87e-4953-8ee4-76b25f7a61c6", "South 4-0", 12),
    ("261001-e54fc15b-92d2-4286-b911-41ba6d0629ca", "East 1-0", 13),
    ("260930-f5119e21-21f2-4600-9de2-d28bb0a16427", "East 4-0", 12),
    ("261001-45a82545-fd6f-4c20-8bb0-63b7c10ec22b", "South 1-0", 7),
]


# --- first closed tenpais ------------------------------------------------------------------------------

def ron_points(han: int, fu: int) -> int:
    """A non-dealer ron: the limits from 5 han, a mangan from 4 han at 40 fu or 3 han at 70."""
    if han >= 13:
        return 32000
    if han >= 11:
        return 24000
    if han >= 8:
        return 16000
    if han >= 6:
        return 12000
    if han <= 0:
        return 0
    base = fu * 2 ** (han + 2)
    return 8000 if han >= 5 or base >= 2000 else int(math.ceil(base * 4 / 100) * 100)


def first_tenpais(path: str, hero_only: bool = True) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if hero_only and not r["lj"]:
                continue
            if not (r["first"] and r["kept"] and r["left"] >= 4 and r["score"] >= 1000):
                continue
            opt = next((o for o in r["opts"] if o["b"] == r["cut"]), None)
            if opt is None or opt["fur"]:
                continue
            out.append({"g": r["g"], "li": r["li"], "t": r["t"], "dl": r["dl"], "nr": r["nr"], "no": r["no"],
                        "riichi": bool(r["riichi"]), "v": opt["dama_min"], "vmax": opt["dama_max"], "live": opt["live"],
                        "two": opt["shape"] in TWO_SIDED, "won": r["won"], "tsumo": r["tsumo"], "dealt": r["dealt"],
                        "net": r["net"], "points": min(ron_points(h, f) for h, f in zip(opt["dama_han"], opt["dama_fu"]))})
    return out


def cell(r: dict) -> str:
    if r["v"] == 0:
        return "some waits" if r["vmax"] > 0 else "no yaku"
    if r["v"] <= 2:
        return "1-2"
    if not r["two"]:
        return f"{'5+' if r['v'] >= 5 else r['v']} other"
    if r["v"] >= 5:
        return "5+ two-sided"
    if r["v"] == 4:
        return "4 two-sided"
    return "two-sided 3,900" if r["points"] < 5200 else "two-sided 5,200"


CELLS = ["no yaku", "some waits", "1-2", "two-sided 3,900", "two-sided 5,200", "4 two-sided", "5+ two-sided",
         "3 other", "4 other", "5+ other"]
CURVE_CELLS = {"3": "two-sided 3,900", "4": "4 two-sided", "5": "5+ two-sided"}


def turn_offsets(rows: list[dict]) -> dict:
    """LuckyJ's two-sided 4+ han tenpais in one logistic model with a common turn slope: does a 4-han hand at
    40 fu (a mangan by ron) or a hand of 5 han or more get declared less than a 4-han pinfu at the same turn?"""
    keep = [r for r in rows if r["nr"] == 0 and r["two"] and r["v"] >= 4]
    x = np.array([[1.0, r["t"] - 9.0, float(r["v"] == 4 and r["points"] >= 8000), float(r["v"] >= 5)] for r in keep])
    y = np.array([float(r["riichi"]) for r in keep])
    beta = np.zeros(4)
    for _ in range(100):
        mu = 1 / (1 + np.exp(-(x @ beta)))
        step = np.linalg.solve((x.T * (mu * (1 - mu))) @ x, x.T @ (y - mu))
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    mu = 1 / (1 + np.exp(-(x @ beta)))
    se = np.sqrt(np.diag(np.linalg.inv((x.T * (mu * (1 - mu))) @ x)))
    counts = {"4 pinfu": [r for r in keep if r["v"] == 4 and r["points"] < 8000],
              "4 at 40 fu": [r for r in keep if r["v"] == 4 and r["points"] >= 8000], "5+": [r for r in keep if r["v"] >= 5]}
    return {"hands": len(keep), "per_turn": [round(float(beta[1]), 3), round(float(se[1]), 3)],
            "4 at 40 fu": [round(float(beta[2]), 3), round(float(se[2]), 3)], "5+": [round(float(beta[3]), 3), round(float(se[3]), 3)],
            "declared": {k: [sum(r["riichi"] for r in v), len(v)] for k, v in counts.items()}}


def rate(rows: list[dict]) -> dict:
    n = len(rows)
    k = sum(r["riichi"] for r in rows)
    return {"n": n, "declared": k, "pct": round(100 * k / n, 1) if n else None}


# --- LuckyJ's riichi share by turn ---------------------------------------------------------------------

def turn_curve(rows: list[dict]) -> dict:
    turns = sorted(r["t"] for r in rows)
    lo = turns[int(0.05 * (len(turns) - 1))]
    hi = turns[int(math.ceil(0.95 * (len(turns) - 1)))]
    by = defaultdict(lambda: [0, 0])
    for r in rows:
        by[r["t"]][0] += r["riichi"]
        by[r["t"]][1] += 1
    points = [[t, k, n] for t, (k, n) in sorted(by.items())]
    saved = timing.FIT_DFS
    timing.FIT_DFS = saved if len(rows) >= SPLINE_MIN_HANDS else (1,)
    try:
        fit = fit_series([{"turn": t, "lj_k": k, "lj_n": n} for t, k, n in points], "lj", lo, hi)
    finally:
        timing.FIT_DFS = saved
    at = {str(round(g[0])): g[1:] for g in fit["grid"] if abs(g[0] - round(g[0])) < 1e-9}
    return {"range": [lo, hi], "points": points, "df": fit["df"], "dispersion": fit["dispersion"],
            "crossings_50": fit["crossings_50"], "grid": fit["grid"], "at": at, "hands": len(rows)}


# --- Mortal on your turns ------------------------------------------------------------------------------

_games: dict[str, dict] = {}


def replay(g: str) -> dict:
    if g not in _games:
        _games[g] = json.loads((REPLAYS / f"{g}.json").read_text())
    return _games[g]


def turn_marks(hand: dict, hero: int) -> list[int]:
    turn, turns = 0, []
    for e in hand["ev"]:
        if e[1] == hero and ((e[0] == "t" and len(e) < 4) or e[0] in ("c", "p", "m")):
            turn += 1
        turns.append(turn)
    return turns


def mortal_at(g: str, li: int, t: int) -> dict:
    """Mortal's weight on riichi, and its first choice, on your draw at turn t."""
    game = replay(g)
    hand = game["hands"][li]
    turns = turn_marks(hand, game["hero"])
    for a in hand["ai"]:
        if turns[a["i"]] == t and a["p"][0][0] != "pass" and not a["p"][0][0].startswith(("chi", "pon", "kan")):
            weights = dict(a["p"])
            return {"riichi": weights.get("riichi", 0.0), "first": a["p"][0], "top": a["p"][:3], "you": a["you"]}
    raise SystemExit(f"no Mortal draw decision at {g} hand {li} turn {t}")


# --- the trade at one turn -----------------------------------------------------------------------------

def pts(han: int, tsumo: bool) -> int:
    """Non-dealer points; 3 and 4 han at 30 fu."""
    if han >= 13:
        return 32000
    if han >= 11:
        return 24000
    if han >= 8:
        return 16000
    if han >= 6:
        return 12000
    if han == 5:
        return 8000
    return {(4, False): 7700, (4, True): 7900, (3, False): 3900, (3, True): 4000}[(han, tsumo)]


def win_values(han: int, extra: dict, mangan_ron: bool = False) -> dict:
    """A ron and a tsumo, dama and riichi; menzen tsumo adds a han either way, a riichi win its ura and ippatsu.

    With ``mangan_ron`` the hand is 4 han at 40 fu: its dama ron is a mangan already.
    """
    return {
        "dama_ron": 8000 if mangan_ron else pts(han, False),
        "dama_tsumo": pts(han + 1, True),
        "riichi_ron": round(sum(p * pts(han + 1 + x, False) for x, p in enumerate(extra["ron"]))),
        "riichi_tsumo": round(sum(p * pts(han + 2 + x, True) for x, p in enumerate(extra["tsumo"]))),
    }


LO_T, HI_T = 3, 16


def _basis(t: np.ndarray, knots: list[float]) -> np.ndarray:
    x = (np.clip(t, LO_T, HI_T) - LO_T) / (HI_T - LO_T)
    return np.array([_ns_row(float(v), knots) for v in x])


def _design(t, live, dl, knots) -> np.ndarray:
    return np.column_stack([_basis(np.asarray(t, float), knots), np.asarray(live, float) - TRADE_LIVE, np.asarray(dl, float)])


def _logit(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    beta = np.zeros(x.shape[1])
    p = min(max(float(y.mean()), 1e-3), 1 - 1e-3)
    beta[0] = math.log(p / (1 - p))
    for _ in range(100):
        eta = x @ beta
        mu = 1 / (1 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-9, None)
        new = np.linalg.solve((x.T * w) @ x + 1e-8 * np.eye(x.shape[1]), (x.T * w) @ (eta + (y - mu) / w))
        if np.max(np.abs(new - beta)) < 1e-10:
            beta = new
            break
        beta = new
    mu = np.clip(1 / (1 + np.exp(-(x @ beta))), 1e-12, 1 - 1e-12)
    return beta, float(-2 * np.sum(y * np.log(mu) + (1 - y) * np.log(1 - mu)) + 2 * x.shape[1])


def _knots(df: int) -> list[float]:
    return [0.0] + [i / df for i in range(1, df)] + [1.0]


class Group:
    """Ron, tsumo and the result of a hand that does not win, for one choice, as functions of the turn."""

    def __init__(self, rows: list[dict], dfs: dict | None = None):
        t = np.array([r["t"] for r in rows], float)
        live = np.array([r["live"] for r in rows], float)
        dl = np.array([r["dl"] for r in rows], float)
        ron = np.array([r["won"] and not r["tsumo"] for r in rows], float)
        tsumo = np.array([bool(r["tsumo"]) for r in rows], float)
        self.dfs = dfs or {}
        self.beta = {}
        for name, y in (("ron", ron), ("tsumo", tsumo)):
            if name not in self.dfs:
                self.dfs[name] = min((1, 2, 3), key=lambda df: _logit(_design(t, live, dl, _knots(df)), y)[1])
            self.beta[name] = _logit(_design(t, live, dl, _knots(self.dfs[name])), y)[0]
        lost = [r for r in rows if not r["won"]]
        xl = np.column_stack([np.ones(len(lost)), [r["t"] - TRADE_TURN for r in lost], [r["dl"] for r in lost]])
        self.lost = np.linalg.lstsq(xl, np.array([r["net"] for r in lost], float), rcond=None)[0]
        self.n = len(rows)

    def at(self, turn: float) -> dict:
        out = {}
        for name in ("ron", "tsumo"):
            x = _design([turn], [TRADE_LIVE], [0.0], _knots(self.dfs[name]))
            out[name] = float(1 / (1 + np.exp(-(x @ self.beta[name])[0])))
        out["lost"] = float(self.lost[0] + self.lost[1] * (turn - TRADE_TURN))
        return out


def expected(rates: dict, values: dict, choice: str) -> float:
    r = rates
    return r["ron"] * values[f"{choice}_ron"] + r["tsumo"] * values[f"{choice}_tsumo"] + (1 - r["ron"] - r["tsumo"]) * r["lost"]


def trade(rows: list[dict], extra: dict, dama_from: int) -> dict:
    """Riichi against dama for a two-sided non-dealer hand at TRADE_TURN, with a game bootstrap."""
    pool = [r for r in rows if r["nr"] == 0 and r["two"] and r["v"] >= 1]
    riichi = [r for r in pool if r["riichi"]]
    dama = [r for r in pool if not r["riichi"] and r["v"] >= dama_from]
    gr, gd = Group(riichi), Group(dama, None)
    rr, rd = gr.at(TRADE_TURN), gd.at(TRADE_TURN)
    out = {"riichi_hands": len(riichi), "dama_hands": len(dama), "dfs": {"riichi": gr.dfs, "dama": gd.dfs},
           "riichi": {k: round(v, 4) for k, v in rr.items()}, "dama": {k: round(v, 4) for k, v in rd.items()}, "hands": {},
           "riichi_by_turn": {str(t): {k: round(v, 4) for k, v in gr.at(t).items()} for t in (5, 7, 9, 11, 13)}}
    by_game = defaultdict(list)
    for r in pool:
        by_game[r["g"]].append(r)
    games = sorted(by_game)
    rng = np.random.default_rng(SEED)
    hands = {"5": win_values(5, extra), "4 at 40 fu": win_values(4, extra, mangan_ron=True), "4 pinfu": win_values(4, extra)}
    boots = {key: [] for key in hands}
    for _ in range(BOOT):
        pick = rng.integers(0, len(games), len(games))
        sample = [r for i in pick for r in by_game[games[i]]]
        br = Group([r for r in sample if r["riichi"]], dict(gr.dfs)).at(TRADE_TURN)
        bd = Group([r for r in sample if not r["riichi"] and r["v"] >= dama_from], dict(gd.dfs)).at(TRADE_TURN)
        for key, values in hands.items():
            boots[key].append(expected(br, values, "riichi") - expected(bd, values, "dama"))
    for key, values in hands.items():
        er, ed = expected(rr, values, "riichi"), expected(rd, values, "dama")
        lo, hi = np.percentile(boots[key], [2.5, 97.5])
        out["hands"][key] = {"values": values, "riichi": round(er), "dama": round(ed), "difference": round(er - ed),
                             "band": [round(float(lo)), round(float(hi))]}
    return out


# --- ura dora and ippatsu ------------------------------------------------------------------------------

def extra_han(manifest: list[dict]) -> dict:
    counts = {"ron": Counter(), "tsumo": Counter()}
    for g in manifest:
        for log in json.load(open(ROOT / g["file"]))["log"]:
            for _, det in tr.result_blocks(log[-1]):
                yaku = {}
                for entry in det[4:]:
                    name = entry.split("(")[0].strip()
                    if name.startswith("yaku") and name[4:].isdigit():
                        name = TENHOU_YAKU.get(int(name[4:]), name)
                    m = HAN.search(entry)
                    yaku[name] = int(m.group(1)) if m else 0
                if "立直" not in yaku and "ダブル立直" not in yaku:
                    continue
                extra = yaku.get("裏ドラ", 0) + yaku.get("一発", 0)
                counts["tsumo" if det[0] == det[1] else "ron"][min(extra, 3)] += 1
    out = {}
    for kind, c in counts.items():
        n = sum(c.values())
        out[kind] = [round(c[i] / n, 4) for i in range(4)]
        out[f"{kind}_wins"] = n
    return out


# --- your riichis --------------------------------------------------------------------------------------

def your_riichis(path: str, dates: dict) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["lj"] and r["riichi"]:
                out.append({"g": r["g"], "li": r["li"], "t": r["t"], "date": dates[r["g"]], "won": r["won"], "dealt": r["dealt"]})
    return out


def hands_in(manifest: list[dict]) -> dict[str, int]:
    return {g["uuid"].split("#")[0]: len(json.load(open(ROOT / g["file"]))["log"]) for g in manifest}


def main() -> None:
    your_tenpai, lj_tenpai, lj_manifest_path, out_path = sys.argv[1:5]
    lj_manifest = json.load(open(lj_manifest_path))
    your_manifest = [g for g in json.load(open(YOUR_MANIFEST)) if g["date"] >= SINCE]
    dates = {g["uuid"]: g["date"] for g in your_manifest}

    lj = first_tenpais(lj_tenpai)
    quiet = [r for r in lj if r["nr"] == 0]
    cells = {c: rate([r for r in quiet if cell(r) == c]) for c in CELLS}
    curves = {key: turn_curve([r for r in quiet if cell(r) == name]) for key, name in CURVE_CELLS.items()}

    def lj_rate(r: dict) -> float:
        name = cell(r)
        for key, curve_name in CURVE_CELLS.items():
            if name == curve_name:
                curve = curves[key]
                t = min(max(r["t"], curve["range"][0]), curve["range"][1])
                return curve["at"][str(t)][0] / 100
        return cells[name]["pct"] / 100

    you = first_tenpais(your_tenpai)
    for r in you:
        r["date"] = dates[r["g"]]
    big = [r for r in you if r["nr"] == 0 and r["v"] >= 3]
    periods = {"before": lambda r: r["date"] < RECENT_FROM, "recent": lambda r: r["date"] >= RECENT_FROM,
               "newest": lambda r: r["date"] >= NEWEST_FROM}
    your_big = {}
    for name, keep in periods.items():
        rows = [r for r in big if keep(r)]
        block = {"hands": len(rows), "declared": sum(r["riichi"] for r in rows),
                 "luckyj_expects": round(sum(lj_rate(r) for r in rows), 2)}
        if name != "before":
            block["mortal_expects"] = round(sum(mortal_at(r["g"], r["li"], r["t"])["riichi"] for r in rows), 2)
            block["turns"] = [{"g": r["g"], "li": r["li"], "t": r["t"], "v": r["v"], "two": r["two"], "riichi": r["riichi"],
                               "luckyj": round(lj_rate(r), 3), "mortal": round(mortal_at(r["g"], r["li"], r["t"])["riichi"], 3)}
                              for r in rows]
        your_big[name] = block

    hands = hands_in(your_manifest)
    lj_hands = sum(hands_in(lj_manifest).values())
    riichis = your_riichis(your_tenpai, dates)
    per100 = {}
    for name, keep in periods.items():
        games = {g for g, d in dates.items() if keep({"date": d})}
        n_hands = sum(hands[g] for g in games)
        rs = [r for r in riichis if r["g"] in games]
        firsts = [r for r in you if r["g"] in games]
        per100[name] = {"games": len(games), "hands": n_hands, "riichis": len(rs), "riichis_per_100": round(100 * len(rs) / n_hands, 1),
                        "first_tenpais": len(firsts), "first_tenpais_per_100": round(100 * len(firsts) / n_hands, 1),
                        "first_declared_pct": round(100 * sum(r["riichi"] for r in firsts) / len(firsts), 1)}
        if name != "before":
            per100[name]["first_mortal_pct"] = round(100 * sum(mortal_at(r["g"], r["li"], r["t"])["riichi"] for r in firsts) / len(firsts), 1)
    lj_riichi_rows = [r for line in open(lj_tenpai) if (r := json.loads(line))["lj"] and r["riichi"]]
    lj_riichis = len(lj_riichi_rows)
    per100["luckyj"] = {"hands": lj_hands, "riichis": lj_riichis, "riichis_per_100": round(100 * lj_riichis / lj_hands, 1),
                        "riichis_won_pct": round(100 * sum(r["won"] for r in lj_riichi_rows) / lj_riichis, 1),
                        "first_tenpais_per_100": round(100 * len(lj) / lj_hands, 1),
                        "first_declared_pct": round(100 * sum(r["riichi"] for r in lj) / len(lj), 1)}
    newest = [r for r in riichis if r["date"] >= NEWEST_FROM]
    newest_out = {"riichis": len(newest), "won": sum(r["won"] for r in newest), "dealt": sum(r["dealt"] for r in newest),
                  "dealt_mortal": sorted(round(mortal_at(r["g"], r["li"], r["t"])["riichi"], 3) for r in newest if r["dealt"])}
    newest_out["neither"] = newest_out["riichis"] - newest_out["won"] - newest_out["dealt"]

    extra = extra_han(lj_manifest)
    everyone = first_tenpais(lj_tenpai, hero_only=False)
    trades = {"dama 4+": trade(everyone, extra, 4), "dama 3+": trade(everyone, extra, 3)}

    chase_rows = [r for r in lj if r["nr"] >= 1 and r["live"] <= 3]
    chase = {"no yaku": rate([r for r in chase_rows if r["v"] == 0]),
             "1-2": rate([r for r in chase_rows if 1 <= r["v"] <= 2]),
             "3": rate([r for r in chase_rows if r["v"] == 3]),
             "4+": rate([r for r in chase_rows if r["v"] >= 4])}

    # Chapter 23 counted a hand by its best winning tile, against callers, from the 10th turn.
    late_callers = [r for r in quiet if r["no"] > 0 and r["t"] >= 10]
    ch23 = {"best tile 5+": rate([r for r in late_callers if r["vmax"] >= 5]),
            "every tile 5+": rate([r for r in late_callers if r["v"] >= 5])}

    examples = []
    for g, rnd, t in EXAMPLES:
        game = replay(g)
        li = next(i for i, h in enumerate(game["hands"]) if h["round"] == rnd)
        m = mortal_at(g, li, t)
        examples.append({"g": g, "round": rnd, "t": t, "mortal_riichi": round(m["riichi"], 3), "mortal_first": m["first"],
                         "mortal_top": m["top"], "you": m["you"]})

    out = {
        "cutoffs": {"since": SINCE, "recent_from": RECENT_FROM, "newest_from": NEWEST_FROM},
        "luckyj_games": len(lj_manifest),
        "luckyj_first_tenpais_quiet": len(quiet),
        "cells": cells,
        "curves": curves,
        "turn_offsets": turn_offsets(lj),
        "you": {"big": your_big, "per_100": per100, "newest_riichis": newest_out},
        "extra_han": extra,
        "trade": {"turn": TRADE_TURN, "live": TRADE_LIVE, **trades},
        "chase": chase,
        "chapter23_definitions": ch23,
        "examples": examples,
    }
    Path(out_path).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: out[k] for k in ("cells", "chase", "chapter23_definitions")}, indent=1))
    for key, c in curves.items():
        print(key, "hands", c["hands"], "range", c["range"], "df", c["df"], "crossings", c["crossings_50"],
              {t: c["at"][str(t)][0] for t in range(c["range"][0], c["range"][1] + 1)})
    print(json.dumps(out["you"], indent=1)[:3000])
    print(json.dumps(out["trade"], indent=1))
    print(json.dumps(out["extra_han"]), json.dumps(out["examples"]))


if __name__ == "__main__":
    main()
