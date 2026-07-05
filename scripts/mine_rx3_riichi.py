#!/usr/bin/env python3
"""Third-pass riichi mining: child-only prescriptions plus dealer-vs-Nishiki checks."""
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import analyze_luckyj as base
import mine_rx_riichi as rx1
import mine_rx2_riichi as rx2

REPO_ROOT = Path(__file__).resolve().parents[1]
base.SHEET_CSV = REPO_ROOT / "data" / "LuckyJ.csv"
base.CACHE_DIR = REPO_ROOT / "data" / "report_cache"

OUT = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx3-riichi.json")
MIN_CELL_N = 120
WAIT_STRATA = ("<=3", "4-7")

CONDITIONS = [
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

VALUE_ORDER = dict(rx2.VALUE_ORDER)
VALUE_ORDER["dealer_status"] = ["child", "dealer"]

PUBLISHED = {
    "first_opportunity_declare_rate_pct": 66.9,
    "wait_8+_declare_rate_pct": 93.6,
    "wait_4-7_declare_rate_pct": 79.5,
    "wait_<=3_declare_rate_pct": 36.1,
    "declined_later_declared_rate_pct": 22.1,
    "declined_stayed_damaten_to_end_rate_pct": 59.4,
    "declined_fold_or_broke_tenpai_rate_pct": 18.5,
    "keiten_0_20-11_riichi_push_>5pct_rate_pct": 67.4,
    "keiten_0_10-6_riichi_push_>5pct_rate_pct": 68.4,
    "keiten_0_5-0_riichi_push_>5pct_rate_pct": 63.1,
    "keiten_2+_20-11_riichi_push_>5pct_rate_pct": 27.4,
    "keiten_2+_10-6_riichi_push_>5pct_rate_pct": 23.9,
    "keiten_2+_5-0_riichi_push_>5pct_rate_pct": 25.2,
    "fold_commitment_stayed_folded_rate_pct": 52.4,
    "stick_tile_danger_>10pct_vs_threat_rate_pct": 42.9,
    "<=3_2+_winning_tile_types_delta_pp": 21.0,
    "4-7_2+_winning_tile_types_delta_pp": 21.0,
    "4-7_south4_delta_pp": -27.0,
    "<=3_existing_riichi_delta_pp": -19.0,
    "4-7_existing_riichi_delta_pp": -12.0,
    "4-7_rank4_delta_pp": 12.0,
    "4-7_2+_dora_delta_pp": -12.0,
    "<=3_big_lead_bad_wait_declare_rate_pct": 35.0,
}


def pct(num, den, digits=1):
    return round(100.0 * num / den, digits) if den else None


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


def rate_entry(n, yes, yes_name="declares", rate_name=None):
    if rate_name is None:
        rate_name = "declare_rate_pct" if yes_name == "declares" else f"{yes_name}_rate_pct"
    ci = ci95_half_width_pp(yes, n)
    return {
        "n": n,
        yes_name: yes,
        rate_name: pct(yes, n),
        "ci95_half_width_pp": round(ci, 1) if ci is not None else None,
    }


def sorted_values(condition_key, values):
    order = VALUE_ORDER.get(condition_key, [])
    return sorted(values, key=lambda value: (order.index(value) if value in order else len(order), str(value)))


def safe_reached(start):
    reached = [False, False, False, False]
    raw = start.get("reached")
    if isinstance(raw, list):
        for seat, value in enumerate(raw[:4]):
            reached[seat] = bool(value)
    return reached


def dealer_status(start, target):
    return "dealer" if start.get("oya") == target else "child"


def reach_head0_prob(state):
    reach = state.get("reach")
    if not isinstance(reach, list) or not reach:
        return None
    try:
        return float(reach[0]) / 10000.0
    except (TypeError, ValueError):
        return None


def add_bool_counter(table, key, yes):
    table[key]["n"] += 1
    table[key]["yes"] += int(bool(yes))


def top_head0_tile(state):
    preds = state.get("dahai_pred")
    if not isinstance(preds, list) or not preds:
        return None
    probs = preds[0]
    if not isinstance(probs, list) or len(probs) < 34:
        return None
    try:
        top, _ = base.top_tile(probs)
        return top
    except Exception:
        return None


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
            "ci95_half_width_pp": round(ci95_half_width_pp(val["push_>5pct"], known), 1) if known else None,
        }
    return out


