#!/usr/bin/env python3
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import analyze_luckyj as base


OUT = Path("site/book-data.json")
SEAT_NAMES = ["self", "shimocha", "toimen", "kamicha"]
WINDS = ["E", "S", "W", "N"]
DRAGONS = {"P", "F", "C"}


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def pct(num, den):
    return 100.0 * num / den if den else 0.0


def tile_id(tile):
    return base.IDX[tile]


def base_tile(tile):
    return str(tile or "").replace("r", "")


def rel_seat(seat, target):
    return SEAT_NAMES[(seat - target) % 4]


def seat_wind(start, seat):
    return WINDS[(seat - start.get("oya", 0)) % 4]


def yakuhai_for_seat(start, seat):
    return DRAGONS | {start.get("bakaze"), seat_wind(start, seat)}


def is_yakuhai_for_seat(tile, start, seat):
    return base_tile(tile) in yakuhai_for_seat(start, seat)


def meld_tiles(meld):
    return [tile for tile in str(meld).split() if tile and tile != "+"]


def meld_shows_yakuhai_contract(meld, start, seat):
    counts = Counter(tile_id(tile) for tile in meld_tiles(meld))
    return any(count >= 3 and is_yakuhai_for_seat(base.TILES[idx], start, seat) for idx, count in counts.items())


def meld_all_simples(meld):
    tiles = meld_tiles(meld)
    return bool(tiles) and all(base.tile_class(tile) == "simple" for tile in tiles)


def open_status_for_seat(start, seat, melds):
    if not melds:
        return None
    if any(meld_shows_yakuhai_contract(meld, start, seat) for meld in melds):
        return "shown_yaku_open"
    if all(meld_all_simples(meld) for meld in melds):
        return "tanyao_shaped_open"
    return "unknown_open_yaku"


def open_context_key(start, target, melds):
    statuses = {
        open_status_for_seat(start, seat, player_melds)
        for seat, player_melds in enumerate(melds)
        if seat != target and player_melds
    }
    if "unknown_open_yaku" in statuses:
        return "unknown_open_yaku"
    if "shown_yaku_open" in statuses:
        return "shown_yaku_open"
    if "tanyao_shaped_open" in statuses:
        return "tanyao_shaped_open"
    return "no_open_hand"


def contract_yakuhai_contexts(start, target, melds, hand):
    contexts = defaultdict(set)
    unique_singletons = []
    seen = set()
    for tile in hand:
        idx = tile_id(tile)
        if idx in seen:
            continue
        seen.add(idx)
        if sum(1 for item in hand if tile_id(item) == idx) == 1:
            unique_singletons.append(tile)

    for seat, player_melds in enumerate(melds):
        if seat == target or not player_melds:
            continue
        status = open_status_for_seat(start, seat, player_melds)
        if not status:
            continue
        for tile in unique_singletons:
            if is_yakuhai_for_seat(tile, start, seat):
                contexts[status].add(tile_id(tile))
    return contexts


def self_yakuhai_singletons(start, target, hand):
    ids = set()
    seen = set()
    for tile in hand:
        idx = tile_id(tile)
        if idx in seen:
            continue
        seen.add(idx)
        if sum(1 for item in hand if tile_id(item) == idx) == 1 and is_yakuhai_for_seat(tile, start, target):
            ids.add(idx)
    return ids


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


def defense_target_class(start, target, read_item):
    seat = read_item["seat"]
    dealer = seat == start.get("oya")
    if read_item.get("reached"):
        return "dealer_riichi" if dealer else "closed_riichi"
    if read_item.get("open_melds"):
        return "dealer_open" if dealer else "nondealer_open"
    if dealer:
        return "dealer_closed"
    return "nondealer_closed"


def add_yakuhai_sample(stats, turns, family, context, actual_id, candidate_ids, own_discards):
    if not candidate_ids:
        return
    key = (family, context)
    stats[key]["opportunities"] += 1
    if own_discards < 6:
        stats[key]["first_row_opportunities"] += 1
    if actual_id in candidate_ids:
        stats[key]["cuts"] += 1
        turns[key].append(own_discards)
        if own_discards < 6:
            stats[key]["first_row_cuts"] += 1


