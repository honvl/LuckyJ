#!/usr/bin/env python3
"""Pushes and folds against a riichi, measured in rank points instead of hand points (guide chapter 36).

A hand's points are the wrong measure when the question is not coming fourth: losing 2,000 points from first costs
little, from third it can cost a place. Each push-or-fold spot of ``mine_thin_pushes.py`` is valued by what the hand
did to the player's expected rank points (EV) for the game:

    EV change = EV at the start of the next hand - EV at the start of this one

and the same for the chance of finishing fourth, where the EV of a game state (the round, its honba, the four scores, whose seat is whose) is the mean Saint 3
Jade-room rank points over simulated finishes: (final score - 30,000) / 1000 plus 130, 65, 0 or -250, rounded up,
ties going to the seat nearer the first dealer. When the hand ended the game, the EV after it is the rank points the
player actually got.

The simulations draw whole hands (the four score changes, turned to the dealer's seat, and whether the dealer kept
the deal) at random from the user's own Mahjong Soul games since January, so the finishes follow the Jade tables'
hand values. A game ends as a Mahjong Soul south game does: below zero ends it; after South 4 it ends when someone
has 30,000 and the dealer did not keep the deal, or the dealer kept it as the top with 30,000; the West hands end as
soon as someone has 30,000, and West 4 ends it in any case.

LuckyJ's spots are valued the same way, on the same Jade model, so the two sides are measured with one ruler.

usage: mine_push_ev.py ROWS_YOU ROWS_LJ OUT.json
  ROWS_*: ``mine_thin_pushes.py compute`` over your games since 1 January and over LuckyJ's 1,255.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import tenhou_replay as tr  # noqa: E402
from mine_thin_pushes import is_thin  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
SINCE = "2026-01-01"
UMA = np.array([130, 65, 0, -250])
SIMS, SEED, MAX_HANDS = 4000, 1, 40
ROUNDS = ("East", "South", "West", "North")


def round_key(name: str) -> tuple[int, int]:
    """'South 2-1' -> (kyoku index 5, honba 1)."""
    wind, rest = name.split()
    number, honba = rest.split("-")
    return ROUNDS.index(wind) * 4 + int(number) - 1, int(honba)


def game_hands(g: dict) -> list[dict]:
    """Each hand's kyoku index, honba and starting scores, with the scores after it (the next hand's start, or the end)."""
    logs = tr.load_logs(str(ROOT / g["file"]))
    hands = []
    for log in logs:
        k, honba, _ = log[0]
        start = list(log[1])
        hands.append({"k": k, "honba": honba, "start": start})
    for i, h in enumerate(hands):
        if i + 1 < len(hands):
            h["after"] = hands[i + 1]["start"]
            h["next_k"] = hands[i + 1]["k"]
        else:
            log = logs[i]
            deltas = tr.result_deltas(log[-1])
            sticks = tr.riichi_sticks_paid(log)
            h["after"] = [s + d - p for s, d, p in zip(h["start"], deltas, sticks)]
            h["next_k"] = None
    return hands


def pool(manifest: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Every hand of the games as score changes turned to the dealer's seat, and whether the dealer kept the deal."""
    rel, keep = [], []
    for g in manifest:
        for h in game_hands(g):
            d = h["k"] % 4
            delta = [a - b for a, b in zip(h["after"], h["start"])]
            rel.append([delta[(d + i) % 4] for i in range(4)])
            keep.append(h["next_k"] == h["k"] if h["next_k"] is not None else delta[d] > 0)
    return np.array(rel, dtype=np.int64), np.array(keep)


