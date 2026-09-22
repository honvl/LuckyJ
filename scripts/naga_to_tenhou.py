#!/usr/bin/env python3
"""Convert the cached NAGA reports of LuckyJ's games into tenhou.net/6 logs.

Every cached report carries the full mjai event stream for all four seats
(deals, every draw, discards, calls, riichi) and the round results, so the
games can be rebuilt as Tenhou-format logs and pushed through the same replay
and review code as the Mahjong Soul corpus. That makes LuckyJ a baseline under
identical definitions for ``review_win_speed.py`` and ``review_self_game.py``.

    .venv/bin/python scripts/naga_to_tenhou.py            # all cached reports
    .venv/bin/python scripts/naga_to_tenhou.py --limit 50 # smoke test

Writes ``data/local_sources/luckyj_tenhou/<report_id>.json`` and a manifest
``index.json`` in the shape ``fetch_majsoul_games.py`` produces (hero seat per
game). Each converted game is replayed and its per-hand deltas reconciled to
the next hand's starting scores before it is written; games that fail are
reported and skipped.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_luckyj as naga  # noqa: E402
import tenhou_replay as tr  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
naga.SHEET_CSV = ROOT / "data" / "LuckyJ.csv"
naga.CACHE_DIR = ROOT / "data" / "report_cache"
OUT_DIR = ROOT / "data" / "local_sources" / "luckyj_tenhou"

HONORS = {"E": 41, "S": 42, "W": 43, "N": 44, "P": 45, "F": 46, "C": 47}
REDS = {"5mr": 51, "5pr": 52, "5sr": 53}
BAKAZE = {"E": 0, "S": 4, "W": 8, "N": 12}
TSUMOGIRI = 60


def code(tile: str) -> int:
    if tile in REDS:
        return REDS[tile]
    if tile in HONORS:
        return HONORS[tile]
    return {"m": 10, "p": 20, "s": 30}[tile[1]] + int(tile[0])


def code_from_tenhou_id(tid: int) -> int:
    """Tenhou's 0-135 tile ids, used for dora markers in hora messages."""
    kind, copy = divmod(tid, 4)
    if kind >= 27:
        return 41 + (kind - 27)
    suit, num = divmod(kind, 9)
    base = (suit + 1) * 10 + num + 1
    if num == 4 and copy == 0:
        return {15: 51, 25: 52, 35: 53}[base]
    return base


def meld_token(letter: str, actor: int, target: int, called: str, consumed: list[str]) -> str:
    """Tenhou meld token; tiles before the letter say who fed the call."""
    offset = (target - actor) % 4  # 3 left, 2 across, 1 right
    tiles = [f"{code(t):02d}" for t in consumed]
    pre = {3: 0, 2: 1, 1: len(tiles)}[offset]
    return "".join(tiles[:pre]) + letter + f"{code(called):02d}" + "".join(tiles[pre:])


def convert_kyoku(states: list[dict]) -> list:
    start = states[0]["info"]["msg"]
    kyoku_index = BAKAZE[start["bakaze"]] + start["kyoku"] - 1
    header = [kyoku_index, start["honba"], start["kyotaku"]]
    scores = list(start["scores"])
    dora = [code(start["dora_marker"])]
    haipai = [[code(t) for t in hand] for hand in start["tehais"]]
    draws = [[] for _ in range(4)]
    discards = [[] for _ in range(4)]
    pending_reach: set[int] = set()
    left = start.get("left_hai_num")

    for state in states[1:]:
        msg = state["info"]["msg"]
        kind = msg.get("type")
        actor = msg.get("actor")
        if "left_hai_num" in msg:
            left = msg["left_hai_num"]
        if kind == "tsumo":
            draws[actor].append(code(msg["pai"]))
        elif kind == "dahai":
            tile = TSUMOGIRI if msg["tsumogiri"] else code(msg["pai"])
            if actor in pending_reach:
                discards[actor].append(f"r{tile}")
                pending_reach.discard(actor)
            else:
                discards[actor].append(tile)
        elif kind == "reach":
            pending_reach.add(actor)
        elif kind == "chi":
            draws[actor].append(meld_token("c", actor, msg["target"], msg["pai"], msg["consumed"]))
        elif kind == "pon":
            draws[actor].append(meld_token("p", actor, msg["target"], msg["pai"], msg["consumed"]))
        elif kind == "daiminkan":
            draws[actor].append(meld_token("m", actor, msg["target"], msg["pai"], msg["consumed"]))
            discards[actor].append(0)
        elif kind == "kakan":
            discards[actor].append("".join(f"{code(t):02d}" for t in msg["consumed"]) + "k" + f"{code(msg['pai']):02d}")
        elif kind == "ankan":
            tiles = [f"{code(t):02d}" for t in msg["consumed"]]
            discards[actor].append("".join(tiles[:3]) + "a" + tiles[3])
        elif kind == "dora":
            dora.append(code(msg["dora_marker"]))

    end_msgs = start.get("end_msgs") or []
    ura: list[int] = []
    if end_msgs and end_msgs[0].get("type") == "hora":
        result = ["和了"]
        for msg in end_msgs:
            if msg.get("type") != "hora":
                continue
            if msg.get("uradora_markers") and not ura:
                ura = [code_from_tenhou_id(t) for t in msg["uradora_markers"]]
            han = f"役満{msg.get('raw_delta', 0)}点" if msg.get("yakuman") else \
                f"{msg.get('hu', 0)}符{msg.get('fan', 0)}飜{msg.get('raw_delta', 0)}点"
            yakus = [f"yaku{y}({h}飜)" for y, h in (msg.get("yakus_detail") or [])]
            result.extend([list(msg["deltas"]), [msg["actor"], msg["target"], msg["actor"], han, *yakus]])
    elif end_msgs:
        msg = end_msgs[0]
        label = "流局" if left == 0 else "途中流局"
        result = [label, list(msg.get("deltas") or [0, 0, 0, 0])]
    else:
        result = ["流局", [0, 0, 0, 0]]

    log = [header, scores, dora, ura]
    for seat in range(4):
        log.extend([haipai[seat], draws[seat], discards[seat]])
    log.append(result)
    return log


