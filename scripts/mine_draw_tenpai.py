#!/usr/bin/env python3
"""The figures behind guide chapter 52: the 58 games of the climb toward Celestial, the calls, the safe tiles, and tenpai
at the draw.

The user's 58 games from 11 to 18 November (a climb of 32 games, then 26 flat ones) against the 223 games between the
guide's first commit and chapter 51, LuckyJ's 1,079 Tokujou games and every other seat at both sets of tables:

- places, rank points and where a game's points came from (wins, deal-ins, tsumo paid, draws);
- the hand mix: hands opened, riichi, closed tenpai and how often a closed tenpai with a yaku was declared, with the
  net points of open and closed hands, and Mortal's share of the same call and riichi chances;
- the genbutsu held at the first discard after a riichi, with the hand not tenpai, closed and open;
- tenpai at the exhaustive draw: how often, what the draw paid, with and without a riichi on the table;
- the calls made from the 12th turn to reach tenpai, and the live tiles pushed from the 13th turn at 1-shanten against a
  riichi, by how many unseen tiles would make tenpai, with Mortal's rating of the pushed tile.

usage: mine_draw_tenpai.py OUT.json
"""

from __future__ import annotations

import json
import math
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import mine_climb_check as cc  # noqa: E402
import mine_costly_run as mc  # noqa: E402
import mine_rank_drain as rd  # noqa: E402
import mine_recent_run as rr  # noqa: E402

REPLAYS = ROOT / "site" / "replays"
GUIDE_GAMES = 80  # games of 2026 before the guide's first commit
CH51_GAMES = 303  # games in the manifest when chapter 51 went up
CLIMB = 32  # the first 32 of the new games: 5,620 to 8,061 rank points
LATE_CALL = 12
LATE_PUSH = 13
FEW_OUTS = 8
CALLS = ("pon", "chi", "kan")


def pct(k: float, n: int, digits: int = 1) -> float:
    return rr.pct(k, n, digits)


def mean(xs) -> float:
    xs = list(xs)
    return float(np.mean(xs)) if xs else 0.0


def safe_set(e: dict, events: list[dict], q: int) -> set[int]:
    from tenhou_replay import base

    out = {base(t) for t in e["rivers"][q]}
    r = e["riichi_seats"][q]
    out |= {base(x["tile"]) for x in events[r + 1: e["index"]] if x.get("tile") is not None}
    return out


