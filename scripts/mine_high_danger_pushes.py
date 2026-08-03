#!/usr/bin/env python3
"""Audit LuckyJ's voluntary nondealer discards at extreme NAGA danger levels."""

import argparse
import json
from collections import Counter
from pathlib import Path

import analyze_luckyj as base
import build_point_examples as points


OUT_PATH = Path("data/nondealer_high_danger_pushes.json")
THRESHOLD = 0.90
EXAMPLE_CATEGORIES = {
    (401, 10, 32): "high_value_tenpai",
    (910, 5, 38): "fourth_place_one_shanten",
    (1173, 2, 25): "riichi_declaration",
    (1031, 3, 39): "valuable_open_tenpai",
    (1043, 2, 26): "three_call_inventory_trap",
    (1020, 4, 5): "engine_rejected_overpush",
}


def outcome_bucket(outcome):
    if outcome.startswith("self won"):
        return "self_win"
    if outcome.startswith("self dealt"):
        return "direct_deal_in"
    if outcome.startswith("draw"):
        return "draw"
    return "other_player_win"


def wall_bucket(left):
    if left > 40:
        return "over_40"
    if left > 20:
        return "21_to_40"
    if left > 12:
        return "13_to_20"
    return "12_or_fewer"


def open_meld_count(melds):
    return sum(meld.get("kind") in base.HURO_TYPES for meld in melds)


def eval_after_discard(hand, discard, discards, melds, dora_markers):
    try:
        visible = points.visible_counter(discards, melds, dora_markers)
        value = points.ukeire_after_discard(hand, discard, visible)
    except (KeyError, ValueError):
        return None
    if not value:
        return None
    return {
        "shanten": value.get("shanten"),
        "ukeire": value.get("ukeire"),
        "effective": value.get("effective") or [],
    }


def decision_row(row, kyoku_index, position, start, state, hands, discards, melds, reached, dora_markers, next_msg):
    target = row["actor"]
    msg = state.get("info", {}).get("msg", {})
    actual = msg.get("real_dahai")
    actual_danger = points.discard_threat_value(state, target, actual)
    if actual_danger is None or actual_danger < THRESHOLD:
        return None

    models = points.model_rows(state, actual)
    nishiki = models[0] if models else None
    nishiki_tile = nishiki.get("top") if nishiki else None
    own_open_melds = open_meld_count(melds[target])
    opponent_reaches = sum(bool(reached[seat]) for seat in range(4) if seat != target)
    outcome = points.end_summary(start, target)

    result = {
        "game": row["idx"],
        "round_index": kyoku_index,
        "position": position,
        "round": points.round_name(start),
        "dealer": False,
        "rank": points.current_rank(start, target),
        "score": start.get("scores", [0, 0, 0, 0])[target],
        "wall_tiles_left": msg.get("left_hai_num"),
        "hand": points.hand_string(hands[target]),
        "draw": msg.get("pai"),
        "discard": actual,
        "danger_proxy": actual_danger,
        "after_discard": eval_after_discard(hands[target], actual, discards, melds, dora_markers),
        "open_melds": own_open_melds,
        "opponent_riichi_count": opponent_reaches,
        "declares_riichi": next_msg.get("type") == "reach" and next_msg.get("actor") == target,
        "model_support_count": sum(model.get("matches_luckyj", False) for model in models),
        "model_heads": [
            {
                "key": model.get("key"),
                "top": model.get("top"),
                "supports_luckyj": model.get("matches_luckyj", False),
            }
            for model in models
        ],
        "nishiki": {
            "discard": nishiki_tile,
            "danger_proxy": points.discard_threat_value(state, target, nishiki_tile) if nishiki_tile else None,
            "after_discard": eval_after_discard(hands[target], nishiki_tile, discards, melds, dora_markers) if nishiki_tile else None,
        },
        "outcome": outcome,
        "outcome_bucket": outcome_bucket(outcome),
        "replay": row.get("paifu"),
        "report": row.get("report"),
    }
    category = EXAMPLE_CATEGORIES.get((row["idx"], kyoku_index, msg.get("left_hai_num")))
    if category:
        result["example_category"] = category
    return result


