#!/usr/bin/env python3
"""Fetch Wind-Up Bird (Nejimakidori) reviews of your own games and keep them in a local cache.

The review site (https://neji-ai.spark-fly.net) grades every decision of one seat: how strongly its model prefers its
own choice (severity) times how much the decision matters (importance). Its API takes a replay link and a seat:

    POST https://neji-ai.spark-fly.net/api/replay
    Authorization: Bearer <token>
    {"url": "https://mahjongsoul.game.yo-star.com/?paipu=<game id>", "seat": 0}

A token covers 24 single-seat reviews and expires after 24 hours. It is made by hand with the "Generate token"
button on the site's API tab (the button sits behind reCAPTCHA) and read here from ``NEJI_REPLAY_TOKEN``, either in
the environment or in the repo's gitignored ``.env.local``. Several tokens, separated by commas, are used one after
the other: when one is spent the next takes over on the same game. A token is never printed.

Games come from ``site/replays`` (the hero's seat is in each replay file). Only the bare game id is sent, never an
account id. Each review is stored whole, gzipped, as ``data/neji_reviews/<game id>-s<seat>.json.gz`` with the fetch
time, because the response carries no model version and the site ships new weights often. The folder is gitignored:
a review holds the other players' names and account ids.

    .venv/bin/python scripts/fetch_neji_reviews.py                 # the newest games not yet cached, up to 24
    .venv/bin/python scripts/fetch_neji_reviews.py --order spread  # an even spread over all your games
    .venv/bin/python scripts/fetch_neji_reviews.py --order spread --rated   # only games both Mortal models rated
    .venv/bin/python scripts/fetch_neji_reviews.py --games ID ...  # these games
    .venv/bin/python scripts/fetch_neji_reviews.py --dry-run       # list what would be fetched
    .venv/bin/python scripts/fetch_neji_reviews.py --status        # what the cache holds
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://neji-ai.spark-fly.net/api/replay"
REPLAY_LINK = "https://mahjongsoul.game.yo-star.com/?paipu={id}"
REPLAYS = ROOT / "site" / "replays"
CACHE = ROOT / "data" / "neji_reviews"
RATED_ROWS = ROOT / "data" / "ladder_skill" / "jade_s42.jsonl"
ENV_FILE = ROOT / ".env.local"
TOKEN_KEY = "NEJI_REPLAY_TOKEN"
PER_TOKEN = 24


class TokenProblem(Exception):
    """The API refused the token: it is missing, expired (401) or used up (429)."""


def read_tokens(env: dict | None = None, env_file: Path = ENV_FILE) -> list[str]:
    """The tokens to use, in order: the environment's if set, else the file's. Several are split on commas or spaces."""
    env = os.environ if env is None else env
    raw = (env.get(TOKEN_KEY) or "").strip()
    if not raw and env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and key.strip() == TOKEN_KEY:
                raw = value.strip().strip('"').strip("'")
    return [t for t in raw.replace(",", " ").split() if t]


def own_games(replays: Path = REPLAYS) -> list[dict]:
    """Your published replays, newest first: id, date, room, placement, points and the hero's seat."""
    index = json.loads((replays / "index.json").read_text(encoding="utf-8"))
    games = []
    for row in index["games"]:
        path = replays / f"{row['id']}.json"
        if not path.exists():
            continue
        hero = json.loads(path.read_text(encoding="utf-8"))["hero"]
        games.append({"id": row["id"], "date": row["date"], "room": row.get("room"),
                      "placement": row["placement"], "points": row.get("points"), "seat": hero})
    return sorted(games, key=lambda g: g["date"], reverse=True)


def cache_path(game_id: str, seat: int, cache: Path = CACHE) -> Path:
    return cache / f"{game_id}-s{seat}.json.gz"


def rated_ids(rows: Path = RATED_ROWS) -> set[str]:
    """Games the ladder scorer has rated with Mortal (``mine_ladder_skill.py``), for the placement comparison."""
    if not rows.exists():
        return set()
    with open(rows, encoding="utf-8") as f:
        return {Path(json.loads(line)["file"]).stem for line in f}


def pick(games: list[dict], cache: Path, limit: int, order: str = "newest", ids: list[str] | None = None,
         only: set[str] | None = None) -> list[dict]:
    """The games to fetch now: not yet cached, in the asked order, at most ``limit``."""
    todo = [g for g in games if not cache_path(g["id"], g["seat"], cache).exists()]
    if only is not None:
        todo = [g for g in todo if g["id"] in only]
    if ids:
        wanted = set(ids)
        unknown = wanted - {g["id"] for g in games}
        if unknown:
            raise SystemExit(f"not among your replays: {', '.join(sorted(unknown))}")
        todo = [g for g in todo if g["id"] in wanted]
    elif order == "oldest":
        todo = todo[::-1]
    elif order == "spread" and len(todo) > limit > 0:
        # evenly spaced over the uncached games in date order, so the sample is not one week of play
        step = len(todo) / limit
        todo = [todo[int(i * step + step / 2)] for i in range(limit)]
    return todo[:limit]


