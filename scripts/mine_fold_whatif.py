#!/usr/bin/env python3
"""Guide chapter 37: chapter 35's 15 folds played out both ways by ``mortal_whatif.py``.

Each fold of a big hand on a thin wait against a riichi (``analysis/thin-pushes-2026-10-12.json``, ``your_folds``) was
run with ``mortal_whatif.py run``: the recorded fold and the push (the tenpai-keeping tile Mortal liked best), Mortal
playing all four seats from there and the rest of the game, 500 samples each (sample 0 on the real wall, the others on
reshuffles of the unseen tiles, the real hands kept), the two lines paired by wall. This script reads the runs and
writes, for each fold and over all 15:

- the rank points (Saint 3 Jade values) of each line and the push's gain over the fold, with its standard error;
- the chance of finishing fourth on each line;
- how the hand itself ended on each line: the user deals in, wins, someone else wins, or a draw.

The real hands are kept, so when the push tile was a riichi's winning tile the push deals in on every sample. Over
many folds that is fair, since the real hands are one draw of what the user could not see; for one fold it is
hindsight. The mean over the 15 is given with two errors: the reshuffles' alone, and the spread across the folds.

usage: mine_fold_whatif.py CASES.json RUNS_DIR OUT.json
  CASES.json: the folds with the discard number, the fold tile and the push tile (one per line of ``your_folds``).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mortal_whatif import rank_points  # noqa: E402


def pct(k: float, n: int) -> float:
    return round(100 * k / n, 1)


def mean_se(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))
    return round(m, 1), round(sd / math.sqrt(n), 1)


def hand_kind(h: dict, hero: int) -> str:
    if h["kind"] in ("ron", "tsumo"):
        if hero in h["winners"]:
            return "won"
        if h["kind"] == "ron" and h["loser"] == hero:
            return "dealt in"
        return "someone else won"
    return "draw"


def line(rows: list[dict], tile: str, hero: int) -> dict:
    n = len(rows)
    pts = [rank_points(r[tile]["scores"][hero], r[tile]["places"][hero]) for r in rows]
    kinds = [hand_kind(r[tile]["hand"], hero) for r in rows]
    m, se = mean_se(pts)
    return {"rank_points": m, "se": se, "fourth": pct(sum(r[tile]["places"][hero] == 3 for r in rows), n),
            "hand": {k: pct(kinds.count(k), n) for k in ("won", "dealt in", "someone else won", "draw")},
            "real_wall": {"hand": hand_kind(rows[0][tile]["hand"], hero), "place": rows[0][tile]["places"][hero] + 1,
                          "rank_points": rank_points(rows[0][tile]["scores"][hero], rows[0][tile]["places"][hero])}}


def main() -> None:
    cases_path, runs_dir, out = sys.argv[1:4]
    cases = json.load(open(cases_path))
    folds, gains, fourths = [], [], []
    for c in cases:
        path = Path(runs_dir) / f"{c['uuid15']}-{c['code']}.json"
        d = json.loads(path.read_text())
        hero, rows = d["hero"], d["samples"]
        fold, push = line(rows, d["played"], hero), line(rows, d["other"], hero)
        diff = [rank_points(r[d["other"]]["scores"][hero], r[d["other"]]["places"][hero])
                - rank_points(r[d["played"]]["scores"][hero], r[d["played"]]["places"][hero]) for r in rows]
        gain, se = mean_se(diff)
        gains.append(gain)
        fourths.append(push["fourth"] - fold["fourth"])
        folds.append({"game": c["game"], "round": c["round"], "turn": c["turn"], "fold": d["played"], "push": d["other"],
                      "samples": len(rows), "errors": d.get("errors", 0), "mortal_keep": c["mortal_keep"],
                      "options": c["options"], "real_hand_points": c["delta"],
                      "fold_line": fold, "push_line": push, "push_gain": gain, "push_gain_se": se,
                      "fourth_change": round(push["fourth"] - fold["fourth"], 1)})
    n = len(folds)
    se_all = math.sqrt(sum(f["push_gain_se"] ** 2 for f in folds)) / n
    data = {"folds": folds, "count": n,
            "mean_push_gain": round(sum(gains) / n, 1), "mean_push_gain_se": round(se_all, 1),
            # the reshuffles' error alone understates it: the real hands differ from fold to fold
            "mean_push_gain_se_across_folds": mean_se(gains)[1],
            "push_deals_in_every_time": sum(f["push_line"]["hand"]["dealt in"] == 100.0 for f in folds),
            "mean_fourth_change": round(sum(fourths) / n, 1),
            "push_better": sum(f["push_gain"] - 2 * f["push_gain_se"] > 0 for f in folds),
            "fold_better": sum(f["push_gain"] + 2 * f["push_gain_se"] < 0 for f in folds),
            "mortal_kept": {"folds": sum(1 for f in folds if f["mortal_keep"] > 0.5),
                            "mean_push_gain": round(sum(f["push_gain"] for f in folds if f["mortal_keep"] > 0.5)
                                                    / max(1, sum(1 for f in folds if f["mortal_keep"] > 0.5)), 1)},
            "mortal_folded": {"folds": sum(1 for f in folds if f["mortal_keep"] <= 0.5),
                              "mean_push_gain": round(sum(f["push_gain"] for f in folds if f["mortal_keep"] <= 0.5)
                                                      / max(1, sum(1 for f in folds if f["mortal_keep"] <= 0.5)), 1)}}
    Path(out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}: {n} folds, push gain {data['mean_push_gain']:+.1f} (± {data['mean_push_gain_se']:.1f}) rank points a fold")


if __name__ == "__main__":
    main()
