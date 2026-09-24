#!/usr/bin/env python3
"""An open hand against another open hand: push or fold when keeping the hand needs an unsafe tile.

For each hand, the first discard where the player's hand is open (a chi, pon or open kan), nobody
is in riichi, another player has called, the player can keep tenpai (or, in a second row, keep
1-shanten), and every tile that keeps it is unsafe against at least one caller (safe = genbutsu,
dead honors, suji, nakasuji, an honor with two other copies showing).

Recorded: the player's state (tenpai or 1-shanten), the best tenpai it could keep (most live
tiles, then most han; han on ron, 0 when no wait has a yaku), every tile that keeps the hand with
its danger, the turn, the callers' tells (chapter 8's three: the latest call on the caller's 9th
discard or later, two calls, the last two discards since the call both drawn and thrown), what the
callers show (dora in their melds, a yakuhai triplet), the truth the player could not see (a caller
was tenpai, the cut tile was on a wait), whether the player kept the hand, the danger of the tile
cut, and how the hand ended.

The same pass records, for every hand, how the player's hand was played (open, riichi, closed
without riichi) with its result, and every honor cut by any seat while a caller is open and nobody
is in riichi: yakuhai for a caller or not, other copies showing, and whether it dealt in.

``leak`` reads the per-hand rows of ``mine_dora_hands.py compute`` and splits the deal-ins in hands
the player opened by the player's state and the kind of hand dealt into. ``wins`` reads the same
rows and splits the han of the player's open wins by source.

usage: mine_open_vs_open.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_open_vs_open.py report LABEL ROWS.json [ROWS.json ...]
       mine_open_vs_open.py leak LABEL DORA_ROWS.json [DORA_ROWS.json ...]
       mine_open_vs_open.py wins LABEL DORA_ROWS.json [DORA_ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}


def value_bucket(han: int) -> str:
    return "no yaku" if han <= 0 else "1 han" if han == 1 else "2 han" if han == 2 else "3+ han"


def tells_bucket(n: int) -> str:
    return "no tells" if n == 0 else "1 tell" if n == 1 else "2-3 tells"


def turn_bucket(turn: int) -> str:
    return "turn 9 or earlier" if turn <= 9 else "turn 10-12" if turn <= 12 else "turn 13+"


def is_open(melds) -> bool:
    return any(m["kind"] != "a" for m in melds)


def yakuhai_for(seat: int, kyoku: int) -> set[int]:
    """Honors that score a yaku as a triplet for this seat: the dragons, its wind, the round wind."""
    import tenhou_replay as tr

    return {45, 46, 47, tr.seat_wind(seat, kyoku), tr.round_wind(kyoku)}


def yakuhai_triplet(meld: dict, seat: int, kyoku: int) -> bool:
    """A pon or kan of a dragon, the seat's own wind or the round wind."""
    from tenhou_replay import base

    return meld["kind"] != "c" and base(meld["tiles"][0]) in yakuhai_for(seat, kyoku)


def _without(tiles, t):
    rest = list(tiles)
    rest.remove(t)
    return rest