def log_rows(g: dict) -> dict:
    """From one game's logs: discards under a riichi (every seat), late calls (every seat), late 1-shanten discards of the hero."""
    import review_win_speed as ws
    import tenhou_replay as tr
    from tenhou_replay import base

    uid, hs = g["uuid"].split("#")[0], g["hero_seat"]
    under, calls, late = [], [], []
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        events, res = game["events"], game["result"]
        delta = tr.result_deltas(res)
        kind = res[0] if res else None
        winners, dealers = set(), set()
        for _d, det in tr.result_blocks(res):
            if kind == "和了":
                winners.add(det[0])
                if det[1] != det[0]:
                    dealers.add(det[1])
        paid = {s: -delta[s] for s in dealers}
        last = {e["seat"]: e["index"] for e in events if e.get("tile") is not None}
        seen, prev = set(), {}
        for e in events:
            s = e["seat"]
            if e["called"] and e["called"]["kind"] != "a" and s in prev and e["turn"] >= LATE_CALL:
                p = prev[s]
                before = ws.hand_shanten(p["hand_after"], p["meld_tiles"], p["closed"])
                after = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
                if before > 0:
                    calls.append({"li": li, "hero": s == hs, "after": after, "won": s in winners, "dealt": s in dealers, "draw": kind == "流局" and len(res) > 1, "delta": delta[s]})
            if e.get("tile") is not None:
                prev[s] = e
            if e.get("tile") is None or e["riichi"] or (e["riichi_seats"][s] is not None and e["riichi_seats"][s] < e["index"]):
                continue
            reached = [q for q in range(4) if q != s and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            if not reached:
                continue
            refs = [safe_set(e, events, q) for q in reached]
            after = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
            safe = all(base(e["tile"]) in x for x in refs)
            first = (li, s) not in seen
            seen.add((li, s))
            under.append({"li": li, "hero": s == hs, "open": not e["closed"], "genbutsu": sum(1 for t in e["hand_before"] if all(base(t) in x for x in refs)),
                          "after": after, "safe": safe, "first": first, "paid": paid.get(s, 0) if last[s] == e["index"] else 0})
            if s == hs and e["turn"] >= LATE_PUSH and after == 1:
                snap = ws.meld_snapshots(game, e["index"])
                vis = ws.visible_counter(e["hand_after"], e["rivers"], snap, game["dora_indicators"][:1], game["players"])
                _sh, outs, _kinds = ws.acceptance(e["hand_after"], e["meld_tiles"], e["closed"], vis)
                late.append({"li": li, "turn": e["turn"], "safe": safe, "outs": outs, "open": not e["closed"]})
    return {"game": uid, "under": under, "calls": calls, "late": late}


def replay_rows(g: dict) -> dict:
    """From the site's replay: Mortal on each call chance and on the first riichi chance of each hand."""
    d = json.loads((REPLAYS / f"{g['uuid']}.json").read_text())
    calls, riichi = [], []
    for h in d["hands"]:
        for a in h["ai"]:
            p = dict(a["p"])
            if "pass" in p and any(k.startswith(CALLS) for k in p):
                calls.append({"mortal": sum(v for k, v in p.items() if k != "pass"), "called": a["you"] != "pass"})
        a = next((a for a in h["ai"] if "riichi" in dict(a["p"])), None)
        if a:
            riichi.append({"mortal": dict(a["p"])["riichi"], "declared": a["you"] == "riichi"})
    return {"calls": calls, "riichi": riichi}


def push_rating(job) -> list[dict]:
    """Mortal's rating of the first live tile the hero pushed in each late 1-shanten hand."""
    import tenhou_replay as tr

    g, keys = job
    hero = g["hero_seat"]
    rep = json.loads((REPLAYS / f"{g['uuid']}.json").read_text())
    logs = tr.load_logs(str(ROOT / g["file"]))
    out = []
    for li, turn in keys:
        game, h = tr.replay(logs[li]), rep["hands"][li]
        ev, ais = h["ev"], {a["i"]: a for a in h["ai"]}
        mine = [e for e in game["events"] if e["seat"] == hero and e.get("tile") is not None]
        dis = [i for i, x in enumerate(ev) if x[0] == "d" and x[1] == hero]
        if len(mine) != len(dis):
            continue
        for di, e in zip(dis, mine):
            if e["turn"] == turn and ais.get(di - 1):
                a = ais[di - 1]
                out.append({"game": g["uuid"], "li": li, "mortal": dict(a["p"]).get(a["you"], 0.0)})
                break
    return out


def outcome(hs: list[dict]) -> dict:
    n = len(hs)
    return {"hands": n, "draw_tenpai_pct": pct(sum(1 for h in hs if h["result_kind"] == "流局" and h["draw_tenpai"]), n), "won_pct": pct(sum(h["won"] for h in hs), n),
            "dealt_in_pct": pct(sum(h["dealt_in"] for h in hs), n), "net": round(mean(h["net"] for h in hs))}


def main() -> None:
    out_path = sys.argv[1]
    per_1000 = json.loads(rd.THIN.read_text())["cost"]["rank_points_per_1000_points"]
    manifest = sorted([g for g in json.loads(cc.MANIFEST.read_text(encoding="utf-8")) if g["date"] >= cc.SINCE], key=lambda g: g["start_time"])
    lj_manifest = [g for g in json.loads(cc.LJ_MANIFEST.read_text(encoding="utf-8")) if g["mode"] == "tenhou-tokujou"]
    n = len(manifest)
    windows = {"before": (CH51_GAMES - 223, CH51_GAMES), "climb": (CH51_GAMES, CH51_GAMES + CLIMB), "recent": (CH51_GAMES + CLIMB, n), "new": (CH51_GAMES, n), "last_10": (n - 10, n)}
    assert windows["before"][0] == GUIDE_GAMES
    order = {g["uuid"].split("#")[0]: i for i, g in enumerate(manifest)}
    in_window = lambda game, w: windows[w][0] <= order[game] < windows[w][1]  # noqa: E731
    recs = {r[0]: r for r in json.loads(cc.AMAE.read_text())["records"]}
    points = lambda g: next(p for p in recs[g["uuid"]][4] if p[0] == cc.ACCOUNT)[4]  # noqa: E731

    # --- results ----------------------------------------------------------------------------------------------
    results = {}
    for w, (lo, hi) in windows.items():
        sel = manifest[lo:hi]
        pl = [g["placement"] for g in sel]
        results[w] = {"games": len(sel), "places": [pl.count(i) for i in (1, 2, 3, 4)], "third_pct": pct(pl.count(3), len(sel)),
                      "rank_points": sum(points(g) for g in sel), "rank_points_a_game": round(sum(points(g) for g in sel) / len(sel), 1)}
    rank = cc.rank_path()
    path, now = [], rank["now"]["points"] - sum(points(g) for g in manifest[CH51_GAMES:])
    start = now
    for g in manifest[CH51_GAMES:]:
        now += points(g)
        path.append(now)
    third_rate = results["before"]["places"][2] / results["before"]["games"]
    k, m = results["new"]["places"][2], results["new"]["games"]
    results["thirds"] = {"expected": round(m * third_rate, 1), "p_at_least": round(sum(math.comb(m, i) * third_rate ** i * (1 - third_rate) ** (m - i) for i in range(k, m + 1)), 3)}
    results["rank"] = {"start": start, "after_climb": path[CLIMB - 1], "now": path[-1], "best": max(path)}

    # --- hands ------------------------------------------------------------------------------------------------
    rows = mc.hand_rows(manifest, "me")
    rows_lj = mc.hand_rows(lj_manifest, "lj")
    hero = {g["uuid"].split("#")[0]: g["hero_seat"] for g in manifest}
    hero_lj = {g["uuid"].split("#")[0]: g["hero_seat"] for g in lj_manifest}
    mine = [r for r in rows if r["seat"] == hero[r["game"]]]
    groups = {w: [r for r in mine if in_window(r["game"], w)] for w in ("before", "climb", "recent", "new")}
    groups["luckyj"] = [r for r in rows_lj if r["seat"] == hero_lj[r["game"]]]
    groups["jade_human"] = [r for r in rows if r["seat"] != hero[r["game"]] and order[r["game"]] >= GUIDE_GAMES]
    groups["tokujou_human"] = [r for r in rows_lj if r["seat"] != hero_lj[r["game"]]]

    style = {}
    for name, R in groups.items():
        h = len(R)
        op, cl = [r for r in R if r["open"]], [r for r in R if not r["open"]]
        wins = [r for r in R if r["won"]]
        closed = [r for r in R if r["first_closed_tenpai"] and not r["first_closed_tenpai"]["yakuless"]]
        style[name] = {"hands": h, "open_pct": pct(len(op), h), "riichi_pct": pct(sum(r["riichi_turn"] is not None for r in R), h), "won_pct": pct(len(wins), h),
                       "average_win": round(mean(r["win_pts"] for r in wins)), "open_net": round(mean(r["net"] for r in op)), "closed_net": round(mean(r["net"] for r in cl)),
                       "closed_tenpai_pct": pct(sum(1 for r in R if r["first_closed_tenpai"]), h),
                       "with_yaku_declared_pct": pct(sum(1 for r in closed if r["first_closed_tenpai"]["declared"]), len(closed)), "with_yaku_closed_tenpais": len(closed)}

    sg = rd.seat_games(rows, hero)
    sources = {}
    for w in ("before", "climb", "recent", "new"):
        c = rd.components(sg, lambda key, x, w=w: x["hero"] and in_window(key[0], w))
        sources[w] = {"won": c["win"], "deal_ins": -c["deal_ins"], "tsumo_paid": -c["tsumo_paid"], "draws": c["draw"], "net": c["net"]}

    # --- the logs: safe tiles, draws, late calls, late pushes -------------------------------------------------------------
    with Pool(10) as pool:
        mine_logs = pool.map(log_rows, manifest, chunksize=4)
        lj_logs = pool.map(log_rows, lj_manifest, chunksize=8)
        mine_replays = pool.map(replay_rows, manifest[GUIDE_GAMES:], chunksize=4)

    def logs_for(name: str) -> tuple[list[dict], bool, int]:
        if name in ("luckyj", "tokujou_human"):
            return lj_logs, name == "luckyj", len(lj_logs) * (1 if name == "luckyj" else 3)
        if name == "jade_human":
            sel = mine_logs[GUIDE_GAMES:]
            return sel, False, 3 * len(sel)
        lo, hi = windows[name]
        return mine_logs[lo:hi], True, hi - lo

    safe_tiles = {}
    for name in ("before", "climb", "recent", "new", "luckyj", "jade_human", "tokujou_human"):
        logs, is_hero, seats = logs_for(name)
        first = [u for g in logs for u in g["under"] if u["hero"] == is_hero and u["first"] and u["after"] > 0]
        allu = [u for g in logs for u in g["under"] if u["hero"] == is_hero]
        safe_tiles[name] = {f"{k}_held_pct": pct(sum(u["genbutsu"] > 0 for u in first if u["open"] == (k == "open")), sum(1 for u in first if u["open"] == (k == "open"))) for k in ("closed", "open")}
        for k in ("closed", "open"):
            sel = [u for u in first if u["open"] == (k == "open")]
            safe_tiles[name][f"{k}_first_discards"] = len(sel)
            safe_tiles[name][f"{k}_held"] = sum(u["genbutsu"] > 0 for u in sel)
        safe_tiles[name]["deal_in_points_under_riichi_a_game"] = round(sum(u["paid"] for u in allu) / seats)
    new_open_bare = [(g["game"], u) for g in mine_logs[CH51_GAMES:] for u in g["under"] if u["hero"] and u["first"] and u["after"] > 0 and u["open"] and u["genbutsu"] == 0]
    safe_tiles["new_open_without_genbutsu"] = {"first_discards": len(new_open_bare), "dealt_in_that_hand": sum(1 for game, u in new_open_bare if next(r for r in mine if r["game"] == game and r["li"] == u["li"])["dealt_in"])}

    # draws
    hand_of = {(r["game"], r["li"]): r for r in mine} | {(r["game"], r["li"]): r for r in groups["luckyj"]}
    faced = {}
    for logs, lj in ((mine_logs, False), (lj_logs, True)):
        for g in logs:
            for u in g["under"]:
                faced[(g["game"], u["li"], u["hero"])] = True
    draws = {}
    for name in ("before", "climb", "recent", "new", "luckyj", "jade_human", "tokujou_human"):
        R = groups[name]
        is_hero = name not in ("jade_human", "tokujou_human")
        D = [r for r in R if r["result_kind"] == "流局" and r["draw_tenpai"] is not None]
        games = len({r["game"] for r in R}) * (1 if is_hero else 3)
        out = {"draws": len(D), "tenpai_pct": pct(sum(1 for r in D if r["draw_tenpai"]), len(D)), "draw_points_a_game": round(sum(r["draw_pts"] for r in R) / games)}
        for k, sel in (("riichi_out", lambda r: faced.get((r["game"], r["li"], is_hero), False)), ("no_riichi", lambda r: not faced.get((r["game"], r["li"], is_hero), False))):
            X = [r for r in D if sel(r)]
            out[k] = {"draws": len(X), "tenpai_pct": pct(sum(1 for r in X if r["draw_tenpai"]), len(X))}
        out["riichi_out_share_pct"] = pct(out["riichi_out"]["draws"], len(D))
        draws[name] = out

    # late calls to tenpai
    late_calls = {}
    for name in ("before", "new", "luckyj", "jade_human"):
        logs, is_hero, seats = logs_for(name)
        firsts = {}
        for g in logs:
            for c in g["calls"]:
                if c["hero"] == is_hero:
                    firsts.setdefault((g["game"], c["li"], is_hero), c)
        T = [c for c in firsts.values() if c["after"] == 0]
        late_calls[name] = {"a_game": round(len(T) / seats, 2), "calls": len(T), "won_pct": pct(sum(c["won"] for c in T), len(T)), "dealt_pct": pct(sum(c["dealt"] for c in T), len(T)),
                            "draw_tenpai_pct": pct(sum(1 for c in T if c["draw"] and c["delta"] > 0), len(T)), "net": round(mean(c["delta"] for c in T))}

    # late pushes at 1-shanten against a riichi
    pushes = {}
    since = mine_logs[GUIDE_GAMES:]
    for name, logs, games in (("you", since, len(since)), ("luckyj", lj_logs, len(lj_logs))):
        per = {}
        for g in logs:
            for x in g["late"]:
                per.setdefault((g["game"], x["li"]), []).append(x)
        out = {"games": games}
        for kind, sel in (("pushed", lambda xs: any(not x["safe"] for x in xs)), ("safe_only", lambda xs: all(x["safe"] for x in xs))):
            keys = [k for k, xs in per.items() if sel(xs) and k in hand_of]
            first_outs = {k: next((x for x in per[k] if not x["safe"]), per[k][0])["outs"] for k in keys}
            out[kind] = dict(outcome([hand_of[k] for k in keys]), a_game=round(len(keys) / games, 2), median_outs=float(np.median(list(first_outs.values()))))
            for band, test in (("few_outs", lambda o: o < FEW_OUTS), ("more_outs", lambda o: o >= FEW_OUTS)):
                ks = [k for k in keys if test(first_outs[k])]
                out[kind][band] = dict(outcome([hand_of[k] for k in ks]), a_game=round(len(ks) / games, 2))
        pushes[name] = out
    jobs = []
    for gi, g in enumerate(manifest):
        if gi < GUIDE_GAMES:
            continue
        first = {}
        for x in mine_logs[gi]["late"]:
            if not x["safe"]:
                first.setdefault(x["li"], x["turn"])
        if first:
            jobs.append((g, sorted(first.items())))
    with Pool(10) as pool:
        rated = [x for chunk in pool.map(push_rating, jobs) for x in chunk]
    pushes["you"]["mortal"] = {"rated": len(rated), "under_25": sum(1 for x in rated if x["mortal"] < 0.25), "at_least_25": sum(1 for x in rated if x["mortal"] >= 0.25)}

    # --- Mortal on calls and riichi -------------------------------------------------------------------------------
    mortal = {}
    for w in ("before", "climb", "recent", "new"):
        lo, hi = windows[w]
        sel = mine_replays[lo - GUIDE_GAMES: hi - GUIDE_GAMES]
        cs = [c for g in sel for c in g["calls"]]
        rs = [r for g in sel for r in g["riichi"]]
        mortal[w] = {"call_chances_a_game": round(len(cs) / len(sel), 2), "you_call_pct": pct(sum(c["called"] for c in cs), len(cs)), "mortal_calls_pct": pct(sum(c["mortal"] for c in cs), len(cs)),
                     "riichi_chances": len(rs), "you_declare_pct": pct(sum(r["declared"] for r in rs), len(rs)), "mortal_declares_pct": pct(sum(r["mortal"] for r in rs), len(rs))}

    out = {"windows": windows, "rank_points_per_1000_points": per_1000, "results": results, "sources": sources, "style": style, "mortal": mortal,
           "safe_tiles": safe_tiles, "draws": draws, "late_calls": late_calls, "late_pushes": pushes}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
