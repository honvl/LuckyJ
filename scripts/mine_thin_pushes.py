#!/usr/bin/env python3
"""The figures behind guide chapter 35: big tenpais on thin waits, pushed against a riichi.

The decisions are ``mine_tenpai_push.py``'s: the first discard of a hand where the player is not in riichi, someone else
has declared, the player holds tenpai, and every tile that keeps the tenpai is unsafe against a riichi player. The
selection is the same, so the rows match that miner's one for one; this one adds what happened after the decision:

- every tile that keeps the tenpai, with its danger, live tiles and han (``options``), and the label of the tile cut;
- the kept tenpai's winning tiles, the most a ron on them pays without a riichi (``dama_han``; 0 is a tenpai that can
  win only by tsumo unless it declares), and how each looks to the riichi player (``safety``): a winning tile that is
  genbutsu, suji, nakasuji, dead or an honor with two copies out is one the players folding against the riichi throw;
- every later discard of the hand: how many were unsafe against a riichi player, and whether the hand later left
  tenpai (a fold after the push);
- the deal-in, if any: on the decision's own tile or later, into a riichi or into someone who had not declared, and
  whether the player was still tenpai when it happened.

``report`` sets the user's pushes of big hands on thin waits (3 han or more counting a closed hand's riichi, 3 live
tiles or fewer) against LuckyJ's: results, where the deal-ins came, deal-ins on the push tile against LuckyJ's rate
for a tile of the same kind, wins by wait (an honor alone or a number), how often the least dangerous tenpai tile was
cut, Mortal's weights from the site's replays (on the tile cut and on keeping the tenpai), and how often LuckyJ's own
rates give results as poor as the user's over the same pushes (``chance``: deal-ins on the push tile drawn at LuckyJ's
rate for each tile's kind, and the points of as many of LuckyJ's pushes drawn at random). It lists the user's pushes and
folds for the cards.

usage: mine_thin_pushes.py compute MANIFEST SINCE|- ROWS_OUT.json
       mine_thin_pushes.py report ROWS_YOU.json ROWS_LJ.json OUT.json
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

SAFE = {"genbutsu", "dead", "suji", "nakasuji", "honor, 2 seen"}
THIN = {"han": 3, "live": 3}  # a big hand: 3 han or more; a thin wait: 3 live tiles or fewer
SEED, DRAWS = 1, 100000


def is_thin(r: dict) -> bool:
    return r["han"] >= THIN["han"] and r["live"] <= THIN["live"]


def game_rows(g: dict) -> list[dict]:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import DANGER, meld_snapshots, safety, site_tile, visible_counter
    from mine_open_tenpai_push import ron_value
    from tenhou_replay import base

    rows = []
    hero = g["hero_seat"]
    for log in tr.load_logs(str(ROOT / g["file"]) if not os.path.isabs(g["file"]) else g["file"]):
        game = tr.replay(log)
        p = game["players"][hero]
        indicators = game["dora_indicators"][:1]
        dset = frozenset(ws.dora_from_indicator(t) for t in indicators)
        blocks = tr.result_blocks(log[-1])
        events = game["events"]
        riichi_turn = {q: next((x["turn"] for x in events if x["seat"] == q and x["riichi"]), None) for q in range(4)}

        def labels_at(e: dict, tile: int, seats: list[int], hand: list[int]) -> list[str]:
            snap = meld_snapshots(game, e["index"] - 1)
            snap[hero] = e["melds"]
            seen = visible_counter(hand, e, game["players"], snap, indicators)
            if base(tile) in {base(x) for x in hand}:
                seen[base(tile)] -= 1
            return [safety(tile, q, e, game, seen) for q in seats]

        for e in events:
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
            best, options = (-1, -1), []
            for t, rest in keep.values():
                ws_ = tr.waits(rest, e["meld_tiles"], e["closed"])
                live = sum(max(0, 4 - visible[base(w)]) for w in ws_)
                hans = [ron_value(rest, my_melds, w, hero, game["kyoku"], dset, riichi=e["closed"]) for w in ws_]
                han = max((h for h in hans if h is not None), default=0)
                best = max(best, (live, han))
                options.append({"tile": site_tile(t), "danger": max(DANGER[lab] for lab in labels(t)), "labels": labels(t),
                                "live": live, "han": han})
            kept = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) == 0

            # the kept tenpai's winning tiles, as the riichi player's opponents see them
            waits, wait_labels, wait_live, dama_han = [], [], 0, None
            if kept:
                waits = tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])
                # what a ron pays on each winning tile without a riichi: 0 means the tenpai cannot ron dama
                dama = [ron_value(e["hand_after"], my_melds, w, hero, game["kyoku"], dset, riichi=False) for w in waits]
                dama_han = max((h for h in dama if h is not None), default=0)
                for w in waits:
                    labs = [safety(w, q, e, game, visible) for q in reached]
                    wait_labels.append(min(labs, key=lambda lab: DANGER[lab]) if all(lab in DANGER for lab in labs) else labs[0])
                    wait_live += max(0, 4 - visible[base(w)])

            # the rest of the hand
            later = [x for x in events if x["seat"] == hero and x["index"] > e["index"] and x.get("tile") is not None]
            unsafe_later, left_tenpai = 0, False
            for x in later:
                seats = [q for q in range(4) if q != hero and x["riichi_seats"][q] is not None and x["riichi_seats"][q] < x["index"]]
                if seats and x["riichi_seats"][hero] is None:
                    if any(lab not in SAFE for lab in labels_at(x, x["tile"], seats, x["hand_before"])):
                        unsafe_later += 1
                if ws.hand_shanten(x["hand_after"], x["meld_tiles"], x["closed"]) > 0:
                    left_tenpai = True
            won = any(d[0] == hero for _, d in blocks)
            dealt = [d for _, d in blocks if d[1] == hero and d[0] != hero]
            deal = None
            if dealt:
                last = ([e] + later)[-1]
                winner = dealt[0][0]
                into_riichi = last["riichi_seats"][winner] is not None and last["riichi_seats"][winner] < last["index"]
                deal = {"turn": last["turn"], "tile": site_tile(last["tile"]), "on_decision": last is e,
                        "into_riichi": into_riichi, "in_own_riichi": last["riichi_seats"][hero] is not None and last["riichi_seats"][hero] < last["index"],
                        "tenpai": ws.hand_shanten(last["hand_after"], last["meld_tiles"], last["closed"]) == 0,
                        "label": labels_at(last, last["tile"], [winner], last["hand_before"])[0] if into_riichi else None}
            rows.append({
                "game": g["uuid"], "round": game["round_name"], "closed": e["closed"], "turn": e["turn"],
                "riichi_ago": e["turn"] - min(riichi_turn[q] or e["turn"] for q in reached), "riichis": len(reached),
                "live": best[0], "han": best[1], "pushed": kept, "chased": bool(e["riichi"]),
                "tile": site_tile(e["tile"]), "danger": max(DANGER[lab] for lab in labels(e["tile"])),
                "labels": labels(e["tile"]), "options": options,
                "waits": [site_tile(w) for w in waits], "wait_labels": wait_labels, "wait_live": wait_live, "dama_han": dama_han,
                "unsafe_later": unsafe_later, "left_tenpai": left_tenpai,
                "won": won, "dealt": bool(dealt), "deal": deal,
                "delta": tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero],
                "south4": log[0][0] >= 7,
            })
            break
    return rows


def compute(manifest: str, since: str | None, out: str) -> None:
    games = json.load(open(manifest))
    if since:
        cutoff = datetime.datetime.strptime(since, "%Y-%m-%d").timestamp()
        games = [g for g in games if g["start_time"] >= cutoff]
    os.chdir(ROOT)
    with Pool(12) as pool:
        rows = [r for chunk in pool.map(game_rows, games, chunksize=4) for r in chunk]
    Path(out + ".tmp").write_text(json.dumps({"games": len(games), "rows": rows}))
    os.replace(out + ".tmp", out)
    print(f"{out}: {len(games)} games, {len(rows)} tenpai push-or-fold hands")


def pct(k: float, n: int, digits: int = 1) -> float | None:
    return round(100 * k / n, digits) if n else None


def results(rows: list[dict]) -> dict:
    n = len(rows)
    avg = lambda rs: round(sum(r["delta"] for r in rs) / len(rs)) if rs else None
    return {"hands": n, "won": pct(sum(r["won"] for r in rows), n), "dealt": pct(sum(r["dealt"] for r in rows), n),
            "points": avg(rows), "a_win": avg([r for r in rows if r["won"]]), "a_deal_in": avg([r for r in rows if r["dealt"]])}


def safe_wait(r: dict) -> bool:
    return any(lab in SAFE for lab in r["wait_labels"])


def side(rows: list[dict]) -> dict:
    thin = [r for r in rows if is_thin(r)]
    pushed = [r for r in thin if r["pushed"]]
    deals = [r["deal"] for r in pushed if r["deal"]]
    return {
        "thin": len(thin), "pushed": len(pushed), "pushed_pct": pct(len(pushed), len(thin)),
        "pushes": results(pushed), "folds": results([r for r in thin if not r["pushed"]]),
        "deal_ins": {"total": len(deals), "on_the_push": sum(d["on_decision"] for d in deals),
                     "later": sum(not d["on_decision"] for d in deals),
                     "into_the_riichi": sum(d["into_riichi"] for d in deals),
                     "into_someone_else": sum(not d["into_riichi"] for d in deals),
                     "still_tenpai": sum(d["tenpai"] for d in deals), "in_own_riichi": sum(d["in_own_riichi"] for d in deals)},
        "deal_in_rates": {"on_the_push": pct(sum(d["on_decision"] for d in deals), len(pushed)),
                          "later_into_the_riichi": pct(sum(not d["on_decision"] and d["into_riichi"] for d in deals), len(pushed)),
                          "later_into_someone_else": pct(sum(not d["on_decision"] and not d["into_riichi"] for d in deals), len(pushed))},
        "left_tenpai_later": pct(sum(r["left_tenpai"] for r in pushed), len(pushed)),
        "unsafe_later": round(sum(r["unsafe_later"] for r in pushed) / len(pushed), 2) if pushed else None,
        "wait_safe": {"share": pct(sum(safe_wait(r) for r in pushed), len(pushed)),
                      "safe": results([r for r in pushed if safe_wait(r)]),
                      "live": results([r for r in pushed if not safe_wait(r)])},
        "by_hand": {"open": results([r for r in pushed if not r["closed"]]),
                    "closed dama": results([r for r in pushed if r["closed"] and not r["chased"]]),
                    "closed riichi": results([r for r in pushed if r["chased"]])},
    }


DANGER_ORDER = {"genbutsu": 0, "dead": 0, "suji": 1, "nakasuji": 1, "honor, 2 seen": 1, "virtual nakasuji": 2, "live honor": 2,
                "live terminal": 2, "half suji": 3, "live 2-3-7-8": 3, "live 4-5-6": 4}
HONORS = {"E", "S", "W", "N", "P", "F", "C"}


def kind(r: dict) -> str:
    """The label of the tile cut against the riichi player it is most dangerous to."""
    return max(r["labels"], key=lambda lab: DANGER_ORDER.get(lab, 0))


def wait_kind(r: dict) -> str:
    return "honor" if r["waits"] and all(w in HONORS for w in r["waits"]) else "number"


def expected_on_push(mine: list[dict], theirs: list[dict]) -> dict:
    """Deal-ins on the push tile itself against LuckyJ's rate for a tile of the same kind."""
    rate = {}
    for k in {kind(r) for r in theirs}:
        s = [r for r in theirs if kind(r) == k]
        rate[k] = sum(bool(r["deal"] and r["deal"]["on_decision"]) for r in s) / len(s)
    return {"pushes": len(mine), "deal_ins": sum(bool(r["deal"] and r["deal"]["on_decision"]) for r in mine),
            "luckyj_expects": round(sum(rate.get(kind(r), 0) for r in mine), 1)}


