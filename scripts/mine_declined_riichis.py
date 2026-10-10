#!/usr/bin/env python3
"""The figures behind guide chapter 31, "Four checks before you declare a riichi".

Every riichi the user declared in the replays (354 in 173 games since January) is read at the moment of
declaring: how many winning tiles were live, whether a yaku stood without the riichi, whether the wait was
furiten (a winning tile already in the user's own river), whether another player was already in riichi,
the turn, and how the hand ended. Mortal's weight on declaring comes from ``site/replays/*.json``; a
riichi it gave under 25% is one it would not declare.

Four screens are read off the table, each from what the user can see when declaring:

- furiten: a winning tile is in the user's own river, so the hand can only win by tsumo;
- late: the riichi is on the user's 13th turn or later;
- thin with a yaku: three live tiles or fewer, and a ron would have a yaku without the riichi;
- into a riichi: another player is already in riichi and the wait has three live tiles or fewer.

The screens are read off the same riichis they are tested on, so they describe the user's games and are
not a held-out test.

Run it from the repo root with the project venv (it has ``mahjong`` and ``libriichi``)::

    .venv/bin/python scripts/mine_declined_riichis.py   # writes analysis/declined-riichis-2026-10-07.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_personal_guide as bpg  # noqa: E402
import tenhou_replay as tr  # noqa: E402
from tenhou_replay import base  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
REPLAYS = ROOT / "site/replays"
OUT = ROOT / "analysis/declined-riichis-2026-10-07.json"
LOW = 0.25
LATE_TURN = 13
THIN = 3

SCREENS = {
    "furiten": lambda r: bool(r["furiten"]),
    "late": lambda r: r["turn"] >= LATE_TURN,
    "thin_with_yaku": lambda r: r["live"] <= THIN and r["yaku"],
    "into_a_riichi": lambda r: r["into_a_riichi"] and r["live"] <= THIN,
}


def riichi_rows(manifest: list[dict]) -> list[dict]:
    rows = []
    for g in manifest:
        replay = json.loads((REPLAYS / f"{g['uuid']}.json").read_text(encoding="utf-8"))
        hero = replay["hero"]
        weights, results = {}, {}
        for h in replay["hands"]:
            ais = {a["i"]: a for a in h["ai"]}
            for i, x in enumerate(h["ev"]):
                if x[0] == "r" and x[1] == hero:
                    weights[h["round"]] = dict(ais[i - 1]["p"]).get("riichi", 0.0)
                    end, result = h["end"], "draw"
                    if end["kind"] == "win":
                        if any(w["seat"] == hero for w in end["wins"]):
                            result = "won"
                        elif any(w["from"] == hero for w in end["wins"]):
                            result = "dealt"
                        else:
                            result = "paid"
                    results[h["round"]] = result
        for log in tr.load_logs(ROOT / g["file"]):
            game = tr.replay(log)
            mine = [e for e in game["events"] if e["seat"] == g["hero_seat"]]
            for k, e in enumerate(mine):
                if not e["riichi"]:
                    continue
                name = game["round_name"]
                rest = list(e["hand_before"])
                rest.remove(e["tile"])
                winning = tr.waits(rest, e["meld_tiles"], e["closed"])
                river = [base(m["tile"]) for m in mine[:k]] + [base(e["tile"])]
                spot = {"id": "scan", "game": g["uuid"][:15], "round": name}
                frame, _ = bpg.build_frame(spot, {"turn": e["turn"], "kind": "riichi"}, g, log, game)
                rows.append({
                    "game": g["uuid"], "date": g["date"], "round": name, "turn": e["turn"],
                    "waits": [bpg.site_tile(t) for t in winning],
                    "furiten": [bpg.site_tile(t) for t in winning if base(t) in river],
                    "live": frame["you"]["accept"], "yaku": frame["ron_yaku_without_riichi"],
                    "into_a_riichi": any("riichi" in t["label"] for t in frame["threats"]),
                    "callers": sum(1 for t in frame["threats"] if "call" in t["label"]),
                    "rank": next(s["rank"] for s in frame["table"]["scores"] if s["seat"] == "self"),
                    "left": frame["left"], "mortal": weights[name], "result": results[name],
                })
    return rows


def tally(rows: list[dict]) -> dict:
    count = lambda key: sum(1 for r in rows if r["result"] == key)  # noqa: E731
    return {"riichis": len(rows), "mortal_low": sum(1 for r in rows if r["mortal"] < LOW),
            "won": count("won"), "dealt": count("dealt"), "paid": count("paid"), "draw": count("draw")}


def main() -> None:
    os.chdir(ROOT)
    manifest = sorted(json.loads(MANIFEST.read_text(encoding="utf-8")), key=lambda g: g["start_time"])
    rows = riichi_rows(manifest)
    flagged = [r for r in rows if any(f(r) for f in SCREENS.values())]
    out = {
        "all": tally(rows),
        "screens": {name: tally([r for r in rows if f(r)]) for name, f in SCREENS.items()},
        "any_screen": tally(flagged),
        "no_screen": tally([r for r in rows if r not in flagged]),
        "furiten_riichis": [{k: r[k] for k in ("date", "round", "turn", "waits", "furiten", "live", "mortal", "result")}
                            for r in rows if r["furiten"]],
        "riichis": rows,
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    for k in ("all", "screens", "any_screen", "no_screen"):
        print(k, json.dumps(out[k]))


if __name__ == "__main__":
    main()
