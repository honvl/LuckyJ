#!/usr/bin/env python3
"""The figures behind guide chapter 33: what changed between the climb and the games since.

The climb is the user's run to the peak of their rank points: from the lowest point in the ten days before the peak
(23 September 18:40, 3,972) to the peak itself (1 October 22:20, 6,749). "Since" is every game after the peak, and
"before" every game from 1 January to the climb. Rank points come from amae-koromo's records, anchored at 6,700
before the 3 October 14:11 game (chapter 27).

- places and rank points a game in each period;
- hands (``contrast/hands_all.py``): wins, deal-ins, points a hand, riichis and riichi wins per 100 hands, and
  deal-ins by the user's state (in their own riichi, tenpai without one, not tenpai) and the winner's hand (riichi,
  open, dama), per 100 hands; LuckyJ's 1,079 Tokujou games for comparison;
- defense against a riichi (``mine_riichi_folds.py`` rows): how often a live tile went out where a safe tile kept the
  shanten, by the best shanten, and deal-ins per 100 discards facing a riichi; tenpai against a riichi with every
  tenpai tile unsafe (``mine_tenpai_push.py`` rows): how often the tenpai was kept, and what that earned. LuckyJ's
  rows here come from all 1,255 of its games, as in chapters 26 and 30;
- riichi (``contrast/tenpai.py`` rows, chapter 24's first closed tenpais: riichi legal, wait not furiten, nobody in
  riichi): how many the user declared against LuckyJ's rate for a hand of the same value and wait (chapter 24's
  cells), live tiles, turn, seat and calls across the table. The rate is a logistic fit over LuckyJ's own 2,177
  such tenpais (``model``); it is checked against LuckyJ's actual rates by turn and by live tiles (``calibration``).
  Per period, per stretch between the guide chapters that spoke about dama, early and late;
- LuckyJ's first tenpais from its 13th turn, cheap (no yaku, or 1 or 2 han on every winning tile) and big, and the
  results of riichis declared from the 13th turn, the user's and LuckyJ's;
- the card turns with LuckyJ's rate.

usage: mine_climb_check.py RF_YOU RF_LJ TP_YOU TP_LJ TENPAI_YOU TENPAI_LJ OUT.json
  RF_*: ``mine_riichi_folds.py compute``; TP_*: ``mine_tenpai_push.py compute``; TENPAI_*: ``contrast/tenpai.py``.
  The user's three are over their games since 1 January, LuckyJ's TENPAI over its Tokujou games. Run it from the main
  checkout with the project venv (the hand rows are computed here, from the manifests' log paths).
"""

from __future__ import annotations

import datetime
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import mine_costly_run as mc  # noqa: E402
import mine_dama_value as dv  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
AMAE = ROOT / "data/self_games/majsoul/amae-koromo-records.json"
ACCOUNT = 120182062
ANCHOR_GAME, ANCHOR = "261004-3d4685b3", 6700  # chapter 27's rank points before the 3 October 14:11 game
SINCE = "2026-01-01"
PERIODS = ("before", "climb", "since")
# when the chapters that spoke about dama went live (their commits), against the games' local start times
STRETCHES = (("to chapter 24", "", "2026-10-01 14:17"), ("chapters 24 to 29", "2026-10-01 14:17", "2026-10-07 18:09"),
             ("chapters 29 to 31", "2026-10-07 18:09", "2026-10-10 18:11"), ("since chapter 31", "2026-10-10 18:11", "9999"))
LATE = 13
CELLS = [c for c in dv.CELLS if c != "1-2"]  # 1 or 2 han is the base of the fit
FEATURES = ["constant"] + CELLS + ["live tiles (to 8), from 5", "2 live tiles or fewer", "turn, from 9", "turns past 12",
                                   "turn, from 9, for a two-sided hand of 4 han or more", "dealer",
                                   "an opponent on 2 calls or more"]
