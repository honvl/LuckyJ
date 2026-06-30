#!/usr/bin/env python3
"""Mine LuckyJ/NAGA/Mortal move patterns for new playbook candidates.

The NAGA report cache is the broad source of truth. Mortal is optional but,
when local model/log assets are available, this script replays a deterministic
sample of statistically interesting NAGA-split positions through Mortal and
summarizes cross-model agreement.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import analyze_luckyj as base
import build_mortal_analysis as mortal


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "model-patterns.json"
RANDOM_SEED = 20260630

OUTSIDE = {"honor", "terminal"}
WINDS = ["E", "S", "W", "N"]
DRAGONS = {"P", "F", "C"}
PATTERN_LABELS = {
    "keep_dora_or_red": "Keep dora/red-five material instead of taking the clean NAGA cut",
    "keep_pair_anchor": "Keep a pair or triplet anchor that NAGA wants to break",
    "break_pair_anchor": "Break a pair earlier than NAGA",
    "keep_defensive_exit": "Keep genbutsu/suji exits while cutting elsewhere",
    "threat_keep_exit": "Keep a defensive exit against an active riichi/open threat",
    "spend_defensive_exit": "Spend a safe-looking tile while NAGA keeps it",
    "cut_inside_keep_outside": "Cut a middle tile while keeping outside/safety/yaku material",
    "cut_outside_keep_inside": "Cut outside material while keeping middle-tile shape",
    "safer_than_naga": "Choose a lower immediate-danger discard than NAGA",
    "riskier_than_naga": "Choose a higher immediate-danger discard than NAGA",
    "leader_low_risk": "Leader/large-stack choices that do not increase danger",
    "behind_risk_buy": "Behind-score choices that buy route/value with extra danger",
    "multi_threat_safe_tenpai": "Middle/late choices preserving exits with multiple threats",
    "honor_cleanup_vs_shape": "Cut a loose honor while NAGA prefers shape cleanup",
    "clean_open_yaku_condition_honor": "Clean a singleton yakuhai before an unproven open hand can use it",
    "early_guest_honor_cleanup": "Cut a loose non-self honor before shape cleanup in the first row",
    "keep_self_yakuhai_pair_anchor": "Keep own yakuhai pair or triplet anchor while NAGA breaks it",
    "spend_off_target_safety_for_shape": "Spend a safe-looking tile that does not answer the current threat",
    "late_named_exit_over_shape": "Late keep of a named exit over NAGA's shape-cleaning discard",
}


def mean(values: list[float | int | None]) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return statistics.mean(vals) if vals else None


def pct(num: int | float, den: int | float) -> float:
    return float(num) / den if den else 0.0


def norm_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def two_prop_p_value(a: int, n_a: int, b: int, n_b: int) -> float | None:
    if n_a <= 0 or n_b <= 0:
        return None
    pooled = (a + b) / (n_a + n_b)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    if se == 0:
        return None
    z = (a / n_a - b / n_b) / se
    return 2 * (1 - norm_cdf(abs(z)))


def score_band(score: int | None) -> str:
    if score is None:
        return "unknown"
    if score >= 35000:
        return "lead"
    if score >= 25000:
        return "above_start"
    if score >= 15000:
        return "behind"
    return "danger"


def tile_id(tile: str) -> int:
    return base.IDX[tile]


def same_tile(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    try:
        return tile_id(a) == tile_id(b)
    except KeyError:
        return False


def tile_base(tile: str | None) -> str:
    return str(tile or "").replace("r", "")


def dora_from_marker(marker: str | None) -> str | None:
    if not marker:
        return None
    marker = tile_base(marker)
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


def is_doraish(tile: str | None, dora_markers: list[str]) -> bool:
    if not tile:
        return False
    return "r" in tile or tile_base(tile) in {dora_from_marker(marker) for marker in dora_markers}


def seat_wind(start: dict[str, Any], seat: int) -> str:
    return WINDS[(seat - start.get("oya", 0)) % 4]


def is_yakuhai_for_seat(tile: str | None, start: dict[str, Any], seat: int) -> bool:
    return tile_base(tile) in (DRAGONS | {start.get("bakaze"), seat_wind(start, seat)})


def meld_tiles(meld: str) -> list[str]:
    return [tile for tile in str(meld).split() if tile and tile != "+"]


def meld_shows_yakuhai_yaku(meld: str, start: dict[str, Any], seat: int) -> bool:
    counts = Counter(tile_id(tile) for tile in meld_tiles(meld))
    return any(count >= 3 and is_yakuhai_for_seat(base.TILES[idx], start, seat) for idx, count in counts.items())


def meld_all_simples(meld: str) -> bool:
    tiles = meld_tiles(meld)
    return bool(tiles) and all(base.tile_class(tile) == "simple" for tile in tiles)


def yaku_condition_threats(start: dict[str, Any], target: int, melds: list[list[str]], tile: str | None) -> list[int]:
    if base.tile_class(tile) != "honor":
        return []
    threats = []
    for seat, player_melds in enumerate(melds):
        if seat == target or not player_melds:
            continue
        if any(meld_shows_yakuhai_yaku(meld, start, seat) for meld in player_melds):
            continue
        if all(meld_all_simples(meld) for meld in player_melds):
            continue
        if is_yakuhai_for_seat(tile, start, seat):
            threats.append(seat)
    return threats


def visible_count(tile: str | None, discards: list[list[str]], melds: list[list[str]], dora_markers: list[str]) -> int:
    if not tile:
        return 0
    target = tile_id(tile)
    count = sum(1 for marker in dora_markers if tile_id(marker) == target)
    count += sum(1 for river in discards for discarded in river if tile_id(discarded) == target)
    count += sum(1 for player_melds in melds for meld in player_melds for item in meld_tiles(meld) if tile_id(item) == target)
    return count


def remove_tile(hand: list[str], tile: str | None) -> bool:
    if not tile:
        return False
    if tile in hand:
        hand.remove(tile)
        return True
    try:
        target = tile_id(tile)
    except KeyError:
        return False
    for item in list(hand):
        if tile_id(item) == target:
            hand.remove(item)
            return True
    return False


def hand_counter(hand: list[str]) -> Counter:
    return Counter(tile_id(tile) for tile in hand)


def pattern_keys(decision: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    if decision["naga_is_doraish"] and not decision["actual_is_doraish"]:
        keys.append("keep_dora_or_red")
    if decision["naga_count"] >= 2 and decision["actual_count"] == 1:
        keys.append("keep_pair_anchor")
    if decision["actual_count"] >= 2 and decision["naga_count"] == 1:
        keys.append("break_pair_anchor")
    if decision["naga_safety_kind"] and not decision["actual_safety_kind"]:
        keys.append("keep_defensive_exit")
    if decision["naga_safety_kind"] and decision["naga_safety_vs_threat"]:
        keys.append("threat_keep_exit")
    if decision["actual_safety_kind"] and not decision["naga_safety_kind"]:
        keys.append("spend_defensive_exit")
    if decision["actual_class"] == "simple" and decision["naga_class"] in OUTSIDE:
        keys.append("cut_inside_keep_outside")
    if decision["actual_class"] in OUTSIDE and decision["naga_class"] == "simple":
        keys.append("cut_outside_keep_inside")
    if decision["danger_delta"] is not None and decision["danger_delta"] < -0.05:
        keys.append("safer_than_naga")
    if decision["danger_delta"] is not None and decision["danger_delta"] > 0.05:
        keys.append("riskier_than_naga")
    if decision["score"] is not None and decision["score"] >= 35000 and (decision["danger_delta"] is None or decision["danger_delta"] <= 0.02):
        keys.append("leader_low_risk")
    if decision["score"] is not None and decision["score"] < 25000 and decision["danger_delta"] is not None and decision["danger_delta"] > 0.04:
        keys.append("behind_risk_buy")
    if decision["stage"] in {"middle", "late"} and decision["active_threats"] >= 2 and decision["naga_safety_kind"]:
        keys.append("multi_threat_safe_tenpai")
    if decision["actual_class"] == "honor" and decision["naga_class"] == "simple" and decision["actual_count"] == 1:
        keys.append("honor_cleanup_vs_shape")
    if (
        decision["actual_class"] == "honor"
        and decision["actual_count"] == 1
        and decision["actual_yaku_condition_threats"] > 0
        and decision["own_discards"] <= 6
        and decision["actual_visible_count"] <= 1
    ):
        keys.append("clean_open_yaku_condition_honor")
    if (
        decision["actual_class"] == "honor"
        and decision["naga_class"] == "simple"
        and decision["actual_count"] == 1
        and not decision["actual_is_self_yakuhai"]
        and decision["own_discards"] <= 5
    ):
        keys.append("early_guest_honor_cleanup")
    if decision["naga_is_self_yakuhai"] and decision["naga_count"] >= 2 and decision["actual_count"] == 1:
        keys.append("keep_self_yakuhai_pair_anchor")
    if decision["actual_safety_kind"] and not decision["actual_safety_vs_threat"] and decision["naga_class"] == "simple":
        keys.append("spend_off_target_safety_for_shape")
    if decision["stage"] == "late" and decision["naga_safety_kind"] and decision["naga_safety_vs_threat"] and decision["naga_class"] in OUTSIDE:
        keys.append("late_named_exit_over_shape")
    return keys


def collect_decisions(max_reports: int | None = None) -> list[dict[str, Any]]:
    rows = base.parse_rows()
    if max_reports:
        rows = rows[:max_reports]
    decisions: list[dict[str, Any]] = []

    for row in rows:
        target = row["actor"]
        log_id = mortal.log_id_from_paifu(row["paifu"])
        data = base.fetch_report(row["report_id"])
        naga_types = base.normalize_report(data)

        for kyoku_index, kyoku in enumerate(data["pred"]):
            start = kyoku[0].get("info", {}).get("msg", {})
            hands = [list(hand) for hand in start.get("tehais", [[], [], [], []])]
            discards = [[], [], [], []]
            melds = [[], [], [], []]
            open_melds = [0, 0, 0, 0]
            reached = [False, False, False, False]
            dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []
            start_rank = None
            if "seat2rank" in start and target < len(start["seat2rank"]):
                start_rank = start["seat2rank"][target] + 1
            score = start.get("scores", [None] * 4)[target]
            end_msgs = start.get("end_msgs") or []
            delta = base.round_delta(end_msgs, target)
            result = base.round_result(end_msgs, target)

            for pos, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")

                if msg_type == "dora" and msg.get("dora_marker"):
                    dora_markers.append(msg["dora_marker"])

                if msg_type == "tsumo":
                    if actor is not None:
                        hands[actor].append(msg["pai"])
                    if (
                        actor == target
                        and "dahai_pred" in state
                        and msg.get("real_dahai") not in (None, "?")
                        and not msg.get("reached")
                        and "reach" not in state
                    ):
                        actual = msg["real_dahai"]
                        model_rows = []
                        for model_idx in range(min(len(naga_types), len(state["dahai_pred"]))):
                            top, top_prob = base.top_tile(state["dahai_pred"][model_idx])
                            actual_prob = base.prob_for(state["dahai_pred"][model_idx], actual)
                            model_rows.append((top, top_prob, actual_prob))
                        if model_rows:
                            naga, naga_prob, actual_prob = model_rows[0]
                            mismatch = not same_tile(actual, naga)
                            hand_counts = hand_counter(hands[target])
                            actual_danger = base.danger_for(state, target, actual)
                            naga_danger = base.danger_for(state, target, naga)
                            actual_safety = base.defensive_tile_read(actual, target, discards, reached, open_melds)
                            naga_safety = base.defensive_tile_read(naga, target, discards, reached, open_melds)
                            left = msg.get("left_hai_num")
                            decision = {
                                "id": f"{row['idx']}:{kyoku_index}:{pos}",
                                "game": row["idx"],
                                "rank": row["rank"],
                                "score": score,
                                "score_band": score_band(score),
                                "start_rank": start_rank,
                                "round_delta": delta,
                                "won_round": bool(result["win"]),
                                "dealt_in": bool(result["deal_in"]),
                                "report": row["report"],
                                "paifu": row["paifu"],
                                "log_id": log_id,
                                "kyoku_index": kyoku_index,
                                "position": pos,
                                "left": left,
                                "stage": base.stage_from_left(left),
                                "actual": actual,
                                "naga": naga,
                                "actual_class": base.tile_class(actual),
                                "naga_class": base.tile_class(naga),
                                "actual_count": hand_counts[tile_id(actual)],
                                "naga_count": hand_counts[tile_id(naga)],
                                "red_count": sum(1 for tile in hands[target] if "r" in tile),
                                "honor_count": sum(1 for tile in hands[target] if base.tile_class(tile) == "honor"),
                                "pair_count": sum(1 for count in hand_counts.values() if count >= 2),
                                "actual_is_doraish": is_doraish(actual, dora_markers),
                                "naga_is_doraish": is_doraish(naga, dora_markers),
                                "actual_prob": actual_prob,
                                "naga_prob": naga_prob,
                                "prob_gap": naga_prob - actual_prob if mismatch else 0.0,
                                "mismatch": mismatch,
                                "big_gap": mismatch and (naga_prob - actual_prob) >= 0.5,
                                "bad_by_naga": mismatch and actual_prob < 0.05,
                                "actual_danger": actual_danger,
                                "naga_danger": naga_danger,
                                "danger_delta": actual_danger - naga_danger if actual_danger is not None and naga_danger is not None else None,
                                "actual_safety_kind": actual_safety["kind"],
                                "actual_safety_vs_threat": actual_safety["safe_against_threat"],
                                "naga_safety_kind": naga_safety["kind"],
                                "naga_safety_vs_threat": naga_safety["safe_against_threat"],
                                "active_threats": sum(1 for seat in range(4) if seat != target and (reached[seat] or open_melds[seat])),
                                "riichi_threats": sum(1 for seat in range(4) if seat != target and reached[seat]),
                                "open_threats": sum(1 for seat in range(4) if seat != target and open_melds[seat]),
                                "own_discards": len(discards[target]),
                                "actual_visible_count": visible_count(actual, discards, melds, dora_markers),
                                "naga_visible_count": visible_count(naga, discards, melds, dora_markers),
                                "actual_is_self_yakuhai": is_yakuhai_for_seat(actual, start, target),
                                "naga_is_self_yakuhai": is_yakuhai_for_seat(naga, start, target),
                                "actual_yaku_condition_threats": len(yaku_condition_threats(start, target, melds, actual)),
                                "naga_yaku_condition_threats": len(yaku_condition_threats(start, target, melds, naga)),
                            }
                            if mismatch:
                                decision["patterns"] = pattern_keys(decision)
                            else:
                                decision["patterns"] = []
                            decisions.append(decision)
                    discard = msg.get("real_dahai")
                    if actor is not None and discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type in base.HURO_TYPES:
                    if actor is not None:
                        consumed = msg.get("consumed", [])
                        call_tiles = consumed + ([msg.get("pai")] if msg.get("pai") else [])
                        melds[actor].append(" ".join(call_tiles))
                        open_melds[actor] += 1
                    for tile in msg.get("consumed", []):
                        if actor is not None:
                            remove_tile(hands[actor], tile)
                    discard = msg.get("real_dahai")
                    if actor is not None and discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type == "ankan":
                    if actor is not None:
                        consumed = msg.get("consumed", [])
                        melds[actor].append(" ".join(consumed))
                        open_melds[actor] += 1
                        for tile in consumed:
                            remove_tile(hands[actor], tile)

                elif msg_type == "kakan":
                    if actor is not None:
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

    return decisions


def summarize_patterns(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    mismatches = [decision for decision in decisions if decision["mismatch"]]
    baseline_bad = sum(1 for decision in mismatches if decision["bad_by_naga"])
    baseline_big = sum(1 for decision in mismatches if decision["big_gap"])

    by_pattern: dict[str, Any] = {}
    pattern_to_decisions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in mismatches:
        for key in decision["patterns"]:
            pattern_to_decisions[key].append(decision)

    for key, items in sorted(pattern_to_decisions.items()):
        n = len(items)
        bad = sum(1 for item in items if item["bad_by_naga"])
        big = sum(1 for item in items if item["big_gap"])
        complement = [item for item in mismatches if key not in item["patterns"]]
        comp_bad = sum(1 for item in complement if item["bad_by_naga"])
        comp_big = sum(1 for item in complement if item["big_gap"])
        by_pattern[key] = {
            "label": PATTERN_LABELS.get(key, key),
            "n": n,
            "share_of_mismatches": pct(n, len(mismatches)),
            "bad_rate": pct(bad, n),
            "bad_lift_vs_other_mismatches": pct(bad, n) - pct(comp_bad, len(complement)),
            "bad_rate_p_value": two_prop_p_value(bad, n, comp_bad, len(complement)),
            "big_gap_rate": pct(big, n),
            "big_gap_lift_vs_other_mismatches": pct(big, n) - pct(comp_big, len(complement)),
            "big_gap_p_value": two_prop_p_value(big, n, comp_big, len(complement)),
            "avg_prob_gap": mean([item["prob_gap"] for item in items]),
            "avg_danger_delta": mean([item["danger_delta"] for item in items]),
            "avg_left": mean([item["left"] for item in items]),
            "stage_counts": dict(Counter(item["stage"] for item in items)),
            "score_band_counts": dict(Counter(item["score_band"] for item in items)),
        }

    return {
        "overall": {
            "decisions": len(decisions),
            "mismatches": len(mismatches),
            "mismatch_rate": pct(len(mismatches), len(decisions)),
            "bad_rate_among_mismatches": pct(baseline_bad, len(mismatches)),
            "big_gap_rate_among_mismatches": pct(baseline_big, len(mismatches)),
        },
        "patterns": by_pattern,
    }


def candidate_score(decision: dict[str, Any]) -> float:
    score = decision["prob_gap"]
    if decision["naga_safety_vs_threat"]:
        score += 0.25
    if decision["danger_delta"] is not None:
        score += min(0.25, abs(decision["danger_delta"]))
    if decision["stage"] == "middle":
        score += 0.05
    if decision["stage"] == "late":
        score += 0.1
    return score


def select_mortal_candidates(decisions: list[dict[str, Any]], per_pattern: int, total_limit: int) -> list[dict[str, Any]]:
    rng = random.Random(RANDOM_SEED)
    mismatches = [decision for decision in decisions if decision["mismatch"] and decision["patterns"]]
    selected: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()

    for pattern in PATTERN_LABELS:
        pool = [decision for decision in mismatches if pattern in decision["patterns"] and decision["prob_gap"] >= 0.08]
        pool.sort(key=candidate_score, reverse=True)
        # Keep the sample from collapsing into one repeated game.
        rng.shuffle(pool[: min(len(pool), per_pattern * 4)])
        pattern_selected = []
        log_counts: Counter = Counter()
        for decision in sorted(pool, key=candidate_score, reverse=True):
            if len(pattern_selected) >= per_pattern:
                break
            key = (decision["log_id"], decision["kyoku_index"], decision["left"], decision["actual"], decision["naga"])
            if key in seen or log_counts[decision["log_id"]] >= 2:
                continue
            seen.add(key)
            log_counts[decision["log_id"]] += 1
            pattern_selected.append(decision)
        selected.extend(pattern_selected)
        if len(selected) >= total_limit:
            break

    selected.sort(key=candidate_score, reverse=True)
    return selected[:total_limit]


def actual_from_opportunity(opp: mortal.Opportunity, fallback: str) -> str | None:
    actual = mortal.actual_choice(opp.actual_events, {"kind": "discard", "actual": fallback})
    return actual.get("tile")


def compare_mortal(candidates: list[dict[str, Any]], log_dir: Path, model_path: Path) -> dict[str, Any]:
    if not candidates:
        return {"enabled": False, "reason": "no candidates"}
    if not log_dir.exists() or not model_path.exists():
        return {"enabled": False, "reason": "missing Mortal log/model assets"}

    engine = mortal.load_mortal_engine(model_path)
    by_log: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_log[candidate["log_id"]].append(candidate)

    matched: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for idx, (log_id, log_candidates) in enumerate(sorted(by_log.items()), 1):
        path = log_dir / f"{log_id}.json.gz"
        if not path.exists():
            missing.extend(log_candidates)
            continue
        events = mortal.load_log(path)
        fallback = mortal.tw_from_paifu(log_candidates[0]["paifu"])
        actor = mortal.actor_for_luckyj(events, fallback)
        opportunities = mortal.replay_opportunities(log_id, events, actor, engine)
        draw_opps = [opp for opp in opportunities if opp.kind == "draw"]

        for candidate in log_candidates:
            pool = []
            for opp in draw_opps:
                if opp.kyoku_index != candidate["kyoku_index"]:
                    continue
                actual = actual_from_opportunity(opp, candidate["actual"])
                if same_tile(actual, candidate["actual"]):
                    pool.append((abs((opp.left or 0) - (candidate["left"] or 0)), opp, actual))
            if not pool:
                missing.append(candidate)
                continue
            _, opp, actual_tile = min(pool, key=lambda item: item[0])
            model = mortal.model_choice(opp.reaction)
            choices = mortal.decode_candidates(opp.reaction)
            model_tile = model.get("tile") if model.get("type") == "dahai" else None
            top_candidates = choices[:6]
            actual_prob = next((item["probability"] for item in choices if same_tile(item.get("tile"), candidate["actual"])), 0.0)
            naga_prob = next((item["probability"] for item in choices if same_tile(item.get("tile"), candidate["naga"])), 0.0)
            matched.append(
                {
                    "candidate_id": candidate["id"],
                    "patterns": candidate["patterns"],
                    "game": candidate["game"],
                    "log_id": log_id,
                    "kyoku_index": candidate["kyoku_index"],
                    "left": candidate["left"],
                    "stage": candidate["stage"],
                    "score_band": candidate["score_band"],
                    "actual": candidate["actual"],
                    "naga": candidate["naga"],
                    "mortal": model,
                    "mortal_agrees_luckyj": same_tile(model_tile, candidate["actual"]),
                    "mortal_agrees_naga": same_tile(model_tile, candidate["naga"]),
                    "mortal_actual_prob": actual_prob,
                    "mortal_naga_prob": naga_prob,
                    "mortal_top_prob": top_candidates[0]["probability"] if top_candidates else None,
                    "top_candidates": top_candidates,
                }
            )
        if idx % 25 == 0:
            print(f"mortal replayed {idx}/{len(by_log)} logs; matched={len(matched)} missing={len(missing)}", flush=True)

    by_pattern: dict[str, Any] = {}
    for pattern in PATTERN_LABELS:
        rows = [row for row in matched if pattern in row["patterns"]]
        if not rows:
            continue
        luckyj = sum(1 for row in rows if row["mortal_agrees_luckyj"])
        naga = sum(1 for row in rows if row["mortal_agrees_naga"])
        by_pattern[pattern] = {
            "label": PATTERN_LABELS[pattern],
            "sampled": len(rows),
            "mortal_agrees_luckyj": luckyj,
            "mortal_agrees_naga": naga,
            "mortal_prefers_other": len(rows) - luckyj - naga,
            "mortal_luckyj_rate": pct(luckyj, len(rows)),
            "mortal_naga_rate": pct(naga, len(rows)),
            "avg_mortal_actual_prob": mean([row["mortal_actual_prob"] for row in rows]),
            "avg_mortal_naga_prob": mean([row["mortal_naga_prob"] for row in rows]),
        }

    return {
        "enabled": True,
        "sample_requested": len(candidates),
        "matched": len(matched),
        "missing": len(missing),
        "by_pattern": by_pattern,
        "examples": matched[:60],
    }


def propose_points(summary: dict[str, Any], mortal_summary: dict[str, Any]) -> list[dict[str, Any]]:
    proposals = []
    mortal_patterns = mortal_summary.get("by_pattern", {}) if mortal_summary.get("enabled") else {}

    candidates = [
        ("clean_open_yaku_condition_honor", "Clean yakuhai before an unproven open hand can use it"),
        ("early_guest_honor_cleanup", "Guest honors can be removed before shape when they have no self job"),
        ("keep_self_yakuhai_pair_anchor", "Self yakuhai pairs are route anchors, not ordinary pairs"),
        ("spend_off_target_safety_for_shape", "Safe-looking tiles can be spent when they do not answer the live target"),
        ("late_named_exit_over_shape", "Late safe exits must be named to a live opponent"),
        ("keep_pair_anchor", "Protect pair anchors until the hand declares its route"),
        ("keep_dora_or_red", "Do not spend value seeds just to obey local cleanliness"),
        ("spend_defensive_exit", "Safe-looking tiles can be spent when they are stale or off-target"),
        ("break_pair_anchor", "Break low-purpose pairs before they trap the hand"),
        ("cut_outside_keep_inside", "When the hand has become real, outside safety loses to middle-tile completion"),
        ("behind_risk_buy", "Behind hands buy route/value with danger only when the upside is concrete"),
        ("multi_threat_safe_tenpai", "Against multiple threats, preserved exits become the hand's main asset"),
    ]
    for key, title in candidates:
        stat = summary["patterns"].get(key)
        min_n = 100 if key == "keep_self_yakuhai_pair_anchor" else 250
        if not stat or stat["n"] < min_n:
            continue
        mortal_stat = mortal_patterns.get(key, {})
        proposals.append(
            {
                "pattern": key,
                "title": title,
                "why_candidate": PATTERN_LABELS.get(key, key),
                "naga_evidence": {
                    "n": stat["n"],
                    "share_of_mismatches": stat["share_of_mismatches"],
                    "bad_rate": stat["bad_rate"],
                    "avg_prob_gap": stat["avg_prob_gap"],
                    "avg_danger_delta": stat["avg_danger_delta"],
                    "stage_counts": stat["stage_counts"],
                },
                "mortal_cross_check": mortal_stat or None,
            }
        )
    proposals.sort(
        key=lambda item: (
            (item["mortal_cross_check"] or {}).get("sampled", 0),
            (item["mortal_cross_check"] or {}).get("mortal_luckyj_rate", 0),
            item["naga_evidence"]["n"],
        ),
        reverse=True,
    )
    return proposals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--max-reports", type=int)
    parser.add_argument("--mortal-per-pattern", type=int, default=18)
    parser.add_argument("--mortal-total", type=int, default=180)
    parser.add_argument("--no-mortal", action="store_true")
    parser.add_argument("--log-dir", type=Path, default=mortal.DEFAULT_LOG_DIR)
    parser.add_argument("--model", type=Path, default=mortal.DEFAULT_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    decisions = collect_decisions(args.max_reports)
    summary = summarize_patterns(decisions)
    candidates = [] if args.no_mortal else select_mortal_candidates(decisions, args.mortal_per_pattern, args.mortal_total)
    mortal_summary = {"enabled": False, "reason": "disabled"}
    if not args.no_mortal:
        mortal_summary = compare_mortal(candidates, args.log_dir, args.model)
    output = {
        "meta": {
            "source": "LuckyJ cached NAGA reports plus optional local Mortal/libriichi replay sample",
            "random_seed": RANDOM_SEED,
            "max_reports": args.max_reports,
            "mortal_per_pattern": args.mortal_per_pattern,
            "mortal_total": args.mortal_total,
        },
        "summary": summary,
        "mortal": mortal_summary,
        "candidate_points": propose_points(summary, mortal_summary),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")
    print(json.dumps({"overall": summary["overall"], "mortal": {k: mortal_summary.get(k) for k in ["enabled", "matched", "missing"]}}, indent=2))


if __name__ == "__main__":
    main()
