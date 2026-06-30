#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

import analyze_luckyj as base
from extract_case_studies import (
    danger_for,
    hand_string,
    remove_tile,
    round_name,
    safety_read,
    score_band,
    ukeire_after_discard,
)


OUT = Path("site/point-examples.json")
SEAT_NAMES = ["self", "shimocha", "toimen", "kamicha"]
WINDS = ["E", "S", "W", "N"]
DRAGONS = {"P", "F", "C"}


POINT_TEXT = {
    "point-01": {
        "title": "Placement changes the price of the same tile",
        "lesson": "The discard is not judged in a vacuum. A leading or fragile placement can make future defense more valuable than a prettier immediate shape.",
        "prompt": "Before choosing, name the hand's job: win now, protect placement, escape last, or keep future exits.",
        "answer": "Copy the risk budget, not the tile. The correct discard is the one that serves the placement job while leaving a playable next turn.",
    },
    "point-02": {
        "title": "Keep the branch point alive",
        "lesson": "LuckyJ often keeps tiles that still serve yaku, value, or safety, even when that makes the current shanten number look worse.",
        "prompt": "List the live routes before cutting: closed riichi, open yaku, value upgrade, chiitoi, and fold.",
        "answer": "Do not collapse into the cleanest single route until the table has forced that commitment.",
    },
    "point-03": {
        "title": "Bad closed shapes buy calls",
        "lesson": "The call is valuable when the closed route is mostly imaginary and the open hand creates yaku, tempo, or real tenpai pressure.",
        "prompt": "Before calling, say what the call creates: yaku, tenpai, real 1-shanten, denial, or safe draw equity.",
        "answer": "Call poor closed shapes when the exposed hand has a contract and still leaves a way to stop.",
    },
    "point-04": {
        "title": "Open hands must keep an exit",
        "lesson": "After opening, the important tile is often the safe tile left behind, not the tile called. LuckyJ's open hands work because they are not all-in by accident.",
        "prompt": "After the call, identify the next safe discard before admiring the new shanten.",
        "answer": "A cheap exposed hand with no exit is usually not LuckyJ-style aggression; it is being forced to push.",
    },
    "point-05": {
        "title": "Cut the future liability now",
        "lesson": "The floater is bad because a slow hand may be forced to discard it after the table becomes dangerous.",
        "prompt": "Find the tile you will hate discarding after the first riichi or second call.",
        "answer": "If the hand is far away and the tile has no value job, remove it before it becomes expensive.",
    },
    "point-06": {
        "title": "Build the hand class early",
        "lesson": "A cheap bad-shape future is not worth optimizing toward when the score job needs more. Early acceptance is the cheapest thing to spend.",
        "prompt": "Ask what score class this hand needs before preserving maximum ukeire.",
        "answer": "Keep dora, yaku, and shape upgrades when the fast hand would be too small or too brittle.",
    },
    "point-07": {
        "title": "Call for tempo with a contract",
        "lesson": "The call has a job beyond completing blocks: speed up a poor hand, contest the table, break a bonus window, or preserve draw equity.",
        "prompt": "No contract, no call. Name the contract before exposing the hand.",
        "answer": "A good tempo call changes the round's clock without making you helpless on the next threat.",
    },
    "point-08": {
        "title": "Riichi converts pressure into equity",
        "lesson": "LuckyJ does not wait for a perfect shape when riichi itself changes the table. The declaration can force rivals to fold, deny calls, or lock in placement value.",
        "prompt": "Before riichi, ask who must now respond to you and whether better upgrades are realistic.",
        "answer": "If the wait is serviceable and the table must respect the stick, declaration pressure can be worth more than waiting.",
    },
    "point-09": {
        "title": "Reprice the hand after every draw",
        "lesson": "A hand that was pushing one turn ago can become a fold when the next required discard is bad. The chain of future discards matters more than the current tile alone.",
        "prompt": "Count the current discard plus the next two likely discards before calling the hand a push.",
        "answer": "If the path contains several live danger tiles, downgrade the hand even when it is close.",
    },
    "point-10": {
        "title": "Late precision beats late invention",
        "lesson": "Late choices should have exact upside: winning tenpai, safe tenpai, or clean fold. Speculative value routes have mostly expired.",
        "prompt": "In the third row, state whether you are winning, taking safe tenpai, or folding.",
        "answer": "The later the hand, the more the example is a counting drill rather than a style imitation.",
    },
    "point-11": {
        "title": "Drawn-hand points are attack equity",
        "lesson": "Late defense is not always surrender. Safe tenpai or harmless 1-shanten can win the hand without winning the hand.",
        "prompt": "When the hand is unlikely to win, count whether a safe route to tenpai still exists.",
        "answer": "Choose the safe discard that leaves the most realistic tenpai path for the draw.",
    },
    "point-12": {
        "title": "A disagreement is a review prompt, not a verdict",
        "lesson": "The useful question is why LuckyJ and NAGA split: safety, route count, value, pressure, or a real mistake.",
        "prompt": "Bucket the disagreement before judging it: blunder, strategic trade-off, or table-reading idea.",
        "answer": "Do not chase match rate. Chase explainable decisions with fewer unpriced risks.",
    },
    "point-13": {
        "title": "Clean yakuhai against unproven open hands",
        "lesson": "When another player calls without showing a clear yaku, singleton dragons and live value winds can become their missing contract. LuckyJ often removes those tiles before they turn into the price of continuing.",
        "prompt": "After an opponent opens, ask which yakuhai still lets that hand win.",
        "answer": "If your hand is not ready to punish them and the yakuhai has no strong job, clean it before the open hand gets to use it.",
    },
    "point-14": {
        "title": "Keep river-safe and suji exits on purpose",
        "lesson": "LuckyJ often keeps a tile because it is already genbutsu or suji against an opponent river, especially before spending safer exits would make the next threat impossible to answer.",
        "prompt": "Before discarding a flexible tile, count which tiles in your hand are genbutsu or suji to each opponent and which of them are still useful next turn.",
        "answer": "Keep the safe tile while it buys future choice; spend it only when the hand has become worth the risk or the draw-point/fold route is already decided.",
    },
}


