#!/usr/bin/env python3
"""A sample of recent ranked games in the Jade and Throne rooms, every player's rank and result.

Pages amae-koromo's game list newest first (one request per ``AMAE_MIN_INTERVAL`` seconds with
the operator's key) and keeps, per game, only the start time, the room, and each seat's rank id,
final score and rank-point change: no names and no account ids. The tutor's threads get the file
as a shared mount, so a coach can ask what a room looks like (how many Saints and Celestials,
how each rank places, what each rank earns) without reaching the API.

    .venv/bin/python scripts/fetch_room_sample.py service/.state/room-sample.json [--pages 50]

Output: {"fetched_at", "modes": {"12": "jade-south", ...}, "games": [[start, mode, [[rank, score,
rank_points] x 4]], ...]}, seats in seat order.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_majsoul_games as fms  # noqa: E402

MODES = {12: "jade-south", 16: "throne-south"}


def sample(token: str, pages: int) -> list:
    games, seen = [], set()
    for mode in MODES:
        end = int(time.time() * 1000)
        start = end - 30 * 86400 * 1000
        for _ in range(pages):
            page = fms.amae_get(f"games/{end}/{start}?limit=100&descending=true&mode={mode}", token)
            for g in page:
                if g["uuid"] in seen:
                    continue
                seen.add(g["uuid"])
                games.append([g["startTime"], g["modeId"],
                              [[p["level"], p["score"], p["gradingScore"]] for p in g["players"]]])
            if len(page) < 100:
                break
            end = min(g["startTime"] for g in page) * 1000 - 1
    return sorted(games, key=lambda g: g[0], reverse=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("--pages", type=int, default=50, help="pages of 100 games per room")
    args = ap.parse_args()
    token = fms.amae_token()
    if not token:
        sys.exit("no AMAE_KOROMO_TOKEN in the environment or tmp/tensoul/.env")
    games = sample(token, args.pages)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"fetched_at": datetime.now().isoformat(timespec="seconds"),
                                    "modes": {str(k): v for k, v in MODES.items()}, "games": games}),
                        encoding="utf-8")
    print(f"{len(games)} games -> {args.out}")


if __name__ == "__main__":
    main()
