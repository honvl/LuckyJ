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

Several fetch accounts can share the work (``accounts()``): the first is the one config.js reads
(``ACCESS_TOKEN`` / ``MJS_RANDOM_KEY``), and ``MJS_ACCESS_TOKEN_2`` .. ``_8`` with their own
``MJS_RANDOM_KEY_<n>`` add more. A run uses one until it is over its limit, then the next, and
ends by saying how many logs each gave. ``--check-accounts GAME`` asks every account for one
game and reports which can still download.

Onboarding runs on a runner whose disk is not kept, so a download that outlasts the job loses
everything: on 20 Nov 2026 the fetch account was over its limit, fetch_many.js spent 75 seconds
retrying each game, and a 283-game sign-up was killed at 30 minutes with nothing to show. A run
now asks for one game first and stops there if the limit is in force. The index is written
after every batch.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
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
CHECK_SECONDS = 100   # long enough for fetch_many.js to finish its own retries and name the error
MAX_ACCOUNTS = 8
TIME_LIMIT_MINUTES = 15


def newest(records: list[dict], limit: int) -> list[dict]:
    """The `limit` most recent records, newest first (all of them when limit is 0)."""
    ordered = sorted(records, key=lambda r: r["start_time"], reverse=True)
    return ordered[:limit] if limit > 0 else ordered


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", type=int, help="the player's Mahjong Soul account id")
    ap.add_argument("--out", type=Path, help="folder for the games and index.json")
    ap.add_argument("--check-accounts", metavar="GAME",
                    help="ask every fetch account for this one game id, report which can download, and stop")
    ap.add_argument("--since", help="only games from this date (YYYY-MM-DD); default: one year back")
    ap.add_argument("--max-games", type=int, default=MAX_GAMES,
                    help=f"tile logs for at most this many of the newest games (default {MAX_GAMES}; 0 for no cap)")
    ap.add_argument("--time-limit", type=float, default=TIME_LIMIT_MINUTES,
                    help=f"start no new batch after this many minutes (default {TIME_LIMIT_MINUTES}); the rest waits for the next run")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched and stop")
    args = ap.parse_args()
    if args.check_accounts:
        check_accounts(args.check_accounts)
    if args.account is None or args.out is None:
        ap.error("--account and --out are required")

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

    pool = accounts()
    written, errors, stopped, gave = download(missing, out, args.account, manifest, manifest_path, pool, args.time_limit)
    rows = sorted(manifest.values(), key=lambda row: row["start_time"], reverse=True)
    left = len(missing) - written - errors
    note = f"; stopped at {stopped}, {left} left for the next run" if stopped else ""
    shares = ", ".join(f"account {a['label']}: {n}" for a, n in zip(pool, gave))
    print(f"wrote {written} games, {errors} errors{note}; {len(rows)} games in {out} ({shares})")
    if not written and (errors or stopped):
        sys.exit(1)


def download(missing: list[dict], out: Path, account_id: int, manifest: dict, manifest_path: Path,
             pool: list[dict], time_limit: float, fetch=None) -> tuple[int, int, str, list[int]]:
    """Fetch `missing` (newest first) with the pool's accounts in turn, writing the index after
    every batch. Returns games written, games that failed for good, why it stopped early (or ""),
    and how many logs each account gave."""
    fetch = fetch or fetch_batch
    started = time.monotonic()
    written = errors = 0
    stopped = ""
    queue = list(missing)            # newest first; a game leaves when it is written or truly fails
    at, probe = 0, True              # the account in use, and whether its next request is the one-game probe
    gave = [0] * len(pool)           # logs each account gave before its limit
    while queue and at < len(pool):
        if time.monotonic() - started > time_limit * 60:
            stopped = f"the {time_limit:g}-minute limit"
            break
        # An account's first request is a single game with a short limit: when it is over its log
        # retrieval limit this costs a few requests, not a batch of them.
        batch = queue[:1 if probe else BATCH]
        status, cut, failure = fetch([r["uuid"] for r in batch], out,
                                     PROBE_SECONDS if probe else BATCH_SECONDS, pool[at]["env"])
        over = refused(status, cut)
        done = set()
        for r in batch:
            st = status.get(r["uuid"])
            if st is None:
                if failure or over:      # the account could not be used; the game stays for the next one
                    continue
                st = {"status": "error", "error": "no output from fetch_many.js"}
            if st["status"] == "error":
                if is_limit(st):         # the next account can still get it
                    continue
                errors += 1
                done.add(r["uuid"])
                print(f"  {r['uuid']}: {st.get('error')}")
                continue
            done.add(r["uuid"])
            if st["status"] == "written":
                written += 1
                gave[at] += 1
            file = Path(st["file"])
            # The row's file is where the thread's sandbox unpacks it, wherever this folder is.
            manifest[r["uuid"]] = fms.manifest_row(r, account_id, fms.ROOT / SANDBOX_DIR / file.name)
        queue = [r for r in queue if r["uuid"] not in done]
        rows = sorted(manifest.values(), key=lambda row: row["start_time"], reverse=True)
        manifest_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        who = f"account {pool[at]['label']} of {len(pool)}"
        print(f"  fetched {written} of {len(missing)} ({errors} errors, {who}, {time.monotonic() - started:.0f} s)", flush=True)
        if failure:
            print(f"  {who} could not be used: {public(failure)}", flush=True)
        elif over:
            print(f"  {who} is over its log retrieval limit after {gave[at]} logs this run", flush=True)
        if failure or over:
            at, probe = at + 1, True
        else:
            probe = False
    if queue and at >= len(pool):
        stopped = ("every fetch account being over its log retrieval limit or unusable" if len(pool) > 1
                   else "the account's log retrieval limit (error 540, or no answer in time)")
    return written, errors, stopped, gave


