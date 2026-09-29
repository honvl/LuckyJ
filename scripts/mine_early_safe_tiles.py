#!/usr/bin/env python3
"""Early safe tiles: which leftover goes first, and what is safe in hand when a riichi comes.

``leftovers`` reads tenhou.net/6 logs and records the book's safe-tile timing choice
(``scripts/mine_safe_tile_timing.py``, which reads LuckyJ's NAGA reports) for any player: in a hand
the player does not deal, at each draw before their own riichi, by their own discard number
(discards after calls count), when the hand holds a leftover already in an opponent's river and a
live leftover of the same kind (guest wind, terminal, middle tile), which of the two was cut. A
leftover is a lone tile with no same-suit tile within two ranks; dragons, the seat wind and the
round wind are left out. Quiet = no opponent in riichi and none with two calls or more. Run on
LuckyJ's converted games it reproduces the published counts exactly. It also records the choice
between a lone guest wind already in an opponent's river and a lone live value honor (a dragon, the
seat wind or the round wind, in no river): kind "wind-vs-value", where a live cut means the value
honor went first and the discarded guest wind was kept.

``riichi`` records, at every riichi declaration, what the player held against the declarer
(``scripts/contrast/riichi_response.py``): genbutsu, other safe tiles, shanten, the label of the
first reply, and whether the player dealt in to that riichi.

``report`` compares the player with LuckyJ in the same spots: for leftovers, LuckyJ's rate at the
same discard and kind, from a curve fitted to LuckyJ's own leftover rows the way the book's safe-tile
section fits them (``fit_series`` in ``scripts/mine_safe_tile_timing.py``); for riichi, LuckyJ's
average at the same declarer discard, from LuckyJ's own riichi rows.

usage: mine_early_safe_tiles.py leftovers MANIFEST SINCE|- ROWS_OUT.json
       mine_early_safe_tiles.py riichi MANIFEST SINCE|- ROWS_OUT.json
       mine_early_safe_tiles.py report LABEL LEFTOVERS.json RIICHI.json LUCKYJ_LEFTOVERS.json LUCKYJ_RIICHI.json [--from YYYY-MM-DD]
"""

from __future__ import annotations

import datetime
import json
import math
import os
import sys
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "contrast"))

MAX_TURN = 18
SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}


def kind_of(b: int) -> str:
    if b >= 41:
        return "honor"
    return "terminal" if b % 10 in (1, 9) else "middle"


def leftovers_of(hand, own_wind: int, round_wind: int) -> set[int]:
    """Lone tiles with no same-suit tile within two ranks; dragons and value winds left out."""
    from tenhou_replay import base

    counts: dict[int, int] = {}
    for t in hand:
        counts[base(t)] = counts.get(base(t), 0) + 1
    out = set()
    for b, n in counts.items():
        if n != 1:
            continue
        if b >= 41:
            if b not in (45, 46, 47, own_wind, round_wind):
                out.add(b)
            continue
        rank, suit = b % 10, b - b % 10
        if not any(counts.get(suit + r) for r in range(rank - 2, rank + 3) if r != rank and 1 <= r <= 9):
            out.add(b)
    return out