EXAMPLES = (("261002-fc3b2f83", "South 2-0", 15), ("261003-2f0295b7", "South 1-0", 12),
            ("261011-e0215b87", "South 2-0", 14), ("261011-d33a542c", "South 1-1", 10))
BANDS = {"tenpai": lambda b: b == 0, "one": lambda b: b == 1, "two_or_more": lambda b: b >= 2}


def pct(k: float, n: int, digits: int = 1) -> float | None:
    return round(100 * k / n, digits) if n else None


# --- the rank path ---------------------------------------------------------------------------------------

def rank_path() -> dict:
    recs = sorted(json.loads(AMAE.read_text())["records"], key=lambda r: r[1])
    deltas = [next(p for p in r[4] if p[0] == ACCOUNT)[4] for r in recs]
    anchor = next(k for k, r in enumerate(recs) if r[0].startswith(ANCHOR_GAME))
    before = [0] * len(recs)
    before[anchor] = ANCHOR
    for k in range(anchor + 1, len(recs)):
        before[k] = before[k - 1] + deltas[k - 1]
    for k in range(anchor - 1, -1, -1):
        before[k] = before[k + 1] - deltas[k]
    after = [b + d for b, d in zip(before, deltas)]
    peak = max(range(len(recs)), key=lambda k: after[k])
    window = [k for k in range(len(recs)) if recs[peak][1] - 10 * 86400 <= recs[k][1] <= recs[peak][1]]
    start = min(window, key=lambda k: before[k])
    since = datetime.datetime.fromisoformat(SINCE).timestamp()
    place = lambda k: sorted(recs[k][4], key=lambda p: -p[3]).index(next(p for p in recs[k][4] if p[0] == ACCOUNT)) + 1
    when = lambda k: datetime.datetime.fromtimestamp(recs[k][1]).strftime("%Y-%m-%d %H:%M")
    spans = {"before": [k for k in range(start) if recs[k][1] >= since], "climb": range(start, peak + 1),
             "since": range(peak + 1, len(recs))}
    periods = {}
    for name, ks in spans.items():
        places = [place(k) for k in ks]
        periods[name] = {"games": len(places), "places": [places.count(i) for i in (1, 2, 3, 4)],
                         "average": round(sum(places) / len(places), 2),
                         "points_a_game": round(sum(deltas[k] for k in ks) / len(places), 1)}
    return {"start": {"game": recs[start][0], "date": when(start), "points": before[start]},
            "peak": {"game": recs[peak][0], "date": when(peak), "points": after[peak]},
            "now": {"date": when(len(recs) - 1), "points": after[-1]}, "periods": periods}


def period_of(manifest: list[dict], rank: dict) -> dict[str, str]:
    start = next(k for k, g in enumerate(manifest) if g["uuid"] == rank["start"]["game"])
    peak = next(k for k, g in enumerate(manifest) if g["uuid"] == rank["peak"]["game"])
    return {g["uuid"]: "before" if k < start else "climb" if k <= peak else "since" for k, g in enumerate(manifest)}


# --- hands -----------------------------------------------------------------------------------------------

def hands(rows: list[dict]) -> dict:
    h = mc.hand_summary(rows)
    n = h["hands"]
    riichi = [r for r in rows if r["riichi_turn"] is not None]
    return {"hands": n, "won": round(100 * h["won_rate"], 1), "avg_win": round(h["avg_win"]),
            "dealt_in": round(100 * h["deal_in_rate"], 1), "avg_deal_in": round(-h["avg_deal_in"]),
            "big_deal_ins_per_100": round(100 * h["big_deal_in_rate"], 1), "points_a_hand": round(h["points_a_hand"]),
            "riichis_per_100": pct(len(riichi), n), "riichi_wins_per_100": pct(sum(r["won"] for r in riichi), n),
            "opened": pct(sum(r["open"] for r in rows), n)}


