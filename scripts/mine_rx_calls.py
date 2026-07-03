#!/usr/bin/env python3
"""Mine prescriptive call-decision thresholds from LuckyJ NAGA reports."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import analyze_luckyj as base
from build_point_examples import CALL_KIND_LABELS, yakuhai_for_seat
from extract_case_studies import counts_34, remove_tile
from mahjong.shanten import Shanten

OUT_PATH = Path("/Users/honvl/.claude/jobs/151072f5/tmp/rx-calls.json")
HURO_TYPES = {"chi", "pon", "daiminkan"}
SHANTEN = Shanten()

TURN_BUCKETS = ["1-6", "7-12", "13+"]
SHANTEN_BUCKETS = ["0-1", "2-3", "4+", "unknown"]
DORA_BUCKETS = ["0", "1", "2+"]
RANK_BUCKETS = ["1st", "4th"]
COPY_BUCKETS = ["first_discarded_copy", "later_copy"]
OPEN_STATUS_BUCKETS = ["fully_closed", "already_open"]
LATE_SHANTEN_BUCKETS = ["1", "2+", "0_or_less", "unknown"]


def pct(num: int, den: int) -> float | None:
    return round(100.0 * num / den, 1) if den else None


def base_tile(tile: str | None) -> str | None:
    return tile.replace("r", "") if isinstance(tile, str) else None


def tile_count(tiles: list[str], tile: str) -> int:
    try:
        target = base.IDX[tile]
    except KeyError:
        return 0
    total = 0
    for item in tiles:
        try:
            total += int(base.IDX[item] == target)
        except KeyError:
            continue
    return total


def turn_bucket(turn: int) -> str:
    if turn <= 6:
        return "1-6"
    if turn <= 12:
        return "7-12"
    return "13+"


def shanten_value(tiles: list[str]) -> int | None:
    try:
        return SHANTEN.calculate_shanten(counts_34(tiles), use_chiitoitsu=False, use_kokushi=False)
    except (KeyError, ValueError):
        return None


def shanten_bucket(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 1:
        return "0-1"
    if value <= 3:
        return "2-3"
    return "4+"


def late_shanten_bucket(value: int | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0:
        return "0_or_less"
    if value == 1:
        return "1"
    return "2+"


def dora_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    return "2+"


def rank_label(start: dict, target: int) -> str | None:
    ranks = start.get("seat2rank") or []
    if target < len(ranks) and ranks[target] is not None:
        rank = ranks[target] + 1
        if rank == 1:
            return "1st"
        if rank == 4:
            return "4th"
    return None


def dora_from_marker(marker: str | None) -> str | None:
    marker = base_tile(marker)
    if not marker:
        return None
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


def dora_count(tiles: list[str], dora_markers: list[str]) -> int:
    dora_tiles = [d for d in (dora_from_marker(marker) for marker in dora_markers) if d]
    total = 0
    for tile in tiles:
        clean = base_tile(tile)
        if clean in dora_tiles:
            total += dora_tiles.count(clean)
        if isinstance(tile, str) and tile.endswith("r"):
            total += 1
    return total


def huro_heads(state: dict, seat: int) -> list[dict[int, int]]:
    huro = state.get("huro") or {}
    if not isinstance(huro, dict):
        return []
    raw = huro.get(str(seat), huro.get(seat, []))
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    heads = []
    for head in raw:
        if not isinstance(head, dict):
            continue
        opts = {}
        for key, value in head.items():
            try:
                opts[int(key)] = int(value)
            except (TypeError, ValueError):
                continue
        if opts:
            heads.append(opts)
    return heads


def available_kinds(state: dict, seat: int) -> set[int]:
    kinds = set()
    for opts in huro_heads(state, seat):
        kinds.update(opts.keys())
    kinds.discard(0)
    return kinds


def actual_call(kyoku: list[dict], pos: int, target: int) -> tuple[bool, str | None, int | None, dict]:
    next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
    if next_msg.get("actor") != target or next_msg.get("type") not in HURO_TYPES:
        return False, None, None, next_msg
    msg_type = next_msg.get("type")
    kind = next_msg.get("kind")
    try:
        kind = int(kind) if kind is not None else None
    except (TypeError, ValueError):
        kind = None
    if kind is None:
        kind = {"chi": 1, "pon": 4, "daiminkan": 5}.get(msg_type)
    return True, msg_type, kind, next_msg


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


def serialize_yak(counter: Counter) -> dict:
    n = int(counter["n"])
    return {
        "n": n,
        "pon": int(counter["pon"]),
        "pon_rate_pct": pct(counter["pon"], n),
        "called_any": int(counter["called_any"]),
        "called_any_rate_pct": pct(counter["called_any"], n),
        "passed": int(counter["passed"]),
    }


def serialize_chi(counter: Counter) -> dict:
    n = int(counter["n"])
    return {
        "n": n,
        "chi": int(counter["chi"]),
        "chi_rate_pct": pct(counter["chi"], n),
        "called_any": int(counter["called_any"]),
        "called_any_rate_pct": pct(counter["called_any"], n),
        "passed": int(counter["passed"]),
    }


def serialize_call(counter: Counter) -> dict:
    n = int(counter["n"])
    return {
        "n": n,
        "called": int(counter["called"]),
        "call_rate_pct": pct(counter["called"], n),
        "passed": int(counter["passed"]),
        "pass_rate_pct": pct(counter["passed"], n),
    }


def serialize_group(groups: dict[str, Counter], labels: list[str], serializer) -> dict:
    for label in labels:
        groups[label]
    ordered = labels + sorted(label for label in groups if label not in labels)
    return {label: serializer(groups[label]) for label in ordered}


def prior_discard_count(discards: list[list[str]], tile: str) -> int:
    target = base_tile(tile)
    return sum(1 for seat_discards in discards for item in seat_discards if base_tile(item) == target)


def find_luckyj_target(data: dict, fallback: int) -> int:
    names = (data.get("player_info") or {}).get("name") or []
    for seat, name in enumerate(names):
        if "LuckyJ" in str(name):
            return seat
    return fallback


def grouped_rows() -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for row in base.parse_rows():
        groups[row["report_id"]].append(row)
    return groups


def choose_row(rows: list[dict], target: int) -> dict:
    for row in rows:
        if row.get("actor") == target:
            return row
    return dict(rows[0], actor=target)


def rate_phrase(obj: dict, key: str) -> str:
    rate = obj.get(key)
    n = obj.get("n", 0)
    if rate is None:
        return f"n={n}"
    return f"{rate:.1f}% (n={n})"


def build_rules(result: dict) -> list[str]:
    yak = result["yakuhai_pon_rate"]
    first = result["first_copy_vs_later"]["by_copy_timing"]["first_discarded_copy"]
    later = result["first_copy_vs_later"]["by_copy_timing"]["later_copy"]
    chi = result["chi_rate_by_purpose"]
    late = result["late_keiten_calls"]
    junk = result["never_call_signals"]

    return [
        "Default to ponning yakuhai pairs: LuckyJ poned "
        f"{rate_phrase(yak['overall'], 'pon_rate_pct')} overall.",
        "Pon the first visible yakuhai copy rather than waiting: first-copy pon rate "
        f"{rate_phrase(first, 'pon_rate_pct')} vs later-copy {rate_phrase(later, 'pon_rate_pct')}.",
        "Use shanten as the main brake on yakuhai pon: 0-1 shanten "
        f"{rate_phrase(yak['by_shanten_bucket']['0-1'], 'pon_rate_pct')}, "
        f"2-3 shanten {rate_phrase(yak['by_shanten_bucket']['2-3'], 'pon_rate_pct')}, "
        f"4+ shanten {rate_phrase(yak['by_shanten_bucket']['4+'], 'pon_rate_pct')}.",
        "Do not make chi your first call lightly: closed-to-open chi rate "
        f"{rate_phrase(chi['closed_to_open'], 'chi_rate_pct')}; once already open, chi rate "
        f"{rate_phrase(chi['by_open_status']['already_open'], 'chi_rate_pct')}.",
        "In the last 12 tiles, call for keiten at 1-shanten: call rate "
        f"{rate_phrase(late['by_shanten']['1'], 'call_rate_pct')} vs 2+ shanten "
        f"{rate_phrase(late['by_shanten']['2+'], 'call_rate_pct')}.",
        "Treat 4+ shanten, 0-dora hands as junk: pass all call chances "
        f"{rate_phrase(junk['all_call_opportunities'], 'pass_rate_pct')}; yakuhai pon still happens only "
        f"{rate_phrase(junk['yakuhai_pon_opportunities'], 'pon_rate_pct')}.",
        "Let dora increase yakuhai-pon willingness: 0 dora "
        f"{rate_phrase(yak['by_dora_bucket']['0'], 'pon_rate_pct')}, 1 dora "
        f"{rate_phrase(yak['by_dora_bucket']['1'], 'pon_rate_pct')}, 2+ dora "
        f"{rate_phrase(yak['by_dora_bucket']['2+'], 'pon_rate_pct')}.",
    ]


def mine() -> dict:
    groups = grouped_rows()
    source = {
        "csv_rows": sum(len(rows) for rows in groups.values()),
        "unique_report_ids": len(groups),
        "duplicate_report_rows": sum(max(0, len(rows) - 1) for rows in groups.values()),
        "processed_reports": 0,
        "target_seat_corrections_from_report_names": 0,
        "errors": [],
    }

    yak_overall = Counter()
    yak_by_turn = defaultdict(Counter)
    yak_by_shanten = defaultdict(Counter)
    yak_by_dora = defaultdict(Counter)
    yak_by_rank = defaultdict(Counter)
    yak_by_copy = defaultdict(Counter)

    chi_overall = Counter()
    chi_by_open = defaultdict(Counter)
    chi_by_turn = defaultdict(Counter)
    chi_by_shanten = defaultdict(Counter)
    chi_closed_to_open = Counter()

    late_overall = Counter()
    late_by_shanten = defaultdict(Counter)

    junk_all = Counter()
    junk_yak = Counter()

    call_opportunities = 0
    yakuhai_pon_opportunities = 0
    chi_opportunities = 0
    late_opportunities = 0

    for game_i, (report_id, rows) in enumerate(sorted(groups.items()), start=1):
        try:
            data = base.fetch_report(report_id)
            base.normalize_report(data)
            fallback_target = rows[0]["actor"]
            target = find_luckyj_target(data, fallback_target)
            if target != fallback_target:
                source["target_seat_corrections_from_report_names"] += 1
            row = choose_row(rows, target)
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
                melds = [[], [], [], []]
                open_melds = [0, 0, 0, 0]
                reached = [False, False, False, False]
                pending_riichi_discard = [False, False, False, False]
                dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []
                yakuhai_tiles = yakuhai_for_seat(start, target)
                rank = rank_label(start, target)

                for pos, state in enumerate(kyoku):
                    msg = state.get("info", {}).get("msg", {})
                    actor = msg.get("actor")
                    msg_type = msg.get("type")

                    if msg_type == "dora" and msg.get("dora_marker"):
                        dora_markers.append(msg["dora_marker"])

                    if msg_type == "dahai" and huro_heads(state, target):
                        discard = msg.get("pai")
                        kinds = available_kinds(state, target)
                        if discard and kinds:
                            called, called_type, called_kind, _ = actual_call(kyoku, pos, target)
                            turn = len(discards[target]) + 1
                            turn_b = turn_bucket(turn)
                            shanten = shanten_value(hands[target])
                            shanten_b = shanten_bucket(shanten)
                            dora_n = dora_count(hands[target], dora_markers)
                            dora_b = dora_bucket(dora_n)
                            call_opportunities += 1

                            if msg.get("left_hai_num") is not None and msg.get("left_hai_num") <= 12:
                                late_opportunities += 1
                                add_call(late_overall, called)
                                add_call(late_by_shanten[late_shanten_bucket(shanten)], called)

                            if shanten is not None and shanten >= 4 and dora_n == 0:
                                add_call(junk_all, called)

                            is_yakuhai_pon_opp = (
                                4 in kinds
                                and base_tile(discard) in yakuhai_tiles
                                and tile_count(hands[target], discard) >= 2
                            )
                            if is_yakuhai_pon_opp:
                                yakuhai_pon_opportunities += 1
                                poned = called and called_type == "pon"
                                add_yak(yak_overall, poned, called)
                                add_yak(yak_by_turn[turn_b], poned, called)
                                add_yak(yak_by_shanten[shanten_b], poned, called)
                                add_yak(yak_by_dora[dora_b], poned, called)
                                if rank in RANK_BUCKETS:
                                    add_yak(yak_by_rank[rank], poned, called)
                                copy_b = "first_discarded_copy" if prior_discard_count(discards, discard) == 0 else "later_copy"
                                add_yak(yak_by_copy[copy_b], poned, called)
                                if shanten is not None and shanten >= 4 and dora_n == 0:
                                    add_yak(junk_yak, poned, called)

                            if kinds & {1, 2, 3}:
                                chi_opportunities += 1
                                chii = called and called_type == "chi"
                                open_b = "already_open" if open_melds[target] > 0 else "fully_closed"
                                add_chi(chi_overall, chii, called)
                                add_chi(chi_by_open[open_b], chii, called)
                                add_chi(chi_by_turn[turn_b], chii, called)
                                add_chi(chi_by_shanten[shanten_b], chii, called)
                                if open_b == "fully_closed":
                                    add_chi(chi_closed_to_open, chii, called)

                    if msg_type == "tsumo" and actor is not None:
                        if msg.get("pai"):
                            hands[actor].append(msg["pai"])
                        discard = msg.get("real_dahai")
                        if discard and discard != "?":
                            remove_tile(hands[actor], discard)

                    elif msg_type in HURO_TYPES and actor is not None:
                        consumed = msg.get("consumed") or []
                        call_tiles = list(consumed) + ([msg.get("pai")] if msg.get("pai") else [])
                        melds[actor].append({"kind": msg_type, "tiles": call_tiles})
                        open_melds[actor] += 1
                        for tile in consumed:
                            remove_tile(hands[actor], tile)
                        discard = msg.get("real_dahai")
                        if discard and discard != "?":
                            remove_tile(hands[actor], discard)

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
                print(f"processed {game_i}/{len(groups)} reports", file=sys.stderr)
        except Exception as exc:  # keep mining despite malformed reports
            source["errors"].append({"report_id": report_id, "error": repr(exc)})
            print(f"error {report_id}: {exc!r}", file=sys.stderr)

    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "definitions": {
            "call_opportunity": "A dahai state whose huro map contains LuckyJ's seat; the dahai state's msg.pai is the triggering discard.",
            "actual_call": "The next state's msg is chi, pon, or daiminkan with actor equal to LuckyJ's seat.",
            "turn": "len(discards[LuckyJ]) + 1 before adding the triggering discard.",
            "shanten": "Regular-hand shanten of LuckyJ's current concealed tiles using mahjong.shanten.Shanten and counts_34; open melds are implied, chiitoitsu/kokushi disabled.",
            "dora_count": "Dora in LuckyJ's current concealed hand from visible dora indicators, plus one for each red five; red fives also count normal dora if the dora tile is five.",
            "yakuhai": "Dragons plus round wind and LuckyJ's seat wind via build_point_examples.yakuhai_for_seat().",
            "first_discarded_copy": "No previous discard of the same tile type in any player's discard list before the triggering discard.",
            "rank_split": "Score rank is read from the kyoku start seat2rank; only 1st and 4th are included in the requested split.",
            "call_kind_labels": {str(k): v for k, v in CALL_KIND_LABELS.items()},
            "all_rates_are_percent": True,
        },
        "totals": {
            "call_opportunities": call_opportunities,
            "yakuhai_pon_opportunities": yakuhai_pon_opportunities,
            "chi_opportunities": chi_opportunities,
            "late_left_hai_num_le_12_opportunities": late_opportunities,
        },
        "yakuhai_pon_rate": {
            "definitions": {
                "included": "Discard is yakuhai for LuckyJ, LuckyJ holds at least two of that tile in the concealed hand, and huro options contain kind 4 (pon).",
                "pon_rate_pct": "Next state is pon by LuckyJ divided by included opportunities.",
                "called_any_rate_pct": "Next state is chi, pon, or daiminkan by LuckyJ divided by included opportunities.",
            },
            "overall": serialize_yak(yak_overall),
            "by_turn_bucket": serialize_group(yak_by_turn, TURN_BUCKETS, serialize_yak),
            "by_shanten_bucket": serialize_group(yak_by_shanten, SHANTEN_BUCKETS, serialize_yak),
            "by_dora_bucket": serialize_group(yak_by_dora, DORA_BUCKETS, serialize_yak),
            "by_score_rank_1st_vs_4th": serialize_group(yak_by_rank, RANK_BUCKETS, serialize_yak),
        },
        "first_copy_vs_later": {
            "definitions": {
                "population": "Same yakuhai pon opportunities as yakuhai_pon_rate.",
                "first_discarded_copy": "The triggering discard is the first discarded copy of that tile type seen in any river.",
                "later_copy": "At least one same-type copy was already discarded before the triggering discard.",
            },
            "by_copy_timing": serialize_group(yak_by_copy, COPY_BUCKETS, serialize_yak),
        },
        "chi_rate_by_purpose": {
            "definitions": {
                "included": "huro options for LuckyJ contain any chi kind (1, 2, or 3).",
                "chi_rate_pct": "Next state is chi by LuckyJ divided by included opportunities.",
                "fully_closed": "LuckyJ has no prior open chi/pon/daiminkan meld before the opportunity; closed kan is not counted as open.",
                "already_open": "LuckyJ already has at least one prior open chi/pon/daiminkan meld before the opportunity.",
            },
            "overall": serialize_chi(chi_overall),
            "closed_to_open": serialize_chi(chi_closed_to_open),
            "by_open_status": serialize_group(chi_by_open, OPEN_STATUS_BUCKETS, serialize_chi),
            "by_turn_bucket": serialize_group(chi_by_turn, TURN_BUCKETS, serialize_chi),
            "by_shanten_bucket": serialize_group(chi_by_shanten, SHANTEN_BUCKETS, serialize_chi),
        },
        "late_keiten_calls": {
            "definitions": {
                "included": "All LuckyJ huro call opportunities with left_hai_num <= 12.",
                "call_rate_pct": "Next state is chi, pon, or daiminkan by LuckyJ divided by included opportunities.",
            },
            "overall": serialize_call(late_overall),
            "by_shanten": serialize_group(late_by_shanten, LATE_SHANTEN_BUCKETS, serialize_call),
        },
        "never_call_signals": {
            "definitions": {
                "junk_hand": "LuckyJ has regular-hand shanten >= 4 and zero dora in the concealed hand at a call opportunity.",
                "all_call_opportunities": "All huro call opportunities matching junk_hand.",
                "yakuhai_pon_opportunities": "Subset that also matches the yakuhai pon opportunity definition.",
            },
            "all_call_opportunities": serialize_call(junk_all),
            "yakuhai_pon_opportunities": serialize_yak(junk_yak),
        },
    }
    result["proposed_rules"] = build_rules(result)
    return result


def main() -> None:
    result = mine()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(json.dumps(result["totals"], ensure_ascii=False, sort_keys=True))
    if result["source"]["errors"]:
        print(f"errors: {len(result['source']['errors'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