def summarize_declined(counter):
    n = counter["n"]
    return {
        "n": n,
        "later_declared": counter["later_declared"],
        "later_declared_rate_pct": pct(counter["later_declared"], n),
        "stayed_damaten_to_end": counter["stayed_damaten_to_end"],
        "stayed_damaten_to_end_rate_pct": pct(counter["stayed_damaten_to_end"], n),
        "fold_or_broke_tenpai": counter["fold_or_broke_tenpai"],
        "fold_or_broke_tenpai_rate_pct": pct(counter["fold_or_broke_tenpai"], n),
    }


def summarize_fold(records):
    n = len(records)
    pushes = sum(1 for rec in records if rec.get("later_push_>5pct"))
    pushed = pct(pushes, n)
    return {
        "n": n,
        "later_push_>5pct": pushes,
        "later_push_>5pct_rate_pct": pushed,
        "stayed_folded_rate_pct": round(100.0 - pushed, 1) if pushed is not None else None,
        "later_discards_known_n": sum(rec.get("later_discards_known_n", 0) for rec in records),
    }


def summarize_safety(counter):
    known = counter["declares_with_existing_threat_danger_known_n"]
    return {
        "declares": counter["declares"],
        "declares_with_existing_threat": counter["declares_with_existing_threat"],
        "declares_with_existing_threat_rate_pct": pct(counter["declares_with_existing_threat"], counter["declares"]),
        "declares_with_existing_threat_danger_known_n": known,
        "mean_danger_vs_existing_threat": round(counter["declares_with_existing_threat_danger_sum"] / known, 4) if known else None,
        "danger_>10pct_vs_threat": counter["danger_>10pct_vs_threat"],
        "danger_>10pct_vs_threat_rate_pct": pct(counter["danger_>10pct_vs_threat"], known),
        "ci95_half_width_pp": round(ci95_half_width_pp(counter["danger_>10pct_vs_threat"], known), 1) if known else None,
    }


