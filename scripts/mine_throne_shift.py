#!/usr/bin/env python3
"""What changes for a new Celestial in the Throne room (guide chapter 54): the points, what they do to a push, the field.

1. Points. Average rank points by finishing place for a Jade-room Saint 3 and for a Throne-room Celestial, from the
   tutor's room sample (``service/.state/room-sample.json``). Celestial points are by place alone and symmetric.
2. A win against a deal-in. Every hand of the user's Jade games since January starts from a real position (the
   round, the four scores, the user's seat). From each one the user wins 3,900 or 8,000 from each other seat in turn,
   and deals the same into each, and the game is finished 3,000 times with ``mine_push_ev.Model`` (hands drawn from
   the user's own games, Mahjong Soul's end rules). The same finishes are scored twice: with Saint 3 Jade points,
   (score - 30,000) / 1000 plus 130, 65, 0, -250, and with Celestial points, 50, 20, -20, -50. The figure reported
   is the deal-in's cost divided by the win's gain, by the user's place at the start of the hand: how many wins of
   that size one deal-in costs. Errors are a bootstrap over the positions.
3. The field. Play statistics of random Jade seats and random Throne seats (amae-koromo ``player_extended_stats``,
   ``data/ladder_skill/throne_style_stats.json``, kept local), weighted by each player's hands, beside the user's.
4. Named hands of the user's, valued the same way.

    .venv/bin/python scripts/mine_throne_shift.py [OUT.json] [--procs P]
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import mine_push_ev as pe  # noqa: E402

OUT = ROOT / "analysis" / "throne-shift-2026-11-21.json"
ROOM_SAMPLE = ROOT / "service" / ".state" / "room-sample.json"
STYLE = ROOT / "data" / "ladder_skill" / "throne_style_stats.json"
S3 = np.array([130, 65, 0, -250])
CEL = np.array([50, 20, -20, -50])
SIZES = (3900, 8000)
SIMS = 3000
RNG = np.random.default_rng(20261121)
# hands the chapter walks through: (game, round, the user's turn, the tile cut, what the user did)
EXAMPLES = [("261002-b0ec9f2d-52a2-4578-b351-df6475cc8b35", "South 3-0", 14, "2s", "fold")]
STATS = {"和牌率": "win", "放铳率": "deal_in", "立直率": "riichi", "副露率": "call", "自摸率": "tsumo_share", "流局率": "draw",
         "流听率": "tenpai_at_draw", "默听率": "dama", "立直后和牌率": "riichi_win", "立直巡目": "riichi_turn",
         "平均打点": "average_win", "平均铳点": "average_deal_in"}
MODEL = None


class Finisher(pe.Model):
    """``mine_push_ev.Model`` whose finishes are scored under both point systems at once."""

    def dist(self, k, scores, seat):
        key = ("d", k, tuple(scores), seat)
        if key in self.cache:
            return self.cache[key]
        n = self.sims
        rng = np.random.default_rng([self.seed, k, *[s // 100 + 1000 for s in scores], seat])
        s = np.tile(np.array(scores, dtype=np.int64), (n, 1))
        kk = np.full(n, k)
        done = np.zeros(n, dtype=bool)
        cols = np.arange(4)[None, :]
        for _ in range(pe.MAX_HANDS):
            live = ~done
            if not live.any():
                break
            pick = rng.integers(0, len(self.rel), size=n)
            d = kk % 4
            delta = self.rel[pick][np.arange(n)[:, None], (cols - d[:, None]) % 4]
            s = np.where(live[:, None], s + delta, s)
            kept = self.keep[pick]
            top = s.max(axis=1)
            dealer_score = s[np.arange(n), d]
            dealer_top = (dealer_score >= top) & (np.argmax(s * 4 - cols, axis=1) == d)
            last = kk >= 7
            ends = (s < 0).any(axis=1)
            ends |= last & ~kept & (top >= 30000)
            ends |= last & kept & dealer_top & (dealer_score >= 30000)
            ends |= (kk >= 8) & (top >= 30000)
            ends |= (kk >= 11) & ~kept
            done |= live & ends
            kk = np.where(live & ~ends & ~kept, kk + 1, kk)
        self.cache[key] = self.final(s, seat)
        return self.cache[key]

    @staticmethod
    def final(s, seat):
        """[Saint 3 points, Celestial points, P(1st), P(2nd), P(3rd), P(4th)], ties to the seat nearer the first dealer."""
        rank = np.argsort(np.argsort(-s * 4 + np.arange(4)[None, :], axis=1), axis=1)[:, seat]
        p = np.bincount(rank, minlength=4) / len(rank)
        return np.array([float((np.ceil((s[:, seat] - 30000) / 1000) + S3[rank]).mean()), float(CEL[rank].mean()), *p])

    def after(self, k, scores, kept, seat):
        """The value once the hand at kyoku ``k`` has ended with these scores."""
        s = np.array([scores], dtype=np.int64)
        top, d = s.max(), k % 4
        ends = bool((s < 0).any()) or (k >= 7 and not kept and top >= 30000) or (k >= 8 and top >= 30000) or \
            (k >= 11 and not kept) or \
            (k >= 7 and kept and s[0, d] >= 30000 and int(np.argmax(s[0] * 4 - np.arange(4))) == d)
        if ends:
            return self.final(s, seat)
        return self.dist(k if kept else k + 1, [int(x) for x in scores], seat)


def init(rel, keep):
    global MODEL
    MODEL = Finisher(rel, keep, sims=SIMS)


def swing(job):
    """One position: its value, and the value after a win from and a deal-in to each other seat, for each size."""
    k, start, seat = job
    dealer = k % 4
    base = MODEL.dist(k, start, seat)
    out = {"k": k, "place": sorted(range(4), key=lambda q: (-start[q], q)).index(seat) + 1, "base": base.tolist()}
    for size in SIZES:
        win, deal = np.zeros(6), np.zeros(6)
        for o in range(4):
            if o == seat:
                continue
            s = list(start)
            s[seat] += size
            s[o] -= size
            win += MODEL.after(k, s, seat == dealer, seat) / 3
            s = list(start)
            s[seat] -= size
            s[o] += size
            deal += MODEL.after(k, s, o == dealer, seat) / 3
        out[str(size)] = {"win": win.tolist(), "deal": deal.tolist()}
    return out


def ratios(rows, size, reps=2000):
    """Gain of a win, cost of a deal-in and cost / gain under both systems, with a bootstrap error on the ratios."""
    b = np.array([r["base"] for r in rows])
    w = np.array([r[str(size)]["win"] for r in rows])
    d = np.array([r[str(size)]["deal"] for r in rows])
    gain, cost = w - b, b - d

    def at(idx):
        g, c = gain[idx].mean(0), cost[idx].mean(0)
        return c[0] / g[0], c[1] / g[1]

    full = at(np.arange(len(rows)))
    boots = np.array([at(RNG.integers(0, len(rows), len(rows))) for _ in range(reps)])
    g, c = gain.mean(0), cost.mean(0)
    return {"positions": len(rows),
            "saint3": {"win": round(float(g[0]), 1), "deal_in": round(float(c[0]), 1), "ratio": round(float(full[0]), 3),
                       "ratio_se": round(float(boots[:, 0].std(ddof=1)), 3)},
            "celestial": {"win": round(float(g[1]), 2), "deal_in": round(float(c[1]), 2), "ratio": round(float(full[1]), 3),
                          "ratio_se": round(float(boots[:, 1].std(ddof=1)), 3)},
            "ratio_change": round(float(full[1] - full[0]), 3),
            "ratio_change_se": round(float((boots[:, 1] - boots[:, 0]).std(ddof=1)), 3),
            "fourth_change_pct": {"win": round(float(-gain[:, 5].mean() * -100), 1), "deal_in": round(float(cost[:, 5].mean() * -100), 1)},
            "first_change_pct": {"win": round(float(gain[:, 2].mean() * 100), 1), "deal_in": round(float(-cost[:, 2].mean() * 100), 1)}}


def points():
    acc = defaultdict(lambda: defaultdict(list))
    values = Counter()
    for _, mode, seats in json.loads(ROOM_SAMPLE.read_text())["games"]:
        order = sorted(range(4), key=lambda i: (-seats[i][1], i))
        for i, s in enumerate(seats):
            place = order.index(i) + 1
            if mode == 12 and s[0] == 10503:
                acc["saint3"][place].append(s[2])
            if mode == 16 and s[0] > 10700:
                acc["celestial"][place].append(s[2])
                values[(place, s[2])] += 1
    out = {}
    for name in ("saint3", "celestial"):
        avg = [float(np.mean(acc[name][p])) for p in (1, 2, 3, 4)]
        steps = [avg[0] - avg[1], avg[1] - avg[2], avg[2] - avg[3]]
        out[name] = {"seats": sum(len(v) for v in acc[name].values()), "average": [round(v, 1) for v in avg],
                     "step_share_pct": [round(100 * v / sum(steps), 1) for v in steps]}
    base = [50, 20, -20, -50]
    out["celestial"]["schedule"] = base
    out["celestial"]["step_share_pct"] = [30.0, 40.0, 30.0]
    n = sum(values.values())
    out["celestial"]["at_schedule_pct"] = round(100 * sum(c for (p, v), c in values.items() if v == base[p - 1]) / n, 1)
    out["celestial"]["at_double_pct"] = round(100 * sum(c for (p, v), c in values.items() if v == 2 * base[p - 1]) / n, 1)
    return out


def field():
    data = json.loads(STYLE.read_text())
    out = {"you_in_jade": {name: data["me"]["jade"][key] for key, name in STATS.items()}, "your_hands": data["me"]["jade"]["count"]}
    for group, label in (("jade_field", "jade"), ("throne_field", "throne"), ("celestial", "celestial")):
        rows = [g for g in data["groups"][group] if g.get("count", 0) >= 30]
        block = {"players": len(rows)}
        for key, name in STATS.items():
            ok = [(g[key], g["count"]) for g in rows if g.get(key) is not None]
            v, w = np.array([a for a, _ in ok], float), np.array([c for _, c in ok], float)
            block[name] = {"mean": round(float((v * w).sum() / w.sum()), 4), "se": round(float(v.std(ddof=1) / np.sqrt(len(v))), 4)}
        out[label] = block
    return out


def main():
    args = sys.argv[1:]
    procs = 12
    if "--procs" in args:
        i = args.index("--procs")
        procs = int(args[i + 1])
        del args[i:i + 2]
    out_path = Path(args[0]) if args else OUT
    # Jade games only: the manifest also holds the user's Throne games from 20 November on
    manifest = [g for g in json.loads(pe.MANIFEST.read_text()) if g["date"] >= pe.SINCE and g.get("mode") == "jade-south"]
    by_id = {g["uuid"]: g for g in manifest}
    rel, keep = pe.pool(manifest)
    jobs = [(h["k"], h["start"], g["hero_seat"]) for g in manifest for h in pe.game_hands(g) if h["k"] <= 7]
    with Pool(procs, initializer=init, initargs=(rel, keep)) as pool:
        rows = pool.map(swing, jobs, chunksize=8)

    swings = {}
    for size in SIZES:
        block = {"all": ratios(rows, size)}
        for place in (1, 2, 3, 4):
            block[str(place)] = ratios([r for r in rows if r["place"] == place], size)
        for stage, pick in (("East", lambda k: k < 4), ("South 1-3", lambda k: 4 <= k < 7), ("South 4", lambda k: k == 7)):
            for place in (1, 2, 3, 4):
                sel = [r for r in rows if r["place"] == place and pick(r["k"])]
                if len(sel) >= 30:
                    block[f"{stage}, {place}"] = ratios(sel, size)
        swings[str(size)] = block

    init(rel, keep)
    examples = []
    for game, rnd, turn, tile, did in EXAMPLES:
        g = by_id[game]
        k, honba = pe.round_key(rnd)
        h = next(h for h in pe.game_hands(g) if h["k"] == k and h["honba"] == honba)
        one = swing((k, h["start"], g["hero_seat"]))
        b = np.array(one["base"])
        row = {"game": game, "date": g["date"], "round": rnd, "turn": turn, "tile": tile, "did": did, "place": one["place"],
               "scores": h["start"], "your_score": h["start"][g["hero_seat"]]}
        for size in SIZES:
            w, d = np.array(one[str(size)]["win"]), np.array(one[str(size)]["deal"])
            row[str(size)] = {"saint3": {"win": round(float(w[0] - b[0]), 1), "deal_in": round(float(b[0] - d[0]), 1),
                                         "ratio": round(float((b[0] - d[0]) / (w[0] - b[0])), 2)},
                              "celestial": {"win": round(float(w[1] - b[1]), 1), "deal_in": round(float(b[1] - d[1]), 1),
                                            "ratio": round(float((b[1] - d[1]) / (w[1] - b[1])), 2)},
                              "fourth_pct": {"now": round(float(b[5] * 100), 1), "after_win": round(float(w[5] * 100), 1),
                                             "after_deal_in": round(float(d[5] * 100), 1)},
                              "first_pct": {"now": round(float(b[2] * 100), 1), "after_win": round(float(w[2] * 100), 1),
                                            "after_deal_in": round(float(d[2] * 100), 1)}}
        examples.append(row)

    out = {"positions": len(rows), "finishes_each": SIMS, "pool_hands": int(len(rel)), "points": points(),
           "swings": swings, "examples": examples, "field": field(),
           "model_rewards": {"earlier_policy_model": [3.0, 1.5, 0.0, -4.5], "mortal_s42": [6.0, 4.0, 2.0, 0.0]},
           "you": {"level": "Celestial 1", "since": "2026-11-20", "points": 950, "level_up_at": 2000, "back_to_saint3_at": 0,
                   "throne_games": [{"place": 3, "score": 28500, "points": -20}, {"place": 2, "score": 37500, "points": 20},
                                    {"place": 4, "score": 20900, "points": -50}]}}
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out_path, len(rows), "positions")


if __name__ == "__main__":
    main()
