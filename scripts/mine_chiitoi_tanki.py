#!/usr/bin/env python3
"""Seven pairs waiting on one tile: how often each kind of wait is released, and what LuckyJ keeps when it can choose.

For every closed hand of any seat in the user's Jade games and LuckyJ's Tokujou games, each moment after a discard when
the hand is six pairs and a single (the wait is that one tile and nothing else) is a *tenpai moment*:

- the wait's kind (a dragon or the round wind, a wind that is an opponent's seat wind, a wind nobody needs, a terminal,
  a dora, any other number), its copies unseen from the waiter's seat (the hand, every river and meld, the
  indicators), and whether the waiter had declared riichi or was furiten;
- the exposure: how many times each other player discarded the wait before the waiter's next discard (a ron if the
  waiter is not furiten), per turn;
- at the first tenpai moment of a riichi hand: whether the waiter won the hand, dealt in, and the points it moved.

When two different discards both leave seven pairs and a single, the moment is a *choice*: the two waits, which one
the player kept, and whether it declared riichi.

``report`` turns those rows into the chapter's figures, and adds the three hands of the user's 15 October games the
chapter walks through (``cases``): the seven-pairs hands of the 100-point game (Mortal's riichi and waits at each turn,
and what the Hatsu and East did after) and the all-last tenpai of the first game with no yaku (the waits of each
discard, the live tiles, who had thrown each tile, the winner's hand, Mortal's ratings).

usage: mine_chiitoi_tanki.py compute YOUR_MANIFEST.json OUT.json
       mine_chiitoi_tanki.py report ROWS.json OUT.json
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"


def seven_pairs_single(hand: list[int]) -> int | None:
    """The single tile if the 13 tiles are six pairs of different tiles and one more tile, else None."""
    from tenhou_replay import base

    c = Counter(base(t) for t in hand)
    if len(hand) != 13 or len(c) != 7 or sorted(c.values()) != [1, 2, 2, 2, 2, 2, 2]:
        return None
    return next(t for t, n in c.items() if n == 1)


def kind_of(w: int, dora: set[int], game: dict, seat: int) -> str:
    if w in dora:
        return "dora honor" if w >= 40 else "dora"
    if w >= 40:
        round_wind = 41 + game["kyoku"] // 4 if game["kyoku"] < 16 else 41
        winds = {41 + (q - game["kyoku"] % 4) % 4 for q in range(4) if q != seat}
        if w >= 45 or w == round_wind:
            return "dragon or round wind"
        return "an opponent's seat wind" if w in winds else "a wind nobody needs"
    return "terminal" if w % 10 in (1, 9) else "number 2-8"


def game_rows(job) -> dict:
    g, table = job
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, visible_counter
    from tenhou_replay import base

    hero = g["hero_seat"]
    moments, choices, hands = [], [], []
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        events = game["events"]
        indicators = game["dora_indicators"][:1]
        dora = {base(ws.dora_from_indicator(x)) for x in indicators}
        blocks = tr.result_blocks(log[-1])
        winners = {d[0]: (d[1] != d[0]) for _, d in blocks}
        deltas = tr.result_deltas(log[-1])
        for k, e in enumerate(events):
            s = e["seat"]
            if e.get("tile") is None or e["melds"] or not e["closed"]:
                continue
            w = seven_pairs_single(e["hand_after"])
            if w is None or {base(x) for x in tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])} != {w}:
                continue
            snap = meld_snapshots(game, e["index"] - 1)
            snap[s] = e["melds"]
            seen = visible_counter(e["hand_after"], e, game["players"], snap, indicators)
            seen[base(e["tile"])] += 1
            unseen = 4 - seen[w]
            own = {base(x) for x in e["rivers"][s]} | {base(e["tile"])}
            furiten = w in own
            nxt = next((j for j in range(k + 1, len(events)) if events[j]["seat"] == s), len(events))
            released = sum(1 for j in range(k + 1, nxt) if base(events[j]["tile"]) == w)
            riichi = e["riichi_seats"][s] is not None or e["riichi"]
            who = ("luckyj" if s == hero else "tokujou_human") if table == "tenhou" else ("you" if s == hero else "jade_human")
            row = {"game": g["uuid"], "li": li, "round": game["round_name"], "turn": e["turn"], "seat": s, "who": who,
                   "wait": w, "kind": kind_of(w, dora, game, s), "unseen": unseen, "riichi": bool(riichi), "furiten": furiten,
                   "released": released, "first": e["riichi"] or not any(m["seat"] == s and m["li"] == li for m in moments),
                   "wins": s in winners, "tsumo": winners.get(s) is False, "delta": deltas[s],
                   "opp_riichi": sum(1 for q in range(4) if q != s and e["riichi_seats"][q] is not None)}
            moments.append(row)
            if e["riichi"]:
                hands.append(row)

        # the discards that left a choice between two waits (hand_before has two singles among six pairs)
        for e in events:
            s = e["seat"]
            if e.get("tile") is None or e["melds"] or not e["closed"]:
                continue
            hb = e["hand_before"]
            c = Counter(base(t) for t in hb)
            opts = []
            for t in set(c):
                d = Counter(c)
                d[t] -= 1
                if d[t] == 0:
                    del d[t]
                if len(d) == 7 and sorted(d.values()) == [1, 2, 2, 2, 2, 2, 2]:
                    opts.append((t, next(x for x, n in d.items() if n == 1)))
            if len(opts) < 2:
                continue
            snap = meld_snapshots(game, e["index"] - 1)
            snap[s] = e["melds"]
            seen = visible_counter(hb, e, game["players"], snap, indicators)
            kept = seven_pairs_single(e["hand_after"])
            who = ("luckyj" if s == hero else "tokujou_human") if table == "tenhou" else ("you" if s == hero else "jade_human")
            choices.append({"game": g["uuid"], "round": game["round_name"], "turn": e["turn"], "who": who, "riichi": e["riichi"],
                            "kept": kept, "thrown": base(e["tile"]),
                            "options": [{"wait": w, "kind": kind_of(w, dora, game, s), "unseen": 4 - seen[w]} for _, w in opts]})
    return {"moments": moments, "hands": hands, "choices": choices}


def compute(your_manifest: str, out: str) -> None:
    os.chdir(ROOT)
    you = json.load(open(your_manifest))
    lj = json.loads(LJ_MANIFEST.read_text(encoding="utf-8"))
    jobs = [(g, "jade") for g in you] + [(g, "tenhou") for g in lj]
    result = {"moments": [], "hands": [], "choices": []}
    with Pool(12) as pool:
        for part in pool.imap(game_rows, jobs, chunksize=4):
            for k in result:
                result[k].extend(part[k])
    Path(out).write_text(json.dumps(result) + "\n")
    print(f"wrote {out}: {len(result['moments'])} tenpai moments, {len(result['hands'])} riichi hands, {len(result['choices'])} choices")


HON = ("dragon or round wind", "an opponent's seat wind", "a wind nobody needs")
GAME_100 = "261016-76fdbc7c-8746-4b3b-97fd-c0b15a1e161f"
GAME_ALL_LAST = "261016-7cc3ee5d-65fc-4333-a381-7cb5db6923eb"
SIDES = ("luckyj", "tokujou_human", "you", "jade_human")


def group(r: dict) -> str:
    if r["kind"] == "dora":
        return "dora number"
    if r["kind"] in HON:
        return "honor, not dora"
    if r["kind"] == "dora honor":
        return "dora honor"
    return "number or terminal, not dora"


def pct(k: float, n: float, digits: int = 1) -> float | None:
    return round(100 * k / n, digits) if n else None


def hand_table(rows: list[dict]) -> dict:
    cell: dict[str, list[dict]] = {}
    for r in rows:
        if not r["furiten"] and r["unseen"] in (1, 2, 3):
            cell.setdefault(group(r), []).append(r)
    out = {}
    for name, rs in sorted(cell.items()):
        wins = [r for r in rs if r["wins"]]
        out[name] = {"hands": len(rs), "won": len(wins), "won_pct": pct(len(wins), len(rs)), "tsumo": sum(r["tsumo"] for r in wins),
                     "avg_win": round(sum(r["delta"] for r in wins) / len(wins)) if wins else None,
                     "points_a_hand": round(sum(r["delta"] for r in rs) / len(rs)),
                     "paid": sum(1 for r in rs if not r["wins"] and r["delta"] < -1000)}
    return out


def release_table(moments: list[dict]) -> dict:
    cell: dict[str, list[int]] = {}
    for m in moments:
        if m["furiten"] or not m["riichi"] or m["unseen"] not in (2, 3):
            continue
        c = cell.setdefault(m["kind"], [0, 0])
        c[0] += 1
        c[1] += m["released"]
    return {k: {"turns": n, "released": rel, "per_100_turns": pct(rel, n)} for k, (n, rel) in sorted(cell.items())}


def choice_table(choices: list[dict]) -> dict:
    """Hands holding a dora number and a non-dora honor as the two singles: one decision per hand (the first turn)."""
    seen: set = set()
    per_hand: dict[str, list[int]] = {w: [0, 0] for w in SIDES}
    riichi: dict[str, list[int]] = {w: [0, 0] for w in SIDES}
    for c in choices:
        kinds = {o["kind"] for o in c["options"]}
        if "dora" not in kinds or not kinds & set(HON):
            continue
        kept_dora = any(o["kind"] == "dora" and o["wait"] == c["kept"] for o in c["options"])
        key = (c["game"], c["round"], c["who"])
        if key not in seen:
            seen.add(key)
            per_hand[c["who"]][0] += 1
            per_hand[c["who"]][1] += kept_dora
        if c["riichi"]:
            riichi[c["who"]][0] += 1
            riichi[c["who"]][1] += kept_dora
    return {"hands": {w: {"hands": n, "kept_dora": k, "kept_other": n - k} for w, (n, k) in per_hand.items()},
            "riichi": {w: {"declarations": n, "kept_dora": k, "kept_other": n - k} for w, (n, k) in riichi.items()}}


def hero_draw_index(hand: dict, hero: int, turn: int) -> int:
    """The replay stream's index of the hero's draw at ``turn`` (the hero must not have called before it)."""
    draws = [i for i, e in enumerate(hand["ev"]) if e[0] == "t" and e[1] == hero]
    assert not any(e[0] in ("c", "p", "m") and e[1] == hero for e in hand["ev"][:draws[turn - 1]]), "a call shifts the turns"
    return draws[turn - 1]


def whatif(row: dict, game: dict, targets: list[tuple[int, int]]) -> dict:
    """Mortal's reaction at the hero's draw ``(hand, stream index)``, and its discard if the hero then declares riichi."""
    import build_replays as br

    engine = br.load_engine()
    from libriichi.mjai import Bot

    out = {}
    for h_target, i_target in targets:
        bot = Bot(engine, game["hero"])
        for h, i, ev in br.mjai_events(game):
            raw = bot.react(json.dumps(ev, ensure_ascii=False), can_act=True)
            if h == h_target and i == i_target:
                played = br.decode(json.loads(raw))
                after = br.decode(json.loads(bot.react(json.dumps({"type": "reach", "actor": game["hero"]}), can_act=True)))
                out[(h_target, i_target)] = {"played": [[a, round(p, 3)] for a, p in played[:5]],
                                             "after_riichi": [[a, round(p, 3)] for a, p in after[:3]]}
                break
    return out


def tile_name(t: int) -> str:
    names = {41: "East", 42: "South", 43: "West", 44: "North", 45: "Haku", 46: "Hatsu", 47: "Chun"}
    return names.get(t) or f"{t % 10}{'mps'[t // 10 - 1]}"


def seven_pairs_cases(rows: dict) -> dict:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, visible_counter
    from tenhou_replay import base
    import build_replays as br

    g = next(x for x in rows["manifest"] if x["uuid"] == GAME_100)
    hero = g["hero_seat"]
    game_row = br.build_game(g)
    replay = json.loads((ROOT / "site" / "replays" / f"{GAME_100}.json").read_text(encoding="utf-8"))
    out = {}
    plan = {"East 4-0": [5], "South 1-0": [5, 6, 7]}
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        if game["round_name"] not in plan:
            continue
        events, indicators = game["events"], game["dora_indicators"][:1]
        dora = {base(ws.dora_from_indicator(x)) for x in indicators}
        hand_replay = replay["hands"][li]
        rec = {"round": game["round_name"], "dealer": game["kyoku"] % 4 == hero, "dora": [tile_name(d) for d in sorted(dora)],
               "end": hand_replay["end"]["kind"], "turns": {}}
        targets = []
        for turn in plan[game["round_name"]]:
            e = next(x for x in events if x["seat"] == hero and x["turn"] == turn)
            hb = e["hand_before"]
            c = Counter(base(t) for t in hb)
            opts = []
            for t in sorted(c):
                d = Counter(c)
                d[t] -= 1
                if d[t] == 0:
                    del d[t]
                if len(d) == 7 and sorted(d.values()) == [1, 2, 2, 2, 2, 2, 2]:
                    opts.append((t, next(x for x, n in d.items() if n == 1)))
            snap = meld_snapshots(game, e["index"] - 1)
            snap[hero] = e["melds"]
            seen = visible_counter(hb, e, game["players"], snap, indicators)
            idx = hero_draw_index(hand_replay, hero, turn)
            targets.append((li, idx))
            rec["turns"][turn] = {"thrown": tile_name(base(e["tile"])), "stream_index": idx,
                                  "options": [{"discard": tile_name(d), "wait": tile_name(w), "dora": w in dora, "unseen": 4 - seen[w]} for d, w in opts]}
        for turn, key in zip(plan[game["round_name"]], targets):
            rec["turns"][turn]["mortal"] = whatif(g, game_row, [key])[key]
        out[game["round_name"]] = rec
        out[game["round_name"]]["_events"] = [{"index": e["index"], "seat": (e["seat"] - hero) % 4, "turn": e["turn"], "drew": tile_name(base(e["drawn"])) if e.get("drawn") is not None else None,
                                               "threw": tile_name(base(e["tile"])) if e.get("tile") is not None else None, "riichi": e["riichi"]}
                                              for e in events]
    east = out["East 4-0"]
    ev = east.pop("_events")
    east["right_riichi_after_your_turn"] = next(e["turn"] for e in ev if e["riichi"] and e["seat"] == 1)
    east["hatsu_after_turn_5"] = [{"who": ("you" if e["seat"] == 0 else {1: "right", 2: "across", 3: "left"}[e["seat"]]), "turn": e["turn"], "kind": "your draw" if e["seat"] == 0 and e["drew"] == "Hatsu" else "discard"}
                                  for e in ev if e["index"] > 17 and ((e["seat"] != 0 and e["threw"] == "Hatsu") or (e["seat"] == 0 and e["drew"] == "Hatsu"))]
    east["pushed_discards"] = sum(1 for e in ev if e["seat"] == 0 and e["turn"] > 5)
    east["deal_in"] = {"turn": 13, "tile": next(e["threw"] for e in ev if e["seat"] == 0 and e["turn"] == 13), "points": 5200}
    south = out["South 1-0"]
    ev = south.pop("_events")
    south["east_after_turn_6"] = [e for e in ev if e["index"] > next(x["index"] for x in ev if x["seat"] == 0 and x["turn"] == 6) and (
        (e["seat"] != 0 and e["threw"] == "East") or (e["seat"] == 0 and e["drew"] == "East"))]
    south["win"] = {"points": 9600, "from": "left", "after_your_turn": 7}
    return out


def all_last_case(rows: dict) -> dict:
    import review_win_speed as ws
    import tenhou_replay as tr
    import mine_open_tenpai_push as otp
    from build_personal_guide import meld_snapshots, visible_counter
    from tenhou_replay import base

    g = next(x for x in rows["manifest"] if x["uuid"] == GAME_ALL_LAST)
    hero = g["hero_seat"]
    replay = json.loads((ROOT / "site" / "replays" / f"{GAME_ALL_LAST}.json").read_text(encoding="utf-8"))
    rel = {0: "you", 1: "right", 2: "across", 3: "left"}
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        if game["round_name"] != "South 4-0":
            continue
        events, indicators = game["events"], game["dora_indicators"][:1]
        dora = {base(ws.dora_from_indicator(x)) for x in indicators}
        e18 = next(x for x in events if x["seat"] == hero and x["turn"] == 18)
        melds = game["players"][hero]["melds"]
        snap = meld_snapshots(game, e18["index"] - 1)
        snap[hero] = e18["melds"]
        seen = visible_counter(e18["hand_before"], e18, game["players"], snap, indicators)
        draws = sum(1 for x in events if x["index"] <= e18["index"] and x.get("drawn") is not None and not x.get("called"))
        rivers = {s: [base(t) for t in e18["rivers"][s]] for s in range(4)}
        options = {}
        for name, code in (("2p", 22), ("3p", 23), ("5p", 25)):
            t = next(x for x in e18["hand_before"] if base(x) == code)
            hand13 = list(e18["hand_before"])
            hand13.remove(t)
            waits = sorted(base(w) for w in tr.waits(hand13, e18["meld_tiles"], e18["closed"]))
            vc = visible_counter(hand13, e18, game["players"], snap, indicators)
            options[name] = {"waits": [tile_name(w) for w in waits], "live": sum(4 - vc[w] for w in waits),
                             "ron_han": [otp.ron_value(hand13, melds, w, hero, game["kyoku"], dora, fu=True)[0] for w in waits],
                             "thrown_by": [rel[(s - hero) % 4] for s in range(4) if s != hero and code in rivers[s]]}
        win_seat = 0
        last = [x for x in events if x["seat"] == win_seat][-1]
        winner = {"seat": rel[(win_seat - hero) % 4], "calls": len(game["players"][win_seat]["melds"]),
                  "waits": sorted(tile_name(base(w)) for w in tr.waits(last["hand_after"], last["meld_tiles"], last["closed"])),
                  "last_discards": [{"tile": tile_name(base(x["tile"])), "drawn_and_thrown": bool(x.get("tsumogiri"))}
                                    for x in [y for y in events if y["seat"] == win_seat and y["index"] <= e18["index"]][-5:]]}
        hand_replay = replay["hands"][li]
        turn, tmap = 0, {}
        for i, e in enumerate(hand_replay["ev"]):
            if e[1] == hero and ((e[0] == "t" and not (len(e) > 3 and e[3])) or e[0] in ("c", "p", "m")):
                turn += 1
            tmap[i] = turn
        ai = next(a for a in hand_replay["ai"] if a.get("p") and tmap[a["i"]] == 18 and a["you"] == "2p")
        calls_others = {rel[(s - hero) % 4]: len(game["players"][s]["melds"]) for s in range(4) if s != hero}
        return {"round": game["round_name"], "dealer": game["kyoku"] % 4 == hero, "start_scores": [game["start_scores"][(hero + k) % 4] for k in range(4)],
                "tiles_left_after_your_draw": 70 - draws, "options": options, "winner": winner, "others_calls": calls_others,
                "mortal": [[a, round(p, 2)] for a, p in ai["p"][:3]], "deal_in": {"points": 7700, "tile": "2p", "final": replay["final"][hero]},
                "dora": [tile_name(d) for d in sorted(dora)]}
    raise RuntimeError("the all-last hand is missing")


def report(rows_path: str, out: str) -> None:
    os.chdir(ROOT)
    rows = json.loads(Path(rows_path).read_text())
    rows["manifest"] = json.loads((ROOT / "data/self_games/majsoul/index.json").read_text(encoding="utf-8"))
    result = {"moments": len(rows["moments"]), "riichi_hands": len(rows["hands"]),
              "riichi": hand_table(rows["hands"]),
              "dama": hand_table([m for m in {(m["game"], m["round"], m["seat"]): m for m in reversed(rows["moments"])}.values() if not m["riichi"]]),
              "release": release_table(rows["moments"]), "choices": choice_table(rows["choices"]),
              "cases": {"seven_pairs": seven_pairs_cases(rows), "all_last": all_last_case(rows)}}
    Path(out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(*sys.argv[2:4])
    else:
        report(*sys.argv[2:4])