def tile_id(tile):
    return base.IDX[tile]


def base_tile(tile):
    return str(tile or "").replace("r", "")


def rel_seat(seat, target):
    if seat is None:
        return "unknown"
    return SEAT_NAMES[(seat - target) % 4]


def seat_wind(start, seat):
    return WINDS[(seat - start.get("oya", 0)) % 4]


def yakuhai_for_seat(start, seat):
    return DRAGONS | {start.get("bakaze"), seat_wind(start, seat)}


def is_yakuhai_for_seat(tile, start, seat):
    return base_tile(tile) in yakuhai_for_seat(start, seat)


def meld_tiles(meld):
    return [tile for tile in str(meld).split() if tile and tile != "+"]


def meld_shows_yakuhai_contract(meld, start, seat):
    counts = Counter(tile_id(tile) for tile in meld_tiles(meld))
    return any(count >= 3 and is_yakuhai_for_seat(base.TILES[idx], start, seat) for idx, count in counts.items())


def yakuhai_cleanup_threats(start, target, melds, tile):
    threats = []
    for seat, player_melds in enumerate(melds):
        if seat == target or not player_melds:
            continue
        if any(meld_shows_yakuhai_contract(meld, start, seat) for meld in player_melds):
            continue
        if is_yakuhai_for_seat(tile, start, seat):
            threats.append(seat)
    return threats


def score_context(start, target):
    scores = start.get("scores", [None] * 4)
    ranks = start.get("seat2rank", [None] * 4)
    dealer = start.get("oya", 0)
    return [
        {
            "seat": rel_seat(seat, target),
            "wind": WINDS[(seat - dealer) % 4],
            "score": scores[seat] if seat < len(scores) else None,
            "rank": ranks[seat] + 1 if seat < len(ranks) and ranks[seat] is not None else None,
            "dealer": seat == dealer,
        }
        for seat in range(4)
    ]


def table_context(start, target, hands, discards, melds, reached, dora_markers):
    return {
        "round": round_name(start),
        "dealer": rel_seat(start.get("oya"), target),
        "dora_markers": dora_markers[:],
        "scores": score_context(start, target),
        "players": [
            {
                "seat": rel_seat(seat, target),
                "wind": WINDS[(seat - start.get("oya", 0)) % 4],
                "hand": hand_string(hands[seat]),
                "discards": discards[seat][:],
                "melds": melds[seat][:],
                "reached": bool(reached[seat]),
            }
            for seat in range(4)
        ],
    }


