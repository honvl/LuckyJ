#!/usr/bin/env python3
"""The figures behind guide chapter 32: the riichis that found the user with no safe tile in hand.

Chapter 30's window (7 October 18:25 to 10 October 14:43) held 107 riichis by other players, and on 14 of them the
user's hand held no tile safe against the declarer (``mine_early_safe_tiles.py riichi``: genbutsu, suji, nakasuji,
an honor with two other copies showing, or a dead honor). For each of the 14 this goes back over the user's discards
before the declaration and finds the tiles that would have been safe against the declarer at the user's next turn
(had the user kept one, its discarded copy would not show, so it is taken off the visible count). Each such discard
is set beside Mortal's probabilities on that turn (``site/replays``): when Mortal's first choice was another tile,
Mortal kept the tile the user threw.

Each riichi then falls into one group:

- ended: the hand ended before the user's next discard;
- early: the declaration came by the user's 3rd turn and no tile the user had thrown would have been safe;
- tenpai: the user was already tenpai when it came;
- same: Mortal threw every would-be-safe tile the user threw, on the same turn;
- kept: on some turn Mortal's first choice kept a would-be-safe tile the user threw.

It also writes LuckyJ's no-safe-tile rate at the same declarer discard for the user's riichis while not tenpai, and,
from ``mine_early_safe_tiles.py leftovers`` over every game since January, the user's and LuckyJ's choice between a
terminal already in an opponent's river and a live one (chapter 17's comparison).

usage: mine_no_safe_riichis.py ESR_YOU ESR_LJ LEFTOVERS_YOU LEFTOVERS_LJ OUT.json
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mine_early_safe_tiles as est  # noqa: E402
import tenhou_replay as tr  # noqa: E402
from build_personal_guide import safety, site_tile, visible_counter, meld_snapshots  # noqa: E402
from tenhou_replay import base  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
REPLAYS = ROOT / "site/replays"
FIRST, LAST = "261008-f937c8f1", "261011-285cf167"  # chapter 30's window
SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}
REL = ("you", "shimocha", "toimen", "kamicha")


def window(manifest: list[dict]) -> list[dict]:
    a = next(k for k, g in enumerate(manifest) if g["uuid"].startswith(FIRST))
    b = next(k for k, g in enumerate(manifest) if g["uuid"].startswith(LAST))
    return manifest[a:b + 1]


def mortal_on(replay: dict, round_name: str, nth: int) -> dict:
    """Mortal's probabilities on the user's nth discard of a hand (1-based)."""
    h = next(h for h in replay["hands"] if h["round"] == round_name)
    ais = {a["i"]: a for a in h["ai"]}
    discards = [i for i, x in enumerate(h["ev"]) if x[0] == "d" and x[1] == replay["hero"]]
    a = ais.get(discards[nth - 1] - 1) or ais.get(discards[nth - 1])
    return dict(a["p"]) if a else {}


def examine(g: dict, row: dict) -> dict:
    hero = g["hero_seat"]
    log = tr.load_logs(str(ROOT / g["file"]))[row["li"]]
    game = tr.replay(log)
    declarer = row["R"]
    decl = next(e for e in game["events"] if e["seat"] == declarer and e["riichi"])
    mine = [e for e in game["events"] if e["seat"] == hero]
    before = [e for e in mine if e["index"] < decl["index"]]
    after = next((e for e in mine if e["index"] > decl["index"]), None)
    out = {"game": g["uuid"], "date": g["date"], "round": game["round_name"], "declarer": REL[(declarer - hero) % 4],
           "declarer_discard": row["r_turn"], "shanten": row["x_shanten"], "open": row["x_open"],
           "your_next_turn": after["turn"] if after else None, "dealt": row["into_R"], "cuts": []}
    if after is None:
        out["group"] = "ended"
        return out
    snap = meld_snapshots(game, after["index"] - 1)
    snap[hero] = after["melds"]
    visible = visible_counter(after["hand_before"], after, game["players"], snap, game["dora_indicators"][:1])
    replay = json.loads((REPLAYS / f"{g['uuid']}.json").read_text(encoding="utf-8"))
    for k, e in enumerate(before, 1):
        seen = visible.copy()
        seen[base(e["tile"])] -= 1
        label = safety(e["tile"], declarer, after, game, seen)
        if label not in SAFE:
            continue
        p = mortal_on(replay, game["round_name"], k)
        name = site_tile(e["tile"])
        top = max(p.items(), key=lambda x: x[1]) if p else (None, 0.0)
        out["cuts"].append({"turn": e["turn"], "tile": name, "label": label, "mortal": round(p.get(name, 0.0), 3),
                            "mortal_top": top[0], "mortal_top_p": round(top[1], 3)})
    if row["x_shanten"] == 0:
        out["group"] = "tenpai"
    elif not out["cuts"] and after["turn"] <= 3:
        out["group"] = "early"
    elif any(c["mortal_top"] != c["tile"] for c in out["cuts"]):
        out["group"] = "kept"
    else:
        out["group"] = "same"
    return out


def main(esr_you: str, esr_lj: str, lo_you: str, lo_lj: str, out: str) -> None:
    os.chdir(ROOT)
    manifest = sorted(json.loads(MANIFEST.read_text(encoding="utf-8")), key=lambda g: g["start_time"])
    games = {g["uuid"]: g for g in window(manifest)}
    rows = [r for r in json.loads(Path(esr_you).read_text())["rows"] if r["lj_X"] and r["game"] in games]
    lj = [r for r in json.loads(Path(esr_lj).read_text())["rows"] if r["lj_X"]]
    none = [r for r in rows if r["n_safe"] == 0]
    riichis = [examine(games[r["game"]], r) for r in none]
    groups = defaultdict(int)
    for x in riichis:
        groups[x["group"]] += 1
    by_turn = defaultdict(list)
    for r in lj:
        if r["x_shanten"] >= 1:
            by_turn[min(r["r_turn"], 15)].append(r)
    waiting = [r for r in rows if r["x_shanten"] >= 1]
    expected = sum(sum(x["n_safe"] == 0 for x in by_turn[min(r["r_turn"], 15)]) / len(by_turn[min(r["r_turn"], 15)])
                   for r in waiting)
    per_game = defaultdict(int)
    for x in riichis:
        per_game[x["game"]] += 1
    you_lo = json.loads(Path(lo_you).read_text())["rows"]
    rates = est.fitted_rates(json.loads(Path(lo_lj).read_text())["rows"], "quiet", "terminal")[0]
    terminals = [r for r in you_lo if r["split"] == "quiet" and r["kind"] == "terminal"]
    result = {
        "window": {"first": next(iter(games.values()))["date"], "last": list(games.values())[-1]["date"], "games": len(games)},
        "riichis": len(rows), "no_safe_tile": len(none),
        "not_tenpai": {"riichis": len(waiting), "no_safe_tile": sum(r["n_safe"] == 0 for r in waiting),
                       "luckyj_expected": round(expected, 1), "luckyj_rate": round(100 * expected / len(waiting), 1)},
        "groups": dict(groups),
        "most_in_one_game": max(per_game.values()),
        "terminal_leftovers": {"choices": len(terminals), "you_live_first": sum(r["live_cut"] for r in terminals),
                               "you_rate": round(100 * sum(r["live_cut"] for r in terminals) / len(terminals), 1),
                               "luckyj_rate": round(100 * sum(rates[r["turn"]] for r in terminals) / len(terminals), 1)},
        "riichis_with_no_safe_tile": riichis,
    }
    Path(out + ".tmp").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(out + ".tmp", out)
    print(json.dumps({k: v for k, v in result.items() if k != "riichis_with_no_safe_tile"}, ensure_ascii=False))
    for x in riichis:
        cuts = ", ".join(f"T{c['turn']} {c['tile']} ({c['mortal']:.2f}, top {c['mortal_top']} {c['mortal_top_p']:.2f})" for c in x["cuts"])
        print(f"{x['date']} {x['game'][:15]} {x['round']:<10} {x['declarer']:<8} {x['declarer_discard']:>2} you {x['shanten']}-sh "
              f"next {x['your_next_turn']} {x['group']:<6} {cuts}")


if __name__ == "__main__":
    main(*sys.argv[1:6])
