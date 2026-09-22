#!/usr/bin/env python3
"""Push and fold against a riichi, with safety measured the way the table allows.

Safety counts a tile as safe against a riichi player when it is in that player's river,
when anyone discarded it after the declaration without being ronned (riichi furiten),
when it is suji of the river, or when it is an honor with two or more other copies
showing. The older review scripts only looked at the declarer's own river, which counts
furiten-safe tiles as pushes.

usage: mine_riichi_folds.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_riichi_folds.py report LABEL ROWS.json [ROWS.json ...] [--examples]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SAFE = {"genbutsu", "dead", "suji", "honor, 2 seen"}
# Safety classes from safest to most dangerous; a tile's class is its worst label over the riichi players.
CLASS_OF = {"genbutsu": "genbutsu", "dead": "genbutsu", "honor, 2 seen": "honor 2 seen", "suji": "suji",
            "live honor": "live honor", "live terminal": "live terminal", "live 2-3-7-8": "live 2-8", "live 4-5-6": "live 2-8"}
CLASS_ORDER = ["genbutsu", "honor 2 seen", "suji", "live honor", "live terminal", "live 2-8"]


def worst_class(labels):
    return max((CLASS_OF[label] for label in labels), key=CLASS_ORDER.index)


def compute(manifest: str, since: str | None, out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, safety, visible_counter
    from tenhou_replay import base, is_red, name, names

    games = json.load(open(manifest))
    if since:
        fmt = "%Y-%m-%dT%H:%M" if "T" in since else "%Y-%m-%d"
        cutoff = datetime.datetime.strptime(since, fmt).timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    rows, tenpai_rows = [], []
    hands = 0
    for g in sorted(games, key=lambda g: g["start_time"]):
        hero = g["hero_seat"]
        for log in tr.load_logs(g["file"]):
            hands += 1
            game = tr.replay(log)
            players = game["players"]
            dset = frozenset(ws.dora_from_indicator(t) for t in game["dora_indicators"][:1])
            blocks = tr.result_blocks(log[-1])
            loser = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            hero_events = [e for e in game["events"] if e["seat"] == hero]
            last = hero_events[-1]["index"] if hero_events else None
            recs = ws.hand_records(log, set())
            ft = recs[hero]["first_closed_tenpai"]
            if ft:
                tenpai_rows.append({"game": g["uuid"], "date": g["date"], "round": game["round_name"], **{
                    k: ft.get(k) for k in ("turn", "declared", "threat", "live", "yakuless")},
                    "riichi_later": recs[hero]["riichi_turn"] is not None,
                    "dora": sum(1 for t in players[hero]["haipai"] if base(t) in dset or is_red(t)),
                    "dealer": game["dealer"] == hero, "won": any(d[0] == hero for _, d in blocks)})
            for e in hero_events:
                if e["riichi_seats"][hero] is not None or e["riichi"]:
                    continue
                reached = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
                if not reached:
                    continue
                snap = meld_snapshots(game, e["index"] - 1)
                snap[hero] = e["melds"]
                visible = visible_counter(e["hand_before"], e, players, snap, game["dora_indicators"][:1])
                cands = {}
                for t in {x for x in e["hand_before"]}:
                    rest = list(e["hand_before"])
                    rest.remove(t)
                    seen = visible.copy()
                    seen[base(t)] -= 1
                    labels = [safety(t, q, e, game, seen) for q in reached]
                    cands[t] = (ws.hand_shanten(rest, e["meld_tiles"], e["closed"]), all(l in SAFE for l in labels), labels)
                best = min(c[0] for c in cands.values())
                a_s, a_safe, a_labels = cands[e["tile"]]
                keep_safe = [t for t, c in cands.items() if c[0] == best and c[1]]
                # the safest class that keeps the best shanten, and the class actually cut
                keep_classes = {worst_class(c[2]) for c in cands.values() if c[0] == best}
                best_keep_class = min(keep_classes, key=CLASS_ORDER.index)
                any_safe = [t for t, c in cands.items() if c[1]]
                acc_gap = None
                if not a_safe and keep_safe:
                    rest = list(e["hand_before"])
                    rest.remove(e["tile"])
                    a_acc = ws.acceptance(rest, e["meld_tiles"], e["closed"], visible)[1]
                    gaps = []
                    for t in keep_safe:
                        r2 = list(e["hand_before"])
                        r2.remove(t)
                        gaps.append(a_acc - ws.acceptance(r2, e["meld_tiles"], e["closed"], visible)[1])
                    acc_gap = min(gaps)
                dora = sum(1 for t in list(e["hand_before"]) + list(e["meld_tiles"]) if base(t) in dset or is_red(t))
                dealt = loser.get(hero) is not None and e["index"] == last
                rows.append({
                    "game": g["uuid"], "date": g["date"], "round": game["round_name"], "turn": e["turn"],
                    "best": best, "a_s": a_s, "push": not a_safe, "keep_safe": bool(keep_safe), "any_safe": bool(any_safe),
                    "acc_gap": acc_gap, "open": not e["closed"], "dora": dora, "dealer": game["dealer"] == hero,
                    "dealt": dealt, "riichis": len(reached), "tile": name(e["tile"]), "labels": a_labels,
                    "safe_keep_tiles": [name(t) for t in keep_safe], "hand": names(e["hand_before"]),
                    "cut_class": worst_class(a_labels), "best_keep_class": best_keep_class,
                })
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "hands": hands, "rows": rows, "tenpai": tenpai_rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {hands} hands, {len(rows)} discards facing a riichi")


def pct(n, d):
    return f"{100 * n / d:5.1f}%" if d else "    -"


def report(label: str, files: list[str], examples: bool) -> None:
    rows, tenpai, games, hands = [], [], 0, 0
    for f in files:
        d = json.loads(Path(f).read_text())
        rows += d["rows"]; tenpai += d["tenpai"]; games += d["games"]; hands += d["hands"]
    print(f"== {label}: {games} games, {hands} hands, {len(rows)} discards facing a riichi (not in riichi yourself)")
    sb = lambda s: "0" if s == 0 else "1" if s == 1 else "2" if s == 2 else "3+"
    tb = lambda t: "<=8" if t <= 8 else "9-12" if t <= 12 else "13+"
    print("  push = the cut was not safe against every riichi player; free fold = a safe tile kept the same shanten")
    for s in ("0", "1", "2", "3+"):
        sub = [r for r in rows if sb(r["best"]) == s]
        line = f"  {s:>2}-shanten n {len(sub):5d}  push {pct(sum(r['push'] for r in sub), len(sub))}"
        line += f"  | free fold existed {pct(sum(r['keep_safe'] for r in sub), len(sub))}, pushed anyway {pct(sum(r['push'] and r['keep_safe'] for r in sub), sum(r['keep_safe'] for r in sub))}"
        line += "  | by turn " + "  ".join(f"{t}: {pct(sum(r['push'] for r in sub if tb(r['turn']) == t), sum(1 for r in sub if tb(r['turn']) == t))} (n {sum(1 for r in sub if tb(r['turn']) == t)})" for t in ("<=8", "9-12", "13+"))
        print(line)
    print("  pushed anyway although a safe tile kept the shanten, by what the safe tile cost in acceptance")
    for s in ("1", "2", "3+"):
        sub = [r for r in rows if sb(r["best"]) == s and r["keep_safe"]]
        for lo, hi, lab in ((None, 0, "cost nothing or gained"), (1, 3, "cost 1-3"), (4, 999, "cost 4+")):
            ss = [r for r in sub if r["acc_gap"] is not None and (r["acc_gap"] <= hi if lo is None else lo <= r["acc_gap"] <= hi)]
            base_n = len(sub)
            print(f"    {s:>2}-shanten, safe tile {lab:<22} pushed {pct(len(ss), base_n)} of {base_n}")
    print("  1-shanten pushes by dora in hand and turn (dealer in brackets)")
    for dk, lab in ((0, "0"), (1, "1"), (2, "2"), (3, "3+")):
        sub = [r for r in rows if r["best"] == 1 and min(r["dora"], 3) == dk]
        cells = []
        for t in ("<=8", "9-12", "13+"):
            ss = [r for r in sub if tb(r["turn"]) == t]
            dd = [r for r in ss if r["dealer"]]
            cells.append(f"{t}: {pct(sum(r['push'] for r in ss), len(ss))} n {len(ss):4d} [{pct(sum(r['push'] for r in dd), len(dd))} n {len(dd)}]")
        print(f"    dora {lab:<3} " + "  ".join(cells))
    one = [r for r in rows if r["riichis"] == 1 and "cut_class" in r]
    print("  deal-ins per 100 cuts against a single riichi, by the class of the tile cut (a deal-in to anyone)")
    for cls in CLASS_ORDER:
        ss = [r for r in one if r["cut_class"] == cls]
        if ss:
            print(f"    {cls:<14} n {len(ss):6d}  deal-in per 100 {100 * sum(r['dealt'] for r in ss) / len(ss):5.2f}")
    print("  what was cut when a tile of the safest class kept the same shanten")
    for keep in ("genbutsu", "honor 2 seen", "suji"):
        ss = [r for r in rows if r.get("best_keep_class") == keep]
        if ss:
            dist = "  ".join(f"{cls} {pct(sum(r['cut_class'] == cls for r in ss), len(ss))}" for cls in CLASS_ORDER)
            print(f"    safest keeping tile {keep:<13} n {len(ss):6d}: {dist}")
    print("  deal-ins per 100 discards facing a riichi, by shanten: " + "  ".join(
        f"{s}: {100 * sum(r['dealt'] for r in rows if sb(r['best']) == s) / max(1, sum(1 for r in rows if sb(r['best']) == s)):.2f}" for s in ("0", "1", "2", "3+")))
    # riichi decision at first closed tenpai
    quiet = [t for t in tenpai if not t["threat"]]
    print(f"  first closed tenpai with no riichi out: {len(quiet)}; declared {pct(sum(t['declared'] for t in quiet), len(quiet))}")
    for lo, hi, lab in ((0, 3, "<=3"), (4, 7, "4-7"), (8, 99, "8+")):
        ss = [t for t in quiet if lo <= (t["live"] or 0) <= hi]
        early = [t for t in ss if t["turn"] <= 10]
        print(f"    waits {lab:<4} n {len(ss):4d} declared {pct(sum(t['declared'] for t in ss), len(ss))}  (turn <=10: {pct(sum(t['declared'] for t in early), len(early))} n {len(early)})")
    yl = [t for t in quiet if t["yakuless"]]
    print(f"    yakuless: n {len(yl)} declared {pct(sum(t['declared'] for t in yl), len(yl))}, riichi later {pct(sum(t['riichi_later'] and not t['declared'] for t in yl), len(yl))}")
    if examples:
        print("  -- 2+ shanten pushes while a safe tile kept the shanten")
        for r in rows:
            if r["best"] >= 2 and r["push"] and r["keep_safe"]:
                print(f"    {r['date']} {r['game'][:15]} {r['round']} T{r['turn']}: cut {r['tile']} {r['labels']} at {r['best']}-shanten; safe keep {r['safe_keep_tiles']} (acceptance gap {r['acc_gap']}); dora {r['dora']}{' DEALT IN' if r['dealt'] else ''}")
        print("  -- 1-shanten pushes turn 13+ while a safe tile kept the shanten")
        for r in rows:
            if r["best"] == 1 and r["push"] and r["keep_safe"] and r["turn"] >= 13:
                print(f"    {r['date']} {r['game'][:15]} {r['round']} T{r['turn']}: cut {r['tile']} {r['labels']}; safe keep {r['safe_keep_tiles']} (gap {r['acc_gap']}); dora {r['dora']}{' DEALT IN' if r['dealt'] else ''}")
        print("  -- first closed tenpai kept dama with no riichi out, 4+ live, turn <= 10")
        for t in quiet:
            if not t["declared"] and (t["live"] or 0) >= 4 and t["turn"] <= 10:
                print(f"    {t['date']} {t['game'][:15]} {t['round']} T{t['turn']}: live {t['live']} yakuless {t['yakuless']} dora {t['dora']} dealer {t['dealer']} riichi later {t['riichi_later']} won {t['won']}")
        print("  -- yakuless first closed tenpai kept dama")
        for t in yl:
            if not t["declared"]:
                print(f"    {t['date']} {t['game'][:15]} {t['round']} T{t['turn']}: live {t['live']} dora {t['dora']} riichi later {t['riichi_later']} won {t['won']}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        args = [a for a in sys.argv[3:] if a != "--examples"]
        report(sys.argv[2], args, "--examples" in sys.argv)
