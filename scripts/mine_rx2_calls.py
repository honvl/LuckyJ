#!/usr/bin/env python3
"""Second-pass mining of LuckyJ call-decision condition effects and dispersion."""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import analyze_luckyj as base
import mine_rx_calls as pass1
from build_point_examples import CALL_KIND_LABELS, yakuhai_for_seat
from extract_case_studies import counts_34, remove_tile
from mahjong.shanten import Shanten

OUT_PATH = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx2-calls.json")
MIN_CELL_N = 120
HURO_TYPES = pass1.HURO_TYPES
SHANTEN = Shanten()

YAK_DORA_BUCKETS = ["0", "1", "2", "3+"]
CHI_DORA_BUCKETS = ["0", "1", "2+"]
TURN_BUCKETS = ["1-6", "7-12", "13+"]
SHANTEN_BUCKETS = ["0-1", "2-3", "4+"]
TURN_SHANTEN_BUCKETS = [f"turn_{turn}_shanten_{shanten}" for turn in TURN_BUCKETS for shanten in SHANTEN_BUCKETS]


# ----------------------------- small helpers -----------------------------


def pct_raw(num: int | float, den: int | float) -> float | None:
    return 100.0 * num / den if den else None


def pct1(num: int | float, den: int | float) -> float | None:
    value = pct_raw(num, den)
    return round(value, 1) if value is not None else None


def round1(value: float | None) -> float | None:
    return round(value, 1) if value is not None and math.isfinite(value) else None


def round2(value: float | None) -> float | None:
    return round(value, 2) if value is not None and math.isfinite(value) else None


def base_tile(tile: str | None) -> str | None:
    return pass1.base_tile(tile)


def tile_id(tile: str) -> int:
    return base.IDX[tile]


