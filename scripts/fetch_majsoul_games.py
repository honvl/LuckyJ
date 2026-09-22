#!/usr/bin/env python3
"""Pull your recent Mahjong Soul games into ``data/self_games/majsoul``.

Drives the local tensoul checkout under ``tmp/tensoul`` (see README, "Scraping
Mahjong Soul games"). Game ids come from two places:

- the logged-in account's own record list (the client keeps the last 30);
- an amae-koromo export, ``data/self_games/majsoul/amae-koromo-records.json``,
  which reaches further back. With an API key from the site maintainer in
  ``tmp/tensoul/.env`` (``AMAE_KOROMO_TOKEN``), ``--refresh-amae`` pulls new
  records into it first, one request per second at most.

Every game not already on disk is converted to tenhou.net/6 format, and a
manifest records the seat you sat in so the review scripts know which hand is
yours.

    .venv/bin/python scripts/fetch_majsoul_games.py --since 2026-01-01
    .venv/bin/python scripts/fetch_majsoul_games.py --dry-run

The manifest ``data/self_games/majsoul/index.json`` holds one row per game:
uuid, file, start time, mode, your seat and placement, and every seat's final
score. Game files are the raw tensoul output, so ``review_self_game.py`` and
``review_win_speed.py`` can read them directly.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TENSOUL = ROOT / "tmp" / "tensoul"
OUT_DIR = ROOT / "data" / "self_games" / "majsoul"
MANIFEST = OUT_DIR / "index.json"
AMAE_EXPORT = OUT_DIR / "amae-koromo-records.json"
AMAE_API = "https://5-data.amae-koromo.com/api/v2/pl4"
AMAE_PAGE = 100
AMAE_MODES = "16.12.9.15.11.8"  # four-player ranked rooms: throne, jade, gold; south and east
AMAE_MIN_INTERVAL = 1.2  # seconds between requests; the key's condition is under 1/second

# Mahjong Soul lobby ids for the standard four-player ranked rooms.
MODE_NAMES = {
    1: "bronze-east", 2: "bronze-south",
    4: "silver-east", 5: "silver-south",
    8: "gold-east", 9: "gold-south",
    11: "jade-east", 12: "jade-south",
    15: "throne-east", 16: "throne-south",
}


def run_node(script: str, *args: str) -> str:
    if not (TENSOUL / script).exists():
        sys.exit(f"missing {TENSOUL / script}; clone tensoul into tmp/ first (see README)")
    proc = subprocess.run(
        ["node", script, *args], cwd=TENSOUL, capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        sys.exit(f"node {script} failed:\n{proc.stderr.strip()}")
    return proc.stdout


# ------------------------------------------------------------------ sources

def amae_token() -> str | None:
    """The amae-koromo API key, from the environment or tmp/tensoul/.env."""
    import os
    if os.environ.get("AMAE_KOROMO_TOKEN"):
        return os.environ["AMAE_KOROMO_TOKEN"]
    env = TENSOUL / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("AMAE_KOROMO_TOKEN="):
                return line.split("=", 1)[1].strip() or None
    return None


def amae_api_refresh(account_id: int, since: str | None, token: str, path: Path) -> int:
    """Pull the player's records from the amae-koromo API into the export file.

    Pages newest-first, one request per ``AMAE_MIN_INTERVAL`` seconds, and merges
    into the existing export (deduplicated by uuid). Returns the number of new rows.
    """
    start_ms = int(datetime.strptime(since, "%Y-%m-%d").timestamp() * 1000) if since else 0
    end_ms = int(time.time() * 1000)
    fetched: list[list] = []
    last_request = 0.0
    while True:
        wait = AMAE_MIN_INTERVAL - (time.time() - last_request)
        if wait > 0:
            time.sleep(wait)
        url = f"{AMAE_API}/player_records/{account_id}/{end_ms}/{start_ms}?limit={AMAE_PAGE}&mode={AMAE_MODES}&descending=true"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}",
                                                   "User-Agent": "LuckyJ self-review"})
        last_request = time.time()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                page = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:200]
            sys.exit(f"amae-koromo API {exc.code}: {body}")
        if not isinstance(page, list):
            sys.exit(f"unexpected amae-koromo response: {str(page)[:200]}")
        for r in page:
            fetched.append([r["uuid"], r["startTime"], r["endTime"], r["modeId"],
                            [[p["accountId"], p["nickname"], p.get("level"), p["score"], p.get("gradingScore")]
                             for p in r["players"]]])
        if len(page) < AMAE_PAGE:
            break
        end_ms = min(r["startTime"] for r in page) * 1000 - 1

    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"records": [], "stats": []}
    known = {r[0] for r in data["records"]}
    new_rows = [r for r in fetched if r[0] not in known]
    data["records"] = sorted(data["records"] + new_rows, key=lambda r: r[1], reverse=True)
    data["exported_at"] = datetime.now().isoformat(timespec="seconds")
    data["source"] = f"{AMAE_API}/player_records (API key)"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(new_rows)


def client_records(count: int) -> tuple[int | None, list[dict]]:
    """The account's own record list, normalised to the manifest's record shape."""
    listing = json.loads(run_node("records.js", "--count", str(count)))
    out = []
    for r in listing["records"]:
        accounts = {a["seat"]: a for a in r["accounts"]}
        scores = {p["seat"]: p["part_point_1"] for p in (r.get("result") or [])}
        out.append({
            "uuid": r["uuid"],
            "start_time": r["start_time"],
            "mode_id": r.get("mode_id"),
            "seats": [{
                "account_id": accounts[s]["account_id"] if s in accounts else None,
                "nickname": accounts[s]["nickname"] if s in accounts else "",
                "score": scores.get(s),
            } for s in range(4)],
            "source": "client",
        })
    return listing.get("account_id"), out


def amae_records(path: Path) -> list[dict]:
    """Records from the amae-koromo export (players are listed in seat order)."""
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for uuid, start, _end, mode_id, players in data["records"]:
        out.append({
            "uuid": uuid,
            "start_time": start,
            "mode_id": mode_id,
            "seats": [{"account_id": p[0], "nickname": p[1], "score": p[3]} for p in players],
            "source": "amae-koromo",
        })
    return out


# ----------------------------------------------------------------- manifest

def load_manifest() -> list[dict]:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return []


def save_manifest(rows: list[dict]) -> None:
    rows.sort(key=lambda r: r["start_time"], reverse=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def manifest_row(record: dict, account_id: int, file: Path) -> dict:
    seats = record["seats"]
    hero_seat = next((i for i, s in enumerate(seats) if s["account_id"] == account_id), None)
    scores = [s["score"] for s in seats]
    placement = None
    if hero_seat is not None and all(isinstance(x, int) for x in scores):
        # ties go to the seat nearer the starting dealer, as in the game
        order = sorted(range(4), key=lambda i: (-scores[i], i))
        placement = order.index(hero_seat) + 1
    return {
        "uuid": record["uuid"],
        "file": str(file.relative_to(ROOT)),
        "start_time": record["start_time"],
        "date": datetime.fromtimestamp(record["start_time"]).strftime("%Y-%m-%d %H:%M"),
        "mode_id": record.get("mode_id"),
        "mode": MODE_NAMES.get(record.get("mode_id"), f"mode-{record.get('mode_id')}"),
        "hero_seat": hero_seat,
        "hero_name": seats[hero_seat]["nickname"] if hero_seat is not None else None,
        "names": [s["nickname"] for s in seats],
        "placement": placement,
        "final_scores": scores,
        "source": record["source"],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--count", type=int, default=100,
                    help="how many of the account's own records to list (the server caps this at 30)")
    ap.add_argument("--since", help="only games starting on or after this date (YYYY-MM-DD)")
    ap.add_argument("--amae", type=Path, default=AMAE_EXPORT,
                    help=f"amae-koromo export to merge (default {AMAE_EXPORT.relative_to(ROOT)})")
    ap.add_argument("--account", type=int, help="your account id (default: from the client login)")
    ap.add_argument("--refresh-amae", action="store_true",
                    help="pull new records from the amae-koromo API first (needs AMAE_KOROMO_TOKEN)")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched and stop")
    args = ap.parse_args()

    account_id, records = client_records(args.count)
    if args.account:
        account_id = args.account
    if account_id is None:
        sys.exit("could not determine the account id; pass --account")

    if args.refresh_amae:
        token = amae_token()
        if not token:
            sys.exit("no AMAE_KOROMO_TOKEN in the environment or tmp/tensoul/.env")
        added = amae_api_refresh(account_id, args.since, token, args.amae)
        print(f"amae-koromo API: {added} new records merged into {args.amae.relative_to(ROOT)}")

    seen = {r["uuid"] for r in records}
    for r in amae_records(args.amae):
        if r["uuid"] not in seen:
            records.append(r)
            seen.add(r["uuid"])
    if args.since:
        cutoff = datetime.strptime(args.since, "%Y-%m-%d").timestamp()
        records = [r for r in records if r["start_time"] >= cutoff]
    if not records:
        sys.exit("no game records to work with")

    manifest = {row["uuid"]: row for row in load_manifest()}
    missing = [r for r in records if r["uuid"] not in manifest
               or not (ROOT / manifest[r["uuid"]]["file"]).exists()]
    print(f"account {account_id}: {len(records)} records"
          f"{' since ' + args.since if args.since else ''}, "
          f"{len(records) - len(missing)} already stored, {len(missing)} to fetch")
    if args.dry_run or not missing:
        for r in missing:
            print(f"  would fetch {r['uuid']}  {datetime.fromtimestamp(r['start_time']):%Y-%m-%d %H:%M}"
                  f"  ({r['source']})")
        if not missing:
            print("nothing to do")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = run_node("fetch_many.js", "--out", str(OUT_DIR), *[r["uuid"] for r in missing])
    status = {}
    for line in out.splitlines():
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
        manifest[r["uuid"]] = manifest_row(r, account_id, Path(st["file"]))
    save_manifest(list(manifest.values()))
    print(f"wrote {written} new game files, {errors} errors; manifest has {len(manifest)} games")


if __name__ == "__main__":
    main()