def add_defense_target_sample(targets, stage, target_class, read_item, left):
    for scope in (targets["overall"][target_class], targets["stage"][stage][target_class]):
        scope["instances"] += 1
        if read_item.get("genbutsu_sources"):
            scope["genbutsu"] += 1
        if read_item.get("suji_sources"):
            scope["suji"] += 1
        if left is not None:
            scope["left_sum"] += left
            scope["left_count"] += 1


def summarize_turns(values):
    if not values:
        return {}
    ordered = sorted(values)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return {
        "avg": sum(values) / len(values),
        "median": median,
        "first_row": sum(1 for value in values if value < 6),
    }


def finalize_yakuhai_pressure(stats, turns):
    out = defaultdict(dict)
    for (family, context), counter in stats.items():
        opportunities = counter["opportunities"]
        cuts = counter["cuts"]
        turn_stats = summarize_turns(turns[(family, context)])
        out[family][context] = {
            "opportunities": opportunities,
            "cuts": cuts,
            "cut_rate": cuts / opportunities if opportunities else None,
            "first_row_opportunities": counter["first_row_opportunities"],
            "first_row_opportunity_rate": counter["first_row_opportunities"] / opportunities if opportunities else None,
            "first_row_cuts": counter["first_row_cuts"],
            "first_row_cut_rate": counter["first_row_cuts"] / cuts if cuts else None,
            "avg_cut_turn": turn_stats.get("avg"),
            "median_cut_turn": turn_stats.get("median"),
        }
    return {family: dict(contexts) for family, contexts in out.items()}


def finalize_defense_targets(targets):
    def convert_scope(scope):
        converted = {}
        for key, counter in scope.items():
            instances = counter["instances"]
            converted[key] = {
                "instances": instances,
                "genbutsu": counter["genbutsu"],
                "suji": counter["suji"],
                "genbutsu_rate": counter["genbutsu"] / instances if instances else None,
                "avg_left": counter["left_sum"] / counter["left_count"] if counter["left_count"] else None,
            }
        return converted

    return {
        "overall": convert_scope(targets["overall"]),
        "stage": {stage: convert_scope(scope) for stage, scope in targets["stage"].items()},
    }


def rank_group(rank):
    return "top_half" if rank <= 2 else "bottom_half"


def add_defense_retention(scope, left, read):
    scope["splits"] += 1
    if left is not None:
        scope["left_sum"] += left
        scope["left_count"] += 1
    if not read["kind"]:
        return
    scope["kept_defense_tile"] += 1
    if left is not None:
        scope["kept_left_sum"] += left
        scope["kept_left_count"] += 1
    if read["kind"] == "genbutsu":
        scope["kept_genbutsu"] += 1
    if read["has_suji"]:
        scope["kept_suji"] += 1
    if read["safe_against_threat"]:
        scope["kept_against_live_threat"] += 1
    if read["opponents"] >= 2:
        scope["kept_multi_opponent"] += 1


def update_table_state(msg_type, actor, msg, discards, open_melds, reached):
    if actor is None:
        return
    if msg_type in base.HURO_TYPES:
        open_melds[actor] += 1
    elif msg_type == "reach":
        reached[actor] = True
    elif msg_type == "dahai" and msg.get("pai"):
        discards[actor].append(msg["pai"])


