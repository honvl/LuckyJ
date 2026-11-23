#!/usr/bin/env python3
"""Do players who reach Celestial stay there? Current and peak rank of every account seen as a Celestial in the
Throne room since 20 July 2026, and of a random 300 Saint 3s from the Jade room sample.

amae-koromo's ``player_stats`` gives each account's current rank (``level``) and the highest it ever held
(``max_level``). Only those two fields and the game count are kept, by account id, in
``data/ladder_skill/celestial_retention_raw.json`` (gitignored, no names); a rerun skips accounts already there.
``report`` writes ``analysis/celestial-retention-2026-11-23.json``.

    .venv/bin/python scripts/mine_celestial_retention.py fetch
    .venv/bin/python scripts/mine_celestial_retention.py report
"""

from __future__ import annotations

import collections
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import fetch_majsoul_games as fms  # noqa: E402
import mine_tier_ranking as tr  # noqa: E402

RAW = ROOT / "data" / "ladder_skill" / "celestial_retention_raw.json"
OUT = ROOT / "analysis" / "celestial-retention-2026-11-23.json"
CELESTIAL = 10701


def cohorts():
    raw, _ = tr.load_rooms()
    seen = collections.defaultdict(list)  # account -> [(start, rank)] in the Throne room
    for start, seats in raw[tr.THRONE]:
        for rank, _, acct in seats:
            seen[acct].append((start, rank))
    celestials = sorted(a for a, g in seen.items() if any(r >= CELESTIAL for _, r in g))
    saint3 = sorted({s[2] for _, seats in raw[tr.JADE] for s in seats if s[0] == 10503})
    sample = random.Random(20261123).sample(saint3, 300)
    return celestials, sample, seen


def fetch():
    token = fms.amae_token()
    if not token:
        sys.exit("no AMAE_KOROMO_TOKEN")
    celestials, sample, _ = cohorts()
    have = json.loads(RAW.read_text()) if RAW.exists() else {}
    todo = [a for a in celestials + sample if str(a) not in have]
    print(f"{len(celestials)} Celestials, {len(sample)} Saint 3s, {len(todo)} to look up", flush=True)
    end = int(time.time() * 1000)
    for n, acct in enumerate(todo, 1):
        st = fms.amae_get(f"player_stats/{acct}/1262304000000/{end}?mode={fms.AMAE_MODES}", token)
        have[str(acct)] = {"level": (st.get("level") or {}).get("id"), "points": ((st.get("level") or {}).get("score") or 0)
                           + ((st.get("level") or {}).get("delta") or 0),
                           "max_level": (st.get("max_level") or {}).get("id"), "count": st.get("count")}
        if n % 100 == 0 or n == len(todo):
            RAW.write_text(json.dumps(have))
            print(f"  {n}/{len(todo)}", flush=True)


def report():
    have = json.loads(RAW.read_text())
    celestials, sample, seen = cohorts()
    out = {"window": "Throne room, 20 July to 20 November 2026; ranks looked up 23 November"}
    # 1. everyone who was a Celestial at some point since 20 July: where are they now?
    rows = [(a, have[str(a)]) for a in celestials if str(a) in have and have[str(a)]["level"]]
    now = collections.Counter("Celestial" if r["level"] >= CELESTIAL else "Saint 3" if r["level"] == 10503 else "lower"
                              for _, r in rows)
    out["celestials_since_july"] = {"accounts": len(rows), "now": dict(now),
                                    "still_celestial_pct": round(100 * now["Celestial"] / len(rows), 1)}
    # by peak level: did the ones who climbed higher stay?
    by_peak = collections.defaultdict(collections.Counter)
    for _, r in rows:
        peak = min((r["max_level"] or CELESTIAL) - 10700, 5)
        by_peak["5+" if peak >= 5 else str(peak)]["Celestial" if r["level"] >= CELESTIAL else "below"] += 1
    out["by_peak_level"] = {k: {"accounts": sum(v.values()), "still_celestial_pct": round(100 * v["Celestial"] / sum(v.values()), 1)}
                            for k, v in sorted(by_peak.items())}
    # by when they were first seen as a Celestial in the window (newer arrivals have had less time to fall)
    by_month = collections.defaultdict(collections.Counter)
    import datetime as dt
    for a, r in rows:
        first = min(t for t, rk in seen[a] if rk >= CELESTIAL)
        first_rank = min((rk for t, rk in seen[a] if t == first), default=0)
        m = dt.datetime.fromtimestamp(first, dt.UTC).strftime("%Y-%m")
        new = first_rank == CELESTIAL and (r["max_level"] or 0) == CELESTIAL
        by_month[m]["Celestial" if r["level"] >= CELESTIAL else "below"] += 1
        if new:  # first seen at level 1 and never above it: the newest arrivals
            by_month[m + ", level 1 only"]["Celestial" if r["level"] >= CELESTIAL else "below"] += 1
    out["by_first_seen"] = {k: {"accounts": sum(v.values()), "still_celestial_pct": round(100 * v["Celestial"] / sum(v.values()), 1)}
                            for k, v in sorted(by_month.items())}
    # 2. today's Saint 3s in the Jade room: how many have been Celestial before?
    srows = [have[str(a)] for a in sample if str(a) in have and have[str(a)]["level"]]
    fallen = sum(1 for r in srows if (r["max_level"] or 0) >= CELESTIAL)
    out["saint3_sample"] = {"accounts": len(srows), "were_celestial": fallen,
                            "were_celestial_pct": round(100 * fallen / len(srows), 1),
                            "still_saint3_pct": round(100 * sum(1 for r in srows if r["level"] == 10503) / len(srows), 1),
                            "now_celestial": sum(1 for r in srows if r["level"] >= CELESTIAL)}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"fetch": fetch, "report": report}[sys.argv[1]]()
