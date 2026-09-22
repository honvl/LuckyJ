#!/usr/bin/env python3
"""Where hands dealt dora are won or lost: reaching tenpai, the wait, the declaration, and after.

For every hand, by the dora and red fives in the deal: whether and when the player reached
tenpai, what the first tenpai looked like (closed or open, live winning tiles, riichi, dama),
whether that tenpai was later given up, how the hand ended, and for a deal-in, what state the
player was in and whether the tile was a push or a fold tile against the winner.

Each win also records where its han came from (dora, red fives, ura, riichi, tsumo, yakuhai,
shape yaku), so the value of a win can be traced to the plan that made it.

``expected`` asks how many of a player's tenpai hands a baseline player would have won from the
same spot: same path (riichi at first tenpai, dama, open), the same table (quiet, a call, a riichi),
the same number of live winning tiles and the same turn. The baseline's win rate in each cell is
shrunk toward its path average (20 hands of weight), because opponents cannot see a hand's dora and
the rate should not depend on it.

usage: mine_dora_hands.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_dora_hands.py report LABEL ROWS.json [ROWS.json ...]
       mine_dora_hands.py expected PLAYER_ROWS.json BASELINE_ROWS.json [BASELINE_ROWS.json ...]
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}
HAN_CATEGORY = {"ドラ": "dora", "赤ドラ": "aka", "裏ドラ": "ura", "立直": "riichi", "ダブル立直": "riichi",
                "一発": "ippatsu", "門前清自摸和": "tsumo"}
FLUSH = {"混一色", "清一色"}


def win_han(detail: list) -> tuple[dict, list]:
    """Han of one win by source, and the yaku names (numeric yaku ids mapped to Tenhou names)."""
    import review_win_speed as ws

    han, names = {}, []
    for entry in detail[4:]:
        name = entry.split("(")[0].strip()
        if name.startswith("yaku") and name[4:].isdigit():
            name = ws.TENHOU_YAKU.get(int(name[4:]), name)
        m = ws.HAN_RE.search(entry)
        h = int(m.group(1)) if m else (13 if "役満" in entry else 0)
        if not h:
            continue
        cat = HAN_CATEGORY.get(name, "yakuhai" if name.startswith("役牌") else "shape")
        han[cat] = han.get(cat, 0) + h
        names.append(name)
    if not han:
        head = detail[3] if len(detail) > 3 else ""
        m = ws.HAN_RE.search(head)
        han["shape"] = int(m.group(1)) if m else next((v for k, v in ws.LIMIT_HAN.items() if k in head), 0)
    return han, names


def path(r: dict) -> str | None:
    """How the hand's first tenpai was played: riichi at once, riichi later, dama, or open."""
    f = r["first"]
    if not f:
        return None
    if not f["closed"]:
        return "open"
    if f["riichi"]:
        return "riichi first"
    return "riichi later" if r["riichi_turn"] else "dama"


