#!/usr/bin/env python3
"""Third-pass call mining: child-only prescriptions and dealer-vs-child NAGA agreement."""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import analyze_luckyj as base
import mine_rx_calls as pass1
import mine_rx2_calls as pass2
from build_point_examples import CALL_KIND_LABELS, yakuhai_for_seat
from extract_case_studies import remove_tile

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "analysis" / "rx3-calls-2026-07-05.json"
MIN_CELL_N = 120
HURO_TYPES = pass1.HURO_TYPES
SIDE_LABELS = ["child", "dealer"]
LATE_SHANTEN_BUCKETS = ["1", "2+", "0_or_less", "unknown"]
COPY_BUCKETS = ["first_discarded_copy", "later_copy"]


PUBLISHED: dict[str, tuple[float, str]] = {
    "yakuhai_pon_overall": (75.0, "baselines.yakuhai_pon.overall.child.pon_rate_pct"),
    "first_copy_yakuhai_pon": (76.9, "baselines.yakuhai_pon.first_copy.child.pon_rate_pct"),
    "later_copy_yakuhai_pon": (58.2, "baselines.yakuhai_pon.later_copy.child.pon_rate_pct"),
    "closed_to_open_chi": (6.8, "baselines.chi.closed_to_open.child.chi_rate_pct"),
    "already_open_chi": (27.4, "baselines.chi.already_open.child.chi_rate_pct"),
    "late_keiten_shanten_1": (31.9, "baselines.late_keiten.by_shanten.1.child.call_rate_pct"),
    "late_keiten_shanten_2plus": (20.7, "baselines.late_keiten.by_shanten.2+.child.call_rate_pct"),
    "late_keiten_shanten_0_or_less": (4.2, "baselines.late_keiten.by_shanten.0_or_less.child.call_rate_pct"),
    "junk_hand_pass": (85.9, "baselines.junk.all_call_opportunities.child.pass_rate_pct"),
    "junk_yakuhai_pon": (72.4, "baselines.junk.yakuhai_pon_opportunities.child.pon_rate_pct"),
    "yakuhai_threat_yes": (83.0, "condition_effects_child_only.yakuhai_pon.requested_cells.existing_table_threat.yes.pon_rate_pct"),
    "yakuhai_threat_no": (40.0, "condition_effects_child_only.yakuhai_pon.requested_cells.existing_table_threat.no.pon_rate_pct"),
    "yakuhai_turn_1_6_shanten_2_3": (87.0, "condition_effects_child_only.yakuhai_pon.requested_cells.turn_x_shanten.turn_1-6_shanten_2-3.pon_rate_pct"),
    "yakuhai_turn_7_12_shanten_0_1": (62.0, "condition_effects_child_only.yakuhai_pon.requested_cells.turn_x_shanten.turn_7-12_shanten_0-1.pon_rate_pct"),
    "yakuhai_turn_7_12_shanten_2_3": (64.0, "condition_effects_child_only.yakuhai_pon.requested_cells.turn_x_shanten.turn_7-12_shanten_2-3.pon_rate_pct"),
    "closed_chi_advances_to_le1_yes": (17.0, "condition_effects_child_only.closed_to_open_chi.requested_cells.best_chi_advances_to_le1.yes.chi_rate_pct"),
    "closed_chi_advances_to_le1_no": (2.0, "condition_effects_child_only.closed_to_open_chi.requested_cells.best_chi_advances_to_le1.no.chi_rate_pct"),
    "closed_chi_left_le_12": (18.0, "condition_effects_child_only.closed_to_open_chi.requested_cells.left_hai_num_le_12.yes.chi_rate_pct"),
    "closed_chi_turn_13_plus": (14.0, "condition_effects_child_only.closed_to_open_chi.requested_cells.turn_bucket.13+.chi_rate_pct"),
    "closed_chi_called_tile_dora": (11.0, "condition_effects_child_only.closed_to_open_chi.requested_cells.called_tile_is_dora.yes.chi_rate_pct"),
}


# ----------------------------- generic stats helpers -----------------------------


def round1(value: float | None) -> float | None:
    return round(value, 1) if value is not None and math.isfinite(value) else None