def collect():
    rows = base.parse_rows()
    meta = {
        "rows_seen": len(rows),
        "unique_report_ids_seen": len({row["report_id"] for row in rows}),
        "reports_processed": 0,
        "kyoku_seen": 0,
        "errors": [],
    }
    first_opps = []
    declined = {"child": Counter(), "dealer": Counter()}
    keiten = {"child": defaultdict(Counter), "dealer": defaultdict(Counter)}
    fold_records = []
    safety = {"child": Counter(), "dealer": Counter()}
    discard_match = {"child": Counter(), "dealer": Counter()}

    for row_idx, row in enumerate(rows, 1):
        if row_idx % 200 == 0:
            print(f"processed {row_idx}/{len(rows)} rows", file=sys.stderr, flush=True)
        target = row.get("actor")
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
            meta["reports_processed"] += 1
        except Exception as exc:
            meta["errors"].append({"report_id": row.get("report_id"), "scope": "report", "error": repr(exc)})
            continue

        for kyoku_index, kyoku in enumerate(data.get("pred") or []):
            if not kyoku:
                continue
            meta["kyoku_seen"] += 1
            try:
                start = kyoku[0].get("info", {}).get("msg", {})
                tehais = start.get("tehais") or [[], [], [], []]
                if len(tehais) < 4 or target is None or not (0 <= target < 4):
                    continue
                status = dealer_status(start, target)
                hands = [list(tehais[seat]) for seat in range(4)]
                discards = [[], [], [], []]
                reached = safe_reached(start)
                open_melds = [0, 0, 0, 0]
                melds = [[], [], [], []]
                public_visible = Counter()
                dora_markers = rx2.initial_dora_markers(start)
                for marker in dora_markers:
                    rx1.add_visible(public_visible, marker)

                reach_opps = []
                target_decisions = []
                fold_consec = 0
                fold_committed = False
                fold_record = None
                kyotaku = rx2.int_or_zero(start.get("kyotaku"))
                honba = rx2.int_or_zero(start.get("honba"))

                for pos, state in enumerate(kyoku):
                    msg = state.get("info", {}).get("msg", {})
                    actor = msg.get("actor")
                    msg_type = msg.get("type")

                    if msg_type == "dora":
                        marker = msg.get("dora_marker")
                        if marker not in (None, "?"):
                            dora_markers.append(marker)
                            rx1.add_visible(public_visible, marker)

                    if msg_type == "tsumo" and actor is not None and 0 <= actor < 4:
                        pai = msg.get("pai")
                        if pai:
                            hands[actor].append(pai)

                    if actor == target and msg_type == "tsumo":
                        actual = msg.get("real_dahai")
                        top = top_head0_tile(state)
                        if actual and actual != "?" and top is not None:
                            discard_match[status]["n"] += 1
                            discard_match[status]["matches"] += int(top == actual)

                    if actor == target and msg_type in rx1.TARGET_DECISION_TYPES:
                        actual = msg.get("real_dahai")
                        if actual and actual != "?":
                            after = rx1.hand_after_decision(hands[actor], msg)
                            regular_shanten = rx1.shanten_value(after, regular_only=True) if after is not None else None
                            full_shanten = rx1.shanten_value(after) if after is not None else None
                            danger = rx1.danger_for_tile(state, target, actual)
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

                            if left is not None and left <= 20 and not reached[target] and not msg.get("reached"):
                                s_bucket = rx1.shanten_bucket(regular_shanten)
                                l_bucket = rx1.keiten_left_bucket(left)
                                t_bucket = rx1.threat_bucket(target, reached, open_melds)
                                if l_bucket != "outside_scope":
                                    add_keiten_bucket(keiten[status], f"{s_bucket}|{l_bucket}|{t_bucket}", danger)

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
                                            "dealer_status": status,
                                            "commit_pos": pos,
                                            "later_push_>5pct": False,
                                            "later_discards_known_n": 0,
                                        }
                                else:
                                    if danger is not None:
                                        fold_record["later_discards_known_n"] += 1
                                        if danger > 0.05:
                                            fold_record["later_push_>5pct"] = True

                    if actor == target and "reach" in state:
                        actual = msg.get("real_dahai")
                        next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
                        declared = next_msg.get("type") == "reach" and next_msg.get("actor") == target
                        turn = len(discards[target]) + 1
                        left = msg.get("left_hai_num")
                        hand14 = list(hands[actor])
                        w_info = rx1.wait_info_after_discard(hand14, actual, public_visible)
                        post_hand = rx2.post_discard_hand(hand14, actual)
                        dora_tiles = list(post_hand or []) + rx2.flatten_melds(melds[target])
                        dora_count = rx2.dora_count_for_tiles(dora_tiles, dora_markers)
                        threat_bucket = rx2.existing_threat_bucket(target, reached, open_melds)
                        wait_types = rx2.winning_tile_types_after_discard(hand14, actual)
                        nishiki_prob = reach_head0_prob(state)
                        nishiki_wants = nishiki_prob is not None and nishiki_prob >= 0.5
                        opp = {
                            "game": row.get("idx"),
                            "report_id": row.get("report_id"),
                            "kyoku_index": kyoku_index,
                            "pos": pos,
                            "dealer_status": status,
                            "declared": bool(declared),
                            "nishiki_declare_prob": nishiki_prob,
                            "nishiki_wants_declare": nishiki_wants if nishiki_prob is not None else None,
                            "nishiki_agrees": (bool(declared) == nishiki_wants) if nishiki_prob is not None else None,
                            "turn": turn,
                            "left": left,
                            "wait_tiles_remaining": w_info.get("wait_tiles_remaining"),
                            "wait_stratum": rx2.wait_stratum(w_info.get("wait_tiles_remaining")),
                            "wait_bucket_pass1": rx1.wait_bucket(w_info.get("wait_tiles_remaining")),
                            "wait_types": wait_types,
                            "winning_tile_types_bucket": rx2.winning_tile_types_bucket(wait_types),
                            "dora_count": dora_count,
                            "dora_count_bucket": rx2.bucket_dora_count(dora_count),
                            "dora_two_way_bucket": rx2.bucket_dora_two_way(dora_count),
                            "rank_start": rx1.score_position_bucket(start, target),
                            "turn_bucket": rx2.turn_bucket(turn),
                            "tiles_left_bucket": rx2.tiles_left_bucket(left),
                            "existing_threat": threat_bucket,
                            "opponent_riichi_present": "yes" if any(seat != target and reached[seat] for seat in range(4)) else "no",
                            "open_2meld_present": "yes" if any(seat != target and open_melds[seat] >= 2 for seat in range(4)) else "no",
                            "kyotaku_start": "1+" if kyotaku >= 1 else "0",
                            "honba_start": "1+" if honba >= 1 else "0",
                            "round_wind": rx2.round_wind_bucket(start),
                            "south4": rx2.south4_bucket(start),
                        }
                        reach_opps.append(opp)

                        if declared:
                            safety[status]["declares"] += 1
                            seats = rx1.threat_seats(target, reached, open_melds)
                            if seats:
                                safety[status]["declares_with_existing_threat"] += 1
                                d_threat = rx1.danger_for_tile(state, target, actual, seats=seats)
                                if d_threat is not None:
                                    safety[status]["declares_with_existing_threat_danger_known_n"] += 1
                                    safety[status]["declares_with_existing_threat_danger_sum"] += d_threat
                                    if d_threat > 0.10:
                                        safety[status]["danger_>10pct_vs_threat"] += 1

                    if msg_type == "tsumo" and actor is not None and 0 <= actor < 4:
                        discard = msg.get("real_dahai")
                        if discard and discard != "?":
                            rx1.remove_tile(hands[actor], discard)
                    else:
                        rx1.update_public_and_hands_after_state(
                            msg, actor, msg_type, hands, discards, public_visible, reached, open_melds, melds
                        )

                if fold_record is not None:
                    fold_records.append(fold_record)

                if reach_opps:
                    first = reach_opps[0]
                    first_opps.append(first)
                    if not first["declared"]:
                        bucket = declined[status]
                        bucket["n"] += 1
                        later_declared = any(opp["declared"] for opp in reach_opps[1:])
                        if later_declared:
                            bucket["later_declared"] += 1
                        else:
                            later_decisions = [d for d in target_decisions if d["pos"] > first["pos"]]
                            broke = any((d.get("full_shanten") is not None and d["full_shanten"] >= 1) for d in later_decisions)
                            if broke:
                                bucket["fold_or_broke_tenpai"] += 1
                            else:
                                bucket["stayed_damaten_to_end"] += 1
            except Exception as exc:
                meta["errors"].append({
                    "report_id": row.get("report_id"),
                    "kyoku_index": kyoku_index,
                    "scope": "kyoku",
                    "error": repr(exc),
                })
                continue

    return {
        "meta": meta,
        "first_opps": first_opps,
        "declined": declined,
        "keiten": keiten,
        "fold_records": fold_records,
        "safety": safety,
        "discard_match": discard_match,
    }