def analyze_decisions(rows):
    counters = {
        "overall": Counter(),
        "stage": defaultdict(Counter),
        "start_rank": defaultdict(Counter),
        "rank_group": defaultdict(Counter),
        "tile_flow": defaultdict(Counter),
        "score_band": defaultdict(Counter),
        "defense_retention": {
            "overall": Counter(),
            "stage": defaultdict(Counter),
            "score_band": defaultdict(Counter),
        },
        "examples": defaultdict(list),
    }

    for row in rows:
        target = row["actor"]
        data = base.fetch_report(row["report_id"])
        naga_types = base.normalize_report(data)
        for kyoku_index, kyoku in enumerate(data["pred"]):
            start = kyoku[0].get("info", {}).get("msg", {})
            discards = [[], [], [], []]
            open_melds = [0, 0, 0, 0]
            reached = [False, False, False, False]
            start_rank = None
            if "seat2rank" in start and target < len(start["seat2rank"]):
                start_rank = start["seat2rank"][target] + 1
            score = start.get("scores", [None] * 4)[target]
            if score is None:
                score_band = "unknown"
            elif score >= 35000:
                score_band = "lead"
            elif score >= 25000:
                score_band = "above_start"
            elif score >= 15000:
                score_band = "behind"
            else:
                score_band = "danger"

            end_msgs = start.get("end_msgs") or []
            delta = base.round_delta(end_msgs, target)
            result = base.round_result(end_msgs, target)

            for pos, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")
                left = msg.get("left_hai_num")
                stage = base.stage_from_left(left)

                if msg_type == "dahai" and "huro" in state and str(target) in state["huro"]:
                    next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
                    actual_called = next_msg.get("actor") == target and next_msg.get("type") in base.HURO_TYPES
                    actual_kind = next_msg.get("kind") if actual_called else 0
                    other_pon = next_msg.get("type") == "pon" and next_msg.get("actor") != target
                    bests = []
                    best_probs = []
                    no_probs = []
                    for opts in state["huro"][str(target)]:
                        opts = {int(k): v / 10000.0 for k, v in opts.items()}
                        best = max(opts, key=lambda k: opts[k])
                        bests.append(best)
                        best_probs.append(opts[best])
                        no_probs.append(opts.get(0, 0.0))
                    key = "call_opportunity"
                    for scope in (counters["overall"], counters["stage"][stage], counters["score_band"][score_band]):
                        scope[key] += 1
                    if actual_called and all(best == 0 for best in bests):
                        for scope in (counters["overall"], counters["stage"][stage], counters["score_band"][score_band]):
                            scope["call_vs_skip"] += 1
                    if not actual_called and not other_pon and any(best != 0 for best in bests):
                        for scope in (counters["overall"], counters["stage"][stage], counters["score_band"][score_band]):
                            scope["skip_vs_call"] += 1
                    if actual_called:
                        for scope in (counters["overall"], counters["stage"][stage], counters["score_band"][score_band]):
                            scope["actual_calls_from_opportunity"] += 1

                if actor == target and "reach" in state:
                    next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
                    actual_reach = next_msg.get("type") == "reach" and next_msg.get("actor") == target
                    model_says_reach = [p / 10000.0 > 0.5 for p in state["reach"]]
                    for scope in (counters["overall"], counters["stage"][stage], counters["score_band"][score_band]):
                        scope["reach_opportunity"] += 1
                    if actual_reach:
                        for scope in (counters["overall"], counters["stage"][stage], counters["score_band"][score_band]):
                            scope["actual_reach"] += 1
                    if actual_reach and not any(model_says_reach):
                        for scope in (counters["overall"], counters["stage"][stage], counters["score_band"][score_band]):
                            scope["reach_vs_no"] += 1
                    if not actual_reach and any(model_says_reach) and next_msg.get("type") != "ankan":
                        for scope in (counters["overall"], counters["stage"][stage], counters["score_band"][score_band]):
                            scope["no_vs_reach"] += 1

                if actor != target or msg_type not in {"tsumo", "chi", "pon"}:
                    update_table_state(msg_type, actor, msg, discards, open_melds, reached)
                    continue
                actual = msg.get("real_dahai")
                if not actual or actual == "?" or msg.get("reached") or "dahai_pred" not in state:
                    update_table_state(msg_type, actor, msg, discards, open_melds, reached)
                    continue

                model_rows = []
                for model_idx in range(min(len(naga_types), len(state["dahai_pred"]))):
                    top, top_prob = base.top_tile(state["dahai_pred"][model_idx])
                    actual_prob = base.prob_for(state["dahai_pred"][model_idx], actual)
                    model_rows.append((top, top_prob, actual_prob, top_prob - actual_prob if top != actual else 0.0))
                if not model_rows:
                    update_table_state(msg_type, actor, msg, discards, open_melds, reached)
                    continue

                mismatch = any(top != actual for top, _, _, _ in model_rows)
                big = mismatch and (mean([diff for *_, diff in model_rows]) or 0) >= 0.5
                bad = mismatch and min(actual_prob for _, _, actual_prob, _ in model_rows) < 0.05
                actual_cls = base.tile_class(actual)
                top_classes = [base.tile_class(top) for top, _, _, _ in model_rows]
                actual_danger = base.danger_for(state, target, actual)
                top_dangers = [base.danger_for(state, target, top) for top, _, _, _ in model_rows]
                top_dangers = [d for d in top_dangers if d is not None]
                top_danger = mean(top_dangers)

                scopes = [
                    counters["overall"],
                    counters["stage"][stage],
                    counters["rank_group"][rank_group(row["rank"])],
                    counters["score_band"][score_band],
                ]
                if start_rank:
                    scopes.append(counters["start_rank"][str(start_rank)])
                for scope in scopes:
                    scope["decisions"] += 1
                    if mismatch:
                        scope["mismatch"] += 1
                    if big:
                        scope["big"] += 1
                    if bad:
                        scope["bad"] += 1
                    if actual_danger is not None and top_danger is not None and mismatch:
                        if actual_danger + 0.05 < top_danger:
                            scope["safer_than_naga"] += 1
                        elif actual_danger > top_danger + 0.05:
                            scope["riskier_than_naga"] += 1
                        else:
                            scope["same_danger"] += 1

                if mismatch:
                    kept_read = base.defensive_tile_read(model_rows[0][0], target, discards, reached, open_melds)
                    for scope in (
                        counters["defense_retention"]["overall"],
                        counters["defense_retention"]["stage"][stage],
                        counters["defense_retention"]["score_band"][score_band],
                    ):
                        add_defense_retention(scope, left, kept_read)

                    if actual_cls == "simple" and all(cls in {"honor", "terminal"} for cls in top_classes):
                        counters["tile_flow"][stage]["kept_outside_cut_simple"] += 1
                    if actual_cls in {"honor", "terminal"} and all(cls == "simple" for cls in top_classes):
                        counters["tile_flow"][stage]["cut_outside_kept_simple"] += 1
                    counters["tile_flow"][stage]["mismatch"] += 1

                    category = "neutral"
                    if actual_danger is not None and top_danger is not None:
                        if actual_danger + 0.05 < top_danger:
                            category = "safer"
                        elif actual_danger > top_danger + 0.05:
                            category = "riskier"
                    outcome = counters["examples"][category]
                    if len(outcome) < 20 and big:
                        outcome.append(
                            {
                                "report": row["report"],
                                "paifu": row["paifu"],
                                "game": row["idx"],
                                "rank": row["rank"],
                                "kyoku_index": kyoku_index,
                                "position": pos,
                                "left": left,
                                "stage": stage,
                                "start_rank": start_rank,
                                "score": score,
                                "actual": actual,
                                "naga": [top for top, _, _, _ in model_rows],
                                "actual_prob_min": min(actual_prob for _, _, actual_prob, _ in model_rows),
                                "top_prob_max": max(top_prob for _, top_prob, _, _ in model_rows),
                                "actual_danger": actual_danger,
                                "naga_danger": top_danger,
                                "round_delta": delta,
                                "won_round": bool(result["win"]),
                                "dealt_in": bool(result["deal_in"]),
                                "kept_safety": kept_read,
                            }
                        )

                update_table_state(msg_type, actor, msg, discards, open_melds, reached)

    return counters


