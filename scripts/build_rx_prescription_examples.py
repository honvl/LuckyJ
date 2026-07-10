#!/usr/bin/env python3
"""Build prescription example snippets from cached LuckyJ NAGA reports."""

from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_luckyj as base
from build_point_examples import is_yakuhai_for_seat, rel_seat, seat_wind
from extract_case_studies import remove_tile, round_name


OUT = Path("site/rx-prescription-examples.json")
HONORS = ["E", "S", "W", "N", "P", "F", "C"]
DRAGONS = {"P", "F", "C"}
WINDS = ["E", "S", "W", "N"]

SEQUENCES = {
    "value_honor_cleanup_animation": [
        {
            "title": "Quiet dragon cleanup",
            "game": 417,
            "round": "East 4-0",
            "start_turn": 1,
            "end_turn": 4,
            "focus_turn": 3,
            "focus_honor": "C",
            "note": "Tokujou, child seat, quiet table: the singleton Red Dragon leaves on turn 3 with all three NAGA heads agreeing.",
        }
    ],
    "value_honor_cleanup": [
        {
            "title": "Green Dragon leaves on turn 3",
            "game": 561,
            "round": "East 3-2",
            "start_turn": 1,
            "end_turn": 4,
            "focus_turn": 3,
            "focus_honor": "F",
            "note": "Tokujou, child seat, quiet table: the singleton Green Dragon leaves on turn 3 with all three NAGA heads agreeing.",
        },
        {
            "title": "Round wind leaves on turn 3",
            "game": 758,
            "round": "East 3-1",
            "start_turn": 1,
            "end_turn": 4,
            "focus_turn": 3,
            "focus_honor": "E",
            "note": "Tokujou, child seat, quiet table: the singleton round wind leaves on turn 3 with all three NAGA heads agreeing.",
        },
        {
            "title": "Seat wind leaves on turn 3",
            "game": 267,
            "round": "East 4-0",
            "start_turn": 1,
            "end_turn": 4,
            "focus_turn": 3,
            "focus_honor": "W",
            "note": "Tokujou, child seat, quiet table: the singleton seat wind leaves on turn 3 with all three NAGA heads agreeing.",
        },
    ],
}


def tile_id(tile: str | None) -> int | None:
    if not tile or tile == "?":
        return None
    return base.IDX.get(str(tile).replace("r", ""))


def base_tile(tile: str | None) -> str:
    return str(tile or "").replace("r", "")


def same_tile(a: str | None, b: str | None) -> bool:
    return tile_id(a) is not None and tile_id(a) == tile_id(b)


def meld_tiles(meld: dict[str, Any] | list[str]) -> list[str]:
    if isinstance(meld, dict):
        return [tile for tile in meld.get("tiles", []) if tile and tile != "+"]
    return [tile for tile in meld if tile and tile != "+"]


def meld_shows_yakuhai_yaku(meld: dict[str, Any] | list[str], start: dict[str, Any], seat: int) -> bool:
    counts = Counter(tile_id(tile) for tile in meld_tiles(meld))
    return any(idx is not None and count >= 3 and is_yakuhai_for_seat(base.TILES[idx], start, seat) for idx, count in counts.items())


def meld_all_simples(meld: dict[str, Any] | list[str]) -> bool:
    tiles = meld_tiles(meld)
    return bool(tiles) and all(base.tile_class(tile) == "simple" for tile in tiles)


def open_context(start: dict[str, Any], target: int, melds: list[list[dict[str, Any]]]) -> dict[str, Any]:
    opened = []
    visible_yaku = False
    tanyao_possible = False
    tanyao_blocked = False
    for seat, player_melds in enumerate(melds):
        if seat == target or not player_melds:
            continue
        seat_visible_yaku = any(meld_shows_yakuhai_yaku(meld, start, seat) for meld in player_melds)
        seat_tanyao_possible = all(meld_all_simples(meld) for meld in player_melds)
        if seat_visible_yaku:
            visible_yaku = True
        if seat_tanyao_possible:
            tanyao_possible = True
        else:
            tanyao_blocked = True
        opened.append(
            {
                "seat": rel_seat(seat, target),
                "melds": len(player_melds),
                "seat_wind": seat_wind(start, seat),
                "visible_yaku": seat_visible_yaku,
                "tanyao": "possible" if seat_tanyao_possible else "not_possible",
            }
        )
    if visible_yaku:
        yaku_text = "visible yakuhai yaku shown"
    elif tanyao_possible and tanyao_blocked:
        yaku_text = "no visible yaku; tanyao possible for one open hand and blocked for another"
    elif tanyao_possible:
        yaku_text = "no visible yaku; tanyao still possible"
    elif opened:
        yaku_text = "no visible yaku; tanyao not possible from exposed tiles"
    else:
        yaku_text = "no opponent opened"
    return {
        "someone_opened": bool(opened),
        "opponents": opened,
        "opponent_melds": sum(item["melds"] for item in opened),
        "visible_yaku": visible_yaku,
        "tanyao_possible": tanyao_possible,
        "tanyao_blocked": tanyao_blocked,
        "visible_yaku_text": yaku_text,
    }