def split_yes_table(records, key, yes_field):
    out = {}
    for value in ("dealer", "child"):
        subset = [rec for rec in records if rec.get(key) == value and rec.get(yes_field) is not None]
        yes = sum(1 for rec in subset if rec.get(yes_field))
        out[value] = rate_entry(len(subset), yes, yes_name="matches", rate_name="match_rate_pct")
    return out


def hypothesis_check(first_opps, discard_match):
    agreement = split_yes_table(first_opps, "dealer_status", "nishiki_agrees")
    discard = {}
    for status in ("dealer", "child"):
        bucket = discard_match[status]
        discard[status] = rate_entry(bucket["n"], bucket["matches"], yes_name="matches", rate_name="match_rate_pct")
    dealer_rate = agreement["dealer"].get("match_rate_pct")
    child_rate = agreement["child"].get("match_rate_pct")
    return {
        "riichi_declare_agreement": {
            "definition": "All LuckyJ first riichi opportunities. Nishiki wants declare iff state['reach'][0] / 10000 >= 0.5; agreement iff LuckyJ's actual declared flag equals that preference.",
            "split_by_dealer_status": agreement,
            "dealer_minus_child_pp": round(dealer_rate - child_rate, 1) if dealer_rate is not None and child_rate is not None else None,
        },
        "secondary_tsumo_discard_match": {
            "definition": "All LuckyJ tsumo-discard decisions with dahai_pred; match iff head-0 top tile string equals real_dahai.",
            "split_by_dealer_status": discard,
            "dealer_minus_child_pp": round(discard["dealer"]["match_rate_pct"] - discard["child"]["match_rate_pct"], 1)
            if discard["dealer"].get("match_rate_pct") is not None and discard["child"].get("match_rate_pct") is not None else None,
        },
    }


