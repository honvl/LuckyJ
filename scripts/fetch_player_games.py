#!/usr/bin/env python3
"""Fetch a subscriber's ranked Mahjong Soul games into a folder the tutor's thread can use.

The player is pinned by account id (the same nickname can exist on the China, Japan and
International servers). Game ids come from the amae-koromo API (Gold room and above, the key in
tmp/tensoul/.env); each game is downloaded by the local tensoul checkout, logged in as the
operator, and written in tenhou.net/6 format.

    .venv/bin/python scripts/fetch_player_games.py --account 120182062 --out service/players/ms-120182062/games

The folder gets ``index.json`` in the shape ``thread.py new`` expects (hero_seat, hero_name,
placement, final scores). Its ``file`` paths point where the sandbox unpacks the games
(``data/self_games/majsoul/<file>``), since this folder is uploaded as is. Rerunning only fetches
games not already in the folder.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_majsoul_games as fms  # noqa: E402

SANDBOX_DIR = "data/self_games/majsoul"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--account", type=int, required=True, help="the player's Mahjong Soul account id")
    ap.add_argument("--out", type=Path, required=True, help="folder for the games and index.json")
    ap.add_argument("--since", help="only games from this date (YYYY-MM-DD); default: one year back")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched and stop")
    args = ap.parse_args()

    since = args.since or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    token = fms.amae_token()
    if not token:
        sys.exit("no AMAE_KOROMO_TOKEN in the environment or tmp/tensoul/.env")

    export = out / "amae-koromo-records.json"
    added = fms.amae_api_refresh(args.account, since, token, export)
    cutoff = datetime.strptime(since, "%Y-%m-%d").timestamp()
    records = [r for r in fms.amae_records(export) if r["start_time"] >= cutoff]
    manifest_path = out / "index.json"
    manifest = {row["uuid"]: row for row in json.loads(manifest_path.read_text(encoding="utf-8"))} if manifest_path.exists() else {}
    missing = [r for r in records if r["uuid"] not in manifest or not (out / Path(manifest[r["uuid"]]["file"]).name).exists()]
    print(f"account {args.account}: {len(records)} ranked games since {since} ({added} new on amae-koromo), "
          f"{len(records) - len(missing)} already here, {len(missing)} to fetch")
    if args.dry_run or not missing:
        return

    status = {}
    for line in fms.run_node("fetch_many.js", "--out", str(out), *[r["uuid"] for r in missing]).splitlines():
        line = line.strip()
        if line.startswith("{"):
            row = json.loads(line)
            status[row["uuid"]] = row

    written = errors = 0
    for r in missing:
        st = status.get(r["uuid"], {"status": "error", "error": "no output from fetch_many.js"})
        if st["status"] == "error":
            errors += 1
            print(f"  {r['uuid']}: {st.get('error')}")
            continue
        written += st["status"] == "written"
        file = Path(st["file"])
        # The row's file is where the thread's sandbox unpacks it, wherever this folder is.
        row = fms.manifest_row(r, args.account, fms.ROOT / SANDBOX_DIR / file.name)
        manifest[r["uuid"]] = row
    rows = sorted(manifest.values(), key=lambda row: row["start_time"], reverse=True)
    manifest_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {written} games, {errors} errors; {len(rows)} games in {out}")
    if errors and not written:
        sys.exit(1)


if __name__ == "__main__":
    main()