class Model:
    def __init__(self, rel: np.ndarray, keep: np.ndarray, sims: int = SIMS, seed: int = SEED):
        self.rel, self.keep, self.sims, self.seed = rel, keep, sims, seed
        self.cache: dict = {}

    def final_points(self, scores: np.ndarray) -> np.ndarray:
        """Rank points of every seat, ties to the seat nearer the first dealer."""
        n = scores.shape[0]
        key = -scores * 4 + np.arange(4)[None, :]  # higher score first, then lower seat
        rank = np.argsort(np.argsort(key, axis=1), axis=1)
        return np.ceil((scores - 30000) / 1000 + UMA[rank]).astype(int)

    def ev(self, k: int, scores: list[int], seat: int) -> float:
        return self.value(k, scores, seat)[0]

    def fourth(self, k: int, scores: list[int], seat: int) -> float:
        return self.value(k, scores, seat)[1]

    def value(self, k: int, scores: list[int], seat: int) -> tuple[float, float]:
        """Mean rank points and the chance of finishing fourth, over simulated finishes of the game."""
        key = (k, tuple(scores), seat)
        if key in self.cache:
            return self.cache[key]
        n = self.sims
        self.rng = np.random.default_rng([self.seed, k, *[s // 100 + 1000 for s in scores], seat])
        s = np.tile(np.array(scores, dtype=np.int64), (n, 1))
        kk = np.full(n, k)
        done = np.zeros(n, dtype=bool)
        cols = np.arange(4)[None, :]
        for _ in range(MAX_HANDS):
            live = ~done
            if not live.any():
                break
            pick = self.rng.integers(0, len(self.rel), size=n)
            d = kk % 4
            idx = (cols - d[:, None]) % 4
            delta = self.rel[pick][np.arange(n)[:, None], idx]
            s = np.where(live[:, None], s + delta, s)
            kept = self.keep[pick]
            top = s.max(axis=1)
            bust = (s < 0).any(axis=1)
            dealer_score = s[np.arange(n), d]
            dealer_top = (dealer_score >= top) & (np.argmax(s * 4 - cols, axis=1) == d)
            last = kk >= 7
            ends = bust.copy()
            # after South 4: the dealer passes and someone has 30,000, or the dealer keeps it as the top with 30,000
            ends |= last & ~kept & (top >= 30000)
            ends |= last & kept & dealer_top & (dealer_score >= 30000)
            ends |= (kk >= 8) & (top >= 30000)
            ends |= (kk >= 11) & ~kept
            done |= live & ends
            kk = np.where(live & ~ends & ~kept, kk + 1, kk)
        pts = self.final_points(s)[:, seat]
        key4 = -s * 4 + np.arange(4)[None, :]
        last = np.argsort(np.argsort(key4, axis=1), axis=1)[:, seat] == 3
        v = (float(pts.mean()), float(last.mean()))
        self.cache[key] = v
        return v


def spot_ev(rows: list[dict], manifest: dict, model: Model) -> list[dict]:
    hands_of: dict = {}
    out = []
    for r in rows:
        g = manifest[r["game"]]
        if r["game"] not in hands_of:
            hands_of[r["game"]] = game_hands(g)
        k, honba = round_key(r["round"])
        h = next(h for h in hands_of[r["game"]] if h["k"] == k and h["honba"] == honba)
        seat = g["hero_seat"]
        before, fourth_before = model.value(h["k"], h["start"], seat)
        if h["next_k"] is None:
            after = float(model.final_points(np.array([h["after"]]))[0, seat])
            fourth_after = float(sorted(range(4), key=lambda q: (-h["after"][q], q)).index(seat) == 3)
        else:
            after, fourth_after = model.value(h["next_k"], h["after"], seat)
        place = sorted(range(4), key=lambda q: (-h["start"][q], q)).index(seat) + 1
        out.append(dict(r, ev_before=round(before, 1), ev_after=round(after, 1), ev_change=round(after - before, 1),
                        fourth_change=round(100 * (fourth_after - fourth_before), 1), place_before=place,
                        stage="East" if h["k"] < 4 else "South 1-3" if h["k"] < 7 else "South 4 on"))
    return out


def summary(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"hands": 0}
    ev = np.array([r["ev_change"] for r in rows])
    return {"hands": n, "ev_change": round(float(ev.mean()), 1),
            "se": round(float(ev.std(ddof=1) / math.sqrt(n)), 1) if n > 1 else None,
            "fourth_change": round(sum(r["fourth_change"] for r in rows) / n, 1),
            "points": round(sum(r["delta"] for r in rows) / n)}


def split(rows: list[dict]) -> dict:
    return {"spots": len(rows), "pushed_pct": round(100 * sum(r["pushed"] for r in rows) / len(rows), 1) if rows else None,
            "pushes": summary([r for r in rows if r["pushed"]]), "folds": summary([r for r in rows if not r["pushed"]])}


def main() -> None:
    you_path, lj_path, out = sys.argv[1:4]
    mine = [g for g in json.loads(MANIFEST.read_text(encoding="utf-8")) if g["date"] >= SINCE]
    lj_manifest = json.loads(LJ_MANIFEST.read_text(encoding="utf-8"))
    rel, keep = pool(mine)
    model = Model(rel, keep)
    start = [model.ev(0, [25000] * 4, s) for s in range(4)]
    you = spot_ev(json.load(open(you_path))["rows"], {g["uuid"]: g for g in mine}, model)
    lj = spot_ev(json.load(open(lj_path))["rows"], {g["uuid"]: g for g in lj_manifest}, model)
    data = {"pool_hands": len(rel), "start_ev": [round(v, 1) for v in start], "sims": SIMS}
    for name, rows in (("you", you), ("luckyj", lj)):
        block = {}
        for cell, keep_cell in (("thin", is_thin), ("all", lambda r: True)):
            rs = [r for r in rows if keep_cell(r)]
            block[cell] = split(rs)
            block[cell]["by_place"] = {str(p): split([r for r in rs if r["place_before"] == p]) for p in (1, 2, 3, 4)}
            block[cell]["by_stage"] = {st: split([r for r in rs if r["stage"] == st]) for st in ("East", "South 1-3", "South 4 on")}
        data[name] = block
    data["your_spots"] = [{k: r[k] for k in ("game", "round", "turn", "pushed", "won", "dealt", "delta", "place_before", "stage",
                                              "ev_before", "ev_after", "ev_change", "fourth_change", "han", "live")}
                          for r in you if is_thin(r)]
    Path(out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
