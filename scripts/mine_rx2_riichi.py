#!/usr/bin/env python3
"""Second-pass mining for LuckyJ riichi declaration condition effects and dispersion."""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import analyze_luckyj as base
import mine_rx_riichi as rx1
from extract_case_studies import remove_tile

REPO_ROOT = Path(__file__).resolve().parents[1]
base.SHEET_CSV = REPO_ROOT / "data" / "LuckyJ.csv"
base.CACHE_DIR = REPO_ROOT / "data" / "report_cache"

OUT = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx2-riichi.json")
MIN_CELL_N = 120
SOUTH4_MIN_N = 100

WAIT_STRATA = ("<=3", "4-7")
DANGER_KEYS = rx1.DANGER_KEYS
OPEN_CALL_TYPES = rx1.OPEN_CALL_TYPES


CONDITIONS = [
    ("dealer", "dealer_vs_non_dealer"),
    ("rank_start", "rank_at_kyoku_start"),
    ("dora_count_bucket", "dora_count_in_tenpai_hand"),
    ("turn_bucket", "turn"),
    ("tiles_left_bucket", "tiles_left"),
    ("existing_threat", "existing_threat"),
    ("kyotaku_start", "kyotaku_sticks_at_start"),
    ("honba_start", "honba_at_start"),
    ("round_wind", "round_wind"),
    ("south4", "south_4_specific"),
    ("winning_tile_types_bucket", "distinct_winning_tile_types"),
]

VALUE_ORDER = {
    "dealer": ["dealer", "nondealer"],
    "rank_start": ["rank1_10k+_lead", "rank1_small_lead", "rank2-3", "rank4"],
    "dora_count_bucket": ["0", "1", "2+"],
    "turn_bucket": ["<=8", "9+"],
    "tiles_left_bucket": [">28", "28-15", "<15"],
    "existing_threat": ["none", "opponent_riichi", "2_meld_open"],
    "kyotaku_start": ["0", "1+"],
    "honba_start": ["0", "1+"],
    "round_wind": ["East", "South"],
    "south4": ["South-4", "not_South-4"],
    "winning_tile_types_bucket": ["1", "2+"],
}


def pct(num, den, digits=1):
    return round(100.0 * num / den, digits) if den else None


def mean(values):
    return sum(values) / len(values) if values else None


def population_std(values):
    if not values:
        return None
    mu = mean(values)
    return math.sqrt(sum((value - mu) ** 2 for value in values) / len(values))


def weighted_std(values, weights):
    total_w = sum(weights)
    if not values or total_w <= 0:
        return None
    mu = sum(value * weight for value, weight in zip(values, weights)) / total_w
    return math.sqrt(sum(weight * (value - mu) ** 2 for value, weight in zip(values, weights)) / total_w)


