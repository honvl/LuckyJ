#!/usr/bin/env python3
"""Open tenpai against a riichi when keeping the wait needs a dangerous tile: push or fold?

For each hand, the first discard where the player holds an open tenpai (some discard keeps
tenpai), someone else is in riichi, and every tenpai-keeping tile is unsafe against at least
one riichi player. Safety is build_personal_guide.safety: genbutsu (river or passed after the
declaration), suji, or an honor with two other copies showing count as safe. The wait is the
best tenpai the player could keep: most live tiles, then most han on ron (0 han = no yaku).

usage: mine_open_tenpai_push.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_open_tenpai_push.py report LABEL ROWS.json [ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}


def to136(codes, used):
    """Replay tile codes to the mahjong library's 136 ids.

    The library treats copy 0 of each five (ids 16, 52, 88) as the red five, so plain fives
    take copies 1-3 and only a real red five takes copy 0. ``used`` counts copies per kind.
    """
    from tenhou_replay import TILE_ORDER, base, is_red

    ids = []
    for c in codes:
        k = TILE_ORDER.index(base(c))
        if is_red(c):
            ids.append(k * 4)
            continue
        start = 1 if base(c) in (15, 25, 35) else 0
        ids.append(k * 4 + start + used[k])
        used[k] += 1
    return ids


def compute(manifest: str, since: str | None, out: str) -> None:
    from mahjong.constants import EAST
    from mahjong.hand_calculating.hand import HandCalculator
    from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules
    from mahjong.meld import Meld

    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, safety, visible_counter
    from tenhou_replay import TILE_ORDER, base, is_red

    calc = HandCalculator()
    rules = OptionalRules(has_open_tanyao=True, has_aka_dora=True)
    kinds = {"c": Meld.CHI, "p": Meld.PON, "m": Meld.KAN, "k": Meld.KAN, "a": Meld.KAN}

    def han_on(hand13, melds, win, seat, kyoku, dora_set):
        used = Counter()
        mo = []
        for m in melds:
            ids = sorted(to136(sorted(m["tiles"], key=base), used))
            mo.append(Meld(meld_type=kinds[m["kind"]], tiles=ids, opened=m["kind"] != "a"))
        hid = to136(list(hand13) + [win], used)
        cfg = HandConfig(is_tsumo=False, is_riichi=False, options=rules,
                         player_wind=EAST + tr.seat_wind(seat, kyoku) - 41, round_wind=EAST + tr.round_wind(kyoku) - 41)
        try:
            res = calc.estimate_hand_value(hid + [t for x in mo for t in x.tiles], hid[-1], melds=mo, config=cfg)
        except Exception:
            return None
        if res.error:
            return 0
        # res.han already includes red fives (has_aka_dora); add the indicator dora.
        dora = sum(1 for t in list(hand13) + [win] + [t for m in melds for t in m["tiles"]] if base(t) in dora_set)
        return res.han + dora

    games = json.load(open(manifest))
    if since:
        fmt = "%Y-%m-%dT%H:%M" if "T" in since else "%Y-%m-%d"
        cutoff = datetime.datetime.strptime(since, fmt).timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    rows = []
    for g in games:
        hero = g["hero_seat"]
        for log in tr.load_logs(g["file"]):
            game = tr.replay(log)
            p = game["players"][hero]
            if not any(m["kind"] != "a" for m in p["melds"]):
                continue
            indicators = game["dora_indicators"][:1]
            dora_set = frozenset(ws.dora_from_indicator(t) for t in indicators)
            blocks = tr.result_blocks(log[-1])
            for e in game["events"]:
                if e["seat"] != hero or e["riichi_seats"][hero] is not None:
                    continue
                my_melds = p["melds"][: len(e["melds"])]
                if not any(m["kind"] != "a" for m in my_melds):
                    continue
                reached = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
                if not reached:
                    continue
                snap = meld_snapshots(game, e["index"] - 1)
                snap[hero] = e["melds"]
                visible = visible_counter(e["hand_before"], e, game["players"], snap, indicators)
                keep = {}
                for t in {x for x in e["hand_before"]}:
                    rest = list(e["hand_before"])
                    rest.remove(t)
                    if ws.hand_shanten(rest, e["meld_tiles"], False) != 0:
                        continue
                    seen = visible.copy()
                    seen[base(t)] -= 1
                    keep[t] = (rest, all(safety(t, q, e, game, seen) in SAFE for q in reached))
                if not keep or any(safe for _, safe in keep.values()):
                    continue
                best_live, best_han, yakuful_live = -1, -1, 0
                for t, (rest, _) in keep.items():
                    waits = tr.waits(rest, e["meld_tiles"], closed=False)
                    live = sum(max(0, 4 - visible[base(w)]) for w in waits)
                    hans = {w: han_on(rest, my_melds, w, hero, game["kyoku"], dora_set) for w in waits}
                    han = max((h for h in hans.values() if h is not None), default=0)
                    yl = sum(max(0, 4 - visible[base(w)]) for w, h in hans.items() if h)
                    if (live, han) > (best_live, best_han):
                        best_live, best_han, yakuful_live = live, han, yl
                pushed = ws.hand_shanten(e["hand_after"], e["meld_tiles"], False) == 0
                rows.append({
                    "game": g["uuid"], "round": game["round_name"], "turn": e["turn"], "live": best_live, "han": best_han,
                    "yakuful_live": yakuful_live, "pushed": pushed,
                    "won": any(d[0] == hero for _, d in blocks),
                    "dealt": any(d[1] == hero and d[0] != hero for _, d in blocks),
                    "delta": tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero],
                })
                break
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} dilemma hands")


def report(label: str, files: list[str]) -> None:
    rows, games = [], 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; games += d["games"]
    pct = lambda a, b: f"{100 * a / b:5.1f}%" if b else "    -"
    print(f"== {label}: {games} games; open tenpai against a riichi where every tenpai-keeping tile is unsafe: {len(rows)} hands")

    def cell(name, sel):
        c = [r for r in rows if sel(r)]
        if not c:
            return
        pu = [r for r in c if r["pushed"]]
        print(f"  {name:<30} n {len(c):5d}  push {pct(len(pu), len(c))}  push: win {pct(sum(r['won'] for r in pu), len(pu))} deal-in {pct(sum(r['dealt'] for r in pu), len(pu))}")

    cell("all", lambda r: True)
    cell("no yaku on any wait", lambda r: r["han"] == 0)
    for w, lo, hi in (("waits <=3", 0, 3), ("waits 4-7", 4, 7), ("waits 8+", 8, 99)):
        cell(w, lambda r, lo=lo, hi=hi: lo <= r["live"] <= hi)
        for v, vlo, vhi in ((" 1-2 han", 1, 2), (" 3-4 han", 3, 4), (" 5+ han", 5, 99)):
            cell(w + v, lambda r, lo=lo, hi=hi, vlo=vlo, vhi=vhi: lo <= r["live"] <= hi and vlo <= r["han"] <= vhi)
    for t, lo, hi in (("turn <=8", 0, 8), ("turn 9-12", 9, 12), ("turn 13+", 13, 99)):
        cell(t, lambda r, lo=lo, hi=hi: lo <= r["turn"] <= hi)


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        report(sys.argv[2], sys.argv[3:])
