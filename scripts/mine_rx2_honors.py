#!/usr/bin/env python3
"""Second-pass honor mining: condition effects and dispersion for LuckyJ honor handling."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from mahjong.shanten import Shanten

import analyze_luckyj as base
from extract_case_studies import counts_34
import mine_rx_honors as pass1


ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx2-honors.json")
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
MIN_CELL_N = 150


# ---------------------------------------------------------------------------
# Small stat helpers


def pct(num: int | float, den: int | float) -> float | None:
    if not den:
        return None
    return round(100.0 * float(num) / float(den), 1)


def round1(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None


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


def turn_distribution(values: list[int]) -> dict[str, Any]:
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "mean": round2(statistics.mean(ordered)) if ordered else None,
        "std": round2(statistics.pstdev(ordered)) if len(ordered) >= 2 else (0 if len(ordered) == 1 else None),
        "p25": nearest_rank(ordered, 0.25),
        "p50": median_value(ordered),
        "p75": nearest_rank(ordered, 0.75),
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


# ---------------------------------------------------------------------------
# Tile, wind, shanten, and dora helpers


def valid_actor(actor: Any) -> bool:
    return isinstance(actor, int) and 0 <= actor < 4


def safe_tile_id(tile: str | None) -> int | None:
    if not tile or tile == "?":
        return None
    try:
        return base.tile_index(tile)
    except Exception:
        return None


def tile_base(tile: str | None) -> str:
    return str(tile or "").replace("r", "")


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


def start_rank_label(start: dict[str, Any], target: int) -> str:
    seat2rank = start.get("seat2rank") or []
    try:
        rank = int(seat2rank[target]) + 1
    except Exception:
        return "unknown"
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(rank, "unknown")


def next_dora(marker: str | None) -> str | None:
    base_tile = tile_base(marker)
    if not base_tile:
        return None
    if len(base_tile) == 2 and base_tile[1] in {"m", "p", "s"}:
        rank = int(base_tile[0])
        return f"{1 if rank == 9 else rank + 1}{base_tile[1]}"
    if base_tile in WINDS:
        return WINDS[(WINDS.index(base_tile) + 1) % 4]
    dragon_order = ["P", "F", "C"]
    if base_tile in dragon_order:
        return dragon_order[(dragon_order.index(base_tile) + 1) % 3]
    return None


def starting_dora_count(start: dict[str, Any], target: int) -> int:
    hands = start.get("tehais") or []
    if target >= len(hands):
        return 0
    dora = next_dora(start.get("dora_marker"))
    dora_idx = safe_tile_id(dora)
    count = 0
    for tile in hands[target]:
        if dora_idx is not None and safe_tile_id(tile) == dora_idx:
            count += 1
        if str(tile).endswith("r"):
            count += 1
    return count


def dora_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    return "2+"


def turn_bucket(turn: int) -> str:
    for label, lo, hi in TURN_BUCKETS:
        if lo <= turn <= hi:
            return label
    return "13+"


# ---------------------------------------------------------------------------
# Replay visibility and threat helpers


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
    """Copies outside LuckyJ's hand: opponent rivers, public melds, and dora indicators."""
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
# Lone-yakuhai start records


