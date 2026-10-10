#!/usr/bin/env python3
"""The figures behind guide chapter 32: where LuckyJ keeps a safe tile and the user throws it.

LuckyJ, not Mortal, is the yardstick: its choices come from its own games through chapter 17's leftover measure
(``mine_early_safe_tiles.py leftovers``). A leftover is a lone tile with no tile of its suit within two ranks; a safe
leftover is one already in an opponent's river. The choice is measured where a non-dealer hand, with nobody in riichi
and no opponent on two calls, holds a safe leftover and a live one of the same kind (guest winds, terminals, middle
tiles), or a guest wind already out and a live lone value honor: which went first. LuckyJ's rate at each of its own
discards is ``fitted_rates`` over its 1,255 games.

- the 14 riichis of chapter 30's window that found the user with no safe tile (``mine_early_safe_tiles.py riichi``):
  the leftover choices the user met before each, with LuckyJ's rate there, and the not-tenpai rate against LuckyJ's
  at the same declarer discard;
- the user's leftover choices since January, kind by kind, against LuckyJ in the same spots;
- the turns where LuckyJ keeps the safe tile at least 60% of the time and the user threw it, and of those, the turns
  where a later riichi in the hand found that tile safe, with the safe tiles the user still held then;
- the example turns the chapter shows as cards.

usage: mine_no_safe_riichis.py ESR_YOU ESR_LJ LEFTOVERS_LJ OUT.json
"""

from __future__ import annotations

import datetime
import json
import math
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mine_early_safe_tiles as est  # noqa: E402
import tenhou_replay as tr  # noqa: E402
from build_personal_guide import meld_snapshots, safety, site_tile, visible_counter  # noqa: E402
from tenhou_replay import base  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
SINCE = "2026-01-01"
FIRST, LAST = "261008-f937c8f1", "261011-285cf167"  # chapter 30's window
SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}
KEEP = 0.6  # LuckyJ throws the live one first at least this often
REL = ("you", "shimocha", "toimen", "kamicha")
KINDS = (("guest winds, discards 1-2", lambda c: c["kind"] == "honor" and c["turn"] <= 2),
         ("guest winds, discard 3 on", lambda c: c["kind"] == "honor" and c["turn"] >= 3),
         ("terminals", lambda c: c["kind"] == "terminal"), ("middle tiles", lambda c: c["kind"] == "middle"),
         ("value honor vs discarded wind", lambda c: c["kind"] == "wind-vs-value"))
EXAMPLES = (("260924-0e508d5e", "South 2-0", 6), ("260928-5a0260b7", "East 2-0", 4), ("261002-990b6d58", "South 1-0", 6),
            ("261010-165003cb", "South 2-1", 10), ("261010-165003cb", "South 2-1", 11))