def compute(manifest: str, since: str | None, out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import DANGER, meld_snapshots, safety, visible_counter
    from mine_caller_tells import TELLS, caller_tells
    from mine_open_tenpai_push import ron_value
    from tenhou_replay import base, is_honor, is_red

    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    rows, hands, honors = [], [], []
    for g in games:
        hero = g["hero_seat"]
        for log in tr.load_logs(g["file"]):
            game = tr.replay(log)
            players = game["players"]
            kyoku = game["kyoku"]
            indicators = game["dora_indicators"][:1]
            dset = frozenset(ws.dora_from_indicator(t) for t in indicators)
            isd = lambda t: base(t) in dset or is_red(t)
            blocks = tr.result_blocks(log[-1])
            winners = {d[0] for _, d in blocks}
            loser = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            delta = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero]
            opened = is_open(players[hero]["melds"])
            riichi = players[hero]["riichi_event"] is not None
            hands.append(["open" if opened else "riichi" if riichi else "closed", int(hero in winners),
                          delta if hero in winners else 0, int(hero in loser), delta])
            start = log[1]
            place = sorted(range(4), key=lambda s: (-start[s], s)).index(hero) + 1
            last = len(game["events"]) - 1
            seat_events = {q: [] for q in range(4)}
            done = set()
            for e in game["events"]:
                s = e["seat"]
                quiet = not any(v is not None for v in e["riichi_seats"].values())
                callers = [q for q in range(4) if q != s and seat_events[q]
                           and is_open(players[q]["melds"][: e["meld_counts"][q]])]
                if quiet and callers and is_honor(e["tile"]):
                    snap = meld_snapshots(game, e["index"] - 1)
                    snap[s] = e["melds"]
                    visible = visible_counter(e["hand_before"], e, players, snap, indicators)
                    b = base(e["tile"])
                    other = visible[b] - sum(1 for x in e["hand_before"] if base(x) == b)
                    genbutsu = all(any(base(x) == b for x in e["rivers"][q]) for q in callers)
                    if not genbutsu and other <= 1:
                        honors.append([int(s == hero), int(any(b in yakuhai_for(q, kyoku) for q in callers)), other,
                                       int(e["index"] == last and s in loser and loser[s] in callers)])
                if s == hero and quiet and callers and e["riichi_seats"][hero] is None:
                    my_melds = players[hero]["melds"][: len(e["melds"])]
                    if is_open(my_melds):
                        sh_best = min(ws.hand_shanten(_without(e["hand_before"], t), e["meld_tiles"], False)
                                      for t in set(e["hand_before"]))
                        state = sh_best if sh_best in (0, 1) else None
                        if state is not None and state not in done:
                            snap = meld_snapshots(game, e["index"] - 1)
                            snap[hero] = e["melds"]
                            visible = visible_counter(e["hand_before"], e, players, snap, indicators)

                            def labels(t):
                                seen = visible.copy()
                                seen[base(t)] -= 1
                                return [safety(t, q, e, game, seen) for q in callers]

                            keep = {}
                            for t in {base(x): x for x in e["hand_before"]}.values():
                                rest = _without(e["hand_before"], t)
                                if ws.hand_shanten(rest, e["meld_tiles"], False) == state:
                                    keep[base(t)] = (t, rest)
                            if not any(all(lab in SAFE for lab in labels(t)) for t, _ in keep.values()):
                                done.add(state)
                                best = (-1, -1)
                                choices = []
                                for t, rest in keep.values():
                                    danger = max(DANGER[lab] for lab in labels(t))
                                    if state == 0:
                                        waits = tr.waits(rest, e["meld_tiles"], False)
                                        size = sum(max(0, 4 - visible[base(w)]) for w in waits)
                                        hans = [ron_value(rest, my_melds, w, hero, kyoku, dset) for w in waits]
                                        han = max((h for h in hans if h is not None), default=0)
                                        best = max(best, (size, han))
                                    else:
                                        size, han = ws.acceptance(rest, e["meld_tiles"], False, visible)[1], 0
                                    choices.append([danger, size, han, base(t) == base(e["tile"])])
                                tells = dict.fromkeys(TELLS, False)
                                count = 0
                                caller_tenpai = on_wait = False
                                dora_melds = 0
                                yakuhai = False
                                for q in callers:
                                    qm = [m for m in players[q]["melds"][: e["meld_counts"][q]] if m["kind"] != "a"]
                                    tq = caller_tells(seat_events[q], len(qm))
                                    count = max(count, sum(bool(tq[k]) for k in TELLS))
                                    for k in TELLS:
                                        tells[k] |= tq[k]
                                    dora_melds = max(dora_melds, sum(1 for m in qm for x in m["tiles"] if isd(x)))
                                    yakuhai |= any(yakuhai_triplet(m, q, kyoku) for m in qm)
                                    qe = seat_events[q][-1]
                                    if ws.hand_shanten(qe["hand_after"], qe["meld_tiles"], qe["closed"]) == 0:
                                        caller_tenpai = True
                                        waits = {base(w) for w in tr.waits(qe["hand_after"], qe["meld_tiles"], qe["closed"])}
                                        on_wait |= base(e["tile"]) in waits
                                rows.append({
                                    "game": g["uuid"], "round": game["round_name"], "state": state, "turn": e["turn"],
                                    "live": best[0], "han": best[1], "choices": choices,
                                    "pushed": ws.hand_shanten(e["hand_after"], e["meld_tiles"], False) == state,
                                    "calls": len(my_melds), "callers": len(callers), "tells": count, **tells,
                                    "dora_melds": dora_melds, "yakuhai_meld": yakuhai,
                                    "caller_tenpai": caller_tenpai, "on_wait": on_wait,
                                    "danger": max(DANGER[lab] for lab in labels(e["tile"])),
                                    "dora": sum(1 for x in list(e["hand_before"]) + list(e["meld_tiles"]) if isd(x)),
                                    "won": hero in winners, "dealt": hero in loser,
                                    "into_caller": hero in loser and loser[hero] in callers,
                                    "delta": delta, "place": place, "south4": log[0][0] >= 7,
                                    "dealer": game["dealer"] == hero,
                                })
                seat_events[s].append(e)
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows, "hands": hands, "honors": honors}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} open-against-open spots, {len(hands)} hands, {len(honors)} honor cuts")


