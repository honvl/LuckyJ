#!/usr/bin/env python3
"""Second-pass defense mining: condition effects and dispersion for LuckyJ push/fold."""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from mahjong.shanten import Shanten

import analyze_luckyj as base
from extract_case_studies import counts_34

OUT = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx2-defense.json")
SHANTEN = Shanten()

DANGER_SUFFIXES = ("s", "t", "k")
TENPAI_SUFFIXES = ("s", "t", "k")
HURO_TYPES = base.HURO_TYPES

WINDS = ["E", "S", "W", "N"]
DRAGONS = {"P", "F", "C"}
DORA_COUNT_ORDER = ["0", "1", "2", "3+"]
DORA_BINARY_ORDER = ["0-1", "2+"]
YES_NO_ORDER = ["yes", "no"]
RANK_BUCKET_ORDER = ["1-2", "3-4", "unknown"]
LEFT_BUCKET_ORDER = [">40", "40-21", "<=20", "unknown"]
GENBUTSU_COUNT_ORDER = ["0", "1", "2+"]
SHANTEN_ORDER = ["0", "1", "2", "3+", "unknown"]
OPEN_OWN_SHANTEN_ORDER = ["<=1", "2+", "unknown"]
MIN_CELL_N = 150


# ----------------------------- basic formatting -----------------------------


def pct(value: int | float | None, den: int | float | None) -> float | None:
    if not den:
        return None
    return round(100.0 * float(value) / float(den), 1)