def table_seen_counts(
    hand: list[str],
    accepted: str | None,
    discards: list[list[str]],
    melds: list[list[dict[str, Any]]],
    dora_markers: list[str],
) -> list[dict[str, Any]]:
    current = list(hand)
    if accepted:
        current.append(accepted)
    hand_counts = Counter(tile_id(tile) for tile in current)
    table_counts: Counter[int] = Counter()
    for marker in dora_markers:
        idx = tile_id(marker)
        if idx is not None:
            table_counts[idx] += 1
    for river in discards:
        for tile in river:
            idx = tile_id(tile)
            if idx is not None:
                table_counts[idx] += 1
    for player_melds in melds:
        for meld in player_melds:
            for tile in meld_tiles(meld):
                idx = tile_id(tile)
                if idx is not None:
                    table_counts[idx] += 1
    rows = []
    for tile in HONORS:
        idx = base.IDX[tile]
        if hand_counts[idx] <= 0:
            continue
        table = min(table_counts[idx], 4)
        in_hand = hand_counts[idx]
        rows.append(
            {
                "tile": tile,
                "in_hand": in_hand,
                "table": table,
                "seen": min(4, in_hand + table),
                "remaining": max(0, 4 - min(4, in_hand + table)),
            }
        )
    return rows


def make_meld(tiles: list[str], called_tile: str | None = None, called_from: str | None = None, kind: str | None = None) -> dict[str, Any]:
    meld = {"tiles": [tile for tile in tiles if tile and tile != "+"]}
    if called_tile:
        meld["called_tile"] = called_tile
    if called_from:
        meld["called_from"] = called_from
    if kind:
        meld["kind"] = kind
    return meld


def decision_label(turn: int, kind: str | None = None) -> str:
    if kind and kind in {"chi", "pon", "daiminkan"}:
        return kind.upper()
    return f"T{turn}"


def frame_from_decision(
    *,
    start: dict[str, Any],
    target: int,
    turn: int,
    hand: list[str],
    accepted: str | None,
    discard: str | None,
    discards: list[list[str]],
    melds: list[list[dict[str, Any]]],
    dora_markers: list[str],
    reached: list[bool],
    kind: str | None = None,
    call: str | None = None,
    hold: str | None = None,
    consumed: list[str] | None = None,
) -> dict[str, Any]:
    context = open_context(start, target, melds)
    if any(seat != target and reached[seat] for seat in range(4)):
        context["riichi_active"] = True
    return {
        "label": decision_label(turn, kind),
        "turn": turn,
        "left": max(0, 70 - 4 * (turn - 1)),
        "hand": list(hand),
        "draw": accepted,
        "discard": discard,
        "hold": hold,
        "call": call,
        "consumed": consumed or [],
        "honor_counts": table_seen_counts(hand, accepted, discards, melds, dora_markers),
        "open_context": context,
    }