def visible_counter(discards, melds, dora_markers):
    visible = Counter()
    for marker in dora_markers:
        visible[tile_id(marker)] += 1
    for river in discards:
        for tile in river:
            visible[tile_id(tile)] += 1
    for player_melds in melds:
        for meld in player_melds:
            for tile in meld.split():
                if tile and tile != "+":
                    visible[tile_id(tile)] += 1
    return visible


def top_rows(state, actual):
    rows = []
    if not actual or actual == "?":
        return rows
    for pred in state.get("dahai_pred", [])[:3]:
        top, top_prob = base.top_tile(pred)
        actual_prob = base.prob_for(pred, actual)
        rows.append((top, top_prob, actual_prob))
    return rows


def end_summary(start, target):
    msgs = start.get("end_msgs") or []
    if not msgs:
        return "No recorded hand result."
    if msgs[0].get("type") == "hora":
        parts = []
        for msg in msgs:
            actor = rel_seat(msg.get("actor"), target)
            fan = msg.get("fan")
            hu = msg.get("hu")
            delta = (msg.get("deltas") or [0, 0, 0, 0])[target]
            if msg.get("actor") == target:
                parts.append(f"self won {fan} han {hu} fu, delta {delta:+}")
            elif msg.get("target") == target:
                parts.append(f"self dealt into {actor}, delta {delta:+}")
            else:
                parts.append(f"{actor} won, self delta {delta:+}")
        return "; ".join(parts)
    delta = sum((msg.get("deltas") or [0, 0, 0, 0])[target] for msg in msgs)
    return f"draw, self delta {delta:+}"


def common_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    score = start.get("scores", [0, 0, 0, 0])[target]
    text = POINT_TEXT[point_key]
    return {
        "point": point_key,
        "title": text["title"],
        "lesson": text["lesson"],
        "prompt": text["prompt"],
        "answer": text["answer"],
        "game": row["idx"],
        "rank": row["rank"],
        "round": round_name(start),
        "kyoku_index": kyoku_index,
        "position": pos,
        "left": msg.get("left_hai_num"),
        "stage": base.stage_from_left(msg.get("left_hai_num")),
        "score": score,
        "score_band": score_band(score),
        "report": row["report"],
        "paifu": row["paifu"],
        "table": table_context(start, target, hands, discards, melds, reached, dora_markers),
        "outcome": end_summary(start, target),
    }


def make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    actual = msg.get("real_dahai")
    rows = top_rows(state, actual)
    if not rows:
        return None
    naga = rows[0][0]
    try:
        visible = visible_counter(discards, melds, dora_markers)
        open_counts = [len(player_melds) for player_melds in melds]
        safety_context = (target, discards, reached, open_counts)
        actual_eval = ukeire_after_discard(hands[target], actual, visible, safety_context)
        naga_eval = ukeire_after_discard(hands[target], naga, visible, safety_context)
    except (KeyError, ValueError):
        return None
    if not actual_eval or not naga_eval:
        return None
    case = common_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key)
    case.update(
        {
            "kind": "discard",
            "hand": hand_string(hands[target]),
            "draw": msg.get("pai"),
            "actual": actual,
            "naga": naga,
            "actual_danger": danger_for(state, target, actual),
            "naga_danger": danger_for(state, target, naga),
            "actual_eval": actual_eval,
            "naga_eval": naga_eval,
            "naga_votes": [row[0] for row in rows],
            "naga_prob": round(rows[0][1], 3),
            "actual_prob": round(rows[0][2], 3),
            "kept_tile_safety": safety_read(naga, target, discards, reached, open_counts),
        }
    )
    return case


def make_yakuhai_cleanup_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, threats):
    case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-13")
    if not case:
        return None
    target = row["actor"]
    case["yakuhai_cleanup"] = {
        "threats": [
            {
                "seat": rel_seat(seat, target),
                "wind": seat_wind(start, seat),
                "melds": melds[seat][:],
            }
            for seat in threats
        ]
    }
    return case