def leftover_choices(g: dict) -> list[dict]:
    """Chapter 17's leftover choices of one game (``est._leftover_work``) with the tiles, and the next riichi."""
    out = []
    hero = g["hero_seat"]
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        if game["dealer"] == hero:
            continue
        own_wind, round_wind = tr.seat_wind(hero, game["kyoku"]), tr.round_wind(game["kyoku"])
        river: set[int] = set()
        own_turn = 0
        declarations = [e for e in game["events"] if e["riichi"] and e["seat"] != hero]
        for e in game["events"]:
            if e["seat"] != hero:
                river.add(base(e["tile"]))
                continue
            own_turn += 1
            if e["called"] is not None or own_turn > est.MAX_TURN:
                continue
            if e["riichi_seats"][hero] is not None and e["riichi_seats"][hero] < e["index"]:
                continue
            opponents = [q for q in range(4) if q != hero]
            riichi = any(e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"] for q in opponents)
            melds = max(len(game["players"][q]["melds"][: e["meld_counts"][q]]) for q in opponents)
            split = "quiet" if not riichi and melds <= 1 else "threat"
            held = est.leftovers_of(e["hand_before"], own_wind, round_wind)
            cut = base(e["tile"])
            choices = [(kind, {b for b in held if est.kind_of(b) == kind and b in river},
                        {b for b in held if est.kind_of(b) == kind and b not in river}) for kind in ("honor", "terminal", "middle")]
            lone = {b for b in {base(t) for t in e["hand_before"]} if b >= 41 and sum(1 for t in e["hand_before"] if base(t) == b) == 1}
            value = {45, 46, 47, own_wind, round_wind}
            choices.append(("wind-vs-value", {b for b in lone if b not in value and b in river}, {b for b in lone if b in value and b not in river}))
            tile = lambda b: next(t for t in e["hand_before"] if base(t) == b)
            for kind, safe, live in choices:
                if not (safe and live and (cut in safe or cut in live)):
                    continue
                later = None
                d = next((x for x in declarations if x["index"] > e["index"]), None)
                nxt = d and next((x for x in game["events"] if x["seat"] == hero and x["index"] > d["index"]), None)
                if nxt is not None:
                    snap = meld_snapshots(game, nxt["index"] - 1)
                    snap[hero] = nxt["melds"]
                    vis = visible_counter(nxt["hand_before"], nxt, game["players"], snap, game["dora_indicators"][:1])
                    labels = {}
                    for b in safe | live:
                        seen = vis.copy()
                        if b == cut:
                            seen[b] -= 1  # kept, the thrown copy would not show
                        labels[site_tile(tile(b))] = safety(tile(b), d["seat"], nxt, game, seen)
                    later = {"declarer": REL[(d["seat"] - hero) % 4], "your_turn": nxt["turn"], "your_cut": site_tile(nxt["tile"]),
                             "labels": labels, "safe_held": sum(1 for t in nxt["hand_before"] if safety(t, d["seat"], nxt, game, vis) in SAFE)}
                out.append({"game": g["uuid"], "date": g["date"], "hand": li, "round": game["round_name"], "turn": own_turn,
                            "split": split, "kind": kind, "cut": site_tile(e["tile"]),
                            "safe": sorted(site_tile(tile(b)) for b in safe), "live": sorted(site_tile(tile(b)) for b in live),
                            "live_cut": cut in live, "riichi_later": later})
    return out


def main(esr_you: str, esr_lj: str, lo_lj: str, out: str) -> None:
    os.chdir(ROOT)
    manifest = sorted(json.loads(MANIFEST.read_text(encoding="utf-8")), key=lambda g: g["start_time"])
    since = datetime.datetime.strptime(SINCE, "%Y-%m-%d").timestamp()
    games = [g for g in manifest if g["start_time"] >= since]
    a = next(k for k, g in enumerate(manifest) if g["uuid"].startswith(FIRST))
    b = next(k for k, g in enumerate(manifest) if g["uuid"].startswith(LAST))
    window = {g["uuid"] for g in manifest[a:b + 1]}

    lj_rows = json.loads(Path(lo_lj).read_text())["rows"]
    rates = {(s, k): est.fitted_rates(lj_rows, s, k)[0] for s in ("quiet", "threat") for k in ("honor", "terminal", "middle", "wind-vs-value")}
    choices = [c for g in games for c in leftover_choices(g)]
    for c in choices:
        c["luckyj_live_first"] = round(rates[(c["split"], c["kind"])][c["turn"]], 3)

    # the 14 riichis
    rows = [r for r in json.loads(Path(esr_you).read_text())["rows"] if r["lj_X"] and r["game"] in window]
    lj = [r for r in json.loads(Path(esr_lj).read_text())["rows"] if r["lj_X"]]
    none = [r for r in rows if r["n_safe"] == 0]
    by_turn = defaultdict(list)
    for r in lj:
        if r["x_shanten"] >= 1:
            by_turn[min(r["r_turn"], 15)].append(r)
    waiting = [r for r in rows if r["x_shanten"] >= 1]
    expected = sum(sum(x["n_safe"] == 0 for x in by_turn[min(r["r_turn"], 15)]) / len(by_turn[min(r["r_turn"], 15)]) for r in waiting)
    before = []
    for r in none:
        g = next(g for g in games if g["uuid"] == r["game"])
        game = tr.replay(tr.load_logs(str(ROOT / g["file"]))[r["li"]])
        decl = next(e for e in game["events"] if e["seat"] == r["R"] and e["riichi"])
        turn = sum(1 for e in game["events"] if e["seat"] == g["hero_seat"] and e["index"] < decl["index"])
        before += [c for c in choices if c["game"] == r["game"] and c["hand"] == r["li"] and c["turn"] <= turn]

    # since January, kind by kind (nobody threatening), against LuckyJ in the same spots
    quiet = [c for c in choices if c["split"] == "quiet"]
    kinds = {}
    for name, sel in KINDS:
        cs = [c for c in quiet if sel(c)]
        p = [c["luckyj_live_first"] for c in cs]
        live = sum(c["live_cut"] for c in cs)
        exp, var = sum(p), sum(q * (1 - q) for q in p)
        kinds[name] = {"choices": len(cs), "you": round(100 * live / len(cs), 1), "luckyj": round(100 * exp / len(cs), 1),
                       "sd": round((live - exp) / math.sqrt(var), 1)}

    keep = [c for c in choices if c["luckyj_live_first"] >= KEEP]
    thrown = [c for c in keep if not c["live_cut"]]
    costly = [c for c in thrown if c["riichi_later"] and c["riichi_later"]["labels"].get(c["cut"]) in SAFE]
    find = lambda g, r, t: next(c for c in choices if c["game"].startswith(g) and c["round"] == r and c["turn"] == t)
    result = {
        "window": {"games": len(window), "riichis": len(rows), "no_safe_tile": len(none),
                   "not_tenpai": {"riichis": len(waiting), "no_safe_tile": sum(r["n_safe"] == 0 for r in waiting),
                                  "luckyj_rate": round(100 * expected / len(waiting), 1)},
                   "most_in_one_game": max(Counter(r["game"] for r in none).values()),
                   "choices_before": before},
        "since_january": {"games": len(games), "choices": len(choices), "kinds": kinds},
        "luckyj_keeps": {"choices": len(keep), "you_threw_safe": len(thrown),
                         "luckyj_would": round(sum(1 - c["luckyj_live_first"] for c in keep), 1),
                         "wind_vs_value": sum(1 for c in thrown if c["kind"] == "wind-vs-value"),
                         "safe_at_a_later_riichi": len(costly),
                         "two_or_fewer_held": sum(1 for c in costly if c["riichi_later"]["safe_held"] <= 2)},
        "examples": [find(*x) for x in EXAMPLES],
    }
    Path(out + ".tmp").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(out + ".tmp", out)
    print(json.dumps({k: v for k, v in result.items() if k != "examples"}, ensure_ascii=False)[:2500])
    for c in result["examples"]:
        print(c["date"], c["game"][:15], c["round"], c["turn"], c["kind"], c["cut"], c["safe"], c["live"], c["luckyj_live_first"], c["riichi_later"])


if __name__ == "__main__":
    main(*sys.argv[1:5])