def round2(value: float | None) -> float | None:
    return round(value, 2) if value is not None and math.isfinite(value) else None


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def population_std(values: list[float]) -> float | None:
    if not values:
        return None
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def weighted_std(values: list[float], weights: list[int]) -> float | None:
    if not values or not weights or sum(weights) <= 0:
        return None
    avg = sum(value * weight for value, weight in zip(values, weights)) / sum(weights)
    return math.sqrt(sum(weight * ((value - avg) ** 2) for value, weight in zip(values, weights)) / sum(weights))


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def rate_payload(success: int, n: int, success_key: str, rate_key: str) -> dict[str, Any]:
    rate = success / n if n else None
    ci = 1.96 * math.sqrt(rate * (1.0 - rate) / n) * 100.0 if rate is not None and n else None
    return {
        "n": int(n),
        success_key: int(success),
        rate_key: round1(rate * 100.0) if rate is not None else None,
        "ci95_half_width_pp": round2(ci),
    }


def summarize_rate(counter: Counter, success_key: str, rate_key: str) -> dict[str, Any]:
    return rate_payload(int(counter["success"]), int(counter["n"]), success_key, rate_key)


def add_rate(counter: Counter, success: bool) -> None:
    counter["n"] += 1
    counter["success"] += int(success)


def add_yak(counter: Counter, poned: bool, called: bool) -> None:
    counter["n"] += 1
    counter["pon"] += int(poned)
    counter["called_any"] += int(called)
    counter["passed"] += int(not called)


def add_chi(counter: Counter, chii: bool, called: bool) -> None:
    counter["n"] += 1
    counter["chi"] += int(chii)
    counter["called_any"] += int(called)
    counter["passed"] += int(not called)


def add_call(counter: Counter, called: bool) -> None:
    counter["n"] += 1
    counter["called"] += int(called)
    counter["passed"] += int(not called)


def serialize_yak(counter: Counter) -> dict[str, Any]:
    n = int(counter["n"])
    return {
        "n": n,
        "pon": int(counter["pon"]),
        "pon_rate_pct": round1(100.0 * counter["pon"] / n) if n else None,
        "called_any": int(counter["called_any"]),
        "called_any_rate_pct": round1(100.0 * counter["called_any"] / n) if n else None,
        "passed": int(counter["passed"]),
    }


def serialize_chi(counter: Counter) -> dict[str, Any]:
    n = int(counter["n"])
    return {
        "n": n,
        "chi": int(counter["chi"]),
        "chi_rate_pct": round1(100.0 * counter["chi"] / n) if n else None,
        "called_any": int(counter["called_any"]),
        "called_any_rate_pct": round1(100.0 * counter["called_any"] / n) if n else None,
        "passed": int(counter["passed"]),
    }


def serialize_call(counter: Counter) -> dict[str, Any]:
    n = int(counter["n"])
    return {
        "n": n,
        "called": int(counter["called"]),
        "call_rate_pct": round1(100.0 * counter["called"] / n) if n else None,
        "passed": int(counter["passed"]),
        "pass_rate_pct": round1(100.0 * counter["passed"] / n) if n else None,
    }