def make_simple_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    actual = msg.get("real_dahai")
    rows = top_rows(state, actual)
    if not rows:
        return None
    naga = rows[0][0]
    open_counts = [len(player_melds) for player_melds in melds]
    case = common_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key)
    case.update(
        {
            "kind": "draw-tenpai",
            "hand": hand_string(hands[target]),
            "draw": msg.get("pai"),
            "actual": actual,
            "naga": naga,
            "actual_danger": danger_for(state, target, actual),
            "naga_danger": danger_for(state, target, naga),
            "naga_votes": [row[0] for row in rows],
            "naga_prob": round(rows[0][1], 3),
            "actual_prob": round(rows[0][2], 3),
            "kept_tile_safety": safety_read(naga, target, discards, reached, open_counts),
        }
    )
    return case


def make_reach_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers):
    reach_prob = max((p / 10000.0 for p in state.get("reach", [])), default=0.0)
    if reach_prob < 0.5:
        return None
    case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-08")
    if case:
        case["kind"] = "reach"
        case["reach_prob"] = round(reach_prob, 3)
        case["actual_reach"] = True
        case["naga_reach"] = True
        case["actual_eval"]["declares_reach"] = True
        case["actual_eval"]["reach_prob"] = round(reach_prob, 3)
        case["naga_eval"]["declares_reach"] = True
        case["naga_eval"]["reach_prob"] = round(reach_prob, 3)
    return case


def make_call_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    if msg.get("actor") != target or msg.get("type") not in base.HURO_TYPES:
        return None
    case = common_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key)
    consumed = msg.get("consumed", [])
    case.update(
        {
            "kind": "call",
            "call": msg.get("type"),
            "called_tile": msg.get("pai"),
            "called_from": rel_seat(msg.get("target"), target),
            "consumed": consumed,
            "discard_after_call": msg.get("real_dahai"),
            "hand": hand_string(hands[target]),
            "post_call_meld": " ".join(consumed + ([msg.get("pai")] if msg.get("pai") else [])),
        }
    )
    return case


def candidate_signature(candidate):
    if not candidate:
        return None
    return (
        candidate.get("game"),
        candidate.get("kyoku_index"),
        candidate.get("position"),
        candidate.get("kind"),
    )


def add(selected, used, point_key, candidate):
    sig = candidate_signature(candidate)
    if point_key not in selected and candidate and sig not in used:
        selected[point_key] = candidate
        used.add(sig)