def round1(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None


def round2(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def round4(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    # Nearest-rank percentile, matching the first-pass script.
    index = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


class BinStats:
    """Danger-threshold proxy; this does not by itself classify strategic push/fold."""

    def __init__(self) -> None:
        self.total_states = 0
        self.n = 0
        self.push = 0

    def add(self, danger: float | None) -> None:
        self.total_states += 1
        if danger is None:
            return
        self.n += 1
        if danger > 0.05:
            self.push += 1

    @property
    def rate_pct(self) -> float | None:
        return pct(self.push, self.n)

    @property
    def p(self) -> float | None:
        if not self.n:
            return None
        return self.push / self.n

    @property
    def ci95_half_width_pp(self) -> float | None:
        if not self.n:
            return None
        p_value = self.push / self.n
        return 1.96 * math.sqrt(p_value * (1.0 - p_value) / self.n) * 100.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_states": self.total_states,
            "n": self.n,
            "missing_danger": self.total_states - self.n,
            "push_count_danger_gt_5pct": self.push,
            "push_rate_pct": self.rate_pct,
            "reader_metric": "actual discard exceeded 5% maximum NAGA danger; not a push/fold classifier",
            "ci95_half_width_pp": round2(self.ci95_half_width_pp),
        }


class GenbutsuStats:
    def __init__(self) -> None:
        self.n = 0
        self.genbutsu = 0

    def add(self, is_genbutsu: bool) -> None:
        self.n += 1
        if is_genbutsu:
            self.genbutsu += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "genbutsu_count": self.genbutsu,
            "genbutsu_rate_pct": pct(self.genbutsu, self.n),
        }


class DangerDistribution:
    def __init__(self) -> None:
        self.total_states = 0
        self.values: list[float] = []

    def add(self, danger: float | None) -> None:
        self.total_states += 1
        if danger is not None:
            self.values.append(float(danger))

    def to_dict(self) -> dict[str, Any]:
        values = self.values
        return {
            "total_states": self.total_states,
            "n": len(values),
            "missing_danger": self.total_states - len(values),
            "mean": round4(statistics.mean(values)) if values else None,
            "std": round4(statistics.pstdev(values)) if values else None,
            "p50": round4(percentile(values, 0.50)),
            "p75": round4(percentile(values, 0.75)),
            "p90": round4(percentile(values, 0.90)),
        }


# ----------------------------- first-pass helpers -----------------------------


def tile_base(tile: str | None) -> str:
    return str(tile or "").replace("r", "")


def tile_index(tile: str | int | None) -> int | None:
    if tile in (None, "?"):
        return None
    try:
        if isinstance(tile, int):
            if 0 <= tile < 34:
                return tile
            if 0 <= tile < 136:
                return tile // 4
            return None
        return base.tile_index(str(tile))
    except Exception:
        return None


def remove_tile(hand: list[str], tile: str | None) -> bool:
    if not tile or tile == "?":
        return False
    if tile in hand:
        hand.remove(tile)
        return True
    idx = tile_index(tile)
    if idx is None:
        return False
    for item in list(hand):
        if tile_index(item) == idx:
            hand.remove(item)
            return True
    return False


def discard_danger(state: dict[str, Any], seat: int, tile: str | None) -> float | None:
    idx = tile_index(tile)
    if idx is None or seat is None:
        return None
    values: list[float] = []
    for suffix in DANGER_SUFFIXES:
        danger = state.get(f"danger_{suffix}") or []
        if isinstance(danger, list) and 0 <= seat < len(danger):
            seat_values = danger[seat] or []
            if isinstance(seat_values, list) and idx < len(seat_values):
                try:
                    values.append(float(seat_values[idx]) / 10000.0)
                except (TypeError, ValueError):
                    pass
    return max(values) if values else None


def tenpai_estimate(state: dict[str, Any], seat: int) -> float | None:
    values: list[float] = []
    for suffix in TENPAI_SUFFIXES:
        tenpai = state.get(f"tenpai_{suffix}") or []
        if isinstance(tenpai, list) and 0 <= seat < len(tenpai):
            try:
                values.append(float(tenpai[seat]) / 100.0)
            except (TypeError, ValueError):
                pass
    return statistics.mean(values) if values else None


def turn_bucket(turn: int | None) -> str:
    if turn is None:
        return "unknown"
    if turn <= 6:
        return "1-6"
    if turn <= 12:
        return "7-12"
    return "13+"


def left_bucket(left: Any) -> str:
    try:
        left_int = int(left)
    except (TypeError, ValueError):
        return "unknown"
    if left_int > 40:
        return ">40"
    if left_int >= 21:
        return "40-21"
    return "<=20"


def closed_shanten_bucket_from_value(shanten: int | None) -> str:
    if shanten is None:
        return "unknown"
    if shanten <= 0:
        return "0"
    if shanten == 1:
        return "1"
    if shanten == 2:
        return "2"
    return "3+"


def compute_shanten_from_concealed(hand: list[str]) -> int | None:
    """Shanten on the current concealed tile count; open melds are implied by tile count."""
    try:
        # Open hands cannot be chiitoi/kokushi, and the library only considers those for >=13 tiles.
        return int(SHANTEN.calculate_shanten(counts_34(hand)))
    except Exception:
        return None


def compute_closed_shanten_if_closed(hand: list[str], open_melds: list[int], target: int) -> int | None:
    if target >= len(open_melds) or open_melds[target] > 0:
        return None
    return compute_shanten_from_concealed(hand)


def own_shanten_leq1_bucket(hand: list[str]) -> str:
    shanten = compute_shanten_from_concealed(hand)
    if shanten is None:
        return "unknown"
    return "<=1" if shanten <= 1 else "2+"


def choose_by_priority(
    seats: list[int],
    target: int,
    open_melds: list[int],
    reached: list[bool],
    tenpais: dict[int, float | None],
    prefer_riichi: bool,
) -> int | None:
    if not seats:
        return None

    def key(seat: int) -> tuple[int, int, float, int]:
        riichi_score = 1 if prefer_riichi and seat < len(reached) and reached[seat] else 0
        meld_score = min(open_melds[seat], 3) if seat < len(open_melds) else 0
        tenpai_score = tenpais.get(seat)
        # Deterministic seat order relative to LuckyJ, preferring shimocha on exact ties.
        rel_order = -((seat - target) % 4)
        return (riichi_score, meld_score, tenpai_score if tenpai_score is not None else -1.0, rel_order)

    return max(seats, key=key)


def classify_table_threat(
    target: int,
    open_melds: list[int],
    reached: list[bool],
    discards: list[list[str]],
    state: dict[str, Any],
) -> dict[str, Any]:
    opponents = [seat for seat in range(4) if seat != target]
    riichi_seats = [seat for seat in opponents if seat < len(reached) and reached[seat]]
    max_open = max((open_melds[seat] for seat in opponents if seat < len(open_melds)), default=0)
    has_open_2plus = any(seat < len(open_melds) and open_melds[seat] >= 2 for seat in opponents)

    if not riichi_seats:
        if max_open >= 3:
            category = "3plus_meld_opponent"
        elif max_open == 2:
            category = "2_meld_opponent"
        elif max_open == 1:
            category = "1_meld_opponent_max"
        else:
            category = "quiet"
    elif len(riichi_seats) >= 2 or has_open_2plus:
        category = "riichi_plus_more"
    else:
        category = "single_riichi"

    tenpais = {seat: tenpai_estimate(state, seat) for seat in opponents}
    if riichi_seats:
        candidates = riichi_seats
        max_seat = choose_by_priority(candidates, target, open_melds, reached, tenpais, prefer_riichi=True)
    elif max_open > 0:
        candidates = [seat for seat in opponents if seat < len(open_melds) and open_melds[seat] == max_open]
        max_seat = choose_by_priority(candidates, target, open_melds, reached, tenpais, prefer_riichi=False)
    else:
        max_seat = choose_by_priority(opponents, target, open_melds, reached, tenpais, prefer_riichi=False)

    max_melds = open_melds[max_seat] if max_seat is not None and max_seat < len(open_melds) else None
    max_turn = len(discards[max_seat]) + 1 if max_seat is not None and max_seat < len(discards) else None
    return {
        "category": category,
        "riichi_count": len(riichi_seats),
        "riichi_seats": riichi_seats,
        "max_opponent_seat": max_seat,
        "max_opponent_melds": max_melds,
        "max_opponent_turn": max_turn,
        "max_opponent_turn_bucket": turn_bucket(max_turn),
    }


# ----------------------------- dora/seat helpers -----------------------------


def marker_to_dora(marker: str | int | None) -> str | None:
    if marker in (None, "?"):
        return None
    if isinstance(marker, int):
        idx = tile_index(marker)
        marker = base.TILES[idx] if idx is not None else None
    marker = tile_base(str(marker)) if marker is not None else ""
    if marker in {"E", "S", "W", "N"}:
        return {"E": "S", "S": "W", "W": "N", "N": "E"}[marker]
    if marker in {"P", "F", "C"}:
        return {"P": "F", "F": "C", "C": "P"}[marker]
    match = re.match(r"^([1-9])([mps])$", marker)
    if not match:
        return None
    rank = int(match.group(1))
    suit = match.group(2)
    return f"{1 if rank == 9 else rank + 1}{suit}"


def append_dora_marker(markers: list[str], marker: str | int | None) -> None:
    if marker in (None, "?"):
        return
    if isinstance(marker, int):
        idx = tile_index(marker)
        if idx is None:
            return
        markers.append(base.TILES[idx])
    else:
        base_tile = tile_base(str(marker))
        if base_tile:
            markers.append(base_tile)


def dora_tile_counter(dora_markers: Iterable[str]) -> Counter[int]:
    counter: Counter[int] = Counter()
    for marker in dora_markers:
        dora = marker_to_dora(marker)
        idx = tile_index(dora)
        if idx is not None:
            counter[idx] += 1
    return counter


def tile_dora_value(tile: str | None, dora_tiles: Counter[int]) -> int:
    idx = tile_index(tile)
    if idx is None:
        return 0
    value = dora_tiles[idx]
    if isinstance(tile, str) and "r" in tile:
        value += 1
    return value


def hand_dora_count(hand: list[str], dora_markers: list[str]) -> int:
    dora_tiles = dora_tile_counter(dora_markers)
    return sum(tile_dora_value(tile, dora_tiles) for tile in hand)


def dora_count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    return "3+"


def dora_binary_bucket(count: int) -> str:
    return "2+" if count >= 2 else "0-1"


def seat_wind(start: dict[str, Any], seat: int) -> str | None:
    try:
        oya = int(start.get("oya"))
    except (TypeError, ValueError):
        return None
    if not (0 <= seat < 4 and 0 <= oya < 4):
        return None
    return WINDS[(seat - oya) % 4]


def is_round_wind_or_dragon(tile: str | None, start: dict[str, Any]) -> bool:
    base_tile = tile_base(tile)
    return base_tile in DRAGONS or bool(base_tile and base_tile == start.get("bakaze"))


def start_rank_bucket(start: dict[str, Any], target: int) -> str:
    ranks = start.get("seat2rank") or []
    try:
        rank = int(ranks[target]) + 1
    except (TypeError, ValueError, IndexError):
        return "unknown"
    if rank in {1, 2}:
        return "1-2"
    if rank in {3, 4}:
        return "3-4"
    return "unknown"


def yes_no(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "unknown"


def dealer_bucket(start: dict[str, Any], seat: int | None) -> str:
    if seat is None:
        return "unknown"
    return yes_no(start.get("oya") == seat)


def own_dealer_bucket(start: dict[str, Any], target: int) -> str:
    return dealer_bucket(start, target)


def genbutsu_count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    return "2+"


def count_safe_tiles_in_hand(hand: list[str], safe_tile_indices: set[int]) -> int:
    return sum(1 for tile in hand if tile_index(tile) in safe_tile_indices)


def meld_has_triplet_or_quad_of_tile_class(meld_tiles: list[str], predicate) -> bool:
    by_idx: dict[int, list[str]] = defaultdict(list)
    for tile in meld_tiles:
        idx = tile_index(tile)
        if idx is not None:
            by_idx[idx].append(tile)
    for idx, tiles in by_idx.items():
        if len(tiles) >= 3 and predicate(base.TILES[idx], tiles):
            return True
    return False


def opponent_has_value_or_dora_pon(
    melds_for_seat: list[list[str]],
    start: dict[str, Any],
    dora_markers: list[str],
) -> bool:
    dora_tiles = dora_tile_counter(dora_markers)

    def predicate(base_tile: str, physical_tiles: list[str]) -> bool:
        if is_round_wind_or_dragon(base_tile, start):
            return True
        idx = tile_index(base_tile)
        if idx is not None and dora_tiles[idx] > 0:
            return True
        return any(isinstance(tile, str) and "r" in tile for tile in physical_tiles)

    return any(meld_has_triplet_or_quad_of_tile_class(meld, predicate) for meld in melds_for_seat)


# ----------------------------- condition-effect finalization -----------------------------


def empty_bin_dict() -> dict[str, Any]:
    return BinStats().to_dict()


def make_effect(value_stats: BinStats, complement_stats: BinStats, min_cell_n: int = MIN_CELL_N) -> dict[str, Any]:
    value_rate = value_stats.rate_pct
    comp_rate = complement_stats.rate_pct
    delta = value_rate - comp_rate if value_rate is not None and comp_rate is not None else None
    value_ci = value_stats.ci95_half_width_pp
    comp_ci = complement_stats.ci95_half_width_pp
    combined_ci = None
    if value_ci is not None and comp_ci is not None:
        combined_ci = math.sqrt(value_ci * value_ci + comp_ci * comp_ci)
    min_met = value_stats.n >= min_cell_n and complement_stats.n >= min_cell_n
    significant = bool(min_met and delta is not None and combined_ci is not None and abs(delta) > combined_ci)
    return value_stats.to_dict() | {
        "complement_n": complement_stats.n,
        "complement_push_count_danger_gt_5pct": complement_stats.push,
        "complement_push_rate_pct": comp_rate,
        "delta_pp_vs_complement": round1(delta),
        "complement_ci95_half_width_pp": round2(comp_ci),
        "combined_ci95_half_width_pp": round2(combined_ci),
        "min_cell_n": min_cell_n,
        "min_cell_n_met": min_met,
        "significant": significant,
    }


def finalize_condition_effects(
    observations: list[dict[str, Any]],
    condition_specs: list[tuple[str, list[str]]],
) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for condition, values in condition_specs:
        by_value: dict[str, BinStats] = {value: BinStats() for value in values}
        total = BinStats()
        for obs in observations:
            danger = obs.get("danger")
            value = obs.get(condition, "unknown")
            total.add(danger)
            if value not in by_value:
                by_value[value] = BinStats()
            by_value[value].add(danger)
        effects = []
        for value, stat in by_value.items():
            complement = BinStats()
            complement.total_states = total.total_states - stat.total_states
            complement.n = total.n - stat.n
            complement.push = total.push - stat.push
            effect = make_effect(stat, complement)
            effect["condition"] = condition
            effect["value"] = value
            effects.append(effect)
        effects.sort(
            key=lambda item: (
                -abs(item["delta_pp_vs_complement"] if item["delta_pp_vs_complement"] is not None else -999.0),
                item["condition"],
                str(item["value"]),
            )
        )
        output[condition] = {
            "n_observations": total.n,
            "total_states": total.total_states,
            "overall": total.to_dict(),
            "values_sorted_by_abs_delta_pp": effects,
        }
    return output


def flatten_significant_effects(condition_effects: dict[str, Any], shanten: str | None = None, scope: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition, payload in condition_effects.items():
        for effect in payload.get("values_sorted_by_abs_delta_pp", []):
            if not effect.get("significant"):
                continue
            row = dict(effect)
            row["condition"] = condition
            if shanten is not None:
                row["shanten"] = shanten
            if scope is not None:
                row["scope"] = scope
            rows.append(row)
    rows.sort(key=lambda item: abs(item.get("delta_pp_vs_complement") or 0), reverse=True)
    return rows


# ----------------------------- proposed modifiers -----------------------------


def fmt_signed(delta: float | None) -> str:
    if delta is None:
        return "+0.0pp"
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f}pp"


def find_effect(condition_effects: dict[str, Any], condition: str, value: str) -> dict[str, Any] | None:
    payload = condition_effects.get(condition) or {}
    for effect in payload.get("values_sorted_by_abs_delta_pp", []):
        if effect.get("value") == value:
            return effect
    return None


def top_effect(significant: list[dict[str, Any]], positive: bool, used_keys: set[tuple[str, str, str]]) -> dict[str, Any] | None:
    candidates = [row for row in significant if (row.get("delta_pp_vs_complement") or 0) > 0] if positive else [row for row in significant if (row.get("delta_pp_vs_complement") or 0) < 0]
    for row in candidates:
        key = (str(row.get("scope", "vs_riichi")), str(row.get("condition")), str(row.get("value")))
        if key not in used_keys:
            used_keys.add(key)
            return row
    return None


def human_condition_phrase(row: dict[str, Any]) -> str:
    condition = row.get("condition")
    value = row.get("value")
    shanten = row.get("shanten")
    prefix = "tenpai" if shanten == "0" else "1-shanten" if shanten == "1" else "open-hand"
    mapping = {
        "dora_count": f"{value} dora",
        "riichi_is_dealer": "riichi dealer" if value == "yes" else "nondealer riichi",
        "own_is_dealer": "LuckyJ dealer" if value == "yes" else "LuckyJ nondealer",
        "own_start_rank": "starting rank 1-2" if value == "1-2" else "starting rank 3-4",
        "tiles_left": f"{value} tiles left",
        "genbutsu_count": f"{value} genbutsu in hand",
        "second_threat_present": "second threat present" if value == "yes" else "single riichi only",
        "opponent_is_dealer": "dealer open hand" if value == "yes" else "nondealer open hand",
        "opponent_has_yakuhai_or_dora_pon": "yakuhai/dora pon visible" if value == "yes" else "no yakuhai/dora pon visible",
        "own_shanten_bucket": "own hand ≤1-shanten" if value == "<=1" else "own hand 2+ shanten",
        "own_rank": "starting rank 1-2" if value == "1-2" else "starting rank 3-4",
    }
    return f"{prefix}, {mapping.get(str(condition), f'{condition}={value}')}"


def make_proposed_modifiers(final: dict[str, Any]) -> list[str]:
    rules: list[str] = []
    used: set[tuple[str, str, str]] = set()
    vs = final["condition_effects_vs_riichi"]
    sig_vs = final["significant_effects"].get("vs_riichi", [])
    sig_open = final["significant_effects"].get("open_hand_turn7plus", [])

    tenpai_overall = vs["0"]["overall"]
    tenpai_base = tenpai_overall.get("push_rate_pct")
    tenpai_dora2 = find_effect(vs["0"]["conditions"], "dora_count", "2")
    tenpai_dora3 = find_effect(vs["0"]["conditions"], "dora_count", "3+")
    tenpai_dora_big = None
    if tenpai_dora2 and tenpai_dora3:
        tenpai_dora_big = tenpai_dora2 if abs(tenpai_dora2.get("delta_pp_vs_complement") or 0) >= abs(tenpai_dora3.get("delta_pp_vs_complement") or 0) else tenpai_dora3
    else:
        tenpai_dora_big = tenpai_dora2 or tenpai_dora3
    if tenpai_dora_big and tenpai_dora_big.get("significant"):
        used.add(("vs_riichi", "dora_count", str(tenpai_dora_big.get("value"))))
        rules.append(
            f"Tenpai vs riichi baseline {tenpai_base:.1f}% push; {fmt_signed(tenpai_dora_big.get('delta_pp_vs_complement'))} with {tenpai_dora_big.get('value')} dora "
            f"({tenpai_dora_big.get('push_rate_pct')}%, n={tenpai_dora_big.get('n')})."
        )

    tenpai_riichi_dealer = find_effect(vs["0"]["conditions"], "riichi_is_dealer", "yes")
    if tenpai_riichi_dealer and tenpai_riichi_dealer.get("significant"):
        used.add(("vs_riichi", "riichi_is_dealer", "yes"))
        rules.append(
            f"Tenpai pushes drop when the riichi is dealer: {fmt_signed(tenpai_riichi_dealer.get('delta_pp_vs_complement'))} "
            f"({tenpai_riichi_dealer.get('push_rate_pct')}%, n={tenpai_riichi_dealer.get('n')})."
        )

    one_gen0 = find_effect(vs["1"]["conditions"], "genbutsu_count", "0")
    if one_gen0:
        used.add(("vs_riichi", "genbutsu_count", "0"))
        rules.append(
            f"At 1-shanten with zero genbutsu, the 'push' rate is {one_gen0.get('push_rate_pct')}% (n={one_gen0.get('n')}); this forced-push cell is {fmt_signed(one_gen0.get('delta_pp_vs_complement'))} vs hands with at least one safe tile."
        )

    for positive in (True, False, True, False):
        row = top_effect(sig_vs, positive=positive, used_keys=used)
        if row:
            rules.append(
                f"Vs riichi: {human_condition_phrase(row)} shifts push {fmt_signed(row.get('delta_pp_vs_complement'))} "
                f"to {row.get('push_rate_pct')}% (n={row.get('n')})."
            )

    open_used = set(used)
    for positive in (True, False):
        row = top_effect(sig_open, positive=positive, used_keys=open_used)
        if row:
            rules.append(
                f"Vs 2+ meld open hands on turn 7+: {human_condition_phrase(row)} shifts push {fmt_signed(row.get('delta_pp_vs_complement'))} "
                f"to {row.get('push_rate_pct')}% (n={row.get('n')})."
            )

    # If the named dora/dealer examples were not significant, still fill 5-8 one-liners with significant effects.
    all_sig = sig_vs + sig_open
    for row in all_sig:
        if len(rules) >= 8:
            break
        key = (str(row.get("scope", "vs_riichi")), str(row.get("condition")), str(row.get("value")))
        if key in used:
            continue
        used.add(key)
        scope = "Vs riichi" if row.get("scope") == "vs_riichi" else "Vs 2+ meld open hands on turn 7+"
        rules.append(
            f"{scope}: {human_condition_phrase(row)} shifts push {fmt_signed(row.get('delta_pp_vs_complement'))} "
            f"to {row.get('push_rate_pct')}% (n={row.get('n')})."
        )

    return rules[:8]


# ----------------------------- main mining loop -----------------------------


def main() -> None:
    raw_rows = base.parse_rows()
    rows = []
    seen_report_ids: set[str] = set()
    duplicate_report_rows = []
    for row in raw_rows:
        report_id = row.get("report_id")
        if report_id in seen_report_ids:
            duplicate_report_rows.append({
                "idx": row.get("idx"),
                "report_id": report_id,
                "actor": row.get("actor"),
                "paifu": row.get("paifu"),
            })
            continue
        seen_report_ids.add(report_id)
        rows.append(row)

    vs_riichi_by_shanten: dict[str, BinStats] = defaultdict(BinStats)
    immediate_by_shanten: dict[str, GenbutsuStats] = defaultdict(GenbutsuStats)
    vs_condition_observations: dict[str, list[dict[str, Any]]] = {"0": [], "1": []}
    two_way: dict[str, dict[str, dict[str, BinStats]]] = {
        sh: {dora: {dealer: BinStats() for dealer in YES_NO_ORDER} for dora in DORA_BINARY_ORDER}
        for sh in ["0", "1"]
    }
    open_condition_observations: list[dict[str, Any]] = []
    single_riichi_distribution: dict[str, DangerDistribution] = defaultdict(DangerDistribution)
    game_push_counts: dict[str, dict[str, Any]] = {}

    summary = {
        "n_rows_from_sheet": len(raw_rows),
        "n_unique_report_ids": len(rows),
        "n_duplicate_report_rows_skipped": len(duplicate_report_rows),
        "duplicate_report_rows_skipped": duplicate_report_rows[:20],
        "n_reports_processed": 0,
        "n_reports_failed": 0,
        "n_kyoku_seen": 0,
        "n_luckyj_tsumo_decision_states": 0,
        "n_vs_riichi_closed_shanten_decisions": 0,
        "n_vs_riichi_condition_observations": 0,
        "n_single_riichi_distribution_observations": 0,
        "n_open_hand_turn7plus_observations": 0,
        "n_immediate_riichi_reactions": 0,
        "errors": [],
    }

    for row_index, row in enumerate(rows, 1):
        if row_index % 200 == 0:
            print(f"processed {row_index}/{len(rows)} reports", flush=True)
        target = row.get("actor")
        if target is None or not (0 <= target < 4):
            continue
        game_key = str(row.get("report_id") or row.get("idx"))
        game_counter = game_push_counts.setdefault(
            game_key,
            {
                "idx": row.get("idx"),
                "report_id": row.get("report_id"),
                "n": 0,
                "push_count_danger_gt_5pct": 0,
            },
        )
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
            summary["n_reports_processed"] += 1
        except Exception as exc:
            summary["n_reports_failed"] += 1
            if len(summary["errors"]) < 20:
                summary["errors"].append({"report_id": row.get("report_id"), "error": repr(exc)})
            continue

        for kyoku_index, kyoku in enumerate(data.get("pred") or []):
            summary["n_kyoku_seen"] += 1
            try:
                start = (kyoku[0].get("info", {}).get("msg", {}) if kyoku else {}) or {}
                start_hands = start.get("tehais") or [[], [], [], []]
                hands = [list(start_hands[i]) if i < len(start_hands) else [] for i in range(4)]
                discards: list[list[str]] = [[], [], [], []]
                open_melds = [0, 0, 0, 0]
                melds: list[list[list[str]]] = [[], [], [], []]
                reached = [False, False, False, False]
                safe_tiles_vs_riichi: list[set[int]] = [set(), set(), set(), set()]
                pending_riichi_discard = [False, False, False, False]
                pending_reaction: dict[int, dict[str, Any]] = {}
                dora_markers: list[str] = []
                append_dora_marker(dora_markers, start.get("dora_marker"))

                rank_bucket = start_rank_bucket(start, target)
                own_dealer = own_dealer_bucket(start, target)

                for pos, state in enumerate(kyoku):
                    msg = state.get("info", {}).get("msg", {}) or {}
                    actor = msg.get("actor")
                    msg_type = msg.get("type")

                    if msg_type == "dora":
                        append_dora_marker(dora_markers, msg.get("dora_marker"))
                        continue

                    if msg_type == "tsumo":
                        if actor is not None and 0 <= actor < 4:
                            pai = msg.get("pai")
                            if pai:
                                hands[actor].append(pai)

                        actual = msg.get("real_dahai")
                        is_luckyj_decision = (
                            actor == target
                            and actual not in (None, "?")
                            and "dahai_pred" in state
                        )

                        if is_luckyj_decision:
                            summary["n_luckyj_tsumo_decision_states"] += 1
                            own_reached = bool(msg.get("reached") or (target < len(reached) and reached[target]))
                            closed_shanten_value = compute_closed_shanten_if_closed(hands[target], open_melds, target) if not own_reached else None
                            closed_shanten = closed_shanten_bucket_from_value(closed_shanten_value) if closed_shanten_value is not None else None
                            actual_danger = discard_danger(state, target, actual)
                            threat = classify_table_threat(target, open_melds, reached, discards, state)
                            threat_cat = threat["category"]
                            lb = left_bucket(msg.get("left_hai_num"))

                            if threat_cat in {"single_riichi", "riichi_plus_more"}:
                                if actual_danger is not None:
                                    game_counter["n"] += 1
                                    if actual_danger > 0.05:
                                        game_counter["push_count_danger_gt_5pct"] += 1

                                if closed_shanten is not None:
                                    summary["n_vs_riichi_closed_shanten_decisions"] += 1
                                    vs_riichi_by_shanten[closed_shanten].add(actual_danger)

                                if threat_cat == "single_riichi" and closed_shanten is not None:
                                    summary["n_single_riichi_distribution_observations"] += 1
                                    single_riichi_distribution[closed_shanten].add(actual_danger)

                                if closed_shanten in {"0", "1"}:
                                    riichi_seat = threat.get("max_opponent_seat")
                                    riichi_dealer = dealer_bucket(start, riichi_seat)
                                    safe_set = safe_tiles_vs_riichi[riichi_seat] if isinstance(riichi_seat, int) and 0 <= riichi_seat < 4 else set()
                                    genbutsu_count = count_safe_tiles_in_hand(hands[target], safe_set)
                                    dora_count = hand_dora_count(hands[target], dora_markers)
                                    obs = {
                                        "danger": actual_danger,
                                        "dora_count": dora_count_bucket(dora_count),
                                        "riichi_is_dealer": riichi_dealer,
                                        "own_is_dealer": own_dealer,
                                        "own_start_rank": rank_bucket,
                                        "tiles_left": lb,
                                        "genbutsu_count": genbutsu_count_bucket(genbutsu_count),
                                        "second_threat_present": yes_no(threat_cat == "riichi_plus_more"),
                                    }
                                    vs_condition_observations[closed_shanten].append(obs)
                                    summary["n_vs_riichi_condition_observations"] += 1
                                    dora_bin = dora_binary_bucket(dora_count)
                                    if riichi_dealer in YES_NO_ORDER:
                                        two_way[closed_shanten][dora_bin][riichi_dealer].add(actual_danger)

                            if threat_cat in {"2_meld_opponent", "3plus_meld_opponent"}:
                                opponent = threat.get("max_opponent_seat")
                                opponent_turn = threat.get("max_opponent_turn")
                                if isinstance(opponent, int) and opponent_turn is not None and opponent_turn >= 7:
                                    open_condition_observations.append({
                                        "danger": actual_danger,
                                        "opponent_is_dealer": dealer_bucket(start, opponent),
                                        "opponent_has_yakuhai_or_dora_pon": yes_no(opponent_has_value_or_dora_pon(melds[opponent], start, dora_markers)),
                                        "own_shanten_bucket": own_shanten_leq1_bucket(hands[target]),
                                        "own_rank": rank_bucket,
                                    })
                                    summary["n_open_hand_turn7plus_observations"] += 1

                            if pending_reaction:
                                # Same first-discard-after-riichi logic as the first pass.
                                actual_idx = tile_index(actual)
                                for riichi_seat in sorted(list(pending_reaction)):
                                    if riichi_seat == target:
                                        continue
                                    safe_tiles = pending_reaction[riichi_seat].get("safe_tile_indices", set())
                                    genbutsu = actual_idx is not None and actual_idx in safe_tiles
                                    reaction_shanten = closed_shanten if closed_shanten is not None else "unknown"
                                    immediate_by_shanten[reaction_shanten].add(genbutsu)
                                    summary["n_immediate_riichi_reactions"] += 1
                                    pending_reaction.pop(riichi_seat, None)

                        if actor is not None and 0 <= actor < 4:
                            discard = msg.get("real_dahai")
                            if discard and discard != "?":
                                remove_tile(hands[actor], discard)

                    elif msg_type in HURO_TYPES:
                        if actor is not None and 0 <= actor < 4:
                            open_melds[actor] += 1
                            consumed = list(msg.get("consumed") or [])
                            called = msg.get("pai")
                            meld_tiles = consumed + ([called] if called else [])
                            melds[actor].append(meld_tiles)
                            for tile in consumed:
                                remove_tile(hands[actor], tile)
                            discard = msg.get("real_dahai")
                            if discard and discard != "?":
                                remove_tile(hands[actor], discard)

                    elif msg_type == "ankan":
                        if actor is not None and 0 <= actor < 4:
                            open_melds[actor] += 1
                            consumed = list(msg.get("consumed") or [])
                            melds[actor].append(consumed)
                            for tile in consumed:
                                remove_tile(hands[actor], tile)

                    elif msg_type == "kakan":
                        if actor is not None and 0 <= actor < 4:
                            pai = msg.get("pai")
                            remove_tile(hands[actor], pai)
                            # Attach the added tile to the first matching pon if possible; otherwise keep a tiny meld record.
                            pai_idx = tile_index(pai)
                            attached = False
                            if pai_idx is not None:
                                for meld in melds[actor]:
                                    if sum(1 for tile in meld if tile_index(tile) == pai_idx) >= 3:
                                        meld.append(pai)
                                        attached = True
                                        break
                            if not attached and pai:
                                melds[actor].append([pai])

                    elif msg_type == "reach":
                        if actor is not None and 0 <= actor < 4:
                            reached[actor] = True
                            pending_riichi_discard[actor] = True
                            existing_safe = {idx for idx in (tile_index(tile) for tile in discards[actor]) if idx is not None}
                            safe_tiles_vs_riichi[actor] = set(existing_safe)
                            if actor != target:
                                pending_reaction[actor] = {
                                    "kyoku_index": kyoku_index,
                                    "pos": pos,
                                    "riichi_seat": actor,
                                    "safe_tile_indices": set(existing_safe),
                                }

                    elif msg_type == "dahai":
                        tile = msg.get("pai")
                        if actor is not None and 0 <= actor < 4 and tile:
                            idx = tile_index(tile)
                            discards[actor].append(tile)
                            if idx is not None:
                                # Genbutsu against a riichi player means that riichi player's own river,
                                # including the declaration discard and any later discards by that player.
                                if reached[actor]:
                                    safe_tiles_vs_riichi[actor].add(idx)
                                for reaction in pending_reaction.values():
                                    if reaction.get("riichi_seat") == actor:
                                        reaction.setdefault("safe_tile_indices", set()).add(idx)
                            if pending_riichi_discard[actor]:
                                pending_riichi_discard[actor] = False

            except Exception as exc:
                if len(summary["errors"]) < 20:
                    summary["errors"].append({"report_id": row.get("report_id"), "kyoku_index": kyoku_index, "error": repr(exc)})
                continue

    vs_condition_specs = [
        ("dora_count", DORA_COUNT_ORDER),
        ("riichi_is_dealer", YES_NO_ORDER),
        ("own_is_dealer", YES_NO_ORDER),
        ("own_start_rank", RANK_BUCKET_ORDER),
        ("tiles_left", LEFT_BUCKET_ORDER),
        ("genbutsu_count", GENBUTSU_COUNT_ORDER),
        ("second_threat_present", YES_NO_ORDER),
    ]
    open_condition_specs = [
        ("opponent_is_dealer", YES_NO_ORDER),
        ("opponent_has_yakuhai_or_dora_pon", YES_NO_ORDER),
        ("own_shanten_bucket", OPEN_OWN_SHANTEN_ORDER),
        ("own_rank", RANK_BUCKET_ORDER),
    ]

    condition_effects_vs_riichi: dict[str, Any] = {}
    sig_vs: list[dict[str, Any]] = []
    for sh in ["0", "1"]:
        conditions = finalize_condition_effects(vs_condition_observations[sh], vs_condition_specs)
        overall = BinStats()
        for obs in vs_condition_observations[sh]:
            overall.add(obs.get("danger"))
        condition_effects_vs_riichi[sh] = {
            "scope": f"closed shanten {sh} decisions while facing at least one riichi",
            "overall": overall.to_dict(),
            "conditions": conditions,
        }
        sig_vs.extend(flatten_significant_effects(conditions, shanten=sh, scope="vs_riichi"))

    open_conditions = finalize_condition_effects(open_condition_observations, open_condition_specs)
    open_overall = BinStats()
    for obs in open_condition_observations:
        open_overall.add(obs.get("danger"))
    sig_open = flatten_significant_effects(open_conditions, scope="open_hand_turn7plus")

    final_two_way = {
        sh: {
            dora: {
                dealer: two_way[sh][dora][dealer].to_dict()
                for dealer in YES_NO_ORDER
            }
            for dora in DORA_BINARY_ORDER
        }
        for sh in ["0", "1"]
    }

    final_vs_baseline = {sh: vs_riichi_by_shanten[sh].to_dict() for sh in SHANTEN_ORDER[:-1]}
    final_immediate = {sh: immediate_by_shanten[sh].to_dict() for sh in SHANTEN_ORDER[:-1]}

    distribution = {sh: single_riichi_distribution[sh].to_dict() for sh in SHANTEN_ORDER[:-1]}

    eligible_games = []
    for game in game_push_counts.values():
        n = game["n"]
        if n >= 5:
            rate = 100.0 * game["push_count_danger_gt_5pct"] / n
            eligible_games.append(game | {"push_rate_pct": round1(rate)})
    total_game_decisions = sum(game["n"] for game in eligible_games)
    weighted_mean = None
    weighted_std = None
    if total_game_decisions:
        weighted_mean = sum(game["push_rate_pct"] * game["n"] for game in eligible_games) / total_game_decisions
        weighted_std = math.sqrt(sum(game["n"] * (game["push_rate_pct"] - weighted_mean) ** 2 for game in eligible_games) / total_game_decisions)
    eligible_rates = [game["push_rate_pct"] for game in eligible_games]
    per_game_consistency = {
        "scope": "games with at least 5 vs-riichi decisions with usable danger; vs-riichi includes single_riichi and riichi_plus_more",
        "n_games": len(eligible_games),
        "n_decisions": total_game_decisions,
        "weighted_mean_push_rate_pct": round1(weighted_mean),
        "weighted_std_push_rate_pct": round1(weighted_std),
        "unweighted_mean_push_rate_pct": round1(statistics.mean(eligible_rates)) if eligible_rates else None,
        "unweighted_std_push_rate_pct": round1(statistics.pstdev(eligible_rates)) if eligible_rates else None,
        "games": sorted(eligible_games, key=lambda item: (item["idx"] if item.get("idx") is not None else 10**9)),
    }

    output: dict[str, Any] = {
        "definitions": {
            "danger": "For LuckyJ's actual discard, max(state[danger_s/t/k][LuckyJ seat][tile_index] / 10000), matching scripts/mine_rx_defense.py.",
            "push": "actual discard danger > 0.05.",
            "condition_effect_delta": "For a condition value within the requested stratum: push_rate(value) - push_rate(all other values of that condition).",
            "ci95_half_width_pp": "1.96 * sqrt(p*(1-p)/n) * 100. significant=true only when value and complement both have n>=150 and |delta_pp| > sqrt(ci_value^2 + ci_complement^2).",
            "vs_riichi_scope": "LuckyJ tsumo decision states with a real actual discard and dahai_pred, classified as single_riichi or riichi_plus_more by the first-pass threat classifier.",
            "closed_shanten": "Only no own melds and not own riichi; shanten is mahjong.shanten over LuckyJ's current 14-tile hand. Buckets are 0/1/2/3+.",
            "dora_count_in_hand": "Counts every indicator-derived dora in LuckyJ's current hand plus red fives; a red five that is also indicator dora counts twice. Dora indicators wrap 9->1, E->S->W->N->E, P->F->C->P.",
            "riichi_is_dealer": "Uses the primary riichi seat selected by the first-pass priority rule; single_riichi has exactly one riichi, riichi_plus_more may have multiple.",
            "genbutsu_count": "Physical tiles in LuckyJ's current hand whose 34-tile index appears in the primary riichi player's own river, including the declaration discard and any later discards by that riichi player. This matches the supplied first-pass genbutsu baseline.",
            "second_threat_present": "yes when first-pass category is riichi_plus_more: another riichi, or at least one riichi plus any opponent with 2+ melds.",
            "open_hand_turn7plus_scope": "No-riichi states classified as 2_meld_opponent or 3plus_meld_opponent, using the selected max-open opponent, with that opponent's turn >= 7.",
            "open_value_or_dora_pon": "Selected open opponent has any visible triplet/quad meld containing dragons, round wind, indicator-derived dora, or a red five.",
            "open_own_shanten_bucket": "Shanten over LuckyJ's current concealed tile count; open melds are implied by tile count in the mahjong.shanten library. Buckets are <=1 vs 2+.",
            "tiles_left_buckets": {">40": "left_hai_num > 40", "40-21": "21 <= left_hai_num <= 40", "<=20": "left_hai_num <= 20"},
            "immediate_riichi_reaction": "For each opponent riichi declaration, LuckyJ's next tsumo discard is genbutsu if its tile index appears in that riichi player's own river, including the declaration discard. This reproduces the supplied first-pass baseline." ,
            "n_fields": "total_states counts matching decisions; n counts decisions with usable danger unless the metric is genbutsu, where n counts reaction observations.",
        },
        "summary": summary,
        "reproduced_baselines": {
            "vs_riichi_push_by_closed_shanten": final_vs_baseline,
            "first_discard_after_riichi_genbutsu_by_closed_shanten": final_immediate,
            "expected_from_pass1_pct": {
                "vs_riichi_push_by_closed_shanten": {"0": 61.3, "1": 33.6, "2": 20.3, "3+": 14.2},
                "first_discard_after_riichi_genbutsu_by_closed_shanten": {"0": 32.6, "1": 55.5, "2": 64.3, "3+": 68.1},
            },
        },
        "condition_effects_vs_riichi": condition_effects_vs_riichi,
        "two_way_shanten_dora_riichi_dealer": final_two_way,
        "condition_effects_open_hand_turn7plus": {
            "scope": "2+ meld opponent, no riichi, selected opponent turn >= 7",
            "overall": open_overall.to_dict(),
            "conditions": open_conditions,
        },
        "dispersion": {
            "single_riichi_actual_discard_danger_by_closed_shanten": distribution,
            "per_game_consistency": per_game_consistency,
        },
        "significant_effects": {
            "vs_riichi": sig_vs,
            "open_hand_turn7plus": sig_open,
        },
    }
    output["proposed_modifiers"] = make_proposed_modifiers(output)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)
    print(json.dumps({
        "summary": output["summary"],
        "reproduced_baselines": output["reproduced_baselines"],
        "top_vs_riichi_effects": output["significant_effects"]["vs_riichi"][:10],
        "top_open_effects": output["significant_effects"]["open_hand_turn7plus"][:10],
        "proposed_modifiers": output["proposed_modifiers"],
        "dispersion_headline": output["dispersion"]["single_riichi_actual_discard_danger_by_closed_shanten"],
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
