#!/usr/bin/env python3
"""Tenpai against a riichi when every tile that keeps the tenpai is unsafe: push or fold.

For each hand, the first discard where the player is not in riichi, someone else has declared,
the player holds tenpai (some discard keeps it), and every tenpai-keeping tile is unsafe against
at least one riichi player (safe = genbutsu including tiles passed after the declaration, dead
honors, suji, nakasuji, an honor with two other copies showing). Open and closed hands both
count; a closed hand that keeps tenpai may declare riichi (a chase) or stay dama.

Recorded: open or closed, the turn, how many turns ago the riichi came, the best tenpai the
player could keep (most live tiles, then most han; han on ron with riichi counted for a closed
hand), whether the player kept tenpai, the danger of the tile cut, and how the hand ended.

usage: mine_tenpai_push.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_tenpai_push.py report LABEL ROWS.json [ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}


def value_bucket(han: int) -> str:
    return "no yaku" if han <= 0 else "1-2 han" if han <= 2 else "3-4 han" if han <= 4 else "5+ han"


def live_bucket(live: int) -> str:
    return "3 or fewer" if live <= 3 else "4-7" if live <= 7 else "8+"


def turn_bucket(turn: int) -> str:
    return "turn 9 or earlier" if turn <= 9 else "turn 10-12" if turn <= 12 else "turn 13+"


def compute(manifest: str, since: str | None, out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import DANGER, meld_snapshots, safety, visible_counter
    from mine_open_tenpai_push import ron_value
    from tenhou_replay import base

    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    rows = []
    for g in games:
        hero = g["hero_seat"]
        for log in tr.load_logs(g["file"]):
            game = tr.replay(log)
            p = game["players"][hero]
            indicators = game["dora_indicators"][:1]
            dset = frozenset(ws.dora_from_indicator(t) for t in indicators)
            blocks = tr.result_blocks(log[-1])
            riichi_turn = {q: next((x["turn"] for x in game["events"] if x["seat"] == q and x["riichi"]), None) for q in range(4)}
            for e in game["events"]:
                if e["seat"] != hero or e["riichi_seats"][hero] is not None:
                    continue
                reached = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
                if not reached:
                    continue
                keep = {}
                for t in {base(x): x for x in e["hand_before"]}.values():
                    rest = list(e["hand_before"])
                    rest.remove(t)
                    if ws.hand_shanten(rest, e["meld_tiles"], e["closed"]) == 0:
                        keep[base(t)] = (t, rest)
                if not keep:
                    continue
                snap = meld_snapshots(game, e["index"] - 1)
                snap[hero] = e["melds"]
                visible = visible_counter(e["hand_before"], e, game["players"], snap, indicators)

                def labels(t):
                    seen = visible.copy()
                    seen[base(t)] -= 1
                    return [safety(t, q, e, game, seen) for q in reached]

                if any(all(lab in SAFE for lab in labels(t)) for t, _ in keep.values()):
                    continue  # a safe tile keeps the tenpai: no dilemma
                my_melds = p["melds"][: len(e["melds"])]
                best = (-1, -1)
                for t, rest in keep.values():
                    waits = tr.waits(rest, e["meld_tiles"], e["closed"])
                    live = sum(max(0, 4 - visible[base(w)]) for w in waits)
                    hans = [ron_value(rest, my_melds, w, hero, game["kyoku"], dset, riichi=e["closed"]) for w in waits]
                    han = max((h for h in hans if h is not None), default=0)
                    best = max(best, (live, han))
                kept = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) == 0
                start = log[1]
                rows.append({
                    "game": g["uuid"], "round": game["round_name"], "closed": e["closed"], "turn": e["turn"],
                    "riichi_ago": e["turn"] - min(riichi_turn[q] or e["turn"] for q in reached), "riichis": len(reached),
                    "live": best[0], "han": best[1], "pushed": kept, "chased": bool(e["riichi"]),
                    "danger": max(DANGER[lab] for lab in labels(e["tile"])),
                    "won": any(d[0] == hero for _, d in blocks),
                    "dealt": any(d[1] == hero and d[0] != hero for _, d in blocks),
                    "delta": tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero],
                    "place": sorted(range(4), key=lambda s: (-start[s], s)).index(hero) + 1,
                    "south4": log[0][0] >= 7,
                })
                break
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} tenpai push-or-fold hands")


def report(label: str, files: list[str]) -> None:
    rows, games = [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; games += d["games"]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    mean = lambda xs: sum(xs) / len(xs) if xs else 0
    print(f"== {label}: {games} games; tenpai against a riichi where every tenpai-keeping tile is unsafe: {len(rows)} hands")

    def cell(name, sel):
        c = [r for r in rows if sel(r)]
        if not c:
            return
        pu = [r for r in c if r["pushed"]]
        fo = [r for r in c if not r["pushed"]]
        wins = [r["delta"] for r in pu if r["won"]]
        losses = [r["delta"] for r in pu if r["dealt"]]
        print(f"  {name:<34} n {len(c):5d}  push {pct(len(pu), len(c))}  pushed: won {pct(len(wins), len(pu))} (avg {mean(wins):6.0f})"
              f"  dealt in {pct(len(losses), len(pu))} (avg {mean(losses):7.0f})  net {mean([r['delta'] for r in pu]):6.0f}"
              f"  | folded: n {len(fo):4d} net {mean([r['delta'] for r in fo]):6.0f}")

    cell("all", lambda r: True)
    cell("open hands", lambda r: not r["closed"])
    cell("closed hands", lambda r: r["closed"])
    for v in ("no yaku", "1-2 han", "3-4 han", "5+ han"):
        cell(v, lambda r, v=v: value_bucket(r["han"]) == v)
    for w in ("3 or fewer", "4-7", "8+"):
        cell(f"live tiles {w}", lambda r, w=w: live_bucket(r["live"]) == w)
    for t in ("turn 9 or earlier", "turn 10-12", "turn 13+"):
        cell(t, lambda r, t=t: turn_bucket(r["turn"]) == t)
    print("  -- value and wait")
    for v in ("1-2 han", "3-4 han", "5+ han"):
        for w in ("3 or fewer", "4-7", "8+"):
            cell(f"{v}, {w} live", lambda r, v=v, w=w: value_bucket(r["han"]) == v and live_bucket(r["live"]) == w)
    print("  -- value and turn")
    for v in ("1-2 han", "3+ han"):
        for t in ("turn 9 or earlier", "turn 10-12", "turn 13+"):
            vs = (lambda r: 1 <= r["han"] <= 2) if v == "1-2 han" else (lambda r: r["han"] >= 3)
            cell(f"{v}, {t}", lambda r, vs=vs, t=t: vs(r) and turn_bucket(r["turn"]) == t)
    nar = [r for r in rows if r["pushed"] and r["live"] <= 3]
    print(f"  -- pushes on 3 or fewer live tiles: n {len(nar)}  live tiles {mean([r['live'] for r in nar]):.2f} on average"
          f"  turn {mean([r['turn'] for r in nar]):.1f}  han {mean([r['han'] for r in nar]):.1f}"
          f"  won {pct(sum(r['won'] for r in nar), len(nar))}  dealt in {pct(sum(r['dealt'] for r in nar), len(nar))}")
    print("  -- the tile pushed")
    for d, name in ((2, "live honor or terminal"), (3, "live 2-3-7-8 or half suji"), (4, "live 4-5-6")):
        c = [r for r in rows if r["pushed"] and r["danger"] == d]
        print(f"  {name:<34} n {len(c):5d}  dealt in {pct(sum(r['dealt'] for r in c), len(c))}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        report(sys.argv[2], sys.argv[3:])