def accounts() -> list[dict]:
    """The fetch accounts in the order a run uses them: [{"label", "env"}].

    The first is whatever config.js reads (ACCESS_TOKEN and MJS_RANDOM_KEY from the environment,
    or tmp/tensoul/.env on the operator's machine), so its env adds nothing. MJS_ACCESS_TOKEN_<n>
    with MJS_RANDOM_KEY_<n>, n from 2 to MAX_ACCOUNTS, add accounts; a slot missing either is skipped.
    """
    pool = [{"label": "1", "env": {}}]
    for n in range(2, MAX_ACCOUNTS + 1):
        token = os.environ.get(f"MJS_ACCESS_TOKEN_{n}", "").strip()
        key = os.environ.get(f"MJS_RANDOM_KEY_{n}", "").strip()
        if token and key:
            pool.append({"label": str(n), "env": {"ACCESS_TOKEN": token, "MJS_RANDOM_KEY": key}})
    return pool


def public(text: str) -> str:
    """An error for a log anyone can read: no account ids, game ids or tokens."""
    text = re.sub(r"\b[0-9a-f]{6}-[0-9a-f]{8}-[0-9a-f-]{20,}\b", "<game>", text)
    text = re.sub(r"[A-Za-z0-9_-]{24,}", "<long>", text)
    return re.sub(r"\d{6,}", "<n>", text).strip().replace("\n", " ")[-200:]


def check_accounts(game: str) -> None:
    """Ask every fetch account for one game and say which can still download logs."""
    pool = accounts()
    good = 0
    for a in pool:
        with tempfile.TemporaryDirectory() as tmp:
            status, cut, failure = fetch_batch([game], Path(tmp), CHECK_SECONDS, a["env"])
        row = next(iter(status.values()), None)
        if row and row["status"] == "written":
            verdict, good = "ok, downloaded one game", good + 1
        elif row and is_limit(row):
            verdict = "over its log retrieval limit (error 540)"
        elif row:
            verdict = f"error: {public(str(row.get('error')))}"
        elif cut:
            verdict = f"no answer in {CHECK_SECONDS} s"
        else:
            verdict = f"could not log in: {public(failure or 'no output')}"
        print(f"fetch account {a['label']} of {len(pool)}: {verdict}", flush=True)
    print(f"{good} of {len(pool)} fetch accounts can download logs now")
    sys.exit(0 if good else 1)


def fetch_batch(ids: list[str], out: Path, seconds: int = BATCH_SECONDS,
                env: dict[str, str] | None = None) -> tuple[dict[str, dict], bool, str]:
    """One fetch_many.js run as one account: {uuid: its status line}, whether it was cut off for
    time, and the error text when the account could not be used at all (a login that failed)."""
    if not (fms.TENSOUL / "fetch_many.js").exists():
        sys.exit(f"missing {fms.TENSOUL / 'fetch_many.js'}; clone tensoul into tmp/ first (see README)")
    failure = ""
    try:
        proc = subprocess.run(["node", "fetch_many.js", "--out", str(out), *ids], cwd=fms.TENSOUL,
                              capture_output=True, text=True, check=False, timeout=seconds,
                              env={**os.environ, **(env or {})})
        text, cut = proc.stdout, False
        if proc.returncode != 0 and not text.strip():
            failure = proc.stderr.strip()[-400:] or f"fetch_many.js exited {proc.returncode}"
    except subprocess.TimeoutExpired as late:
        raw = late.stdout or ""
        text, cut = raw if isinstance(raw, str) else raw.decode("utf-8", "replace"), True
    status = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{"):
            row = json.loads(line)
            status[row["uuid"]] = row
    return status, cut, failure


def is_limit(row: dict) -> bool:
    """A game that ended in error 540, the game's "log retrieval limit exceeded"."""
    return row.get("status") == "error" and '"code":540' in str(row.get("error", "")).replace(" ", "")


def refused(status: dict[str, dict], cut: bool) -> bool:
    """True when the account's log retrieval limit is in force: a game came back with error 540
    (after fetch_many.js's own retries), or the batch was cut off for time while retrying."""
    return cut or any(is_limit(row) for row in status.values())


if __name__ == "__main__":
    main()
