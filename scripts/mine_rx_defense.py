#!/usr/bin/env python3
"""Mine LuckyJ defense trigger thresholds from cached NAGA reports."""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from mahjong.shanten import Shanten

import analyze_luckyj as base
from extract_case_studies import counts_34

OUT = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx-defense.json")
SHANTEN = Shanten()

DANGER_SUFFIXES = ("s", "t", "k")
TENPAI_SUFFIXES = ("s", "t", "k")

THREAT_ORDER = [
    "quiet",
    "1_meld_opponent_max",
    "2_meld_opponent",
    "3plus_meld_opponent",
    "single_riichi",
    "riichi_plus_more",
]
THREAT_LABELS = {
    "quiet": "no riichi and no opponent with any melds",
    "1_meld_opponent_max": "no riichi; max opponent meld count is 1",
    "2_meld_opponent": "no riichi; max opponent meld count is 2",
    "3plus_meld_opponent": "no riichi; max opponent meld count is 3+",
    "single_riichi": "exactly one opponent riichi and no opponent with 2+ melds",
    "riichi_plus_more": "2+ opponent riichi, or at least one riichi plus an opponent with 2+ melds",
}
TENPAI_BUCKET_ORDER = ["<30%", "30-60%", ">60%", "unknown"]
DECILE_ORDER = [f"{i * 10}-{(i + 1) * 10}%" for i in range(10)] + ["unknown"]
OWN_STATE_ORDER = [
    "closed_tenpai",
    "closed_1_shanten",
    "closed_2plus_shanten",
    "own_open_hand",
    "own_riichi",
    "closed_unknown",
]
CLOSED_SHANTEN_ORDER = ["0", "1", "2", "3+", "unknown"]
LEFT_BUCKET_ORDER = [">40", "40-21", "<=20", "unknown"]
TURN_BUCKET_ORDER = ["1-6", "7-12", "13+", "unknown"]
MELD_COUNT_ORDER = ["2", "3+"]


def pct(value: int | float | None, den: int | float | None) -> float | None:
    if not den:
        return None
    return round(100.0 * float(value) / float(den), 1)


