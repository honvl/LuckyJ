#!/usr/bin/env python3
"""Recent games against the rest of the corpus: tenpai, wins, deal-ins, open-tenpai pushes, rank points.

``blocks`` splits a player's hands into the last N games and the games before them. It reads
rows written by ``mine_dora_hands.py compute`` (every hand) and ``mine_open_tenpai_push.py
compute`` (open tenpai against a riichi where every tenpai-keeping tile is unsafe), both of
which record the game uuid. Baseline push rows (LuckyJ) can be added for the pooled line.

``ranks`` reads the amae-koromo export (``fetch_majsoul_games.py --refresh-amae``) and prints
the rank-point change by placement, the average per game, the last N games, and the share of
fourths that would make the average zero with the other placements unchanged.

usage: review_recent_games.py blocks MANIFEST LAST_N DORA_ROWS.json OTP_ROWS.json [BASELINE_OTP_ROWS.json ...]
       review_recent_games.py ranks AMAE_EXPORT.json ACCOUNT_ID SINCE LAST_N
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from pathlib import Path


def pct(a: float, b: float) -> str:
    return f"{100 * a / b:5.1f}%" if b else "    -"


def se(q: float, n: int) -> float:
    return 100 * math.sqrt(q * (1 - q) / n) if n else 0.0


def split_games(manifest: str, last_n: int) -> tuple[set, set]:
    games = sorted(json.loads(Path(manifest).read_text()), key=lambda g: g["start_time"])
    uuids = [g["uuid"] for g in games]
    return set(uuids[:-last_n]), set(uuids[-last_n:])


def blocks(manifest: str, last_n: int, dora_rows: str, otp_rows: str, baseline: list[str]) -> None:
    early, recent = split_games(manifest, last_n)
    hands = json.loads(Path(dora_rows).read_text())["rows"]
    pushes = json.loads(Path(otp_rows).read_text())["rows"]
    print(f"== the last {last_n} games against the {len(early)} before them")
    for name, keep in (("earlier games", early), (f"last {last_n} games", recent)):
        rs = [r for r in hands if r["game"] in keep]
        n = len(rs)
        tenpai = [r for r in rs if r["first"]]
        won_t = sum(r["won"] for r in tenpai)
        wins = [r for r in rs if r["won"]]
        dealt = [r for r in rs if r["deal"]]
        q_t = won_t / len(tenpai) if tenpai else 0
        q_d = len(dealt) / n if n else 0
        print(f"-- {name}: {len({r['game'] for r in rs})} games, {n} hands")
        print(f"   tenpai {pct(len(tenpai), n)}  tenpai won {100 * q_t:5.1f}% ±{se(q_t, len(tenpai)):.1f}  won {pct(len(wins), n)}"
              f"  average win {sum(r['value'] for r in wins) / max(1, len(wins)):6.0f}")
        print(f"   dealt in {100 * q_d:5.1f}% ±{se(q_d, n):.1f}  average deal-in {sum(r['deal']['cost'] for r in dealt) / max(1, len(dealt)):6.0f}"
              f"  opened {pct(sum(bool(r['opened_turn']) for r in rs), n)}")
        by_state = "  ".join(
            f"{label} {100 * sum(1 for r in dealt if r['deal']['state'] == st) / n:4.1f}"
            for label, st in (("in riichi", "riichi"), ("tenpai", "0"), ("1-shanten", "1"), ("2+ shanten", "2")))
        open_share = 100 * sum(1 for r in dealt if r["opened_turn"]) / n
        print(f"   deal-ins per 100 hands: {by_state}  | with the hand open {open_share:4.1f}")
        ps = [r for r in pushes if r["game"] in keep]
        pu = [r for r in ps if r["pushed"]]
        fo = [r for r in ps if not r["pushed"]]
        print(f"   open tenpai against a riichi, no safe tile keeps it: n {len(ps)}  pushed {pct(len(pu), len(ps))}"
              f"  pushed hands won {pct(sum(r['won'] for r in pu), len(pu))} dealt in {pct(sum(r['dealt'] for r in pu), len(pu))}")
    base = [r for f in baseline for r in json.loads(Path(f).read_text())["rows"]]
    print("-- pushes pooled over every game, by value and wait")
    for label, rows in (("this player", pushes), ("baseline", base)):
        if not rows:
            continue
        for name, sel in (("3+ han, 4+ live tiles", lambda r: r["han"] >= 3 and r["live"] >= 4),
                          ("3+ han, 3 or fewer", lambda r: r["han"] >= 3 and r["live"] <= 3),
                          ("1-2 han", lambda r: r["han"] <= 2)):
            rs = [r for r in rows if sel(r)]
            pu = [r for r in rs if r["pushed"]]
            print(f"   {label:<12} {name:<22} n {len(rs):4d}  pushed {pct(len(pu), len(rs))}  pushed hands won {pct(sum(r['won'] for r in pu), len(pu))}"
                  f"  dealt in {pct(sum(r['dealt'] for r in pu), len(pu))}")


def placement(players: list, account: int) -> int:
    """Final place from an amae-koromo player list; ties go to the earlier seat in the list."""
    order = sorted(range(len(players)), key=lambda i: (-players[i][3], i))
    return next(k for k, i in enumerate(order, 1) if players[i][0] == account)


def break_even_fourths(shares: dict, means: dict) -> float:
    """The share of fourths that makes the average rank-point change zero, moving fourths into thirds."""
    expected = sum(shares[p] * means[p] for p in (1, 2, 3, 4))
    return shares[4] + expected / (means[3] - means[4])


def ranks(export: str, account: int, since: str, last_n: int) -> None:
    records = json.loads(Path(export).read_text())["records"]
    cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
    games = []
    for r in sorted(records, key=lambda r: r[1]):
        me = next((p for p in r[4] if p[0] == account), None)
        if me is None or r[1] < cutoff:
            continue
        games.append((r[1], placement(r[4], account), me[4], me[2]))
    n = len(games)
    print(f"== rank points since {since}: {n} games, level {games[-1][3] if games else '-'}")
    means = {}
    for p in (1, 2, 3, 4):
        d = [g[2] for g in games if g[1] == p]
        means[p] = sum(d) / len(d) if d else 0
        print(f"   place {p}: n {len(d):3d}  change {means[p]:+7.1f} on average (from {min(d, default=0):+d} to {max(d, default=0):+d})")
    total = sum(g[2] for g in games)
    shares = {p: sum(1 for g in games if g[1] == p) / n for p in (1, 2, 3, 4)}
    print(f"   total {total:+d}, {total / n:+.1f} per game;"
          f" places 1/2/3/4 {' / '.join(pct(shares[p] * n, n).strip() for p in (1, 2, 3, 4))}")
    print(f"   fourths that would make the average zero, other places unchanged: {100 * break_even_fourths(shares, means):.1f}%")
    recent = games[-last_n:]
    places = [g[1] for g in recent]
    print(f"   last {last_n}: places {' '.join(map(str, places))}  change {sum(g[2] for g in recent):+d};"
          f" fourths expected at the long-run rate {shares[4] * last_n:.1f}, actual {places.count(4)}")


if __name__ == "__main__":
    if sys.argv[1] == "blocks":
        blocks(sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6:])
    else:
        ranks(sys.argv[2], int(sys.argv[3]), sys.argv[4], int(sys.argv[5]))