def replay_sequence(row: dict[str, Any], spec: dict[str, Any], kyoku: list[dict[str, Any]]) -> dict[str, Any]:
    target = row["actor"]
    start = kyoku[0].get("info", {}).get("msg", {})
    hands = [list(hand) for hand in start.get("tehais", [[], [], [], []])]
    discards: list[list[str]] = [[], [], [], []]
    melds: list[list[dict[str, Any]]] = [[], [], [], []]
    reached = [False, False, False, False]
    dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []
    frames: list[dict[str, Any]] = []

    def remove_for_actor(actor: int | None, tile: str | None) -> None:
        if actor is None or tile in (None, "?"):
            return
        remove_tile(hands[actor], tile)

    for state in kyoku:
        msg = state.get("info", {}).get("msg", {})
        actor = msg.get("actor")
        msg_type = msg.get("type")

        if msg_type == "dora" and msg.get("dora_marker"):
            dora_markers.append(msg["dora_marker"])
            continue

        if msg_type == "reach" and actor is not None:
            reached[actor] = True
            continue

        if msg_type == "tsumo" and actor is not None:
            draw = msg.get("pai")
            hand_before_draw = list(hands[actor])
            if draw:
                hands[actor].append(draw)
            real_dahai = msg.get("real_dahai")
            if actor == target:
                turn = len(discards[target]) + 1
                if spec["start_turn"] <= turn <= spec["end_turn"] and real_dahai not in (None, "?"):
                    frames.append(
                        frame_from_decision(
                            start=start,
                            target=target,
                            turn=turn,
                            hand=hand_before_draw,
                            accepted=draw,
                            discard=real_dahai,
                            discards=deepcopy(discards),
                            melds=deepcopy(melds),
                            dora_markers=list(dora_markers),
                            reached=list(reached),
                            hold=spec.get("hold") if spec.get("hold") and any(same_tile(tile, spec["hold"]) for tile in hand_before_draw) else None,
                        )
                    )
            if real_dahai not in (None, "?"):
                remove_for_actor(actor, real_dahai)
                discards[actor].append(real_dahai)
            continue

        if msg_type in base.HURO_TYPES and actor is not None:
            real_dahai = msg.get("real_dahai")
            consumed = msg.get("consumed") or []
            if actor == target and real_dahai not in (None, "?"):
                turn = len(discards[target]) + 1
                if spec["start_turn"] <= turn <= spec["end_turn"]:
                    frames.append(
                        frame_from_decision(
                            start=start,
                            target=target,
                            turn=turn,
                            hand=list(hands[target]),
                            accepted=msg.get("pai"),
                            discard=real_dahai,
                            discards=deepcopy(discards),
                            melds=deepcopy(melds),
                            dora_markers=list(dora_markers),
                            reached=list(reached),
                            kind=msg_type,
                            call=msg_type,
                            consumed=list(consumed),
                            hold=spec.get("hold") if spec.get("hold") and any(same_tile(tile, spec["hold"]) for tile in hands[target]) else None,
                        )
                    )
            call_tiles = [tile for tile in consumed if tile]
            if msg.get("pai"):
                call_tiles.append(msg.get("pai"))
            melds[actor].append(make_meld(call_tiles, msg.get("pai"), rel_seat(msg.get("target"), actor), msg_type))
            for tile in consumed:
                remove_for_actor(actor, tile)
            if real_dahai not in (None, "?"):
                remove_for_actor(actor, real_dahai)
                discards[actor].append(real_dahai)
            continue

        if msg_type in {"ankan", "kakan"} and actor is not None:
            consumed = msg.get("consumed") or ([msg.get("pai")] if msg.get("pai") else [])
            melds[actor].append(make_meld([tile for tile in consumed if tile], kind=msg_type))
            for tile in consumed:
                remove_for_actor(actor, tile)

    focus_indexes = [idx for idx, frame in enumerate(frames) if frame["turn"] in {spec["focus_turn"] - 1, spec["focus_turn"], spec["focus_turn"] + 1}]
    if not focus_indexes:
        focus_indexes = list(range(len(frames)))
    for frame in frames:
        frame["focus_honor"] = spec.get("focus_honor")
        if spec.get("focus_honor") and same_tile(frame.get("discard"), spec["focus_honor"]):
            frame["discard_focus_honor"] = True
    return {
        "title": spec["title"],
        "game": row["idx"],
        "round": round_name(start),
        "kyoku_index": spec.get("kyoku_index"),
        "actor": target,
        "oya": start.get("oya"),
        "dealer_status": "child",
        "room": row.get("room"),
        "room_code": row.get("room_code"),
        "focus_honor": spec.get("focus_honor"),
        "note": spec.get("note"),
        "autoplay_indices": focus_indexes,
        "turns": frames,
    }


def build_sequences() -> dict[str, list[dict[str, Any]]]:
    rows = base.parse_rows()
    by_idx = {row["idx"]: row for row in rows}
    report_cache: dict[int, dict[str, Any]] = {}
    output: dict[str, list[dict[str, Any]]] = {}
    for key, specs in SEQUENCES.items():
        output[key] = []
        for spec in specs:
            row = by_idx[spec["game"]]
            if row.get("room") != "Tokujou":
                raise ValueError(f"non-Tokujou prescription example selected: game {spec['game']} ({row.get('room')})")
            if spec["game"] not in report_cache:
                data = base.fetch_report(row["report_id"])
                base.normalize_report(data)
                report_cache[spec["game"]] = data
            data = report_cache[spec["game"]]
            kyoku = None
            kyoku_index = None
            for idx, candidate in enumerate(data.get("pred", [])):
                start = candidate[0].get("info", {}).get("msg", {}) if candidate else {}
                if round_name(start) == spec["round"]:
                    if row["actor"] == start.get("oya"):
                        raise ValueError(f"dealer example selected: game {spec['game']} {spec['round']}")
                    kyoku = candidate
                    kyoku_index = idx
                    break
            if kyoku is None:
                raise ValueError(f"could not find {spec['round']} in game {spec['game']}")
            spec = {**spec, "kyoku_index": kyoku_index}
            output[key].append(replay_sequence(row, spec, kyoku))
    return output


def main() -> None:
    OUT.write_text(json.dumps(build_sequences(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