def build_first_baseline(first_opps, status):
    records = [opp for opp in first_opps if opp.get("dealer_status") == status]
    declares = sum(1 for opp in records if opp["declared"])
    waits = {}
    for key in ("8+", "4-7", "<=3", "unknown"):
        subset = [opp for opp in records if opp.get("wait_stratum") == key]
        waits[key] = rate_entry(len(subset), sum(1 for opp in subset if opp["declared"]))
    return {"overall": rate_entry(len(records), declares), "by_unseen_waits": waits}


def selected_keiten(final_table):
    keys = [
        "0|20-11|riichi", "0|10-6|riichi", "0|5-0|riichi",
        "2+|20-11|riichi", "2+|10-6|riichi", "2+|5-0|riichi",
    ]
    return {key: final_table.get(key, {"n": 0, "danger_known_n": 0, "push_>5pct": 0, "push_>5pct_rate_pct": None}) for key in keys}


def side_by_side(child, dealer, rate_key):
    child_rate = child.get(rate_key)
    dealer_rate = dealer.get(rate_key)
    return {
        "child": child,
        "dealer": dealer,
        "dealer_minus_child_pp": round(dealer_rate - child_rate, 1) if child_rate is not None and dealer_rate is not None else None,
    }


def build_child_dealer_baselines(collected):
    first = {status: build_first_baseline(collected["first_opps"], status) for status in ("child", "dealer")}
    declined = {status: summarize_declined(collected["declined"][status]) for status in ("child", "dealer")}
    keiten_all = {status: finalize_keiten_table(collected["keiten"][status]) for status in ("child", "dealer")}
    keiten_sel = {status: selected_keiten(keiten_all[status]) for status in ("child", "dealer")}
    fold = {status: summarize_fold([rec for rec in collected["fold_records"] if rec.get("dealer_status") == status]) for status in ("child", "dealer")}
    safety = {status: summarize_safety(collected["safety"][status]) for status in ("child", "dealer")}

    comparisons = {
        "first_opportunity_overall": side_by_side(first["child"]["overall"], first["dealer"]["overall"], "declare_rate_pct"),
        "first_opportunity_by_unseen_waits": {
            key: side_by_side(first["child"]["by_unseen_waits"][key], first["dealer"]["by_unseen_waits"][key], "declare_rate_pct")
            for key in ("8+", "4-7", "<=3", "unknown")
        },
        "declined_then_what": {
            "child": declined["child"],
            "dealer": declined["dealer"],
            "deltas_dealer_minus_child_pp": {
                key: round(declined["dealer"].get(key) - declined["child"].get(key), 1)
                for key in ("later_declared_rate_pct", "stayed_damaten_to_end_rate_pct", "fold_or_broke_tenpai_rate_pct")
                if declined["dealer"].get(key) is not None and declined["child"].get(key) is not None
            },
        },
        "late_game_keiten_push_selected_under_riichi": {
            key: side_by_side(keiten_sel["child"][key], keiten_sel["dealer"][key], "push_>5pct_rate_pct")
            for key in keiten_sel["child"]
        },
        "fold_commitment": side_by_side(fold["child"], fold["dealer"], "stayed_folded_rate_pct"),
        "stick_tile_danger_gt_10pct_among_declares_into_threats": side_by_side(safety["child"], safety["dealer"], "danger_>10pct_vs_threat_rate_pct"),
    }

    return {
        "published_targets_all_seats": {key: PUBLISHED[key] for key in PUBLISHED if not key.endswith("_delta_pp") and "big_lead" not in key},
        "child": {
            "riichi_first_opportunity": first["child"],
            "declined_then_what": declined["child"],
            "late_game_keiten_push": {"all_buckets": keiten_all["child"], "selected_under_riichi": keiten_sel["child"]},
            "fold_commitment": fold["child"],
            "riichi_declaration_tile_safety": safety["child"],
        },
        "dealer": {
            "riichi_first_opportunity": first["dealer"],
            "declined_then_what": declined["dealer"],
            "late_game_keiten_push": {"all_buckets": keiten_all["dealer"], "selected_under_riichi": keiten_sel["dealer"]},
            "fold_commitment": fold["dealer"],
            "riichi_declaration_tile_safety": safety["dealer"],
        },
        "side_by_side_deltas": comparisons,
    }