def mortal(r: dict) -> dict | None:
    """Mortal's weights at the decision, from the site's replay: on the tile cut, and on keeping the tenpai."""
    path = ROOT / "site/replays" / f"{r['game']}.json"
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    hero = d["hero"]
    h = next((h for h in d["hands"] if h["round"] == r["round"]), None)
    if h is None:
        return None
    ais = {a["i"]: a for a in h["ai"]}
    turn, best = 0, None
    for i, x in enumerate(h["ev"]):
        if x[1] == hero and x[0] in ("t", "c", "p", "m"):
            turn += 1
        if x[0] == "d" and x[1] == hero and x[2] == r["tile"]:
            if best is None or abs(turn - r["turn"]) < abs(best[0] - r["turn"]):
                best = (turn, i)
    if best is None:
        return None
    i = best[1]
    a = ais.get(i - 1) or ais.get(i - 2) if h["ev"][i - 1][0] == "r" else ais.get(i - 1) or ais.get(i)
    if a is None:
        return None
    p = dict(a["p"])
    keep = sum(p.get(o["tile"], 0) for o in r["options"]) + p.get("riichi", 0)
    return {"cut": round(p.get(r["tile"], 0) + (p.get("riichi", 0) if r["chased"] else 0), 3), "keep_tenpai": round(keep, 3),
            "top": [[t, round(q, 3)] for t, q in sorted(a["p"], key=lambda x: -x[1])[:3]]}