def deal_in_state(r: dict) -> str:
    if r["riichi_turn"] is not None and r["riichi_turn"] <= r["deal_in_turn"]:
        return "in your own riichi"
    shanten = r["shanten_by_turn"][min(r["deal_in_turn"], len(r["shanten_by_turn"])) - 1]
    return "tenpai, no riichi" if shanten == 0 else "not tenpai"


def deal_ins(rows: list[dict]) -> dict:
    n = len(rows)
    c = Counter((deal_in_state(r), r["deal_in_into"]) for r in rows if r["dealt_in"])
    return {f"{state} into {into}": {"deal_ins": k, "per_100": pct(k, n)} for (state, into), k in sorted(c.items())}


# --- defense ---------------------------------------------------------------------------------------------

def riichi_defense(rows: list[dict]) -> dict:
    out = {}
    for name, keep in BANDS.items():
        s = [r for r in rows if r["keep_safe"] and keep(r["best"])]
        out[name] = {"turns": len(s), "live": pct(sum(r["push"] for r in s), len(s))}
    dealt = sum(1 for r in rows if r["dealt"])
    out.update(discards=len(rows), dealt=dealt, dealt_per_100=pct(dealt, len(rows), 2))
    return out


def tenpai_push(rows: list[dict]) -> dict:
    pushed = [r for r in rows if r["pushed"]]
    folded = [r for r in rows if not r["pushed"]]
    avg = lambda rs: round(sum(r["delta"] for r in rs) / len(rs)) if rs else None
    return {"hands": len(rows), "pushed": len(pushed), "pushed_pct": pct(len(pushed), len(rows)),
            "pushed_won": pct(sum(r["won"] for r in pushed), len(pushed), 0),
            "pushed_dealt": pct(sum(r["dealt"] for r in pushed), len(pushed), 0),
            "pushed_avg": avg(pushed), "folded_avg": avg(folded)}


# --- riichi ----------------------------------------------------------------------------------------------

def first_tenpais(path: str) -> list[dict]:
    """Chapter 24's first closed tenpais (``dv.first_tenpais``) with the round, the wall and the calls across the table."""
    extra = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["lj"] and r["first"]:
                extra[(r["g"], r["li"], r["t"])] = {"k": r["k"], "h": r["h"], "mo": r["mo"], "left": r["left"]}
    rows = dv.first_tenpais(path)
    for r in rows:
        x = extra[(r["g"], r["li"], r["t"])]
        r.update(x, round=f"{'East' if x['k'] < 4 else 'South'} {x['k'] % 4 + 1}-{x['h']}", cell=dv.cell(r))
    return rows


def features(r: dict) -> list[float]:
    big = float(r["two"] and r["v"] >= 4)
    return ([1.0] + [float(r["cell"] == c) for c in CELLS] +
            [min(r["live"], 8) - 5, float(r["live"] <= 2), r["t"] - 9, max(0, r["t"] - 12), big * (r["t"] - 9),
             float(r["dl"]), float(r["mo"] >= 2)])