def collect_decisions():
    decisions = []
    for row in base.parse_rows():
        if row.get("room") != "Tokujou":
            continue
        target = row["actor"]
        data = base.fetch_report(row["report_id"])
        base.normalize_report(data)

        for kyoku_index, kyoku in enumerate(data["pred"]):
            start = kyoku[0].get("info", {}).get("msg", {})
            if start.get("oya") == target:
                continue

            hands = [list(hand) for hand in start.get("tehais", [[], [], [], []])]
            discards = [[], [], [], []]
            melds = [[], [], [], []]
            reached = [False, False, False, False]
            dora_markers = [start["dora_marker"]] if start.get("dora_marker") else []

            for position, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")

                if msg_type == "dora" and msg.get("dora_marker"):
                    dora_markers.append(msg["dora_marker"])

                if msg_type == "tsumo":
                    hands[actor].append(msg["pai"])
                    if (
                        actor == target
                        and not reached[target]
                        and "dahai_pred" in state
                        and msg.get("real_dahai") not in (None, "?")
                    ):
                        next_msg = kyoku[position + 1].get("info", {}).get("msg", {}) if position + 1 < len(kyoku) else {}
                        decision = decision_row(
                            row,
                            kyoku_index,
                            position,
                            start,
                            state,
                            hands,
                            discards,
                            melds,
                            reached,
                            dora_markers,
                            next_msg,
                        )
                        if decision:
                            decisions.append(decision)
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        points.remove_tile(hands[actor], discard)

                elif msg_type in base.HURO_TYPES:
                    consumed = msg.get("consumed", [])
                    call_tiles = consumed + ([msg.get("pai")] if msg.get("pai") else [])
                    melds[actor].append(
                        points.make_meld(call_tiles, msg.get("pai"), points.rel_seat(msg.get("target"), actor), msg_type)
                    )
                    for tile in consumed:
                        points.remove_tile(hands[actor], tile)
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        points.remove_tile(hands[actor], discard)

                elif msg_type == "ankan":
                    consumed = msg.get("consumed", [])
                    melds[actor].append(points.make_meld(consumed, kind=msg_type))
                    for tile in consumed:
                        points.remove_tile(hands[actor], tile)

                elif msg_type == "kakan":
                    tile = msg.get("pai")
                    if tile:
                        melds[actor].append(points.make_meld([tile], kind=msg_type))
                        points.remove_tile(hands[actor], tile)

                elif msg_type == "reach" and actor is not None:
                    reached[actor] = True

                elif msg_type == "dahai" and actor is not None and msg.get("pai"):
                    discards[actor].append(msg["pai"])

    return decisions


def counter_dict(values, keys):
    counts = Counter(values)
    return {key: counts.get(key, 0) for key in keys}


def build_output(decisions):
    shanten = Counter((decision.get("after_discard") or {}).get("shanten") for decision in decisions)
    summary = {
        "decisions": len(decisions),
        "capped_at_99_99": sum(decision["danger_proxy"] >= 0.9999 for decision in decisions),
        "shanten": {
            "tenpai": shanten.get(0, 0),
            "one_shanten": shanten.get(1, 0),
            "two_or_more_shanten": sum(count for value, count in shanten.items() if value is not None and value >= 2),
        },
        "hand_state": {
            "closed": sum(decision["open_melds"] == 0 for decision in decisions),
            "open": sum(decision["open_melds"] > 0 for decision in decisions),
            "open_meld_counts": counter_dict((str(decision["open_melds"]) for decision in decisions), ["0", "1", "2", "3"]),
        },
        "declares_riichi": sum(decision["declares_riichi"] for decision in decisions),
        "against_at_least_one_riichi": sum(decision["opponent_riichi_count"] > 0 for decision in decisions),
        "supported_by_at_least_two_naga_heads": sum(decision["model_support_count"] >= 2 for decision in decisions),
        "rank": counter_dict((str(decision["rank"]) for decision in decisions), ["1", "2", "3", "4"]),
        "wall": counter_dict((wall_bucket(decision["wall_tiles_left"]) for decision in decisions), ["over_40", "21_to_40", "13_to_20", "12_or_fewer"]),
        "outcomes": counter_dict((decision["outcome_bucket"] for decision in decisions), ["self_win", "direct_deal_in", "other_player_win", "draw"]),
    }
    examples = [decision for decision in decisions if decision.get("example_category")]
    examples.sort(key=lambda decision: list(EXAMPLE_CATEGORIES.values()).index(decision["example_category"]))
    return {
        "methodology": {
            "room": "Tokujou",
            "unit": "decision states",
            "danger_metric": "maximum NAGA danger proxy across the three NAGA heads",
            "threshold": THRESHOLD,
            "luckyj_dealer_states": "excluded",
            "post_luckyj_riichi_locked_discards": "excluded",
            "riichi_declaration_discards": "included because the discard is chosen before the lock",
            "note": "Repeated 0.9999 readings behave like a capped alarm state, not a calibrated 99.99% deal-in probability.",
        },
        "summary": summary,
        "examples": examples,
        "decisions": decisions,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT_PATH)
    args = parser.parse_args()
    output = build_output(collect_decisions())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}; decisions={output['summary']['decisions']} examples={len(output['examples'])}")


if __name__ == "__main__":
    main()
