#!/usr/bin/env python3
"""Download a list of Mahjong Soul games (any players') with every fetch account in turn.

For room-wide analyses (guide chapter 55: the Throne room). Each account downloads in batches of 20 until the game
refuses it (error 540, the log retrieval limit) and the next account takes over. Games already in OUT are skipped, so
runs on different machines (the operator's own account here, the fetch accounts on GitHub) add up. The logs carry
the players' names: keep OUT out of the repository (``data/ladder_skill/`` is gitignored) and encrypt anything that
leaves a runner.

Output prints counts only, no game ids or account ids.

    .venv/bin/python scripts/fetch_room_games.py IDS.txt OUT_DIR [--time-limit MINUTES]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fetch_player_games as fpg  # noqa: E402

BATCH = 20


def main() -> None:
    args = sys.argv[1:]
    minutes = 50.0
    if "--time-limit" in args:
        i = args.index("--time-limit")
        minutes = float(args[i + 1])
        del args[i:i + 2]
    ids = [l.strip() for l in Path(args[0]).read_text().split() if l.strip()]
    out = Path(args[1])
    out.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + minutes * 60
    todo = [u for u in ids if not (out / fpg.log_name(u)).exists()]
    pool = fpg.accounts()
    print(f"{len(ids)} games listed, {len(ids) - len(todo)} already here, {len(pool)} accounts", flush=True)
    got = 0
    for a in pool:
        while todo and time.time() < deadline:
            batch = todo[:BATCH]
            status, cut, failure = fpg.fetch_batch(batch, out, fpg.BATCH_SECONDS, a["env"])
            written = [u for u in batch if (out / fpg.log_name(u)).exists()]
            got += len(written)
            todo = [u for u in todo if u not in written]
            print(f"account {a['label']}: {len(written)} of {len(batch)} written", flush=True)
            if failure or fpg.refused(status, cut) or not written:
                print(f"account {a['label']}: stopped ({'limit' if fpg.refused(status, cut) else 'error'})", flush=True)
                break
        if not todo or time.time() >= deadline:
            break
    print(f"downloaded {got}; {len(todo)} still missing", flush=True)


if __name__ == "__main__":
    main()