def fit(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    x = np.array([features(r) for r in rows])
    y = np.array([float(r["riichi"]) for r in rows])
    beta = np.zeros(x.shape[1])
    for _ in range(100):
        mu = 1 / (1 + np.exp(-(x @ beta)))
        step = np.linalg.solve((x.T * (mu * (1 - mu))) @ x, x.T @ (y - mu))
        beta = beta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    mu = 1 / (1 + np.exp(-(x @ beta)))
    se = np.sqrt(np.diag(np.linalg.inv((x.T * (mu * (1 - mu))) @ x)))
    return beta, se


def declared(rows: list[dict], rate) -> dict:
    """Riichis declared against the sum of LuckyJ's rates, and the gap in standard deviations of that sum."""
    k, e = sum(r["riichi"] for r in rows), sum(rate(r) for r in rows)
    var = sum(rate(r) * (1 - rate(r)) for r in rows)
    return {"tenpais": len(rows), "declared": k, "declared_pct": pct(k, len(rows)), "luckyj": round(e, 1),
            "luckyj_pct": pct(e, len(rows)), "sd": round((k - e) / var ** 0.5, 1) if var else None}


def outcome(rows: list[dict]) -> dict:
    n = len(rows)
    return {"n": n, "wins": sum(r["won"] for r in rows), "won": pct(sum(r["won"] for r in rows), n, 0), "tsumo": sum(bool(r["tsumo"]) for r in rows if r["won"]),
            "dealt": pct(sum(r["dealt"] for r in rows), n, 0), "net": round(sum(r["net"] for r in rows) / n) if n else None,
            "live": round(sum(r["live"] for r in rows) / n, 2) if n else None,
            "turn": round(sum(r["t"] for r in rows) / n, 1) if n else None}


def late_riichis(path: str) -> dict:
    """Every riichi declared from the 13th turn, first tenpai or not, with the live tiles of the wait it chose."""
    rows = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["lj"] and r["riichi"] and r["t"] >= LATE:
                opt = next((o for o in r["opts"] if o["b"] == r["cut"]), None)
                rows.append({"won": r["won"], "tsumo": r["tsumo"], "dealt": r["dealt"], "net": r["net"], "t": r["t"],
                             "live": opt["live"] if opt else 0, "left": r["left"]})
    out = outcome(rows)
    out["wall"] = round(sum(r["left"] for r in rows) / len(rows), 1)
    return out


def main() -> None:
    rf_you, rf_lj, tp_you, tp_lj, tenpai_you, tenpai_lj, out_path = sys.argv[1:8]
    manifest = sorted([g for g in json.loads(MANIFEST.read_text(encoding="utf-8")) if g["date"] >= SINCE],
                      key=lambda g: g["start_time"])
    date = {g["uuid"]: g["date"] for g in manifest}
    rank = rank_path()
    per = period_of(manifest, rank)

    mine = mc.hero_rows(mc.hand_rows(manifest, "me"), manifest)
    lj_manifest = [g for g in json.loads(LJ_MANIFEST.read_text(encoding="utf-8")) if g["mode"] == "tenhou-tokujou"]
    lj_hands = [r for r in mc.hand_rows(lj_manifest, "lj") if r["lj"]]
    by = lambda rows, p, key="game": [r for r in rows if per.get(r[key]) == p]

    rf, rfl = json.load(open(rf_you))["rows"], json.load(open(rf_lj))["rows"]
    tp, tpl = json.load(open(tp_you))["rows"], json.load(open(tp_lj))["rows"]

    lj_first = [r for r in first_tenpais(tenpai_lj) if r["nr"] == 0]
    beta, se = fit(lj_first)
    rate = lambda r: float(1 / (1 + np.exp(-np.dot(features(r), beta))))
    calibration = {}
    for name, keep in (("turns 1-9", lambda r: r["t"] <= 9), ("turns 10-12", lambda r: 10 <= r["t"] <= 12),
                       ("turn 13 on", lambda r: r["t"] >= LATE), ("2 live or fewer", lambda r: r["live"] <= 2),
                       ("3 live", lambda r: r["live"] == 3), ("4-5 live", lambda r: 4 <= r["live"] <= 5),
                       ("6 live or more", lambda r: r["live"] >= 6), ("an opponent on 2+ calls", lambda r: r["mo"] >= 2)):
        s = [r for r in lj_first if keep(r)]
        calibration[name] = {"tenpais": len(s), "actual": pct(sum(r["riichi"] for r in s), len(s)),
                             "fit": pct(sum(rate(r) for r in s), len(s))}
    you_first = [r for r in first_tenpais(tenpai_you) if r["nr"] == 0]
    for r in you_first:
        r["date"], r["period"] = date[r["g"]], per[r["g"]]

    riichi = {"model": {"tenpais": len(lj_first), "declared_pct": pct(sum(r["riichi"] for r in lj_first), len(lj_first)),
                        "terms": {n: [round(float(b), 3), round(float(s), 3)] for n, b, s in zip(FEATURES, beta, se)},
                        "calibration": calibration},
              "periods": {}, "stretches": {}}
    for p in PERIODS:
        rows = [r for r in you_first if r["period"] == p]
        block = declared(rows, rate)
        block["by_turn"] = {"to 12": declared([r for r in rows if r["t"] < LATE], rate),
                            "13 on": declared([r for r in rows if r["t"] >= LATE], rate)}
        block["cells"] = {c: declared([r for r in rows if r["cell"] == c], rate) for c in dv.CELLS
                          if any(r["cell"] == c for r in rows)}
        block["cheap"] = declared([r for r in rows if r["v"] <= 2], rate)
        block["big"] = declared([r for r in rows if r["v"] >= 3], rate)
        riichi["periods"][p] = block
    for name, lo, hi in STRETCHES:
        rows = [r for r in you_first if r["period"] != "before" and lo <= r["date"] < hi]
        riichi["stretches"][name] = dict(declared(rows, rate), games=len({r["g"] for r in rows}))

    late = [r for r in lj_first if r["t"] >= LATE]
    cheap, big = [r for r in late if r["v"] <= 2], [r for r in late if r["v"] >= 3]
    late_out = {
        "tenpais": len(late), "declared_pct": pct(sum(r["riichi"] for r in late), len(late)),
        "cheap": {"tenpais": len(cheap), "declared_pct": pct(sum(r["riichi"] for r in cheap), len(cheap))},
        "big": {"tenpais": len(big), "declared_pct": pct(sum(r["riichi"] for r in big), len(big))},
        "cheap_by_live": {name: {"tenpais": len(s), "declared_pct": pct(sum(r["riichi"] for r in s), len(s))}
                          for name, s in (("3 or fewer", [r for r in cheap if r["live"] <= 3]),
                                          ("4-5", [r for r in cheap if 4 <= r["live"] <= 5]),
                                          ("6 or more", [r for r in cheap if r["live"] >= 6]))},
        "first_tenpais": {"luckyj": {"riichi": outcome([r for r in late if r["riichi"]]),
                                     "dama": outcome([r for r in late if not r["riichi"]])}},
        "riichis": {"you": late_riichis(tenpai_you), "luckyj": late_riichis(tenpai_lj)},
    }
    you_all = [r for r in first_tenpais(tenpai_you) if r["t"] >= LATE]
    late_out["first_tenpais"]["you"] = {"riichi": outcome([r for r in you_all if r["riichi"]]),
                                        "dama": outcome([r for r in you_all if not r["riichi"]])}
    luckyj_all = [r for r in first_tenpais(tenpai_lj) if r["t"] >= LATE]
    late_out["first_tenpais"]["luckyj_all"] = {"riichi": outcome([r for r in luckyj_all if r["riichi"]]),
                                               "dama": outcome([r for r in luckyj_all if not r["riichi"]])}

    examples = []
    for g, rnd, t in EXAMPLES:
        r = next(r for r in you_first if r["g"].startswith(g) and r["round"] == rnd and r["t"] == t)
        examples.append({"game": r["g"], "date": r["date"], "period": r["period"], "round": rnd, "turn": t,
                         "declared": r["riichi"], "cell": r["cell"], "han": r["v"], "live": r["live"], "dealer": r["dl"],
                         "calls_across": r["mo"], "luckyj": round(rate(r), 3), "won": r["won"], "net": r["net"]})

    out = {
        "rank": rank,
        "hands": {**{p: hands(by(mine, p)) for p in PERIODS}, "luckyj": hands(lj_hands)},
        "deal_ins": {p: deal_ins(by(mine, p)) for p in PERIODS},
        "defense": {"riichi": {**{p: riichi_defense(by(rf, p)) for p in PERIODS}, "luckyj": riichi_defense(rfl)},
                    "tenpai_push": {**{p: tenpai_push(by(tp, p)) for p in PERIODS}, "luckyj": tenpai_push(tpl)}},
        "riichi": riichi,
        "late": late_out,
        "examples": examples,
    }
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