def report(you_path: str, lj_path: str, out: str) -> None:
    you, lj = json.load(open(you_path)), json.load(open(lj_path))
    for r in you["rows"]:
        if is_thin(r):
            r["mortal"] = mortal(r)
    mine = [r for r in you["rows"] if is_thin(r) and r["pushed"]]
    theirs = [r for r in lj["rows"] if is_thin(r) and r["pushed"]]
    folds = [r for r in you["rows"] if is_thin(r) and not r["pushed"]]
    rated = [r for r in mine if r["mortal"]]
    on_push = [r for r in rated if r["deal"] and r["deal"]["on_decision"]]
    choice = lambda rs: [r for r in rs if len(r["options"]) > 1]
    least = lambda rs: sum(r["danger"] == min(o["danger"] for o in r["options"]) for r in choice(rs))
    others = lambda rows: [r for r in rows if r["pushed"] and not is_thin(r)]
    data = {"games": {"you": you["games"], "luckyj": lj["games"]}, "rows": {"you": len(you["rows"]), "luckyj": len(lj["rows"])},
            "you": side(you["rows"]), "luckyj": side(lj["rows"]),
            "other_pushes": {"you": results(others(you["rows"])), "luckyj": results(others(lj["rows"]))},
            "on_push_expected": {"thin": expected_on_push(mine, theirs),
                                 "other": expected_on_push(others(you["rows"]), others(lj["rows"]))},
            "wait_kinds": {who: {k: results([r for r in rs if wait_kind(r) == k]) for k in ("honor", "number")}
                           for who, rs in (("you", mine), ("luckyj", theirs))},
            "tile_choice": {"you": {"with_a_choice": len(choice(mine)), "least_dangerous": least(mine)},
                            "luckyj": {"with_a_choice": len(choice(theirs)), "least_dangerous": least(theirs)}},
            "mortal": {"pushes_rated": len(rated), "keep_tenpai": round(sum(r["mortal"]["keep_tenpai"] for r in rated) / len(rated), 3),
                       "on_push_deal_ins": len(on_push),
                       "on_push_backed": sum(r["mortal"]["keep_tenpai"] >= 0.75 for r in on_push),
                       "other_tile_preferred": sum(r["mortal"]["cut"] <= 0.2 and r["mortal"]["keep_tenpai"] >= 0.8 for r in rated),
                       "folds_rated": sum(1 for r in folds if r["mortal"]),
                       "folds_mortal_keeps": sum(1 for r in folds if r["mortal"] and r["mortal"]["keep_tenpai"] > 0.5)},
            "your_pushes": [{k: r[k] for k in ("game", "round", "turn", "closed", "chased", "live", "han", "tile", "danger", "labels", "options", "waits",
                                               "wait_labels", "unsafe_later", "left_tenpai", "mortal", "won", "dealt", "deal", "delta")}
                            for r in sorted(mine, key=lambda r: (r["game"], r["round"]))],
            "your_folds": [{k: r[k] for k in ("game", "round", "turn", "closed", "live", "han", "tile", "labels", "options", "mortal",
                                              "won", "dealt", "delta")} for r in sorted(folds, key=lambda r: (r["game"], r["round"]))]}
    # how often LuckyJ's own rates give results as poor as yours, over the same number of pushes
    import random
    rng = random.Random(SEED)
    rate = {}
    for k in {kind(r) for r in theirs}:
        s = [r for r in theirs if kind(r) == k]
        rate[k] = sum(bool(r["deal"] and r["deal"]["on_decision"]) for r in s) / len(s)
    seen_deals = sum(bool(r["deal"] and r["deal"]["on_decision"]) for r in mine)
    seen_points = sum(r["delta"] for r in mine)
    deals = points = 0
    for _ in range(DRAWS):
        deals += sum(rng.random() < rate.get(kind(r), 0) for r in mine) >= seen_deals
        points += sum(rng.choice(theirs)["delta"] for _ in mine) <= seen_points
    data["chance"] = {"draws": DRAWS, "on_push_deal_ins": pct(deals, DRAWS), "points": pct(points, DRAWS)}
    one = [r for r in lj["rows"] if r["han"] >= THIN["han"] and r["live"] <= 1]
    data["luckyj_one_live"] = {"spots": len(one), "pushed": sum(r["pushed"] for r in one)}
    Path(out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(sys.argv[2], None if sys.argv[3] == "-" else sys.argv[3], sys.argv[4])
    else:
        report(*sys.argv[2:5])
