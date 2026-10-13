#!/usr/bin/env python3
"""Guide chapter 39: are the user's pushes against a riichi worse than a human's, and do chasers or callers explain it?

Chapter 38 measured the user's pushes against LuckyJ's. This sets them against the human players at both tables:
the other three seats of the user's Jade games and of LuckyJ's 1,255 Tenhou games, through the same push-or-fold
spots (``mine_thin_pushes.game_rows`` run for each seat). It also asks the user's two questions about the tables:

- chasing: in every hand where an opponent declared first, how often another opponent declared after, and who won;
  and the push spots that already faced two riichis;
- open hands: how often a caller sat at the table at a push spot, and after a push, how often an open hand won, how
  often the push dealt into one, and the push's results with and without a caller;
- the riichis' waits themselves: for every discard of a live tile against a lone riichi, by any player, how often it
  was one of the riichi's winning tiles (from the declarer's real hand), by the tile's kind.

usage: mine_push_company.py compute YOUR_MANIFEST.json OUT_DIR
       mine_push_company.py report THIN_YOU THIN_LJ OUT_DIR OUT.json
  THIN_*: ``mine_thin_pushes.py compute`` rows for the user's games since January and LuckyJ's 1,255.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import mine_thin_pushes as mt  # noqa: E402

LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
LIVE = ("live honor", "live terminal", "half suji", "live 2-3-7-8", "live 4-5-6")
WINNERS = ("you", "the riichi", "a later riichi", "an open hand", "a closed hand without riichi", "draw")


def other_seats(g: dict) -> list[dict]:
    return [r for s in range(4) if s != g["hero_seat"] for r in mt.game_rows(dict(g, hero_seat=s))]


def table_hands(g: dict) -> list[dict]:
    """Every hand where an opponent of the user (or of LuckyJ) declared first: later riichis and the winners."""
    import tenhou_replay as tr

    out, hero = [], g["hero_seat"]
    for log in tr.load_logs(str(ROOT / g["file"])):
        game = tr.replay(log)
        riichis = [e["seat"] for e in game["events"] if e["riichi"]]
        if not riichis or riichis[0] == hero:
            continue
        winners = [d[0] for _, d in tr.result_blocks(log[-1])]
        chasers = [s for s in riichis[1:] if s != hero]
        out.append({"chased": bool(chasers), "first_won": riichis[0] in winners,
                    "chaser_won": any(w in chasers for w in winners), "hero_chased": hero in riichis[1:]})
    return out


def waits_of(g: dict) -> dict:
    """For every discard of a live tile against a lone riichi: is it one of that riichi's winning tiles? By kind and seat."""
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, safety, visible_counter
    from tenhou_replay import base

    hero = g["hero_seat"]
    out = defaultdict(lambda: [0, 0])
    for log in tr.load_logs(str(ROOT / g["file"])):
        game = tr.replay(log)
        events = game["events"]
        indicators = game["dora_indicators"][:1]
        waits = {e["seat"]: {base(w) for w in tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])}
                 for e in events if e["riichi"]}
        for e in events:
            s = e["seat"]
            reached = [q for q in range(4) if q != s and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            if len(reached) != 1 or e["riichi_seats"][s] is not None or e.get("tile") is None or not waits.get(reached[0]):
                continue
            q = reached[0]
            snap = meld_snapshots(game, e["index"] - 1)
            snap[s] = e["melds"]
            seen = visible_counter(e["hand_before"], e, game["players"], snap, indicators)
            seen[base(e["tile"])] -= 1
            label = safety(e["tile"], q, e, game, seen)
            if label in LIVE:
                cell = out[f"{'hero' if s == hero else 'others'}|{label}"]
                cell[0] += 1
                cell[1] += base(e["tile"]) in waits[q]
    return dict(out)


def compute(your_manifest: str, out_dir: str) -> None:
    os.chdir(ROOT)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    you = json.load(open(your_manifest))
    lj = json.loads(LJ_MANIFEST.read_text(encoding="utf-8"))
    tokujou = [g for g in lj if g["mode"] == "tenhou-tokujou"]
    with Pool(12) as pool:
        humans = {"jade": [r for c in pool.map(other_seats, you, chunksize=2) for r in c],
                  "tenhou": [r for c in pool.map(other_seats, lj, chunksize=4) for r in c]}
        tables = {"you": [h for c in pool.map(table_hands, you, chunksize=2) for h in c],
                  "luckyj": [h for c in pool.map(table_hands, tokujou, chunksize=4) for h in c]}
        waits = {}
        for name, games in (("you", you), ("luckyj", tokujou)):
            total = defaultdict(lambda: [0, 0])
            for d in pool.map(waits_of, games, chunksize=4):
                for k, (n, w) in d.items():
                    total[k][0] += n
                    total[k][1] += w
            waits[name] = dict(total)
    (out / "humans.json").write_text(json.dumps(humans))
    (out / "tables.json").write_text(json.dumps(tables))
    (out / "waits.json").write_text(json.dumps(waits))
    print(f"wrote {out}: {len(humans['jade'])} and {len(humans['tenhou'])} human push-or-fold spots")


def pct(k: float, n: int, digits: int = 1) -> float | None:
    return round(100 * k / n, digits) if n else None


def on_push(r: dict) -> bool:
    return bool(r["deal"] and r["deal"]["on_decision"])


def group(rows: list[dict]) -> dict:
    pushes = [r for r in rows if r["pushed"]]
    thin = [r for r in pushes if r["live"] <= 3]
    kinds = {k: [sum(on_push(r) for r in pushes if mt.kind(r) == k), sum(1 for r in pushes if mt.kind(r) == k)] for k in LIVE}
    winners = {}
    for name, s in (("pushes", pushes), ("folds", [r for r in rows if not r["pushed"]])):
        c = Counter(w for r in s for w in (r["winners"] or ["draw"]))
        winners[name] = {"hands": len(s), **{w: pct(c[w], len(s)) for w in WINNERS}}
    callers = {}
    for name, keep in (("no caller", lambda r: r["open_opponents"] == 0), ("a caller", lambda r: r["open_opponents"] > 0)):
        s = [r for r in pushes if keep(r)]
        callers[name] = {"pushes": len(s), "won": pct(sum(r["won"] for r in s), len(s)), "dealt": pct(sum(r["dealt"] for r in s), len(s)),
                         "on_the_push": [sum(on_push(r) for r in s), pct(sum(on_push(r) for r in s), len(s))],
                         "into_an_open_hand": pct(sum(bool(r["deal"] and r["deal"].get("into_open_hand")) for r in s), len(s)),
                         "an_open_hand_won": pct(sum("an open hand" in r["winners"] for r in s), len(s))}
    return {"spots": len(rows), "pushed": pct(len(pushes), len(rows)), "with_a_caller": pct(sum(r["open_opponents"] > 0 for r in rows), len(rows)),
            "two_riichis": pct(sum(r["riichis"] >= 2 for r in pushes), len(pushes)),
            "on_the_push": [sum(on_push(r) for r in pushes), len(pushes), pct(sum(on_push(r) for r in pushes), len(pushes))],
            "kinds": {k: v + [pct(v[0], v[1])] for k, v in kinds.items()},
            "thin_wins": [sum(r["won"] for r in thin), len(thin), pct(sum(r["won"] for r in thin), len(thin))],
            "won": pct(sum(r["won"] for r in pushes), len(pushes)), "dealt": pct(sum(r["dealt"] for r in pushes), len(pushes)),
            "later_deal_ins": pct(sum(bool(r["deal"] and not r["deal"]["on_decision"]) for r in pushes), len(pushes)),
            "winners": winners, "callers": callers}


def report(thin_you: str, thin_lj: str, out_dir: str, out: str) -> None:
    d = Path(out_dir)
    humans = json.loads((d / "humans.json").read_text())
    tables = json.loads((d / "tables.json").read_text())
    waits = json.loads((d / "waits.json").read_text())
    you, lj = json.load(open(thin_you))["rows"], json.load(open(thin_lj))["rows"]
    data = {"groups": {"you": group(you), "jade_players": group(humans["jade"]), "tokujou_humans": group(humans["tenhou"]),
                       "luckyj": group(lj)}}
    data["chasing"] = {}
    for name, hs in tables.items():
        n = len(hs)
        data["chasing"][name] = {"hands": n, "chased": pct(sum(h["chased"] for h in hs), n), "first_won": pct(sum(h["first_won"] for h in hs), n),
                                 "chaser_won": pct(sum(h["chaser_won"] for h in hs), n)}
    data["waits"] = {}
    for name, cells in waits.items():
        data["waits"][name] = {f"{who}|{k}": cells.get(f"{who}|{k}", [0, 0]) + [pct(cells.get(f"{who}|{k}", [0, 0])[1], cells.get(f"{who}|{k}", [0, 0])[0])]
                               for who in ("hero", "others") for k in LIVE}
    Path(out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(*sys.argv[2:4])
    else:
        report(*sys.argv[2:6])