def compute(manifest: str, since: str | None, out: str) -> None:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, safety, visible_counter
    from mine_open_tenpai_push import ron_value
    from tenhou_replay import base, is_red

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
            indicators = game["dora_indicators"][:1]
            dset = frozenset(ws.dora_from_indicator(t) for t in indicators)
            isd = lambda t: base(t) in dset or is_red(t)
            blocks = tr.result_blocks(log[-1])
            won = any(d[0] == hero for _, d in blocks)
            loser = {d[1]: d[0] for _, d in blocks if len(d) > 1 and d[0] != d[1]}
            value = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero] if won else 0
            evs = [e for e in game["events"] if e["seat"] == hero]
            if not evs:
                continue

            def threat_at(e):
                riichi = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
                calls = max((sum(1 for m in game["players"][q]["melds"][: e["meld_counts"][q]] if m["kind"] != "a")
                             for q in range(4) if q != hero), default=0)
                return "riichi" if riichi else f"{min(calls, 2)} call" if calls else "quiet"

            first = None
            broke = None
            for e in evs:
                sh = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
                if sh == 0 and first is None:
                    snap = meld_snapshots(game, e["index"] - 1)
                    snap[hero] = e["melds"]
                    visible = visible_counter(e["hand_before"], e, game["players"], snap, indicators)
                    waits = tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])
                    live = sum(max(0, 4 - visible[base(w)]) for w in waits)
                    yakuless = e["closed"] and not any(ws.ron_has_yaku(e["hand_after"], w, hero, game["kyoku"]) for w in waits)
                    first = {"turn": e["turn"], "closed": e["closed"], "live": live, "kinds": len(waits),
                             "riichi": e["riichi"], "threat": threat_at(e), "yakuless": bool(yakuless)}
                elif first is not None and sh > 0 and broke is None and e["riichi_seats"][hero] is None:
                    broke = {"turn": e["turn"], "threat": threat_at(e)}
            riichi_turn = next((e["turn"] for e in evs if e["riichi"]), None)
            # open first tenpai with no yaku on any wait
            if first is not None and not first["closed"]:
                fe = next(e for e in evs if e["turn"] == first["turn"])
                my_melds = p["melds"][: len(fe["melds"])]
                hans = [ron_value(fe["hand_after"], my_melds, w, hero, game["kyoku"], dset)
                        for w in tr.waits(fe["hand_after"], fe["meld_tiles"], False)]
                first["yakuless"] = not any(h for h in hans if h)
            # legal rons the player let go: a winning tile discarded by someone else while the player
            # was tenpai with a yaku and not furiten, and the player did not call ron
            passed = []
            waits, furiten, temp_furiten, riichi_furiten, state = [], False, False, False, None
            end_idx = len(game["events"]) - 1
            ron_on = {d[1] for _, d in blocks if d[0] == hero and d[1] != hero}
            for ev in game["events"]:
                if ev["seat"] == hero:
                    waits = tr.waits(ev["hand_after"], ev["meld_tiles"], ev["closed"])
                    mine = {base(x) for x in ev["rivers"][hero]} | {base(ev["tile"])}
                    furiten = any(base(w) in mine for w in waits)
                    temp_furiten = False
                    in_riichi = ev["riichi_seats"][hero] is not None or ev["riichi"]
                    state = (ev["hand_after"], p["melds"][: len(ev["melds"])], ev["closed"], in_riichi)
                    continue
                if not waits or state is None or base(ev["tile"]) not in {base(w) for w in waits}:
                    continue
                hand13, my_melds, closed, in_riichi = state
                legal = not (furiten or temp_furiten or riichi_furiten)
                if legal:
                    han = ron_value(hand13, my_melds, ev["tile"], hero, game["kyoku"], dset, riichi=in_riichi)
                    took = ev["index"] == end_idx and ev["seat"] in ron_on
                    if han and not took:
                        passed.append({"turn": ev["turn"], "han": han, "riichi": in_riichi})
                temp_furiten = True
                if in_riichi:
                    riichi_furiten = True
            deal = None
            if loser.get(hero) is not None:
                e = evs[-1]
                w = loser[hero]
                snap = meld_snapshots(game, e["index"] - 1)
                snap[hero] = e["melds"]
                visible = visible_counter(e["hand_before"], e, game["players"], snap, indicators)
                seen = visible.copy()
                seen[base(e["tile"])] -= 1
                label = safety(e["tile"], w, e, game, seen)
                wp = game["players"][w]
                deal = {
                    "state": "riichi" if e["riichi_seats"][hero] is not None or e["riichi"] else
                             str(min(ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]), 2)),
                    "into": "riichi" if wp["riichi_event"] is not None else "open" if any(m["kind"] != "a" for m in wp["melds"]) else "dama",
                    "fold_tile": label in SAFE, "label": label, "turn": e["turn"],
                    "cost": -tr.result_deltas(log[-1])[hero],
                }
            opened = next((e["turn"] for e in evs if e["called"] is not None), None)
            han, yaku = ({}, [])
            for _, d in blocks:
                if d[0] == hero:
                    han, yaku = win_han(d)
            rows.append({
                "game": g["uuid"], "round": game["round_name"],
                "hd": sum(1 for t in p["haipai"] if isd(t)),
                "haipai_shanten": ws.hand_shanten(p["haipai"]),
                "dealer": game["dealer"] == hero, "first": first, "broke": broke, "riichi_turn": riichi_turn,
                "opened_turn": opened, "won": won, "tsumo": won and any(d[0] == hero == d[1] for _, d in blocks),
                "value": value, "deal": deal, "draw": not blocks,
                "tenpai_end": bool(evs) and ws.hand_shanten(evs[-1]["hand_after"], evs[-1]["meld_tiles"], evs[-1]["closed"]) == 0,
                "passed": passed, "han": han, "yaku": yaku,
                "end": "won" if won else "dealt" if loser.get(hero) is not None else "draw" if not blocks else
                       "other tsumo" if any(d[0] == d[1] for _, d in blocks) else "other ron",
            })
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
    print(f"== {label}: {games} games, {len(rows)} hands")
    buckets = (("no dora", lambda r: r["hd"] == 0), ("1 dora", lambda r: r["hd"] == 1), ("2+ dora", lambda r: r["hd"] >= 2),
               ("any dora", lambda r: r["hd"] >= 1))
    for name, sel in buckets:
        rs = [r for r in rows if sel(r)]
        n = len(rs)
        t = [r for r in rs if r["first"]]
        closed = [r for r in t if r["first"]["closed"]]
        opn = [r for r in t if not r["first"]["closed"]]
        quiet_closed = [r for r in closed if r["first"]["threat"] == "quiet" and not r["first"]["yakuless"]]
        wins = [r for r in rs if r["won"]]
        print(f"-- {name}: {n} hands  (deal shanten {mean([r['haipai_shanten'] for r in rs]):.2f})")
        print(f"   reached tenpai {pct(len(t), n)}  first tenpai turn {mean([r['first']['turn'] for r in t]):.1f}"
              f"  by turn 9 {pct(sum(r['first']['turn'] <= 9 for r in t), n)}  by turn 12 {pct(sum(r['first']['turn'] <= 12 for r in t), n)}")
        print(f"   first tenpai closed {pct(len(closed), len(t))}  open {pct(len(opn), len(t))}"
              f"  live tiles {mean([r['first']['live'] for r in t]):.2f}  4+ live {pct(sum(r['first']['live'] >= 4 for r in t), len(t))}"
              f"  2+ wait kinds {pct(sum(r['first']['kinds'] >= 2 for r in t), len(t))}")
        print(f"   closed first tenpai, quiet table, with a yaku: n {len(quiet_closed)}  declared {pct(sum(r['first']['riichi'] for r in quiet_closed), len(quiet_closed))}")
        conv = [r for r in t]
        print(f"   won {pct(len(wins), n)}  won given tenpai {pct(sum(r['won'] for r in conv), len(conv))}"
              f"  by first tenpai: closed {pct(sum(r['won'] for r in closed), len(closed))} open {pct(sum(r['won'] for r in opn), len(opn))}"
              f"  riichi {pct(sum(r['won'] for r in t if r['riichi_turn']), sum(1 for r in t if r['riichi_turn']))}"
              f"  dama {pct(sum(r['won'] for r in closed if not r['riichi_turn']), sum(1 for r in closed if not r['riichi_turn']))}")
        gave = [r for r in t if r["broke"] and not r["won"]]
        print(f"   tenpai given up and not won back {pct(len(gave), len(t))}"
              f"  (under a riichi {pct(sum(r['broke']['threat'] == 'riichi' for r in gave), len(gave))})"
              f"  tenpai at a draw {pct(sum(r['draw'] and r['tenpai_end'] for r in rs), sum(r['draw'] for r in rs))}")
        print(f"   win value {mean([r['value'] for r in wins]):6.0f}  tsumo share {pct(sum(r['tsumo'] for r in wins), len(wins))}")
        yl_open = [r for r in opn if r["first"].get("yakuless")]
        yl_closed = [r for r in closed if r["first"].get("yakuless")]
        print(f"   first tenpai with no yaku: open {pct(len(yl_open), len(opn))} (won {pct(sum(r['won'] for r in yl_open), len(yl_open))})"
              f"  closed {pct(len(yl_closed), len(closed))} (won {pct(sum(r['won'] for r in yl_closed), len(yl_closed))})")
        pr = [r for r in t if r["passed"]]
        print(f"   tenpai hands that let a legal ron go by {pct(len(pr), len(t))}  (later won {pct(sum(r['won'] for r in pr), len(pr))},"
              f" later dealt in {pct(sum(bool(r['deal']) for r in pr), len(pr))}); passes per 100 tenpai hands {100 * sum(len(r['passed']) for r in t) / max(1, len(t)):.1f}")
        lost = [r for r in t if not r["won"]]
        print("   unwon tenpai hands ended by: " + "  ".join(f"{k} {pct(sum(r['end'] == k for r in lost), len(lost))}"
                                                        for k in ("other ron", "other tsumo", "dealt", "draw")))
        di = [r for r in rs if r["deal"]]
        print(f"   points per hand: won {sum(r['value'] for r in wins) / n:6.0f}  lost to deal-ins {sum(r['deal']['cost'] for r in di) / n:5.0f}")
        for pa in ("riichi first", "riichi later", "dama", "open"):
            w = [r for r in wins if path(r) == pa]
            if not w:
                continue
            h = lambda *ks: mean([sum(r["han"].get(k, 0) for k in ks) for r in w])
            print(f"      {pa:<13} wins per 100 hands {100 * len(w) / n:5.2f}  value {mean([r['value'] for r in w]):6.0f}"
                  f"  mangan+ {pct(sum(r['value'] >= 7700 for r in w), len(w))}  han: dora+red {h('dora', 'aka'):.2f}  ura {h('ura'):.2f}"
                  f"  riichi/ippatsu/tsumo {h('riichi', 'ippatsu', 'tsumo'):.2f}  yakuhai {h('yakuhai'):.2f}  shape {h('shape'):.2f}")
        for pa, sel in (("riichi first", lambda r: path(r) == "riichi first"), ("open", lambda r: path(r) == "open"),
                        ("all wins", lambda r: True)):
            w = [r for r in wins if sel(r)]
            if w:
                print(f"      {pa:<13} wins with no shape yaku {pct(sum(not r['han'].get('shape') for r in w), len(w))}"
                      f"  pinfu {pct(sum('平和' in r['yaku'] for r in w), len(w))}  tanyao {pct(sum('断幺九' in r['yaku'] for r in w), len(w))}")
        ow = [r for r in wins if path(r) == "open"]
        if ow:
            print(f"      open wins with a half or full flush {pct(sum(any(y in FLUSH for y in r['yaku']) for r in ow), len(ow))}"
                  f"  with tanyao {pct(sum('断幺九' in r['yaku'] for r in ow), len(ow))}")
        print(f"   dealt in {pct(len(di), n)}  avg cost {mean([r['deal']['cost'] for r in di]):5.0f}")
        for st in ("riichi", "0", "1", "2"):
            ss = [r for r in di if r["deal"]["state"] == st]
            lab = {"riichi": "in riichi", "0": "at tenpai", "1": "at 1-shanten", "2": "at 2+ shanten"}[st]
            print(f"      {lab:<14} {len(ss) * 100 / n:5.2f} per 100 hands  (with a fold tile {pct(sum(r['deal']['fold_tile'] for r in ss), len(ss))})"
                  f"  into riichi {sum(r['deal']['into'] == 'riichi' for r in ss) * 100 / n:4.2f}  open {sum(r['deal']['into'] == 'open' for r in ss) * 100 / n:4.2f}"
                  f"  dama {sum(r['deal']['into'] == 'dama' for r in ss) * 100 / n:4.2f}")