def convert_counter_tree(obj):
    if isinstance(obj, Counter):
        return dict(obj)
    if isinstance(obj, defaultdict):
        return {k: convert_counter_tree(v) for k, v in obj.items()}
    if isinstance(obj, dict):
        return {k: convert_counter_tree(v) for k, v in obj.items()}
    return obj


def analyze_pressure_patterns(rows):
    yakuhai_stats = defaultdict(Counter)
    yakuhai_turns = defaultdict(list)
    defense_targets = {
        "overall": defaultdict(Counter),
        "stage": defaultdict(lambda: defaultdict(Counter)),
    }

    for row in rows:
        target = row["actor"]
        data = base.fetch_report(row["report_id"])
        base.normalize_report(data)
        for kyoku in data["pred"]:
            start = kyoku[0].get("info", {}).get("msg", {})
            hands = [list(hand) for hand in start.get("tehais", [[], [], [], []])]
            discards = [[], [], [], []]
            melds = [[], [], [], []]
            reached = [False, False, False, False]

            for pos, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")

                if msg_type == "tsumo":
                    hands[actor].append(msg["pai"])
                    actual = msg.get("real_dahai")
                    if actor == target and actual and actual != "?" and not msg.get("reached") and "dahai_pred" in state:
                        own_discards = len(discards[target])
                        actual_id = tile_id(actual)
                        context = open_context_key(start, target, melds)
                        add_yakuhai_sample(
                            yakuhai_stats,
                            yakuhai_turns,
                            "self_yakuhai",
                            context,
                            actual_id,
                            self_yakuhai_singletons(start, target, hands[target]),
                            own_discards,
                        )

                        for contract_context, tile_ids in contract_yakuhai_contexts(start, target, melds, hands[target]).items():
                            add_yakuhai_sample(
                                yakuhai_stats,
                                yakuhai_turns,
                                "contract_yakuhai",
                                contract_context,
                                actual_id,
                                tile_ids,
                                own_discards,
                            )

                        top, _ = base.top_tile(state["dahai_pred"][0])
                        if top != actual:
                            left = msg.get("left_hai_num")
                            stage = base.stage_from_left(left)
                            open_counts = [len(player_melds) for player_melds in melds]
                            kept_read = base.defensive_tile_read(top, target, discards, reached, open_counts)
                            for read_item in kept_read["against"]:
                                target_class = defense_target_class(start, target, read_item)
                                add_defense_target_sample(defense_targets, stage, target_class, read_item, left)

                    if actual and actual != "?":
                        remove_tile(hands[actor], actual)

                elif msg_type in base.HURO_TYPES:
                    consumed = msg.get("consumed", [])
                    call_tiles = consumed + ([msg.get("pai")] if msg.get("pai") else [])
                    melds[actor].append(" ".join(call_tiles))
                    for tile in consumed:
                        remove_tile(hands[actor], tile)
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type == "ankan":
                    consumed = msg.get("consumed", [])
                    melds[actor].append(" ".join(consumed))
                    for tile in consumed:
                        remove_tile(hands[actor], tile)

                elif msg_type == "kakan":
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

    return {
        "yakuhai_pressure": finalize_yakuhai_pressure(yakuhai_stats, yakuhai_turns),
        "defense_targets": finalize_defense_targets(defense_targets),
    }


