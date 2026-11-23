#!/usr/bin/env python3
"""How long did today's Celestials take to get there, and how well did they place from the start?

For a random sample of players who are Celestial today (from ``mine_celestial_retention.py``'s lookups) and for the
user, the whole ranked four-player history on amae-koromo (Gold, Jade and Throne rooms; Bronze and Silver are not
recorded there): the games from the first recorded game to the first game as Saint 3 and as Celestial, the rank the
history starts at, and the average place over the first 500 and the first 1,000 recorded games.

A player who starts strong (good early placements, few games to Saint 3) came in with knowledge: another account,
Tenhou, or real-life mahjong. Only those numbers are kept, by account id, no names
(``data/ladder_skill/celestial_careers_raw.json``, gitignored). ``report`` writes
``analysis/celestial-careers-2026-11-23.json``.

    .venv/bin/python scripts/mine_celestial_careers.py fetch [N]
    .venv/bin/python scripts/mine_celestial_careers.py report
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_majsoul_games as fms  # noqa: E402

LOOKUPS = ROOT / "data" / "ladder_skill" / "celestial_retention_raw.json"
RAW = ROOT / "data" / "ladder_skill" / "celestial_careers_raw.json"
OUT = ROOT / "analysis" / "celestial-careers-2026-11-23.json"
PAGE = 500
SAINT3, CELESTIAL, MASTER1 = 10503, 10701, 10401


def history(account: int, token: str) -> list[tuple[int, int, int]]:
    """Every recorded ranked four-player game, oldest first: (start, rank id held, place)."""
    end_ms, rows = int(time.time() * 1000), []
    while True:
        page = fms.amae_get(f"player_records/{account}/{end_ms}/0?limit={PAGE}&mode={fms.AMAE_MODES}&descending=true", token)
        if not isinstance(page, list):
            sys.exit(f"unexpected amae-koromo response: {str(page)[:200]}")
        for r in page:
            players = sorted(r["players"], key=lambda p: -p["score"])  # ties are rare; seat order is not given
            for place, p in enumerate(players, 1):
                if p["accountId"] == account:
                    rows.append((r["startTime"], p.get("level") or 0, place))
        if not page:  # the API returns at most about 150 a page whatever the limit, so page until it is empty
            break
        end_ms = min(r["startTime"] for r in page) * 1000 - 1
    return sorted(set(rows))


def summary(rows: list[tuple[int, int, int]]) -> dict:
    ranks = [r for _, r, _ in rows]
    places = np.array([p for _, _, p in rows], float)

    def first(level):
        return next((i for i, r in enumerate(ranks) if r >= level), None)

    return {"games": len(rows), "first_rank": ranks[0] if ranks else None, "first_start": rows[0][0] if rows else None,
            "games_to_master": first(MASTER1), "games_to_saint3": first(SAINT3), "games_to_celestial": first(CELESTIAL),
            "place_first_500": round(float(places[:500].mean()), 4) if len(places) >= 500 else None,
            "place_first_1000": round(float(places[:1000].mean()), 4) if len(places) >= 1000 else None,
            "place_last_500": round(float(places[-500:].mean()), 4) if len(places) >= 500 else None}


def user_account() -> int:
    """The user's account id, matched from their own Throne games in the room sample."""
    import mine_tier_ranking as tr
    idx = json.loads((ROOT / "data" / "self_games" / "majsoul" / "index.json").read_text(encoding="utf-8"))
    raw, _ = tr.load_rooms()
    by_start = {g["start_time"]: g for g in idx}
    for start, seats in raw[tr.THRONE]:
        g = by_start.get(start)
        if g:
            hits = [s[2] for s in seats if s[1] == g["final_scores"][g["hero_seat"]]]
            if len(hits) == 1:
                return hits[0]
    sys.exit("could not find the user's account id")


def fetch(n: int):
    token = fms.amae_token()
    if not token:
        sys.exit("no AMAE_KOROMO_TOKEN")
    looks = json.loads(LOOKUPS.read_text())
    celestials = sorted(int(a) for a, r in looks.items() if (r.get("level") or 0) >= CELESTIAL)
    sample = random.Random(20261123).sample(celestials, min(n, len(celestials)))
    have = json.loads(RAW.read_text()) if RAW.exists() else {}
    me = user_account()
    todo = [("you", me)] + [(str(a), a) for a in sample]
    todo = [(k, a) for k, a in todo if k not in have]
    print(f"{len(todo)} careers to fetch", flush=True)
    for i, (key, acct) in enumerate(todo, 1):
        s = summary(history(acct, token))
        s["level_now"] = (looks.get(str(acct)) or {}).get("level")
        have[key] = s
        RAW.write_text(json.dumps(have))
        if i % 10 == 0 or i == len(todo):
            print(f"  {i}/{len(todo)}", flush=True)


def report():
    have = json.loads(RAW.read_text())
    you = have.get("you")
    # a history that starts above Expert began before amae-koromo recorded it (or skipped the Gold room); its
    # counts would be too small, so only histories that start at Expert count
    everyone = [v for k, v in have.items() if k != "you" and v["games"]]
    others = [v for v in everyone if (v.get("first_rank") or 0) < MASTER1]

    def dist(key, rows=others):
        x = np.array([r[key] for r in rows if r.get(key) is not None], float)
        return {"players": int(len(x)), "median": round(float(np.median(x)), 3), "q1": round(float(np.percentile(x, 25)), 3),
                "q3": round(float(np.percentile(x, 75)), 3)} if len(x) else None

    def share_better(key, value, lower_is_better=True):
        x = [r[key] for r in others if r.get(key) is not None]
        if value is None or not x:
            return None
        return round(100 * sum((v < value) if lower_is_better else (v > value) for v in x) / len(x), 1)

    out = {"sample": len(others), "looked_up": len(everyone), "note": "Gold, Jade and Throne rooms only; amae-koromo does not record Bronze and Silver",
           "games_to_saint3": dist("games_to_saint3"), "games_to_celestial": dist("games_to_celestial"),
           "games_to_master": dist("games_to_master"),
           "place_first_500": dist("place_first_500"), "place_first_1000": dist("place_first_1000"),
           "place_last_500": dist("place_last_500"),
           "you": you,
           "faster_than_you_to_celestial_pct": share_better("games_to_celestial", (you or {}).get("games_to_celestial")),
           "better_first_500_than_you_pct": share_better("place_first_500", (you or {}).get("place_first_500"))}
    # does starting strong go with a fast climb? (early placement against games to Celestial)
    pairs = np.array([(r["place_first_500"], r["games_to_celestial"]) for r in others
                      if r.get("place_first_500") is not None and r.get("games_to_celestial") is not None], float)
    if len(pairs) > 10:
        out["early_place_vs_games_to_celestial_r"] = round(float(np.corrcoef(pairs[:, 0], pairs[:, 1])[0, 1]), 3)
        fast = pairs[pairs[:, 0] <= np.percentile(pairs[:, 0], 25)]
        slow = pairs[pairs[:, 0] >= np.percentile(pairs[:, 0], 75)]
        out["games_to_celestial_by_start"] = {"best_quarter_first_500": round(float(np.median(fast[:, 1]))),
                                              "worst_quarter_first_500": round(float(np.median(slow[:, 1])))}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        fetch(int(sys.argv[2]) if len(sys.argv) > 2 else 120)
    else:
        report()
