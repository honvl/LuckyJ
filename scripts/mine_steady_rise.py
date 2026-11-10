#!/usr/bin/env python3
"""The figures behind guide chapter 51: why the rank is stuck and what a steady rise takes.

The 61 games from 23 October 22:53 to 10 November, and the 223 games since the guide began, for the question "how do I
rise consistently":

- the places and rank points of the 61 games, and chapter 50's check on them (hands dealt 4-shanten or worse);
- the pace since the guide beside the other three players at those tables, LuckyJ's Tokujou games and the humans at its
  tables, all under the Saint 3 Jade formula, and the chance of being ahead after 50, 100 and 200 games at a given pace;
- where a game's points come from (wins, deal-ins, tsumo paid, the rest) as an edge over the table, yours and LuckyJ's;
- the tiles thrown at a riichi from a hand that is not tenpai, for every seat of both corpora: how many are not
  genbutsu, how often they deal in and what they cost a game;
- every discard since the guide with Mortal's rating of it: how often a tile Mortal rates under 25% deals in beside one
  it accepts, and what each deal-in class is worth if its points are handed back on the recorded final scores;
- the deal-ins on a tile Mortal rated under 25%, one by one: the hand's distance from tenpai after the cut and after
  Mortal's tile, whether Mortal's tile was a genbutsu, whether it would have dealt in too, and the replay turn.

usage: mine_steady_rise.py OUT.json
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from collections import Counter
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
import mine_run_update as ru  # noqa: E402

GUIDE = "2026-09-22 14:17"  # the first commit of the guide
RUN_FROM = "2026-10-19 20:00"  # chapter 48's ten games and chapter 50's fifteen
NEW_FROM = "2026-10-23 20:00"  # after the 23 October 18:31 game, before the 22:53 one
PEAK = datetime.datetime(2026, 10, 1, 22, 21).timestamp()
REPLAYS = ROOT / "site" / "replays"
LOW = 0.25
LATE = 15
PACES = (5, 11, 17, 20)
HONOR = {"E": 41, "S": 42, "W": 43, "N": 44, "P": 45, "F": 46, "C": 47}
NOT_A_TILE = ("riichi", "kan", "tsumo", "pass", "ryukyoku")


def code(tile: str) -> int:
    """A replay tile name ('5mr', '9p', 'F') as the log's two-digit code, red fives folded into the five."""
    tile = tile[:-1] if len(tile) == 3 and tile.endswith("r") else tile
    return HONOR[tile] if tile in HONOR else {"m": 10, "p": 20, "s": 30}[tile[1]] + int(tile[0])


def stamp(text: str) -> float:
    return datetime.datetime.strptime(text, "%Y-%m-%d %H:%M").timestamp()


def chance_ahead(pace: float, games: int, sd: float) -> float:
    """The chance that ``games`` games at ``pace`` rank points a game end above where they began."""
    return round(100 * 0.5 * (1 + math.erf(pace * math.sqrt(games) / sd / math.sqrt(2))), 0)


def safe_against(e: dict, events: list[dict], q: int) -> set[int]:
    """The tiles that cannot deal into seat ``q``: its river, and after its riichi every tile thrown since."""
    from tenhou_replay import base

    out = {base(t) for t in e["rivers"][q]}
    r = e["riichi_seats"][q]
    if r is not None and r < e["index"]:
        out |= {base(x["tile"]) for x in events[r + 1: e["index"]] if x.get("tile") is not None}
    return out