def same_tile(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    try:
        return tile_id(a) == tile_id(b)
    except KeyError:
        return False


def dora_tiles_from_markers(dora_markers: list[str]) -> list[str]:
    return [d for d in (pass1.dora_from_marker(marker) for marker in dora_markers) if d]


def is_tile_dora(tile: str | None, dora_markers: list[str]) -> bool:
    clean = base_tile(tile)
    return bool(clean and clean in dora_tiles_from_markers(dora_markers))


def yak_dora_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    return "3+"


def chi_dora_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    return "2+"


def rank_number(start: dict[str, Any], target: int) -> int | None:
    ranks = start.get("seat2rank") or []
    if target < len(ranks) and ranks[target] is not None:
        return int(ranks[target]) + 1
    return None


def rank_tier(start: dict[str, Any], target: int) -> str | None:
    rank = rank_number(start, target)
    if rank in {1, 2}:
        return "1-2"
    if rank in {3, 4}:
        return "3-4"
    return None


def round_wind_bucket(start: dict[str, Any]) -> str | None:
    wind = start.get("bakaze")
    if wind == "E":
        return "East"
    if wind == "S":
        return "South"
    return None


def shanten_bucket_3(value: int | None) -> str | None:
    if value is None:
        return None
    if value <= 1:
        return "0-1"
    if value <= 3:
        return "2-3"
    return "4+"


def turn_shanten_bucket(turn: int, shanten: int | None) -> str | None:
    shanten_b = shanten_bucket_3(shanten)
    if not shanten_b:
        return None
    return f"turn_{pass1.turn_bucket(turn)}_shanten_{shanten_b}"


def existing_table_threat(target: int, reached: list[bool], open_melds: list[int]) -> bool:
    return any(seat != target and (reached[seat] or open_melds[seat] >= 2) for seat in range(4))


def has_second_yakuhai_pair(hand: list[str], called_yakuhai_tile: str, yakuhai_tiles: set[str]) -> bool:
    called = base_tile(called_yakuhai_tile)
    for tile in yakuhai_tiles:
        if tile != called and pass1.tile_count(hand, tile) >= 2:
            return True
    return False


def visible_counter_for_updates(discards: list[list[str]], melds: list[list[dict[str, Any]]], dora_markers: list[str]) -> Counter:
    counts = Counter()
    for marker in dora_markers:
        try:
            counts[tile_id(marker)] += 1
        except KeyError:
            pass
    for river in discards:
        for tile in river:
            try:
                counts[tile_id(tile)] += 1
            except KeyError:
                pass
    for player_melds in melds:
        for meld in player_melds:
            for tile in meld.get("tiles", []):
                try:
                    counts[tile_id(tile)] += 1
                except KeyError:
                    pass
    return counts


# ----------------------------- chi simulation -----------------------------


def chi_consumed_for_kind(discard: str | None, kind: int) -> list[str] | None:
    clean = base_tile(discard)
    if not clean or len(clean) != 2 or clean[1] not in {"m", "p", "s"} or not clean[0].isdigit():
        return None
    rank = int(clean[0])
    suit = clean[1]
    if kind == 1 and rank <= 7:
        return [f"{rank + 1}{suit}", f"{rank + 2}{suit}"]
    if kind == 2 and 2 <= rank <= 8:
        return [f"{rank - 1}{suit}", f"{rank + 1}{suit}"]
    if kind == 3 and rank >= 3:
        return [f"{rank - 2}{suit}", f"{rank - 1}{suit}"]
    return None


def remove_consumed(hand: list[str], consumed: Iterable[str]) -> list[str] | None:
    trial = list(hand)
    for tile in consumed:
        if not remove_tile(trial, tile):
            return None
    return trial


def shanten_value(tiles: list[str]) -> int | None:
    try:
        return SHANTEN.calculate_shanten(counts_34(tiles), use_chiitoitsu=False, use_kokushi=False)
    except (KeyError, ValueError):
        return None


def best_discard_shanten(concealed_after_consumed: list[str]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    seen_ids = sorted({tile_id(tile) for tile in concealed_after_consumed})
    for idx in seen_ids:
        discard_name = base.TILES[idx]
        trial = list(concealed_after_consumed)
        if not remove_tile(trial, discard_name):
            continue
        shanten = shanten_value(trial)
        if shanten is None:
            continue
        # Tie-breaker: fewer honors/terminals discarded last; this is intentionally light.
        score = (shanten, 0 if base.tile_class(discard_name) in {"honor", "terminal"} else 1)
        if best is None or score < best["score"]:
            best = {
                "discard": discard_name,
                "after_shanten": shanten,
                "score": score,
                "concealed_after_discard_n": len(trial),
            }
    if best:
        best.pop("score", None)
    return best


def best_chi_after_shanten(hand: list[str], discard: str | None, kinds: set[int]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for kind in sorted(kinds & {1, 2, 3}):
        consumed = chi_consumed_for_kind(discard, kind)
        if not consumed:
            continue
        after_consumed = remove_consumed(hand, consumed)
        if after_consumed is None:
            continue
        item = best_discard_shanten(after_consumed)
        if not item:
            continue
        item.update({"kind": kind, "consumed": consumed})
        key = (item["after_shanten"], item["kind"])
        if best is None or key < (best["after_shanten"], best["kind"]):
            best = item
    return best


# ----------------------------- statistical summaries -----------------------------


def add_rate(counter: Counter, success: bool) -> None:
    counter["n"] += 1
    counter["success"] += int(success)


def rate_payload(success: int, n: int, success_key: str, rate_key: str) -> dict[str, Any]:
    rate = success / n if n else None
    ci = 1.96 * math.sqrt(rate * (1.0 - rate) / n) * 100.0 if n and rate is not None else None
    return {
        "n": int(n),
        success_key: int(success),
        rate_key: round1(rate * 100.0) if rate is not None else None,
        "ci95_half_width_pp": round2(ci),
    }


def effect_payload(
    condition: str,
    value: str,
    group_success: int,
    group_n: int,
    total_success: int,
    total_n: int,
    success_key: str,
    rate_key: str,
) -> dict[str, Any] | None:
    if group_n < MIN_CELL_N:
        return None
    comp_n = total_n - group_n
    comp_success = total_success - group_success
    if comp_n <= 0:
        return None
    item = rate_payload(group_success, group_n, success_key, rate_key)
    comp_rate = comp_success / comp_n if comp_n else None
    group_rate = group_success / group_n if group_n else None
    delta = (group_rate - comp_rate) * 100.0 if group_rate is not None and comp_rate is not None else None
    diff_ci = None
    significant = False
    if group_rate is not None and comp_rate is not None and comp_n >= MIN_CELL_N:
        diff_ci = 1.96 * math.sqrt(group_rate * (1.0 - group_rate) / group_n + comp_rate * (1.0 - comp_rate) / comp_n) * 100.0
        significant = bool(delta is not None and abs(delta) > diff_ci)
    item.update(
        {
            "condition": condition,
            "value": value,
            "complement_n": int(comp_n),
            f"complement_{success_key}": int(comp_success),
            f"complement_{rate_key}": round1(comp_rate * 100.0) if comp_rate is not None else None,
            "delta_pp_vs_complement": round1(delta),
            "diff_ci95_half_width_pp": round2(diff_ci),
            "significant": significant,
        }
    )
    return item


def sorted_effects(groups: dict[tuple[str, str], Counter], total: Counter, success_key: str, rate_key: str) -> list[dict[str, Any]]:
    items = []
    total_success = int(total["success"])
    total_n = int(total["n"])
    for (condition, value), counter in groups.items():
        item = effect_payload(condition, value, int(counter["success"]), int(counter["n"]), total_success, total_n, success_key, rate_key)
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: (abs(item.get("delta_pp_vs_complement") or 0.0), item["n"]), reverse=True)
    return items


def add_condition(groups: dict[tuple[str, str], Counter], condition: str, value: Any, success: bool) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        label = "yes" if value else "no"
    else:
        label = str(value)
    add_rate(groups[(condition, label)], success)


def summarize_counter(counter: Counter, success_key: str, rate_key: str) -> dict[str, Any]:
    return rate_payload(int(counter["success"]), int(counter["n"]), success_key, rate_key)


def serialize_bucket(counter: Counter, success_key: str, rate_key: str) -> dict[str, Any]:
    return summarize_counter(counter, success_key, rate_key)


def mean_std(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    if len(values) == 1:
        return values[0], 0.0
    return statistics.mean(values), statistics.pstdev(values)


def percentile(values: list[int | float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(float(v) for v in values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def dispersion_summary(per_game: dict[str, Counter], taken_turns: list[int]) -> dict[str, Any]:
    eligible = []
    for report_id, counter in sorted(per_game.items()):
        n = int(counter["n"])
        if n >= 3:
            pon = int(counter["success"])
            eligible.append(
                {
                    "report_id": report_id,
                    "n": n,
                    "pon": pon,
                    "pon_rate_pct": pct1(pon, n),
                }
            )
    total_n = sum(item["n"] for item in eligible)
    total_pon = sum(item["pon"] for item in eligible)
    weighted_mean = pct_raw(total_pon, total_n)
    if total_n and weighted_mean is not None:
        weighted_std = math.sqrt(
            sum(item["n"] * ((item["pon_rate_pct"] or 0.0) - weighted_mean) ** 2 for item in eligible) / total_n
        )
    else:
        weighted_std = None
    unweighted_mean, unweighted_std = mean_std([item["pon_rate_pct"] for item in eligible if item["pon_rate_pct"] is not None])
    turn_mean, turn_std = mean_std([float(turn) for turn in taken_turns])
    return {
        "per_game_yakuhai_pon_consistency": {
            "included_games_min_3_opportunities": len(eligible),
            "n": total_n,
            "pon": total_pon,
            "weighted_mean_pon_rate_pct": round1(weighted_mean),
            "weighted_std_pon_rate_pp": round1(weighted_std),
            "unweighted_mean_pon_rate_pct": round1(unweighted_mean),
            "unweighted_std_pon_rate_pp": round1(unweighted_std),
            "per_game": eligible,
        },
        "taken_yakuhai_pon_call_turn_distribution": {
            "n": len(taken_turns),
            "mean": round2(turn_mean),
            "std": round2(turn_std),
            "p25": round2(percentile(taken_turns, 0.25)),
            "p50": round2(percentile(taken_turns, 0.50)),
            "p75": round2(percentile(taken_turns, 0.75)),
        },
    }


# ----------------------------- proposed modifiers -----------------------------


def sig_items(effects: list[dict[str, Any]], condition: str | None = None, positive: bool | None = None) -> list[dict[str, Any]]:
    out = [item for item in effects if item.get("significant")]
    if condition is not None:
        out = [item for item in out if item.get("condition") == condition]
    if positive is not None:
        out = [item for item in out if (item.get("delta_pp_vs_complement") or 0) > 0 == positive]
    return out


def find_sig(effects: list[dict[str, Any]], condition: str, value: str) -> dict[str, Any] | None:
    for item in effects:
        if item.get("condition") == condition and item.get("value") == value and item.get("significant"):
            return item
    return None


def fmt_delta(delta: float | None) -> str:
    if delta is None:
        return "0pp"
    sign = "+" if delta >= 0 else "−"
    return f"{sign}{abs(delta):.1f}pp"


def build_proposed_modifiers(result: dict[str, Any]) -> list[str]:
    yak = result["condition_effects"]["yakuhai_pon"]
    chi = result["condition_effects"]["closed_to_open_chi"]
    yak_effects = yak["effects"]
    chi_effects = chi["effects"]
    yak_base = result["reproduced_baselines"]["yakuhai_pon"]["pon_rate_pct"]
    chi_base = result["reproduced_baselines"]["closed_to_open_chi"]["chi_rate_pct"]
    lines: list[str] = []

    for condition, value, label in [
        ("pair_is_dora", "yes", "when the yakuhai pair itself is dora"),
        ("dora_count", "3+", "with 3+ dora in hand"),
        ("turn_x_shanten", "turn_1-6_shanten_2-3", "when it is turns 1-6 at 2-3 shanten"),
        ("turn_x_shanten", "turn_7-12_shanten_0-1", "when it is turns 7-12 at 0-1 shanten"),
        ("turn_x_shanten", "turn_13+_shanten_0-1", "when it is turn 13+ at 0-1 shanten"),
        ("existing_table_threat", "yes", "when an opponent already has riichi or 2+ melds"),
        ("own_hand_already_open", "yes", "once the hand is already open"),
    ]:
        item = find_sig(yak_effects, condition, value)
        if item:
            lines.append(
                f"Yakuhai pon baseline {yak_base:.1f}%; {fmt_delta(item['delta_pp_vs_complement'])} {label} (n={item['n']})."
            )

    for condition, value, label in [
        ("best_chi_advances_to_le1", "yes", "when the best chi creates ≤1-shanten"),
        ("turn_bucket", "13+", "on turn 13+"),
        ("left_hai_num_le_12", "yes", "with ≤12 tiles left"),
        ("rank_3_4", "yes", "from 3rd/4th"),
        ("called_tile_is_dora", "yes", "when the called tile is dora"),
        ("dora_count", "2+", "with 2+ dora"),
    ]:
        item = find_sig(chi_effects, condition, value)
        if item:
            lines.append(
                f"First chi baseline {chi_base:.1f}%; {fmt_delta(item['delta_pp_vs_complement'])} {label} (n={item['n']})."
            )

    combo_effects = result["condition_effects"]["closed_to_open_chi"].get("interaction_effects", [])
    combo = find_sig(combo_effects, "best_chi_advances_to_le1_x_dora_2plus", "yes")
    if combo:
        lines.append(
            f"First chi baseline {chi_base:.1f}%; {fmt_delta(combo['delta_pp_vs_complement'])} when it creates ≤1-shanten with 2+ dora (n={combo['n']})."
        )

    # Deduplicate while preserving order, then cap at 8 one-liners. If too few, add strongest significant effects.
    deduped = []
    seen = set()
    for line in lines:
        if line not in seen:
            seen.add(line)
            deduped.append(line)
    if len(deduped) < 5:
        for item in [x for x in yak_effects + chi_effects if x.get("significant")]:
            prefix = "Yakuhai pon" if item in yak_effects else "First chi"
            base_rate = yak_base if item in yak_effects else chi_base
            rate_key = "pon_rate_pct" if item in yak_effects else "chi_rate_pct"
            line = (
                f"{prefix} baseline {base_rate:.1f}%; {fmt_delta(item['delta_pp_vs_complement'])} "
                f"for {item['condition']}={item['value']} ({item[rate_key]:.1f}%, n={item['n']})."
            )
            if line not in seen:
                seen.add(line)
                deduped.append(line)
            if len(deduped) >= 5:
                break
    return deduped[:8]


# ----------------------------- main miner -----------------------------


def mine() -> dict[str, Any]:
    groups = pass1.grouped_rows()
    source = {
        "csv_rows": sum(len(rows) for rows in groups.values()),
        "unique_report_ids": len(groups),
        "duplicate_report_rows": sum(max(0, len(rows) - 1) for rows in groups.values()),
        "processed_reports": 0,
        "target_seat_corrections_from_report_names": 0,
        "errors": [],
    }

    # Baseline counters reproduced from pass 1.
    yak_total = Counter()
    yak_by_copy = defaultdict(Counter)
    chi_open_total = Counter()
    chi_closed_to_open = Counter()
    chi_already_open = Counter()

    yak_effect_groups: dict[tuple[str, str], Counter] = defaultdict(Counter)
    chi_effect_groups: dict[tuple[str, str], Counter] = defaultdict(Counter)
    chi_combo_groups: dict[tuple[str, str], Counter] = defaultdict(Counter)

    per_game_yak = defaultdict(Counter)
    taken_yak_turns: list[int] = []

    diagnostics = {
        "yakuhai_pon_opportunities": 0,
        "closed_to_open_chi_opportunities": 0,
        "chi_best_after_shanten_available": 0,
        "chi_best_after_shanten_missing": 0,
    }

    for game_i, (report_id, rows) in enumerate(sorted(groups.items()), start=1):
        try:
            data = base.fetch_report(report_id)
            base.normalize_report(data)
            fallback_target = rows[0]["actor"]
            target = pass1.find_luckyj_target(data, fallback_target)
            if target != fallback_target:
                source["target_seat_corrections_from_report_names"] += 1
            row = pass1.choose_row(rows, target)
            pred = data.get("pred") or []

            for kyoku in pred:
                if not kyoku:
                    continue
                start = kyoku[0].get("info", {}).get("msg", {})
                tehais = start.get("tehais") or [[], [], [], []]
                if len(tehais) < 4:
                    continue
                hands = [list(h) for h in tehais[:4]]
                discards = [[], [], [], []]
                melds: list[list[dict[str, Any]]] = [[], [], [], []]
                open_melds = [0, 0, 0, 0]
                reached = [False, False, False, False]
                pending_riichi_discard = [False, False, False, False]
                dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []
                yakuhai_tiles = yakuhai_for_seat(start, target)
                target_rank_tier = rank_tier(start, target)
                target_rank_number = rank_number(start, target)
                target_round_wind = round_wind_bucket(start)
                is_dealer = start.get("oya") == target

                for pos, state in enumerate(kyoku):
                    msg = state.get("info", {}).get("msg", {})
                    actor = msg.get("actor")
                    msg_type = msg.get("type")

                    if msg_type == "dora" and msg.get("dora_marker"):
                        dora_markers.append(msg["dora_marker"])

                    if msg_type == "dahai" and pass1.huro_heads(state, target):
                        discard = msg.get("pai")
                        kinds = pass1.available_kinds(state, target)
                        if discard and kinds:
                            called, called_type, called_kind, _ = pass1.actual_call(kyoku, pos, target)
                            turn = len(discards[target]) + 1
                            turn_b = pass1.turn_bucket(turn)
                            shanten = pass1.shanten_value(hands[target])
                            shanten_b = shanten_bucket_3(shanten)
                            dora_n = pass1.dora_count(hands[target], dora_markers)
                            table_threat = existing_table_threat(target, reached, open_melds)

                            is_yakuhai_pon_opp = (
                                4 in kinds
                                and base_tile(discard) in yakuhai_tiles
                                and pass1.tile_count(hands[target], discard) >= 2
                            )
                            if is_yakuhai_pon_opp:
                                diagnostics["yakuhai_pon_opportunities"] += 1
                                poned = bool(called and called_type == "pon")
                                add_rate(yak_total, poned)
                                add_rate(per_game_yak[report_id], poned)
                                if poned:
                                    taken_yak_turns.append(turn)

                                copy_b = "first_discarded_copy" if pass1.prior_discard_count(discards, discard) == 0 else "later_copy"
                                add_rate(yak_by_copy[copy_b], poned)

                                add_condition(yak_effect_groups, "dora_count", yak_dora_bucket(dora_n), poned)
                                add_condition(yak_effect_groups, "pair_is_dora", is_tile_dora(discard, dora_markers), poned)
                                add_condition(yak_effect_groups, "dealer", is_dealer, poned)
                                add_condition(yak_effect_groups, "rank_tier", target_rank_tier, poned)
                                add_condition(yak_effect_groups, "round_wind", target_round_wind, poned)
                                add_condition(yak_effect_groups, "turn_x_shanten", turn_shanten_bucket(turn, shanten), poned)
                                add_condition(yak_effect_groups, "own_hand_already_open", open_melds[target] > 0, poned)
                                add_condition(
                                    yak_effect_groups,
                                    "second_yakuhai_pair_in_hand",
                                    has_second_yakuhai_pair(hands[target], discard, yakuhai_tiles),
                                    poned,
                                )
                                add_condition(yak_effect_groups, "existing_table_threat", table_threat, poned)

                            if kinds & {1, 2, 3}:
                                chii = bool(called and called_type == "chi")
                                open_b = "already_open" if open_melds[target] > 0 else "fully_closed"
                                add_rate(chi_open_total, chii)
                                if open_b == "already_open":
                                    add_rate(chi_already_open, chii)
                                else:
                                    add_rate(chi_closed_to_open, chii)
                                    diagnostics["closed_to_open_chi_opportunities"] += 1

                                    best_chi = best_chi_after_shanten(hands[target], discard, kinds)
                                    if best_chi is not None:
                                        diagnostics["chi_best_after_shanten_available"] += 1
                                        after_shanten = best_chi["after_shanten"]
                                        advances_to_le1 = bool(shanten is not None and after_shanten <= 1 and after_shanten < shanten)
                                    else:
                                        diagnostics["chi_best_after_shanten_missing"] += 1
                                        after_shanten = None
                                        advances_to_le1 = None

                                    left = msg.get("left_hai_num")
                                    rank_34 = target_rank_number in {3, 4} if target_rank_number is not None else None
                                    called_tile_dora = is_tile_dora(discard, dora_markers)

                                    add_condition(chi_effect_groups, "best_chi_advances_to_le1", advances_to_le1, chii)
                                    add_condition(chi_effect_groups, "dora_count", chi_dora_bucket(dora_n), chii)
                                    add_condition(chi_effect_groups, "turn_bucket", turn_b, chii)
                                    add_condition(chi_effect_groups, "left_hai_num_le_12", left is not None and left <= 12, chii)
                                    add_condition(chi_effect_groups, "rank_3_4", rank_34, chii)
                                    add_condition(chi_effect_groups, "called_tile_is_dora", called_tile_dora, chii)

                                    if advances_to_le1 is not None:
                                        add_condition(
                                            chi_combo_groups,
                                            "best_chi_advances_to_le1_x_dora_2plus",
                                            advances_to_le1 and dora_n >= 2,
                                            chii,
                                        )
                                        add_condition(
                                            chi_combo_groups,
                                            "best_chi_advances_to_le1_x_called_tile_dora",
                                            advances_to_le1 and called_tile_dora,
                                            chii,
                                        )

                    if msg_type == "tsumo" and actor is not None:
                        if msg.get("pai"):
                            hands[actor].append(msg["pai"])
                        discard_after = msg.get("real_dahai")
                        if discard_after and discard_after != "?":
                            remove_tile(hands[actor], discard_after)

                    elif msg_type in HURO_TYPES and actor is not None:
                        consumed = msg.get("consumed") or []
                        call_tiles = list(consumed) + ([msg.get("pai")] if msg.get("pai") else [])
                        melds[actor].append({"kind": msg_type, "tiles": call_tiles})
                        open_melds[actor] += 1
                        for tile in consumed:
                            remove_tile(hands[actor], tile)
                        discard_after = msg.get("real_dahai")
                        if discard_after and discard_after != "?":
                            remove_tile(hands[actor], discard_after)

                    elif msg_type == "ankan" and actor is not None:
                        consumed = msg.get("consumed") or []
                        melds[actor].append({"kind": msg_type, "tiles": list(consumed)})
                        for tile in consumed:
                            remove_tile(hands[actor], tile)

                    elif msg_type == "kakan" and actor is not None:
                        tile = msg.get("pai")
                        if tile:
                            melds[actor].append({"kind": msg_type, "tiles": [tile]})
                            remove_tile(hands[actor], tile)

                    elif msg_type == "reach" and actor is not None:
                        reached[actor] = True
                        pending_riichi_discard[actor] = True

                    elif msg_type == "dahai" and actor is not None:
                        tile = msg.get("pai")
                        if tile:
                            discards[actor].append(tile)
                            if pending_riichi_discard[actor]:
                                pending_riichi_discard[actor] = False

            source["processed_reports"] += 1
            if game_i % 200 == 0:
                print(f"processed {game_i}/{len(groups)} reports", file=sys.stderr)
        except Exception as exc:  # keep mining despite malformed reports
            source["errors"].append({"report_id": report_id, "error": repr(exc)})
            print(f"error {report_id}: {exc!r}", file=sys.stderr)

    yak_effects = sorted_effects(yak_effect_groups, yak_total, "pon", "pon_rate_pct")
    chi_effects = sorted_effects(chi_effect_groups, chi_closed_to_open, "chi", "chi_rate_pct")
    chi_combo_effects = sorted_effects(chi_combo_groups, chi_closed_to_open, "chi", "chi_rate_pct")

    result: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "definitions": {
            "call_opportunity": "Reused from scripts/mine_rx_calls.py: a dahai state whose huro map contains LuckyJ's seat; msg.pai is the triggering discard.",
            "actual_call": "Reused from scripts/mine_rx_calls.py: the next state is chi, pon, or daiminkan with actor equal to LuckyJ's seat.",
            "yakuhai_pon_opportunity": "Reused first-pass detector: triggering discard is yakuhai for LuckyJ, LuckyJ holds at least two of that tile in concealed hand, and huro options contain kind 4 (pon).",
            "closed_to_open_chi_opportunity": "huro options contain any chi kind (1, 2, 3) and LuckyJ has no prior open chi/pon/daiminkan meld; closed kan is not counted as open.",
            "turn": "len(discards[LuckyJ]) + 1 before adding the triggering discard.",
            "shanten": "Regular-hand shanten of LuckyJ's current concealed tiles using mahjong.shanten.Shanten and counts_34; chiitoitsu/kokushi disabled. Shortened concealed hands after calls are evaluated the same way as build_point_examples.post_call_eval.",
            "dora_mapping": "Ranks wrap 9→1 in suit; winds E→S→W→N→E; dragons P→F→C→P; red fives add one dora and also count as normal dora if the dora tile is five.",
            "yakuhai_pair_is_dora": "The triggering yakuhai tile is among dora tiles pointed to by visible dora indicators.",
            "second_yakuhai_pair_in_hand": "Besides the called yakuhai pair, LuckyJ has another yakuhai tile with at least two copies in concealed hand.",
            "existing_table_threat": "Any opponent has declared riichi or already has at least two open chi/pon/daiminkan melds before the opportunity.",
            "best_chi_advances_to_le1": "For closed-to-open chi opportunities, simulate all available chi kinds from huro options, remove consumed tiles, choose the discard that minimizes post-call shanten, and mark yes iff post-call shanten is ≤1 and lower than pre-call shanten.",
            "condition_effect_delta_pp_vs_complement": "Cell rate minus rate for all other opportunities in the same population.",
            "ci95_half_width_pp": "1.96*sqrt(p*(1-p)/n)*100 for the cell rate.",
            "significant": f"True when n and complement_n are at least {MIN_CELL_N} and |delta_pp_vs_complement| exceeds the 95% two-proportion normal half-width.",
            "min_cell_n": MIN_CELL_N,
            "all_rates_are_percent": True,
            "call_kind_labels": {str(k): v for k, v in CALL_KIND_LABELS.items()},
        },
        "reproduced_baselines": {
            "yakuhai_pon": serialize_bucket(yak_total, "pon", "pon_rate_pct"),
            "first_copy_yakuhai_pon": serialize_bucket(yak_by_copy["first_discarded_copy"], "pon", "pon_rate_pct"),
            "later_copy_yakuhai_pon": serialize_bucket(yak_by_copy["later_copy"], "pon", "pon_rate_pct"),
            "closed_to_open_chi": serialize_bucket(chi_closed_to_open, "chi", "chi_rate_pct"),
            "already_open_chi": serialize_bucket(chi_already_open, "chi", "chi_rate_pct"),
            "all_chi_opportunities": serialize_bucket(chi_open_total, "chi", "chi_rate_pct"),
        },
        "condition_effects": {
            "yakuhai_pon": {
                "population": serialize_bucket(yak_total, "pon", "pon_rate_pct"),
                "effects_sorted_by_abs_delta_pp": True,
                "effects": yak_effects,
            },
            "closed_to_open_chi": {
                "population": serialize_bucket(chi_closed_to_open, "chi", "chi_rate_pct"),
                "effects_sorted_by_abs_delta_pp": True,
                "effects": chi_effects,
                "interaction_effects_note": "Not part of the one-at-a-time requirement; included only to support proposed_modifiers when significant.",
                "interaction_effects": chi_combo_effects,
            },
        },
        "dispersion": dispersion_summary(per_game_yak, taken_yak_turns),
        "diagnostics": diagnostics,
    }
    result["proposed_modifiers"] = build_proposed_modifiers(result)
    return result


def main() -> None:
    result = mine()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(json.dumps(result["reproduced_baselines"], ensure_ascii=False, sort_keys=True))
    if result["source"]["errors"]:
        print(f"errors: {len(result['source']['errors'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