def paired_side_payload(child: dict[str, Any], dealer: dict[str, Any], rate_key: str) -> dict[str, Any]:
    child_rate = child.get(rate_key)
    dealer_rate = dealer.get(rate_key)
    return {
        "child": child,
        "dealer": dealer,
        "delta_child_minus_dealer_pp": round1(child_rate - dealer_rate) if child_rate is not None and dealer_rate is not None else None,
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
    comp_n = total_n - group_n
    comp_success = total_success - group_success
    if group_n <= 0 or comp_n <= 0:
        return None
    item = rate_payload(group_success, group_n, success_key, rate_key)
    group_rate = group_success / group_n
    comp_rate = comp_success / comp_n if comp_n else None
    delta = (group_rate - comp_rate) * 100.0 if comp_rate is not None else None
    diff_ci = None
    significant = False
    if comp_rate is not None:
        diff_ci = 1.96 * math.sqrt(group_rate * (1.0 - group_rate) / group_n + comp_rate * (1.0 - comp_rate) / comp_n) * 100.0
        significant = bool(group_n >= MIN_CELL_N and comp_n >= MIN_CELL_N and delta is not None and abs(delta) > diff_ci)
    item.update(
        {
            "condition": condition,
            "value": value,
            "meets_min_cell_n": group_n >= MIN_CELL_N,
            "complement_meets_min_cell_n": comp_n >= MIN_CELL_N,
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
    items: list[dict[str, Any]] = []
    for (condition, value), counter in groups.items():
        item = effect_payload(
            condition,
            value,
            int(counter["success"]),
            int(counter["n"]),
            int(total["success"]),
            int(total["n"]),
            success_key,
            rate_key,
        )
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: (abs(item.get("delta_pp_vs_complement") or 0.0), item["n"]), reverse=True)
    return items


def add_condition(groups: dict[tuple[str, str], Counter], condition: str, value: Any, success: bool) -> None:
    if value is None:
        return
    label = "yes" if value is True else "no" if value is False else str(value)
    add_rate(groups[(condition, label)], success)


def condition_cells(effects: list[dict[str, Any]], requests: dict[str, list[str]]) -> dict[str, dict[str, dict[str, Any]]]:
    by_key = {(item["condition"], item["value"]): item for item in effects}
    return {condition: {value: by_key.get((condition, value), {"n": 0}) for value in values} for condition, values in requests.items()}


def get_path(obj: dict[str, Any], path: str) -> Any:
    cur: Any = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


# ----------------------------- decision helpers -----------------------------


def top_kind_from_nishiki_head(state: dict[str, Any], target: int) -> int | None:
    heads = pass1.huro_heads(state, target)
    if not heads:
        return None
    opts = heads[0]
    if not opts:
        return None
    return max(opts, key=lambda kind: opts[kind])


def add_agreement(counter: Counter, actual: bool, model_wants: bool) -> None:
    counter["n"] += 1
    counter["agree"] += int(actual == model_wants)
    counter["luckyj_called"] += int(actual)
    counter["nishiki_wants_call"] += int(model_wants)


def serialize_agreement(counter: Counter) -> dict[str, Any]:
    n = int(counter["n"])
    agree = int(counter["agree"])
    payload = rate_payload(agree, n, "agree", "agreement_rate_pct")
    payload["luckyj_called"] = int(counter["luckyj_called"])
    payload["nishiki_wants_call"] = int(counter["nishiki_wants_call"])
    return payload


def add_discard_match(counter: Counter, matched: bool) -> None:
    counter["n"] += 1
    counter["match"] += int(matched)


def serialize_discard_match(counter: Counter) -> dict[str, Any]:
    return rate_payload(int(counter["match"]), int(counter["n"]), "match", "match_rate_pct")


def per_game_yakuhai_pon_consistency(per_game: dict[str, Counter]) -> dict[str, Any]:
    games = []
    for report_id, counter in sorted(per_game.items()):
        n = int(counter["n"])
        if n < 3:
            continue
        pon = int(counter["success"])
        games.append(
            {
                "report_id": report_id,
                "n": n,
                "pon": pon,
                "pon_rate_pct": round1(100.0 * pon / n) if n else None,
            }
        )

    rates = [(game["pon_rate_pct"] or 0.0) / 100.0 for game in games]
    weights = [game["n"] for game in games]
    total_n = sum(weights)
    total_pon = sum(game["pon"] for game in games)
    weighted_mean = total_pon / total_n if total_n else None
    weighted_std_value = weighted_std(rates, weights)
    unweighted_mean = mean(rates)
    unweighted_std_value = population_std(rates)
    return {
        "definition": "Child-only games with at least three yakuhai pon opportunities; weighted standard deviation uses each game's opportunity count as weight.",
        "included_games_min_3_opportunities": len(games),
        "n": total_n,
        "pon": total_pon,
        "weighted_mean_pon_rate_pct": round1(weighted_mean * 100.0) if weighted_mean is not None else None,
        "weighted_std_pon_rate_pp": round1(weighted_std_value * 100.0) if weighted_std_value is not None else None,
        "unweighted_mean_pon_rate_pct": round1(unweighted_mean * 100.0) if unweighted_mean is not None else None,
        "unweighted_std_pon_rate_pp": round1(unweighted_std_value * 100.0) if unweighted_std_value is not None else None,
        "p25_pon_rate_pct": round1(percentile(rates, 0.25) * 100.0) if rates else None,
        "p50_pon_rate_pct": round1(percentile(rates, 0.50) * 100.0) if rates else None,
        "p75_pon_rate_pct": round1(percentile(rates, 0.75) * 100.0) if rates else None,
    }


def nishiki_top_discard(state: dict[str, Any]) -> str | None:
    rows = state.get("dahai_pred") or []
    if not rows:
        return None
    probs = rows[0]
    if not isinstance(probs, list) or len(probs) < 34:
        return None
    return base.TILES[max(range(34), key=lambda idx: probs[idx])]


def same_tile(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    try:
        return base.IDX[a] == base.IDX[b]
    except KeyError:
        return False


# ----------------------------- main miner -----------------------------


def mine() -> dict[str, Any]:
    groups = pass1.grouped_rows()
    source: dict[str, Any] = {
        "csv_rows": sum(len(rows) for rows in groups.values()),
        "unique_report_ids": len(groups),
        "duplicate_report_rows": sum(max(0, len(rows) - 1) for rows in groups.values()),
        "processed_reports": 0,
        "target_seat_corrections_from_report_names": 0,
        "errors": [],
    }

    agreement = {side: Counter() for side in SIDE_LABELS}
    discard_match = {side: Counter() for side in SIDE_LABELS}

    yak_total = {side: Counter() for side in SIDE_LABELS}
    yak_by_copy = {side: defaultdict(Counter) for side in SIDE_LABELS}
    chi_closed_to_open = {side: Counter() for side in SIDE_LABELS}
    chi_already_open = {side: Counter() for side in SIDE_LABELS}
    late_by_shanten = {side: defaultdict(Counter) for side in SIDE_LABELS}
    junk_all = {side: Counter() for side in SIDE_LABELS}
    junk_yak = {side: Counter() for side in SIDE_LABELS}

    child_yak_effect_total = Counter()
    child_chi_effect_total = Counter()
    child_yak_per_game: dict[str, Counter] = defaultdict(Counter)
    yak_effect_groups: dict[tuple[str, str], Counter] = defaultdict(Counter)
    chi_effect_groups: dict[tuple[str, str], Counter] = defaultdict(Counter)

    diagnostics = Counter()

    for game_i, (report_id, rows) in enumerate(sorted(groups.items()), start=1):
        try:
            data = base.fetch_report(report_id)
            base.normalize_report(data)
            fallback_target = rows[0]["actor"]
            target = pass1.find_luckyj_target(data, fallback_target)
            if target != fallback_target:
                source["target_seat_corrections_from_report_names"] += 1
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
                is_dealer = start.get("oya") == target
                side = "dealer" if is_dealer else "child"

                for pos, state in enumerate(kyoku):
                    msg = state.get("info", {}).get("msg", {})
                    actor = msg.get("actor")
                    msg_type = msg.get("type")

                    if msg_type == "dora" and msg.get("dora_marker"):
                        dora_markers.append(msg["dora_marker"])

                    if msg_type == "dahai" and pass1.huro_heads(state, target):
                        discard = msg.get("pai")
                        if discard:
                            called, called_type, called_kind, _ = pass1.actual_call(kyoku, pos, target)

                            # A. Hypothesis check: all huro opportunities, before prescription filters.
                            top_kind = top_kind_from_nishiki_head(state, target)
                            if top_kind is not None:
                                add_agreement(agreement[side], bool(called), top_kind != 0)

                            kinds = pass1.available_kinds(state, target)
                            if kinds:
                                turn = len(discards[target]) + 1
                                turn_b = pass1.turn_bucket(turn)
                                shanten = pass1.shanten_value(hands[target])
                                dora_n = pass1.dora_count(hands[target], dora_markers)
                                dora_b = pass2.yak_dora_bucket(dora_n)
                                table_threat = pass2.existing_table_threat(target, reached, open_melds)
                                diagnostics[f"{side}_call_opportunities_with_nonzero_kind"] += 1

                                left = msg.get("left_hai_num")
                                if left is not None and left <= 12:
                                    add_call(late_by_shanten[side][pass1.late_shanten_bucket(shanten)], called)

                                junk_hand = shanten is not None and shanten >= 4 and dora_n == 0
                                if junk_hand:
                                    add_call(junk_all[side], called)

                                is_yakuhai_pon_opp = (
                                    4 in kinds
                                    and pass1.base_tile(discard) in yakuhai_tiles
                                    and pass1.tile_count(hands[target], discard) >= 2
                                )
                                if is_yakuhai_pon_opp:
                                    poned = bool(called and called_type == "pon")
                                    add_yak(yak_total[side], poned, called)
                                    copy_b = "first_discarded_copy" if pass1.prior_discard_count(discards, discard) == 0 else "later_copy"
                                    add_yak(yak_by_copy[side][copy_b], poned, called)
                                    if junk_hand:
                                        add_yak(junk_yak[side], poned, called)
                                    if side == "child":
                                        add_rate(child_yak_per_game[report_id], poned)
                                        add_rate(child_yak_effect_total, poned)
                                        add_condition(yak_effect_groups, "existing_table_threat", table_threat, poned)
                                        add_condition(yak_effect_groups, "turn_x_shanten", pass2.turn_shanten_bucket(turn, shanten), poned)
                                        add_condition(yak_effect_groups, "dora_count", dora_b, poned)
                                        add_condition(
                                            yak_effect_groups,
                                            "second_yakuhai_pair_in_hand",
                                            pass2.has_second_yakuhai_pair(hands[target], discard, yakuhai_tiles),
                                            poned,
                                        )

                                if kinds & {1, 2, 3}:
                                    chii = bool(called and called_type == "chi")
                                    if open_melds[target] > 0:
                                        add_chi(chi_already_open[side], chii, called)
                                    else:
                                        add_chi(chi_closed_to_open[side], chii, called)
                                        if side == "child":
                                            add_rate(child_chi_effect_total, chii)
                                            best_chi = pass2.best_chi_after_shanten(hands[target], discard, kinds)
                                            if best_chi is not None:
                                                after_shanten = best_chi["after_shanten"]
                                                advances_to_le1 = bool(shanten is not None and after_shanten <= 1 and after_shanten < shanten)
                                            else:
                                                advances_to_le1 = None
                                                diagnostics["child_chi_best_after_shanten_missing"] += 1
                                            add_condition(chi_effect_groups, "best_chi_advances_to_le1", advances_to_le1, chii)
                                            add_condition(chi_effect_groups, "left_hai_num_le_12", left is not None and left <= 12, chii)
                                            add_condition(chi_effect_groups, "turn_bucket", turn_b, chii)
                                            add_condition(chi_effect_groups, "called_tile_is_dora", pass2.is_tile_dora(discard, dora_markers), chii)

                    # Secondary: plain tsumo-discard match by dealer/child.
                    if actor == target and msg_type == "tsumo" and not msg.get("reached"):
                        actual_discard = msg.get("real_dahai")
                        top_discard = nishiki_top_discard(state)
                        if actual_discard and actual_discard != "?" and top_discard:
                            add_discard_match(discard_match[side], same_tile(actual_discard, top_discard))

                    # State updates, kept aligned with pass-1/pass-2 miners.
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
                print(f"processed {game_i}/{len(groups)} reports", file=sys.stderr, flush=True)
        except Exception as exc:  # keep mining despite malformed reports
            source["errors"].append({"report_id": report_id, "error": repr(exc)})
            print(f"error {report_id}: {exc!r}", file=sys.stderr, flush=True)

    yak_effects = sorted_effects(yak_effect_groups, child_yak_effect_total, "pon", "pon_rate_pct")
    chi_effects = sorted_effects(chi_effect_groups, child_chi_effect_total, "chi", "chi_rate_pct")

    baselines = {
        "yakuhai_pon": {
            "overall": paired_side_payload(serialize_yak(yak_total["child"]), serialize_yak(yak_total["dealer"]), "pon_rate_pct"),
            "first_copy": paired_side_payload(
                serialize_yak(yak_by_copy["child"]["first_discarded_copy"]),
                serialize_yak(yak_by_copy["dealer"]["first_discarded_copy"]),
                "pon_rate_pct",
            ),
            "later_copy": paired_side_payload(
                serialize_yak(yak_by_copy["child"]["later_copy"]),
                serialize_yak(yak_by_copy["dealer"]["later_copy"]),
                "pon_rate_pct",
            ),
        },
        "chi": {
            "closed_to_open": paired_side_payload(serialize_chi(chi_closed_to_open["child"]), serialize_chi(chi_closed_to_open["dealer"]), "chi_rate_pct"),
            "already_open": paired_side_payload(serialize_chi(chi_already_open["child"]), serialize_chi(chi_already_open["dealer"]), "chi_rate_pct"),
        },
        "late_keiten": {
            "by_shanten": {
                bucket: paired_side_payload(serialize_call(late_by_shanten["child"][bucket]), serialize_call(late_by_shanten["dealer"][bucket]), "call_rate_pct")
                for bucket in LATE_SHANTEN_BUCKETS
            }
        },
        "junk": {
            "all_call_opportunities": paired_side_payload(serialize_call(junk_all["child"]), serialize_call(junk_all["dealer"]), "pass_rate_pct"),
            "yakuhai_pon_opportunities": paired_side_payload(serialize_yak(junk_yak["child"]), serialize_yak(junk_yak["dealer"]), "pon_rate_pct"),
        },
    }

    result: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "definitions": {
            "dealer_vs_child_naga_match": "All LuckyJ huro opportunities before prescription filtering. Nishiki is huro options head 0; Nishiki wants call iff the top-probability kind is not 0. Agreement is (LuckyJ actually called) == (Nishiki wants call).",
            "child": "LuckyJ is not oya for the kyoku.",
            "dealer": "LuckyJ is oya for the kyoku.",
            "yakuhai_pon_opportunity": "Pass-1 detector: triggering discard is yakuhai for LuckyJ's current seat, LuckyJ has at least two in concealed hand, and huro options include kind 4. Seat wind is recomputed from oya per kyoku.",
            "closed_to_open_chi_opportunity": "huro options contain chi kind 1/2/3 and LuckyJ has no prior open chi/pon/daiminkan meld; closed kan is not counted as open.",
            "late_keiten": "All pass-1 nonzero-kind huro opportunities with left_hai_num <= 12, bucketed by regular-hand shanten.",
            "condition_effect_delta_pp_vs_complement": "Cell rate minus rate for all other child-only opportunities in the same population.",
            "significant": f"True when n and complement_n are at least {MIN_CELL_N} and |delta_pp_vs_complement| exceeds the 95% two-proportion normal half-width.",
            "per_game_consistency_child_only": "Child-only per-game spread for the intro sentence; yakuhai pon requires at least three pon opportunities per game.",
            "min_cell_n": MIN_CELL_N,
            "all_rates_are_percent": True,
            "call_kind_labels": {str(k): v for k, v in CALL_KIND_LABELS.items()},
        },
        "dealer_vs_child_naga_match": {
            "call_decision_agreement": {side: serialize_agreement(agreement[side]) for side in SIDE_LABELS},
            "plain_tsumo_discard_match": {side: serialize_discard_match(discard_match[side]) for side in SIDE_LABELS},
        },
        "baselines": baselines,
        "per_game_consistency_child_only": {
            "yakuhai_pon": per_game_yakuhai_pon_consistency(child_yak_per_game),
        },
        "condition_effects_child_only": {
            "yakuhai_pon": {
                "population": summarize_rate(child_yak_effect_total, "pon", "pon_rate_pct"),
                "effects_sorted_by_abs_delta_pp": True,
                "effects": yak_effects,
                "requested_cells": condition_cells(
                    yak_effects,
                    {
                        "existing_table_threat": ["yes", "no"],
                        "turn_x_shanten": [
                            "turn_1-6_shanten_2-3",
                            "turn_7-12_shanten_0-1",
                            "turn_7-12_shanten_2-3",
                            "turn_1-6_shanten_0-1",
                            "turn_13+_shanten_0-1",
                        ],
                        "dora_count": ["0", "1", "2", "3+"],
                        "second_yakuhai_pair_in_hand": ["yes", "no"],
                    },
                ),
            },
            "closed_to_open_chi": {
                "population": summarize_rate(child_chi_effect_total, "chi", "chi_rate_pct"),
                "effects_sorted_by_abs_delta_pp": True,
                "effects": chi_effects,
                "requested_cells": condition_cells(
                    chi_effects,
                    {
                        "best_chi_advances_to_le1": ["yes", "no"],
                        "left_hai_num_le_12": ["yes", "no"],
                        "turn_bucket": ["13+", "1-6", "7-12"],
                        "called_tile_is_dora": ["yes", "no"],
                    },
                ),
            },
        },
        "diagnostics": dict(diagnostics),
    }

    changed = []
    for label, (published, path) in PUBLISHED.items():
        current = get_path(result, path)
        if isinstance(current, (int, float)) and abs(float(current) - published) >= 2.0:
            changed.append(
                {
                    "label": label,
                    "published_pct": published,
                    "child_only_pct": round1(float(current)),
                    "delta_pp": round1(float(current) - published),
                    "path": path,
                }
            )
    changed.sort(key=lambda item: abs(item["delta_pp"]), reverse=True)
    result["changed_vs_published"] = changed
    return result


def main() -> None:
    result = mine()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(
        json.dumps(
            {
                "dealer_vs_child_naga_match": result["dealer_vs_child_naga_match"]["call_decision_agreement"],
                "changed_vs_published": result["changed_vs_published"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if result["source"]["errors"]:
        print(f"errors: {len(result['source']['errors'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
