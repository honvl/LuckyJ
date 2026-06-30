#!/usr/bin/env python3
import json
from collections import Counter, defaultdict
from pathlib import Path

from mahjong.shanten import Shanten

import analyze_luckyj as base


OUT = Path("site/case-studies.json")
SHANTEN = Shanten()
SEAT_NAMES = ["self", "shimocha", "toimen", "kamicha"]


def tile_id(tile):
    return base.IDX[tile]


def rel_seat(seat, target):
    if seat is None:
        return "unknown"
    return SEAT_NAMES[(seat - target) % 4]


def safety_read(tile, target, discards, reached=None, open_melds=None):
    read = base.defensive_tile_read(tile, target, discards, reached, open_melds)
    for item in read["against"]:
        item["seat_label"] = rel_seat(item["seat"], target)
    return read


def retained_safety(tiles, target, discards, reached=None, open_melds=None):
    reads = []
    seen = set()
    for tile in sorted(tiles, key=lambda t: (tile_id(t), t)):
        key = tile_id(tile)
        if key in seen:
            continue
        seen.add(key)
        read = safety_read(tile, target, discards, reached, open_melds)
        if read["kind"]:
            reads.append(read)
    return {
        "total": len(reads),
        "genbutsu": sum(1 for read in reads if read["has_genbutsu"]),
        "suji": sum(1 for read in reads if read["kind"] == "suji"),
        "against_threat": sum(1 for read in reads if read["safe_against_threat"]),
        "tiles": reads[:8],
    }


def counts_34(tiles):
    counts = [0] * 34
    for tile in tiles:
        counts[tile_id(tile)] += 1
    return counts


def remove_tile(hand, tile):
    if tile in hand:
        hand.remove(tile)
        return True
    target = tile_id(tile)
    for item in list(hand):
        if tile_id(item) == target:
            hand.remove(item)
            return True
    return False


def hand_string(tiles):
    return " ".join(sorted(tiles, key=lambda t: (tile_id(t), t)))


def shanten_for(tiles):
    return SHANTEN.calculate_shanten(counts_34(tiles))


def ukeire_after_discard(hand14, discard, public_visible, safety_context=None):
    hand = list(hand14)
    if not remove_tile(hand, discard):
        return None
    base_shanten = shanten_for(hand)
    known = Counter(tile_id(t) for t in hand)
    known.update(public_visible)
    ukeire = 0
    effective = []
    for idx, name in enumerate(base.TILES):
        remaining = max(0, 4 - known[idx])
        if not remaining:
            continue
        trial = hand + [name]
        if shanten_for(trial) < base_shanten:
            ukeire += remaining
            effective.append(name)
    result = {
        "discard": discard,
        "shanten": base_shanten,
        "ukeire": ukeire,
        "effective": effective[:24],
        "hand_after": hand_string(hand),
        "kept_honors": sum(1 for t in hand if base.tile_class(t) == "honor"),
        "kept_terminals": sum(1 for t in hand if base.tile_class(t) == "terminal"),
    }
    if safety_context:
        result["kept_safety"] = retained_safety(hand, *safety_context)
    return result


def danger_for(state, target, tile):
    value = base.danger_for(state, target, tile)
    return round(value, 3) if value is not None else None


def round_name(start):
    wind = {"E": "East", "S": "South", "W": "West", "N": "North"}.get(start.get("bakaze"), start.get("bakaze"))
    return f"{wind} {start.get('kyoku')}-{start.get('honba', 0)}"


def score_band(score):
    if score >= 35000:
        return "lead"
    if score >= 25000:
        return "above starting score"
    if score >= 15000:
        return "behind"
    return "danger zone"


def make_case(row, kyoku_index, pos, start, state, hand14, public_visible, model_rows, label, discards=None, reached=None, open_melds=None):
    actual = state["info"]["msg"]["real_dahai"]
    naga = model_rows[0][0]
    safety_context = (row["actor"], discards, reached, open_melds) if discards is not None else None
    actual_eval = ukeire_after_discard(hand14, actual, public_visible, safety_context)
    naga_eval = ukeire_after_discard(hand14, naga, public_visible, safety_context)
    if not actual_eval or not naga_eval:
        return None
    msg = state["info"]["msg"]
    score = start["scores"][row["actor"]]
    case = {
        "label": label,
        "game": row["idx"],
        "rank": row["rank"],
        "round": round_name(start),
        "kyoku_index": kyoku_index,
        "position": pos,
        "left": msg.get("left_hai_num"),
        "stage": base.stage_from_left(msg.get("left_hai_num")),
        "score": score,
        "score_band": score_band(score),
        "hand": hand_string(hand14),
        "draw": msg.get("pai"),
        "actual": actual,
        "naga": naga,
        "naga_votes": [r[0] for r in model_rows],
        "actual_prob_min": round(min(r[2] for r in model_rows), 3),
        "naga_prob_max": round(max(r[1] for r in model_rows), 3),
        "actual_danger": danger_for(state, row["actor"], actual),
        "naga_danger": danger_for(state, row["actor"], naga),
        "actual_eval": actual_eval,
        "naga_eval": naga_eval,
        "report": row["report"],
        "paifu": row["paifu"],
    }
    if discards is not None:
        case["kept_safety"] = safety_read(naga, row["actor"], discards, reached, open_melds)
    return case