def threat_rows(g: dict) -> list[tuple]:
    """Every discard of every seat made with another seat's riichi on the table or two calls showing.

    (hero, riichis out, most calls of another seat, shanten after the cut, genbutsu, points paid on this tile)
    """
    import review_win_speed as ws
    import tenhou_replay as tr
    from tenhou_replay import base

    out = []
    for log in tr.load_logs(str(ROOT / g["file"])):
        game = tr.replay(log)
        events, res = game["events"], game["result"]
        paid: dict[int, int] = {}
        if res and res[0] == "和了":
            for j in range(1, len(res) - 1, 2):
                deltas, detail = res[j], res[j + 1]
                if detail[0] != detail[1]:
                    paid[detail[1]] = paid.get(detail[1], 0) - deltas[detail[1]]
        last = {e["seat"]: e["index"] for e in events if e.get("tile") is not None}
        for e in events:
            s = e["seat"]
            if e.get("tile") is None or e["riichi"] or (e["riichi_seats"][s] is not None and e["riichi_seats"][s] < e["index"]):
                continue
            reached = [q for q in range(4) if q != s and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            calls = max(e["meld_counts"][q] for q in range(4) if q != s)
            if not reached and calls < 2:
                continue
            after = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
            safe = all(base(e["tile"]) in safe_against(e, events, q) for q in reached) if reached else None
            out.append((s == g["hero_seat"], len(reached), calls, after, safe, paid.get(s, 0) if last[s] == e["index"] else 0))
    return out


def live_tile_table(games: list[list[tuple]], hero: bool) -> dict:
    """Per seat-game: the throws at a riichi from a hand not tenpai, the ones that were not genbutsu, and their cost."""
    rows = [r for g in games for r in g if r[0] == hero]
    seats = len(games) * (1 if hero else 3)

    def line(sel: list[tuple]) -> dict:
        n, hits, pts = len(sel), sum(1 for r in sel if r[5]), sum(r[5] for r in sel)
        return {"throws": n, "a_game": round(n / seats, 2), "deal_ins": hits, "deal_in_pct": rr.pct(hits, n, 2), "points_a_throw": round(pts / n) if n else 0, "points_a_game": round(pts / seats)}

    far = [r for r in rows if r[1] >= 1 and r[3] > 0]
    live = [r for r in far if not r[4]]
    return {"seat_games": seats, "not_tenpai_at_a_riichi": {"throws_a_game": round(len(far) / seats, 2), "live_pct": rr.pct(len(live), len(far)), "live": line(live)},
            "tenpai_at_a_riichi_live": line([r for r in rows if r[1] >= 1 and r[3] == 0 and not r[4]]),
            "not_tenpai_at_two_calls": line([r for r in rows if r[1] == 0 and r[2] >= 2 and r[3] > 0])}


def discard_rows(g: dict) -> list[dict]:
    """Each of the user's discards before their own riichi, with Mortal's rating of it and whether it dealt in."""
    import review_win_speed as ws
    import tenhou_replay as tr
    from tenhou_replay import base

    hero, out = g["hero_seat"], []
    rep = json.loads((REPLAYS / f"{g['uuid']}.json").read_text())
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game, h = tr.replay(log), rep["hands"][li]
        assert h["round"] == game["round_name"], (g["uuid"], h["round"])
        ev, ais = h["ev"], {a["i"]: a for a in h["ai"]}
        mine = [i for i, x in enumerate(ev) if x[0] == "d" and x[1] == hero]
        logged = [e for e in game["events"] if e["seat"] == hero and e.get("tile") is not None]
        if len(mine) != len(logged):
            continue
        paid = 0
        if h["end"]["kind"] == "win":
            paid = sum(-w["deltas"][hero] for w in h["end"]["wins"] if w["from"] == hero and w["seat"] != hero)
        for k, (di, e) in enumerate(zip(mine, logged)):
            a = ais.get(di - 1)
            if a is None or ev[di - 1][0] == "r" or (e["riichi_seats"][hero] is not None and e["riichi_seats"][hero] < e["index"]):
                continue
            reached = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            out.append({"mortal": dict(a["p"]).get(a["you"], 0.0), "after": ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]), "riichi": len(reached),
                        "safe": all(base(e["tile"]) in safe_against(e, game["events"], q) for q in reached) if reached else None,
                        "paid": paid if k == len(mine) - 1 else 0})
    return out


