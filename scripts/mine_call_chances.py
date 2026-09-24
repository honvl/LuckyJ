#!/usr/bin/env python3
"""Chances to open a closed hand: when LuckyJ calls, and how often the player does.

Every discard the player could chi or pon while the hand is closed and not in riichi is checked:

- from 1-shanten, the call must give a tenpai with a yaku on some wait;
- from 2-shanten, the call must give a 1-shanten that can still reach a tenpai with a yaku.

Recorded per chance: which of the two, the player's turn (discards made + 1), the closed hand's
acceptance (unseen copies that cut a shanten), dora held, whether the called tile is a dora, the
route the open hand takes (yakuhai pon, tanyao, flush, other), from 1-shanten the open tenpai's han
and live tiles, a riichi on the table, whether the player called, and how the hand went. A chance
taken away by another seat's ron or call is skipped.

usage: mine_call_chances.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_call_chances.py report LABEL ROWS.json [ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def row_of(turn: int) -> int:
    """The row of the river the next discard lands in: turns 1-6, 7-12, 13 and later."""
    return 1 if turn <= 6 else 2 if turn <= 12 else 3


def call_options(hand13: list[int], tile: int, from_left: bool) -> list[tuple[str, list[int]]]:
    """(kind, the two hand tiles used) for every pon and chi on ``tile``; chi only off the left seat."""
    from tenhou_replay import base, is_honor, is_red

    b = base(tile)
    opts = []
    same = sorted((x for x in hand13 if base(x) == b), key=is_red)
    if len(same) >= 2:
        opts.append(("p", same[:2]))
    if from_left and not is_honor(tile):
        n, suit = b % 10, b - b % 10
        for a, c in ((n - 2, n - 1), (n - 1, n + 1), (n + 1, n + 2)):
            if 1 <= a <= 9 and 1 <= c <= 9:
                # keep a red five in hand when a plain copy can go into the meld
                xa = sorted((x for x in hand13 if base(x) == suit + a), key=is_red)
                xc = sorted((x for x in hand13 if base(x) == suit + c), key=is_red)
                if xa and xc:
                    opts.append(("c", [xa[0], xc[0]]))
    return opts


def kuikae(kind: str, tile: int, used: list[int]) -> set[int]:
    """Tiles that may not be cut right after the call: the called tile, and for a chi on an end
    of the run, the tile that would extend the run at the other end."""
    from tenhou_replay import base

    b = base(tile)
    bad = {b}
    if kind == "c":
        lo = min(base(x) for x in used + [tile])
        hi = max(base(x) for x in used + [tile])
        if b == lo and hi % 10 < 9:
            bad.add(hi + 1)
        if b == hi and lo % 10 > 1:
            bad.add(lo - 1)
    return bad


def route(kind: str, tile: int, meld_tiles: list[int], rest: list[int], seat: int, kyoku: int) -> str:
    """The yaku the open hand is heading for, read from the meld and the tiles kept."""
    import tenhou_replay as tr
    from tenhou_replay import base

    if kind == "p" and base(tile) in {45, 46, 47, tr.seat_wind(seat, kyoku), tr.round_wind(kyoku)}:
        return "yakuhai pon"
    simple = lambda b: b < 41 and b % 10 not in (1, 9)
    meld = [base(x) for x in meld_tiles]
    tiles = [base(x) for x in rest] + meld
    if all(simple(b) for b in meld) and sum(1 for b in tiles if not simple(b)) <= 1:
        return "tanyao"
    if len({b // 10 for b in tiles if b < 41}) == 1:
        return "flush"
    return "other"


@lru_cache(maxsize=200000)
def yaku_reachable(rest_bases: tuple, meld_bases: tuple, kind: str, seat: int, kyoku: int, dset: frozenset) -> bool:
    """Can this open 1-shanten reach a tenpai with a yaku on some wait in one draw?"""
    import review_win_speed as ws
    import tenhou_replay as tr
    from mine_open_tenpai_push import ron_value

    meld = {"kind": kind, "tiles": list(meld_bases), "called": meld_bases[0]}
    count = {}
    for x in list(rest_bases) + list(meld_bases):
        count[x] = count.get(x, 0) + 1
    for t in tr.TILE_ORDER:
        if count.get(t, 0) >= 4:
            continue
        r11 = list(rest_bases) + [t]
        for d in set(r11):
            r = list(r11)
            r.remove(d)
            if ws.hand_shanten(r, meld["tiles"], False) != 0:
                continue
            if any(ron_value(r, [meld], w, seat, kyoku, dset) for w in tr.waits(r, meld["tiles"], False)):
                return True
    return False


def compute(manifest: str, since: str | None, out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, visible_counter
    from mine_open_tenpai_push import ron_value
    from tenhou_replay import base, is_red

    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    rows = []
    for g in games:
        hero = g["hero_seat"]
        left = (hero + 3) % 4
        for li, log in enumerate(tr.load_logs(g["file"])):
            game = tr.replay(log)
            indicators = game["dora_indicators"][:1]
            dset = frozenset(ws.dora_from_indicator(t) for t in indicators)
            isd = lambda t: base(t) in dset or is_red(t)
            blocks = tr.result_blocks(log[-1])
            won = any(d[0] == hero for _, d in blocks)
            dealt = any(len(d) > 1 and d[1] == hero and d[0] != hero for _, d in blocks)
            net = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero]
            events = game["events"]
            mine_all = [x for x in events if x["seat"] == hero]
            first_tenpai = next((x["turn"] for x in mine_all
                                 if ws.hand_shanten(x["hand_after"], x["meld_tiles"], x["closed"]) == 0), None)
            hand_rows = []
            for i, e in enumerate(events):
                if e["seat"] == hero or i + 1 >= len(events):
                    continue
                mine = [x for x in events[:i] if x["seat"] == hero]
                if not mine:
                    continue
                me = mine[-1]
                if not me["closed"] or me["melds"] or me["riichi_seats"][hero] is not None or me["riichi"]:
                    continue
                hand13 = list(me["hand_after"])
                sh = ws.hand_shanten(hand13)
                if sh not in (1, 2):
                    continue
                t = e["tile"]
                nxt = events[i + 1]
                if nxt["called"] is not None and nxt["seat"] != hero and nxt["called"]["src"] == e["seat"]:
                    continue  # another seat called this tile first
                took = (nxt["seat"] == hero and nxt["called"] is not None and nxt["called"]["src"] == e["seat"]
                        and nxt["called"]["kind"] in ("c", "p", "m"))
                opts = call_options(hand13, t, e["seat"] == left)
                if not opts:
                    continue
                snap = meld_snapshots(game, i)
                best = None
                for kind, used in opts:
                    rest = list(hand13)
                    for x in used:
                        rest.remove(x)
                    mtiles = sorted(used + [t], key=base)
                    bad = kuikae(kind, t, used)
                    for d in {base(x): x for x in rest}.values():
                        if base(d) in bad:
                            continue
                        r10 = list(rest)
                        r10.remove(d)
                        if ws.hand_shanten(r10, mtiles, False) != sh - 1:
                            continue
                        sn = dict(snap)
                        sn[hero] = [mtiles]
                        vis = visible_counter(r10 + [d], e, game["players"], sn, indicators)
                        if sh == 1:
                            waits = tr.waits(r10, mtiles, False)
                            meld = {"kind": kind, "tiles": mtiles, "called": t}
                            hans = [ron_value(r10, [meld], w, hero, game["kyoku"], dset) for w in waits]
                            han = max((h for h in hans if h is not None), default=0)
                            if han <= 0:
                                continue
                            size = sum(max(0, 4 - vis[base(w)]) for w in waits)
                        else:
                            if not yaku_reachable(tuple(sorted(base(x) for x in r10)), tuple(base(x) for x in mtiles),
                                                  kind, hero, game["kyoku"], dset):
                                continue
                            han = 0
                            size = ws.acceptance(r10, mtiles, False, vis)[1]
                        cand = (han, size, kind, route(kind, t, mtiles, r10, hero, game["kyoku"]))
                        best = max(best, cand) if best else cand
                if best is None:
                    continue
                vis_closed = visible_counter(hand13, e, game["players"], snap, indicators)
                acc = ws.acceptance(hand13, [], True, vis_closed)[1]
                riichi_out = any(e["riichi_seats"][q] is not None and e["riichi_seats"][q] <= i for q in range(4) if q != hero)
                hand_rows.append({
                    "game": g["uuid"], "hand": li, "round": game["round_name"], "from": sh, "turn": len(mine) + 1,
                    "took": took, "kind": best[2], "route": best[3], "open_han": best[0], "open_size": best[1],
                    "acc": acc, "dora": sum(1 for x in hand13 if isd(x)), "called_dora": isd(t),
                    "riichi_out": riichi_out, "won": won, "dealt": dealt, "net": net, "first_tenpai": first_tenpai,
                    "riichi_later": game["players"][hero]["riichi_event"] is not None,
                })
            seen = set()
            for r in hand_rows:
                r["first"] = r["from"] not in seen
                seen.add(r["from"])
            rows += hand_rows
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} chances to call")


def acc1_bucket(acc: int) -> str:
    return "under 12 tiles" if acc < 12 else "12-19 tiles" if acc < 20 else "20+ tiles"


def acc2_bucket(acc: int) -> str:
    return "under 24 tiles" if acc < 24 else "24-39 tiles" if acc < 40 else "40+ tiles"


def dora_bucket(d: int) -> str:
    return "no dora" if d == 0 else "1 dora" if d == 1 else "2+ dora"


def report(label: str, files: list[str]) -> None:
    rows, games = [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; games += d["games"]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    mean = lambda xs: sum(xs) / len(xs) if xs else 0
    quiet = [r for r in rows if not r["riichi_out"]]

    def rate(name, sel, pool=quiet):
        c = [r for r in pool if sel(r)]
        print(f"  {name:<46} n {len(c):5d}  called {pct(sum(r['took'] for r in c), len(c))}")

    def outcome(name, sel):
        c = [r for r in quiet if r["first"] and sel(r)]
        for took in (True, False):
            b = [r for r in c if r["took"] == took]
            if not b:
                continue
            tp = [r["first_tenpai"] for r in b if r["first_tenpai"]]
            print(f"  {name:<34} {'called' if took else 'passed':<7} n {len(b):4d}  reached tenpai {pct(len(tp), len(b))}"
                  f" (turn {mean(tp):4.1f})  won {pct(sum(r['won'] for r in b), len(b))}  dealt in {pct(sum(r['dealt'] for r in b), len(b))}"
                  f"  net {mean([r['net'] for r in b]):+6.0f}" + ("" if took else f"  riichi later {pct(sum(r['riichi_later'] for r in b), len(b))}"))

    print(f"== {label}: {games} games; chances to call from a closed hand, no riichi on the table unless stated")
    print("-- from 1-shanten, the call gives a tenpai with a yaku")
    one = lambda r: r["from"] == 1
    rate("all", one)
    for w in (1, 2, 3):
        rate(f"row {w}", lambda r, w=w: one(r) and row_of(r["turn"]) == w)
    for a in ("under 12 tiles", "12-19 tiles", "20+ tiles"):
        rate(f"closed acceptance {a}", lambda r, a=a: one(r) and acc1_bucket(r["acc"]) == a)
        for w in (1, 2, 3):
            rate(f"   row {w}", lambda r, a=a, w=w: one(r) and acc1_bucket(r["acc"]) == a and row_of(r["turn"]) == w)
    for h, sel in (("open tenpai 1 han", lambda h: h == 1), ("open tenpai 2 han", lambda h: h == 2), ("open tenpai 3+ han", lambda h: h >= 3)):
        rate(h, lambda r, sel=sel: one(r) and sel(r["open_han"]))
        for w in (1, 2, 3):
            rate(f"   row {w}", lambda r, sel=sel, w=w: one(r) and sel(r["open_han"]) and row_of(r["turn"]) == w)
    rate("riichi on the table", one, [r for r in rows if r["riichi_out"]])
    print("   first chance in the hand, called or passed:")
    for a in ("under 12 tiles", "12-19 tiles", "20+ tiles"):
        for h, sel in (("1-2 han", lambda h: h <= 2), ("3+ han", lambda h: h >= 3)):
            outcome(f"{a}, {h}", lambda r, a=a, sel=sel: one(r) and acc1_bucket(r["acc"]) == a and sel(r["open_han"]))
    print("-- from 2-shanten, the call gives a 1-shanten that can still reach a yaku")
    two = lambda r: r["from"] == 2
    rate("all", two)
    for w in (1, 2, 3):
        rate(f"row {w}", lambda r, w=w: two(r) and row_of(r["turn"]) == w)
    for rt in ("yakuhai pon", "tanyao", "flush", "other"):
        rate(rt, lambda r, rt=rt: two(r) and r["route"] == rt)
        for w in (1, 2, 3):
            rate(f"   row {w}", lambda r, rt=rt, w=w: two(r) and r["route"] == rt and row_of(r["turn"]) == w)
    early_tanyao = lambda r: two(r) and r["route"] == "tanyao" and row_of(r["turn"]) <= 2
    print("   tanyao in rows 1-2:")
    for d in ("no dora", "1 dora", "2+ dora"):
        rate(d, lambda r, d=d: early_tanyao(r) and dora_bucket(r["dora"]) == d)
        for a in ("under 24 tiles", "24-39 tiles", "40+ tiles"):
            rate(f"   closed acceptance {a}", lambda r, d=d, a=a: early_tanyao(r) and dora_bucket(r["dora"]) == d and acc2_bucket(r["acc"]) == a)
    print("   first chance in the hand, rows 1-2, called or passed:")
    for rt in ("yakuhai pon", "tanyao", "other"):
        for d in ("no dora", "1 dora", "2+ dora"):
            outcome(f"{rt}, {d}", lambda r, rt=rt, d=d: two(r) and row_of(r["turn"]) <= 2 and r["route"] == rt and dora_bucket(r["dora"]) == d)


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        report(sys.argv[2], sys.argv[3:])