def cell(r: dict) -> tuple:
    """The spot a first tenpai was reached in: path, table, live winning tiles and turn, bucketed."""
    f = r["first"]
    live = 0 if f["live"] <= 2 else 1 if f["live"] <= 4 else 2 if f["live"] <= 7 else 3
    turn = 0 if f["turn"] <= 6 else 1 if f["turn"] <= 9 else 2 if f["turn"] <= 12 else 3
    table = "riichi" if f["threat"] == "riichi" else "quiet" if f["threat"] == "quiet" else "call"
    kind = "open" if not f["closed"] else "riichi" if f["riichi"] else "dama"
    return kind, table, live, turn


def expected(player_file: str, base_files: list[str], prior: float = 20) -> None:
    import math
    from collections import defaultdict

    base = [r for f in base_files for r in json.loads(Path(f).read_text())["rows"] if r["first"]]
    rows = [r for r in json.loads(Path(player_file).read_text())["rows"] if r["first"]]
    tallies = {k: defaultdict(lambda: [0, 0]) for k in ("win", "tsumo", "ron")}
    paths = {k: defaultdict(lambda: [0, 0]) for k in tallies}
    for r in base:
        c = cell(r)
        for k, hit in (("win", r["won"]), ("tsumo", r["won"] and r["tsumo"]), ("ron", r["won"] and not r["tsumo"])):
            tallies[k][c][0] += hit; tallies[k][c][1] += 1
            paths[k][c[0]][0] += hit; paths[k][c[0]][1] += 1

    def rate(k, c):
        w, n = tallies[k][c]
        pw, pn = paths[k][c[0]]
        return (w + prior * pw / pn) / (n + prior)

    print(f"== {Path(player_file).name} against {len(base)} baseline tenpai hands: wins the baseline's rate predicts for the same spots")
    for dn, ds in (("no dora", lambda r: r["hd"] == 0), ("dora", lambda r: r["hd"] >= 1)):
        for kind in ("riichi", "dama", "open", "all"):
            rs = [r for r in rows if ds(r) and (kind == "all" or cell(r)[0] == kind)]
            if not rs:
                continue
            line = f"   {dn:<8} {kind:<7} n {len(rs):4d}"
            for k, hit in (("win", lambda r: r["won"]), ("tsumo", lambda r: r["won"] and r["tsumo"]), ("ron", lambda r: r["won"] and not r["tsumo"])):
                exp = sum(rate(k, cell(r)) for r in rs)
                var = sum(rate(k, cell(r)) * (1 - rate(k, cell(r))) for r in rs)
                act = sum(1 for r in rs if hit(r))
                line += f"  {k}: expected {exp:5.1f} actual {act:3d} (z {(act - exp) / math.sqrt(var):+.2f})"
            print(line)


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "expected":
        expected(sys.argv[2], sys.argv[3:])
    else:
        report(sys.argv[2], sys.argv[3:])
