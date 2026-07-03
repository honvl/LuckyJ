#!/usr/bin/env python3
"""Mine prescriptive riichi declaration and late-game/keiten thresholds for LuckyJ."""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from mahjong.shanten import Shanten

import analyze_luckyj as base
from extract_case_studies import counts_34, remove_tile

OUT = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx-riichi.json")
SHANTEN = Shanten()
DANGER_KEYS = ("danger_s", "danger_t", "danger_k")
OPEN_CALL_TYPES = {"chi", "pon", "daiminkan"}
TARGET_DECISION_TYPES = {"tsumo", "chi", "pon", "daiminkan"}


def pct(num, den):
    return round(100.0 * num / den, 1) if den else None


def rate_stat(n, yes, yes_name="yes"):
    return {
        "n": n,
        yes_name: yes,
        f"{yes_name}_rate_pct": pct(yes, n),
    }


def mean(values):
    values = [v for v in values if v is not None and not math.isnan(v)]
    return round(sum(values) / len(values), 4) if values else None


def tile_id(tile):
    return base.IDX[tile]


def add_visible(counter, tile):
    if tile in (None, "?"):
        return
    try:
        if isinstance(tile, int):
            # Report end messages sometimes use 136 IDs; live dora messages are strings.
            if 0 <= tile < 34:
                counter[tile] += 1
            elif 0 <= tile < 136:
                counter[tile // 4] += 1
        else:
            counter[tile_id(tile)] += 1
    except (KeyError, TypeError):
        return


def shanten_value(tiles, regular_only=False):
    try:
        if regular_only:
            return SHANTEN.calculate_shanten(counts_34(tiles), use_chiitoitsu=False, use_kokushi=False)
        return SHANTEN.calculate_shanten(counts_34(tiles))
    except Exception:
        return None


def hand_after_decision(hand_before, msg):
    """Return concealed tiles after LuckyJ's actual discard for this state."""
    discard = msg.get("real_dahai")
    if not discard or discard == "?":
        return None
    hand = list(hand_before)
    if msg.get("type") in OPEN_CALL_TYPES:
        for tile in msg.get("consumed") or []:
            remove_tile(hand, tile)
    if not remove_tile(hand, discard):
        # Logs occasionally normalize red fives differently; remove by 34-id as a fallback.
        return None
    return hand


def wait_info_after_discard(hand14, discard, public_visible):
    """Compute winning tile types and unseen copies after discarding from a riichi-able hand."""
    hand = list(hand14)
    if not discard or discard == "?" or not remove_tile(hand, discard):
        return {"wait_tiles_remaining": None, "wait_types": [], "winning_tiles": []}
    hand_shanten = shanten_value(hand)
    known = Counter(public_visible)
    for tile in hand:
        add_visible(known, tile)

    winning = []
    remaining_total = 0
    for idx, tile in enumerate(base.TILES):
        remaining = max(0, 4 - known[idx])
        if remaining <= 0:
            continue
        if shanten_value(hand + [tile]) == -1:
            winning.append({"tile": tile, "remaining": remaining})
            remaining_total += remaining

    return {
        "wait_tiles_remaining": remaining_total,
        "wait_types": len(winning),
        "winning_tiles": winning,
        "post_discard_shanten": hand_shanten,
    }


def wait_bucket(wait_remaining):
    if wait_remaining is None:
        return "unknown"
    if wait_remaining <= 3:
        return "<=3_bad"
    if wait_remaining <= 7:
        return "4-7"
    return "8+"


def first_turn_bucket(turn):
    if turn is None:
        return "unknown"
    if turn <= 6:
        return "<=6"
    if turn <= 11:
        return "7-11"
    return "12+"


def first_left_bucket(left):
    if left is None:
        return "unknown"
    return "<=20" if left <= 20 else ">20"


def keiten_left_bucket(left):
    if left is None:
        return "unknown"
    if 11 <= left <= 20:
        return "20-11"
    if 6 <= left <= 10:
        return "10-6"
    if 0 <= left <= 5:
        return "5-0"
    return "outside_scope"


def shanten_bucket(shanten):
    if shanten is None:
        return "unknown"
    if shanten <= 0:
        return "0"
    if shanten == 1:
        return "1"
    return "2+"


def shanten_bucket_exact(shanten):
    if shanten is None:
        return "unknown"
    if shanten <= 0:
        return "0"
    return str(shanten)


def score_position_bucket(start, target):
    scores = start.get("scores") or []
    seat2rank = start.get("seat2rank") or []
    if target >= len(scores):
        return "unknown"
    rank = None
    if target < len(seat2rank):
        try:
            rank = int(seat2rank[target]) + 1
        except Exception:
            rank = None
    if rank is None:
        return "unknown"
    if rank == 1:
        others = [score for seat, score in enumerate(scores) if seat != target]
        lead = scores[target] - max(others) if others else 0
        return "rank1_10k+_lead" if lead >= 10000 else "rank1_small_lead"
    if rank in (2, 3):
        return "rank2-3"
    if rank == 4:
        return "rank4"
    return "unknown"


def threat_flags(target, reached, open_melds):
    opp_riichi = any(seat != target and reached[seat] for seat in range(4))
    open_2meld = any(seat != target and open_melds[seat] >= 2 for seat in range(4))
    return opp_riichi, open_2meld


def threat_bucket(target, reached, open_melds):
    opp_riichi, open_2meld = threat_flags(target, reached, open_melds)
    if opp_riichi:
        return "riichi"
    if open_2meld:
        return "open_2meld"
    return "none"


def threat_combo_bucket(target, reached, open_melds):
    opp_riichi, open_2meld = threat_flags(target, reached, open_melds)
    if opp_riichi and open_2meld:
        return "riichi+open_2meld"
    if opp_riichi:
        return "opp_riichi"
    if open_2meld:
        return "open_2meld"
    return "none"


def threat_seats(target, reached, open_melds):
    return [
        seat
        for seat in range(4)
        if seat != target and (reached[seat] or open_melds[seat] >= 2)
    ]


def danger_for_tile(state, target, tile, seats=None):
    if not tile or tile == "?":
        return None
    try:
        idx = tile_id(tile)
    except KeyError:
        return None
    vals = []
    for key in DANGER_KEYS:
        danger = state.get(key)
        if not danger:
            continue
        iterable = seats if seats is not None else range(len(danger))
        for seat in iterable:
            if seat == target or seat is None or seat >= len(danger):
                continue
            arr = danger[seat]
            if arr is not None and idx < len(arr):
                vals.append(arr[idx] / 10000.0)
    return max(vals) if vals else None


def add_rate_bucket(table, key, declared):
    bucket = table[key]
    bucket["n"] += 1
    bucket["declares"] += int(bool(declared))


def finalize_rate_table(table):
    return {
        key: {
            "n": val["n"],
            "declares": val["declares"],
            "declare_rate_pct": pct(val["declares"], val["n"]),
        }
        for key, val in sorted(table.items())
    }


def add_keiten_bucket(table, key, danger):
    bucket = table[key]
    bucket["n"] += 1
    if danger is not None:
        bucket["danger_known_n"] += 1
        bucket["danger_sum"] += danger
        bucket["push_>5pct"] += int(danger > 0.05)


def finalize_keiten_table(table):
    out = {}
    for key, val in sorted(table.items()):
        known = val["danger_known_n"]
        out[key] = {
            "n": val["n"],
            "danger_known_n": known,
            "mean_actual_discard_danger": round(val["danger_sum"] / known, 4) if known else None,
            "push_>5pct": val["push_>5pct"],
            "push_>5pct_rate_pct": pct(val["push_>5pct"], known),
        }
    return out


def update_public_and_hands_after_state(msg, actor, msg_type, hands, discards, public_visible, reached, open_melds, melds):
    if msg_type in OPEN_CALL_TYPES:
        call_tiles = list(msg.get("consumed") or [])
        if msg.get("pai"):
            call_tiles.append(msg.get("pai"))
        if actor is not None and 0 <= actor < 4:
            melds[actor].append(call_tiles)
            open_melds[actor] += 1
            for tile in msg.get("consumed") or []:
                remove_tile(hands[actor], tile)
                add_visible(public_visible, tile)
            discard = msg.get("real_dahai")
            if discard and discard != "?":
                remove_tile(hands[actor], discard)
        return

    if msg_type == "ankan":
        if actor is not None and 0 <= actor < 4:
            consumed = list(msg.get("consumed") or [])
            melds[actor].append(consumed)
            for tile in consumed:
                remove_tile(hands[actor], tile)
                add_visible(public_visible, tile)
        return

    if msg_type == "kakan":
        if actor is not None and 0 <= actor < 4:
            tile = msg.get("pai")
            if tile:
                melds[actor].append([tile])
                remove_tile(hands[actor], tile)
                add_visible(public_visible, tile)
        return

    if msg_type == "reach":
        if actor is not None and 0 <= actor < 4:
            reached[actor] = True
        return

    if msg_type == "dahai":
        tile = msg.get("pai")
        if actor is not None and 0 <= actor < 4 and tile:
            discards[actor].append(tile)
            add_visible(public_visible, tile)
        return


def summarize_declined(outcome_counts):
    n = outcome_counts["n"]
    return {
        "n": n,
        "later_declared": outcome_counts["later_declared"],
        "later_declared_rate_pct": pct(outcome_counts["later_declared"], n),
        "stayed_damaten_to_end": outcome_counts["stayed_damaten_to_end"],
        "stayed_damaten_to_end_rate_pct": pct(outcome_counts["stayed_damaten_to_end"], n),
        "fold_or_broke_tenpai": outcome_counts["fold_or_broke_tenpai"],
        "fold_or_broke_tenpai_rate_pct": pct(outcome_counts["fold_or_broke_tenpai"], n),
    }


def get_rate(result, *path):
    cur = result
    for key in path:
        cur = cur.get(key, {}) if isinstance(cur, dict) else {}
    return cur if isinstance(cur, dict) else {}


def fmt_rate(bucket, numerator="declares"):
    n = bucket.get("n") or bucket.get("danger_known_n") or 0
    rate_key = "declare_rate_pct" if numerator == "declares" else "push_>5pct_rate_pct"
    return f"{bucket.get(rate_key)}% (n={n})"


def build_proposed_rules(result):
    rules = []
    wait = result["riichi_first_opportunity"]["splits"]["wait_tiles_remaining"]
    turn = result["riichi_first_opportunity"]["splits"]["turn_bucket"]
    score = result["riichi_first_opportunity"]["splits"]["score_position"]
    threat = result["riichi_first_opportunity"]["splits"]["threat"]
    cross_wait_score = result["riichi_first_opportunity"]["cross_tabs"]["wait_tiles_remaining_x_score_position"]
    keiten = result["late_game_keiten_push"]["buckets"]
    declined = result["declined_then_what"]
    fold = result["fold_commitment"]
    bonus = result["riichi_declaration_tile_safety"]

    if "8+" in wait:
        rules.append(f"Declare immediately on 8+ unseen waits: LuckyJ did so {fmt_rate(wait['8+'])}.")
    if "<=3_bad" in wait:
        rules.append(f"Treat <=3 unseen waits as the main damaten zone: first-chance riichi only {fmt_rate(wait['<=3_bad'])}.")
    big_lead_bad = cross_wait_score.get("<=3_bad|rank1_10k+_lead")
    if big_lead_bad and big_lead_bad.get("n", 0) >= 5:
        rules.append(f"With a bad wait and a 10k+ first-place lead, bias damaten: declare {fmt_rate(big_lead_bad)}.")
    if "12+" in turn:
        rules.append(f"Late riichi is still live: on turn 12+ LuckyJ declared {fmt_rate(turn['12+'])} when first offered.")
    if "riichi" in threat:
        rules.append(f"Oikake is selective, not forbidden: into an existing riichi/open threat bucket, first-chance declare rate was {fmt_rate(threat['riichi'])}.")
    if declined.get("n"):
        rules.append(
            "If the first riichi is declined, expect damaten more than a delayed stick: "
            f"later riichi {declined['later_declared_rate_pct']}%, stayed damaten {declined['stayed_damaten_to_end_rate_pct']}%, "
            f"broke/folded {declined['fold_or_broke_tenpai_rate_pct']}% (n={declined['n']})."
        )
    # Pick a late 2+ shanten under riichi bucket if present.
    for key in ("2+|5-0|riichi", "2+|10-6|riichi", "2+|20-11|riichi"):
        bucket = keiten.get(key)
        if bucket and bucket.get("danger_known_n", 0) >= 10:
            rules.append(
                f"For late keiten, 2+ shanten under riichi stops pushing: {key} pushed >5% danger "
                f"{bucket['push_>5pct_rate_pct']}% (n={bucket['danger_known_n']})."
            )
            break
    if fold.get("n"):
        stay = round(100.0 - (fold.get("later_push_>5pct_rate_pct") or 0.0), 1)
        rules.append(
            f"Once LuckyJ folds with two <1% tiles while 2+ shanten under riichi, it stays folded {stay}% of the time "
            f"(later >5% push {fold.get('later_push_>5pct_rate_pct')}%, n={fold.get('n')})."
        )
    if bonus.get("declares_with_existing_threat_danger_known_n"):
        rules.append(
            f"When LuckyJ declares into an existing threat, the stick tile itself is >10% danger "
            f"{bonus.get('danger_>10pct_vs_threat_rate_pct')}% of the time "
            f"(n={bonus.get('declares_with_existing_threat_danger_known_n')})."
        )
    return rules[:8]


def analyze():
    rows = base.parse_rows()
    result_meta = {
        "rows_seen": len(rows),
        "unique_report_ids_seen": len({row["report_id"] for row in rows}),
        "reports_processed": 0,
        "kyoku_seen": 0,
        "errors": [],
    }

    first_overall = Counter()
    first_splits = {
        "wait_tiles_remaining": defaultdict(Counter),
        "turn_bucket": defaultdict(Counter),
        "tiles_left": defaultdict(Counter),
        "score_position": defaultdict(Counter),
        "dealer": defaultdict(Counter),
        "threat": defaultdict(Counter),
        "opponent_riichi_present": defaultdict(Counter),
        "open_2meld_present": defaultdict(Counter),
    }
    first_cross = {
        "wait_tiles_remaining_x_turn_bucket": defaultdict(Counter),
        "wait_tiles_remaining_x_score_position": defaultdict(Counter),
        "wait_tiles_remaining_x_threat": defaultdict(Counter),
    }
    declined_outcomes = Counter()
    keiten_buckets = defaultdict(Counter)
    fold_commitments = []
    bonus = Counter()

    for row_idx, row in enumerate(rows, 1):
        if row_idx % 200 == 0:
            print(f"processed {row_idx}/{len(rows)} rows", file=sys.stderr, flush=True)
        target = row.get("actor")
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
            result_meta["reports_processed"] += 1
        except Exception as exc:
            result_meta["errors"].append({"report_id": row.get("report_id"), "error": repr(exc)})
            continue

        for kyoku_index, kyoku in enumerate(data.get("pred") or []):
            if not kyoku:
                continue
            result_meta["kyoku_seen"] += 1
            start = kyoku[0].get("info", {}).get("msg", {})
            tehais = start.get("tehais") or [[], [], [], []]
            if len(tehais) < 4:
                continue
            hands = [list(tehais[seat]) for seat in range(4)]
            discards = [[], [], [], []]
            reached = [False, False, False, False]
            # Report start sometimes carries already-reached state for continuations; honor it if present.
            for seat, value in enumerate(start.get("reached") or []):
                if seat < 4:
                    reached[seat] = bool(value)
            open_melds = [0, 0, 0, 0]
            melds = [[], [], [], []]
            public_visible = Counter()
            add_visible(public_visible, start.get("dora_marker"))

            reach_opps = []
            target_decisions = []
            fold_consec = 0
            fold_committed = False
            fold_record = None

            for pos, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")

                if msg_type == "dora":
                    add_visible(public_visible, msg.get("dora_marker"))

                # Draw first, so the decision helpers see the 14-tile hand.
                if msg_type == "tsumo" and actor is not None and 0 <= actor < 4:
                    pai = msg.get("pai")
                    if pai:
                        hands[actor].append(pai)

                if actor == target and msg_type in TARGET_DECISION_TYPES:
                    actual = msg.get("real_dahai")
                    if actual and actual != "?":
                        after = hand_after_decision(hands[actor], msg)
                        regular_shanten = shanten_value(after, regular_only=True) if after is not None else None
                        full_shanten = shanten_value(after) if after is not None else None
                        danger = danger_for_tile(state, target, actual)
                        left = msg.get("left_hai_num")
                        decision = {
                            "pos": pos,
                            "left": left,
                            "actual": actual,
                            "danger": danger,
                            "regular_shanten": regular_shanten,
                            "full_shanten": full_shanten,
                            "under_riichi": any(seat != target and reached[seat] for seat in range(4)),
                        }
                        target_decisions.append(decision)

                        # Late-game keiten push table.
                        if left is not None and left <= 20 and not reached[target] and not msg.get("reached"):
                            s_bucket = shanten_bucket(regular_shanten)
                            l_bucket = keiten_left_bucket(left)
                            t_bucket = threat_bucket(target, reached, open_melds)
                            if l_bucket != "outside_scope":
                                add_keiten_bucket(keiten_buckets, f"{s_bucket}|{l_bucket}|{t_bucket}", danger)

                        # Fold commitment detector.
                        if not reached[target] and decision["under_riichi"] and regular_shanten is not None:
                            if not fold_committed:
                                if regular_shanten >= 2 and danger is not None and danger < 0.01:
                                    fold_consec += 1
                                else:
                                    fold_consec = 0
                                if fold_consec >= 2:
                                    fold_committed = True
                                    fold_record = {
                                        "game": row.get("idx"),
                                        "report_id": row.get("report_id"),
                                        "kyoku_index": kyoku_index,
                                        "commit_pos": pos,
                                        "later_push_>5pct": False,
                                        "later_discards_known_n": 0,
                                    }
                            else:
                                if danger is not None:
                                    fold_record["later_discards_known_n"] += 1
                                    if danger > 0.05:
                                        fold_record["later_push_>5pct"] = True

                # Riichi opportunity detection: LuckyJ tsumo state with reach probabilities.
                if actor == target and "reach" in state:
                    actual = msg.get("real_dahai")
                    next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
                    declared = next_msg.get("type") == "reach" and next_msg.get("actor") == target
                    turn = len(discards[target]) + 1
                    left = msg.get("left_hai_num")
                    w_info = wait_info_after_discard(hands[actor], actual, public_visible)
                    w_bucket = wait_bucket(w_info.get("wait_tiles_remaining"))
                    t_bucket = first_turn_bucket(turn)
                    l_bucket = first_left_bucket(left)
                    score_bucket = score_position_bucket(start, target)
                    dealer_bucket = "dealer" if start.get("oya") == target else "nondealer"
                    threat_combo = threat_combo_bucket(target, reached, open_melds)
                    opp_riichi, open_2meld = threat_flags(target, reached, open_melds)
                    opp_riichi_bucket = "yes" if opp_riichi else "no"
                    open_2meld_bucket = "yes" if open_2meld else "no"

                    opp = {
                        "pos": pos,
                        "declared": declared,
                        "turn": turn,
                        "left": left,
                        "wait_tiles_remaining": w_info.get("wait_tiles_remaining"),
                        "wait_types": w_info.get("wait_types"),
                        "wait_bucket": w_bucket,
                        "turn_bucket": t_bucket,
                        "tiles_left_bucket": l_bucket,
                        "score_position": score_bucket,
                        "dealer": dealer_bucket,
                        "threat": threat_combo,
                        "opponent_riichi_present": opp_riichi_bucket,
                        "open_2meld_present": open_2meld_bucket,
                        "actual": actual,
                        "danger_vs_any": danger_for_tile(state, target, actual),
                    }
                    reach_opps.append(opp)

                    # Bonus: all actual declarations, not just first opportunities.
                    if declared:
                        bonus["declares"] += 1
                        seats = threat_seats(target, reached, open_melds)
                        if seats:
                            bonus["declares_with_existing_threat"] += 1
                            d_threat = danger_for_tile(state, target, actual, seats=seats)
                            if d_threat is not None:
                                bonus["declares_with_existing_threat_danger_known_n"] += 1
                                bonus["declares_with_existing_threat_danger_sum"] += d_threat
                                if d_threat > 0.10:
                                    bonus["danger_>10pct_vs_threat"] += 1

                # Now mutate the replay state after all analyses at this state.
                if msg_type == "tsumo" and actor is not None and 0 <= actor < 4:
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)
                else:
                    update_public_and_hands_after_state(
                        msg, actor, msg_type, hands, discards, public_visible, reached, open_melds, melds
                    )

            if fold_record is not None:
                fold_commitments.append(fold_record)

            if reach_opps:
                first = reach_opps[0]
                declared = first["declared"]
                first_overall["n"] += 1
                first_overall["declares"] += int(declared)
                split_keys = {
                    "wait_tiles_remaining": "wait_bucket",
                    "turn_bucket": "turn_bucket",
                    "tiles_left": "tiles_left_bucket",
                    "score_position": "score_position",
                    "dealer": "dealer",
                    "threat": "threat",
                    "opponent_riichi_present": "opponent_riichi_present",
                    "open_2meld_present": "open_2meld_present",
                }
                for split_name, opp_key in split_keys.items():
                    add_rate_bucket(first_splits[split_name], first[opp_key], declared)
                add_rate_bucket(first_cross["wait_tiles_remaining_x_turn_bucket"], f"{first['wait_bucket']}|{first['turn_bucket']}", declared)
                add_rate_bucket(first_cross["wait_tiles_remaining_x_score_position"], f"{first['wait_bucket']}|{first['score_position']}", declared)
                add_rate_bucket(first_cross["wait_tiles_remaining_x_threat"], f"{first['wait_bucket']}|{first['threat']}", declared)

                if not declared:
                    declined_outcomes["n"] += 1
                    later_declared = any(opp["declared"] for opp in reach_opps[1:])
                    if later_declared:
                        declined_outcomes["later_declared"] += 1
                    else:
                        later_decisions = [d for d in target_decisions if d["pos"] > first["pos"]]
                        broke = any((d.get("full_shanten") is not None and d["full_shanten"] >= 1) for d in later_decisions)
                        if broke:
                            declined_outcomes["fold_or_broke_tenpai"] += 1
                        else:
                            declined_outcomes["stayed_damaten_to_end"] += 1

    fold_n = len(fold_commitments)
    fold_push = sum(1 for rec in fold_commitments if rec["later_push_>5pct"])

    result = {
        "definitions": {
            "source": "data/report_cache/*.json.gz via scripts/analyze_luckyj.py parse_rows/fetch_report/normalize_report",
            "riichi_opportunity": "LuckyJ tsumo state containing state['reach']; declaration iff next state's msg is type='reach' with actor==LuckyJ.",
            "first_opportunity": "First riichi opportunity per LuckyJ kyoku only.",
            "wait_tiles_remaining": "After LuckyJ's actual real_dahai from the 14-tile hand, winning tile types are tiles that make shanten -1; remaining copies are 4 minus own post-discard hand, all rivers, called/kan tiles, and dora indicators visible so far.",
            "turn": "len(discards[LuckyJ]) + 1 before LuckyJ's discard.",
            "score_position": "Start-of-kyoku scores and seat2rank; rank1_10k+_lead means first place leads second by at least 10,000.",
            "threat": "For riichi first-opportunity splits, threat is none/opponent riichi/open 2+ meld/both. For keiten buckets, riichi takes priority over open_2meld.",
            "danger": "Max danger_s/danger_t/danger_k over opponent seats for LuckyJ's actual discard, scaled /10000. Bonus declaration safety restricts opponent seats to existing riichi or open-2meld threats.",
            "keiten_shanten": "Regular-hand shanten of LuckyJ's concealed tiles after the actual discard, with open melds inferred by tile count; bucketed as 0/1/2+.",
            "keiten_push": "A late-game decision with left_hai_num <= 20; push means actual discard danger > 5%.",
            "fold_commitment": "Per kyoku, first time LuckyJ makes two consecutive target discards under an opponent riichi, both 2+ regular shanten after discard and each <1% danger; later push means a subsequent LuckyJ discard in that kyoku is >5% danger.",
            "declined_fold_or_broke_tenpai": "After declining first riichi and never declaring later, any later LuckyJ discard that leaves full closed shanten >=1.",
        },
        "meta": result_meta,
        "riichi_first_opportunity": {
            "overall": {
                "n": first_overall["n"],
                "declares": first_overall["declares"],
                "declare_rate_pct": pct(first_overall["declares"], first_overall["n"]),
            },
            "splits": {name: finalize_rate_table(table) for name, table in first_splits.items()},
            "cross_tabs": {name: finalize_rate_table(table) for name, table in first_cross.items()},
        },
        "declined_then_what": summarize_declined(declined_outcomes),
        "late_game_keiten_push": {
            "definitions": {
                "bucket_key": "own_regular_shanten_after_discard|tiles_left_bucket|threat_bucket",
                "tiles_left_buckets": ["20-11", "10-6", "5-0"],
                "threat_priority": "riichi if any opponent riichi, else open_2meld if any opponent has >=2 open calls, else none",
            },
            "buckets": finalize_keiten_table(keiten_buckets),
        },
        "fold_commitment": {
            "n": fold_n,
            "later_push_>5pct": fold_push,
            "later_push_>5pct_rate_pct": pct(fold_push, fold_n),
            "stayed_folded_rate_pct": round(100.0 - pct(fold_push, fold_n), 1) if fold_n else None,
            "later_discards_known_n": sum(rec["later_discards_known_n"] for rec in fold_commitments),
        },
        "riichi_declaration_tile_safety": {
            "declares": bonus["declares"],
            "declares_with_existing_threat": bonus["declares_with_existing_threat"],
            "declares_with_existing_threat_rate_pct": pct(bonus["declares_with_existing_threat"], bonus["declares"]),
            "declares_with_existing_threat_danger_known_n": bonus["declares_with_existing_threat_danger_known_n"],
            "mean_danger_vs_existing_threat": round(
                bonus["declares_with_existing_threat_danger_sum"] / bonus["declares_with_existing_threat_danger_known_n"], 4
            ) if bonus["declares_with_existing_threat_danger_known_n"] else None,
            "danger_>10pct_vs_threat": bonus["danger_>10pct_vs_threat"],
            "danger_>10pct_vs_threat_rate_pct": pct(
                bonus["danger_>10pct_vs_threat"], bonus["declares_with_existing_threat_danger_known_n"]
            ),
        },
    }
    result["proposed_rules"] = build_proposed_rules(result)
    return result


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result = analyze()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