def _leftover_work(g: dict) -> list:
    import tenhou_replay as tr
    from tenhou_replay import base

    rows = []
    hero = g["hero_seat"]
    for li, log in enumerate(tr.load_logs(g["file"])):
        game = tr.replay(log)
        if game["dealer"] == hero:
            continue
        own_wind, round_wind = tr.seat_wind(hero, game["kyoku"]), tr.round_wind(game["kyoku"])
        river: set[int] = set()
        own_turn = 0
        for e in game["events"]:
            if e["seat"] != hero:
                river.add(base(e["tile"]))
                continue
            own_turn += 1
            if e["called"] is not None or own_turn > MAX_TURN:
                continue
            if e["riichi_seats"][hero] is not None and e["riichi_seats"][hero] < e["index"]:
                continue
            opponents = [q for q in range(4) if q != hero]
            riichi = any(e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"] for q in opponents)
            melds = max(len(game["players"][q]["melds"][: e["meld_counts"][q]]) for q in opponents)
            split = "quiet" if not riichi and melds <= 1 else "threat"
            held = leftovers_of(e["hand_before"], own_wind, round_wind)
            cut = base(e["tile"])
            choices = [(kind, {b for b in held if kind_of(b) == kind and b in river},
                        {b for b in held if kind_of(b) == kind and b not in river}) for kind in ("honor", "terminal", "middle")]
            lone_honors = {b for b in {base(t) for t in e["hand_before"]}
                           if b >= 41 and sum(1 for t in e["hand_before"] if base(t) == b) == 1}
            value = {45, 46, 47, own_wind, round_wind}
            choices.append(("wind-vs-value", {b for b in lone_honors if b not in value and b in river},
                            {b for b in lone_honors if b in value and b not in river}))
            for kind, safe, live in choices:
                if safe and live and (cut in safe or cut in live):
                    rows.append({"game": g["uuid"], "hand": li, "round": game["round_name"], "turn": own_turn,
                                 "split": split, "kind": kind, "live_cut": cut in live})
    return rows


def _games(manifest: str, since: str | None) -> list[dict]:
    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    return games


def _write(out: str, payload: dict) -> None:
    Path(out + ".tmp").write_text(json.dumps(payload))
    os.replace(out + ".tmp", out)


def leftovers(manifest: str, since: str | None, out: str) -> None:
    games = _games(manifest, since)
    with Pool(8) as pool:
        rows = [r for chunk in pool.map(_leftover_work, games, chunksize=4) for r in chunk]
    _write(out, {"games": len(games), "rows": rows})
    print(f"{out}: {len(games)} games, {len(rows)} leftover choices")


def riichi(manifest: str, since: str | None, out: str) -> None:
    import riichi_response

    games = _games(manifest, since)
    with Pool(8) as pool:
        rows = [r for chunk in pool.map(riichi_response.work, games, chunksize=4) for r in chunk if r["lj_X"]]
    _write(out, {"games": len(games), "rows": rows})
    print(f"{out}: {len(games)} games, {len(rows)} riichi declarations faced")


def fitted_rates(rows: list[dict], split: str, kind: str) -> tuple[dict[int, float], dict]:
    """Per discard, a player's share of live cuts: a logistic spline fit where each discard has 10 or more
    choices, and outside that run the pooled counts of the nearest discards."""
    import mine_safe_tile_timing as timing

    by_turn = {t: [r for r in rows if r["split"] == split and r["kind"] == kind and r["turn"] == t] for t in range(1, MAX_TURN + 1)}
    points = [{"turn": t, "lj_k": sum(r["live_cut"] for r in c), "lj_n": len(c), "naga_k": 0, "naga_n": 0}
              for t, c in by_turn.items()]
    rates, fit = {}, {}
    span = timing._longest_run(list(range(1, MAX_TURN + 1)), {p["turn"]: p["lj_n"] for p in points}, timing.FIT_MIN_CHOICES)
    if span and span[1] > span[0] + 1:
        fit = timing.fit_series(points, "lj", span[0], span[1])
        fit["range"] = list(span)
        for t, pct, _, _ in fit["grid"]:
            if abs(t - round(t)) < 1e-6:
                rates[int(round(t))] = pct / 100
    for t in range(1, MAX_TURN + 1):
        if t in rates:
            continue
        k = n = 0
        for d in (0, -1, 1, -2, 2, -3, 3):
            p = next((q for q in points if q["turn"] == t + d), None)
            if p:
                k += p["lj_k"]
                n += p["lj_n"]
            if n >= 10:
                break
        rates[t] = k / n if n else 0.5
    return rates, fit


def report(label: str, leftover_file: str, riichi_file: str, luckyj_leftover_file: str, luckyj_riichi_file: str,
           since: str | None) -> None:
    cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp() if since else None
    manifest = {g["uuid"]: g["start_time"] for g in json.load(open("data/self_games/majsoul/index.json"))}
    keep = (lambda r: manifest.get(r["game"], 0) >= cutoff) if cutoff else (lambda r: True)
    rows = [r for r in json.loads(Path(leftover_file).read_text())["rows"] if keep(r)]
    lj_rows = json.loads(Path(luckyj_leftover_file).read_text())["rows"]
    rates = {(split, kind): fitted_rates(lj_rows, split, kind)[0]
             for split in ("quiet", "threat") for kind in ("honor", "terminal", "middle", "wind-vs-value")}
    print(f"== {label}{' since ' + since if since else ''}: leftover choices, you against LuckyJ at the same discard")
    groups = (("guest winds, discards 1-2", lambda r: r["kind"] == "honor" and r["turn"] <= 2),
              ("guest winds, discard 3 on", lambda r: r["kind"] == "honor" and r["turn"] >= 3),
              ("terminals", lambda r: r["kind"] == "terminal"), ("middle tiles", lambda r: r["kind"] == "middle"),
              ("value honor vs discarded wind", lambda r: r["kind"] == "wind-vs-value"))
    for split in ("quiet", "threat"):
        for name, sel in groups:
            c = [r for r in rows if r["split"] == split and sel(r)]
            if not c:
                continue
            live = sum(r["live_cut"] for r in c)
            p = [rates[(split, r["kind"])][r["turn"]] for r in c]
            exp, var = sum(p), sum(q * (1 - q) for q in p)
            z = (live - exp) / math.sqrt(var) if var else 0.0
            print(f"  {split:<6} {name:<27} threw the live one {live:4d} of {len(c):4d} = {100 * live / len(c):5.1f}%"
                  f"   LuckyJ in the same spots {100 * exp / len(c):5.1f}%   ({z:+.1f} SD)")
    for kind, name in (("honor", "two guest winds, one already discarded"),
                       ("wind-vs-value", "a live value honor against a discarded guest wind")):
        print(f"== {name}, nobody threatening: per discard, the share where the live one went first")
        for who, rs in (("LuckyJ", lj_rows), (label, rows)):
            per, fit = fitted_rates(rs, "quiet", kind)
            counts = {t: [r for r in rs if r["split"] == "quiet" and r["kind"] == kind and r["turn"] == t] for t in range(1, 9)}
            cross = [c["turn"] for c in fit.get("crossings_50", [])]
            print(f"  {who:<8} fitted over discards {fit.get('range')}, 50% crossed at {cross}: " + "  ".join(
                f"{t}: {100 * per[t]:3.0f}% ({sum(r['live_cut'] for r in counts[t])}/{len(counts[t])})" for t in range(1, 9)))
    you = [r for r in json.loads(Path(riichi_file).read_text())["rows"] if keep(r) and r["x_shanten"] >= 1 and not r["other_riichi"]]
    lj = [r for r in json.loads(Path(luckyj_riichi_file).read_text())["rows"] if r["x_shanten"] >= 1 and not r["other_riichi"]]
    by_turn: dict[int, list] = {}
    for r in lj:
        by_turn.setdefault(min(r["r_turn"], MAX_TURN), []).append(r)

    def lj_mean(turn: int, f) -> float:
        rs = by_turn.get(min(turn, MAX_TURN)) or []
        return sum(f(r) for r in rs) / len(rs) if rs else 0.0

    print(f"== {label}: a riichi declared while you were not tenpai, against LuckyJ at the same declarer discard")
    for name, sel in (("declared by their 4th discard", lambda r: r["r_turn"] <= 4), ("5th or 6th", lambda r: 5 <= r["r_turn"] <= 6),
                      ("7th to 9th", lambda r: 7 <= r["r_turn"] <= 9), ("10th to 12th", lambda r: 10 <= r["r_turn"] <= 12),
                      ("13th on", lambda r: r["r_turn"] >= 13), ("every riichi", lambda r: True)):
        c = [r for r in you if sel(r)]
        if not c:
            continue
        n = len(c)
        gen = sum(r["n_gen"] for r in c) / n
        none = sum(r["n_gen"] == 0 for r in c) / n
        live = sum(bool(r["first_lab"]) and r["first_lab"] not in SAFE for r in c) / n
        into = sum(r["into_R"] for r in c) / n
        e_gen = sum(lj_mean(r["r_turn"], lambda x: x["n_gen"]) for r in c) / n
        e_none = sum(lj_mean(r["r_turn"], lambda x: x["n_gen"] == 0) for r in c) / n
        e_live = sum(lj_mean(r["r_turn"], lambda x: bool(x["first_lab"]) and x["first_lab"] not in SAFE) for r in c) / n
        e_into = sum(lj_mean(r["r_turn"], lambda x: x["into_R"]) for r in c) / n
        print(f"  {name:<30} n {n:4d}  genbutsu held {gen:4.2f} (LuckyJ {e_gen:4.2f})  none {100 * none:5.1f}% ({100 * e_none:5.1f}%)"
              f"  first reply live {100 * live:5.1f}% ({100 * e_live:5.1f}%)  dealt in to it {100 * into:5.1f}% ({100 * e_into:5.1f}%)")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode in ("leftovers", "riichi"):
        (leftovers if mode == "leftovers" else riichi)(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        since = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else None
        args = [a for i, a in enumerate(sys.argv[2:], 2) if a != "--from" and sys.argv[i - 1] != "--from"]
        report(args[0], args[1], args[2], args[3], args[4], since)