def make_effect(condition_key, condition_label, value, n, declares, total_n, total_declares):
    comp_n = total_n - n
    comp_declares = total_declares - declares
    rate = declares / n if n else None
    comp_rate = comp_declares / comp_n if comp_n else None
    delta = (rate - comp_rate) * 100.0 if rate is not None and comp_rate is not None else None
    ci = ci95_half_width_pp(declares, n)
    delta_ci = delta_ci95_half_width_pp(declares, n, comp_declares, comp_n)
    meets_min = n >= MIN_CELL_N and comp_n >= MIN_CELL_N
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


def build_condition_effects_child(first_opps):
    child = [opp for opp in first_opps if opp.get("dealer_status") == "child"]
    out = {}
    for stratum in WAIT_STRATA:
        records = [opp for opp in child if opp.get("wait_stratum") == stratum]
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
                effect = make_effect(condition_key, condition_label, value, bucket["n"], bucket["declares"], total_n, total_declares)
                cells.append(effect)
                sorted_effects.append(effect)
            by_condition[condition_label] = {
                "condition_key": condition_key,
                "n": total_n,
                "declares": total_declares,
                "declare_rate_pct": pct(total_declares, total_n),
                "values": sorted(cells, key=lambda item: abs(item["delta_pp"]) if item["delta_pp"] is not None else -1, reverse=True),
            }
        out[stratum] = {
            "baseline": rate_entry(len(records), baseline_declares),
            "by_condition": by_condition,
            "sorted_effects": sorted(sorted_effects, key=lambda item: abs(item["delta_pp"]) if item["delta_pp"] is not None else -1, reverse=True),
        }
    return out


def find_effect(condition_effects, stratum, condition_key, value):
    for effect in condition_effects.get(stratum, {}).get("sorted_effects", []):
        if effect.get("condition_key") == condition_key and effect.get("value") == value:
            return effect
    return None


def summarize_bad_wait_cells(first_opps):
    child_bad = [opp for opp in first_opps if opp.get("dealer_status") == "child" and opp.get("wait_stratum") == "<=3"]
    by_rank = {}
    for rank in ("rank1_10k+_lead", "rank1_small_lead", "rank2-3", "rank4"):
        subset = [opp for opp in child_bad if opp.get("rank_start") == rank]
        by_rank[rank] = rate_entry(len(subset), sum(1 for opp in subset if opp["declared"]))
    return {
        "definition": "Child-only first riichi opportunities with <=3 unseen waits, split by start rank bucket.",
        "by_rank_start": by_rank,
        "big_lead_bad_wait_cell": by_rank["rank1_10k+_lead"],
        "published_dealer_modifiers_out_of_scope": {
            "<=3_waits_dealer_delta_pp": 8.0,
            "dealer_bad_wait_cell_declare_rate_pct": 42.0,
            "note": "These are dealer-specific published modifiers and are not prescriptions inside a child-only base.",
        },
    }