def marker(rows: list[dict], games: int, per_1000: float) -> dict:
    """How often a tile Mortal rates under 25% deals in, beside a tile it accepts, from hands not tenpai after the cut."""
    def line(sel: list[dict]) -> dict:
        n, hits, pts = len(sel), sum(1 for r in sel if r["paid"]), sum(r["paid"] for r in sel)
        return {"throws": n, "a_game": round(n / games, 2), "deal_ins": hits, "deal_in_pct": rr.pct(hits, n, 2), "points": pts, "points_a_throw": round(pts / n, 1) if n else 0}

    far = [r for r in rows if r["after"] > 0]
    low, ok = [r for r in far if r["mortal"] < LOW], [r for r in far if r["mortal"] >= LOW]
    out = {"not_tenpai": {"disliked": line(low), "accepted": line(ok)}}
    live = [r for r in far if r["riichi"] and not r["safe"]]
    out["live_at_a_riichi"] = {"disliked": line([r for r in live if r["mortal"] < LOW]), "accepted": line([r for r in live if r["mortal"] >= LOW])}
    # if the disliked throws had cost what the accepted ones cost, per throw
    spare = sum(r["paid"] for r in low) - len(low) * sum(r["paid"] for r in ok) / len(ok)
    out["at_the_accepted_cost"] = {"points_a_game": round(spare / games), "rank_points_a_game": round(spare / games * per_1000 / 1000, 1)}
    return out


def levers(games: list[dict], replay_index: dict) -> tuple[dict, list[dict]]:
    """Each deal-in class, and the fourths and rank points if its points went back on the recorded final scores."""
    n = len(games)
    deals, _ = mc.deal_ins_and_riichis([replay_index[g["uuid"]] for g in games])
    winners: dict[str, list] = {}
    for g in games:
        d = json.loads((REPLAYS / f"{g['uuid']}.json").read_text())
        winners[g["uuid"]] = [(h["round"], -w["deltas"][d["hero"]], w["seat"]) for h in d["hands"] if h["end"]["kind"] == "win"
                              for w in h["end"]["wins"] if w["from"] == d["hero"] and w["seat"] != d["hero"]]
    for d in deals:
        d["winner"] = next(x[2] for x in winners[d["game"]] if x[0] == d["round"] and x[1] == d["paid"])
        low = d["mortal"] is not None and d["mortal"] < LOW
        d["class"] = ("cut_disliked" if low else "cut_accepted") if d["kind"] == "cut" else ("riichi_disliked" if low else "riichi_accepted")

    def handed_back(pick) -> tuple[int, float]:
        fourths = total = 0
        for g in games:
            s, h = list(g["final_scores"]), g["hero_seat"]
            for d in deals:
                if d["game"] == g["uuid"] and pick(d):
                    s[h] += d["paid"]
                    s[d["winner"]] -= d["paid"]
            place = rd.places_of(s)[h]
            fourths += place == 4
            total += rd.rank_points(s[h], place)
        return fourths, total / n

    f0, r0 = handed_back(lambda d: False)
    out = {"games": n, "deal_ins": len(deals), "a_game": round(len(deals) / n, 2), "points_a_game": round(sum(d["paid"] for d in deals) / n), "fourths": f0, "classes": {}}
    for name in ("cut_disliked", "cut_accepted", "riichi_disliked", "riichi_accepted"):
        ds = [d for d in deals if d["class"] == name]
        f, r = handed_back(lambda d: d["class"] == name)
        out["classes"][name] = {"deal_ins": len(ds), "a_game": round(len(ds) / n, 2), "points": sum(d["paid"] for d in ds), "points_a_game": round(sum(d["paid"] for d in ds) / n),
                                "average": round(float(np.mean([d["paid"] for d in ds]))), "fourths_handed_back": f, "rank_points_a_game_handed_back": round(r - r0, 1)}
    return out, deals