def parse_review(body: str) -> dict:
    """The review object from a response body: one JSON document, or the site's line stream ending in "complete"."""
    body = body.strip()
    try:
        doc = json.loads(body)
    except json.JSONDecodeError:
        doc = None
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            message = json.loads(line)
            if message.get("type") == "complete":
                doc = message
        if doc is None:
            raise ValueError("the response held no completed review")
    game = doc.get("game", doc)
    if not isinstance(game, dict) or "grades" not in game or "annotations" not in game:
        raise ValueError("the response is not a review (no grades or annotations)")
    return game


def request_review(token: str, game_id: str, seat: int, opener=urllib.request.urlopen, timeout: int = 900) -> dict:
    payload = json.dumps({"url": REPLAY_LINK.format(id=game_id), "seat": seat}).encode()
    req = urllib.request.Request(API, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "replay-review-cache/1"})
    try:
        with opener(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise TokenProblem("the token is invalid or has expired (401): make a new one on the site's API tab") from None
        if e.code == 429:
            raise TokenProblem("this token's 24 reviews are used up (429): make a new one on the site's API tab") from None
        detail = e.read().decode("utf-8", "replace")[:200] if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTP {e.code} {detail}".strip()) from None
    return parse_review(body)


def store(review: dict, game: dict, cache: Path = CACHE, now: dt.datetime | None = None) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    now = now or dt.datetime.now(dt.timezone.utc)
    doc = {"fetched_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "game_id": game["id"], "seat": game["seat"],
           "placement": game["placement"], "points": game.get("points"), "review": review}
    path = cache_path(game["id"], game["seat"], cache)
    tmp = path.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(path)
    return path


def load(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def cached(cache: Path = CACHE) -> list[Path]:
    return sorted(cache.glob("*-s[0-3].json.gz")) if cache.exists() else []


def fetch(todo: list[dict], tokens: str | list[str], cache: Path = CACHE, opener=urllib.request.urlopen,
          out=print) -> dict:
    """Fetch ``todo`` in order. A refused token gives way to the next one and the same game is asked again; the run
    stops when none is left. A game that fails for another reason is reported and skipped."""
    tokens = [tokens] if isinstance(tokens, str) else list(tokens)
    done, failed, stopped, used = [], [], None, 1
    for n, game in enumerate(todo, 1):
        t0 = time.time()
        review = None
        while tokens and review is None:
            try:
                review = request_review(tokens[0], game["id"], game["seat"], opener=opener)
            except TokenProblem as e:
                tokens.pop(0)
                stopped = str(e)
                if tokens:
                    used += 1
                    out(f"  token {used - 1} is spent, moving to the next ({len(tokens)} left)")
            except Exception as e:  # noqa: BLE001  one bad game should not end the run
                failed.append({"id": game["id"], "error": str(e)})
                out(f"  {n}/{len(todo)} {game['id']} failed: {e}")
                break
        if not tokens:
            break
        stopped = None
        if review is None:
            continue
        store(review, game, cache)
        grade = (review.get("grades") or [{}] * 4)[game["seat"]]
        done.append(game["id"])
        out(f"  {n}/{len(todo)} {game['id']} seat {game['seat']}: grade {grade.get('letter')} "
            f"{grade.get('score', 0):.1f}, placed {game['placement']} ({time.time() - t0:.0f}s)")
    return {"fetched": done, "failed": failed, "stopped": stopped}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch Wind-Up Bird reviews of your own games into data/neji_reviews.")
    ap.add_argument("--limit", type=int, default=None, help="how many to fetch (default: 24 for each token)")
    ap.add_argument("--order", choices=("newest", "oldest", "spread"), default="newest")
    ap.add_argument("--games", nargs="*", help="game ids to fetch")
    ap.add_argument("--rated", action="store_true", help="only games in data/ladder_skill/jade_s42.jsonl")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    games = own_games()
    if args.status:
        have = cached()
        print(f"{len(have)} reviews cached of {len(games)} replays")
        return 0
    limit = args.limit if args.limit is not None else PER_TOKEN * max(1, len(read_tokens()))
    todo = pick(games, CACHE, limit, args.order, args.games, rated_ids() if args.rated else None)
    if not todo:
        print("nothing to fetch: every asked game is cached")
        return 0
    if args.dry_run:
        for g in todo:
            print(f"{g['id']}  seat {g['seat']}  {g['date']}  {g['room']}  placed {g['placement']}")
        print(f"{len(todo)} to fetch")
        return 0
    tokens = read_tokens()
    if not tokens:
        print(f"no token: put {TOKEN_KEY}=... in .env.local (API tab of https://neji-ai.spark-fly.net)", file=sys.stderr)
        return 2
    print(f"fetching {len(todo)} reviews (about two minutes each)")
    result = fetch(todo, tokens)
    print(f"fetched {len(result['fetched'])}, failed {len(result['failed'])}, cached now {len(cached())}")
    if result["stopped"]:
        print(result["stopped"], file=sys.stderr)
        return 3
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