def build_cited_child_modifiers(condition_effects, first_opps):
    return {
        "published_targets": {key: PUBLISHED[key] for key in PUBLISHED if key.endswith("_delta_pp") or "big_lead" in key},
        "effects": {
            "<=3_2+_winning_tile_types_vs_1": find_effect(condition_effects, "<=3", "winning_tile_types_bucket", "2+"),
            "4-7_2+_winning_tile_types_vs_1": find_effect(condition_effects, "4-7", "winning_tile_types_bucket", "2+"),
            "4-7_south4": find_effect(condition_effects, "4-7", "south4", "South-4"),
            "<=3_into_existing_riichi": find_effect(condition_effects, "<=3", "existing_threat", "opponent_riichi"),
            "4-7_into_existing_riichi": find_effect(condition_effects, "4-7", "existing_threat", "opponent_riichi"),
            "4-7_starting_rank4": find_effect(condition_effects, "4-7", "rank_start", "rank4"),
            "4-7_2+_dora": find_effect(condition_effects, "4-7", "dora_count_bucket", "2+"),
        },
        "child_bad_wait_cells": summarize_bad_wait_cells(first_opps),
    }


def changed_vs_published(baselines, condition_effects, cited):
    child = baselines["child"]
    changes = []

    def add(name, published, current, path, metric="rate_pct"):
        if current is None:
            return
        delta = round(current - published, 1)
        if abs(delta) >= 2.0:
            changes.append({
                "name": name,
                "metric": metric,
                "published": published,
                "child_only": current,
                "delta_pp": delta,
                "json_path": path,
            })

    add("first opportunity declare", PUBLISHED["first_opportunity_declare_rate_pct"], child["riichi_first_opportunity"]["overall"]["declare_rate_pct"], "child_dealer_baselines.child.riichi_first_opportunity.overall.declare_rate_pct")
    for wait, pub_key in (("8+", "wait_8+_declare_rate_pct"), ("4-7", "wait_4-7_declare_rate_pct"), ("<=3", "wait_<=3_declare_rate_pct")):
        add(f"first opportunity declare, waits {wait}", PUBLISHED[pub_key], child["riichi_first_opportunity"]["by_unseen_waits"][wait]["declare_rate_pct"], f"child_dealer_baselines.child.riichi_first_opportunity.by_unseen_waits.{wait}.declare_rate_pct")
    for key, pub_key in (
        ("later_declared_rate_pct", "declined_later_declared_rate_pct"),
        ("stayed_damaten_to_end_rate_pct", "declined_stayed_damaten_to_end_rate_pct"),
        ("fold_or_broke_tenpai_rate_pct", "declined_fold_or_broke_tenpai_rate_pct"),
    ):
        add(f"declined then what: {key}", PUBLISHED[pub_key], child["declined_then_what"][key], f"child_dealer_baselines.child.declined_then_what.{key}")
    for key in child["late_game_keiten_push"]["selected_under_riichi"]:
        pub_key = f"keiten_{key.replace('|', '_')}_push_>5pct_rate_pct"
        if pub_key in PUBLISHED:
            add(f"late keiten push {key}", PUBLISHED[pub_key], child["late_game_keiten_push"]["selected_under_riichi"][key].get("push_>5pct_rate_pct"), f"child_dealer_baselines.child.late_game_keiten_push.selected_under_riichi.{key}.push_>5pct_rate_pct")
    add("fold commitment stayed folded", PUBLISHED["fold_commitment_stayed_folded_rate_pct"], child["fold_commitment"].get("stayed_folded_rate_pct"), "child_dealer_baselines.child.fold_commitment.stayed_folded_rate_pct")
    add("stick tile >10% danger among declares into threats", PUBLISHED["stick_tile_danger_>10pct_vs_threat_rate_pct"], child["riichi_declaration_tile_safety"].get("danger_>10pct_vs_threat_rate_pct"), "child_dealer_baselines.child.riichi_declaration_tile_safety.danger_>10pct_vs_threat_rate_pct")

    effect_specs = [
        ("<=3 2+ winning tile types delta", "<=3", "winning_tile_types_bucket", "2+", "<=3_2+_winning_tile_types_delta_pp"),
        ("4-7 2+ winning tile types delta", "4-7", "winning_tile_types_bucket", "2+", "4-7_2+_winning_tile_types_delta_pp"),
        ("4-7 South-4 delta", "4-7", "south4", "South-4", "4-7_south4_delta_pp"),
        ("<=3 into existing riichi delta", "<=3", "existing_threat", "opponent_riichi", "<=3_existing_riichi_delta_pp"),
        ("4-7 into existing riichi delta", "4-7", "existing_threat", "opponent_riichi", "4-7_existing_riichi_delta_pp"),
        ("4-7 starting rank 4 delta", "4-7", "rank_start", "rank4", "4-7_rank4_delta_pp"),
        ("4-7 2+ dora delta", "4-7", "dora_count_bucket", "2+", "4-7_2+_dora_delta_pp"),
    ]
    for label, stratum, cond, value, pub_key in effect_specs:
        effect = find_effect(condition_effects, stratum, cond, value)
        add(label, PUBLISHED[pub_key], effect.get("delta_pp") if effect else None, f"condition_effects_child.{stratum}.sorted_effects[{cond}={value}].delta_pp", metric="delta_pp")
    add("<=3 big-lead bad-wait declare cell", PUBLISHED["<=3_big_lead_bad_wait_declare_rate_pct"], cited["child_bad_wait_cells"]["big_lead_bad_wait_cell"].get("declare_rate_pct"), "cited_child_condition_effects.child_bad_wait_cells.big_lead_bad_wait_cell.declare_rate_pct")
    return sorted(changes, key=lambda item: abs(item["delta_pp"]), reverse=True)


