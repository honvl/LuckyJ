#!/usr/bin/env python3
"""Third-pass honor mining: child-only HONOR-HANDLING prescriptions plus dealer comparison."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mahjong.shanten import Shanten

import analyze_luckyj as base
from extract_case_studies import counts_34
import mine_rx_honors as pass1
import mine_rx2_honors as pass2


ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx3-honors.json")
SHANTEN = Shanten()

WINDS = ["E", "S", "W", "N"]
DRAGONS = {"P", "F", "C"}
HONORS = set(WINDS) | DRAGONS
HONOR_IDXS = [base.IDX[tile] for tile in ["E", "S", "W", "N", "P", "F", "C"]]
TURN_BUCKETS = [
    ("1-3", 1, 3),
    ("4-6", 4, 6),
    ("7-9", 7, 9),
    ("10-12", 10, 12),
    ("13+", 13, 99),
]
THREAT_LEVELS = ["none", "open_threat", "riichi"]
VISIBLE_BUCKETS = [0, 1, 2, 3]
OPEN_CONTEXTS = ["no_opponent_open", "some_opponent_open"]
MIN_CELL_N = 150


# ---------------------------------------------------------------------------
# Small stat helpers


def pct(num: int | float, den: int | float) -> float | None:
    if not den:
        return None
    return round(100.0 * float(num) / float(den), 1)


def round2(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def clean_number(value: float | int | None, digits: int = 1) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, float):
        return round(value, digits)
    return value


def nearest_rank(values: list[int | float], q: float) -> int | float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


def median_value(values: list[int | float]) -> float | int | None:
    if not values:
        return None
    return clean_number(statistics.median(sorted(values)))


def summarize_turns(turns: list[int]) -> dict[str, Any]:
    ordered = sorted(turns)
    return {
        "n": len(ordered),
        "p25": nearest_rank(ordered, 0.25),
        "median": median_value(ordered),
        "p75": nearest_rank(ordered, 0.75),
        "min": ordered[0] if ordered else None,
        "max": ordered[-1] if ordered else None,
    }


def ci95_half_width_pp(successes: int, n: int) -> float | None:
    if n <= 0:
        return None
    p = successes / n
    return 1.96 * math.sqrt(p * (1.0 - p) / n) * 100.0


def rate_payload(successes: int, n: int, name: str) -> dict[str, Any]:
    return {
        "n": n,
        f"{name}_n": successes,
        f"{name}_rate_pct": pct(successes, n),
        "ci95_half_width_pp": round2(ci95_half_width_pp(successes, n)),
    }


def pct_obj(numerator: int, denominator: int) -> dict[str, Any]:
    return {"count": numerator, "n": denominator, "pct": pct(numerator, denominator)}


# ---------------------------------------------------------------------------
# Tile, replay, and feature helpers


def valid_actor(actor: Any) -> bool:
    return isinstance(actor, int) and 0 <= actor < 4


def safe_tile_id(tile: str | None) -> int | None:
    if not tile or tile == "?":
        return None
    try:
        return base.tile_index(tile)
    except Exception:
        return None


def tile_name(idx: int) -> str:
    return base.TILES[idx]


def remove_tile(hand: list[str], tile: str | None) -> bool:
    if not tile or tile == "?":
        return False
    if tile in hand:
        hand.remove(tile)
        return True
    idx = safe_tile_id(tile)
    if idx is None:
        return False
    for item in list(hand):
        if safe_tile_id(item) == idx:
            hand.remove(item)
            return True
    return False


def count_tile(hand: list[str], idx: int) -> int:
    return sum(1 for tile in hand if safe_tile_id(tile) == idx)


def hand_counter(hand: list[str]) -> Counter[int]:
    counter: Counter[int] = Counter()
    for tile in hand:
        idx = safe_tile_id(tile)
        if idx is not None:
            counter[idx] += 1
    return counter


def shanten_value(tiles: list[str]) -> int | None:
    try:
        return SHANTEN.calculate_shanten(counts_34(tiles))
    except Exception:
        return None


def shanten_a_bucket(value: int | None) -> str:
    if value is None:
        return "unknown"
    return "<=2" if value <= 2 else ">=3"


def shanten_b_bucket(value: int | None) -> str:
    if value is None:
        return "unknown"
    return "0-1" if value <= 1 else "2+"


def seat_wind(start: dict[str, Any], seat: int) -> str:
    return WINDS[(seat - int(start.get("oya", 0))) % 4]


def yakuhai_for_seat(start: dict[str, Any], seat: int) -> set[str]:
    return DRAGONS | {start.get("bakaze"), seat_wind(start, seat)}


def guest_winds_for_seat(start: dict[str, Any], seat: int) -> set[str]:
    return set(WINDS) - {start.get("bakaze"), seat_wind(start, seat)}


def honor_type_for_start(start: dict[str, Any], target: int, tile: str) -> str:
    if tile in DRAGONS:
        return "dragon"
    round_wind = start.get("bakaze")
    own_wind = seat_wind(start, target)
    if tile == round_wind and tile == own_wind:
        return "double_wind"
    if tile == round_wind:
        return "round_wind"
    if tile == own_wind:
        return "seat_wind"
    return "guest_wind"


def turn_bucket(turn: int) -> str:
    for label, lo, hi in TURN_BUCKETS:
        if lo <= turn <= hi:
            return label
    return "13+"


def meld_tiles(meld: list[str] | dict[str, Any] | str) -> list[str]:
    if isinstance(meld, dict):
        return [tile for tile in meld.get("tiles", []) if tile and tile != "+"]
    if isinstance(meld, list):
        return [tile for tile in meld if tile and tile != "+"]
    return [tile for tile in str(meld).split() if tile and tile != "+"]


def visible_elsewhere_count(
    idx: int,
    target: int,
    discards: list[list[str]],
    melds: list[list[list[str]]],
    dora_markers: list[str],
) -> int:
    count = 0
    for marker in dora_markers:
        if safe_tile_id(marker) == idx:
            count += 1
    for seat, river in enumerate(discards):
        if seat == target:
            continue
        for tile in river:
            if safe_tile_id(tile) == idx:
                count += 1
    for player_melds in melds:
        for meld in player_melds:
            for tile in meld_tiles(meld):
                if safe_tile_id(tile) == idx:
                    count += 1
    return min(count, 3)


def visible_in_opponent_rivers_by_now(idx: int, target: int, discards: list[list[str]]) -> int:
    count = 0
    for seat, river in enumerate(discards):
        if seat == target:
            continue
        for tile in river:
            if safe_tile_id(tile) == idx:
                count += 1
    return count


def threat_level(target: int, reached: list[bool], open_melds: list[int]) -> str:
    if any(seat != target and reached[seat] for seat in range(4)):
        return "riichi"
    if any(seat != target and open_melds[seat] >= 2 for seat in range(4)):
        return "open_threat"
    return "none"


def opponent_open_context(target: int, open_melds: list[int]) -> tuple[str, int]:
    total = sum(open_melds[seat] for seat in range(4) if seat != target)
    return ("some_opponent_open" if total else "no_opponent_open"), total


def opponent_riichi(target: int, reached: list[bool]) -> bool:
    return any(seat != target and reached[seat] for seat in range(4))


def primary_riichi_player(target: int, reached: list[bool], reach_order: list[int]) -> int | None:
    for seat in reach_order:
        if seat != target and seat < len(reached) and reached[seat]:
            return seat
    for seat in range(4):
        if seat != target and reached[seat]:
            return seat
    return None


def genbutsu_count_in_hand(hand: list[str], riichi_player: int | None, discards: list[list[str]]) -> int | None:
    if riichi_player is None:
        return None
    safe_idxs = {safe_tile_id(tile) for tile in discards[riichi_player]}
    safe_idxs.discard(None)
    return sum(1 for tile in hand if safe_tile_id(tile) in safe_idxs)


def count_bucket_0_1_2plus(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "0"
    if value == 1:
        return "1"
    return "2+"


# ---------------------------------------------------------------------------
# Start records and replay collectors


def initial_cleanup_records(row: dict[str, Any], kyoku_index: int, start: dict[str, Any], target: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    hand = list(start.get("tehais", [[], [], [], []])[target])
    counts = hand_counter(hand)
    yakuhai = yakuhai_for_seat(start, target)
    guests = guest_winds_for_seat(start, target)
    dealer = int(start.get("oya", -1)) == target
    for tile in sorted(HONORS, key=lambda t: base.IDX[t]):
        idx = base.IDX[tile]
        if counts[idx] != 1:
            continue
        if tile in DRAGONS:
            kind = "dragon"
        elif tile in yakuhai:
            kind = "value_wind"
        elif tile in guests:
            kind = "guest_wind"
        else:
            continue
        records.append(
            {
                "game": row.get("idx"),
                "report_id": row.get("report_id"),
                "kyoku_index": kyoku_index,
                "target": target,
                "tile": tile,
                "tile_idx": idx,
                "kind": kind,
                "honor_type": honor_type_for_start(start, target, tile),
                "is_dealer": "dealer" if dealer else "child",
                "first_discard_turn": None,
                "discard_open_context": None,
                "discard_opponent_melds": None,
                "discard_any_riichi": None,
                "discard_msg_type": None,
                "paired_before_cut": False,
                "paired_turn": None,
                "max_decision_turn": 0,
                "total_luckyj_turns": 0,
                "turn3_shanten": None,
                "turn3_shanten_bucket": "unknown",
                "turn3_another_copy_in_opponent_rivers": None,
                "turn3_another_copy_bucket": "unknown",
                "outcome": None,
            }
        )
    return records


def mark_decision_turn(records: list[dict[str, Any]], turn: int) -> None:
    for record in records:
        if record["first_discard_turn"] is None:
            record["max_decision_turn"] = max(record["max_decision_turn"], turn)


def mark_total_turn(records: list[dict[str, Any]], turn: int) -> None:
    for record in records:
        record["total_luckyj_turns"] = max(record["total_luckyj_turns"], turn)


def mark_pair_draw(records: list[dict[str, Any]], drawn_idx: int | None, hands: list[list[str]], target: int, turn: int) -> None:
    if drawn_idx is None:
        return
    for record in records:
        if record["tile_idx"] != drawn_idx or record["first_discard_turn"] is not None:
            continue
        if not record["paired_before_cut"] and count_tile(hands[target], drawn_idx) >= 2:
            record["paired_before_cut"] = True
            record["paired_turn"] = turn


def mark_turn3_snapshot(records: list[dict[str, Any]], hand: list[str], target: int, discards: list[list[str]]) -> None:
    shanten = shanten_value(hand)
    for record in records:
        if record["turn3_shanten"] is None:
            record["turn3_shanten"] = shanten
            record["turn3_shanten_bucket"] = shanten_a_bucket(shanten)
            visible = visible_in_opponent_rivers_by_now(record["tile_idx"], target, discards)
            record["turn3_another_copy_in_opponent_rivers"] = visible
            record["turn3_another_copy_bucket"] = "1+" if visible >= 1 else "0"


def mark_cleanup_discard(
    records: list[dict[str, Any]],
    discard: str | None,
    turn: int,
    target: int,
    open_melds: list[int],
    reached: list[bool],
    msg_type: str,
) -> None:
    discard_idx = safe_tile_id(discard)
    if discard_idx is None:
        return
    open_context, total_melds = opponent_open_context(target, open_melds)
    any_riichi = opponent_riichi(target, reached)
    for record in records:
        if record["tile_idx"] != discard_idx or record["first_discard_turn"] is not None:
            continue
        record["first_discard_turn"] = turn
        record["discard_open_context"] = open_context
        record["discard_opponent_melds"] = total_melds
        record["discard_any_riichi"] = any_riichi
        record["discard_msg_type"] = msg_type


def finalize_cleanup_records(records: list[dict[str, Any]], hands: list[list[str]], target: int) -> None:
    for record in records:
        if record["first_discard_turn"] is not None:
            record["outcome"] = "discarded_after_pair" if record["paired_before_cut"] else "discarded_lone"
        elif record["paired_before_cut"]:
            record["outcome"] = "paired_up_later"
        elif count_tile(hands[target], record["tile_idx"]) > 0:
            record["outcome"] = "kept_to_end"
        else:
            record["outcome"] = "hand_ended_or_consumed"


def process_matrix_opportunities(
    matrix: dict[tuple[str, int, str], Counter[str]],
    hand: list[str],
    real_dahai: str,
    turn: int,
    target: int,
    discards: list[list[str]],
    melds: list[list[list[str]]],
    dora_markers: list[str],
    reached: list[bool],
    open_melds: list[int],
) -> None:
    counts = hand_counter(hand)
    discard_idx = safe_tile_id(real_dahai)
    bucket = turn_bucket(turn)
    threat = threat_level(target, reached, open_melds)
    for idx in HONOR_IDXS:
        if counts[idx] != 1:
            continue
        visible = visible_elsewhere_count(idx, target, discards, melds, dora_markers)
        key = (bucket, visible, threat)
        matrix[key]["n"] += 1
        if discard_idx == idx:
            matrix[key]["discard"] += 1


def process_bonus(
    bonus: Counter[str],
    drawn_tile: str | None,
    real_dahai: str | None,
    next_tsumogiri: Any,
    turn: int,
    target: int,
    discards: list[list[str]],
    melds: list[list[list[str]]],
    dora_markers: list[str],
    reached: list[bool],
) -> None:
    drawn_idx = safe_tile_id(drawn_tile)
    if drawn_idx is None or drawn_idx not in HONOR_IDXS:
        return
    if turn <= 12 or not opponent_riichi(target, reached):
        return
    visible = visible_elsewhere_count(drawn_idx, target, discards, melds, dora_markers)
    if visible > 1:
        return
    real_idx = safe_tile_id(real_dahai)
    bonus["n"] += 1
    if real_idx == drawn_idx and (next_tsumogiri is True or next_tsumogiri is None):
        bonus["immediate_tsumogiri"] += 1
    elif real_idx == drawn_idx:
        bonus["same_honor_cut_not_tsumogiri_flagged"] += 1
        bonus["immediate_same_type_cut"] += 1
    else:
        bonus["held"] += 1


def collect_b_opportunities(
    opportunities: list[dict[str, Any]],
    hand: list[str],
    real_dahai: str,
    turn: int,
    target: int,
    discards: list[list[str]],
    melds: list[list[list[str]]],
    dora_markers: list[str],
    reached: list[bool],
    reach_order: list[int],
) -> None:
    if turn < 7 or not opponent_riichi(target, reached):
        return
    primary = primary_riichi_player(target, reached, reach_order)
    shanten = shanten_value(hand)
    genbutsu_count = genbutsu_count_in_hand(hand, primary, discards)
    discard_idx = safe_tile_id(real_dahai)
    counts = hand_counter(hand)
    for idx in HONOR_IDXS:
        if counts[idx] != 1:
            continue
        if visible_elsewhere_count(idx, target, discards, melds, dora_markers) != 0:
            continue
        opportunities.append(
            {
                "turn": turn,
                "turn_bucket": turn_bucket(turn),
                "tile": tile_name(idx),
                "tile_idx": idx,
                "discard_live_honor": discard_idx == idx,
                "own_shanten": shanten,
                "own_shanten_bucket": shanten_b_bucket(shanten),
                "genbutsu_count_vs_riichi": genbutsu_count,
                "genbutsu_bucket": count_bucket_0_1_2plus(genbutsu_count),
            }
        )


def collect_hypothesis_decision(hypothesis: dict[str, Counter[str]], state: dict[str, Any], start: dict[str, Any], target: int) -> bool:
    msg = state.get("info", {}).get("msg", {})
    if msg.get("actor") != target or "dahai_pred" not in state:
        return False
    actual = msg.get("real_dahai")
    if not actual or actual == "?" or msg.get("reached"):
        return False
    preds = state.get("dahai_pred") or []
    if not preds:
        return False
    probs = preds[0]
    try:
        top, _top_prob = base.top_tile(probs)
        actual_prob = base.prob_for(probs, actual)
    except Exception:
        return False
    split = "dealer" if int(start.get("oya", -1)) == target else "child"
    counter = hypothesis[split]
    counter["n"] += 1
    if top == actual:
        counter["top_match"] += 1
    else:
        counter["top_mismatch"] += 1
        if actual_prob < 0.05:
            counter["severe_mismatch_cheap_actual"] += 1
    return True


def process_kyoku(row: dict[str, Any], kyoku_index: int, kyoku: list[dict[str, Any]], hypothesis: dict[str, Counter[str]]) -> dict[str, Any] | None:
    target = row.get("actor")
    if not valid_actor(target) or not kyoku:
        return None
    start = kyoku[0].get("info", {}).get("msg", {})
    tehais = start.get("tehais")
    if start.get("type") != "start_kyoku" or not isinstance(tehais, list) or len(tehais) != 4:
        return None

    hands = [list(hand) for hand in tehais]
    discards: list[list[str]] = [[], [], [], []]
    melds: list[list[list[str]]] = [[], [], [], []]
    open_melds = [0, 0, 0, 0]
    reached = [False, False, False, False]
    reach_order: list[int] = []
    dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []
    records = initial_cleanup_records(row, kyoku_index, start, target)
    matrix: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    bonus: Counter[str] = Counter()
    b_opportunities: list[dict[str, Any]] = []
    decisions = 0
    hypothesis_decisions = 0
    malformed = False
    is_dealer = int(start.get("oya", -1)) == target

    def remove_for_actor(actor: Any, tile: str | None) -> None:
        nonlocal malformed
        if not valid_actor(actor) or not tile or tile == "?":
            return
        ok = remove_tile(hands[actor], tile)
        if actor == target and not ok:
            malformed = True

    for state in kyoku:
        msg = state.get("info", {}).get("msg", {})
        actor = msg.get("actor")
        msg_type = msg.get("type")
        if collect_hypothesis_decision(hypothesis, state, start, target):
            hypothesis_decisions += 1

        if msg_type == "dora" and msg.get("dora_marker"):
            dora_markers.append(msg["dora_marker"])
            continue

        if msg_type == "tsumo":
            if not valid_actor(actor):
                continue
            drawn = msg.get("pai")
            if not drawn:
                if actor == target:
                    malformed = True
                continue
            hands[actor].append(drawn)
            if actor == target:
                turn = len(discards[target]) + 1
                mark_total_turn(records, turn)
                mark_pair_draw(records, safe_tile_id(drawn), hands, target, turn)
                if turn == 3:
                    mark_turn3_snapshot(records, hands[target], target, discards)
                real_dahai = msg.get("real_dahai")
                is_decision = real_dahai not in (None, "?") and not reached[target] and not msg.get("reached")
                if is_decision:
                    decisions += 1
                    mark_decision_turn(records, turn)
                    process_matrix_opportunities(matrix, hands[target], real_dahai, turn, target, discards, melds, dora_markers, reached, open_melds)
                    process_bonus(bonus, drawn, real_dahai, msg.get("next_tsumogiri"), turn, target, discards, melds, dora_markers, reached)
                    collect_b_opportunities(b_opportunities, hands[target], real_dahai, turn, target, discards, melds, dora_markers, reached, reach_order)
                    mark_cleanup_discard(records, real_dahai, turn, target, open_melds, reached, msg_type)
                if real_dahai not in (None, "?"):
                    remove_for_actor(actor, real_dahai)

        elif msg_type in base.HURO_TYPES:
            if not valid_actor(actor):
                continue
            real_dahai = msg.get("real_dahai")
            consumed = msg.get("consumed") or []
            if actor == target and real_dahai not in (None, "?"):
                turn = len(discards[target]) + 1
                mark_total_turn(records, turn)
                huro_hand = list(hands[target])
                for tile in consumed:
                    remove_tile(huro_hand, tile)
                if turn == 3:
                    mark_turn3_snapshot(records, huro_hand, target, discards)
                if not reached[target]:
                    decisions += 1
                    mark_decision_turn(records, turn)
                    mark_cleanup_discard(records, real_dahai, turn, target, open_melds, reached, msg_type)
            call_tiles = [tile for tile in consumed if tile]
            if msg.get("pai"):
                call_tiles.append(msg.get("pai"))
            melds[actor].append(call_tiles)
            open_melds[actor] += 1
            for tile in consumed:
                remove_for_actor(actor, tile)
            if real_dahai not in (None, "?"):
                remove_for_actor(actor, real_dahai)

        elif msg_type == "ankan":
            if not valid_actor(actor):
                continue
            consumed = msg.get("consumed") or []
            melds[actor].append([tile for tile in consumed if tile])
            open_melds[actor] += 1
            for tile in consumed:
                remove_for_actor(actor, tile)

        elif msg_type == "kakan":
            if not valid_actor(actor):
                continue
            tile = msg.get("pai")
            if tile:
                melds[actor].append([tile])
                remove_for_actor(actor, tile)

        elif msg_type == "reach":
            if valid_actor(actor):
                reached[actor] = True
                if actor not in reach_order:
                    reach_order.append(actor)

        elif msg_type == "dahai":
            tile = msg.get("pai")
            if valid_actor(actor) and tile:
                discards[actor].append(tile)

        if malformed:
            return None

    finalize_cleanup_records(records, hands, target)
    return {
        "is_dealer": is_dealer,
        "records": records,
        "matrix": matrix,
        "bonus": bonus,
        "b_opportunities": b_opportunities,
        "decisions": decisions,
        "hypothesis_decisions": hypothesis_decisions,
    }


# ---------------------------------------------------------------------------
# Summaries


def summarize_cleanup_family(records: list[dict[str, Any]], kinds: list[str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for kind in kinds:
        subset = [record for record in records if record["kind"] == kind]
        discarded = [record for record in subset if record["first_discard_turn"] is not None]
        outcomes = Counter(record["outcome"] for record in subset)
        kind_summary: dict[str, Any] = {
            "n_start_singletons": len(subset),
            "discard_turn_all": summarize_turns([int(record["first_discard_turn"]) for record in discarded]),
            "discarded_pct": pct_obj(len(discarded), len(subset)),
            "never_cut_pct": pct_obj(sum(1 for record in subset if record["first_discard_turn"] is None), len(subset)),
            "paired_before_cut_pct": pct_obj(sum(1 for record in subset if record["paired_before_cut"]), len(subset)),
            "outcomes": {outcome: {"count": count, "n": len(subset), "pct": pct(count, len(subset))} for outcome, count in sorted(outcomes.items())},
            "by_discard_opponent_open_context": {},
        }
        for context in OPEN_CONTEXTS:
            cell_discards = [record for record in discarded if record["discard_open_context"] == context]
            riichi_count = sum(1 for record in cell_discards if record["discard_any_riichi"])
            kind_summary["by_discard_opponent_open_context"][context] = {
                "n_start_singletons": len(subset),
                "n_discarded_in_context": len(cell_discards),
                "discard_turn": summarize_turns([int(record["first_discard_turn"]) for record in cell_discards]),
                "discarded_here_pct_of_start_singletons": pct_obj(len(cell_discards), len(subset)),
                "riichi_at_discard_pct": pct_obj(riichi_count, len(cell_discards)),
            }
        output[kind] = kind_summary
    return output


def summarize_guest(records: list[dict[str, Any]]) -> dict[str, Any]:
    subset = [record for record in records if record["kind"] == "guest_wind"]
    discarded = [record for record in subset if record["first_discard_turn"] is not None]
    eligible_turn6 = [
        record
        for record in subset
        if (record["first_discard_turn"] is not None and record["first_discard_turn"] <= 6) or record["max_decision_turn"] >= 6
    ]
    kept_past_6 = [record for record in eligible_turn6 if record["first_discard_turn"] is None or record["first_discard_turn"] > 6]
    by_context: dict[str, Any] = {}
    for context in OPEN_CONTEXTS:
        cell_discards = [record for record in discarded if record["discard_open_context"] == context]
        by_context[context] = {
            "n_start_singletons": len(subset),
            "n_discarded_in_context": len(cell_discards),
            "discard_turn": summarize_turns([int(record["first_discard_turn"]) for record in cell_discards]),
            "discarded_here_pct_of_start_singletons": pct_obj(len(cell_discards), len(subset)),
        }
    outcomes = Counter(record["outcome"] for record in subset)
    return {
        "n_start_singletons": len(subset),
        "discard_turn_all": summarize_turns([int(record["first_discard_turn"]) for record in discarded]),
        "discarded_pct": pct_obj(len(discarded), len(subset)),
        "never_cut_pct": pct_obj(sum(1 for record in subset if record["first_discard_turn"] is None), len(subset)),
        "paired_before_cut_pct": pct_obj(sum(1 for record in subset if record["paired_before_cut"]), len(subset)),
        "kept_past_turn6_pct": pct_obj(len(kept_past_6), len(eligible_turn6)),
        "outcomes": {outcome: {"count": count, "n": len(subset), "pct": pct(count, len(subset))} for outcome, count in sorted(outcomes.items())},
        "by_discard_opponent_open_context": by_context,
    }


def summarize_matrix(matrix: dict[tuple[str, int, str], Counter[str]]) -> dict[str, Any]:
    cells = []
    nested: dict[str, Any] = {}
    for bucket, _, _ in TURN_BUCKETS:
        nested[bucket] = {}
        for visible in VISIBLE_BUCKETS:
            nested[bucket][str(visible)] = {}
            for threat in THREAT_LEVELS:
                counter = matrix.get((bucket, visible, threat), Counter())
                n = int(counter.get("n", 0))
                discard_n = int(counter.get("discard", 0))
                cell = {
                    "turn_bucket": bucket,
                    "visible_copies": visible,
                    "threat_level": threat,
                    "n": n,
                    "discard_n": discard_n,
                    "hold_n": n - discard_n,
                    "discard_rate_pct": pct(discard_n, n),
                }
                cells.append(cell)
                nested[bucket][str(visible)][threat] = cell
    return {"cells": cells, "nested": nested}


def summarize_bonus(bonus: Counter[str]) -> dict[str, Any]:
    n = int(bonus.get("n", 0))
    immediate = int(bonus.get("immediate_tsumogiri", 0))
    same_type = int(bonus.get("immediate_same_type_cut", 0))
    held = int(bonus.get("held", 0))
    not_flagged = int(bonus.get("same_honor_cut_not_tsumogiri_flagged", 0))
    return {
        "n": n,
        "immediate_tsumogiri_n": immediate,
        "immediate_tsumogiri_pct": pct(immediate, n),
        "immediate_same_type_cut_n": same_type,
        "immediate_same_type_cut_pct": pct(same_type, n),
        "held_n": held,
        "held_pct": pct(held, n),
        "same_honor_cut_not_tsumogiri_flagged_n": not_flagged,
    }


def summarize_core_matrix_and_bonus(matrix_summary: dict[str, Any], bonus_summary: dict[str, Any]) -> dict[str, Any]:
    def cell(bucket: str, visible: int, threat: str) -> dict[str, Any]:
        src = matrix_summary["nested"][bucket][str(visible)][threat]
        return {"n": src["n"], "discard_n": src["discard_n"], "discard_rate_pct": src["discard_rate_pct"]}

    return {
        "under_riichi_turns_7_9_visible_0": cell("7-9", 0, "riichi"),
        "under_riichi_turns_7_9_visible_1": cell("7-9", 1, "riichi"),
        "under_riichi_turns_13plus_visible_0": cell("13+", 0, "riichi"),
        "under_riichi_turns_13plus_visible_1": cell("13+", 1, "riichi"),
        "late_live_honor_draw_hold_rate": {
            "n": bonus_summary["n"],
            "held_n": bonus_summary["held_n"],
            "held_pct": bonus_summary["held_pct"],
        },
    }


def cut_by6_event(record: dict[str, Any]) -> dict[str, Any] | None:
    if record.get("kind") not in {"dragon", "value_wind"}:
        return None
    if int(record.get("total_luckyj_turns") or 0) < 6:
        return None
    paired_turn = record.get("paired_turn")
    first_turn = record.get("first_discard_turn")
    if paired_turn is not None and paired_turn <= 6 and (first_turn is None or first_turn > 6):
        return None
    return {**record, "cut_by_turn6": first_turn is not None and first_turn <= 6, "cut_turn": first_turn}


def condition_effects(
    events: list[dict[str, Any]],
    condition_key: str,
    values: list[str],
    outcome_key: str,
    outcome_name: str,
    include_median_turn: bool = False,
) -> dict[str, Any]:
    filtered = [event for event in events if event.get(condition_key) in values]
    cells: list[dict[str, Any]] = []
    for value in values:
        cell_events = [event for event in filtered if event.get(condition_key) == value]
        comp_events = [event for event in filtered if event.get(condition_key) != value]
        n = len(cell_events)
        yes = sum(1 for event in cell_events if event.get(outcome_key))
        comp_n = len(comp_events)
        comp_yes = sum(1 for event in comp_events if event.get(outcome_key))
        p = yes / n if n else None
        comp_p = comp_yes / comp_n if comp_n else None
        delta = (p - comp_p) * 100.0 if p is not None and comp_p is not None else None
        ci = ci95_half_width_pp(yes, n)
        comp_ci = ci95_half_width_pp(comp_yes, comp_n)
        combined_ci = math.sqrt((ci or 0.0) ** 2 + (comp_ci or 0.0) ** 2) if ci is not None and comp_ci is not None else None
        small_sample = n < MIN_CELL_N or comp_n < MIN_CELL_N
        significant = bool(delta is not None and combined_ci is not None and not small_sample and abs(delta) > combined_ci)
        payload: dict[str, Any] = {
            "condition": condition_key,
            "value": value,
            **rate_payload(yes, n, outcome_name),
            "complement_n": comp_n,
            "complement_success_n": comp_yes,
            "complement_rate_pct": pct(comp_yes, comp_n),
            "complement_ci95_half_width_pp": round2(comp_ci),
            "delta_pp_vs_complement": round2(delta),
            "combined_ci95_half_width_pp": round2(combined_ci),
            "significant": significant,
            "small_sample": small_sample,
            "minimum_cell_n": MIN_CELL_N,
        }
        if include_median_turn:
            turns = [int(event["cut_turn"]) for event in cell_events if event.get("cut_turn") is not None]
            payload["median_cut_turn"] = {"n": len(turns), "value": median_value(turns)}
        cells.append(payload)
    cells.sort(key=lambda item: (abs(item["delta_pp_vs_complement"] or 0.0), item["n"]), reverse=True)
    return {"condition": condition_key, "n": len(filtered), "cells_sorted_by_abs_delta_pp": cells}


def baseline_rate(events: list[dict[str, Any]], outcome_key: str, outcome_name: str) -> dict[str, Any]:
    n = len(events)
    yes = sum(1 for event in events if event.get(outcome_key))
    return rate_payload(yes, n, outcome_name)


def summarize_condition_effects_a(records: list[dict[str, Any]]) -> dict[str, Any]:
    events = [event for record in records if (event := cut_by6_event(record)) is not None]
    return {
        "baseline": baseline_rate(events, "cut_by_turn6", "cut_by_turn6"),
        "denominator_note": "Child-only lone dragon/value-wind starting singleton records in rounds with at least 6 LuckyJ turns, excluding starts that paired before/at turn 6 before being cut.",
        "effects": [
            condition_effects(events, "turn3_shanten_bucket", ["<=2", ">=3"], "cut_by_turn6", "cut_by_turn6", True),
            condition_effects(events, "honor_type", ["double_wind", "round_wind", "seat_wind", "dragon"], "cut_by_turn6", "cut_by_turn6", True),
        ],
    }


def summarize_condition_effects_b(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "baseline": baseline_rate(opportunities, "discard_live_honor", "discard_live_honor"),
        "denominator_note": "Child-only turn-7+ tsumo discard decisions while any opponent riichi is active; each held honor tile type with exactly one copy and 0 visible copies outside LuckyJ's hand is one opportunity.",
        "effects": [
            condition_effects(opportunities, "own_shanten_bucket", ["0-1", "2+"], "discard_live_honor", "discard_live_honor"),
            condition_effects(opportunities, "genbutsu_bucket", ["0", "1", "2+"], "discard_live_honor", "discard_live_honor"),
        ],
    }


def split_summary(records: list[dict[str, Any]], matrix: dict[tuple[str, int, str], Counter[str]], bonus: Counter[str]) -> dict[str, Any]:
    yak = summarize_cleanup_family(records, ["dragon", "value_wind"])
    guest = summarize_guest(records)
    matrix_summary = summarize_matrix(matrix)
    bonus_summary = summarize_bonus(bonus)
    return {
        "lone_yakuhai_cleanup_timing": {"summary_by_kind_and_opponent_open": yak},
        "guest_wind_cleanup": guest,
        "stop_matching_honors_matrix": matrix_summary,
        "bonus_late_live_honor_draw_under_riichi": bonus_summary,
        "headline_core_cells": summarize_core_matrix_and_bonus(matrix_summary, bonus_summary),
    }


def summarize_hypothesis(hypothesis: dict[str, Counter[str]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for split in ["dealer", "child"]:
        counter = hypothesis[split]
        n = int(counter.get("n", 0))
        match = int(counter.get("top_match", 0))
        severe = int(counter.get("severe_mismatch_cheap_actual", 0))
        output[split] = {
            "n": n,
            "top_match_n": match,
            "top_match_rate_pct": pct(match, n),
            "top_match_ci95_half_width_pp": round2(ci95_half_width_pp(match, n)),
            "severe_mismatch_cheap_actual_n": severe,
            "severe_mismatch_cheap_actual_rate_pct": pct(severe, n),
            "severe_mismatch_cheap_actual_ci95_half_width_pp": round2(ci95_half_width_pp(severe, n)),
        }
    dealer_rate = output["dealer"]["top_match_rate_pct"]
    child_rate = output["child"]["top_match_rate_pct"]
    dealer_severe = output["dealer"]["severe_mismatch_cheap_actual_rate_pct"]
    child_severe = output["child"]["severe_mismatch_cheap_actual_rate_pct"]
    output["delta_dealer_minus_child"] = {
        "top_match_pp": round2(dealer_rate - child_rate) if dealer_rate is not None and child_rate is not None else None,
        "severe_mismatch_cheap_actual_pp": round2(dealer_severe - child_severe) if dealer_severe is not None and child_severe is not None else None,
    }
    return output


def get_path(obj: dict[str, Any], path: list[str]) -> Any:
    cur: Any = obj
    for key in path:
        if cur is None or not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def delta_summary(child: dict[str, Any], dealer: dict[str, Any]) -> dict[str, Any]:
    specs = {
        "lone_dragon_quiet_median_turn": ["lone_yakuhai_cleanup_timing", "summary_by_kind_and_opponent_open", "dragon", "by_discard_opponent_open_context", "no_opponent_open", "discard_turn", "median"],
        "lone_dragon_after_open_median_turn": ["lone_yakuhai_cleanup_timing", "summary_by_kind_and_opponent_open", "dragon", "by_discard_opponent_open_context", "some_opponent_open", "discard_turn", "median"],
        "value_wind_quiet_median_turn": ["lone_yakuhai_cleanup_timing", "summary_by_kind_and_opponent_open", "value_wind", "by_discard_opponent_open_context", "no_opponent_open", "discard_turn", "median"],
        "value_wind_after_open_median_turn": ["lone_yakuhai_cleanup_timing", "summary_by_kind_and_opponent_open", "value_wind", "by_discard_opponent_open_context", "some_opponent_open", "discard_turn", "median"],
        "dragon_paired_before_cut_pct": ["lone_yakuhai_cleanup_timing", "summary_by_kind_and_opponent_open", "dragon", "paired_before_cut_pct", "pct"],
        "value_wind_paired_before_cut_pct": ["lone_yakuhai_cleanup_timing", "summary_by_kind_and_opponent_open", "value_wind", "paired_before_cut_pct", "pct"],
        "guest_wind_median_turn": ["guest_wind_cleanup", "discard_turn_all", "median"],
        "guest_wind_p75_turn": ["guest_wind_cleanup", "discard_turn_all", "p75"],
        "guest_wind_kept_past_turn6_pct": ["guest_wind_cleanup", "kept_past_turn6_pct", "pct"],
        "riichi_7_9_v0_discard_rate_pct": ["headline_core_cells", "under_riichi_turns_7_9_visible_0", "discard_rate_pct"],
        "riichi_7_9_v1_discard_rate_pct": ["headline_core_cells", "under_riichi_turns_7_9_visible_1", "discard_rate_pct"],
        "riichi_13plus_v0_discard_rate_pct": ["headline_core_cells", "under_riichi_turns_13plus_visible_0", "discard_rate_pct"],
        "riichi_13plus_v1_discard_rate_pct": ["headline_core_cells", "under_riichi_turns_13plus_visible_1", "discard_rate_pct"],
        "late_live_honor_draw_hold_pct": ["headline_core_cells", "late_live_honor_draw_hold_rate", "held_pct"],
    }
    out: dict[str, Any] = {}
    for name, path in specs.items():
        c = get_path(child, path)
        d = get_path(dealer, path)
        out[name] = {"child": c, "dealer": d, "child_minus_dealer": round2(c - d) if isinstance(c, (int, float)) and isinstance(d, (int, float)) else None}
    return out


def effect_cell(summary: dict[str, Any], section: str, condition: str, value: str) -> dict[str, Any] | None:
    for effect in summary.get(section, {}).get("effects", []):
        if effect.get("condition") != condition:
            continue
        for cell in effect.get("cells_sorted_by_abs_delta_pp", []):
            if cell.get("value") == value:
                return cell
    return None


def changed_vs_published(child_summary: dict[str, Any], child_conditions: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def add(name: str, published: float | int, current: Any, unit: str, n: int | None = None) -> None:
        moved = False
        delta = None
        if isinstance(current, (int, float)):
            delta = round2(float(current) - float(published))
            threshold = 1.0 if unit == "turn" else 2.0
            moved = abs(delta) >= threshold
        items.append({"name": name, "published": published, "child_only": current, "unit": unit, "n": n, "delta": delta, "moved_materially": moved})

    yak = child_summary["lone_yakuhai_cleanup_timing"]["summary_by_kind_and_opponent_open"]
    guest = child_summary["guest_wind_cleanup"]
    core = child_summary["headline_core_cells"]
    add("lone dragon quiet median", 3, yak["dragon"]["by_discard_opponent_open_context"]["no_opponent_open"]["discard_turn"]["median"], "turn", yak["dragon"]["by_discard_opponent_open_context"]["no_opponent_open"]["discard_turn"]["n"])
    add("lone dragon after-open median", 5, yak["dragon"]["by_discard_opponent_open_context"]["some_opponent_open"]["discard_turn"]["median"], "turn", yak["dragon"]["by_discard_opponent_open_context"]["some_opponent_open"]["discard_turn"]["n"])
    add("value wind quiet median", 3, yak["value_wind"]["by_discard_opponent_open_context"]["no_opponent_open"]["discard_turn"]["median"], "turn", yak["value_wind"]["by_discard_opponent_open_context"]["no_opponent_open"]["discard_turn"]["n"])
    add("value wind after-open median", 6, yak["value_wind"]["by_discard_opponent_open_context"]["some_opponent_open"]["discard_turn"]["median"], "turn", yak["value_wind"]["by_discard_opponent_open_context"]["some_opponent_open"]["discard_turn"]["n"])
    add("lone dragon paired before cut", 12, yak["dragon"]["paired_before_cut_pct"]["pct"], "pct", yak["dragon"]["paired_before_cut_pct"]["n"])
    add("value wind paired before cut", 11, yak["value_wind"]["paired_before_cut_pct"]["pct"], "pct", yak["value_wind"]["paired_before_cut_pct"]["n"])
    add("guest wind median", 1, guest["discard_turn_all"]["median"], "turn", guest["discard_turn_all"]["n"])
    add("guest wind p75", 3, guest["discard_turn_all"]["p75"], "turn", guest["discard_turn_all"]["n"])
    add("guest wind kept past turn 6", 15, guest["kept_past_turn6_pct"]["pct"], "pct", guest["kept_past_turn6_pct"]["n"])
    add("riichi T7-9 0-visible discard", 14, core["under_riichi_turns_7_9_visible_0"]["discard_rate_pct"], "pct", core["under_riichi_turns_7_9_visible_0"]["n"])
    add("riichi T7-9 1-visible discard", 35, core["under_riichi_turns_7_9_visible_1"]["discard_rate_pct"], "pct", core["under_riichi_turns_7_9_visible_1"]["n"])
    add("riichi T13+ 0-visible discard", 9, core["under_riichi_turns_13plus_visible_0"]["discard_rate_pct"], "pct", core["under_riichi_turns_13plus_visible_0"]["n"])
    add("riichi T13+ 1-visible discard", 36, core["under_riichi_turns_13plus_visible_1"]["discard_rate_pct"], "pct", core["under_riichi_turns_13plus_visible_1"]["n"])
    add("late live-honor draw hold", 50, core["late_live_honor_draw_hold_rate"]["held_pct"], "pct", core["late_live_honor_draw_hold_rate"]["n"])

    cell = effect_cell(child_conditions, "condition_effects_lone_yakuhai_cut_by_turn6", "turn3_shanten_bucket", "<=2")
    if cell:
        add("modifier cut-by-6 turn3 shanten <=2", 85, cell["cut_by_turn6_rate_pct"], "pct", cell["n"])
    cell = effect_cell(child_conditions, "condition_effects_lone_yakuhai_cut_by_turn6", "turn3_shanten_bucket", ">=3")
    if cell:
        add("modifier cut-by-6 turn3 shanten >=3", 63, cell["cut_by_turn6_rate_pct"], "pct", cell["n"])
    for label, published in [("double_wind", 59), ("round_wind", 78), ("seat_wind", 68)]:
        cell = effect_cell(child_conditions, "condition_effects_lone_yakuhai_cut_by_turn6", "honor_type", label)
        if cell:
            add(f"modifier cut-by-6 {label}", published, cell["cut_by_turn6_rate_pct"], "pct", cell["n"])
    cell = effect_cell(child_conditions, "condition_effects_stop_matching_live_honor_under_riichi_turn7plus", "own_shanten_bucket", "0-1")
    if cell:
        add("modifier live honor discard own shanten 0-1", 31, cell["discard_live_honor_rate_pct"], "pct", cell["n"])
    cell = effect_cell(child_conditions, "condition_effects_stop_matching_live_honor_under_riichi_turn7plus", "own_shanten_bucket", "2+")
    if cell:
        add("modifier live honor discard own shanten 2+", 5, cell["discard_live_honor_rate_pct"], "pct", cell["n"])
    for label, published in [("0", 20), ("2+", 9)]:
        cell = effect_cell(child_conditions, "condition_effects_stop_matching_live_honor_under_riichi_turn7plus", "genbutsu_bucket", label)
        if cell:
            add(f"modifier live honor discard genbutsu {label}", published, cell["discard_live_honor_rate_pct"], "pct", cell["n"])
    return items


def unique_rows_by_report_id(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unique: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for row in rows:
        report_id = row.get("report_id")
        if report_id in seen:
            kept = seen[report_id]
            duplicates.append({"report_id": report_id, "kept_idx": kept.get("idx"), "kept_actor": kept.get("actor"), "skipped_idx": row.get("idx"), "skipped_actor": row.get("actor")})
            continue
        seen[report_id] = row
        unique.append(row)
    return unique, duplicates


def main() -> None:
    source_rows = base.parse_rows()
    rows, duplicate_rows = unique_rows_by_report_id(source_rows)
    split_records: dict[str, list[dict[str, Any]]] = {"dealer": [], "child": []}
    split_matrix: dict[str, dict[tuple[str, int, str], Counter[str]]] = {"dealer": defaultdict(Counter), "child": defaultdict(Counter)}
    split_bonus: dict[str, Counter[str]] = {"dealer": Counter(), "child": Counter()}
    split_b_opps: dict[str, list[dict[str, Any]]] = {"dealer": [], "child": []}
    hypothesis: dict[str, Counter[str]] = {"dealer": Counter(), "child": Counter()}
    processed_reports = 0
    processed_kyoku = 0
    skipped_kyoku = 0
    decisions = 0
    hypothesis_decisions = 0

    for index, row in enumerate(rows, 1):
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
        except Exception as exc:  # noqa: BLE001 - batch miner; report and continue.
            print(f"skip report {row.get('idx')} {row.get('report_id')}: {exc}")
            continue
        processed_reports += 1
        for kyoku_index, kyoku in enumerate(data.get("pred", [])):
            mined = process_kyoku(row, kyoku_index, kyoku, hypothesis)
            if mined is None:
                skipped_kyoku += 1
                continue
            processed_kyoku += 1
            split = "dealer" if mined["is_dealer"] else "child"
            decisions += mined["decisions"]
            hypothesis_decisions += mined["hypothesis_decisions"]
            split_records[split].extend(mined["records"])
            split_b_opps[split].extend(mined["b_opportunities"])
            split_bonus[split].update(mined["bonus"])
            for key, counter in mined["matrix"].items():
                split_matrix[split][key].update(counter)
        if index % 200 == 0:
            print(f"processed {index}/{len(rows)} games; kyoku={processed_kyoku}; skipped_kyoku={skipped_kyoku}")

    child_summary = split_summary(split_records["child"], split_matrix["child"], split_bonus["child"])
    dealer_summary = split_summary(split_records["dealer"], split_matrix["dealer"], split_bonus["dealer"])
    child_conditions = {
        "condition_effects_lone_yakuhai_cut_by_turn6": summarize_condition_effects_a(split_records["child"]),
        "condition_effects_stop_matching_live_honor_under_riichi_turn7plus": summarize_condition_effects_b(split_b_opps["child"]),
    }
    dealer_conditions = {
        "condition_effects_lone_yakuhai_cut_by_turn6": summarize_condition_effects_a(split_records["dealer"]),
        "condition_effects_stop_matching_live_honor_under_riichi_turn7plus": summarize_condition_effects_b(split_b_opps["dealer"]),
    }

    output: dict[str, Any] = {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "repo_root": str(ROOT),
            "source_rows": len(source_rows),
            "unique_report_rows_analyzed": len(rows),
            "duplicate_report_rows_skipped": duplicate_rows,
            "reports_processed": processed_reports,
            "kyoku_processed": processed_kyoku,
            "kyoku_skipped_malformed": skipped_kyoku,
            "luckyj_decisions_processed_for_honor_replay": decisions,
            "all_decisions_processed_for_hypothesis_check": hypothesis_decisions,
            "child_cleanup_records": len(split_records["child"]),
            "dealer_cleanup_records": len(split_records["dealer"]),
            "child_stop_matching_live_honor_opportunities": len(split_b_opps["child"]),
            "dealer_stop_matching_live_honor_opportunities": len(split_b_opps["dealer"]),
        },
        "definitions": {
            "child_round": "A kyoku where LuckyJ is not oya/dealer at start_kyoku. This is the prescription base requested for the book.",
            "dealer_round": "A kyoku where LuckyJ is oya/dealer at start_kyoku, output side-by-side only for comparison.",
            "hypothesis_check_population": "All LuckyJ discard-prediction states with dahai_pred head 0 and real_dahai present before child/dealer filtering; riichi-declaration states with msg.reached are excluded, matching existing NAGA-decision miners.",
            "top_discard_match": "Nishiki/head-0 top tile from dahai_pred equals LuckyJ real_dahai.",
            "severe_mismatch_cheap_actual": "Nishiki/head-0 top tile differs from real_dahai and Nishiki assigns real_dahai probability < 0.05.",
            "turn_number": "For LuckyJ, len(discards[LuckyJ]) + 1 at the decision state, matching scripts/mine_rx_honors.py and scripts/mine_rx2_honors.py replay timing.",
            "lone_cleanup_population": "Honor tile types held exactly once in LuckyJ's starting hand; starting pairs/triples are excluded. dragon/value_wind/guest_wind use LuckyJ's round/seat winds.",
            "paired_before_cut": "LuckyJ drew another copy of that same honor before the first recorded decision discard of the tile.",
            "quiet_vs_after_open": "quiet means the first discard of the tracked honor occurred before any opponent had an open meld; after_open means at least one opponent meld existed at discard time.",
            "stop_matching_opportunity": "Every non-riichi LuckyJ tsumo discard decision, for each honor tile type LuckyJ holds exactly one copy of before discarding.",
            "visible_copies_for_matrix": "Copies outside LuckyJ's concealed hand: opponent rivers, all public melds, and current dora indicators. LuckyJ's own river is excluded. Counts are capped at 3.",
            "threat_level": "riichi if any opponent has reached; otherwise open_threat if any opponent has 2+ melds; otherwise none.",
            "late_live_honor_draw": "After turn 12, non-riichi LuckyJ tsumo decisions where LuckyJ drew an honor with 0-1 visible copies outside hand while at least one opponent riichi was active.",
            "cut_by_turn6": "For child condition-effect A, true if a starting singleton dragon/value wind's first tracked non-riichi discard turn is <=6. Denominator requires the kyoku to reach at least 6 LuckyJ turns and excludes starts that paired before/at turn 6 before being cut.",
            "stop_matching_live_honor_condition_effect": "For child condition-effect B, turn-7+ tsumo discard decisions while any opponent riichi is active; each held honor tile type with exactly one copy and 0 visible copies outside LuckyJ's hand is one opportunity.",
            "genbutsu_count_vs_riichi": "Number of tile copies in LuckyJ's current hand whose 34-tile type appears in the primary riichi player's river, bucketed 0/1/2+.",
            "significance": "For each condition value, delta_pp_vs_complement compares its rate to all other listed values. significant is true when |delta| exceeds sqrt(cell_ci^2 + complement_ci^2); CI is 1.96*sqrt(p*(1-p)/n)*100. Cells or complements below n=150 are small_sample and not significant.",
        },
        "dealer_vs_child_naga_match": summarize_hypothesis(hypothesis),
        "child_only_baselines": child_summary,
        "dealer_only_baselines": dealer_summary,
        "child_vs_dealer_delta": delta_summary(child_summary, dealer_summary),
        "child_only_condition_effects": child_conditions,
        "dealer_only_condition_effects_for_comparison": dealer_conditions,
    }
    output["changed_vs_published"] = changed_vs_published(child_summary, child_conditions)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        f"reports={processed_reports}/{len(rows)} unique_rows source_rows={len(source_rows)} "
        f"duplicates_skipped={len(duplicate_rows)} kyoku={processed_kyoku} skipped={skipped_kyoku} "
        f"hypothesis_decisions={hypothesis_decisions} child_records={len(split_records['child'])} dealer_records={len(split_records['dealer'])}"
    )


if __name__ == "__main__":
    main()