def collect_cases():
    rows = base.parse_rows()
    buckets = defaultdict(list)
    for row in rows:
        target = row["actor"]
        data = base.fetch_report(row["report_id"])
        naga_types = base.normalize_report(data)
        for kyoku_index, kyoku in enumerate(data["pred"]):
            start = kyoku[0].get("info", {}).get("msg", {})
            hands = [list(h) for h in start.get("tehais", [[], [], [], []])]
            open_melds = [0, 0, 0, 0]
            reached = [False, False, False, False]
            discards = [[], [], [], []]
            public_visible = Counter()
            if start.get("dora_marker"):
                public_visible[tile_id(start["dora_marker"])] += 1

            for pos, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")

                if msg_type == "dora" and msg.get("dora_marker"):
                    public_visible[tile_id(msg["dora_marker"])] += 1

                if msg_type == "tsumo":
                    hands[actor].append(msg["pai"])
                    if actor == target and open_melds[target] == 0 and "dahai_pred" in state and msg.get("real_dahai") not in (None, "?") and not msg.get("reached"):
                        actual = msg["real_dahai"]
                        model_rows = []
                        for model_idx in range(min(len(naga_types), len(state["dahai_pred"]))):
                            top, top_prob = base.top_tile(state["dahai_pred"][model_idx])
                            actual_prob = base.prob_for(state["dahai_pred"][model_idx], actual)
                            model_rows.append((top, top_prob, actual_prob))
                        if model_rows and any(top != actual for top, _, _ in model_rows):
                            stage = base.stage_from_left(msg.get("left_hai_num"))
                            actual_cls = base.tile_class(actual)
                            top_classes = [base.tile_class(top) for top, _, _ in model_rows]
                            kept_read = safety_read(model_rows[0][0], target, discards, reached, open_melds)
                            if kept_read["kind"] == "genbutsu":
                                case = make_case(row, kyoku_index, pos, start, state, hands[actor], public_visible, model_rows, "Kept genbutsu tile", discards, reached, open_melds)
                                if case:
                                    buckets["kept_river_safe"].append(case)
                            elif kept_read["kind"] == "suji":
                                case = make_case(row, kyoku_index, pos, start, state, hands[actor], public_visible, model_rows, "Kept suji tile", discards, reached, open_melds)
                                if case:
                                    buckets["kept_suji_exit"].append(case)
                            if stage == "early" and actual_cls == "simple" and all(c in {"honor", "terminal"} for c in top_classes):
                                case = make_case(row, kyoku_index, pos, start, state, hands[actor], public_visible, model_rows, "Early safety hedge", discards, reached, open_melds)
                                if case:
                                    buckets["early_safety_hedge"].append(case)
                            if stage == "middle" and actual_cls == "simple" and all(c in {"honor", "terminal"} for c in top_classes):
                                case = make_case(row, kyoku_index, pos, start, state, hands[actor], public_visible, model_rows, "Middle route hedge", discards, reached, open_melds)
                                if case:
                                    buckets["middle_route_hedge"].append(case)
                            if stage == "late" and actual_cls in {"honor", "terminal"} and all(c == "simple" for c in top_classes):
                                case = make_case(row, kyoku_index, pos, start, state, hands[actor], public_visible, model_rows, "Late tightening", discards, reached, open_melds)
                                if case:
                                    buckets["late_tightening"].append(case)
                            if base.danger_for(state, target, actual) is not None and base.danger_for(state, target, model_rows[0][0]) is not None:
                                actual_d = base.danger_for(state, target, actual)
                                naga_d = base.danger_for(state, target, model_rows[0][0])
                                if actual_d + 0.05 < naga_d:
                                    case = make_case(row, kyoku_index, pos, start, state, hands[actor], public_visible, model_rows, "Safer than Nishiki", discards, reached, open_melds)
                                    if case:
                                        buckets["safer_than_naga"].append(case)
                                elif actual_d > naga_d + 0.05:
                                    case = make_case(row, kyoku_index, pos, start, state, hands[actor], public_visible, model_rows, "Riskier than Nishiki", discards, reached, open_melds)
                                    if case:
                                        buckets["riskier_than_naga"].append(case)
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type in {"chi", "pon", "daiminkan"}:
                    open_melds[actor] += 1
                    for consumed in msg.get("consumed", []):
                        remove_tile(hands[actor], consumed)
                        public_visible[tile_id(consumed)] += 1
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type == "ankan":
                    open_melds[actor] += 1
                    for consumed in msg.get("consumed", []):
                        remove_tile(hands[actor], consumed)
                        public_visible[tile_id(consumed)] += 1

                elif msg_type == "reach":
                    if actor is not None:
                        reached[actor] = True

                elif msg_type == "dahai":
                    tile = msg.get("pai")
                    if actor is not None and tile:
                        discards[actor].append(tile)
                        public_visible[tile_id(tile)] += 1

    # Keep compact, high-signal examples. Prefer large Nishiki confidence gaps, but avoid pathological missing evals.
    selected = {}
    for name, cases in buckets.items():
        cases.sort(
            key=lambda c: (
                c["naga_prob_max"] - c["actual_prob_min"],
                abs(c["naga_eval"]["ukeire"] - c["actual_eval"]["ukeire"]),
            ),
            reverse=True,
        )
        selected[name] = cases[:8]
    return selected


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(collect_cases(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