def analyze():
    collected = collect()
    hypothesis = hypothesis_check(collected["first_opps"], collected["discard_match"])
    baselines = build_child_dealer_baselines(collected)
    condition_effects = build_condition_effects_child(collected["first_opps"])
    cited = build_cited_child_modifiers(condition_effects, collected["first_opps"])
    result = {
        "definitions": {
            "source": "data/report_cache/*.json.gz via scripts/analyze_luckyj.py parse_rows/fetch_report/normalize_report",
            "scope": "rx3 keeps all riichi first-opportunities for the hypothesis check, then restricts prescription baselines/effects to child (LuckyJ not start-of-kyoku oya). Dealer-only baseline versions are shown only as contrasts.",
            "riichi_first_opportunity": "First LuckyJ state per kyoku containing state['reach']; declaration iff next state's msg is type='reach' with actor==LuckyJ.",
            "nishiki_declare_preference": "Head 0 state['reach'] probability / 10000 >= 0.5.",
            "wait_tiles_remaining": "After LuckyJ's actual real_dahai from the 14-tile hand, winning tile types are tiles that make shanten -1; remaining copies subtract own post-discard hand plus public visible tiles, matching scripts/mine_rx_riichi.py.",
            "condition_effect_stats": f"rx2-style cells within child-only wait strata. Delta is value rate minus complement rate; meets_min_cell_n requires both value and complement n >= {MIN_CELL_N}.",
            "keiten_push": "Late-game decisions with left_hai_num <= 20; push means actual discard danger >5%; selected cells shown for tenpai and 2+ shanten under opponent riichi.",
            "fold_commitment": "First time LuckyJ makes two consecutive target discards under opponent riichi, both 2+ regular shanten after discard and each <1% danger; stayed folded means no later >5% danger push.",
        },
        "meta": collected["meta"],
        "dealer_vs_child_naga_match": hypothesis,
        "child_dealer_baselines": baselines,
        "condition_effects_child": condition_effects,
        "cited_child_condition_effects": cited,
    }
    result["changed_vs_published"] = changed_vs_published(baselines, condition_effects, cited)
    return result


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result = analyze()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