def percentile(values, q):
    values = sorted(values)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    pos = (len(values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return values[lo]
    return values[lo] * (hi - pos) + values[hi] * (pos - lo)


def ci95_half_width_pp(yes, n):
    if not n:
        return None
    p = yes / n
    return 1.96 * math.sqrt(p * (1.0 - p) / n) * 100.0


def delta_ci95_half_width_pp(yes, n, comp_yes, comp_n):
    if not n or not comp_n:
        return None
    p = yes / n
    q = comp_yes / comp_n
    return 1.96 * math.sqrt((p * (1.0 - p) / n) + (q * (1.0 - q) / comp_n)) * 100.0


def rate_entry(n, declares):
    return {
        "n": n,
        "declares": declares,
        "declare_rate_pct": pct(declares, n),
        "ci95_half_width_pp": round(ci95_half_width_pp(declares, n), 1) if n else None,
    }


def sorted_values(condition_key, values):
    order = VALUE_ORDER.get(condition_key, [])
    return sorted(values, key=lambda value: (order.index(value) if value in order else len(order), str(value)))


def tile_name(tile):
    if tile is None or tile == "?":
        return None
    if isinstance(tile, int):
        if 0 <= tile < 34:
            return base.TILES[tile]
        if 0 <= tile < 136:
            return base.TILES[tile // 4]
        return None
    return str(tile)


def dora_from_marker(marker):
    marker = tile_name(marker)
    if not marker:
        return None
    marker = marker.replace("r", "")
    if len(marker) == 2 and marker[0].isdigit() and marker[1] in {"m", "p", "s"}:
        rank = int(marker[0])
        return f"{1 if rank == 9 else rank + 1}{marker[1]}"
    winds = ["E", "S", "W", "N"]
    dragons = ["P", "F", "C"]
    if marker in winds:
        return winds[(winds.index(marker) + 1) % len(winds)]
    if marker in dragons:
        return dragons[(dragons.index(marker) + 1) % len(dragons)]
    return None


def initial_dora_markers(start):
    markers = []
    multi = start.get("dora_markers")
    if isinstance(multi, list):
        markers.extend(marker for marker in multi if marker not in (None, "?"))
    marker = start.get("dora_marker")
    if marker not in (None, "?") and marker not in markers:
        markers.append(marker)
    return markers


def dora_count_for_tiles(tiles, dora_markers):
    dora_indices = []
    for marker in dora_markers:
        dora = dora_from_marker(marker)
        if dora is not None:
            dora_indices.append(base.IDX[dora])
    count = 0
    for tile in tiles or []:
        name = tile_name(tile)
        if not name:
            continue
        if name.endswith("r"):
            count += 1
        try:
            idx = rx1.tile_id(name)
        except KeyError:
            continue
        count += sum(1 for dora_idx in dora_indices if dora_idx == idx)
    return count


def bucket_dora_count(count):
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    return "2+"


def bucket_dora_two_way(count):
    return "2+" if count >= 2 else "0-1"


def wait_stratum(wait_remaining):
    if wait_remaining is None:
        return "unknown"
    if wait_remaining <= 3:
        return "<=3"
    if wait_remaining <= 7:
        return "4-7"
    return "8+"


def turn_bucket(turn):
    if turn is None:
        return "unknown"
    return "<=8" if turn <= 8 else "9+"


def tiles_left_bucket(left):
    if left is None:
        return "unknown"
    if left > 28:
        return ">28"
    if left >= 15:
        return "28-15"
    return "<15"


def existing_threat_bucket(target, reached, open_melds):
    opp_riichi, open_2meld = rx1.threat_flags(target, reached, open_melds)
    if opp_riichi:
        return "opponent_riichi"
    if open_2meld:
        return "2_meld_open"
    return "none"


def int_or_zero(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def round_wind_bucket(start):
    wind = start.get("bakaze")
    if wind == "E":
        return "East"
    if wind == "S":
        return "South"
    return "Other"


def south4_bucket(start):
    return "South-4" if start.get("bakaze") == "S" and int_or_zero(start.get("kyoku")) == 4 else "not_South-4"


def winning_tile_types_bucket(wait_types):
    if not isinstance(wait_types, int):
        return "unknown"
    if wait_types == 1:
        return "1"
    if wait_types >= 2:
        return "2+"
    return "unknown"


def post_discard_hand(hand14, discard):
    hand = list(hand14 or [])
    if discard in (None, "?"):
        return None
    if not remove_tile(hand, discard):
        return None
    return hand


def flatten_melds(melds_for_seat):
    tiles = []
    for meld in melds_for_seat or []:
        tiles.extend(tile for tile in meld if tile not in (None, "?"))
    return tiles


def safe_start_reached(start):
    reached = [False, False, False, False]
    raw = start.get("reached")
    if isinstance(raw, list):
        for seat, value in enumerate(raw[:4]):
            reached[seat] = bool(value)
    return reached


def collect_opportunities():
    rows = base.parse_rows()
    meta = {
        "rows_seen": len(rows),
        "unique_report_ids_seen": len({row["report_id"] for row in rows}),
        "reports_processed": 0,
        "kyoku_seen": 0,
        "errors": [],
    }
    first_opps = []
    declaration_threat_dangers = []
    declaration_threat_counts = Counter()

    for row_idx, row in enumerate(rows, 1):
        if row_idx % 200 == 0:
            print(f"processed {row_idx}/{len(rows)} rows", file=sys.stderr, flush=True)
        target = row.get("actor")
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
            meta["reports_processed"] += 1
        except Exception as exc:
            meta["errors"].append({"report_id": row.get("report_id"), "error": repr(exc)})
            continue

        for kyoku_index, kyoku in enumerate(data.get("pred") or []):
            if not kyoku:
                continue
            meta["kyoku_seen"] += 1
            start = kyoku[0].get("info", {}).get("msg", {})
            tehais = start.get("tehais") or [[], [], [], []]
            if len(tehais) < 4 or target is None or not (0 <= target < 4):
                continue

            hands = [list(tehais[seat]) for seat in range(4)]
            discards = [[], [], [], []]
            reached = safe_start_reached(start)
            open_melds = [0, 0, 0, 0]
            melds = [[], [], [], []]
            public_visible = Counter()
            dora_markers = initial_dora_markers(start)
            for marker in dora_markers:
                rx1.add_visible(public_visible, marker)

            reach_opps = []
            kyotaku = int_or_zero(start.get("kyotaku"))
            honba = int_or_zero(start.get("honba"))

            for pos, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")

                if msg_type == "dora":
                    marker = msg.get("dora_marker")
                    if marker not in (None, "?"):
                        dora_markers.append(marker)
                        rx1.add_visible(public_visible, marker)

                # Draw first, matching pass 1's opportunity detector.
                if msg_type == "tsumo" and actor is not None and 0 <= actor < 4:
                    pai = msg.get("pai")
                    if pai:
                        hands[actor].append(pai)

                if actor == target and "reach" in state:
                    actual = msg.get("real_dahai")
                    next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
                    declared = next_msg.get("type") == "reach" and next_msg.get("actor") == target
                    turn = len(discards[target]) + 1
                    left = msg.get("left_hai_num")
                    hand14 = list(hands[actor])
                    w_info = rx1.wait_info_after_discard(hand14, actual, public_visible)
                    post_hand = post_discard_hand(hand14, actual)
                    dora_tiles = list(post_hand or []) + flatten_melds(melds[target])
                    dora_count = dora_count_for_tiles(dora_tiles, dora_markers)
                    w_stratum = wait_stratum(w_info.get("wait_tiles_remaining"))
                    threat_bucket = existing_threat_bucket(target, reached, open_melds)
                    dealer_bucket = "dealer" if start.get("oya") == target else "nondealer"
                    wait_types = w_info.get("wait_types")

                    opp = {
                        "game": row.get("idx"),
                        "report_id": row.get("report_id"),
                        "kyoku_index": kyoku_index,
                        "pos": pos,
                        "declared": bool(declared),
                        "turn": turn,
                        "left": left,
                        "wait_tiles_remaining": w_info.get("wait_tiles_remaining"),
                        "wait_bucket_pass1": rx1.wait_bucket(w_info.get("wait_tiles_remaining")),
                        "wait_stratum": w_stratum,
                        "wait_types": wait_types,
                        "winning_tile_types_bucket": winning_tile_types_bucket(wait_types),
                        "dora_count": dora_count,
                        "dora_count_bucket": bucket_dora_count(dora_count),
                        "dora_two_way_bucket": bucket_dora_two_way(dora_count),
                        "dealer": dealer_bucket,
                        "rank_start": rx1.score_position_bucket(start, target),
                        "turn_bucket": turn_bucket(turn),
                        "tiles_left_bucket": tiles_left_bucket(left),
                        "existing_threat": threat_bucket,
                        "opponent_riichi_present": "yes" if any(seat != target and reached[seat] for seat in range(4)) else "no",
                        "open_2meld_present": "yes" if any(seat != target and open_melds[seat] >= 2 for seat in range(4)) else "no",
                        "kyotaku_start": "1+" if kyotaku >= 1 else "0",
                        "honba_start": "1+" if honba >= 1 else "0",
                        "round_wind": round_wind_bucket(start),
                        "south4": south4_bucket(start),
                    }
                    reach_opps.append(opp)

                    # Dispersion: all actual declarations, not just first opportunity, into an existing threat.
                    if declared:
                        declaration_threat_counts["declares"] += 1
                        seats = rx1.threat_seats(target, reached, open_melds)
                        if seats:
                            declaration_threat_counts["declares_with_existing_threat"] += 1
                            danger = rx1.danger_for_tile(state, target, actual, seats=seats)
                            if danger is not None:
                                declaration_threat_dangers.append(danger)
                                declaration_threat_counts["danger_known_n"] += 1
                                if danger > 0.10:
                                    declaration_threat_counts["danger_>10pct"] += 1

                # Now mutate replay state after all analyses at this state.
                if msg_type == "tsumo" and actor is not None and 0 <= actor < 4:
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)
                else:
                    rx1.update_public_and_hands_after_state(
                        msg, actor, msg_type, hands, discards, public_visible, reached, open_melds, melds
                    )

            if reach_opps:
                first_opps.append(reach_opps[0])

    return meta, first_opps, declaration_threat_dangers, declaration_threat_counts


def make_effect(condition_key, condition_label, value, n, declares, total_n, total_declares):
    comp_n = total_n - n
    comp_declares = total_declares - declares
    rate = declares / n if n else None
    comp_rate = comp_declares / comp_n if comp_n else None
    delta = (rate - comp_rate) * 100.0 if rate is not None and comp_rate is not None else None
    ci = ci95_half_width_pp(declares, n)
    delta_ci = delta_ci95_half_width_pp(declares, n, comp_declares, comp_n)
    meets_min = n >= MIN_CELL_N and comp_n >= MIN_CELL_N
    if condition_key == "south4" and value == "South-4":
        meets_min = n >= SOUTH4_MIN_N and comp_n >= MIN_CELL_N
    significant = bool(meets_min and delta_ci is not None and delta is not None and abs(delta) > delta_ci)
    return {
        "condition": condition_label,
        "condition_key": condition_key,
        "value": value,
        "n": n,
        "declares": declares,
        "declare_rate_pct": pct(declares, n),
        "ci95_half_width_pp": round(ci, 1) if ci is not None else None,
        "complement_n": comp_n,
        "complement_declares": comp_declares,
        "complement_rate_pct": pct(comp_declares, comp_n),
        "delta_pp": round(delta, 1) if delta is not None else None,
        "delta_ci95_half_width_pp": round(delta_ci, 1) if delta_ci is not None else None,
        "meets_min_cell_n": meets_min,
        "significant": significant,
    }


def build_condition_effects(first_opps):
    out = {}
    for stratum in WAIT_STRATA:
        records = [opp for opp in first_opps if opp.get("wait_stratum") == stratum]
        baseline_declares = sum(1 for opp in records if opp["declared"])
        by_condition = {}
        sorted_effects = []

        for condition_key, condition_label in CONDITIONS:
            counts = defaultdict(Counter)
            for opp in records:
                value = opp.get(condition_key)
                if value in (None, "unknown", "Other"):
                    continue
                counts[value]["n"] += 1
                counts[value]["declares"] += int(opp["declared"])
            total_n = sum(bucket["n"] for bucket in counts.values())
            total_declares = sum(bucket["declares"] for bucket in counts.values())
            cells = []
            for value in sorted_values(condition_key, counts.keys()):
                bucket = counts[value]
                effect = make_effect(
                    condition_key,
                    condition_label,
                    value,
                    bucket["n"],
                    bucket["declares"],
                    total_n,
                    total_declares,
                )
                cells.append(effect)
                sorted_effects.append(effect)
            by_condition[condition_label] = {
                "condition_key": condition_key,
                "n": total_n,
                "declares": total_declares,
                "declare_rate_pct": pct(total_declares, total_n),
                "values": sorted(
                    cells,
                    key=lambda item: abs(item["delta_pp"]) if item["delta_pp"] is not None else -1,
                    reverse=True,
                ),
            }

        out[stratum] = {
            "baseline": rate_entry(len(records), baseline_declares),
            "by_condition": by_condition,
            "sorted_effects": sorted(
                sorted_effects,
                key=lambda item: abs(item["delta_pp"]) if item["delta_pp"] is not None else -1,
                reverse=True,
            ),
        }
    return out


def build_two_way(first_opps):
    cells = []
    for stratum in WAIT_STRATA:
        for dora_bucket in ("0-1", "2+"):
            for dealer_bucket in ("dealer", "nondealer"):
                records = [
                    opp for opp in first_opps
                    if opp.get("wait_stratum") == stratum
                    and opp.get("dora_two_way_bucket") == dora_bucket
                    and opp.get("dealer") == dealer_bucket
                ]
                declares = sum(1 for opp in records if opp["declared"])
                cell = rate_entry(len(records), declares)
                cell.update({
                    "waits": stratum,
                    "dora_count": dora_bucket,
                    "dealer": dealer_bucket,
                })
                cells.append(cell)
    return {
        "definitions": {
            "waits": "First opportunity unseen winning-tile copies after LuckyJ's actual discard, bucketed as <=3 or 4-7.",
            "dora_count": "0-1 vs 2+ dora in the tenpai hand after the actual discard, including red fives.",
            "dealer": "LuckyJ is start-of-kyoku oya vs not.",
        },
        "cells": cells,
    }


def build_baselines(first_opps):
    overall_declares = sum(1 for opp in first_opps if opp["declared"])
    wait_counts = defaultdict(Counter)
    for opp in first_opps:
        wait_counts[opp["wait_stratum"]]["n"] += 1
        wait_counts[opp["wait_stratum"]]["declares"] += int(opp["declared"])
    pass1_targets = {
        "first_opportunity_declare_rate_pct": 66.9,
        "by_unseen_waits_pct": {"8+": 93.6, "4-7": 79.5, "<=3": 36.1},
    }
    by_waits = {}
    for key in ("8+", "4-7", "<=3", "unknown"):
        bucket = wait_counts.get(key, Counter())
        by_waits[key] = rate_entry(bucket["n"], bucket["declares"])
    comparisons = {
        "overall_within_1pp": abs(pct(overall_declares, len(first_opps)) - pass1_targets["first_opportunity_declare_rate_pct"]) <= 1.0,
        "by_waits_within_1pp": {
            key: abs(by_waits[key]["declare_rate_pct"] - target) <= 1.0
            for key, target in pass1_targets["by_unseen_waits_pct"].items()
        },
    }
    return {
        "pass1_targets": pass1_targets,
        "computed": {
            "first_opportunity": rate_entry(len(first_opps), overall_declares),
            "by_unseen_waits": by_waits,
        },
        "comparisons": comparisons,
    }


def build_dispersion(first_opps, threat_dangers, threat_counts):
    danger_known_n = len(threat_dangers)
    danger_gt_10 = sum(1 for value in threat_dangers if value > 0.10)

    game_counts = defaultdict(Counter)
    for opp in first_opps:
        game_counts[opp["game"]]["n"] += 1
        game_counts[opp["game"]]["declares"] += int(opp["declared"])
    game_records = []
    for game, bucket in sorted(game_counts.items()):
        if bucket["n"] >= 2:
            game_records.append({
                "game": game,
                "n": bucket["n"],
                "declares": bucket["declares"],
                "declare_rate_pct": pct(bucket["declares"], bucket["n"]),
            })
    rates = [record["declares"] / record["n"] for record in game_records]
    weights = [record["n"] for record in game_records]
    weighted_mean = sum(rate * weight for rate, weight in zip(rates, weights)) / sum(weights) if weights else None
    weighted_std_value = weighted_std(rates, weights)
    unweighted_mean = mean(rates)
    unweighted_std_value = population_std(rates)

    return {
        "declaration_stick_tile_danger_into_existing_threat": {
            "declares": threat_counts["declares"],
            "declares_with_existing_threat": threat_counts["declares_with_existing_threat"],
            "declares_with_existing_threat_rate_pct": pct(threat_counts["declares_with_existing_threat"], threat_counts["declares"]),
            "danger_known_n": danger_known_n,
            "mean": round(mean(threat_dangers), 4) if threat_dangers else None,
            "std": round(population_std(threat_dangers), 4) if threat_dangers else None,
            "p50": round(percentile(threat_dangers, 0.50), 4) if threat_dangers else None,
            "p75": round(percentile(threat_dangers, 0.75), 4) if threat_dangers else None,
            "mean_pct": round(mean(threat_dangers) * 100.0, 1) if threat_dangers else None,
            "std_pct": round(population_std(threat_dangers) * 100.0, 1) if threat_dangers else None,
            "p50_pct": round(percentile(threat_dangers, 0.50) * 100.0, 1) if threat_dangers else None,
            "p75_pct": round(percentile(threat_dangers, 0.75) * 100.0, 1) if threat_dangers else None,
            "danger_>10pct": danger_gt_10,
            "danger_>10pct_rate_pct": pct(danger_gt_10, danger_known_n),
        },
        "per_game_consistency": {
            "min_first_opportunities_per_game": 2,
            "games_n": len(game_records),
            "first_opportunities_n": sum(weights),
            "declares": sum(record["declares"] for record in game_records),
            "weighted_mean_declare_rate_pct": round(weighted_mean * 100.0, 1) if weighted_mean is not None else None,
            "weighted_std_declare_rate_pct": round(weighted_std_value * 100.0, 1) if weighted_std_value is not None else None,
            "unweighted_mean_declare_rate_pct": round(unweighted_mean * 100.0, 1) if unweighted_mean is not None else None,
            "unweighted_std_declare_rate_pct": round(unweighted_std_value * 100.0, 1) if unweighted_std_value is not None else None,
            "p50_declare_rate_pct": round(percentile(rates, 0.50) * 100.0, 1) if rates else None,
            "p25_declare_rate_pct": round(percentile(rates, 0.25) * 100.0, 1) if rates else None,
            "p75_declare_rate_pct": round(percentile(rates, 0.75) * 100.0, 1) if rates else None,
        },
    }


def label_for_effect(effect):
    condition = effect["condition_key"]
    value = effect["value"]
    labels = {
        ("dealer", "dealer"): "as dealer",
        ("dealer", "nondealer"): "as non-dealer",
        ("rank_start", "rank1_10k+_lead"): "holding 1st with a 10k+ lead",
        ("rank_start", "rank1_small_lead"): "holding 1st without a 10k lead",
        ("rank_start", "rank2-3"): "starting 2nd-3rd",
        ("rank_start", "rank4"): "starting 4th",
        ("dora_count_bucket", "0"): "with 0 dora",
        ("dora_count_bucket", "1"): "with 1 dora",
        ("dora_count_bucket", "2+"): "with 2+ dora",
        ("turn_bucket", "<=8"): "by turn 8",
        ("turn_bucket", "9+"): "on turn 9+",
        ("tiles_left_bucket", ">28"): "with >28 tiles left",
        ("tiles_left_bucket", "28-15"): "with 28-15 tiles left",
        ("tiles_left_bucket", "<15"): "with <15 tiles left",
        ("existing_threat", "none"): "with no existing threat",
        ("existing_threat", "opponent_riichi"): "into opponent riichi",
        ("existing_threat", "2_meld_open"): "against a 2-meld open threat",
        ("kyotaku_start", "0"): "with no kyotaku stick",
        ("kyotaku_start", "1+"): "with kyotaku on the table",
        ("honba_start", "0"): "with no honba",
        ("honba_start", "1+"): "with honba on the table",
        ("round_wind", "East"): "in East round",
        ("round_wind", "South"): "in South round",
        ("south4", "South-4"): "in South-4",
        ("south4", "not_South-4"): "outside South-4",
        ("winning_tile_types_bucket", "1"): "on one winning tile type",
        ("winning_tile_types_bucket", "2+"): "on 2+ winning tile types",
    }
    return labels.get((condition, value), f"{condition}={value}")


def build_proposed_modifiers(condition_effects):
    candidates = []
    for stratum, section in condition_effects.items():
        baseline = section["baseline"]["declare_rate_pct"]
        for effect in section["sorted_effects"]:
            if effect.get("significant"):
                candidates.append((abs(effect["delta_pp"]), stratum, baseline, effect))
    candidates.sort(reverse=True, key=lambda item: item[0])

    lines = []
    seen = set()
    for _, stratum, baseline, effect in candidates:
        # Avoid immediate binary duplicates that say the same thing in reverse.
        binary_key = (stratum, effect["condition_key"])
        if effect["condition_key"] in {"dealer", "turn_bucket", "kyotaku_start", "honba_start", "round_wind", "south4", "winning_tile_types_bucket"} and binary_key in seen:
            continue
        seen.add(binary_key)
        direction = "adds" if effect["delta_pp"] > 0 else "cuts"
        lines.append(
            f"At {stratum} waits baseline {baseline}%; {label_for_effect(effect)} {direction} {abs(effect['delta_pp']):.1f}pp "
            f"(rate {effect['declare_rate_pct']}%, n={effect['n']})."
        )
        if len(lines) >= 8:
            break
    return lines


def analyze():
    meta, first_opps, threat_dangers, threat_counts = collect_opportunities()
    baselines = build_baselines(first_opps)
    condition_effects = build_condition_effects(first_opps)
    two_way = build_two_way(first_opps)
    dispersion = build_dispersion(first_opps, threat_dangers, threat_counts)
    result = {
        "definitions": {
            "source": "data/report_cache/*.json.gz via scripts/analyze_luckyj.py parse_rows/fetch_report/normalize_report",
            "reused_pass1_code": "Opportunity detection, shanten/wait calculation, hand mutation, score-position, threat, danger and visible-tile helpers are reused from scripts/mine_rx_riichi.py.",
            "riichi_opportunity": "LuckyJ state containing state['reach']; declaration iff next state's msg is type='reach' with actor==LuckyJ. First opportunity is the first such state per LuckyJ kyoku.",
            "declare_at_first_opportunity": "Binary outcome for only the first riichi opportunity in each LuckyJ kyoku.",
            "wait_tiles_remaining": "After LuckyJ's actual real_dahai from the 14-tile hand, winning tile types are tiles that make shanten -1; remaining copies are 4 minus own post-discard hand, all rivers, called/kan tiles, and dora indicators visible so far, matching pass 1.",
            "wait_strata": "<=3 and 4-7 unseen winning-tile copies are the marginal strata used for condition effects; 8+ is retained only for reproduced baselines.",
            "distinct_winning_tile_types": "Count of distinct tile types that complete the post-discard tenpai hand, bucketed 1 vs 2+.",
            "dora_count_in_tenpai_hand": "Dora in the post-discard tenpai hand plus closed/open kan tiles tracked for the target; red fives add one dora. If a red five is also marker dora it counts both red and normal dora.",
            "dora_mapping": "Suits wrap 9->1; winds E->S->W->N->E; dragons P->F->C->P.",
            "rank_at_kyoku_start": "Start-of-kyoku scores and seat2rank; rank1_10k+_lead means first place leads second by at least 10,000.",
            "turn_and_tiles_left": "Turn is len(discards[LuckyJ])+1 before LuckyJ's discard, bucketed <=8 vs 9+. Tiles left is left_hai_num bucketed >28, 28-15, <15.",
            "existing_threat": "Priority bucket: opponent_riichi if any opponent already reached; else 2_meld_open if any opponent has at least two open calls; else none.",
            "kyotaku_honba_start": "Kyotaku and honba are read from kyoku start and bucketed 0 vs 1+ separately.",
            "round": "Round wind is East vs South; South-4 is also evaluated specifically. South-4 is displayed even from n>=100, but significance still requires a stable complement.",
            "condition_effect_stats": "For each value within each wait stratum: declare rate, n, normal 95% CI half-width 1.96*sqrt(p(1-p)/n)*100, delta_pp versus the complement of that value, and a significant flag.",
            "significant_flag": f"True when the value and complement meet min cell n={MIN_CELL_N} (South-4 value allowed from n={SOUTH4_MIN_N}) and the 95% two-proportion CI for delta excludes 0.",
            "declaration_stick_tile_danger": "Max danger_s/danger_t/danger_k for LuckyJ's declaration discard, restricted to opponent seats that are existing threats, scaled /10000.",
            "per_game_consistency": "For games with at least two first opportunities, per-game declare rates are summarized with opportunity-weighted mean/std; std is population weighted standard deviation.",
        },
        "meta": meta,
        "reproduced_baselines": baselines,
        "condition_effects": condition_effects,
        "two_way_waits_x_dora_x_dealer": two_way,
        "dispersion": dispersion,
    }
    result["proposed_modifiers"] = build_proposed_modifiers(condition_effects)
    return result


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result = analyze()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
