#!/usr/bin/env python3
"""Fetch a subscriber's ranked Mahjong Soul games into a folder the tutor's thread can use.

The player is pinned by account id (the same nickname can exist on the China, Japan and
International servers). Game ids come from the amae-koromo API (Gold room and above, the key in
tmp/tensoul/.env); each game is downloaded by the local tensoul checkout, logged in as the
operator, and written in tenhou.net/6 format.

    .venv/bin/python scripts/fetch_player_games.py --account 120182062 --out service/players/ms-120182062/games

The folder gets ``index.json`` in the shape ``thread.py new`` expects (hero_seat, hero_name,
placement, final scores), ``amae-koromo-records.json`` (every ranked game of the whole history
with all four players' ranks, scores and rank-point changes) and ``amae-koromo-stats.json`` (the
live rank and points, placement rates and play stats). Its ``file`` paths point where the sandbox unpacks the games
(``data/self_games/majsoul/<file>``), since this folder is uploaded as is. Rerunning only fetches
games not already in the folder.

Tile logs are capped at the newest ``--max-games`` of the past year (300 by default), newest first,
and the download stops at ``--time-limit`` minutes or as soon as the account's log retrieval
limit is reached, keeping what it has. Error 540 is the game's "log retrieval limit exceeded": a
quota on the account that downloads, not a burst throttle, so retrying does not help. Its size
and reset time are not known yet; the progress lines show how many logs a run got before it.

Onboarding runs on a runner whose disk is not kept, so a download that outlasts the job loses
everything: on 20 Nov 2026 the fetch account was over its limit, fetch_many.js spent 75 seconds
retrying each game, and a 283-game sign-up was killed at 30 minutes with nothing to show. A run
now asks for one game first and stops there if the limit is in force. The index is written
after every batch.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_majsoul_games as fms  # noqa: E402

SANDBOX_DIR = "data/self_games/majsoul"
MAX_GAMES = 300
BATCH = 20            # games per fetch_many.js run (one login each)
BATCH_SECONDS = 240   # a healthy batch takes about a minute; over the limit, 75 s of retries a game
PROBE_SECONDS = 30    # one game: login and download take a few seconds when the account is under its limit
TIME_LIMIT_MINUTES = 15


def newest(records: list[dict], limit: int) -> list[dict]:
    """The `limit` most recent records, newest first (all of them when limit is 0)."""
    ordered = sorted(records, key=lambda r: r["start_time"], reverse=True)
    return ordered[:limit] if limit > 0 else ordered


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", type=int, required=True, help="the player's Mahjong Soul account id")
    ap.add_argument("--out", type=Path, required=True, help="folder for the games and index.json")
    ap.add_argument("--since", help="only games from this date (YYYY-MM-DD); default: one year back")
    ap.add_argument("--max-games", type=int, default=MAX_GAMES,
                    help=f"tile logs for at most this many of the newest games (default {MAX_GAMES}; 0 for no cap)")
    ap.add_argument("--time-limit", type=float, default=TIME_LIMIT_MINUTES,
                    help=f"start no new batch after this many minutes (default {TIME_LIMIT_MINUTES}); the rest waits for the next run")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched and stop")
    args = ap.parse_args()

    since = args.since or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    token = fms.amae_token()
    if not token:
        sys.exit("no AMAE_KOROMO_TOKEN in the environment or tmp/tensoul/.env")

    # Records (ranks, scores, rank points of all four players) cover the whole history; they are
    # cheap, and questions about opponents and rank movement need years. Tile logs stay at `since`.
    export = out / "amae-koromo-records.json"
    added = fms.amae_api_refresh(args.account, None, token, export)
    if not args.dry_run:
        stats = fms.amae_stats(args.account, token)
        (out / "amae-koromo-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
    cutoff = datetime.strptime(since, "%Y-%m-%d").timestamp()
    in_window = [r for r in fms.amae_records(export) if r["start_time"] >= cutoff]
    records = newest(in_window, args.max_games)
    manifest_path = out / "index.json"
    manifest = {row["uuid"]: row for row in json.loads(manifest_path.read_text(encoding="utf-8"))} if manifest_path.exists() else {}
    missing = [r for r in records if r["uuid"] not in manifest or not (out / Path(manifest[r["uuid"]]["file"]).name).exists()]
    capped = f", newest {len(records)} kept" if len(records) < len(in_window) else ""
    print(f"account {args.account}: {len(in_window)} ranked games since {since}{capped} ({added} new on amae-koromo), "
          f"{len(records) - len(missing)} already here, {len(missing)} to fetch")
    if args.dry_run or not missing:
        return

    started = time.monotonic()
    written = errors = tried = 0
    stopped = ""
    # The first request is a single game with a short limit: when the account is over its log
    # retrieval limit this costs a few requests, not a batch of them.
    batches = [missing[:1]] + [missing[at:at + BATCH] for at in range(1, len(missing), BATCH)]
    for n, batch in enumerate(batches):
        if time.monotonic() - started > args.time_limit * 60:
            stopped = f"the {args.time_limit:g}-minute limit"
            break
        status, cut = fetch_batch([r["uuid"] for r in batch], out, PROBE_SECONDS if n == 0 else BATCH_SECONDS)
        for r in batch:
            st = status.get(r["uuid"])
            if st is None:  # the batch was cut off before reaching this game
                continue
            tried += 1
            if st["status"] == "error":
                errors += 1
                print(f"  {r['uuid']}: {st.get('error')}")
                continue
            written += st["status"] == "written"
            file = Path(st["file"])
            # The row's file is where the thread's sandbox unpacks it, wherever this folder is.
            manifest[r["uuid"]] = fms.manifest_row(r, args.account, fms.ROOT / SANDBOX_DIR / file.name)
        rows = sorted(manifest.values(), key=lambda row: row["start_time"], reverse=True)
        manifest_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  fetched {written} of {len(missing)} ({errors} errors, {time.monotonic() - started:.0f} s)", flush=True)
        if refused(status, cut):
            stopped = "the account's log retrieval limit (error 540, or no answer in time)"
            break
    rows = sorted(manifest.values(), key=lambda row: row["start_time"], reverse=True)
    left = len(missing) - written
    note = f"; stopped at {stopped}, {left} left for the next run" if stopped else ""
    print(f"wrote {written} games, {errors} errors{note}; {len(rows)} games in {out}")
    if not written and (errors or stopped):
        sys.exit(1)


def fetch_batch(ids: list[str], out: Path, seconds: int = BATCH_SECONDS) -> tuple[dict[str, dict], bool]:
    """One fetch_many.js run: {uuid: its status line} and whether the run was cut off for time."""
    if not (fms.TENSOUL / "fetch_many.js").exists():
        sys.exit(f"missing {fms.TENSOUL / 'fetch_many.js'}; clone tensoul into tmp/ first (see README)")
    try:
        proc = subprocess.run(["node", "fetch_many.js", "--out", str(out), *ids], cwd=fms.TENSOUL,
                              capture_output=True, text=True, check=False, timeout=seconds)
        text, cut = proc.stdout, False
        if proc.returncode != 0 and not text.strip():
            sys.exit(f"node fetch_many.js failed:\n{proc.stderr.strip()[-400:]}")
    except subprocess.TimeoutExpired as late:
        raw = late.stdout or ""
        text, cut = raw if isinstance(raw, str) else raw.decode("utf-8", "replace"), True
    status = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            row = json.loads(line)
            status[row["uuid"]] = row
    return status, cut


def refused(status: dict[str, dict], cut: bool) -> bool:
    """True when the account's log retrieval limit is in force: a game came back with error 540
    (after fetch_many.js's own retries), or the batch was cut off for time while retrying."""
    over = any(row["status"] == "error" and '"code":540' in str(row.get("error", "")).replace(" ", "") for row in status.values())
    return cut or over


if __name__ == "__main__":
    main()
