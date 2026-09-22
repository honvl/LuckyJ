#!/usr/bin/env python3
"""When a player starts tanyao and a flush, read from the deal.

Every hand is sorted by its 13-tile deal:

- terminals and honors in the deal (tiles, so a pair of 9s counts twice), for tanyao;
- the most tiles that fit one suit plus honors, and whether the deal holds a pair of the
  player's value honors (dragons, seat wind, round wind), for a flush.

Then the hand is followed turn by turn. It counts as a tanyao hand by turn T when, after the
player's T-th discard, the hand and its melds hold no terminal or honor; as a flush hand when
every number tile left is in one suit. The rates by turn T only count hands that lasted T
discards, so hands ended early by someone else's win do not count as plans dropped.

usage: mine_shape_plans.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_shape_plans.py report LABEL ROWS.json [ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

TURNS = (3, 6, 9)
FLUSH = {"混一色", "清一色"}


def yaochuu(tiles: list) -> int:
    """Terminals and honors among the tiles."""
    from tenhou_replay import base, is_honor

    return sum(1 for t in tiles if is_honor(t) or base(t) % 10 in (1, 9))


def flush_fit(tiles: list) -> int:
    """The most tiles that fit one suit plus honors."""
    from tenhou_replay import base, is_honor

    honors = sum(1 for t in tiles if is_honor(t))
    suits = [sum(1 for t in tiles if not is_honor(t) and base(t) // 10 == s) for s in (1, 2, 3)]
    return honors + max(suits)


def main_suit(tiles: list) -> int:
    """The suit with the most tiles (1 man, 2 pin, 3 sou); ties go to the lower suit."""
    from tenhou_replay import base, is_honor

    counts = [sum(1 for t in tiles if not is_honor(t) and base(t) // 10 == s) for s in (1, 2, 3)]
    return 1 + max(range(3), key=lambda i: (counts[i], -i))


def is_flush(tiles: list) -> bool:
    from tenhou_replay import base, is_honor

    return len({base(t) // 10 for t in tiles if not is_honor(t)}) <= 1


def compute(manifest: str, since: str | None, out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from tenhou_replay import base, is_honor, is_red

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
            deal = list(p["haipai"])
            dset = frozenset(ws.dora_from_indicator(t) for t in game["dora_indicators"][:1])
            value_honors = tr.yakuhai_for(hero, game["kyoku"])
            honor_counts = {}
            for t in deal:
                if is_honor(t):
                    honor_counts[base(t)] = honor_counts.get(base(t), 0) + 1
            evs = [e for e in game["events"] if e["seat"] == hero]
            suit = main_suit(deal)
            by_turn = {}
            for T in TURNS:
                e = next((x for x in evs if x["turn"] == T), None)
                if e is None:
                    continue
                tiles = list(e["hand_after"]) + list(e["meld_tiles"])
                by_turn[T] = {"tanyao": yaochuu(tiles) == 0, "flush": is_flush(tiles), "y_left": yaochuu(tiles),
                              "off_left": sum(1 for t in tiles if not is_honor(t) and base(t) // 10 != suit)}
            first3 = [e["tile"] for e in evs if e["turn"] <= 3]
            first_call = next((e for e in evs if e["called"] is not None and e["called"]["kind"] != "a"), None)
            call_simple = call_flush = None
            if first_call is not None:
                meld = p["melds"][len(first_call["melds"]) - 1]
                call_simple = yaochuu(meld["tiles"]) == 0
                call_flush = is_flush(list(first_call["hand_after"]) + list(first_call["meld_tiles"]))
            blocks = tr.result_blocks(log[-1])
            win = next((d for _, d in blocks if d[0] == hero), None)
            loser = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            delta = tr.result_deltas(log[-1])[hero]
            yaku = set(ws.yaku_names(win)) if win else set()
            rows.append(dict(
                hd=sum(1 for t in deal if base(t) in dset or is_red(t)),
                yaochuu=yaochuu(deal), fit=flush_fit(deal), off_deal=sum(1 for t in deal if not is_honor(t) and base(t) // 10 != suit),
                first3_y=yaochuu(first3) if len(first3) == 3 else None,
                first3_off=sum(1 for t in first3 if not is_honor(t) and base(t) // 10 != suit) if len(first3) == 3 else None,
                value_pair=any(n >= 2 for b, n in honor_counts.items() if b in value_honors),
                honors=sum(honor_counts.values()),
                by_turn=by_turn, called=first_call is not None, call_turn=first_call["turn"] if first_call else None,
                call_simple=call_simple, call_flush=call_flush,
                won=win is not None, tanyao_win="断幺九" in yaku, flush_win=bool(FLUSH & yaku),
                value=delta - 1000 * tr.riichi_sticks_paid(log)[hero] if win else 0,
                cost=-delta if hero in loser else 0))
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} hands")


def report(label: str, files: list[str]) -> None:
    rows, games = [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; games += d["games"]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    mean = lambda xs: sum(xs) / len(xs) if xs else 0

    def reached(rs, key, T):
        lasted = [r for r in rs if str(T) in r["by_turn"]]
        return pct(sum(r["by_turn"][str(T)][key] for r in lasted), len(lasted))

    def line(name, rs, key, win_key):
        wins = [r for r in rs if r["won"]]
        plan_wins = [r for r in rs if r[win_key]]
        print(f"   {name:<22} n {len(rs):5d} ({pct(len(rs), len(rows))})  by turn 3 {reached(rs, key, 3)}  turn 6 {reached(rs, key, 6)}"
              f"  turn 9 {reached(rs, key, 9)}  won with it {pct(len(plan_wins), len(rs))} (value {mean([r['value'] for r in plan_wins]):5.0f})"
              f"  won {pct(len(wins), len(rs))}  net per hand {mean([r['value'] - r['cost'] for r in rs]):6.0f}")

    print(f"== {label}: {games} games, {len(rows)} hands")
    for dn, ds in (("all hands", lambda r: True), ("no dora in the deal", lambda r: r["hd"] == 0),
                   ("dora in the deal", lambda r: r["hd"] >= 1)):
        rs = [r for r in rows if ds(r)]
        print(f"-- {dn}: {len(rs)} hands; tanyao wins per 100 hands {100 * sum(r['tanyao_win'] for r in rs) / len(rs):.2f}, "
              f"flush wins per 100 hands {100 * sum(r['flush_win'] for r in rs) / len(rs):.2f}")
    print("-- tanyao, by terminals and honors in the deal: share of hands with none left by turn 3, 6, 9")
    for dn, ds in (("all hands", lambda r: True), ("no dora", lambda r: r["hd"] == 0)):
        print(f"   [{dn}]")
        for name, lo, hi in (("0-2 in the deal", 0, 2), ("3", 3, 3), ("4", 4, 4), ("5", 5, 5), ("6-7", 6, 7), ("8 or more", 8, 99)):
            line(name, [r for r in rows if ds(r) and lo <= r["yaochuu"] <= hi], "tanyao", "tanyao_win")
    print("-- tanyao pace: terminals and honors among the first three discards, and left in hand after turns 3 and 6")
    for name, lo, hi in (("0-2 in the deal", 0, 2), ("3", 3, 3), ("4", 4, 4), ("5", 5, 5), ("6-7", 6, 7)):
        rs = [r for r in rows if lo <= r["yaochuu"] <= hi]
        f3 = [r["first3_y"] for r in rs if r["first3_y"] is not None]
        left = {T: [r["by_turn"][str(T)]["y_left"] for r in rs if str(T) in r["by_turn"]] for T in (3, 6)}
        print(f"   {name:<22} first three discards: {mean(f3):4.2f} terminals/honors  left after turn 3 {mean(left[3]):4.2f}"
              f"  after turn 6 {mean(left[6]):4.2f}")
    print("-- flush, by tiles fitting one suit plus honors in the deal: share of hands in one suit by turn 3, 6, 9")
    for dn, ds in (("all hands", lambda r: True), ("no dora", lambda r: r["hd"] == 0)):
        print(f"   [{dn}]")
        for name, lo, hi in (("7 or fewer", 0, 7), ("8", 8, 8), ("9", 9, 9), ("10", 10, 10), ("11 or more", 11, 13)):
            line(name, [r for r in rows if ds(r) and lo <= r["fit"] <= hi], "flush", "flush_win")
    print("   [flush pace: off-suit number tiles in the deal, among the first three discards, left after turns 3 and 6]")
    for name, lo, hi in (("8", 8, 8), ("9", 9, 9), ("10", 10, 10), ("11 or more", 11, 13)):
        rs = [r for r in rows if lo <= r["fit"] <= hi]
        f3 = [r["first3_off"] for r in rs if r["first3_off"] is not None]
        left = {T: [r["by_turn"][str(T)]["off_left"] for r in rs if str(T) in r["by_turn"]] for T in (3, 6)}
        print(f"   {name:<22} off-suit in the deal {mean([r['off_deal'] for r in rs]):4.2f}  among the first three discards {mean(f3):4.2f}"
              f"  left after turn 3 {mean(left[3]):4.2f}  after turn 6 {mean(left[6]):4.2f}")
    print("   [8 or more fitting, by a value-honor pair in the deal]")
    for pair in (True, False):
        for name, lo, hi in (("8", 8, 8), ("9", 9, 9), ("10+", 10, 13)):
            label = f"{'value pair' if pair else 'no value pair'}, {name}"
            line(label, [r for r in rows if r["value_pair"] == pair and lo <= r["fit"] <= hi], "flush", "flush_win")
    print("-- first calls")
    called = [r for r in rows if r["called"]]
    for name, sel in (("0-3 terminals/honors", lambda r: r["yaochuu"] <= 3), ("4-5", lambda r: 4 <= r["yaochuu"] <= 5),
                      ("6 or more", lambda r: r["yaochuu"] >= 6)):
        rs = [r for r in rows if sel(r)]
        c = [r for r in rs if r["called"]]
        print(f"   deal with {name:<22} opened {pct(len(c), len(rs))}  first call all simples {pct(sum(r['call_simple'] for r in c), len(c))}"
              f"  first call on turn {mean([r['call_turn'] for r in c]):4.1f}  tanyao wins among opened {pct(sum(r['tanyao_win'] for r in c), len(c))}")
    print(f"   all first calls: n {len(called)}  already one suit after the call {pct(sum(r['call_flush'] for r in called), len(called))}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        report(sys.argv[2], sys.argv[3:])
