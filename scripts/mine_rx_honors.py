#!/usr/bin/env python3
"""Mine prescriptive honor-tile timing thresholds from LuckyJ/NAGA reports."""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import analyze_luckyj as base


ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx-honors.json")

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
OPEN_CONTEXTS = ["no_opponent_open", "some_opponent_open"]
THREAT_LEVELS = ["none", "open_threat", "riichi"]
VISIBLE_BUCKETS = [0, 1, 2, 3]


def pct(numerator: int | float, denominator: int | float) -> float | None:
    if not denominator:
        return None
    return round(100.0 * float(numerator) / float(denominator), 1)


def pct_obj(numerator: int, denominator: int) -> dict[str, Any]:
    return {"count": numerator, "n": denominator, "pct": pct(numerator, denominator)}


def clean_number(value: float | int | None) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, float):
        return round(value, 1)
    return value


def nearest_rank(values: list[int], q: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


def summarize_turns(turns: list[int]) -> dict[str, Any]:
    ordered = sorted(turns)
    median = statistics.median(ordered) if ordered else None
    return {
        "n": len(ordered),
        "p25": nearest_rank(ordered, 0.25),
        "median": clean_number(median),
        "p75": nearest_rank(ordered, 0.75),
        "min": ordered[0] if ordered else None,
        "max": ordered[-1] if ordered else None,
    }


def safe_tile_id(tile: str | None) -> int | None:
    if not tile or tile == "?":
        return None
    try:
        return base.tile_index(tile)
    except KeyError:
        return None


def tile_base(tile: str | None) -> str:
    return str(tile or "").replace("r", "")


def tile_name(idx: int) -> str:
    return base.TILES[idx]


def valid_actor(actor: Any) -> bool:
    return isinstance(actor, int) and 0 <= actor < 4


def remove_tile(hand: list[str], tile: str | None) -> bool:
    if not tile or tile == "?":
        return False
    if tile in hand:
        hand.remove(tile)
        return True
    target = safe_tile_id(tile)
    if target is None:
        return False
    for item in list(hand):
        if safe_tile_id(item) == target:
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


def seat_wind(start: dict[str, Any], seat: int) -> str:
    return WINDS[(seat - int(start.get("oya", 0))) % 4]


def yakuhai_for_seat(start: dict[str, Any], seat: int) -> set[str]:
    return DRAGONS | {start.get("bakaze"), seat_wind(start, seat)}


def guest_winds_for_seat(start: dict[str, Any], seat: int) -> set[str]:
    return set(WINDS) - {start.get("bakaze"), seat_wind(start, seat)}


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
    """Copies outside LuckyJ's hand: opponent rivers, all public melds, dora indicators."""
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


def initial_cleanup_records(row: dict[str, Any], kyoku_index: int, start: dict[str, Any], target: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    hand = list(start.get("tehais", [[], [], [], []])[target])
    counts = hand_counter(hand)
    yakuhai = yakuhai_for_seat(start, target)
    guests = guest_winds_for_seat(start, target)
    for tile in sorted(HONORS, key=lambda t: base.IDX[t]):
        idx = base.IDX[tile]
        if counts[idx] != 1:
            continue
        if tile in DRAGONS:
            kind = "dragon"
            family = "yakuhai"
        elif tile in yakuhai:
            kind = "value_wind"
            family = "yakuhai"
        elif tile in guests:
            kind = "guest_wind"
            family = "guest_wind"
        else:
            continue
        records.append(
            {
                "game": row.get("idx"),
                "report_id": row.get("report_id"),
                "kyoku_index": kyoku_index,
                "tile": tile,
                "tile_idx": idx,
                "kind": kind,
                "family": family,
                "first_discard_turn": None,
                "discard_open_context": None,
                "discard_opponent_melds": None,
                "discard_any_riichi": None,
                "discard_msg_type": None,
                "paired_before_cut": False,
                "paired_turn": None,
                "max_decision_turn": 0,
                "outcome": None,
            }
        )
    return records


def mark_decision_turn(records: list[dict[str, Any]], turn: int) -> None:
    for record in records:
        if record["first_discard_turn"] is None:
            record["max_decision_turn"] = max(record["max_decision_turn"], turn)


def mark_pair_draw(records: list[dict[str, Any]], drawn_idx: int | None, hands: list[list[str]], target: int, turn: int) -> None:
    if drawn_idx is None:
        return
    for record in records:
        if record["tile_idx"] != drawn_idx or record["first_discard_turn"] is not None:
            continue
        if not record["paired_before_cut"] and count_tile(hands[target], drawn_idx) >= 2:
            record["paired_before_cut"] = True
            record["paired_turn"] = turn


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
    dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []
    records = initial_cleanup_records(row, kyoku_index, start, target)
    matrix: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    bonus: Counter[str] = Counter()
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
                mark_pair_draw(records, safe_tile_id(drawn), hands, target, turn)
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
                    process_bonus(
                        bonus,
                        drawn,
                        real_dahai,
                        msg.get("next_tsumogiri"),
                        turn,
                        target,
                        discards,
                        melds,
                        dora_markers,
                        reached,
                    )
                    mark_cleanup_discard(records, real_dahai, turn, target, open_melds, reached, msg_type)
                if real_dahai not in (None, "?"):
                    remove_for_actor(actor, real_dahai)

        elif msg_type in base.HURO_TYPES:
            if not valid_actor(actor):
                continue
            real_dahai = msg.get("real_dahai")
            if actor == target and real_dahai not in (None, "?") and not reached[target]:
                turn = len(discards[target]) + 1
                decisions += 1
                mark_decision_turn(records, turn)
                mark_cleanup_discard(records, real_dahai, turn, target, open_melds, reached, msg_type)
            consumed = msg.get("consumed") or []
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

        elif msg_type == "dahai":
            tile = msg.get("pai")
            if valid_actor(actor) and tile:
                discards[actor].append(tile)

        if malformed:
            return None

    finalize_cleanup_records(records, hands, target)
    return {"records": records, "matrix": matrix, "bonus": bonus, "decisions": decisions}


def summarize_cleanup_family(records: list[dict[str, Any]], kinds: list[str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for kind in kinds:
        subset = [record for record in records if record["kind"] == kind]
        discarded = [record for record in subset if record["first_discard_turn"] is not None]
        outcomes = Counter(record["outcome"] for record in subset)
        kind_summary: dict[str, Any] = {
            "n_start_singletons": len(subset),
            "discard_turn_all": summarize_turns([record["first_discard_turn"] for record in discarded]),
            "discarded_pct": pct_obj(len(discarded), len(subset)),
            "never_cut_pct": pct_obj(sum(1 for record in subset if record["first_discard_turn"] is None), len(subset)),
            "paired_before_cut_pct": pct_obj(sum(1 for record in subset if record["paired_before_cut"]), len(subset)),
            "outcomes": {
                outcome: {"count": count, "n": len(subset), "pct": pct(count, len(subset))}
                for outcome, count in sorted(outcomes.items())
            },
            "by_discard_opponent_open_context": {},
        }
        for context in OPEN_CONTEXTS:
            cell_discards = [record for record in discarded if record["discard_open_context"] == context]
            riichi_count = sum(1 for record in cell_discards if record["discard_any_riichi"])
            kind_summary["by_discard_opponent_open_context"][context] = {
                "n_start_singletons": len(subset),
                "n_discarded_in_context": len(cell_discards),
                "discard_turn": summarize_turns([record["first_discard_turn"] for record in cell_discards]),
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
    kept_past_6 = [
        record
        for record in eligible_turn6
        if record["first_discard_turn"] is None or record["first_discard_turn"] > 6
    ]
    by_context: dict[str, Any] = {}
    for context in OPEN_CONTEXTS:
        cell_discards = [record for record in discarded if record["discard_open_context"] == context]
        by_context[context] = {
            "n_start_singletons": len(subset),
            "n_discarded_in_context": len(cell_discards),
            "discard_turn": summarize_turns([record["first_discard_turn"] for record in cell_discards]),
            "discarded_here_pct_of_start_singletons": pct_obj(len(cell_discards), len(subset)),
        }
    outcomes = Counter(record["outcome"] for record in subset)
    return {
        "n_start_singletons": len(subset),
        "discard_turn_all": summarize_turns([record["first_discard_turn"] for record in discarded]),
        "discarded_pct": pct_obj(len(discarded), len(subset)),
        "never_cut_pct": pct_obj(sum(1 for record in subset if record["first_discard_turn"] is None), len(subset)),
        "paired_before_cut_pct": pct_obj(sum(1 for record in subset if record["paired_before_cut"]), len(subset)),
        "kept_past_turn6_pct": pct_obj(len(kept_past_6), len(eligible_turn6)),
        "kept_past_turn6_denominator_note": "Denominator excludes hands that ended before LuckyJ either cut the guest wind by turn 6 or completed a turn-6 discard decision.",
        "outcomes": {
            outcome: {"count": count, "n": len(subset), "pct": pct(count, len(subset))}
            for outcome, count in sorted(outcomes.items())
        },
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


def cell_rate(matrix_summary: dict[str, Any], bucket: str, visible: int, threat: str) -> tuple[float | None, int]:
    cell = matrix_summary["nested"][bucket][str(visible)][threat]
    return cell["discard_rate_pct"], cell["n"]


def fmt_rate(rate: float | None, n: int) -> str:
    return f"{rate:.1f}% (n={n})" if rate is not None else f"n/a (n={n})"


def fmt_turn(value: Any) -> str:
    return "n/a" if value is None else str(value)


def proposed_rules(summary: dict[str, Any]) -> list[str]:
    yak = summary["lone_yakuhai_cleanup_timing"]["summary_by_kind_and_opponent_open"]
    guest = summary["guest_wind_cleanup"]
    matrix = summary["stop_matching_honors_matrix"]
    bonus = summary["bonus_late_live_honor_draw_under_riichi"]

    dragon = yak["dragon"]
    value = yak["value_wind"]
    d_no = dragon["by_discard_opponent_open_context"]["no_opponent_open"]["discard_turn"]
    d_open = dragon["by_discard_opponent_open_context"]["some_opponent_open"]["discard_turn"]
    v_no = value["by_discard_opponent_open_context"]["no_opponent_open"]["discard_turn"]
    v_open = value["by_discard_opponent_open_context"]["some_opponent_open"]["discard_turn"]
    guest_turns = guest["discard_turn_all"]

    r_46_v0_none, n_46_v0_none = cell_rate(matrix, "4-6", 0, "none")
    r_46_v1_none, n_46_v1_none = cell_rate(matrix, "4-6", 1, "none")
    r_79_v0_none, n_79_v0_none = cell_rate(matrix, "7-9", 0, "none")
    r_79_v1_none, n_79_v1_none = cell_rate(matrix, "7-9", 1, "none")
    r_79_v0_riichi, n_79_v0_riichi = cell_rate(matrix, "7-9", 0, "riichi")
    r_79_v1_riichi, n_79_v1_riichi = cell_rate(matrix, "7-9", 1, "riichi")
    r_1012_v0_riichi, n_1012_v0_riichi = cell_rate(matrix, "10-12", 0, "riichi")
    r_1012_v1_riichi, n_1012_v1_riichi = cell_rate(matrix, "10-12", 1, "riichi")

    rules = [
        "Cut lone dragons in the first row unless they pair: no-open median "
        f"T{fmt_turn(d_no['median'])} / p75 T{fmt_turn(d_no['p75'])} (n={d_no['n']} cuts); "
        f"after an opponent has opened, median T{fmt_turn(d_open['median'])} (n={d_open['n']} cuts); "
        f"never cut {dragon['never_cut_pct']['pct']}% and paired before cut {dragon['paired_before_cut_pct']['pct']}% (n={dragon['n_start_singletons']}).",
        "Clean lone value winds on nearly the same clock: no-open median "
        f"T{fmt_turn(v_no['median'])} / p75 T{fmt_turn(v_no['p75'])} (n={v_no['n']} cuts); "
        f"with any opponent open, median T{fmt_turn(v_open['median'])} (n={v_open['n']} cuts); "
        f"never cut {value['never_cut_pct']['pct']}% and paired before cut {value['paired_before_cut_pct']['pct']}% (n={value['n_start_singletons']}).",
        "Treat guest winds as early cleanup first, safety second: median cut "
        f"T{fmt_turn(guest_turns['median'])} / p75 T{fmt_turn(guest_turns['p75'])} (n={guest_turns['n']} cuts), "
        f"but {guest['kept_past_turn6_pct']['pct']}% survived past turn 6 among eligible starts (n={guest['kept_past_turn6_pct']['n']}).",
        "When nobody is threatening, matching already-seen honors is much more acceptable by turns 4-6: "
        f"0-visible cut rate {fmt_rate(r_46_v0_none, n_46_v0_none)} vs 1-visible {fmt_rate(r_46_v1_none, n_46_v1_none)}.",
        "By turns 7-9 with no threat, stop treating live first-copy honors as automatic cuts: "
        f"0-visible cut rate {fmt_rate(r_79_v0_none, n_79_v0_none)} vs 1-visible {fmt_rate(r_79_v1_none, n_79_v1_none)}.",
        "Under riichi, be stricter with live honors: turns 7-9 cut rates are "
        f"0-visible {fmt_rate(r_79_v0_riichi, n_79_v0_riichi)} and 1-visible {fmt_rate(r_79_v1_riichi, n_79_v1_riichi)}; "
        f"turns 10-12 are 0-visible {fmt_rate(r_1012_v0_riichi, n_1012_v0_riichi)} and 1-visible {fmt_rate(r_1012_v1_riichi, n_1012_v1_riichi)}.",
        "After turn 12 under riichi, do not auto-tsumogiri live honors you draw: immediate tsumogiri "
        f"{bonus['immediate_tsumogiri_pct']}% vs hold {bonus['held_pct']}% (n={bonus['n']}).",
    ]
    return rules


def main() -> None:
    source_rows = base.parse_rows()
    rows, duplicate_rows = unique_rows_by_report_id(source_rows)
    all_records: list[dict[str, Any]] = []
    matrix: dict[tuple[str, int, str], Counter[str]] = defaultdict(Counter)
    bonus: Counter[str] = Counter()
    processed_reports = 0
    processed_kyoku = 0
    skipped_kyoku = 0
    decisions = 0

    for index, row in enumerate(rows, 1):
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
        except Exception as exc:  # noqa: BLE001 - this is a batch miner; keep going and report the skip.
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
            all_records.extend(mined["records"])
            for key, counter in mined["matrix"].items():
                matrix[key].update(counter)
            bonus.update(mined["bonus"])
        if index % 200 == 0:
            print(f"processed {index}/{len(rows)} games; kyoku={processed_kyoku}; skipped_kyoku={skipped_kyoku}")

    yak_summary = summarize_cleanup_family(all_records, ["dragon", "value_wind"])
    guest_summary = summarize_guest(all_records)
    matrix_summary = summarize_matrix(matrix)
    bonus_summary = summarize_bonus(bonus)
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
            "cleanup_records": len(all_records),
        },
        "definitions": {
            "turn_number": "For LuckyJ, len(discards[LuckyJ]) + 1 at the decision state, matching scripts/build_point_examples.py replay timing.",
            "yakuhai": "Dragons P/F/C plus round wind (bakaze) plus LuckyJ seat wind, where seat wind = WINDS[(seat - oya) % 4] and WINDS=[E,S,W,N].",
            "value_wind": "A wind that is LuckyJ's round wind and/or seat wind; if round wind equals seat wind it is counted once.",
            "guest_wind": "A wind that is neither round wind nor LuckyJ's seat wind.",
            "lone_cleanup_population": "Honor tile types held exactly once in LuckyJ's starting hand; starting pairs/triples are excluded.",
            "paired_before_cut": "LuckyJ drew another copy of that same honor before the first recorded decision discard of the tile.",
            "opponent_open_context": "At discard time, no_opponent_open means total opponent meld count is 0; some_opponent_open means total opponent meld count is 1+ using the same meld/open_melds replay as build_point_examples.py.",
            "visible_copies_for_matrix": "Copies outside LuckyJ's concealed hand: opponent rivers, all public melds, and current dora indicators. LuckyJ's own river is excluded. Counts are capped at 3.",
            "threat_level": "riichi if any opponent has reached; otherwise open_threat if any opponent has 2+ melds; otherwise none.",
            "stop_matching_opportunity": "Every non-riichi LuckyJ tsumo discard decision, for each honor tile type LuckyJ holds exactly one copy of before discarding.",
            "bonus_live_honor_draw": "After turn 12, non-riichi LuckyJ tsumo decisions where LuckyJ drew an honor with 0-1 visible copies outside hand while at least one opponent riichi was active.",
            "percentiles": "p25/p75 use nearest-rank percentiles over integer discard turns; median uses the standard median.",
        },
        "lone_yakuhai_cleanup_timing": {
            "summary_by_kind_and_opponent_open": yak_summary,
        },
        "guest_wind_cleanup": guest_summary,
        "stop_matching_honors_matrix": matrix_summary,
        "bonus_late_live_honor_draw_under_riichi": bonus_summary,
    }
    output["proposed_rules"] = proposed_rules(output)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(
        f"reports={processed_reports}/{len(rows)} unique_rows source_rows={len(source_rows)} "
        f"duplicates_skipped={len(duplicate_rows)} kyoku={processed_kyoku} skipped={skipped_kyoku} "
        f"cleanup_records={len(all_records)} matrix_opps={sum(c.get('n', 0) for c in matrix.values())}"
    )


if __name__ == "__main__":
    main()