def round4(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    # Nearest-rank percentile: concrete and stable for small buckets.
    index = max(0, min(len(ordered) - 1, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


class DangerStats:
    def __init__(self) -> None:
        self.total_states = 0
        self.values: list[float] = []
        self.push_count = 0
        self.hard_push_count = 0

    def add(self, danger: float | None) -> None:
        self.total_states += 1
        if danger is None:
            return
        self.values.append(float(danger))
        if danger > 0.05:
            self.push_count += 1
        if danger > 0.10:
            self.hard_push_count += 1

    def to_dict(self) -> dict[str, Any]:
        n = len(self.values)
        return {
            "total_states": self.total_states,
            "n": n,
            "missing_danger": self.total_states - n,
            "mean_danger": round4(statistics.mean(self.values)) if self.values else None,
            "p75_danger": round4(percentile(self.values, 0.75)),
            "push_count_danger_gt_5pct": self.push_count,
            "push_rate_danger_gt_5pct": pct(self.push_count, n),
            "hard_push_count_danger_gt_10pct": self.hard_push_count,
            "hard_push_rate_danger_gt_10pct": pct(self.hard_push_count, n),
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
            "genbutsu_rate": pct(self.genbutsu, self.n),
        }


def get_nested_stat(root: dict[str, Any], *keys: str) -> DangerStats:
    node: dict[str, Any] = root
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    final = keys[-1]
    stat = node.get(final)
    if stat is None:
        stat = DangerStats()
        node[final] = stat
    return stat


def get_nested_bool_stat(root: dict[str, Any], *keys: str) -> GenbutsuStats:
    node: dict[str, Any] = root
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    final = keys[-1]
    stat = node.get(final)
    if stat is None:
        stat = GenbutsuStats()
        node[final] = stat
    return stat


def finalize_nested(obj: Any, key_order: list[str] | None = None) -> Any:
    if isinstance(obj, DangerStats) or isinstance(obj, GenbutsuStats):
        return obj.to_dict()
    if not isinstance(obj, dict):
        return obj
    keys = list(obj.keys())
    if key_order:
        order_index = {key: i for i, key in enumerate(key_order)}
        keys.sort(key=lambda key: (order_index.get(key, len(order_index)), str(key)))
    else:
        keys.sort(key=str)
    return {key: finalize_nested(obj[key]) for key in keys}


def tile_index(tile: str | None) -> int | None:
    if not tile:
        return None
    try:
        return base.tile_index(tile)
    except Exception:
        return None


def same_tile(a: str | None, b: str | None) -> bool:
    ai = tile_index(a)
    bi = tile_index(b)
    return ai is not None and ai == bi


def remove_tile(hand: list[str], tile: str | None) -> bool:
    if not tile:
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


def tenpai_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value < 0.30:
        return "<30%"
    if value <= 0.60:
        return "30-60%"
    return ">60%"


def tenpai_decile(value: float | None) -> str:
    if value is None:
        return "unknown"
    pct_value = max(0.0, min(99.999, value * 100.0))
    low = int(pct_value // 10) * 10
    return f"{low}-{low + 10}%"


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


def general_own_state(open_melds: list[int], target: int, own_reached: bool, shanten: int | None) -> str:
    if own_reached:
        return "own_riichi"
    if target < len(open_melds) and open_melds[target] > 0:
        return "own_open_hand"
    if shanten is None:
        return "closed_unknown"
    if shanten <= 0:
        return "closed_tenpai"
    if shanten == 1:
        return "closed_1_shanten"
    return "closed_2plus_shanten"


def compute_shanten_if_closed(hand: list[str], open_melds: list[int], target: int) -> int | None:
    if target >= len(open_melds) or open_melds[target] > 0:
        return None
    try:
        return int(SHANTEN.calculate_shanten(counts_34(hand)))
    except Exception:
        return None


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
        # Last element is deterministic seat order relative to LuckyJ, preferring shimocha on exact ties.
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

    max_tenpai = tenpais.get(max_seat) if max_seat is not None else None
    max_melds = open_melds[max_seat] if max_seat is not None and max_seat < len(open_melds) else None
    max_turn = len(discards[max_seat]) + 1 if max_seat is not None and max_seat < len(discards) else None
    return {
        "category": category,
        "riichi_count": len(riichi_seats),
        "max_opponent_seat": max_seat,
        "max_opponent_melds": max_melds,
        "max_opponent_turn": max_turn,
        "max_opponent_turn_bucket": turn_bucket(max_turn),
        "max_opponent_tenpai_estimate": max_tenpai,
        "max_opponent_tenpai_bucket": tenpai_bucket(max_tenpai),
        "max_opponent_tenpai_decile": tenpai_decile(max_tenpai),
    }


def empty_danger_dict() -> dict[str, Any]:
    return DangerStats().to_dict()


def metric_from_nested(root: dict[str, Any], *keys: str) -> dict[str, Any]:
    node: Any = root
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return empty_danger_dict()
        node = node[key]
    if isinstance(node, DangerStats):
        return node.to_dict()
    if isinstance(node, dict):
        return finalize_nested(node)
    return empty_danger_dict()


def first_below_decile(decile_root: dict[str, Any], threshold_pct: float, min_n: int = 0) -> dict[str, Any] | None:
    for label in DECILE_ORDER:
        if label == "unknown":
            continue
        metrics = metric_from_nested(decile_root, label)
        rate = metrics.get("push_rate_danger_gt_5pct")
        n = metrics.get("n", 0)
        if rate is not None and n >= min_n and rate < threshold_pct:
            return {"decile": label, "n": n, "push_rate_danger_gt_5pct": rate, "min_n": min_n}
    return None


def build_cumulative_deciles(observations: list[tuple[float | None, float | None]]) -> dict[str, DangerStats]:
    cumulative: dict[str, DangerStats] = {label: DangerStats() for label in DECILE_ORDER[:-1]}
    for tenpai, danger in observations:
        if tenpai is None:
            continue
        pct_value = tenpai * 100.0
        for low in range(0, 100, 10):
            if pct_value >= low:
                cumulative[f"{low}-{low + 10}%"].add(danger)
    return cumulative


def first_below_cumulative(cumulative: dict[str, DangerStats], threshold_pct: float, min_n: int = 30) -> dict[str, Any] | None:
    for label in DECILE_ORDER[:-1]:
        metrics = cumulative[label].to_dict()
        rate = metrics.get("push_rate_danger_gt_5pct")
        n = metrics.get("n", 0)
        if rate is not None and n >= min_n and rate < threshold_pct:
            return {"estimate_at_least_decile": label, "n": n, "push_rate_danger_gt_5pct": rate, "min_n": min_n}
    return None


def first_turn_below(proxy_root: dict[str, Any], meld_key: str, threshold_pct: float) -> dict[str, Any] | None:
    for tb in TURN_BUCKET_ORDER[:-1]:
        metrics = metric_from_nested(proxy_root, meld_key, tb)
        rate = metrics.get("push_rate_danger_gt_5pct")
        if rate is not None and metrics.get("n", 0) > 0 and rate < threshold_pct:
            return {"turn_bucket": tb, "n": metrics["n"], "push_rate_danger_gt_5pct": rate}
    return None


def fmt_rate(metrics: dict[str, Any]) -> str:
    rate = metrics.get("push_rate_danger_gt_5pct")
    n = metrics.get("n", 0)
    return f"{rate:.1f}% (n={n})" if rate is not None else f"n={n}"


def fmt_gen(metrics: dict[str, Any]) -> str:
    rate = metrics.get("genbutsu_rate")
    n = metrics.get("n", 0)
    return f"{rate:.1f}% (n={n})" if rate is not None else f"n={n}"


def make_proposed_rules(final: dict[str, Any]) -> list[str]:
    rules: list[str] = []
    open_proxy = final["open_hand_trigger"]["human_proxy_by_meld_count_and_turn"]
    open_thresholds = final["open_hand_trigger"].get("thresholds", {})
    vs = final["vs_riichi"]
    reaction = final["immediate_reaction_after_riichi"]

    two_mid = open_proxy.get("2", {}).get("7-12", empty_danger_dict())
    two_late = open_proxy.get("2", {}).get("13+", empty_danger_dict())
    three_early = open_proxy.get("3+", {}).get("1-6", empty_danger_dict())
    three_mid = open_proxy.get("3+", {}).get("7-12", empty_danger_dict())

    if two_mid.get("n", 0):
        rules.append(
            "Against a 2-meld open hand, start pricing defense by the second row: the share of actual discards with Nishiki max danger above 5% was "
            f"{fmt_rate(two_mid)}, and turn 13+ was {fmt_rate(two_late)}."
        )
    if three_early.get("n", 0) or three_mid.get("n", 0):
        strongest_three = three_early if three_early.get("n", 0) else three_mid
        rules.append(
            "Against 3+ melds, treat the hand as a live threat immediately; the share of LuckyJ's actual discards with Nishiki max danger above 5% was "
            f"{fmt_rate(strongest_three)} in the earliest populated bucket."
        )

    decile_below_50 = open_thresholds.get("per_decile_first_below_50pct", {})
    decile_below_25 = open_thresholds.get("per_decile_first_below_25pct", {})
    if decile_below_50:
        extra = ""
        if decile_below_25:
            extra = (
                f"; below 25% first appeared at {decile_below_25.get('decile')} "
                f"({decile_below_25.get('push_rate_danger_gt_5pct')}%, n={decile_below_25.get('n')})"
            )
        rules.append(
            "With an engine tenpai read on 2+ melds, the first decile where push fell below 50% was "
            f"{decile_below_50.get('decile')} ({decile_below_50.get('push_rate_danger_gt_5pct')}%, n={decile_below_50.get('n')}){extra}."
        )

    by_shanten = vs.get("by_closed_shanten", {})
    tenpai = by_shanten.get("0", empty_danger_dict())
    one = by_shanten.get("1", empty_danger_dict())
    two = by_shanten.get("2", empty_danger_dict())
    three = by_shanten.get("3+", empty_danger_dict())
    if tenpai.get("n", 0) and two.get("n", 0):
        rules.append(
            "Versus riichi, tenpai is the main license to continue: closed tenpai pushed "
            f"{fmt_rate(tenpai)}, while closed 2-shanten pushed {fmt_rate(two)}."
        )
    if one.get("n", 0) and three.get("n", 0):
        rules.append(
            "Versus riichi, downgrade sharply outside tenpai: closed 1-shanten pushed "
            f"{fmt_rate(one)}, and closed 3+ shanten pushed {fmt_rate(three)}."
        )

    late_two = vs.get("by_closed_shanten_and_tiles_left", {}).get("2", {}).get("<=20", empty_danger_dict())
    late_one = vs.get("by_closed_shanten_and_tiles_left", {}).get("1", {}).get("<=20", empty_danger_dict())
    if late_two.get("n", 0) or late_one.get("n", 0):
        rules.append(
            "In the last 20 tiles versus riichi, don't chase from far away: 1-shanten pushed "
            f"{fmt_rate(late_one)}, 2-shanten pushed {fmt_rate(late_two)}."
        )

    reaction_by_shanten = reaction.get("by_own_shanten", {})
    r_tenpai = reaction_by_shanten.get("0", {"n": 0})
    r_one = reaction_by_shanten.get("1", {"n": 0})
    r_two = reaction_by_shanten.get("2", {"n": 0})
    if r_tenpai.get("n", 0) and (r_one.get("n", 0) or r_two.get("n", 0)):
        rules.append(
            "First discard after an opponent riichi should usually be genbutsu unless the hand is real: tenpai genbutsu "
            f"{fmt_gen(r_tenpai)}, 1-shanten {fmt_gen(r_one)}, 2-shanten {fmt_gen(r_two)}."
        )

    return rules[:8]


def main() -> None:
    raw_rows = base.parse_rows()
    rows = []
    seen_report_ids = set()
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

    table_by_threat: dict[str, Any] = {}
    table_by_threat_tenpai: dict[str, Any] = {}
    open_deciles: dict[str, Any] = {}
    open_proxy: dict[str, Any] = {}
    open_observations: list[tuple[float | None, float | None]] = []
    vs_riichi_by_shanten_left: dict[str, Any] = {}
    vs_riichi_by_shanten: dict[str, Any] = {}
    vs_riichi_by_left: dict[str, Any] = {}
    immediate_by_shanten: dict[str, Any] = {}
    immediate_by_general_state: dict[str, Any] = {}
    all_decisions = DangerStats()

    summary = {
        "n_rows_from_sheet": len(raw_rows),
        "n_unique_report_ids": len(rows),
        "n_duplicate_report_rows_skipped": len(duplicate_report_rows),
        "duplicate_report_rows_skipped": duplicate_report_rows[:20],
        "n_reports_processed": 0,
        "n_reports_failed": 0,
        "n_kyoku_seen": 0,
        "n_luckyj_tsumo_decision_states": 0,
        "n_own_riichi_tsumo_states_included": 0,
        "n_open_threat_states": 0,
        "n_riichi_threat_states": 0,
        "n_immediate_riichi_reactions": 0,
        "errors": [],
    }

    for row_index, row in enumerate(rows, 1):
        if row_index % 200 == 0:
            print(f"processed {row_index}/{len(rows)} reports")
        target = row.get("actor")
        if target is None or not (0 <= target < 4):
            continue
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
            summary["n_reports_processed"] += 1
        except Exception as exc:  # malformed or missing cache/network problem
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
                reached = [False, False, False, False]
                pending_riichi_discard = [False, False, False, False]
                pending_reaction: dict[int, dict[str, Any]] = {}

                for pos, state in enumerate(kyoku):
                    msg = state.get("info", {}).get("msg", {}) or {}
                    actor = msg.get("actor")
                    msg_type = msg.get("type")

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
                            if own_reached:
                                summary["n_own_riichi_tsumo_states_included"] += 1
                            shanten = compute_shanten_if_closed(hands[target], open_melds, target)
                            own_state = general_own_state(open_melds, target, own_reached, shanten)
                            closed_shanten = closed_shanten_bucket_from_value(shanten) if open_melds[target] == 0 and not own_reached else None
                            actual_danger = discard_danger(state, target, actual)
                            threat = classify_table_threat(target, open_melds, reached, discards, state)
                            threat_cat = threat["category"]
                            max_tenpai_bucket = threat["max_opponent_tenpai_bucket"]

                            all_decisions.add(actual_danger)
                            get_nested_stat(table_by_threat, threat_cat, own_state).add(actual_danger)
                            get_nested_stat(table_by_threat_tenpai, threat_cat, max_tenpai_bucket, own_state).add(actual_danger)

                            if threat_cat in {"2_meld_opponent", "3plus_meld_opponent"}:
                                summary["n_open_threat_states"] += 1
                                decile = threat["max_opponent_tenpai_decile"]
                                open_observations.append((threat["max_opponent_tenpai_estimate"], actual_danger))
                                get_nested_stat(open_deciles, decile).add(actual_danger)
                                meld_key = "3+" if (threat["max_opponent_melds"] or 0) >= 3 else "2"
                                get_nested_stat(open_proxy, meld_key, threat["max_opponent_turn_bucket"]).add(actual_danger)

                            if threat_cat in {"single_riichi", "riichi_plus_more"}:
                                summary["n_riichi_threat_states"] += 1
                                lb = left_bucket(msg.get("left_hai_num"))
                                if closed_shanten is not None:
                                    get_nested_stat(vs_riichi_by_shanten_left, closed_shanten, lb).add(actual_danger)
                                    get_nested_stat(vs_riichi_by_shanten, closed_shanten).add(actual_danger)
                                else:
                                    get_nested_stat(vs_riichi_by_shanten, own_state).add(actual_danger)
                                get_nested_stat(vs_riichi_by_left, lb).add(actual_danger)

                            if pending_reaction:
                                # One observation per outstanding opponent riichi declaration; if two players declare before
                                # LuckyJ's next tsumo, the same discard is judged against each declarer's own river plus
                                # the post-declaration tiles that have already passed safely this cycle.
                                actual_idx = tile_index(actual)
                                for riichi_seat in sorted(list(pending_reaction)):
                                    if riichi_seat == target:
                                        continue
                                    safe_tiles = pending_reaction[riichi_seat].get("safe_tile_indices", set())
                                    genbutsu = actual_idx is not None and actual_idx in safe_tiles
                                    if closed_shanten is not None:
                                        get_nested_bool_stat(immediate_by_shanten, closed_shanten).add(genbutsu)
                                    else:
                                        get_nested_bool_stat(immediate_by_shanten, own_state).add(genbutsu)
                                    get_nested_bool_stat(immediate_by_general_state, own_state).add(genbutsu)
                                    summary["n_immediate_riichi_reactions"] += 1
                                    pending_reaction.pop(riichi_seat, None)

                        if actor is not None and 0 <= actor < 4:
                            discard = msg.get("real_dahai")
                            if discard and discard != "?":
                                remove_tile(hands[actor], discard)

                    elif msg_type in base.HURO_TYPES:
                        if actor is not None and 0 <= actor < 4:
                            open_melds[actor] += 1
                            for tile in msg.get("consumed", []) or []:
                                remove_tile(hands[actor], tile)
                            discard = msg.get("real_dahai")
                            if discard and discard != "?":
                                remove_tile(hands[actor], discard)

                    elif msg_type == "ankan":
                        if actor is not None and 0 <= actor < 4:
                            open_melds[actor] += 1
                            for tile in msg.get("consumed", []) or []:
                                remove_tile(hands[actor], tile)

                    elif msg_type == "kakan":
                        if actor is not None and 0 <= actor < 4:
                            remove_tile(hands[actor], msg.get("pai"))

                    elif msg_type == "reach":
                        if actor is not None and 0 <= actor < 4:
                            reached[actor] = True
                            pending_riichi_discard[actor] = True
                            if actor != target:
                                existing_safe = {idx for idx in (tile_index(tile) for tile in discards[actor]) if idx is not None}
                                pending_reaction[actor] = {"kyoku_index": kyoku_index, "pos": pos, "safe_tile_indices": existing_safe}

                    elif msg_type == "dahai":
                        tile = msg.get("pai")
                        if actor is not None and 0 <= actor < 4 and tile:
                            idx = tile_index(tile)
                            discards[actor].append(tile)
                            for reaction in pending_reaction.values():
                                if idx is not None:
                                    reaction.setdefault("safe_tile_indices", set()).add(idx)
                            if pending_riichi_discard[actor]:
                                pending_riichi_discard[actor] = False

            except Exception as exc:
                if len(summary["errors"]) < 20:
                    summary["errors"].append({"report_id": row.get("report_id"), "kyoku_index": kyoku_index, "error": repr(exc)})
                continue

    cumulative_deciles = build_cumulative_deciles(open_observations)

    # Build final dicts with stable ordering and empty buckets where useful for threshold reading.
    final_open_deciles = {label: metric_from_nested(open_deciles, label) for label in DECILE_ORDER}
    final_cumulative = {label: cumulative_deciles[label].to_dict() for label in DECILE_ORDER[:-1]}
    final_open_proxy = {
        meld_key: {tb: metric_from_nested(open_proxy, meld_key, tb) for tb in TURN_BUCKET_ORDER}
        for meld_key in MELD_COUNT_ORDER
    }
    final_vs_shanten_left = {
        sh: {lb: metric_from_nested(vs_riichi_by_shanten_left, sh, lb) for lb in LEFT_BUCKET_ORDER}
        for sh in CLOSED_SHANTEN_ORDER
    }
    final_vs_shanten = {
        sh: metric_from_nested(vs_riichi_by_shanten, sh)
        for sh in CLOSED_SHANTEN_ORDER + ["own_open_hand", "own_riichi", "closed_unknown"]
    }
    final_vs_left = {lb: metric_from_nested(vs_riichi_by_left, lb) for lb in LEFT_BUCKET_ORDER}

    final_immediate_by_shanten = {
        key: finalize_nested(immediate_by_shanten[key]) if key in immediate_by_shanten else GenbutsuStats().to_dict()
        for key in CLOSED_SHANTEN_ORDER + ["own_open_hand", "own_riichi", "closed_unknown"]
    }
    final_immediate_by_general = {
        key: finalize_nested(immediate_by_general_state[key]) if key in immediate_by_general_state else GenbutsuStats().to_dict()
        for key in OWN_STATE_ORDER
    }

    final_table_by_threat = {
        threat: {own: metric_from_nested(table_by_threat, threat, own) for own in OWN_STATE_ORDER}
        for threat in THREAT_ORDER
    }
    final_table_by_threat_tenpai = {
        threat: {
            tb: {own: metric_from_nested(table_by_threat_tenpai, threat, tb, own) for own in OWN_STATE_ORDER}
            for tb in TENPAI_BUCKET_ORDER
        }
        for threat in THREAT_ORDER
    }

    output: dict[str, Any] = {
        "definitions": {
            "danger": "For LuckyJ's actual discard, max(state[danger_s/t/k][LuckyJ seat][tile_index] / 10000).",
            "push": "legacy field name: actual discard Nishiki max danger > 0.05; this is a danger proxy, not a push/fold label.",
            "hard_push": "legacy field name: actual discard Nishiki max danger > 0.10; this is a danger proxy, not a push/fold label.",
            "tenpai_estimate": "mean(state[tenpai_s/t/k][opponent seat]) / 100.",
            "tenpai_buckets": {"<30%": "estimate < 0.30", "30-60%": "0.30 <= estimate <= 0.60", ">60%": "estimate > 0.60"},
            "table_threats": THREAT_LABELS,
            "max_threat_opponent": "Riichi seats are chosen first when any opponent has riichi; otherwise the opponent(s) with max meld count are chosen, tied by higher NAGA tenpai estimate. Quiet tables use the highest tenpai estimate among opponents.",
            "meld_count_tracking": "chi/pon/daiminkan and ankan increment meld count; kakan upgrades without increment, matching scripts/build_point_examples.py collect_examples().",
            "turn": "opponent turn = len(discards[opponent]) + 1 at LuckyJ's decision.",
            "own_state": {
                "closed_tenpai": "no own melds, not already riichi, raw shanten <= 0 on the 13-tile hand plus draw",
                "closed_1_shanten": "no own melds, not already riichi, raw shanten == 1",
                "closed_2plus_shanten": "no own melds, not already riichi, raw shanten >= 2",
                "own_open_hand": "LuckyJ has at least one meld; shanten intentionally not computed",
                "own_riichi": "LuckyJ is already in riichi; included because every tsumo state with real_dahai+dahai_pred is counted, but it is not a free push/fold choice",
            },
            "tiles_left_buckets": {">40": "left_hai_num > 40", "40-21": "21 <= left_hai_num <= 40", "<=20": "left_hai_num <= 20"},
            "immediate_riichi_reaction": "For each opponent riichi declaration, LuckyJ's next tsumo discard is tested as genbutsu if its tile index appears in that riichi player's river or in any subsequent discard that passed safely before LuckyJ's next decision; multiple pending riichi declarations create multiple observations.",
            "n_fields": "In danger metrics, total_states counts matching decisions; n counts decisions with usable danger; rates use n. In genbutsu metrics, n counts reaction observations.",
        },
        "summary": summary | {"all_decisions_metric": all_decisions.to_dict()},
        "table_threat_metrics": {
            "by_threat": final_table_by_threat,
            "by_threat_and_max_opponent_tenpai_bucket": final_table_by_threat_tenpai,
        },
        "open_hand_trigger": {
            "scope": "no-riichi states where the max opponent has exactly 2 melds or 3+ melds",
            "by_opponent_tenpai_decile": final_open_deciles,
            "cumulative_at_or_above_tenpai_decile": final_cumulative,
            "thresholds": {
                "per_decile_first_below_50pct": first_below_decile(open_deciles, 50.0),
                "per_decile_first_below_25pct": first_below_decile(open_deciles, 25.0),
                "cumulative_first_below_50pct_min_n30": first_below_cumulative(cumulative_deciles, 50.0, min_n=30),
                "cumulative_first_below_25pct_min_n30": first_below_cumulative(cumulative_deciles, 25.0, min_n=30),
                "turn_proxy_first_below_50pct": {meld: first_turn_below(open_proxy, meld, 50.0) for meld in MELD_COUNT_ORDER},
                "turn_proxy_first_below_25pct": {meld: first_turn_below(open_proxy, meld, 25.0) for meld in MELD_COUNT_ORDER},
            },
            "human_proxy_by_meld_count_and_turn": final_open_proxy,
        },
        "vs_riichi": {
            "scope": "states classified as single_riichi or riichi_plus_more",
            "by_closed_shanten_and_tiles_left": final_vs_shanten_left,
            "by_closed_shanten": final_vs_shanten,
            "by_tiles_left": final_vs_left,
        },
        "immediate_reaction_after_riichi": {
            "by_own_shanten": final_immediate_by_shanten,
            "by_general_own_state": final_immediate_by_general,
        },
    }
    output["proposed_rules"] = make_proposed_rules(output)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(json.dumps({"summary": output["summary"], "proposed_rules": output["proposed_rules"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