def main():
    rows = base.parse_rows()
    aggregate = json.loads(Path("data/luckyj_analysis.json").read_text(encoding="utf-8"))
    decisions = analyze_decisions(rows)
    pressure_patterns = analyze_pressure_patterns(rows)
    decisions.update(pressure_patterns)
    games = aggregate["game_features"]

    top_half = [g for g in games if g["rank"] <= 2]
    bottom_half = [g for g in games if g["rank"] >= 3]

    book_data = {
        "summary": {
            "games": aggregate["games_analyzed"],
            "hands": aggregate["totals"]["rounds"],
            "decisions": aggregate["totals"]["decision_count"],
            "avg_rank": aggregate["avg_rank"],
            "avg_score": aggregate["avg_score"],
            "rank_counts": aggregate["rank_counts"],
            "win_rate_per_hand": aggregate["totals"]["round_wins"] / aggregate["totals"]["rounds"],
            "deal_in_rate_per_hand": aggregate["totals"]["deal_ins"] / aggregate["totals"]["rounds"],
            "call_round_rate": aggregate["totals"]["call_rounds"] / aggregate["totals"]["rounds"],
            "draw_tenpai_plus_rate": aggregate["totals"]["draw_tenpai_plus"] / aggregate["totals"]["draws"],
            "mismatch_rate": aggregate["totals"]["mismatch_count"] / aggregate["totals"]["decision_count"],
            "bad_rate": aggregate["totals"]["bad_count"] / aggregate["totals"]["decision_count"],
            "big_mismatch_rate": aggregate["totals"]["big_mismatch_count"] / aggregate["totals"]["decision_count"],
        },
        "top_bottom": {
            "top_half": {
                "games": len(top_half),
                "avg_score": mean([g["score"] for g in top_half]),
                "wins_per_game": mean([g["round_wins"] for g in top_half]),
                "deal_ins_per_game": mean([g["deal_ins"] for g in top_half]),
                "riichi_per_game": mean([g["riichi"] for g in top_half]),
                "calls_per_game": mean([g["calls"] for g in top_half]),
            },
            "bottom_half": {
                "games": len(bottom_half),
                "avg_score": mean([g["score"] for g in bottom_half]),
                "wins_per_game": mean([g["round_wins"] for g in bottom_half]),
                "deal_ins_per_game": mean([g["deal_ins"] for g in bottom_half]),
                "riichi_per_game": mean([g["riichi"] for g in bottom_half]),
                "calls_per_game": mean([g["calls"] for g in bottom_half]),
            },
        },
        "decision_counters": convert_counter_tree(decisions),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(book_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