def verify(logs: list[list], final_scores: list[int] | None) -> str | None:
    """Replay every hand and reconcile deltas hand to hand. Returns an error or None."""
    for i, log in enumerate(logs):
        game = tr.replay(log)
        for p in game["players"]:
            # a tsumo winner's last draw has no discard after it
            if p["ci"] != len(p["discards"]) or p["di"] < len(p["draws"]) - 1 or len(p["hand"]) > 13:
                return f"hand {i} {game['round_name']}: replay did not consume every event"
        deltas = tr.result_deltas(log[-1])
        paid = tr.riichi_sticks_paid(log)
        expected = [log[1][s] + deltas[s] - 1000 * paid[s] for s in range(4)]
        if i + 1 < len(logs):
            if expected != list(logs[i + 1][1]):
                return f"hand {i} {game['round_name']}: scores {expected} vs next start {list(logs[i + 1][1])}"
        elif final_scores is not None:
            # the report's last scores predate Tenhou's award of leftover sticks to first place
            leftover = log[0][2] + sum(paid)
            if (log[-1][0] == "和了" or not leftover) and expected != final_scores:
                return f"final scores {expected} vs {final_scores}"
    return None


def convert_report(row: dict) -> tuple[dict | None, str | None]:
    data = naga.fetch_report(row["report_id"])
    naga.normalize_report(data)
    names = list((data.get("player_info") or {}).get("name") or [])
    hero = next((i for i, n in enumerate(names) if "LuckyJ" in str(n)), row["actor"])
    logs = [convert_kyoku(k) for k in data["pred"] if k and k[0]["info"]["msg"].get("type") == "start_kyoku"]
    if not logs:
        return None, "no kyoku"
    last_end = (data["pred"][-1][0]["info"]["msg"].get("end_msgs") or [{}])[-1]
    final_scores = list(last_end["scores"]) if last_end.get("scores") else None
    err = verify(logs, final_scores)
    if err:
        return None, err
    log_id = row.get("tenhou_log_id") or data.get("haihu_id") or ""
    try:
        start_time = int(datetime.strptime(log_id[:10], "%Y%m%d%H").timestamp())
    except ValueError:
        start_time = 0
    game = {
        "title": [row.get("room", ""), log_id],
        "name": names,
        "rule": {"disp": row.get("room", ""), "aka": 1},
        "log": logs,
    }
    if final_scores:
        order = sorted(range(4), key=lambda s: (-final_scores[s], s))
        placement = order.index(hero) + 1
    else:
        placement = row.get("rank")
    manifest = {
        "uuid": row["report_id"],
        "start_time": start_time,
        "date": log_id[:10],
        "mode_id": None,
        "mode": f"tenhou-{row.get('room', '').lower()}",
        "hero_seat": hero,
        "hero_name": names[hero] if hero < len(names) else "LuckyJ",
        "names": names,
        "placement": placement,
        "final_scores": final_scores,
        "source": "naga",
    }
    return {"game": game, "manifest": manifest}, None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, help="convert only the first N sheet rows")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()

    rows = naga.parse_rows()
    if args.limit:
        rows = rows[:args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    manifest, errors = [], []
    for row in rows:
        try:
            result, err = convert_report(row)
        except Exception as exc:  # noqa: BLE001 - report and keep going
            result, err = None, f"{type(exc).__name__}: {exc}"
        if err:
            errors.append((row["report_id"], err))
            continue
        path = args.out / f"{row['report_id']}.json"
        path.write_text(json.dumps(result["game"], ensure_ascii=False), encoding="utf-8")
        result["manifest"]["file"] = str(path.relative_to(ROOT))
        manifest.append(result["manifest"])
    manifest.sort(key=lambda r: r["start_time"], reverse=True)
    (args.out / "index.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"converted {len(manifest)} games, {len(errors)} skipped -> {args.out.relative_to(ROOT)}")
    for report_id, err in errors[:20]:
        print(f"  {report_id[:16]}: {err}")


if __name__ == "__main__":
    main()