def cut_cases(games: list[dict], deals: list[dict]) -> list[dict]:
    """The deal-ins on a tile Mortal rated under 25%: what the hand was, and what Mortal's tile would have done."""
    import review_win_speed as ws
    import tenhou_replay as tr
    from tenhou_replay import base

    by_game = {g["uuid"]: g for g in games}
    turns = {(r["game"], r["round"], r["paid"]): r["turn"] for r in ru.deal_in_rows(games)}
    out = []
    for d in [d for d in deals if d["class"] == "cut_disliked"]:
        g = by_game[d["game"]]
        hero = g["hero_seat"]
        rep = json.loads((REPLAYS / f"{d['game']}.json").read_text())
        h = next(x for x in rep["hands"] if x["round"] == d["round"])
        ev = h["ev"]
        last = max(i for i, x in enumerate(ev) if x[0] == "d" and x[1] == hero)
        ai = next(a for a in h["ai"] if a["i"] in (last - 1, last))
        top = ai["p"][0][0]
        win = next(w for w in h["end"]["wins"] if w["from"] == hero and w["seat"] == d["winner"])
        yaku = [y[0] for y in win["yaku"]]
        called = any(x[0] in ("c", "p", "m") and x[1] == d["winner"] for x in ev[:last])
        into = "riichi" if "riichi" in yaku or "double riichi" in yaku else "caller" if called else "dama"
        game = next(x for x in (tr.replay(log) for log in tr.load_logs(str(ROOT / g["file"]))) if x["round_name"] == d["round"])
        e = [x for x in game["events"] if x["seat"] == hero and x.get("tile") is not None][-1]
        hb = e["hand_before"]
        without = lambda b: min(ws.hand_shanten(hb[:k] + hb[k + 1:], e["meld_tiles"], e["closed"]) for k in range(len(hb)) if base(hb[k]) == b)  # noqa: E731
        yours = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
        best = min(ws.hand_shanten(hb[:k] + hb[k + 1:], e["meld_tiles"], e["closed"]) for k in range(len(hb)))
        a_tile = top not in NOT_A_TILE
        mortals = without(code(top)) if a_tile else best
        ref = safe_against(e, game["events"], d["winner"])
        also = False
        if a_tile:
            for q in range(4):
                prev = [x for x in game["events"] if x["seat"] == q and x["index"] < e["index"] and x.get("tile") is not None]
                if q == hero or not prev:
                    continue
                waits = {base(t) for t in tr.waits(prev[-1]["hand_after"], prev[-1]["meld_tiles"], prev[-1]["closed"])}
                also = also or (code(top) in waits and code(top) not in {base(t) for t in e["rivers"][q]})
        out.append({"game": d["game"], "round": d["round"], "turn": turns[(d["game"], d["round"], d["paid"])], "tile": d["tile"], "mortal": round(d["mortal"], 3), "mortal_tile": top,
                    "mortal_tile_pct": round(100 * ai["p"][0][1], 1), "paid": d["paid"], "value": win["value"], "into": into,
                    "a_riichi_was_out": any(x[0] == "r" and x[1] != hero for x in ev[:last]), "shanten": yours, "shanten_mortal": mortals,
                    "mortal_tile_genbutsu": a_tile and code(top) in ref, "held_a_genbutsu": any(base(x) in ref for x in hb), "mortal_tile_deals_in": also})
    return out


def cut_summary(cases: list[dict]) -> dict:
    far = [c for c in cases if c["shanten"] > 0]
    late = [c for c in far if c["turn"] >= LATE]
    into = Counter(c["into"] for c in cases)
    return {"count": len(cases), "points": sum(c["paid"] for c in cases), "not_tenpai": len(far), "one_shanten": sum(c["shanten"] == 1 for c in cases),
            "two_shanten_or_worse": sum(c["shanten"] >= 2 for c in cases), "mortal_as_close_or_closer": sum(c["shanten_mortal"] <= c["shanten"] for c in cases),
            "mortal_gave_up_distance": sum(c["shanten_mortal"] > c["shanten"] for c in cases), "mortal_tile_genbutsu": sum(c["mortal_tile_genbutsu"] for c in cases),
            "held_a_genbutsu": sum(c["held_a_genbutsu"] for c in cases), "mortal_tile_deals_in": sum(c["mortal_tile_deals_in"] for c in cases),
            "into": {k: {"count": into[k], "points": sum(c["paid"] for c in cases if c["into"] == k)} for k in ("riichi", "caller", "dama")},
            "late_not_tenpai": {"from_turn": LATE, "count": len(late), "points": sum(c["paid"] for c in late)},
            "average_turn": round(float(np.mean([c["turn"] for c in cases])), 1)}


