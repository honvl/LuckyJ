#!/usr/bin/env python3
"""Cutting live tiles against open hands: which tells mark a tenpai caller, and who reads them.

Every discard made while nobody is in riichi and at least one opponent has an open meld is
checked against the full game record:

- the danger of the cut tile against the most-called opponent(s), with the guide's safety labels;
- whether the player held a tile of danger 1 or less (a safe tile) at that moment;
- the caller's visible tells: the latest call came on turn 9 or later, a second call, the last two
  discards since the call were both tsumogiri, and (weaker) three cuts from hand since the call, a
  3-7 cut from hand as the latest discard, a meld with dora in it;
- the truth the player could not see: was a caller tenpai, and was the cut tile on their wait;
- reads the safety labels leave out: the tile went by after every caller's last discard (they cannot
  ron it until they discard again), every sequence wait on it needs a tile whose four copies are
  visible (no chance), it shares a suit with a caller's meld, it is a dora or within two of one.

The other three seats' cuts are recorded too (danger, dora, deal-in only), so a player's hit rate
can be read against the people at the same tables.

usage: mine_caller_tells.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_caller_tells.py report LABEL ROWS.json [ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TELLS = ("late_call", "two_calls", "tsumogiri2")
WEAK_TELLS = ("ted3", "inside_last", "dora_meld")


def caller_tells(caller_events: list, calls: int, turn_limit: int = 9) -> dict:
    """The visible tells of one caller, from their own discards so far (each event is one discard)."""
    from tenhou_replay import base, is_honor

    called = [x for x in caller_events if x["called"] is not None]
    if not called:
        return dict.fromkeys(TELLS + WEAK_TELLS[:2], False)
    last_call = called[-1]
    after = [x for x in caller_events if x["index"] > last_call["index"]]
    latest = caller_events[-1]
    return {
        "late_call": last_call["turn"] >= turn_limit,
        "two_calls": calls >= 2,
        "tsumogiri2": len(after) >= 2 and after[-1]["tsumogiri"] and after[-2]["tsumogiri"],
        "ted3": sum(1 for x in after if not x["tsumogiri"]) >= 3,
        "inside_last": not latest["tsumogiri"] and not is_honor(latest["tile"]) and 3 <= base(latest["tile"]) % 10 <= 7,
    }


def no_chance(b: int, visible) -> bool:
    """Every two-tile sequence shape that waits on number tile b needs a tile with four copies visible."""
    n = b % 10
    shapes = []
    if n + 2 <= 9:
        shapes.append((b + 1, b + 2))
    if n - 2 >= 1:
        shapes.append((b - 2, b - 1))
    if 2 <= n <= 8:
        shapes.append((b - 1, b + 1))
    return all(any(visible[x] >= 4 for x in pair) for pair in shapes)


def compute(manifest: str, since: str | None, out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import DANGER, meld_snapshots, safety, visible_counter
    from tenhou_replay import base, is_honor, is_red

    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    rows, others = [], []
    for g in games:
        hero = g["hero_seat"]
        for log in tr.load_logs(g["file"]):
            game = tr.replay(log)
            players = game["players"]
            indicators = game["dora_indicators"][:1]
            dset = frozenset(ws.dora_from_indicator(t) for t in indicators)
            isd = lambda t: base(t) in dset or is_red(t)
            blocks = tr.result_blocks(log[-1])
            loser = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            last = len(game["events"]) - 1
            seat_events = {q: [] for q in range(4)}
            last_discard = {}
            for e in game["events"]:
                s = e["seat"]
                if not any(v is not None for v in e["riichi_seats"].values()):
                    melds = {q: [m for m in players[q]["melds"][: e["meld_counts"][q]] if m["kind"] != "a"]
                             for q in range(4) if q != s}
                    mx = max(len(v) for v in melds.values())
                    if mx and all(seat_events[q] for q, v in melds.items() if v):
                        threats = [q for q, v in melds.items() if len(v) == mx]
                        snap = meld_snapshots(game, e["index"] - 1)
                        snap[s] = e["melds"]
                        visible = visible_counter(e["hand_before"], e, players, snap, indicators)

                        def danger(t):
                            seen = visible.copy()
                            seen[base(t)] -= 1
                            return max(DANGER[safety(t, q, e, game, seen)] for q in threats)

                        d = danger(e["tile"])
                        into = int(e["index"] == last and s in loser and loser[s] in threats)
                        dora = sum(1 for t in list(e["hand_before"]) + list(e["meld_tiles"]) if isd(t))
                        if s != hero:
                            others.append([dora, d, into])
                        else:
                            tells = dict.fromkeys(TELLS + WEAK_TELLS, False)
                            tenpai = on_wait = False
                            for q in threats:
                                for k, v in caller_tells(seat_events[q], mx).items():
                                    tells[k] |= v
                                tells["dora_meld"] |= any(isd(t) for m in melds[q] for t in m["tiles"])
                                qe = seat_events[q][-1]
                                if ws.hand_shanten(qe["hand_after"], qe["meld_tiles"], qe["closed"]) == 0:
                                    tenpai = True
                                    waits = {base(w) for w in tr.waits(qe["hand_after"], qe["meld_tiles"], qe["closed"])}
                                    on_wait |= base(e["tile"]) in waits
                            held_safe = min(danger(t) for t in {base(x): x for x in e["hand_before"]}.values())
                            b = base(e["tile"])
                            number = not is_honor(e["tile"])
                            events = game["events"]
                            reads = {
                                "passed": all(q in last_discard and any(base(x["tile"]) == b for x in events[last_discard[q] + 1: e["index"]]
                                                                        if x["seat"] != q) for q in threats),
                                "no_chance": number and no_chance(b, visible),
                                "in_suit": number and any(not is_honor(t) and base(t) // 10 == b // 10
                                                          for q in threats for m in melds[q] for t in m["tiles"]),
                                "near_dora": number and any(d_ // 10 == b // 10 and abs(d_ - b) <= 2 for d_ in dset if d_ < 40),
                            }
                            rows.append(dict(dora=dora, turn=e["turn"], calls=mx, danger=d, held_safe=held_safe,
                                             sh=min(ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]), 2),
                                             tenpai=tenpai, on_wait=on_wait, into=into, **tells, **reads))
                seat_events[s].append(e)
                last_discard[s] = e["index"]
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows, "others": others}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} discards facing a caller, {len(others)} by the other seats")


def tell_count(r: dict) -> int:
    return sum(bool(r[k]) for k in TELLS)


def report(label: str, files: list[str]) -> None:
    rows, others, games = [], [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; others += d["others"]; games += d["games"]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    per100 = lambda rs: 100 * sum(r["into"] for r in rs) / len(rs) if rs else 0
    print(f"== {label}: {games} games, {len(rows)} discards facing a caller with nobody in riichi")
    print("-- live cuts that dealt in to a caller, per 100 live cuts (danger 2+)")
    for dn, ds in (("no dora in hand", lambda x: x == 0), ("dora in hand", lambda x: x >= 1)):
        mine = [r for r in rows if ds(r["dora"]) and r["danger"] >= 2]
        table = [o for o in others if ds(o[0]) and o[1] >= 2]
        print(f"   {dn:<16} this player {per100(mine):4.2f} (n {len(mine):6d}, live {pct(len(mine), sum(1 for r in rows if ds(r['dora'])))})"
              f"   the other three seats {100 * sum(o[2] for o in table) / max(1, len(table)):4.2f} (n {len(table):6d})")
    print("-- share of cuts that were live, dora in hand, by turn and by the caller's calls")
    dr = [r for r in rows if r["dora"] >= 1]
    for name, sel in (("turn <= 6", lambda r: r["turn"] <= 6), ("turn 7-9", lambda r: 7 <= r["turn"] <= 9),
                      ("turn 10-12", lambda r: 10 <= r["turn"] <= 12), ("turn 13+", lambda r: r["turn"] >= 13),
                      ("one call", lambda r: r["calls"] == 1), ("two calls", lambda r: r["calls"] == 2),
                      ("three or more", lambda r: r["calls"] >= 3)):
        a = [r for r in dr if sel(r)]
        live = [r for r in a if r["danger"] >= 2]
        print(f"   {name:<14} {pct(len(a), len(dr))} of cuts  live {pct(len(live), len(a))}  hits/100 live {per100(live):4.2f}")
    print("-- live cuts with dora in hand, by reads the safety labels leave out: share of live cuts, hits per 100")
    live = [r for r in dr if r["danger"] >= 2]
    for k, name in (("passed", "passed since every caller's last discard"), ("no_chance", "no chance (wall)"),
                    ("in_suit", "same suit as a caller's meld"), ("near_dora", "a dora or within two of one")):
        a = [r for r in live if r.get(k)]; b = [r for r in live if not r.get(k)]
        print(f"   {name:<42} {pct(len(a), len(live))}  hits/100 {per100(a):4.2f}   without: {per100(b):4.2f}")
    print("-- how often a caller was tenpai, by the tells showing")
    for k in TELLS + WEAK_TELLS:
        a = [r for r in rows if r[k]]; b = [r for r in rows if not r[k]]
        print(f"   {k:<12} showing {pct(len(a), len(rows))}: tenpai {pct(sum(r['tenpai'] for r in a), len(a))}   not showing: {pct(sum(r['tenpai'] for r in b), len(b))}")
    for n in range(4):
        a = [r for r in rows if tell_count(r) == n]
        print(f"   {n} of the three main tells: {pct(len(a), len(rows))} of discards, caller tenpai {pct(sum(r['tenpai'] for r in a), len(a))}")
    print("-- live cuts: was the caller tenpai, and was the tile on the wait")
    for dn, ds in (("no dora in hand", lambda x: x == 0), ("dora in hand", lambda x: x >= 1)):
        live = [r for r in rows if ds(r["dora"]) and r["danger"] >= 2]
        t = [r for r in live if r["tenpai"]]
        print(f"   {dn:<16} caller tenpai {pct(len(t), len(live))}  tile on the wait {pct(sum(r['on_wait'] for r in live), len(live))}"
              f"  (given tenpai {pct(sum(r['on_wait'] for r in t), len(t))})")
    print("-- live-cut rate while holding a safe tile, by the main tells and shanten after the cut (± one standard error)")
    for dn, ds in (("no dora in hand", lambda x: x == 0), ("dora in hand", lambda x: x >= 1)):
        for sh in (0, 1, 2):
            base_rows = [r for r in rows if ds(r["dora"]) and r["held_safe"] <= 1 and r["sh"] == sh]
            line = f"   {dn:<16} {sh}{'+' if sh == 2 else ''}-shanten"
            for name, sel in (("no tell", lambda r: tell_count(r) == 0), ("1 tell", lambda r: tell_count(r) == 1),
                              ("2+ tells", lambda r: tell_count(r) >= 2), ("all 3", lambda r: tell_count(r) == 3)):
                a = [r for r in base_rows if sel(r)]
                live = [r for r in a if r["danger"] >= 2]
                q = len(live) / len(a) if a else 0
                se = 100 * math.sqrt(q * (1 - q) / len(a)) if a else 0
                line += f" | {name}: live {pct(len(live), len(a))} ±{se:3.1f} (n {len(a):5d}) hits/100 live {per100(live):4.1f}"
            print(line)


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        report(sys.argv[2], sys.argv[3:])