def try_discard_points(selected, used, row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, open_melds):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    if open_melds[target] or msg.get("reached"):
        return
    actual = msg.get("real_dahai")
    rows = top_rows(state, actual)
    if not rows:
        return

    naga = rows[0][0]
    if naga == actual and "point-08" in selected:
        return
    left = msg.get("left_hai_num") or 0
    stage = base.stage_from_left(left)
    score = start.get("scores", [0, 0, 0, 0])[target]
    actual_cls = base.tile_class(actual)
    naga_cls = base.tile_class(naga)
    actual_d = danger_for(state, target, actual)
    naga_d = danger_for(state, target, naga)
    public_visible = visible_counter(discards, melds, dora_markers)

    if "point-08" not in selected and "reach" in state:
        add(selected, used, "point-08", make_reach_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers))

    if "point-01" not in selected and score >= 35000 and actual_d is not None and naga_d is not None and actual_d <= naga_d:
        add(selected, used, "point-01", make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-01"))

    if "point-02" not in selected and stage == "early" and actual_cls == "simple" and naga_cls in {"honor", "terminal"}:
        add(selected, used, "point-02", make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-02"))

    if "point-05" not in selected and actual_cls == "simple" and naga_cls in {"honor", "terminal"} and (actual_d is None or naga_d is None or actual_d >= naga_d):
        add(selected, used, "point-05", make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-05"))

    if "point-06" not in selected and stage == "early" and naga != actual:
        case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-06")
        if case and case["actual_eval"]["ukeire"] < case["naga_eval"]["ukeire"] and case["actual_eval"]["kept_honors"] >= case["naga_eval"]["kept_honors"]:
            add(selected, used, "point-06", case)

    if "point-09" not in selected and actual_d is not None and naga_d is not None and actual_d < 0.02 and naga_d > 0.08:
        add(selected, used, "point-09", make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-09"))

    kept_read = safety_read(naga, target, discards, reached, open_melds)
    if "point-14" not in selected and naga != actual and kept_read["kind"] and kept_read["safe_against_threat"]:
        add(selected, used, "point-14", make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-14"))

    if "point-10" not in selected and stage == "late" and naga != actual:
        add(selected, used, "point-10", make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-10"))

    if "point-12" not in selected and naga != actual:
        add(selected, used, "point-12", make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-12"))

    if "point-13" not in selected and actual_cls == "honor" and naga != actual:
        threats = yakuhai_cleanup_threats(start, target, melds, actual)
        actual_count = sum(1 for tile in hands[target] if tile_id(tile) == tile_id(actual))
        visible_count = public_visible[tile_id(actual)]
        danger_ok = actual_d is None or naga_d is None or actual_d <= naga_d + 0.02
        if threats and actual_count == 1 and visible_count <= 1 and danger_ok:
            add(selected, used, "point-13", make_yakuhai_cleanup_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, threats))

    if "point-11" not in selected and start.get("end_msgs") and start["end_msgs"][0].get("type") != "hora":
        delta = sum((m.get("deltas") or [0, 0, 0, 0])[target] for m in start.get("end_msgs") or [])
        if delta > 0 and stage == "late":
            add(selected, used, "point-11", make_simple_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-11"))


def try_call_points(selected, used, row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers):
    msg = state.get("info", {}).get("msg", {})
    if msg.get("actor") != row["actor"] or msg.get("type") not in base.HURO_TYPES:
        return
    active_threats = sum(1 for value in reached if value)
    if "point-03" not in selected:
        add(selected, used, "point-03", make_call_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-03"))
    elif "point-04" not in selected and (active_threats or (msg.get("real_dahai") and base.tile_class(msg.get("real_dahai")) in {"honor", "terminal"})):
        add(selected, used, "point-04", make_call_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-04"))
    elif "point-07" not in selected:
        add(selected, used, "point-07", make_call_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-07"))


def collect_examples():
    selected = {}
    used = set()
    for row in base.parse_rows():
        target = row["actor"]
        data = base.fetch_report(row["report_id"])
        base.normalize_report(data)
        for kyoku_index, kyoku in enumerate(data["pred"]):
            start = kyoku[0].get("info", {}).get("msg", {})
            hands = [list(h) for h in start.get("tehais", [[], [], [], []])]
            discards = [[], [], [], []]
            melds = [[], [], [], []]
            open_melds = [0, 0, 0, 0]
            reached = [False, False, False, False]
            dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []

            for pos, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")

                if msg_type == "dora" and msg.get("dora_marker"):
                    dora_markers.append(msg["dora_marker"])

                if msg_type == "tsumo":
                    hands[actor].append(msg["pai"])
                    if actor == target and "dahai_pred" in state and msg.get("real_dahai") not in (None, "?"):
                        try_discard_points(selected, used, row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, open_melds)
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type in base.HURO_TYPES:
                    try_call_points(selected, used, row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers)
                    consumed = msg.get("consumed", [])
                    call_tiles = consumed + ([msg.get("pai")] if msg.get("pai") else [])
                    melds[actor].append(" ".join(call_tiles))
                    open_melds[actor] += 1
                    for tile in consumed:
                        remove_tile(hands[actor], tile)
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type == "ankan":
                    consumed = msg.get("consumed", [])
                    melds[actor].append(" ".join(consumed))
                    open_melds[actor] += 1
                    for tile in consumed:
                        remove_tile(hands[actor], tile)

                elif msg_type == "kakan":
                    tile = msg.get("pai")
                    if tile:
                        melds[actor].append(f"+ {tile}")
                        remove_tile(hands[actor], tile)

                elif msg_type == "reach":
                    if actor is not None:
                        reached[actor] = True

                elif msg_type == "dahai":
                    tile = msg.get("pai")
                    if actor is not None and tile:
                        discards[actor].append(tile)

                if len(selected) == len(POINT_TEXT):
                    return selected
    return selected


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = collect_examples()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [key for key in sorted(POINT_TEXT) if key not in data]
    print(f"wrote {OUT}; examples={len(data)} missing={missing}")


if __name__ == "__main__":
    main()