def main() -> None:
    out_path = sys.argv[1]
    per_1000 = json.loads(rd.THIN.read_text())["cost"]["rank_points_per_1000_points"]
    manifest = sorted([g for g in json.loads(cc.MANIFEST.read_text(encoding="utf-8")) if g["date"] >= cc.SINCE], key=lambda g: g["start_time"])
    lj_manifest = [g for g in json.loads(cc.LJ_MANIFEST.read_text(encoding="utf-8")) if g["mode"] == "tenhou-tokujou"]
    n = len(manifest)
    n_before = sum(1 for g in manifest if g["start_time"] < stamp(GUIDE))
    n_new = sum(1 for g in manifest if g["start_time"] >= stamp(NEW_FROM))
    n_run = sum(1 for g in manifest if stamp(RUN_FROM) <= g["start_time"] < stamp(NEW_FROM))
    since, new = manifest[n_before:], manifest[n - n_new:]
    order = {g["uuid"].split("#")[0]: i for i, g in enumerate(manifest)}
    recs = {r[0]: r for r in json.loads(cc.AMAE.read_text())["records"]}
    points = lambda g: next(p for p in recs[g["uuid"]][4] if p[0] == cc.ACCOUNT)[4]  # noqa: E731

    def result(sel: list[dict]) -> dict:
        pl, pts = [g["placement"] for g in sel], [points(g) for g in sel]
        return {"games": len(sel), "places": [pl.count(i) for i in (1, 2, 3, 4)], "fourth_pct": rr.pct(pl.count(4), len(sel)), "rank_points": sum(pts), "rank_points_a_game": round(sum(pts) / len(sel), 1)}

    sd = float(np.std([points(g) for g in manifest]))
    rank = cc.rank_path()
    half = n_new // 2
    results = {"new": result(new), "new_first": result(new[:half]), "new_second": result(new[half:]), "since_the_guide": result(since),
               "since_the_peak": result([g for g in manifest if g["start_time"] > PEAK]), "sd_a_game": round(sd, 1),
               "se_a_game_over_the_new_games": round(sd / math.sqrt(n_new), 1), "se_over_the_new_games": round(sd * math.sqrt(n_new)),
               "rank": {"now": rank["now"]["points"], "peak": rank["peak"]["points"], "below_the_peak": rank["peak"]["points"] - rank["now"]["points"]}}

    # --- chapter 50's check: the hands dealt 4-shanten or worse ---------------------------------------------------
    rows = mc.hand_rows(manifest, "me")
    hero = {g["uuid"].split("#")[0]: g["hero_seat"] for g in manifest}
    mine = [r for r in rows if r["seat"] == hero[r["game"]]]
    spans = {"usual": (0, n - n_new - n_run), "run": (n - n_new - n_run, n - n_new), "new": (n - n_new, n)}
    check = {}
    for name, (lo, hi) in spans.items():
        rs = [r for r in mine if lo <= order[r["game"]] < hi]
        poor = [r for r in rs if r["haipai_shanten"] >= 4]
        check[name] = {"games": hi - lo, "hands": len(rs), "dealt_4_shanten_or_worse": len(poor), "won": sum(r["won"] for r in poor), "won_pct": rr.pct(sum(r["won"] for r in poor), len(poor)),
                       "tenpai_by_turn_10_pct": rr.pct(sum(1 for r in rs if r["tenpai_turn"] is not None and r["tenpai_turn"] <= 10), len(rs)),
                       "won_pct_all_hands": rr.pct(sum(r["won"] for r in rs), len(rs)), "dealt_in_pct": rr.pct(sum(r["dealt_in"] for r in rs), len(rs))}

    # --- the pace beside the table and beside LuckyJ -----------------------------------------------------------
    def seats(games: list[dict], hero_seat: bool) -> dict:
        out = []
        for g in games:
            pl = rd.places_of(g["final_scores"])
            out += [(pl[s], rd.rank_points(g["final_scores"][s], pl[s])) for s in range(4) if (s == g["hero_seat"]) == hero_seat]
        pls = [x[0] for x in out]
        return {"seat_games": len(out), "places": [pls.count(i) for i in (1, 2, 3, 4)], "fourth_pct": rr.pct(pls.count(4), len(out)), "rank_points_a_game": round(sum(x[1] for x in out) / len(out), 1)}

    pace = {"you": seats(since, True), "jade_human": seats(since, False), "luckyj": seats(lj_manifest, True), "tokujou_human": seats(lj_manifest, False)}
    pace["above_the_table"] = {"you": round(pace["you"]["rank_points_a_game"] - pace["jade_human"]["rank_points_a_game"], 1),
                               "luckyj": round(pace["luckyj"]["rank_points_a_game"] - pace["tokujou_human"]["rank_points_a_game"], 1)}
    pace["luckyj_in_your_seat"] = round(pace["jade_human"]["rank_points_a_game"] + pace["above_the_table"]["luckyj"], 1)
    climb = [{"pace": p, "games_per_1000": round(1000 / p), "ahead_after_50_pct": chance_ahead(p, 50, sd), "ahead_after_100_pct": chance_ahead(p, 100, sd),
              "ahead_after_200_pct": chance_ahead(p, 200, sd)} for p in PACES]

    # --- where a game's points come from --------------------------------------------------------------------------
    rows_lj = mc.hand_rows(lj_manifest, "lj")
    hero_lj = {g["uuid"].split("#")[0]: g["hero_seat"] for g in lj_manifest}
    sg, sg_lj = rd.seat_games(rows, hero), rd.seat_games(rows_lj, hero_lj)
    you = rd.components(sg, lambda k, c: c["hero"] and order[k[0]] >= n_before)
    table = rd.components(sg, lambda k, c: not c["hero"] and order[k[0]] >= n_before)
    edges = {"you": rd.edge(you, table, per_1000), "luckyj": rd.edge(rd.components(sg_lj, lambda k, c: c["hero"]), rd.components(sg_lj, lambda k, c: not c["hero"]), per_1000)}
    edges["gap"] = {k: {"points": edges["luckyj"][k]["points"] - edges["you"][k]["points"], "rank_points": round(edges["luckyj"][k]["rank_points"] - edges["you"][k]["rank_points"], 1)} for k in edges["you"]}

    # --- the tiles thrown at a riichi from a hand not tenpai ----------------------------------------------------
    with Pool(10) as pool:
        mine_threat = pool.map(threat_rows, since, chunksize=4)
        lj_threat = pool.map(threat_rows, lj_manifest, chunksize=8)
        discards = pool.map(discard_rows, since, chunksize=4)
    live = {"you": live_tile_table(mine_threat, True), "jade_human": live_tile_table(mine_threat, False), "luckyj": live_tile_table(lj_threat, True), "tokujou_human": live_tile_table(lj_threat, False)}
    a, b = live["you"]["not_tenpai_at_a_riichi"]["live"], live["luckyj"]["not_tenpai_at_a_riichi"]["live"]
    live["gap_to_luckyj"] = {"points_a_game": a["points_a_game"] - b["points_a_game"], "rank_points_a_game": round((a["points_a_game"] - b["points_a_game"]) * per_1000 / 1000, 1),
                             "z_deal_in_rate": rr.two_prop_z((a["deal_ins"], a["throws"]), (b["deal_ins"], b["throws"]))}

    # --- Mortal as the marker, the levers and the cases -----------------------------------------------------------
    replay_index = {g["id"]: g for g in json.loads((REPLAYS / "index.json").read_text())["games"]}
    mark = marker([r for g in discards for r in g], len(since), per_1000)
    lev, deals = levers(since, replay_index)
    cases = cut_cases(since, deals)
    new_ids = {g["uuid"] for g in new}
    cuts = {"since_the_guide": cut_summary(cases), "new_games": cut_summary([c for c in cases if c["game"] in new_ids]), "list": cases}

    out = {"guide": GUIDE, "new_from": NEW_FROM, "games": {"all": n, "before": n_before, "since": len(since), "run": n_run, "new": n_new}, "rank_points_per_1000_points": per_1000,
           "results": results, "chapter_50_check": check, "pace": pace, "climb": climb, "edges": edges, "live_tiles": live, "mortal_marker": mark, "levers": lev, "cuts": cuts}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