def initial_lone_yakuhai_records(row: dict[str, Any], kyoku_index: int, start: dict[str, Any], target: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    hand = list(start.get("tehais", [[], [], [], []])[target])
    counts = hand_counter(hand)
    yakuhai = yakuhai_for_seat(start, target)
    dealer = int(start.get("oya", -1)) == target
    dora_n = starting_dora_count(start, target)
    for tile in sorted(HONORS, key=lambda t: base.IDX[t]):
        idx = base.IDX[tile]
        if counts[idx] != 1 or tile not in yakuhai:
            continue
        htype = honor_type_for_start(start, target, tile)
        records.append(
            {
                "game": row.get("idx"),
                "report_id": row.get("report_id"),
                "kyoku_index": kyoku_index,
                "target": target,
                "tile": tile,
                "tile_idx": idx,
                "kind": "dragon" if tile in DRAGONS else "value_wind",
                "honor_type": htype,
                "is_dealer": "dealer" if dealer else "non_dealer",
                "start_rank": start_rank_label(start, target),
                "starting_dora_count": dora_n,
                "starting_dora_bucket": dora_bucket(dora_n),
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


# ---------------------------------------------------------------------------
# Stop-matching opportunities and first-pass matrix reproduction


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


def collect_b_opportunities(
    opportunities: list[dict[str, Any]],
    start: dict[str, Any],
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
        tile = tile_name(idx)
        yakuhai_for_riichi = False
        if primary is not None:
            yakuhai_for_riichi = tile in yakuhai_for_seat(start, primary)
        opportunities.append(
            {
                "turn": turn,
                "turn_bucket": turn_bucket(turn),
                "tile": tile,
                "tile_idx": idx,
                "discard_live_honor": discard_idx == idx,
                "own_shanten": shanten,
                "own_shanten_bucket": shanten_b_bucket(shanten),
                "genbutsu_count_vs_riichi": genbutsu_count,
                "genbutsu_bucket": count_bucket_0_1_2plus(genbutsu_count),
                "riichi_player": primary,
                "riichi_player_dealer": "dealer" if primary == int(start.get("oya", -1)) else "non_dealer",
                "honor_yakuhai_for_riichi_player": "yakuhai" if yakuhai_for_riichi else "pure_guest",
            }
        )


# ---------------------------------------------------------------------------
# Kyoku processing


def process_kyoku(row: dict[str, Any], kyoku_index: int, kyoku: list[dict[str, Any]]) -> dict[str, Any] | None:
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
    records = initial_lone_yakuhai_records(row, kyoku_index, start, target)
    matrix: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    b_opportunities: list[dict[str, Any]] = []
    decisions = 0
    malformed = False

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
                    process_matrix_opportunities(
                        matrix,
                        hands[target],
                        real_dahai,
                        turn,
                        target,
                        discards,
                        melds,
                        dora_markers,
                        reached,
                        open_melds,
                    )
                    collect_b_opportunities(
                        b_opportunities,
                        start,
                        hands[target],
                        real_dahai,
                        turn,
                        target,
                        discards,
                        melds,
                        dora_markers,
                        reached,
                        reach_order,
                    )
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
    return {"records": records, "matrix": matrix, "b_opportunities": b_opportunities, "decisions": decisions}


# ---------------------------------------------------------------------------
# Condition-effect summaries


def cut_by6_event(record: dict[str, Any]) -> dict[str, Any] | None:
    # Requirement A denominator: the kyoku reached at least 6 LuckyJ turns while
    # the starting singleton remained a lone honor unless it was cut by then.
    if int(record.get("total_luckyj_turns") or 0) < 6:
        return None
    paired_turn = record.get("paired_turn")
    first_turn = record.get("first_discard_turn")
    if paired_turn is not None and paired_turn <= 6 and (first_turn is None or first_turn > 6):
        return None
    return {
        **record,
        "cut_by_turn6": first_turn is not None and first_turn <= 6,
        "cut_turn": first_turn,
    }


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
    return {
        "condition": condition_key,
        "n": len(filtered),
        "cells_sorted_by_abs_delta_pp": cells,
    }


def baseline_rate(events: list[dict[str, Any]], outcome_key: str, outcome_name: str) -> dict[str, Any]:
    n = len(events)
    yes = sum(1 for event in events if event.get(outcome_key))
    return rate_payload(yes, n, outcome_name)


def summarize_condition_effects_a(records: list[dict[str, Any]]) -> dict[str, Any]:
    events = [event for record in records if (event := cut_by6_event(record)) is not None]
    return {
        "baseline": baseline_rate(events, "cut_by_turn6", "cut_by_turn6"),
        "denominator_note": "Lone-yakuhai starting singleton records in rounds with at least 6 LuckyJ turns, excluding starts that paired before/at turn 6 before being cut; cut-by-T6 is true when first non-riichi tracked discard turn is <=6.",
        "effects": [
            condition_effects(events, "is_dealer", ["dealer", "non_dealer"], "cut_by_turn6", "cut_by_turn6", True),
            condition_effects(events, "start_rank", ["1st", "2nd", "3rd", "4th"], "cut_by_turn6", "cut_by_turn6", True),
            condition_effects(events, "starting_dora_bucket", ["0", "1", "2+"], "cut_by_turn6", "cut_by_turn6", True),
            condition_effects(events, "turn3_shanten_bucket", ["<=2", ">=3"], "cut_by_turn6", "cut_by_turn6", True),
            condition_effects(events, "honor_type", ["dragon", "round_wind", "seat_wind", "double_wind"], "cut_by_turn6", "cut_by_turn6", True),
            condition_effects(events, "turn3_another_copy_bucket", ["0", "1+"], "cut_by_turn6", "cut_by_turn6", True),
        ],
    }


def summarize_condition_effects_b(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "baseline": baseline_rate(opportunities, "discard_live_honor", "discard_live_honor"),
        "denominator_note": "Turn 7+ tsumo discard decisions while any opponent riichi is active; each held honor tile type with exactly one copy and 0 visible copies outside LuckyJ's hand is one opportunity.",
        "effects": [
            condition_effects(opportunities, "own_shanten_bucket", ["0-1", "2+"], "discard_live_honor", "discard_live_honor"),
            condition_effects(opportunities, "genbutsu_bucket", ["0", "1", "2+"], "discard_live_honor", "discard_live_honor"),
            condition_effects(opportunities, "riichi_player_dealer", ["dealer", "non_dealer"], "discard_live_honor", "discard_live_honor"),
            condition_effects(opportunities, "honor_yakuhai_for_riichi_player", ["yakuhai", "pure_guest"], "discard_live_honor", "discard_live_honor"),
        ],
    }


# ---------------------------------------------------------------------------
# Pass-1 reproduction and dispersion


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


def pass1_reproduction(records: list[dict[str, Any]], matrix_summary: dict[str, Any]) -> dict[str, Any]:
    def median_for(kind: str, context: str | None = None) -> dict[str, Any]:
        subset = [record for record in records if record["kind"] == kind and record["first_discard_turn"] is not None]
        if context is not None:
            subset = [record for record in subset if record.get("discard_open_context") == context]
        turns = [int(record["first_discard_turn"]) for record in subset]
        return {"n": len(turns), "median": median_value(turns)}

    def matrix_rate(bucket: str, visible: int, threat: str) -> dict[str, Any]:
        cell = matrix_summary["nested"][bucket][str(visible)][threat]
        return {"n": cell["n"], "discard_n": cell["discard_n"], "discard_rate_pct": cell["discard_rate_pct"]}

    actual = {
        "lone_dragon_quiet_median_turn": median_for("dragon", "no_opponent_open"),
        "lone_dragon_after_open_median_turn": median_for("dragon", "some_opponent_open"),
        "guest_wind_median_turn": median_for("guest_wind"),
        "stop_matching_under_riichi_turns_7_9_visible_0": matrix_rate("7-9", 0, "riichi"),
        "stop_matching_under_riichi_turns_7_9_visible_1": matrix_rate("7-9", 1, "riichi"),
    }
    expected = {
        "lone_dragon_quiet_median_turn": 3,
        "lone_dragon_after_open_median_turn": 5,
        "guest_wind_median_turn": 1,
        "stop_matching_under_riichi_turns_7_9_visible_0_rate_pct": 14.3,
        "stop_matching_under_riichi_turns_7_9_visible_1_rate_pct": 34.8,
    }
    return {
        "expected_from_pass1_prompt": expected,
        "reproduced": actual,
        "agreement": {
            "lone_dragon_quiet_median_turn_matches": actual["lone_dragon_quiet_median_turn"]["median"] == expected["lone_dragon_quiet_median_turn"],
            "lone_dragon_after_open_median_turn_matches": actual["lone_dragon_after_open_median_turn"]["median"] == expected["lone_dragon_after_open_median_turn"],
            "guest_wind_median_turn_matches": actual["guest_wind_median_turn"]["median"] == expected["guest_wind_median_turn"],
            "visible_0_rate_delta_pp": round2(actual["stop_matching_under_riichi_turns_7_9_visible_0"]["discard_rate_pct"] - expected["stop_matching_under_riichi_turns_7_9_visible_0_rate_pct"]),
            "visible_1_rate_delta_pp": round2(actual["stop_matching_under_riichi_turns_7_9_visible_1"]["discard_rate_pct"] - expected["stop_matching_under_riichi_turns_7_9_visible_1_rate_pct"]),
            "rates_within_1pp": abs(actual["stop_matching_under_riichi_turns_7_9_visible_0"]["discard_rate_pct"] - expected["stop_matching_under_riichi_turns_7_9_visible_0_rate_pct"]) <= 1.0
            and abs(actual["stop_matching_under_riichi_turns_7_9_visible_1"]["discard_rate_pct"] - expected["stop_matching_under_riichi_turns_7_9_visible_1_rate_pct"]) <= 1.0,
        },
    }


def guest_wind_records(row: dict[str, Any], kyoku_index: int, start: dict[str, Any], target: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    hand = list(start.get("tehais", [[], [], [], []])[target])
    counts = hand_counter(hand)
    guests = set(WINDS) - {start.get("bakaze"), seat_wind(start, target)}
    for tile in sorted(guests, key=lambda t: base.IDX[t]):
        idx = base.IDX[tile]
        if counts[idx] != 1:
            continue
        records.append(
            {
                "game": row.get("idx"),
                "report_id": row.get("report_id"),
                "kyoku_index": kyoku_index,
                "target": target,
                "tile": tile,
                "tile_idx": idx,
                "kind": "guest_wind",
                "first_discard_turn": None,
                "discard_open_context": None,
                "paired_before_cut": False,
                "max_decision_turn": 0,
                "total_luckyj_turns": 0,
            }
        )
    return records


def dispersion(records: list[dict[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for kind in ["dragon", "value_wind"]:
        output[kind] = {}
        for context, label in [("no_opponent_open", "quiet"), ("some_opponent_open", "after_open")]:
            turns = [
                int(record["first_discard_turn"])
                for record in records
                if record["kind"] == kind and record.get("discard_open_context") == context and record.get("first_discard_turn") is not None
            ]
            output[kind][label] = turn_distribution(turns)
    combined: dict[str, Any] = {}
    for context, label in [("no_opponent_open", "quiet"), ("some_opponent_open", "after_open")]:
        turns = [
            int(record["first_discard_turn"])
            for record in records
            if record["kind"] in {"dragon", "value_wind"}
            and record.get("discard_open_context") == context
            and record.get("first_discard_turn") is not None
        ]
        combined[label] = turn_distribution(turns)
    output["combined_lone_yakuhai"] = combined
    return output


def per_game_consistency(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_game: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        event = cut_by6_event(record)
        if event is not None:
            by_game[record.get("game")].append(event)
    rates: list[dict[str, Any]] = []
    for game, events in by_game.items():
        if len(events) < 3:
            continue
        cut = sum(1 for event in events if event["cut_by_turn6"])
        rates.append({"game": game, "n": len(events), "cut_by_turn6_n": cut, "rate": cut / len(events)})
    total_n = sum(item["n"] for item in rates)
    if total_n:
        weighted_mean = sum(item["rate"] * item["n"] for item in rates) / total_n
        weighted_var = sum(item["n"] * (item["rate"] - weighted_mean) ** 2 for item in rates) / total_n
        unweighted_values = [item["rate"] for item in rates]
    else:
        weighted_mean = None
        weighted_var = None
        unweighted_values = []
    return {
        "games_n": len(rates),
        "lone_yakuhai_starts_n": total_n,
        "weighted_mean_cut_by_turn6_rate_pct": round1(weighted_mean * 100.0) if weighted_mean is not None else None,
        "weighted_std_cut_by_turn6_rate_pp": round2(math.sqrt(weighted_var) * 100.0) if weighted_var is not None else None,
        "unweighted_mean_cut_by_turn6_rate_pct": round1(statistics.mean(unweighted_values) * 100.0) if unweighted_values else None,
        "unweighted_std_cut_by_turn6_rate_pp": round2(statistics.pstdev(unweighted_values) * 100.0) if len(unweighted_values) >= 2 else (0 if len(unweighted_values) == 1 else None),
        "per_game_rate_percentiles": {
            "n": len(unweighted_values),
            "p25": round1(float(nearest_rank([value * 100.0 for value in unweighted_values], 0.25))) if unweighted_values else None,
            "p50": round1(float(median_value([value * 100.0 for value in unweighted_values]))) if unweighted_values else None,
            "p75": round1(float(nearest_rank([value * 100.0 for value in unweighted_values], 0.75))) if unweighted_values else None,
        },
    }


# ---------------------------------------------------------------------------
# Modifier one-liners


A_VALUE_PHRASES = {
    "is_dealer": {"dealer": "LuckyJ is dealer", "non_dealer": "LuckyJ is non-dealer"},
    "start_rank": {"1st": "start rank is 1st", "2nd": "start rank is 2nd", "3rd": "start rank is 3rd", "4th": "start rank is 4th"},
    "starting_dora_bucket": {"0": "starting hand has 0 dora", "1": "starting hand has 1 dora", "2+": "starting hand has 2+ dora"},
    "turn3_shanten_bucket": {"<=2": "hand is ≤2 shanten at turn 3", ">=3": "hand is ≥3 shanten at turn 3"},
    "honor_type": {"dragon": "honor is a dragon", "round_wind": "honor is round wind", "seat_wind": "honor is seat wind", "double_wind": "honor is double wind"},
    "turn3_another_copy_bucket": {"0": "no other copy is in opponent rivers by turn 3", "1+": "another copy is in opponent rivers by turn 3"},
}
B_VALUE_PHRASES = {
    "own_shanten_bucket": {"0-1": "own shanten is 0-1", "2+": "own shanten is 2+"},
    "genbutsu_bucket": {"0": "0 genbutsu are in hand vs the riichi player", "1": "1 genbutsu is in hand vs the riichi player", "2+": "2+ genbutsu are in hand vs the riichi player"},
    "riichi_player_dealer": {"dealer": "riichi player is dealer", "non_dealer": "riichi player is non-dealer"},
    "honor_yakuhai_for_riichi_player": {"yakuhai": "honor is yakuhai for the riichi player", "pure_guest": "honor is pure guest for the riichi player"},
}


def all_effect_cells(summary: dict[str, Any], section: str) -> Iterable[dict[str, Any]]:
    for effect in summary[section]["effects"]:
        for cell in effect["cells_sorted_by_abs_delta_pp"]:
            yield cell


def proposed_modifiers(summary: dict[str, Any]) -> list[str]:
    a_base = summary["condition_effects_lone_yakuhai_cut_by_turn6"]["baseline"]["cut_by_turn6_rate_pct"]
    b_base = summary["condition_effects_stop_matching_live_honor_under_riichi_turn7plus"]["baseline"]["discard_live_honor_rate_pct"]
    candidates: list[tuple[float, str]] = []
    for cell in all_effect_cells(summary, "condition_effects_lone_yakuhai_cut_by_turn6"):
        if not cell["significant"]:
            continue
        phrase = A_VALUE_PHRASES.get(cell["condition"], {}).get(cell["value"], f"{cell['condition']}={cell['value']}")
        delta = cell["delta_pp_vs_complement"]
        line = (
            f"Cut-by-6 baseline {a_base:.1f}%; {delta:+.1f}pp when {phrase} "
            f"(rate {cell['cut_by_turn6_rate_pct']:.1f}%, n={cell['n']})."
        )
        candidates.append((abs(delta), line))
    for cell in all_effect_cells(summary, "condition_effects_stop_matching_live_honor_under_riichi_turn7plus"):
        if not cell["significant"]:
            continue
        phrase = B_VALUE_PHRASES.get(cell["condition"], {}).get(cell["value"], f"{cell['condition']}={cell['value']}")
        delta = cell["delta_pp_vs_complement"]
        line = (
            f"Live-honor discard baseline {b_base:.1f}%; {delta:+.1f}pp when {phrase} "
            f"(rate {cell['discard_live_honor_rate_pct']:.1f}%, n={cell['n']})."
        )
        candidates.append((abs(delta), line))
    candidates.sort(key=lambda item: item[0], reverse=True)
    return [line for _, line in candidates[:8]]


# ---------------------------------------------------------------------------
# Row de-dup and main


def unique_rows_by_report_id(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    unique: list[dict[str, Any]] = []
    seen: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for row in rows:
        report_id = row.get("report_id")
        if report_id in seen:
            kept = seen[report_id]
            duplicates.append(
                {
                    "report_id": report_id,
                    "kept_idx": kept.get("idx"),
                    "kept_actor": kept.get("actor"),
                    "skipped_idx": row.get("idx"),
                    "skipped_actor": row.get("actor"),
                }
            )
            continue
        seen[report_id] = row
        unique.append(row)
    return unique, duplicates


def main() -> None:
    source_rows = base.parse_rows()
    rows, duplicate_rows = unique_rows_by_report_id(source_rows)
    all_yakuhai_records: list[dict[str, Any]] = []
    all_guest_records: list[dict[str, Any]] = []
    all_for_reproduction: list[dict[str, Any]] = []
    matrix: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    b_opportunities: list[dict[str, Any]] = []
    processed_reports = 0
    processed_kyoku = 0
    skipped_kyoku = 0
    decisions = 0

    for index, row in enumerate(rows, 1):
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
        except Exception as exc:  # noqa: BLE001 - batch miner; report and continue.
            print(f"skip report {row.get('idx')} {row.get('report_id')}: {exc}")
            continue
        processed_reports += 1
        for kyoku_index, kyoku in enumerate(data.get("pred", [])):
            mined = process_kyoku(row, kyoku_index, kyoku)
            if mined is None:
                skipped_kyoku += 1
                continue
            processed_kyoku += 1
            decisions += mined["decisions"]
            yak_records = mined["records"]
            all_yakuhai_records.extend(yak_records)
            b_opportunities.extend(mined["b_opportunities"])
            for key, counter in mined["matrix"].items():
                matrix[key].update(counter)

            # For pass-1 guest-wind baseline reproduction, reuse the same replay pass state by
            # running the first-pass script's logic would be overkill; instead replay guest starts
            # with the same start metadata and then fill them via a compact second replay below.
            # This keeps the second-pass yakuhai record population separate and explicit.
            # We collect guest records with a dedicated pass after processing all rows.
        if index % 200 == 0:
            print(f"processed {index}/{len(rows)} games; kyoku={processed_kyoku}; skipped_kyoku={skipped_kyoku}")

    # Build guest records for pass-1 reproduction by using the original first-pass miner directly.
    # This avoids changing the first-pass script while making baseline agreement transparent.
    # The data source and report de-duplication are the same as the second-pass replay above.
    # A fresh replay is fast because reports are cached locally.
    guest_matrix_dummy: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    for row in rows:
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
        except Exception:
            continue
        for kyoku_index, kyoku in enumerate(data.get("pred", [])):
            mined = pass1.process_kyoku(row, kyoku_index, kyoku)
            if mined is None:
                continue
            guest_records = [record for record in mined["records"] if record["kind"] == "guest_wind"]
            all_guest_records.extend(guest_records)
            for key, counter in mined["matrix"].items():
                guest_matrix_dummy[key].update(counter)

    all_for_reproduction = all_yakuhai_records + all_guest_records
    matrix_summary = summarize_matrix(matrix)

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
            "luckyj_decisions_processed": decisions,
            "lone_yakuhai_records": len(all_yakuhai_records),
            "stop_matching_live_honor_opportunities": len(b_opportunities),
        },
        "definitions": {
            "turn_number": "For LuckyJ, len(discards[LuckyJ]) + 1 at the decision state, matching scripts/mine_rx_honors.py and build_point_examples.py replay timing.",
            "lone_yakuhai_start": "A dragon or LuckyJ value wind (round wind and/or seat wind) held exactly once in LuckyJ's starting hand. Starting pairs/triples are excluded; guest winds are excluded from condition-effect A.",
            "cut_by_turn6": "For condition-effect A, true if the starting singleton's first tracked non-riichi discard turn is <=6. Denominator requires the kyoku to reach at least 6 LuckyJ turns and excludes starts that paired before/at turn 6 before being cut, because they stopped being lone-yakuhai starts before the horizon.",
            "hand_quality_turn3": "Mahjong Shanten.calculate_shanten(counts_34(current concealed tiles)) at LuckyJ's turn-3 discard state. For open hands, the library infers existing open melds from the smaller concealed tile count.",
            "dora_count_start": "Starting-hand dora count uses the next tile after the start dora_marker (suit ranks wrap 9->1; winds E->S->W->N->E; dragons P->F->C->P). Red fives 5mr/5pr/5sr add one dora each; if a red five is also indicator dora it counts twice.",
            "another_copy_visible_by_turn3": "Whether at least one other copy of the tracked honor is visible in opponent rivers before LuckyJ's turn-3 discard. LuckyJ's own river is excluded so an early cut does not count as another copy.",
            "honor_type": "dragon, round_wind, seat_wind, or double_wind when round wind equals LuckyJ seat wind.",
            "stop_matching_live_honor_opportunity": "For condition-effect B, each turn-7+ LuckyJ tsumo discard decision while any opponent riichi is active, for each honor tile type LuckyJ holds exactly once with 0 visible copies outside LuckyJ's hand.",
            "visible_elsewhere_for_stop_matching": "Copies outside LuckyJ's concealed hand: opponent rivers, all public melds, and current dora indicators. LuckyJ's own river is excluded. Counts are capped at 3 for reproduced matrix cells.",
            "primary_riichi_player": "The earliest active opponent riichi in reach-message order; riichi-player dealer/yakuhai and genbutsu counts use this seat.",
            "genbutsu_count_vs_riichi": "Number of tile copies in LuckyJ's current hand whose 34-tile type appears in the primary riichi player's river, bucketed 0/1/2+.",
            "significance": "For each condition value, delta_pp_vs_complement compares its rate to all other listed values for that condition. significant is true when |delta| exceeds sqrt(cell_ci^2 + complement_ci^2); CI is 1.96*sqrt(p*(1-p)/n)*100. Cells or complements below n=150 are marked small_sample and not significant.",
            "dispersion_std": "Cut-turn and per-game consistency standard deviations are population standard deviations. p25/p75 use nearest-rank percentiles; p50 uses median.",
            "quiet_vs_after_open": "quiet means the first discard of the tracked honor occurred before any opponent had an open meld (no_opponent_open in pass 1); after_open means at least one opponent meld existed at discard time.",
        },
        "reproduced_baselines": pass1_reproduction(all_for_reproduction, matrix_summary),
        "condition_effects_lone_yakuhai_cut_by_turn6": summarize_condition_effects_a(all_yakuhai_records),
        "condition_effects_stop_matching_live_honor_under_riichi_turn7plus": summarize_condition_effects_b(b_opportunities),
        "dispersion": {
            "lone_dragon_and_value_wind_cut_turns": dispersion(all_yakuhai_records),
            "per_game_consistency": per_game_consistency(all_yakuhai_records),
        },
        "stop_matching_honors_matrix_reproduced": matrix_summary,
    }
    output["proposed_modifiers"] = proposed_modifiers(output)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        f"reports={processed_reports}/{len(rows)} unique_rows source_rows={len(source_rows)} "
        f"duplicates_skipped={len(duplicate_rows)} kyoku={processed_kyoku} skipped={skipped_kyoku} "
        f"lone_yakuhai_records={len(all_yakuhai_records)} live_honor_opps={len(b_opportunities)}"
    )


if __name__ == "__main__":
    main()