def report(label: str, files: list[str]) -> None:
    rows, hands, honors, games = [], [], [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; hands += d["hands"]; honors += d["honors"]; games += d["games"]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    mean = lambda xs: sum(xs) / len(xs) if xs else 0
    print(f"== {label}: {games} games, {len(hands)} hands")
    print("-- how the hand was played")
    for kind in ("open", "riichi", "closed"):
        b = [h for h in hands if h[0] == kind]
        nets = [h[4] for h in b]
        m = mean(nets)
        se = math.sqrt(sum((x - m) ** 2 for x in nets) / len(nets) / len(nets)) if len(nets) > 1 else 0
        print(f"  {kind:<7} {pct(len(b), len(hands))} of hands  won {pct(sum(h[1] for h in b), len(b))}"
              f"  average win {mean([h[2] for h in b if h[1]]):6.0f}  dealt in {pct(sum(h[3] for h in b), len(b))}"
              f"  net per hand {m:+6.0f} (se {se:.0f})")

    def cell(name, sel):
        c = [r for r in rows if sel(r)]
        if not c:
            return
        pu = [r for r in c if r["pushed"]]
        fo = [r for r in c if not r["pushed"]]
        print(f"  {name:<36} n {len(c):5d}  push {pct(len(pu), len(c))}  pushed: won {pct(sum(r['won'] for r in pu), len(pu))}"
              f"  dealt in {pct(sum(r['dealt'] for r in pu), len(pu))} (into a caller {pct(sum(r['into_caller'] for r in pu), len(pu))})"
              f"  net {mean([r['delta'] for r in pu]):6.0f} | folded: n {len(fo):4d} won {pct(sum(r['won'] for r in fo), len(fo))}"
              f" dealt {pct(sum(r['dealt'] for r in fo), len(fo))} net {mean([r['delta'] for r in fo]):6.0f}")

    print("-- your hand open, another player open, no riichi, every tile that keeps the hand unsafe")
    for st, name in ((0, "tenpai"), (1, "1-shanten")):
        print(f"-- {name}")
        cell("all", lambda r, st=st: r["state"] == st)
        for t in ("no tells", "1 tell", "2-3 tells"):
            cell(t, lambda r, st=st, t=t: r["state"] == st and tells_bucket(r["tells"]) == t)
        for t in ("turn 9 or earlier", "turn 10-12", "turn 13+"):
            cell(t, lambda r, st=st, t=t: r["state"] == st and turn_bucket(r["turn"]) == t)
        cell("caller shows dora in a meld", lambda r, st=st: r["state"] == st and r["dora_melds"] > 0)
        cell("caller shows a yakuhai triplet", lambda r, st=st: r["state"] == st and r["yakuhai_meld"])
        if st == 1:
            for d in (0, 1, 2):
                cell(f"your dora {d}{'+' if d == 2 else ''}", lambda r, d=d: r["state"] == 1 and min(r["dora"], 2) == d)
    print("-- tenpai, by your value and the callers' tells")
    for v in ("no yaku", "1 han", "2 han", "3+ han"):
        cell(v, lambda r, v=v: r["state"] == 0 and value_bucket(r["han"]) == v)
        for t in ("no tells", "1 tell", "2-3 tells"):
            cell(f"   {t}", lambda r, v=v, t=t: r["state"] == 0 and value_bucket(r["han"]) == v and tells_bucket(r["tells"]) == t)
    print("-- tenpai with 1-2 han, by turn and by live tiles")
    for t in ("turn 9 or earlier", "turn 10-12", "turn 13+"):
        cell(t, lambda r, t=t: r["state"] == 0 and 1 <= r["han"] <= 2 and turn_bucket(r["turn"]) == t)
    for lo, hi in ((0, 3), (4, 7), (8, 30)):
        cell(f"live {lo}-{hi}", lambda r, lo=lo, hi=hi: r["state"] == 0 and 1 <= r["han"] <= 2 and lo <= r["live"] <= hi)
    print("-- the truth behind the tells: a caller was tenpai, and the pushed tile was on a caller's wait")
    for st, name in ((0, "tenpai"), (1, "1-shanten")):
        for t in ("no tells", "1 tell", "2-3 tells"):
            c = [r for r in rows if r["state"] == st and tells_bucket(r["tells"]) == t]
            pu = [r for r in c if r["pushed"]]
            print(f"  {name:<10} {t:<10} n {len(c):5d}  caller tenpai {pct(sum(r['caller_tenpai'] for r in c), len(c))}"
                  f"  pushed tile on a wait {pct(sum(r['on_wait'] for r in pu), len(pu))}")
    print("-- the tile pushed, where the tiles that keep the hand differ in danger")
    names = {2: "live honor or terminal", 3: "live 2-3-7-8 or half suji", 4: "live 4-5-6"}
    for st, name in ((0, "tenpai"), (1, "1-shanten")):
        pu = [r for r in rows if r["state"] == st and r["pushed"]]
        mixed = [r for r in pu if len({c[0] for c in r["choices"]}) > 1]
        least = [r for r in mixed if next(c[0] for c in r["choices"] if c[3]) == min(c[0] for c in r["choices"])]
        widest = [r for r in mixed if next(c[1] for c in r["choices"] if c[3]) == max(c[1] for c in r["choices"])]
        print(f"  {name:<10} pushes {len(pu):5d}, with a choice {len(mixed):4d}: cut the least dangerous {pct(len(least), len(mixed))}"
              f"  kept the most {'live tiles' if st == 0 else 'acceptance'} {pct(len(widest), len(mixed))}")
        print("   " + "  ".join(f"{names[d]} {pct(sum(1 for r in pu if r['danger'] == d), len(pu))}"
                               f" (into a caller {pct(sum(r['into_caller'] for r in pu if r['danger'] == d), sum(1 for r in pu if r['danger'] == d))})"
                               for d in (2, 3, 4)))
    print("-- honors cut while a caller is open and nobody is in riichi (not genbutsu, 0 or 1 other copy showing)")
    for who, flag in (("the player", 1), ("the other seats", 0)):
        parts = []
        for yak in (1, 0):
            for other in (0, 1):
                b = [h for h in honors if h[0] == flag and h[1] == yak and h[2] == other]
                parts.append(f"{'yakuhai' if yak else 'guest wind'}, {other} showing: {pct(sum(h[3] for h in b), len(b))} of {len(b):5d}")
        print(f"  {who:<16} dealt into a caller " + "  ".join(parts))


def leak(label: str, files: list[str]) -> None:
    rows = [r for f in files for r in json.loads(Path(f).read_text())["rows"]]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    opened = [r for r in rows if r["opened_turn"]]
    closed = [r for r in rows if not r["opened_turn"]]
    print(f"== {label}: deal-ins per 100 hands, by the kind of hand dealt into and your state at the deal-in")
    for name, rs in (("hands you opened", opened), ("hands kept closed", closed)):
        d = [r for r in rs if r["deal"]]
        print(f"-- {name}: n {len(rs)}, dealt in {pct(len(d), len(rs))}")
        for into in ("open", "riichi", "dama"):
            parts = "  ".join(f"{lab} {pct(sum(1 for r in d if r['deal']['into'] == into and r['deal']['state'] == st), len(rs))}"
                              for lab, st in (("tenpai", "0"), ("1-shanten", "1"), ("2+ shanten", "2"), ("in riichi", "riichi")))
            print(f"   into {into:<7} {pct(sum(1 for r in d if r['deal']['into'] == into), len(rs))}   {parts}")
        cost = [r["deal"]["cost"] for r in d if r["deal"]["into"] == "open"]
        print(f"   average deal-in into an open hand {sum(cost) / max(1, len(cost)):6.0f}")


def wins(label: str, files: list[str]) -> None:
    rows = [r for f in files for r in json.loads(Path(f).read_text())["rows"]]
    op = [r for r in rows if r["opened_turn"] and r["won"] and r.get("han")]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    total = [sum(r["han"].values()) for r in op]
    sources = sorted({k for r in op for k in r["han"]})
    print(f"== {label}: {len(op)} open wins, average {sum(r['value'] for r in op) / max(1, len(op)):6.0f} points,"
          f" {sum(total) / max(1, len(op)):.2f} han")
    print("   han per win by source: " + ", ".join(f"{k} {sum(r['han'].get(k, 0) for r in op) / len(op):.2f}" for k in sources))
    print(f"   1 han {pct(sum(1 for t in total if t == 1), len(op))}  2 han {pct(sum(1 for t in total if t == 2), len(op))}"
          f"  3 han or more {pct(sum(1 for t in total if t >= 3), len(op))}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "leak":
        leak(sys.argv[2], sys.argv[3:])
    elif sys.argv[1] == "wins":
        wins(sys.argv[2], sys.argv[3:])
    else:
        report(sys.argv[2], sys.argv[3:])
