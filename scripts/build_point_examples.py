#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from pathlib import Path

import analyze_luckyj as base
from extract_case_studies import (
    counts_34,
    hand_string,
    remove_tile,
    retained_safety,
    round_name,
    safety_read,
    score_band,
    ukeire_after_discard,
)
from mahjong.shanten import Shanten


OUT = Path("site/point-examples.json")
MORTAL_PATH = Path("site/mortal-analysis.json")
SEAT_NAMES = ["self", "shimocha", "toimen", "kamicha"]
SEAT_LABELS_EN = {
    "self": "self",
    "shimocha": "right player",
    "toimen": "across player",
    "kamicha": "left player",
}
SEAT_LABELS_JA = {
    "self": "自分",
    "shimocha": "下家",
    "toimen": "対面",
    "kamicha": "上家",
}
WINDS = ["E", "S", "W", "N"]
DRAGONS = {"P", "F", "C"}
# Each point shows a few replays that differ from one another, not ten of the same spot.
EXAMPLES_PER_POINT = 6
MIN_EXAMPLES_PER_POINT = 4
POOL_PER_POINT = 400
SHANTEN = Shanten()
MODEL_KEYS = ["nishiki", "hibakari", "kagashi"]
MODEL_LABELS = {"nishiki": "Nishiki", "hibakari": "Hibakari", "kagashi": "Kagashi"}
MODEL_LABELS_JA = {"nishiki": "ニシキ", "hibakari": "ヒバカリ", "kagashi": "カガシ"}
HIBAKARI_SPLIT_POINTS = {
    "point-04",
    "point-05",
    "point-09",
    "point-14",
    "point-15",
    "point-16",
}
DANGER_HEADS = [
    ("k", "dangerK"),
    ("t", "dangerT"),
    ("s", "dangerS"),
]
CALL_KIND_LABELS = {
    0: "pass",
    1: "chi",
    2: "chi",
    3: "chi",
    4: "pon",
    5: "open kan",
}


POINT_TEXT = {
    "point-01": {
        "title": "Placement changes the price of the same tile",
        "lesson": "When the score is already good enough, the hand does not need to chase every point. A lead lowers ambition only when the discard also reduces real danger or preserves a clean next turn.",
        "prompt": "Before choosing, say the placement job and the concrete risk this discard removes.",
        "answer": "Copy the score job first. Lower ambition only when the hand still has a cheap end, clean fold, or safe next discard.",
    },
    "point-02": {
        "title": "Keep the branch point alive",
        "lesson": "LuckyJ often keeps tiles that still serve yaku, value, or safety, even when that makes the current shanten number look worse.",
        "prompt": "List the live routes before cutting: closed riichi, open yaku, value upgrade, chiitoi, and fold.",
        "answer": "Keep multiple live routes until the table forces a commitment.",
    },
    "point-03": {
        "title": "Calls need a named purpose",
        "lesson": "The call is valuable when it repairs a fake closed route, creates yaku or tenpai, changes the round clock, denies time, or preserves safe draw equity.",
        "prompt": "Before calling, say what the call creates and what you discard after it.",
        "answer": "Open poor closed shapes only when the exposed hand has a clear job, a first discard, and still leaves a way to stop.",
    },
    "point-04": {
        "title": "Open hands must keep a safe tile",
        "lesson": "After opening, the safe tile left behind is often the important tile. LuckyJ's open hands keep defensive tiles by design.",
        "prompt": "After the call, identify the next safe discard before admiring the new shanten.",
        "answer": "A cheap exposed hand needs a safe tile so the next threat avoids a bad forced push.",
    },
    "point-05": {
        "title": "Cut the future liability now",
        "lesson": "The floater is bad because a slow hand may be forced to discard it after the table becomes dangerous.",
        "prompt": "Find the tile you will hate discarding after the first riichi or second call.",
        "answer": "If the hand is far away and the tile has no value job, remove it before it becomes expensive.",
    },
    "point-06": {
        "title": "Build the value early",
        "lesson": "When the score job needs more, optimizing toward a cheap bad-shape future is too small. Early acceptance is the cheapest thing to spend.",
        "prompt": "Ask how many points this hand needs before preserving maximum ukeire.",
        "answer": "Keep dora, yaku, and shape upgrades when the fast hand would be too small or too brittle.",
    },
    "point-08": {
        "title": "Riichi converts pressure into equity",
        "lesson": "LuckyJ can declare before the shape is perfect when riichi itself changes the table. The declaration can force rivals to fold, deny calls, or lock in placement value.",
        "prompt": "Before riichi, ask who must now respond to you and whether better upgrades are realistic.",
        "answer": "If the wait is serviceable and the table must respect the stick, declaration pressure can be worth more than waiting.",
    },
    "point-09": {
        "title": "Reprice the hand after every draw",
        "lesson": "A hand that was pushing one turn ago can become a fold when the next required discard is bad. The chain of future discards matters more than the current tile alone.",
        "prompt": "Count the current discard plus the next two likely discards before calling the hand a push.",
        "answer": "If the path contains several live danger tiles, downgrade the hand even when it is close.",
    },
    "point-10": {
        "title": "Late precision beats late invention",
        "lesson": "Late choices should have exact upside: winning tenpai, safe tenpai, or clean fold. Speculative value routes have mostly expired.",
        "prompt": "In the third row, state whether you are winning, taking safe tenpai, or folding.",
        "answer": "Late examples are counting drills first; style imitation comes after the numbers work.",
    },
    "point-11": {
        "title": "Drawn-hand points are attack equity",
        "lesson": "Late defense can still earn points. Safe tenpai or harmless 1-shanten can win the hand through the draw.",
        "prompt": "When the hand is unlikely to win, count whether a safe route to tenpai still exists.",
        "answer": "Choose the safe discard that leaves the most realistic tenpai path for the draw.",
    },
    "point-12": {
        "title": "A disagreement is a review prompt",
        "lesson": "The useful question is why LuckyJ and each NAGA head split: safety, route count, value, pressure, or a real mistake.",
        "prompt": "Bucket the disagreement before judging it: blunder, strategic trade-off, or table-reading idea.",
        "answer": "Use match rate as a review cue, then aim for explainable decisions with fewer unpriced risks.",
    },
    "point-13": {
        "title": "Price the missing yakuhai",
        "lesson": "When another player calls with an unclear yaku, a singleton dragon or value wind becomes a timing choice: release it while no yaku or clear advancement is visible, accepting today's pon risk, or choke it once advancement becomes visible.",
        "prompt": "After an opponent opens, is this yakuhai still cheap enough to release, or has it become a tile to choke?",
        "answer": "Discarding is not denial. Release early only when carrying the tile into a more advanced hand would be worse; otherwise hold it rather than feed the yaku switch.",
    },
    "point-14": {
        "title": "Keep safe tiles for a named target",
        "lesson": "LuckyJ keeps genbutsu, suji, and weaker outside-river safety only when the tile answers a specific opponent and a specific future decision.",
        "prompt": "For each kept safe tile, complete the sentence: safe against X if Y happens.",
        "answer": "Keep the safe tile while it covers the live threat and buys future choice; spend it when the target is vague, quiet, or already covered.",
    },
    "point-15": {
        "title": "Safe tiles expire",
        "lesson": "A tile that was safe earlier can become the correct discard once it no longer protects against the live danger or starts damaging the hand's real route.",
        "prompt": "Name the player this safe tile protects against, then ask whether that player is still the main danger.",
        "answer": "Spend stale safety when it is off-target, the hand is real, and another safe tile remains for the next bad draw.",
    },
    "point-16": {
        "title": "Late outside cuts can preserve the route",
        "lesson": "Under pressure, cutting an edge or terminal can be the attacking discard because it keeps the middle tile that connects the actual path to tenpai.",
        "prompt": "When a terminal cut looks timid, check whether the inside tile is the hand's real connector.",
        "answer": "Treat the outside cut as route preservation when the outside tile carries little value or target-specific safety.",
    },
    "point-18": {
        "title": "Honor tiles need role labels",
        "lesson": "An honor can be self value, an opponent yaku condition, dead material, or a defensive tile. Those are different tiles in review.",
        "prompt": "Before cutting or keeping an honor, label its current job.",
        "answer": "Cut loose honors when their only live job helps an opponent or when they are dead; keep honors that are value, route, or target-specific defensive tiles.",
    },
}


PREFERRED_CASES = {
    "point-15": [{"game": 352, "kyoku_index": 0, "left": 43, "actual": "5m", "naga": "P"}],
    "point-16": [{"game": 107, "kyoku_index": 7, "left": 16, "actual": "1s", "naga": "2s"}],
    "point-18": [{"game": 584, "kyoku_index": 6, "left": 27, "actual": "N", "naga": "1s"}],
}


def tile_id(tile):
    return base.IDX[tile]


def same_tile(a, b):
    if not a or not b:
        return False
    try:
        return tile_id(a) == tile_id(b)
    except KeyError:
        return False


def base_tile(tile):
    return str(tile or "").replace("r", "")


def rel_seat(seat, target):
    if seat is None:
        return "unknown"
    return SEAT_NAMES[(seat - target) % 4]


def seat_wind(start, seat):
    return WINDS[(seat - start.get("oya", 0)) % 4]


def yakuhai_for_seat(start, seat):
    return DRAGONS | {start.get("bakaze"), seat_wind(start, seat)}


def is_yakuhai_for_seat(tile, start, seat):
    return base_tile(tile) in yakuhai_for_seat(start, seat)


def make_meld(tiles, called_tile=None, called_from=None, kind=None):
    clean_tiles = [tile for tile in (tiles or []) if tile and tile != "+"]
    meld = {"tiles": clean_tiles}
    if called_tile:
        meld["called_tile"] = called_tile
    if called_from:
        meld["called_from"] = called_from
    if kind:
        meld["kind"] = kind
    return meld


def meld_tiles(meld):
    if isinstance(meld, dict):
        return [tile for tile in meld.get("tiles", []) if tile and tile != "+"]
    return [tile for tile in str(meld).split() if tile and tile != "+"]


def meld_shows_yakuhai_yaku(meld, start, seat):
    counts = Counter(tile_id(tile) for tile in meld_tiles(meld))
    return any(count >= 3 and is_yakuhai_for_seat(base.TILES[idx], start, seat) for idx, count in counts.items())


def meld_all_simples(meld):
    tiles = meld_tiles(meld)
    return bool(tiles) and all(base.tile_class(tile) == "simple" for tile in tiles)


def yakuhai_cleanup_threats(start, target, melds, tile):
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


def score_context(start, target):
    scores = start.get("scores", [None] * 4)
    ranks = start.get("seat2rank", [None] * 4)
    dealer = start.get("oya", 0)
    return [
        {
            "seat": rel_seat(seat, target),
            "wind": WINDS[(seat - dealer) % 4],
            "score": scores[seat] if seat < len(scores) else None,
            "rank": ranks[seat] + 1 if seat < len(ranks) and ranks[seat] is not None else None,
            "dealer": seat == dealer,
        }
        for seat in range(4)
    ]


def current_rank(start, target):
    ranks = start.get("seat2rank", [None] * 4)
    if target < len(ranks) and ranks[target] is not None:
        return ranks[target] + 1
    return None


def danger_head_value(state, seat, tile, suffix):
    try:
        idx = tile_id(tile)
    except KeyError:
        return None
    danger = (state or {}).get(f"danger_{suffix}") or []
    if seat < len(danger) and idx < len(danger[seat]):
        return danger[seat][idx] / 10000.0
    return None


def hand_tile_threats(state, target, hand):
    threats = []
    for tile in hand:
        bars = []
        for suffix, label in DANGER_HEADS:
            danger = danger_head_value(state, target, tile, suffix)
            bars.append(
                {
                    "head": label,
                    "label": label,
                    "danger": round(danger, 3) if danger is not None else None,
                }
            )
        threats.append({"tile": tile, "bars": bars})
    return threats


def discard_threat_value(state, target, tile):
    values = []
    for suffix, _label in DANGER_HEADS:
        danger = danger_head_value(state, target, tile, suffix)
        if danger is not None:
            values.append(danger)
    return max(values) if values else None


def discard_threat_profile(state, target, tile):
    bars = []
    for suffix, label in DANGER_HEADS:
        danger = danger_head_value(state, target, tile, suffix)
        bars.append(
            {
                "head": label,
                "danger": round(danger, 3) if danger is not None else None,
            }
        )
    values = [bar for bar in bars if bar["danger"] is not None]
    if not values:
        return {"tile": tile, "bars": bars, "max": None, "peak_head": None}
    peak = max(values, key=lambda bar: bar["danger"])
    return {
        "tile": tile,
        "bars": bars,
        "max": peak["danger"],
        "peak_head": peak["head"],
    }


def table_context(start, target, hands, discards, melds, reached, dora_markers, state=None, riichi_discard_indices=None):
    rendered_hands = [sorted(hand, key=lambda tile: (tile_id(tile), tile)) for hand in hands]
    riichi_discard_indices = riichi_discard_indices or [None, None, None, None]
    return {
        "round": round_name(start),
        "dealer": rel_seat(start.get("oya"), target),
        "dora_markers": dora_markers[:],
        "scores": score_context(start, target),
        "players": [
            {
                "seat": rel_seat(seat, target),
                "wind": WINDS[(seat - start.get("oya", 0)) % 4],
                "hand": hand_string(rendered_hands[seat]),
                "tile_threats": hand_tile_threats(state, target, rendered_hands[seat]) if seat == target else [],
                "discards": discards[seat][:],
                "melds": melds[seat][:],
                "reached": bool(reached[seat]),
                "riichi_discard_index": riichi_discard_indices[seat] if seat < len(riichi_discard_indices) else None,
            }
            for seat in range(4)
        ],
    }


def visible_counter(discards, melds, dora_markers):
    visible = Counter()
    for marker in dora_markers:
        visible[tile_id(marker)] += 1
    for river in discards:
        for tile in river:
            visible[tile_id(tile)] += 1
    for player_melds in melds:
        for meld in player_melds:
            for tile in meld_tiles(meld):
                visible[tile_id(tile)] += 1
    return visible


def model_rows(state, actual):
    rows = []
    if not actual or actual == "?":
        return rows
    for index, pred in enumerate(state.get("dahai_pred", [])[:3]):
        top, top_prob = base.top_tile(pred)
        actual_prob = base.prob_for(pred, actual)
        key = MODEL_KEYS[index] if index < len(MODEL_KEYS) else f"model_{index}"
        rows.append(
            {
                "key": key,
                "label": MODEL_LABELS.get(key, key),
                "label_ja": MODEL_LABELS_JA.get(key, key),
                "top": top,
                "top_prob": top_prob,
                "actual_prob": actual_prob,
                "matches_luckyj": same_tile(top, actual),
            }
        )
    return rows


def top_rows(state, actual):
    return [(row["top"], row["top_prob"], row["actual_prob"]) for row in model_rows(state, actual)]


def model_head(rows, key):
    return next((row for row in rows if row.get("key") == key), None)


def call_kind_label(kind):
    try:
        kind = int(kind)
    except (TypeError, ValueError):
        return str(kind or "unknown")
    return CALL_KIND_LABELS.get(kind, f"call {kind}")


def huro_model_heads(previous_state, target, actual_kind):
    options = (previous_state or {}).get("huro", {}).get(str(target))
    if not options:
        return []
    if isinstance(options, dict):
        options = [options]
    heads = []
    for index, raw_options in enumerate(options[:3]):
        probs = {int(key): value / 10000.0 for key, value in raw_options.items()}
        top_kind, top_prob = max(probs.items(), key=lambda item: item[1])
        actual_prob = probs.get(int(actual_kind), 0.0) if actual_kind is not None else 0.0
        pass_prob = probs.get(0, 0.0)
        key = MODEL_KEYS[index] if index < len(MODEL_KEYS) else f"model_{index}"
        heads.append(
            {
                "key": key,
                "label": MODEL_LABELS.get(key, key),
                "label_ja": MODEL_LABELS_JA.get(key, key),
                "top_kind": top_kind,
                "top_action": call_kind_label(top_kind),
                "top_prob": round(top_prob, 3),
                "actual_kind_prob": round(actual_prob, 3),
                "pass_prob": round(pass_prob, 3),
                "supports_call": top_kind == int(actual_kind),
                "prefers_pass": top_kind == 0,
            }
        )
    return heads


def tile_suit_rank(tile):
    tile = base_tile(tile)
    if len(tile) < 2 or tile[-1] not in {"m", "p", "s"}:
        return None, None
    try:
        return tile[-1], int(tile[:-1])
    except ValueError:
        return None, None


def shape_tile_name(suit, rank):
    return f"{rank}{suit}"


def normalize_shape_hand(hand):
    if isinstance(hand, str):
        hand = hand.split()
    return [base_tile(tile) for tile in hand if tile]


def shape_counts(hand):
    return Counter(normalize_shape_hand(hand))


def suited_rank_counts(hand, suit):
    counts = Counter()
    for tile in normalize_shape_hand(hand):
        tile_suit, rank = tile_suit_rank(tile)
        if tile_suit == suit and rank is not None:
            counts[rank] += 1
    return counts


def consecutive_run_for_tile(hand, tile):
    tile = base_tile(tile)
    suit, rank = tile_suit_rank(tile)
    if suit is None:
        return []
    counts = suited_rank_counts(hand, suit)
    if not counts.get(rank):
        return []
    start = rank
    while start > 1 and counts.get(start - 1):
        start -= 1
    end = rank
    while end < 9 and counts.get(end + 1):
        end += 1
    return [shape_tile_name(suit, value) for value in range(start, end + 1)]


def remove_shape_tile(hand, tile):
    tile = base_tile(tile)
    remaining = normalize_shape_hand(hand)
    for index, item in enumerate(remaining):
        if item == tile:
            remaining.pop(index)
            break
    return remaining


def find_block_for_tile(hand, tile):
    tile = base_tile(tile)
    hand_tiles = normalize_shape_hand(hand)
    if tile not in hand_tiles:
        return [tile]
    
    suit, rank = tile_suit_rank(tile)
    if suit is None:
        return [t for t in hand_tiles if t == tile]
        
    suit_tiles = [t for t in hand_tiles if tile_suit_rank(t)[0] == suit]
    
    target_ranks = {rank}
    changed = True
    while changed:
        changed = False
        for t in suit_tiles:
            t_suit, t_rank = tile_suit_rank(t)
            if t_rank not in target_ranks:
                if any(abs(t_rank - r) <= 2 for r in target_ranks):
                    target_ranks.add(t_rank)
                    changed = True
                    
    block = [t for t in suit_tiles if tile_suit_rank(t)[1] in target_ranks]
    block.sort(key=lambda t: tile_suit_rank(t)[1])
    return block


def tile_shape_role(hand, tile):
    tile = base_tile(tile)
    block = find_block_for_tile(hand, tile)
    
    if len(block) == 1:
        suit, rank = tile_suit_rank(tile)
        if suit is None:
            return {"kind": "single honor", "block_tiles": block, "breaks_block": False}
        edge = rank in {1, 9}
        return {
            "kind": "isolated terminal" if edge else "isolated tile",
            "block_tiles": block,
            "breaks_block": False,
        }
        
    if len(block) == 2:
        if block[0] == block[1]:
            suit, rank = tile_suit_rank(tile)
            if suit is None:
                return {"kind": "honor pair", "block_tiles": block, "breaks_block": True}
            return {"kind": "pair", "block_tiles": block, "breaks_block": True}
        return {"kind": "two-tile block", "block_tiles": block, "breaks_block": True}
        
    if len(set(block)) == 1:
        suit, rank = tile_suit_rank(tile)
        if suit is None:
            return {"kind": "honor triplet", "block_tiles": block, "breaks_block": True}
        return {"kind": "triplet", "block_tiles": block, "breaks_block": True}
        
    ranks = sorted(list({tile_suit_rank(t)[1] for t in block}))
    if len(ranks) == len(block) and ranks[-1] - ranks[0] == len(block) - 1:
        return {"kind": "connected run", "block_tiles": block, "breaks_block": True}
        
    return {"kind": "complex block", "block_tiles": block, "breaks_block": True}



def discard_shape_effect(hand, discard):
    role = tile_shape_role(hand, discard)
    discard = base_tile(discard)
    remaining = remove_shape_tile(hand, discard)
    leftovers = [tile for tile in role.get("block_tiles", []) if tile != discard]
    effect = "removes"
    if role.get("breaks_block"):
        effect = "breaks"
    floating_after = []
    for tile in leftovers:
        tile_counts = shape_counts(remaining)
        if tile_counts.get(tile, 0) == 1 and tile_shape_role(remaining, tile).get("kind", "").startswith("isolated"):
            floating_after.append(tile)
    return {
        "tile": discard,
        "role": role["kind"],
        "block_tiles": role.get("block_tiles", []),
        "breaks_block": bool(role.get("breaks_block")),
        "floating_after": floating_after,
        "effect": effect,
    }


def build_shape_facts(hand, actual, naga):
    actual_effect = discard_shape_effect(hand, actual)
    naga_effect = discard_shape_effect(hand, naga)
    notes = []
    if actual_effect["breaks_block"] and not naga_effect["breaks_block"]:
        notes.append(
            f"LuckyJ breaks the {' '.join(actual_effect['block_tiles'])} block by cutting {actual_effect['tile']}; "
            f"Nishiki preserves that shape by cutting {naga_effect['tile']}."
        )
    elif actual_effect["breaks_block"] and naga_effect["breaks_block"]:
        notes.append(
            f"Both candidates break shape, but LuckyJ breaks {' '.join(actual_effect['block_tiles'])} "
            f"while Nishiki breaks {' '.join(naga_effect['block_tiles'])}."
        )
    elif not actual_effect["breaks_block"] and naga_effect["breaks_block"]:
        notes.append(
            f"LuckyJ removes {actual_effect['tile']} without breaking a block; Nishiki would break "
            f"{' '.join(naga_effect['block_tiles'])}."
        )

    if actual_effect.get("floating_after"):
        notes.append(f"After LuckyJ's discard, {' '.join(actual_effect['floating_after'])} is left floating.")
    if naga_effect.get("floating_after"):
        notes.append(f"After Nishiki's discard, {' '.join(naga_effect['floating_after'])} is left floating.")

    return {
        "actual": actual_effect,
        "nishiki": naga_effect,
        "notes": notes,
    }


def attach_shape_facts(case):
    if not case or case.get("kind") == "call" or not case.get("hand") or not case.get("actual") or not case.get("naga"):
        return case
    case["shape_facts"] = build_shape_facts(case["hand"], case["actual"], case["naga"])
    return case


def end_summary(start, target):
    msgs = start.get("end_msgs") or []
    if not msgs:
        return "No recorded hand result."
    if msgs[0].get("type") == "hora":
        parts = []
        for msg in msgs:
            actor = rel_seat(msg.get("actor"), target)
            fan = msg.get("fan")
            hu = msg.get("hu")
            delta = (msg.get("deltas") or [0, 0, 0, 0])[target]
            if msg.get("actor") == target:
                parts.append(f"self won {fan} han {hu} fu, delta {delta:+}")
            elif msg.get("target") == target:
                parts.append(f"self dealt into {actor}, delta {delta:+}")
            else:
                parts.append(f"{actor} won, self delta {delta:+}")
        return "; ".join(parts)
    delta = sum((msg.get("deltas") or [0, 0, 0, 0])[target] for msg in msgs)
    return f"draw, self delta {delta:+}"


def common_case(
    row,
    kyoku_index,
    pos,
    start,
    state,
    hands,
    discards,
    melds,
    reached,
    dora_markers,
    point_key,
    riichi_discard_indices=None,
):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    score = start.get("scores", [0, 0, 0, 0])[target]
    text = POINT_TEXT[point_key]
    return {
        "point": point_key,
        "game": row["idx"],
        "rank": row["rank"],
        "round": round_name(start),
        "kyoku_index": kyoku_index,
        "position": pos,
        "left": msg.get("left_hai_num"),
        "stage": base.stage_from_left(msg.get("left_hai_num")),
        "score": score,
        "score_band": score_band(score),
        "current_rank": current_rank(start, target),
        "report": row["report"],
        "paifu": row["paifu"],
        "room": row.get("room"),
        "room_code": row.get("room_code"),
        "table": table_context(start, target, hands, discards, melds, reached, dora_markers, state, riichi_discard_indices),
        "outcome": end_summary(start, target),
    }


def make_discard_case(
    row,
    kyoku_index,
    pos,
    start,
    state,
    hands,
    discards,
    melds,
    reached,
    dora_markers,
    point_key,
    riichi_discard_indices=None,
):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    actual = msg.get("real_dahai")
    model_head_rows = model_rows(state, actual)
    rows = [(row["top"], row["top_prob"], row["actual_prob"]) for row in model_head_rows]
    if not rows:
        return None
    naga = rows[0][0]
    try:
        visible = visible_counter(discards, melds, dora_markers)
        open_counts = [len(player_melds) for player_melds in melds]
        safety_context = (target, discards, reached, open_counts)
        actual_eval = ukeire_after_discard(hands[target], actual, visible, safety_context)
        naga_eval = ukeire_after_discard(hands[target], naga, visible, safety_context)
    except (KeyError, ValueError):
        return None
    if not actual_eval or not naga_eval:
        return None
    model_heads = []
    for model in model_head_rows:
        model_heads.append(
            {
                "key": model["key"],
                "label": model["label"],
                "top": model["top"],
                "top_prob": round(model["top_prob"], 3),
                "actual_prob": round(model["actual_prob"], 3),
                "matches_luckyj": model["matches_luckyj"],
                "matches_nishiki": same_tile(model["top"], naga),
                "danger": discard_threat_value(state, target, model["top"]),
            }
        )
    case = common_case(
        row,
        kyoku_index,
        pos,
        start,
        state,
        hands,
        discards,
        melds,
        reached,
        dora_markers,
        point_key,
        riichi_discard_indices,
    )
    case.update(
        {
            "kind": "discard",
            "hand": hand_string(hands[target]),
            "draw": msg.get("pai"),
            "actual": actual,
            "naga": naga,
            "actual_danger": discard_threat_value(state, target, actual),
            "naga_danger": discard_threat_value(state, target, naga),
            "actual_threat": discard_threat_profile(state, target, actual),
            "naga_threat": discard_threat_profile(state, target, naga),
            "actual_eval": actual_eval,
            "naga_eval": naga_eval,
            "naga_votes": [row[0] for row in rows],
            "model_heads": model_heads,
            "naga_prob": round(rows[0][1], 3),
            "actual_prob": round(rows[0][2], 3),
            "actual_tile_safety": safety_read(actual, target, discards, reached, open_counts),
            "kept_tile_safety": safety_read(naga, target, discards, reached, open_counts),
        }
    )
    return case


def make_yakuhai_cleanup_case(
    row,
    kyoku_index,
    pos,
    start,
    state,
    hands,
    discards,
    melds,
    reached,
    dora_markers,
    threats,
    riichi_discard_indices=None,
):
    case = make_discard_case(
        row,
        kyoku_index,
        pos,
        start,
        state,
        hands,
        discards,
        melds,
        reached,
        dora_markers,
        "point-13",
        riichi_discard_indices,
    )
    if not case:
        return None
    target = row["actor"]
    case["yakuhai_cleanup"] = {
        "threats": [
            {
                "seat": rel_seat(seat, target),
                "wind": seat_wind(start, seat),
                "melds": melds[seat][:],
            }
            for seat in threats
        ]
    }
    return case


def make_simple_discard_case(
    row,
    kyoku_index,
    pos,
    start,
    state,
    hands,
    discards,
    melds,
    reached,
    dora_markers,
    point_key,
    riichi_discard_indices=None,
):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    actual = msg.get("real_dahai")
    model_head_rows = model_rows(state, actual)
    rows = [(row["top"], row["top_prob"], row["actual_prob"]) for row in model_head_rows]
    if not rows:
        return None
    naga = rows[0][0]
    open_counts = [len(player_melds) for player_melds in melds]
    try:
        visible = visible_counter(discards, melds, dora_markers)
        safety_context = (target, discards, reached, open_counts)
        actual_eval = ukeire_after_discard(hands[target], actual, visible, safety_context)
        naga_eval = ukeire_after_discard(hands[target], naga, visible, safety_context)
    except (KeyError, ValueError):
        actual_eval = naga_eval = None
    case = common_case(
        row,
        kyoku_index,
        pos,
        start,
        state,
        hands,
        discards,
        melds,
        reached,
        dora_markers,
        point_key,
        riichi_discard_indices,
    )
    case.update(
        {
            "kind": "draw-tenpai",
            "hand": hand_string(hands[target]),
            "draw": msg.get("pai"),
            "actual": actual,
            "naga": naga,
            "actual_eval": actual_eval,
            "naga_eval": naga_eval,
            "actual_danger": discard_threat_value(state, target, actual),
            "naga_danger": discard_threat_value(state, target, naga),
            "actual_threat": discard_threat_profile(state, target, actual),
            "naga_threat": discard_threat_profile(state, target, naga),
            "naga_votes": [row[0] for row in rows],
            "model_heads": [
                {
                    "key": model["key"],
                    "label": model["label"],
                    "top": model["top"],
                    "top_prob": round(model["top_prob"], 3),
                    "actual_prob": round(model["actual_prob"], 3),
                    "matches_luckyj": model["matches_luckyj"],
                    "matches_nishiki": same_tile(model["top"], naga),
                    "danger": discard_threat_value(state, target, model["top"]),
                }
                for model in model_head_rows
            ],
            "naga_prob": round(rows[0][1], 3),
            "actual_prob": round(rows[0][2], 3),
            "actual_tile_safety": safety_read(actual, target, discards, reached, open_counts),
            "kept_tile_safety": safety_read(naga, target, discards, reached, open_counts),
        }
    )
    return case


def make_reach_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, riichi_discard_indices=None):
    reach_prob = max((p / 10000.0 for p in state.get("reach", [])), default=0.0)
    if reach_prob < 0.5:
        return None
    case = make_discard_case(
        row,
        kyoku_index,
        pos,
        start,
        state,
        hands,
        discards,
        melds,
        reached,
        dora_markers,
        "point-08",
        riichi_discard_indices,
    )
    if case:
        case["kind"] = "reach"
        case["reach_prob"] = round(reach_prob, 3)
        case["actual_reach"] = True
        case["naga_reach"] = True
        case["actual_eval"]["declares_reach"] = True
        case["actual_eval"]["reach_prob"] = round(reach_prob, 3)
        case["naga_eval"]["declares_reach"] = True
        case["naga_eval"]["reach_prob"] = round(reach_prob, 3)
    return case


def make_call_case(
    row,
    kyoku_index,
    pos,
    start,
    state,
    hands,
    discards,
    melds,
    reached,
    dora_markers,
    point_key,
    previous_state=None,
    riichi_discard_indices=None,
):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    if msg.get("actor") != target or msg.get("type") not in base.HURO_TYPES:
        return None
    case = common_case(
        row,
        kyoku_index,
        pos,
        start,
        state,
        hands,
        discards,
        melds,
        reached,
        dora_markers,
        point_key,
        riichi_discard_indices,
    )
    consumed = msg.get("consumed", [])
    shape = post_call_eval(hands[target], consumed, msg.get("real_dahai"))
    open_counts = [len(player_melds) for player_melds in melds]
    open_counts[target] += 1
    post_call_tiles = shape.get("hand_after", "").split()
    shape["kept_safety"] = retained_safety(post_call_tiles, target, discards, reached, open_counts)
    opponents = [seat for seat in range(4) if seat != target]
    riichi_seats = [seat for seat in opponents if reached[seat]]
    threat_seats = riichi_seats or [seat for seat in opponents if open_counts[seat] > 0]
    primary_threat = None
    if threat_seats:
        primary_threat = max(
            threat_seats,
            key=(
                (lambda seat: (int(seat == start.get("oya")), open_counts[seat], -((seat - target) % 4)))
                if riichi_seats
                else (lambda seat: (open_counts[seat], int(seat == start.get("oya")), -((seat - target) % 4)))
            ),
        )
        shape["primary_threat"] = {
            "seat": rel_seat(primary_threat, target),
            "kind": "riichi" if reached[primary_threat] else "open_hand",
            "open_melds": open_counts[primary_threat],
            "dealer": primary_threat == start.get("oya"),
        }

    reserve_reads = []
    seen_tiles = set()
    for tile in post_call_tiles:
        tile_key = base.tile_index(tile)
        if tile_key in seen_tiles:
            continue
        seen_tiles.add(tile_key)
        read = safety_read(tile, target, discards, reached, open_counts)
        target_read = next(
            (
                item
                for item in read.get("against", [])
                if item.get("seat") == primary_threat
                and (item.get("genbutsu_sources") or item.get("suji_sources"))
            ),
            None,
        )
        if target_read:
            reserve_reads.append((0 if target_read.get("genbutsu_sources") else 1, tile_key, read))
    reserve_reads.sort(key=lambda item: (item[0], item[1]))
    shape["primary_threat_reserve_reads"] = [item[2] for item in reserve_reads]
    shape["targeted_reserve_tiles"] = [item[2]["tile"] for item in reserve_reads]
    case.update(
        {
            "kind": "call",
            "call": msg.get("type"),
            "call_kind": msg.get("kind"),
            "called_tile": msg.get("pai"),
            "called_from": rel_seat(msg.get("target"), target),
            "consumed": consumed,
            "discard_after_call": msg.get("real_dahai"),
            "hand": hand_string(hands[target]),
            "post_call_meld": " ".join(consumed + ([msg.get("pai")] if msg.get("pai") else [])),
            "post_call_eval": shape,
        }
    )
    call_heads = huro_model_heads(previous_state, target, msg.get("kind"))
    if call_heads:
        case["call_model_heads"] = call_heads
    post_call_model_head_rows = model_rows(state, msg.get("real_dahai"))
    if post_call_model_head_rows:
        naga = post_call_model_head_rows[0]["top"]
        case.update(
            {
                "post_call_naga": naga,
                "post_call_naga_votes": [row["top"] for row in post_call_model_head_rows],
                "post_call_model_heads": [
                    {
                        "key": model["key"],
                        "label": model["label"],
                        "label_ja": model["label_ja"],
                        "top": model["top"],
                        "top_prob": round(model["top_prob"], 3),
                        "actual_prob": round(model["actual_prob"], 3),
                        "matches_luckyj": model["matches_luckyj"],
                        "matches_nishiki": same_tile(model["top"], naga),
                    }
                    for model in post_call_model_head_rows
                ],
                "post_call_naga_prob": round(post_call_model_head_rows[0]["top_prob"], 3),
                "post_call_actual_prob": round(post_call_model_head_rows[0]["actual_prob"], 3),
            }
        )
    return case


def call_has_naga_discrepancy(case):
    nishiki = model_head((case or {}).get("call_model_heads") or [], "nishiki")
    if not nishiki:
        return False
    return not nishiki.get("supports_call")


def call_has_teaching_disagreement(case):
    nishiki = model_head((case or {}).get("call_model_heads") or [], "nishiki")
    if not nishiki:
        return False
    # Same-call agreement with only a post-call discard split is too narrow for
    # a public teaching example.
    if nishiki.get("supports_call"):
        return False
    if nishiki.get("prefers_pass"):
        return True
    if nishiki.get("top_action") != (case or {}).get("call"):
        return True
    return False


def case_model_head(case, key):
    return next((head for head in case.get("model_heads") or [] if head.get("key") == key), None)


FALSE_PASS_WHEN_CALLING_PATTERNS = [
    re.compile(r"\bnishiki\b[^.。]{0,120}\b(?:passes|passed)\b", re.I),
    re.compile(r"\bnishiki\b[^.。]{0,120}\b(?:opts|chooses|prefers|would)\s+to\s+pass\b", re.I),
    re.compile(r"\bnishiki\b[^.。]{0,120}\b(?:opts\s+for|chooses|prefers|would)\s+(?:passing|a\s+pass|pass)\b", re.I),
    re.compile(r"\bnishiki\b[^.。]{0,120}\b(?:declines|declined)\s+the\s+call\b", re.I),
    re.compile(r"\bnishiki\b[^.。]{0,120}\b(?:keep|keeps|maintain|maintains|remain|remains|staying)\b[^.。]{0,80}\bclosed\b", re.I),
    re.compile(r"(?:nishiki|ニシキ|naga（nishiki）)[^。、.]{0,80}スルー", re.I),
    re.compile(r"(?:nishiki|ニシキ|naga（nishiki）)[^。、.]{0,80}(?:門前|メンゼン)[^。、.]{0,60}維持", re.I),
]
FALSE_AGREEMENT_PATTERNS = [
    re.compile(r"\bnishiki\b[^.。]{0,120}\b(?:completely|fully)\s+agree", re.I),
    re.compile(r"\bnishiki\b[^.。]{0,120}\bfully\s+support(?:s|ed)?\s+(?:this\s+)?(?:decision|play)", re.I),
    re.compile(r"\bnishiki\b[^.。]{0,120}\bmatching\b", re.I),
    re.compile(r"\bnishiki\b[^.。]{0,120}\bagrees?\s+with\s+this\s+(?:decision|play)", re.I),
    re.compile(r"\bnishiki\b[^.。]{0,160}\bagree(?:ing|s|d)?\s+on\s+both\b", re.I),
    re.compile(r"\bno\s+(?:naga\s+)?(?:discrepancy|difference)\b", re.I),
    re.compile(r"(?:nishiki|ニシキ|naga)[^。]{0,100}(?:完全に一致|全面的に一致|完全に同意|全面的に同意)", re.I),
]
FALSE_TENPAI_CALL_SHAPE_PATTERNS = [
    re.compile(r"\bLuckyJ\b[^.。]{0,180}\b(?<!from )(?:1-shanten|one[- ]?away)\b(?!\s+to\s+tenpai)", re.I),
    re.compile(r"\b(?:This call|The call|After the call|By discarding|By calling)\b[^.。]{0,180}\b(?<!from )(?:1-shanten|one[- ]?away)\b(?!\s+to\s+tenpai)", re.I),
    re.compile(r"(?:LuckyJ|この鳴き|鳴いた後|切ることで)[^。]{0,180}(?:一向聴(?!から)|1シャンテン(?!から)|テンパイまであと一歩)", re.I),
]


def route_line(name, detail):
    return f"{name}: {detail}"


def sequence_seed_for_route(counts, suit, start):
    tiles = [f"{rank}{suit}" for rank in range(start, start + 3)]
    present = [tile for tile in tiles if counts[tile]]
    missing = [tile for tile in tiles if not counts[tile]]
    if len(present) == 3:
        kind = "complete"
    elif len(present) == 2:
        kind = "two-tile seed"
    elif len(present) == 1:
        kind = "one-tile seed"
    else:
        kind = "absent"
    return {"present": present, "missing": missing, "kind": kind}


def detect_sanshoku_route_descriptions(counts):
    routes = []
    for start in range(1, 8):
        seeds = [sequence_seed_for_route(counts, suit, start) for suit in "mps"]
        present_counts = [len(seed["present"]) for seed in seeds]
        complete_count = sum(1 for seed in seeds if seed["kind"] == "complete")
        has_faraway_skeleton = min(present_counts) >= 1 and sum(present_counts) >= 6 and complete_count >= 1
        if all(count >= 2 for count in present_counts) or has_faraway_skeleton:
            route_tiles = f"{start}{start + 1}{start + 2}"
            parts = []
            for seed in seeds:
                if seed["kind"] == "complete":
                    parts.append(f"{' '.join(seed['present'])} complete")
                elif seed["kind"] == "one-tile seed":
                    parts.append(f"{' '.join(seed['present'])} only, needs {'/'.join(seed['missing'])}")
                else:
                    parts.append(f"{' '.join(seed['present'])} needs {'/'.join(seed['missing'])}")
            strength = "strong" if all(count >= 2 for count in present_counts) else "faraway"
            label = f"{route_tiles} sanshoku doujun seed"
            if strength == "faraway":
                label = f"faraway {label}"
            routes.append(f"{label}: " + "; ".join(parts))
    return routes


def detect_ittsu_route_descriptions(counts):
    routes = []
    for suit in "mps":
        seeds = [sequence_seed_for_route(counts, suit, start) for start in (1, 4, 7)]
        if all(len(seed["present"]) >= 2 for seed in seeds):
            parts = []
            for seed in seeds:
                if seed["kind"] == "complete":
                    parts.append(f"{' '.join(seed['present'])} complete")
                else:
                    parts.append(f"{' '.join(seed['present'])} needs {'/'.join(seed['missing'])}")
            routes.append(route_line("ittsu", f"{suit}-suit 123/456/789 seed: " + "; ".join(parts)))
    return routes


def detect_identical_sequence_route_descriptions(counts):
    routes = []
    iipeikou = []
    for suit in "mps":
        for start in range(1, 8):
            tiles = [f"{rank}{suit}" for rank in range(start, start + 3)]
            paired_ranks = [tile for tile in tiles if counts[tile] >= 2]
            if len(paired_ranks) == 3:
                iipeikou.append(f"{' '.join(tiles)} doubled")
            elif len(paired_ranks) == 2:
                missing = [tile for tile in tiles if counts[tile] < 2]
                iipeikou.append(f"{' '.join(paired_ranks)} paired, needs another {'/'.join(missing)}")
    if iipeikou:
        routes.append(route_line("iipeikou/ryanpeikou seed", "; ".join(iipeikou[:3])))
    return routes


def detect_sequence_route_descriptions(counts):
    return (
        detect_sanshoku_route_descriptions(counts)
        + detect_ittsu_route_descriptions(counts)
        + detect_identical_sequence_route_descriptions(counts)
    )


def route_needs_discarded_tile(route, tile):
    tile = base_tile(tile)
    if not tile:
        return False
    return bool(re.search(rf"\bneeds(?:\s+another)?\s+[^;,.。]*\b{re.escape(tile)}\b", route, re.I))


def route_terms_for_text(route):
    route_lower = route.lower()
    if route_lower.startswith("ittsu:"):
        return ["ittsu", "一気通貫", "イッツー"]
    if "sanshoku" in route_lower:
        return ["sanshoku", "三色"]
    if "iipeikou" in route_lower or "ryanpeikou" in route_lower:
        return ["iipeikou", "ryanpeikou", "一盃口", "二盃口"]
    return []


def sequence_routes_requiring_discarded_tile(case, tile):
    if not tile:
        return []
    counts = Counter(base_tile(item) for item in case.get("hand", "").split())
    discarded = base_tile(tile)
    counts[discarded] -= 1
    if counts[discarded] <= 0:
        del counts[discarded]
    return [
        route
        for route in detect_sequence_route_descriptions(counts)
        if route_needs_discarded_tile(route, tile)
    ]


def text_claims_discard_preserves_route(text, tile, route):
    tile = base_tile(tile)
    terms = route_terms_for_text(route)
    if not tile or not terms:
        return False
    term_re = "|".join(re.escape(term) for term in terms)
    tile_re = re.escape(f"[[{tile}]]")
    preserve_en = r"(?:preserv\w*|keep\w*|maintain\w*|retain\w*|kept|left[^.。]{0,40}(?:alive|intact))"
    preserve_ja = r"(?:温存|維持|残)"
    discard_tile_en = (
        rf"(?:discarding|discards?|cutting|cuts?|cut)"
        rf"(?:\s+(?:the|a|an|relatively|non-safe|safe|safer|terminal|outside|outer|"
        rf"genbutsu|suji|dangerous|central|middle|live|lone|single|floating|moderately|"
        rf"absolute|double-genbutsu|high-danger|low-danger))*\s+{tile_re}"
    )
    patterns = [
        rf"{discard_tile_en}[^.。]{{0,220}}{preserve_en}[^.。]{{0,160}}(?:{term_re})",
        rf"{discard_tile_en}[^.。]{{0,220}}(?:{term_re})[^.。]{{0,160}}{preserve_en}",
        rf"{tile_re}\s+(?:discard|cut|line)[^.。]{{0,160}}{preserve_en}[^.。]{{0,160}}(?:{term_re})",
        rf"{tile_re}\s+(?:discard|cut|line)[^.。]{{0,160}}(?:{term_re})[^.。]{{0,160}}{preserve_en}",
        rf"{tile_re}(?:を|の)?(?:切|打)[^。]{{0,220}}(?:{term_re})[^。]{{0,160}}{preserve_ja}",
        rf"(?:切|打)\s*{tile_re}[^。]{{0,220}}(?:{term_re})[^。]{{0,160}}{preserve_ja}",
    ]
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def cached_guide_has_discarded_route_claim(case, text):
    if case.get("kind") == "call":
        return False
    for tile in (case.get("actual"), case.get("naga")):
        for route in sequence_routes_requiring_discarded_tile(case, tile):
            if text_claims_discard_preserves_route(text, tile, route):
                return True
    return False


def route_family(route):
    lower = str(route or "").lower()
    if lower.startswith("ittsu:"):
        return "ittsu"
    if "sanshoku" in lower:
        return "sanshoku"
    if "iipeikou" in lower or "ryanpeikou" in lower:
        return "iipeikou"
    return None


def route_families_after_discard(case, tile):
    counts = Counter(base_tile(item) for item in case.get("hand", "").split())
    discarded = base_tile(tile)
    counts[discarded] -= 1
    if counts[discarded] <= 0:
        del counts[discarded]
    return {
        family
        for route in detect_sequence_route_descriptions(counts)
        if (family := route_family(route))
    }


def text_claims_asymmetric_shared_route(text, actual, naga, family):
    terms = {
        "ittsu": ["ittsu", "一気通貫", "イッツー"],
        "sanshoku": ["sanshoku", "三色"],
        "iipeikou": ["iipeikou", "ryanpeikou", "一盃口", "二盃口"],
    }[family]
    term_re = "|".join(re.escape(term) for term in terms)
    actual_re = re.escape(f"[[{base_tile(actual)}]]")
    naga_re = re.escape(f"[[{base_tile(naga)}]]")
    preserve = r"(?:preserv\w*|keep\w*|maintain\w*|retain\w*|kept|残|維持|温存)"
    lose = r"(?:sever\w*|destroy\w*|lose\w*|break\w*|close\w*|消|失|壊|断|閉ざ)"
    if re.search(rf"(?:both|shared|survives both|両方|共通)[^.。]{{0,120}}(?:{term_re})", text, re.I):
        return False
    patterns = [
        rf"(?:cut(?:ting)?|discard(?:ing)?)?[^.。]{{0,40}}{actual_re}[^.。]{{0,220}}{preserve}[^.。]{{0,160}}(?:{term_re})",
        rf"{actual_re}(?:を|の)?(?:切|打)[^。]{{0,220}}(?:{term_re})[^。]{{0,160}}{preserve}",
        rf"(?:cut(?:ting)?|discard(?:ing)?)?[^.。]{{0,40}}{naga_re}[^.。]{{0,220}}{lose}[^.。]{{0,160}}(?:{term_re})",
        rf"{naga_re}(?:を|の)?(?:切|打)[^。]{{0,220}}(?:{term_re})[^。]{{0,160}}{lose}",
    ]
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def cached_guide_has_asymmetric_shared_route_claim(case, text):
    if case.get("kind") == "call":
        return False
    actual = case.get("actual")
    naga = case.get("naga")
    shared = route_families_after_discard(case, actual) & route_families_after_discard(case, naga)
    return any(text_claims_asymmetric_shared_route(text, actual, naga, family) for family in shared)


def cached_call_guide_conflicts(case, cached_entry):
    if case.get("kind") != "call":
        return False
    nishiki = model_head(case.get("call_model_heads") or [], "nishiki")
    if not nishiki or not (nishiki.get("supports_call") or nishiki.get("top_action") == case.get("call")):
        return False
    text = " ".join(
        str((cached_entry.get(section) or {}).get(field, ""))
        for section in ("guide", "guide_ja")
        for field in ("read", "whyNot", "prompt", "answer")
    )
    text = (
        text.replace("Nishiki does not pass", "")
        .replace("Nishiki doesn't pass", "")
        .replace("Nishiki はスルーしていません", "")
        .replace("Nishikiはスルーしていません", "")
        .replace("ニシキはスルーしていません", "")
    )
    text = re.sub(r"\b(?:Hibakari|Kagashi)\b[^.。]*", "", text)
    text = re.sub(r"(?:ヒバカリ|カガシ)[^。]*", "", text)
    return any(pattern.search(text) for pattern in FALSE_PASS_WHEN_CALLING_PATTERNS)


def middle_suji_tile(tile):
    tile = base_tile(tile)
    if len(tile) != 2 or tile[1] not in {"m", "p", "s"}:
        return False
    try:
        return 4 <= int(tile[0]) <= 6
    except ValueError:
        return False


def iter_safety_reads(value):
    if isinstance(value, dict):
        if "tile" in value and "against" in value and "has_suji" in value:
            yield value
        for item in value.values():
            yield from iter_safety_reads(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_safety_reads(item)


def text_claims_suji_for_tile(text, tile):
    tokens = {f"[[{tile}]]", f"[[{base_tile(tile)}]]"}
    for token in tokens:
        for match in re.finditer(re.escape(token), text):
            window = text[max(0, match.start() - 80): match.end() + 80].lower()
            if "suji" in window or "筋" in window or "スジ" in window:
                return True
    return False


def cached_guide_has_false_suji_claim(case, text):
    for read in iter_safety_reads(case):
        tile = read.get("tile")
        if tile and middle_suji_tile(tile) and not read.get("has_suji") and text_claims_suji_for_tile(text, tile):
            return True
    return False


def approved_safety_tiles(case):
    approved = set((case.get("post_call_eval") or {}).get("targeted_reserve_tiles") or [])
    for read in iter_safety_reads(case):
        if read.get("safe_against_threat") and read.get("tile"):
            approved.add(base_tile(read["tile"]))
    return {base_tile(tile) for tile in approved if tile}


def cached_guide_has_unsupported_safety_claim(case, text):
    if re.search(r"(?<![\d.])0\.\d{2,4}(?!\d)", text):
        return True
    approved = approved_safety_tiles(case)
    claim = re.compile(
        r"defensive reserve|safety (?:anchor|reserve)|safe tile|low(?:est)? (?:max )?danger|"
        r"high safety|almost safe|near[- ]dead|守備(?:牌|材料|予備)|安全牌|高い安全度|低い危険度|ほぼ安全",
        re.I,
    )
    for match in claim.finditer(text):
        window = text[max(0, match.start() - 180): match.end() + 180]
        named = {base_tile(tile) for tile in re.findall(r"\[\[([^\]]+)\]\]", window)}
        if named and any(tile not in approved for tile in named):
            return True
        if not named and "reserve" in match.group(0).lower() and not approved:
            return True
    return False


def cached_guide_treats_danger_proxy_as_probability(text):
    patterns = (
        r"\bdeal[- ]?in\s+(?:probability|chance|rate|risk)\b",
        r"\b(?:probability|chance|rate|risk)\s+of\s+(?:a\s+)?deal[- ]?in\b",
        r"\b(?:maximum|max|peak|highest)\s+deal[- ]?in\s+(?:probability|chance|rate|risk)\b",
        r"放銃(?:率|確率|リスク)",
    )
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def cached_guide_uses_ambiguous_naga_threat_label(text):
    return bool(re.search(r"\bNAGA threat\b|NAGA脅威", text, re.I))


def point13_guide_lacks_pon_risk_acknowledgement(case, text):
    """Do not reuse yakuhai-timing prose that implies a discard denies the call.

    A correct Point 13 explanation must say plainly that releasing the honor offers
    the pon now.  This also invalidates older cached prose that described the discard
    as removing the opponent's yaku switch from the table.
    """
    if case.get("point") != "point-13":
        return False
    acknowledgements = (
        r"(?:accept|take|pay|offer|allow)\w*[^.。]{0,80}(?:pon|call) risk",
        r"offers?[^.。]{0,50}(?:the )?pon",
        r"(?:ポン|鳴き)(?:される|させる|の)?[^。]{0,50}(?:リスク|危険|覚悟)",
        r"(?:今|現時点)[^。]{0,50}(?:ポン|鳴か)",
        r"ポンリスク",
    )
    return not any(re.search(pattern, text, re.I) for pattern in acknowledgements)


def point13_guide_infers_hidden_distance(case, text):
    """Reject prose that treats missing visible yaku as known concealed distance."""
    if case.get("point") != "point-13":
        return False
    patterns = (
        r"(?:opponent|open hand|hand)\s+(?:is\s+)?still\s+incomplete",
        r"opponent\s+still\s+looks?\s+incomplete",
        r"相手がまだ未完成",
        r"相手がまだ遠い",
        r"副露手がまだ遠い",
    )
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def cached_guide_conflicts(case, cached_entry):
    text = " ".join(
        str((cached_entry.get(section) or {}).get(field, ""))
        for section in ("guide", "guide_ja")
        for field in ("read", "whyNot", "prompt", "answer")
    )
    if cached_guide_has_discarded_route_claim(case, text):
        return True
    if cached_guide_has_asymmetric_shared_route_claim(case, text):
        return True
    if cached_guide_has_false_suji_claim(case, text):
        return True
    if cached_guide_has_unsupported_safety_claim(case, text):
        return True
    if cached_guide_treats_danger_proxy_as_probability(text):
        return True
    if cached_guide_uses_ambiguous_naga_threat_label(text):
        return True
    if point13_guide_infers_hidden_distance(case, text):
        return True
    if point13_guide_lacks_pon_risk_acknowledgement(case, text):
        return True
    if case_has_naga_split(case) and any(pattern.search(text) for pattern in FALSE_AGREEMENT_PATTERNS):
        nishiki_call = model_head((case or {}).get("call_model_heads") or [], "nishiki")
        nishiki_post = model_head((case or {}).get("post_call_model_heads") or [], "nishiki")
        describes_post_call_split = bool(
            case.get("kind") == "call"
            and nishiki_call
            and nishiki_call.get("supports_call")
            and nishiki_post
            and not nishiki_post.get("matches_luckyj")
            and (
                re.search(r"(post-call|after (?:the )?call|鳴いた後|副露後)[^.。]{0,100}(?:split|differs?|instead|分かれ|別)", text, re.I)
                or re.search(r"(?:split|differs?|instead|分かれ|別)[^.。]{0,100}(post-call|after (?:the )?call|鳴いた後|副露後)", text, re.I)
            )
        )
        if describes_post_call_split:
            return cached_call_guide_conflicts(case, cached_entry)
        return True
    shape = case.get("post_call_eval") or {}
    if case.get("kind") == "call" and shape.get("shanten") is not None and shape.get("shanten") <= 0:
        if any(pattern.search(text) for pattern in FALSE_TENPAI_CALL_SHAPE_PATTERNS):
            return True
    return cached_call_guide_conflicts(case, cached_entry)


COMMENTARY_PATH = Path("data/replay_commentary.json")
_COMMENTARY = None
MISSING_COMMENTARY = []


def load_commentary():
    """The written commentary for each replay: question, read, and the case for the other line."""
    global _COMMENTARY
    if _COMMENTARY is None:
        try:
            _COMMENTARY = json.loads(COMMENTARY_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _COMMENTARY = {}
    return _COMMENTARY


def commentary_key(case):
    return f"{case.get('point')}_{case.get('game')}_{case.get('kyoku_index')}_{case.get('position')}"


def attach_example_guides(case):
    attach_shape_facts(case)
    written = load_commentary().get(commentary_key(case))
    if not written:
        MISSING_COMMENTARY.append(commentary_key(case))
        case["guide"], case["guide_ja"] = {}, {}
        return case
    for field, lang in (("guide", "en"), ("guide_ja", "ja")):
        part = written.get(lang) or {}
        case[field] = {"prompt": part.get("question", ""), "read": part.get("read", ""), "whyNot": part.get("other", "")}
    case["reading_order"] = written.get("order")
    return case


def candidate_signature(candidate):
    if not candidate:
        return None
    return (
        candidate.get("game"),
        candidate.get("kyoku_index"),
        candidate.get("position"),
        candidate.get("kind"),
    )


def selected_min_score(selected, point_key):
    rows = selected.get(point_key) or []
    if not rows:
        return float("-inf")
    return min(row["score"] for row in rows)


def wants_candidate(selected, point_key, score):
    rows = selected.get(point_key) or []
    return len(rows) < POOL_PER_POINT or score > selected_min_score(selected, point_key)


def safe_tile_class(tile):
    if not tile:
        return None
    try:
        return base.tile_class(tile)
    except (AttributeError, KeyError):
        return None


def opponents(case):
    table = case.get("table") or {}
    return [player for player in table.get("players", []) if player.get("seat") != "self"]


def opponent_open_count(case):
    return sum(1 for player in opponents(case) if player.get("melds"))


def opponent_meld_count(case):
    return sum(len(player.get("melds") or []) for player in opponents(case))


def opponent_riichi_count(case):
    return sum(1 for player in opponents(case) if player.get("reached"))


def active_threat_count(case):
    return sum(1 for player in opponents(case) if player.get("reached") or player.get("melds"))


def is_discard_case(case):
    return case.get("kind") in {"discard", "draw-tenpai", "reach"}


def numeric(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def is_live_safety_read(read):
    return bool(read and read.get("kind") and read.get("safe_against_threat"))


def safety_read_has_target(read):
    return bool(read and (read.get("kind") or read.get("has_sotogawa")))


def retained_safety_count(eval_item, key="total"):
    safety = (eval_item or {}).get("kept_safety") or {}
    return int(safety.get(key) or 0)


def eval_hand_tiles(eval_item):
    return str((eval_item or {}).get("hand_after") or "").split()


def eval_contains_tile_class(eval_item, classes):
    return any(safe_tile_class(tile) in classes for tile in eval_hand_tiles(eval_item))


def eval_tile_count(eval_item, tile):
    if not tile:
        return 0
    return sum(1 for item in eval_hand_tiles(eval_item) if same_tile(item, tile))


def tile_class_count_delta(actual_eval, naga_eval, key):
    return (actual_eval or {}).get(key, 0) - (naga_eval or {}).get(key, 0)


def branch_point_preserved(case):
    actual_eval = case.get("actual_eval") or {}
    naga_eval = case.get("naga_eval") or {}
    naga = case.get("naga")
    naga_cls = safe_tile_class(naga)
    if naga_cls == "honor" and tile_class_count_delta(actual_eval, naga_eval, "kept_honors") > 0:
        return True
    if naga_cls == "terminal" and tile_class_count_delta(actual_eval, naga_eval, "kept_terminals") > 0:
        return True
    if eval_tile_count(actual_eval, naga) >= 2:
        return True
    return safety_read_has_target(case.get("kept_tile_safety"))


def value_tradeoff_signal(case):
    actual_eval = case.get("actual_eval") or {}
    naga_eval = case.get("naga_eval") or {}
    return (
        tile_class_count_delta(actual_eval, naga_eval, "kept_honors") > 0
        or tile_class_count_delta(actual_eval, naga_eval, "kept_terminals") > 0
        or retained_safety_count(actual_eval, "against_threat") > retained_safety_count(naga_eval, "against_threat")
    )


def post_call_has_defensive_reserve(case):
    shape = case.get("post_call_eval") or {}
    return bool(shape.get("targeted_reserve_tiles"))


def point16_has_branch_difference(case):
    actual_eval = case.get("actual_eval") or {}
    naga_eval = case.get("naga_eval") or {}
    if actual_eval.get("shanten") != naga_eval.get("shanten"):
        return True
    if actual_eval.get("ukeire") != naga_eval.get("ukeire"):
        return True
    if set(actual_eval.get("effective") or []) != set(naga_eval.get("effective") or []):
        return True
    hand = case.get("hand") or ""
    if not hand:
        return False
    actual_shape = discard_shape_effect(hand, case.get("actual"))
    naga_shape = discard_shape_effect(hand, case.get("naga"))
    return (
        actual_shape.get("role"),
        tuple(actual_shape.get("block_tiles") or []),
        tuple(actual_shape.get("floating_after") or []),
    ) != (
        naga_shape.get("role"),
        tuple(naga_shape.get("block_tiles") or []),
        tuple(naga_shape.get("floating_after") or []),
    )


def call_has_purpose(case):
    heads = case.get("call_model_heads") or []
    shape = case.get("post_call_eval") or {}
    left = case.get("left") or 0
    if any(head.get("supports_call") for head in heads):
        return True
    if shape.get("shanten") is not None and shape.get("shanten") <= 1 and left <= 40:
        return True
    return bool(heads) and any((head.get("actual_kind_prob") or 0) >= 0.25 for head in heads)


def review_disagreement_signal(case):
    heads = case.get("model_heads") or []
    if not heads:
        return False
    nishiki = case_model_head(case, "nishiki")
    if nishiki and (nishiki.get("top_prob") or 0) - (nishiki.get("actual_prob") or 0) >= 0.12:
        return True
    tops = {head.get("top") for head in heads if head.get("top")}
    if len(tops) > 1:
        return True
    return any(head.get("matches_luckyj") and not head.get("matches_nishiki") for head in heads)


def stale_safety_spend(case):
    actual_read = case.get("actual_tile_safety") or {}
    actual_eval = case.get("actual_eval") or {}
    if not safety_read_has_target(actual_read):
        return False
    if is_live_safety_read(actual_read):
        return False
    return retained_safety_count(actual_eval, "against_threat") > 0


def honor_role_signal(case):
    if (case.get("yakuhai_cleanup") or {}).get("threats"):
        return True
    if safety_read_has_target(case.get("actual_tile_safety")):
        return True
    actual_d = numeric(case.get("actual_danger"))
    return active_threat_count(case) > 0 or (actual_d is not None and actual_d >= 0.03)


def case_has_naga_split(case):
    if case.get("kind") == "call":
        return call_has_naga_discrepancy(case)
    return bool(case.get("naga") and case.get("actual") and not same_tile(case.get("naga"), case.get("actual")))


def case_has_hibakari_split(case):
    if case.get("kind") == "call":
        hibakari = model_head((case or {}).get("call_model_heads") or [], "hibakari")
        if not hibakari:
            return False
        if not hibakari.get("supports_call"):
            return True
        post_hibakari = model_head((case or {}).get("post_call_model_heads") or [], "hibakari")
        return bool(post_hibakari) and not post_hibakari.get("matches_luckyj")
    hibakari = model_head((case or {}).get("model_heads") or [], "hibakari")
    return bool(hibakari) and not hibakari.get("matches_luckyj")


NEXT_DORA = {**{f"{n}{s}": f"{n % 9 + 1}{s}" for s in "mps" for n in range(1, 10)},
             "E": "S", "S": "W", "W": "N", "N": "E", "P": "F", "F": "C", "C": "P"}


def case_round_wind(case):
    return "S" if str(case.get("round", "")).startswith("South") else "E"


def case_round_number(case):
    match = re.match(r"^\w+ (\d)", str(case.get("round", "")))
    return int(match.group(1)) if match else None


def case_is_all_last(case):
    return case_round_wind(case) == "S" and case_round_number(case) == 4


def case_is_late_game(case):
    # South rounds, or East 4 when the half-game turns.
    return case_round_wind(case) == "S" or case_round_number(case) == 4


def case_is_dealer(case):
    return (case.get("table") or {}).get("dealer") == "self"


def case_value_units(tiles, case):
    """Dora, red fives, and yakuhai pairs in a hand: the material a hand keeps for points."""
    table = case.get("table") or {}
    dora = Counter(NEXT_DORA.get(base_tile(marker)) for marker in table.get("dora_markers") or [])
    self_wind = next((row.get("wind") for row in table.get("scores") or [] if row.get("seat") == "self"), None)
    yakuhai = DRAGONS | {case_round_wind(case), self_wind}
    counts = Counter(base_tile(tile) for tile in tiles)
    value = sum(dora.get(base_tile(tile), 0) + (1 if str(tile).endswith("r") else 0) for tile in tiles)
    value += sum(1 for tile, count in counts.items() if tile in yakuhai and count >= 2)
    return value


def case_unseen_counts(case):
    """Copies of each tile LuckyJ cannot see: not in its hand, a river, a meld or the dora indicators."""
    table = case.get("table") or {}
    seen = Counter(base_tile(tile) for tile in str(case.get("hand") or "").split())
    for player in table.get("players") or []:
        for tile in player.get("discards") or []:
            tile = tile if isinstance(tile, str) else (tile or {}).get("tile")
            if tile:
                seen[base_tile(tile)] += 1
        for meld in player.get("melds") or []:
            seen.update(base_tile(tile) for tile in meld_tiles(meld))
    seen.update(base_tile(marker) for marker in table.get("dora_markers") or [])
    return Counter({tile: max(0, 4 - count) for tile, count in seen.items()})


def case_value_potential(tiles, case):
    """Dora, red fives and yakuhai a hand can still turn into points. A yakuhai single counts only while
    it can still pair: two or more copies unseen. A singleton with one copy left is not value."""
    table = case.get("table") or {}
    dora = Counter(NEXT_DORA.get(base_tile(marker)) for marker in table.get("dora_markers") or [])
    self_wind = next((row.get("wind") for row in table.get("scores") or [] if row.get("seat") == "self"), None)
    yakuhai = DRAGONS | {case_round_wind(case), self_wind}
    held = Counter(base_tile(tile) for tile in tiles)
    unseen = case_unseen_counts(case)
    value = sum(dora.get(base_tile(tile), 0) + (1 if str(tile).endswith("r") else 0) for tile in tiles)
    value += sum(count for tile, count in held.items() if tile in yakuhai and (count >= 2 or unseen.get(tile, 4) >= 2))
    return value


def line_delta(case):
    """How LuckyJ's line differs from Nishiki's: positive means LuckyJ's line has more of it."""
    actual_eval = case.get("actual_eval") or {}
    naga_eval = case.get("naga_eval") or {}
    actual_d = numeric(case.get("actual_danger"))
    naga_d = numeric(case.get("naga_danger"))
    shanten_a = actual_eval.get("shanten")
    shanten_n = naga_eval.get("shanten")
    return {
        "ukeire": (actual_eval.get("ukeire") or 0) - (naga_eval.get("ukeire") or 0),
        "shanten": (shanten_a - shanten_n) if shanten_a is not None and shanten_n is not None else 0,
        "danger": round(actual_d - naga_d, 4) if actual_d is not None and naga_d is not None else 0.0,
        "safety": retained_safety_count(actual_eval, "against_threat") - retained_safety_count(naga_eval, "against_threat"),
        "value": case_value_units(eval_hand_tiles(actual_eval), case) - case_value_units(eval_hand_tiles(naga_eval), case),
        "accepts_differ": set(actual_eval.get("effective") or []) != set(naga_eval.get("effective") or []),
        "honors": tile_class_count_delta(actual_eval, naga_eval, "kept_honors"),
        "terminals": tile_class_count_delta(actual_eval, naga_eval, "kept_terminals"),
    }


def placement_job(case):
    """The score job a Point 01 frame shows, or None when the two lines do not show one.

    protect: LuckyJ leads and takes the safer line at a real cost in shape.
    value:   LuckyJ is behind late and keeps dora, red fives or a yakuhai pair at a cost.
    push:    LuckyJ is behind late and takes the faster line although it is the hotter tile.
    """
    if case.get("kind") != "discard":
        return None
    rank = case.get("current_rank")
    delta = line_delta(case)
    cost = delta["ukeire"] < 0 or delta["shanten"] > 0
    if rank == 1 and (case.get("score") or 0) >= 33000:
        safer = delta["danger"] <= -0.03 or delta["safety"] > 0
        return "protect" if safer and cost and delta["danger"] <= 0.02 else None
    behind = rank in {3, 4} or (rank == 2 and case_is_all_last(case))
    if not (behind and case_is_late_game(case)):
        return None
    if delta["value"] > 0 and (cost or delta["danger"] >= 0.03):
        return "value"
    if delta["danger"] >= 0.03 and (delta["ukeire"] > 0 or delta["shanten"] < 0):
        return "push"
    return None


def has_named_difference(point_key, case):
    """A replay earns its place only when the two lines differ in something the reader can see:
    speed, safety, or value. Lines that only swap which tiles they accept teach little."""
    if case.get("kind") not in {"discard", "draw-tenpai"}:
        return True
    if case.get("kind") == "draw-tenpai" and not (case.get("actual_eval") and case.get("naga_eval")):
        return False
    delta = line_delta(case)
    strong = (
        abs(delta["ukeire"]) >= 2
        or delta["shanten"] != 0
        or abs(delta["danger"]) >= 0.03
        or delta["safety"] != 0
        or delta["value"] != 0
    )
    if point_key == "point-02":
        # The branch point is only a lesson when keeping it costs something now.
        return (delta["ukeire"] < 0 or delta["shanten"] > 0) and (delta["honors"] > 0 or delta["terminals"] > 0 or delta["accepts_differ"])
    if point_key == "point-16":
        return strong or delta["accepts_differ"]
    if point_key == "point-06":
        # Buying value means LuckyJ's line keeps more dora, red fives or yakuhai than Nishiki's.
        actual_tiles = eval_hand_tiles(case.get("actual_eval"))
        naga_tiles = eval_hand_tiles(case.get("naga_eval"))
        return case_value_potential(actual_tiles, case) > case_value_potential(naga_tiles, case)
    return strong


def threat_kind(case):
    players = (case.get("table") or {}).get("players") or []
    others = [player for player in players if player.get("seat") != "self"]
    if any(player.get("reached") for player in others):
        return "riichi"
    if any(player.get("melds") for player in others):
        return "open"
    return "quiet"


def point_candidate_eligible(point_key, case):
    if not case:
        return False

    kind = case.get("kind")
    actual_cls = safe_tile_class(case.get("actual"))
    naga_cls = safe_tile_class(case.get("naga"))
    stage = case.get("stage")
    left = case.get("left") or 0
    actual_d = numeric(case.get("actual_danger"))
    naga_d = numeric(case.get("naga_danger"))
    actual_eval = case.get("actual_eval") or {}
    naga_eval = case.get("naga_eval") or {}
    kept_read = case.get("kept_tile_safety") or {}
    score = case.get("score") or 0
    rank = case.get("current_rank") or case.get("rank")

    if kind == "call":
        if not call_has_naga_discrepancy(case):
            return False
    elif kind in {"discard", "draw-tenpai", "reach"}:
        if not case_has_naga_split(case):
            return False
    if point_key in HIBAKARI_SPLIT_POINTS and not case_has_hibakari_split(case):
        return False
    if not has_named_difference(point_key, case):
        return False

    if point_key == "point-01":
        job = placement_job(case)
        if job:
            case["placement_job"] = job
        return job is not None
    if point_key == "point-02":
        return (
            kind == "discard"
            and stage == "early"
            and opponent_riichi_count(case) == 0
            and actual_cls == "simple"
            and naga_cls in {"honor", "terminal"}
            and branch_point_preserved(case)
        )
    if point_key == "point-03":
        shape = case.get("post_call_eval") or {}
        return kind == "call" and case.get("discard_after_call") not in {None, "?"} and call_has_teaching_disagreement(case) and (shape.get("shanten") is None or shape.get("shanten") <= 1 or left <= 24)
    if point_key == "point-04":
        post_discard_cls = safe_tile_class(case.get("discard_after_call"))
        shape = case.get("post_call_eval") or {}
        return (
            kind == "call"
            and case.get("discard_after_call") not in {None, "?"}
            and call_has_teaching_disagreement(case)
            and post_call_has_defensive_reserve(case)
            and (shape.get("shanten") is None or shape.get("shanten") > 0)
            and (active_threat_count(case) > 0 or post_discard_cls in {"honor", "terminal"})
        )
    if point_key == "point-05":
        return (
            kind == "discard"
            and opponent_riichi_count(case) == 0
            and opponent_meld_count(case) <= 1
            and stage in {"early", "middle"}
            and actual_cls == "simple"
            and naga_cls in {"honor", "terminal"}
            and actual_d is not None
            and naga_d is not None
            and actual_d >= naga_d
            and actual_eval.get("shanten") is not None
            and actual_eval.get("shanten") >= 1
        )
    if point_key == "point-06":
        return (
            kind == "discard"
            and stage == "early"
            and opponent_riichi_count(case) == 0
            and case_has_naga_split(case)
            and actual_eval.get("ukeire") is not None
            and naga_eval.get("ukeire") is not None
            and actual_eval.get("ukeire") < naga_eval.get("ukeire")
            and (score < 30000 or rank in {3, 4})
            and value_tradeoff_signal(case)
        )
    if point_key == "point-08":
        return kind == "reach" and case.get("actual_reach") and (case.get("reach_prob") is None or case.get("reach_prob") >= 0.5)
    if point_key == "point-09":
        return (
            kind == "discard"
            and case_has_naga_split(case)
            and active_threat_count(case) > 0
            and actual_d is not None
            and naga_d is not None
            and actual_d < 0.02
            and naga_d > 0.08
        )
    if point_key == "point-10":
        return kind == "discard" and stage == "late" and left <= 24 and case_has_naga_split(case)
    if point_key == "point-11":
        return kind == "draw-tenpai" and stage == "late" and left <= 24 and "draw" in str(case.get("outcome", ""))
    if point_key == "point-12":
        return is_discard_case(case) and case_has_naga_split(case) and review_disagreement_signal(case)
    if point_key == "point-13":
        return (
            kind == "discard"
            and stage == "early"
            and opponent_riichi_count(case) == 0
            and actual_cls == "honor"
            and naga_cls != "honor"
            and bool((case.get("yakuhai_cleanup") or {}).get("threats"))
        )
    if point_key == "point-14":
        return kind == "discard" and is_live_safety_read(kept_read)
    if point_key == "point-15":
        return (
            kind == "discard"
            and active_threat_count(case) > 0
            and actual_d is not None
            and actual_d <= 0.15
            and case_has_naga_split(case)
            and stale_safety_spend(case)
        )
    if point_key == "point-16":
        return (
            kind == "discard"
            and stage in {"middle", "late"}
            and actual_cls == "terminal"
            and naga_cls == "simple"
            and point16_has_branch_difference(case)
        )
    if point_key == "point-18":
        return kind == "discard" and actual_cls == "honor" and honor_role_signal(case)
    return True


def baseline_example_bonus(candidate):
    if not candidate or candidate.get("kind") not in {"discard", "draw-tenpai", "reach"}:
        if candidate and candidate.get("kind") == "call" and not candidate.get("call_model_heads"):
            return -1000.0
        if candidate and candidate.get("kind") == "call" and candidate.get("call_model_heads"):
            return 2.0
        return 0.0
    heads = candidate.get("model_heads") or []
    hibakari = next((head for head in heads if head.get("key") == "hibakari"), None)
    if not hibakari:
        return 0.0
    if hibakari.get("matches_luckyj"):
        return 5.0
    if not hibakari.get("matches_nishiki"):
        return 2.0
    return 0.0


# Points whose teaching value comes from the disagreement itself; the "no engine backs
# LuckyJ" penalty does not apply to them.
DISAGREEMENT_POINTS = {"point-12"}

_MORTAL_VERDICTS = None


def load_mortal_verdicts():
    """Map (log_id, kyoku_index, left, kind-ish action) -> the prior Mortal record from the
    previous site/mortal-analysis.json run, so re-selection can prefer examples where the
    second engine already backed LuckyJ without re-running the replay."""
    global _MORTAL_VERDICTS
    if _MORTAL_VERDICTS is not None:
        return _MORTAL_VERDICTS
    verdicts = {}
    if MORTAL_PATH.exists():
        try:
            data = json.loads(MORTAL_PATH.read_text())
            for entries in (data.get("points") or {}).values():
                for item in entries:
                    sig = item.get("input_signature") or []
                    if len(sig) == 7:
                        # drop the point key: the verdict is a property of the game frame
                        verdicts[tuple(sig[1:])] = item
        except (json.JSONDecodeError, OSError):
            pass
    _MORTAL_VERDICTS = verdicts
    return verdicts


def log_id_from_report(candidate):
    paifu = candidate.get("paifu") or ""
    match = re.search(r"log=([0-9a-zA-Z-]+)", paifu)
    return match.group(1) if match else None


def mortal_frame_signature(candidate):
    kind = candidate.get("kind")
    if kind == "call":
        action_type = str(candidate.get("call", "")).lower()
        action_tile = candidate.get("called_tile")
        post_discard = candidate.get("discard_after_call")
    elif kind == "reach":
        action_type = "reach"
        action_tile = candidate.get("actual")
        post_discard = None
    else:
        action_type = "dahai"
        action_tile = candidate.get("actual")
        post_discard = None
    return (
        log_id_from_report(candidate),
        candidate.get("kyoku_index"),
        candidate.get("left"),
        action_type,
        action_tile,
        post_discard,
    )


def engine_backing(candidate):
    """Return exact NAGA support count and the matching prior Mortal record, when any."""
    kind = candidate.get("kind")
    if kind == "call":
        call_heads = candidate.get("call_model_heads") or []
        post_heads = candidate.get("post_call_model_heads") or []
        naga = sum(
            head.get("supports_call")
            and (model_head(post_heads, head.get("key")) or {}).get("matches_luckyj", True)
            for head in call_heads
        )
    else:
        naga = sum(bool(head.get("matches_luckyj")) for head in candidate.get("model_heads") or [])
    mortal = load_mortal_verdicts().get(mortal_frame_signature(candidate))
    return naga, mortal


def example_evidence_tier(candidate):
    naga_count, mortal_item = engine_backing(candidate)
    mortal_agrees = bool((mortal_item or {}).get("mortal_agrees_luckyj"))
    mortal_type = ((mortal_item or {}).get("mortal") or {}).get("type")
    declaration_only = candidate.get("kind") == "reach" and mortal_type == "reach"
    full_mortal_support = mortal_agrees and not declaration_only
    if full_mortal_support and naga_count >= 1:
        return "corroborated"
    if full_mortal_support or naga_count >= 2:
        return "split_supported"
    if naga_count >= 1:
        return "contested"
    if mortal_item is None:
        return "unverified"
    return "unsupported"


def defensibility_bonus(point_key, candidate):
    """Prefer showcase examples that at least one independent engine endorses.

    A playbook example teaches "copy this line"; an example where every engine prefers the
    other tile teaches the opposite lesson no matter how good the prose is. point-12 is
    exempt because its subject is the disagreement itself."""
    if point_key in DISAGREEMENT_POINTS:
        return 0.0
    tier = example_evidence_tier(candidate)
    return {
        "corroborated": 8.0,
        "split_supported": 6.0,
        "contested": 3.0,
        "unverified": 0.0,
        "unsupported": -100.0,
    }[tier]


def add(selected, used, point_key, candidate, score=0.0):
    sig = candidate_signature(candidate)
    if not candidate or not sig or not point_candidate_eligible(point_key, candidate):
        return
    tier = example_evidence_tier(candidate)
    # A showcase that tells readers to copy a line needs at least one model-side
    # endorsement. Unknown Mortal status plus zero NAGA support is not enough; keep
    # those frames for Point 12's disagreement lab instead of cycling them through
    # prescriptive points as new Mortal replays arrive.
    if tier in {"unsupported", "unverified"} and point_key not in DISAGREEMENT_POINTS:
        return
    candidate["evidence_tier"] = tier
    score += baseline_example_bonus(candidate)
    score += defensibility_bonus(point_key, candidate)
    point_seen = used.setdefault(point_key, set())
    if sig in point_seen:
        return
    rows = selected.setdefault(point_key, [])
    if len(rows) >= POOL_PER_POINT:
        worst_idx, worst = min(enumerate(rows), key=lambda item: item[1]["score"])
        if score <= worst["score"]:
            return
        rows.pop(worst_idx)
        point_seen.discard(candidate_signature(worst["case"]))
    rows.append({"score": score, "case": candidate})
    point_seen.add(sig)


def add_best(selected, used, scores, point_key, candidate, score):
    add(selected, used, point_key, candidate, score)


def situation_features(case):
    return {
        "rank": case.get("current_rank"),
        "stage": case.get("stage"),
        "threat": threat_kind(case),
        "job": case.get("placement_job"),
        "dealer": case_is_dealer(case),
        "wind": case_round_wind(case),
        "all_last": case_is_all_last(case),
        "tiles": (base_tile(case.get("actual")), base_tile(case.get("naga"))),
        "classes": (safe_tile_class(case.get("actual")), safe_tile_class(case.get("naga"))),
        "call": case.get("call") if case.get("kind") == "call" else None,
    }


# How much a repeat costs, per feature. The same pair of tiles twice is the worst repeat;
# the same placement, threat and stage are next.
VARIETY_WEIGHTS = {
    "tiles": 1.5,
    "rank": 0.9,
    "job": 0.8,
    "threat": 0.6,
    "stage": 0.5,
    "call": 0.4,
    "all_last": 0.3,
    "dealer": 0.25,
    "wind": 0.2,
    "classes": 0.15,
}
VARIETY_PRICE = 0.35
# Below this, the best remaining replay mostly repeats ones already chosen, so the point stops early.
VARIETY_STOP = -0.5


def pick_varied(rows, seen_source_frames, point_key):
    """Choose a few replays that each show a different table: greedy by model score, with a price
    on every feature an earlier pick already showed. One replay per game. Stops early, once it has
    MIN_EXAMPLES_PER_POINT, when the best remaining replay would mostly repeat the earlier ones."""
    ordered = [
        row
        for row in sorted(rows, key=lambda row: row["score"], reverse=True)
        if candidate_signature(row["case"]) not in seen_source_frames
        and ("hand", row["case"].get("game"), row["case"].get("kyoku_index")) not in seen_source_frames
    ][:200]
    if not ordered:
        return []
    quality = {id(row): 1.0 - index / max(1, len(ordered) - 1) for index, row in enumerate(ordered)}
    features = {id(row): situation_features(row["case"]) for row in ordered}
    # A feature that every candidate shares (Point 02 is always early) cannot vary, so it costs nothing.
    varying = {
        key for key in VARIETY_WEIGHTS
        if len({repr(features[id(row)][key]) for row in ordered}) > 1
    }
    picked = []
    games = set()
    situations = set()
    seen = {key: Counter() for key in VARIETY_WEIGHTS}
    while len(picked) < EXAMPLES_PER_POINT:
        best = None
        best_value = None
        for row in ordered:
            if row in picked or row["case"].get("game") in games:
                continue
            feats = features[id(row)]
            # Two replays in one chapter never show the same seat, stage and threat.
            if (feats["rank"], feats["stage"], feats["threat"]) in situations:
                continue
            penalty = sum(VARIETY_WEIGHTS[key] * seen[key][repr(feats[key])] for key in varying)
            value = quality[id(row)] - VARIETY_PRICE * penalty
            if best_value is None or value > best_value:
                best, best_value = row, value
        if best is None:
            break
        if len(picked) >= MIN_EXAMPLES_PER_POINT and best_value < VARIETY_STOP:
            break
        picked.append(best)
        games.add(best["case"].get("game"))
        situations.add((features[id(best)]["rank"], features[id(best)]["stage"], features[id(best)]["threat"]))
        for key in VARIETY_WEIGHTS:
            seen[key][repr(features[id(best)][key])] += 1
    return picked


def finalize_examples(selected):
    output = {}
    seen_source_frames = set()
    # Reserve hand-pinned PREFERRED_CASES frames (score bonus >= 1000) for their own point
    # so an earlier-sorted point cannot claim the same source frame first.
    reserved = {}
    for point_key, rows in selected.items():
        for row in rows:
            if row["score"] >= 1000.0:
                sig = candidate_signature(row["case"])
                if sig:
                    reserved[sig] = point_key
    for point_key in sorted(POINT_TEXT):
        rows = selected.get(point_key, [])
        rows = [
            row
            for row in rows
            if reserved.get(candidate_signature(row["case"]), point_key) == point_key
        ]
        rows = sorted(rows, key=lambda row: row["score"], reverse=True)
        examples = []
        for row in pick_varied(rows, seen_source_frames, point_key):
            case = row["case"]
            index = len(examples) + 1
            case["example_index"] = index
            case["example_score"] = round(row["score"], 4)
            attach_example_guides(case)
            examples.append(case)
            seen_source_frames.add(candidate_signature(case))
            # A hand appears once in the book, even at a different turn.
            seen_source_frames.add(("hand", case.get("game"), case.get("kyoku_index")))
        if examples and all(case.get("reading_order") for case in examples):
            examples.sort(key=lambda case: case["reading_order"])
            for index, case in enumerate(examples, 1):
                case["example_index"] = index
        for case in examples:
            case.pop("reading_order", None)
        if examples:
            output[point_key] = examples
    return output


def preferred_bonus(point_key, row, kyoku_index, left, actual, naga):
    for item in PREFERRED_CASES.get(point_key, []):
        if (
            item["game"] == row["idx"]
            and item["kyoku_index"] == kyoku_index
            and item["left"] == left
            and same_tile(item["actual"], actual)
            and same_tile(item["naga"], naga)
        ):
            return 1000.0
    return 0.0


def tile_count(hand, tile):
    try:
        idx = tile_id(tile)
    except KeyError:
        return 0
    return sum(1 for item in hand if tile_id(item) == idx)


def post_call_eval(hand, consumed, discard_after_call):
    concealed = list(hand)
    for tile in consumed or []:
        remove_tile(concealed, tile)
    if discard_after_call:
        remove_tile(concealed, discard_after_call)
    try:
        shanten = SHANTEN.calculate_shanten(counts_34(concealed), use_chiitoitsu=False, use_kokushi=False)
    except ValueError:
        shanten = None
    return {
        "shanten": shanten,
        "hand_after": hand_string(concealed),
        "pair_like_tiles": sum(1 for count in Counter(tile_id(tile) for tile in concealed).values() if count >= 2),
    }


def call_score_adjustment(case):
    shape = case.get("post_call_eval") or {}
    shanten = shape.get("shanten")
    left = case.get("left") or 0
    if shanten is None:
        return 0.0
    if shanten <= 0:
        return 1.2
    if shanten == 1 and left > 6:
        return 0.35
    if left <= 1:
        return -0.75
    return 0.0


def try_discard_points(
    selected,
    used,
    scores,
    row,
    kyoku_index,
    pos,
    start,
    state,
    hands,
    discards,
    melds,
    reached,
    dora_markers,
    open_melds,
    riichi_discard_indices=None,
    actual_declares_reach=False,
):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    if open_melds[target] or msg.get("reached"):
        return
    actual = msg.get("real_dahai")
    rows = top_rows(state, actual)
    if not rows:
        return

    naga = rows[0][0]
    if naga == actual and "point-08" in selected:
        return
    left = msg.get("left_hai_num") or 0
    stage = base.stage_from_left(left)
    score = start.get("scores", [0, 0, 0, 0])[target]
    actual_cls = base.tile_class(actual)
    naga_cls = base.tile_class(naga)
    actual_d = discard_threat_value(state, target, actual)
    naga_d = discard_threat_value(state, target, naga)
    public_visible = visible_counter(discards, melds, dora_markers)
    active_threats = sum(1 for seat in range(4) if seat != target and (reached[seat] or open_melds[seat]))
    actual_read = safety_read(actual, target, discards, reached, open_melds)
    naga_read = safety_read(naga, target, discards, reached, open_melds)
    gap = rows[0][1] - rows[0][2]

    if actual_declares_reach and "reach" in state:
        score_value = 0.4 + gap + (max((p / 10000.0 for p in state.get("reach", [])), default=0.0) / 2)
        if wants_candidate(selected, "point-08", score_value):
            add(
                selected,
                used,
                "point-08",
                make_reach_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    riichi_discard_indices,
                ),
                score_value,
            )

    rank_now = current_rank(start, target)
    late_game = start.get("bakaze") == "S" or start.get("kyoku") == 4
    all_last = start.get("bakaze") == "S" and start.get("kyoku") == 4
    placement_seat = (
        (rank_now == 1 and score >= 33000)
        or (rank_now in {3, 4} and late_game)
        or (rank_now == 2 and all_last)
    )
    if placement_seat and actual_d is not None and naga_d is not None:
        score_value = gap + abs(naga_d - actual_d) + (0.2 if stage in {"middle", "late"} else 0.0)
        if wants_candidate(selected, "point-01", score_value):
            add(
                selected,
                used,
                "point-01",
                make_discard_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    "point-01",
                    riichi_discard_indices,
                ),
                score_value,
            )

    if stage == "early" and actual_cls == "simple" and naga_cls in {"honor", "terminal"}:
        score_value = gap + (0.25 if naga_read["kind"] else 0.0) + (0.2 if tile_count(hands[target], naga) >= 2 else 0.0)
        if wants_candidate(selected, "point-02", score_value):
            add(
                selected,
                used,
                "point-02",
                make_discard_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    "point-02",
                    riichi_discard_indices,
                ),
                score_value,
            )

    if actual_cls == "simple" and naga_cls in {"honor", "terminal"} and (actual_d is None or naga_d is None or actual_d >= naga_d):
        score_value = gap + (max(0.0, actual_d - naga_d) if actual_d is not None and naga_d is not None else 0.0)
        if stage == "middle":
            score_value += 0.15
        if wants_candidate(selected, "point-05", score_value):
            add(
                selected,
                used,
                "point-05",
                make_discard_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    "point-05",
                    riichi_discard_indices,
                ),
                score_value,
            )

    if stage == "early" and naga != actual:
        score_value = gap + (0.2 if score < 25000 else 0.0)
        if wants_candidate(selected, "point-06", score_value):
            case = make_discard_case(
                row,
                kyoku_index,
                pos,
                start,
                state,
                hands,
                discards,
                melds,
                reached,
                dora_markers,
                "point-06",
                riichi_discard_indices,
            )
            if case and case["actual_eval"]["ukeire"] < case["naga_eval"]["ukeire"] and case["actual_eval"]["kept_honors"] >= case["naga_eval"]["kept_honors"]:
                add(selected, used, "point-06", case, score_value)

    if actual_d is not None and naga_d is not None and actual_d < 0.02 and naga_d > 0.08:
        score_value = gap + (naga_d - actual_d) + 0.15 * active_threats
        if wants_candidate(selected, "point-09", score_value):
            add(
                selected,
                used,
                "point-09",
                make_discard_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    "point-09",
                    riichi_discard_indices,
                ),
                score_value,
            )

    kept_read = safety_read(naga, target, discards, reached, open_melds)
    if naga != actual and kept_read["kind"] and kept_read["safe_against_threat"]:
        score_value = gap + 0.25 + 0.15 * active_threats
        if stage in {"middle", "late"}:
            score_value += 0.15
        if wants_candidate(selected, "point-14", score_value):
            add(
                selected,
                used,
                "point-14",
                make_discard_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    "point-14",
                    riichi_discard_indices,
                ),
                score_value,
            )

    if naga != actual and actual_read["kind"] and not naga_read["kind"]:
        score_value = preferred_bonus("point-15", row, kyoku_index, left, actual, naga) + gap
        if actual_d is not None and naga_d is not None:
            score_value += max(0.0, naga_d - actual_d)
        if active_threats:
            score_value += 0.2
        if wants_candidate(selected, "point-15", score_value):
            case = make_discard_case(
                row,
                kyoku_index,
                pos,
                start,
                state,
                hands,
                discards,
                melds,
                reached,
                dora_markers,
                "point-15",
                riichi_discard_indices,
            )
            add_best(selected, used, scores, "point-15", case, score_value)

    if naga != actual and actual_cls == "terminal" and naga_cls == "simple" and stage in {"middle", "late"}:
        score_value = preferred_bonus("point-16", row, kyoku_index, left, actual, naga) + gap
        if stage == "late":
            score_value += 0.3
        if actual_d is not None and naga_d is not None:
            score_value += max(0.0, naga_d - actual_d)
        if wants_candidate(selected, "point-16", score_value):
            case = make_discard_case(
                row,
                kyoku_index,
                pos,
                start,
                state,
                hands,
                discards,
                melds,
                reached,
                dora_markers,
                "point-16",
                riichi_discard_indices,
            )
            add_best(selected, used, scores, "point-16", case, score_value)

    if naga != actual and actual_cls == "honor" and naga_cls == "simple" and tile_count(hands[target], actual) == 1:
        score_value = preferred_bonus("point-18", row, kyoku_index, left, actual, naga) + gap
        if actual_d is not None and naga_d is not None:
            score_value += max(0.0, naga_d - actual_d)
        if active_threats:
            score_value += 0.1
        if wants_candidate(selected, "point-18", score_value):
            case = make_discard_case(
                row,
                kyoku_index,
                pos,
                start,
                state,
                hands,
                discards,
                melds,
                reached,
                dora_markers,
                "point-18",
                riichi_discard_indices,
            )
            add_best(selected, used, scores, "point-18", case, score_value)

    if stage == "late" and naga != actual:
        score_value = gap + 0.1 * active_threats
        if actual_d is not None and naga_d is not None:
            score_value += abs(actual_d - naga_d) / 2
        if wants_candidate(selected, "point-10", score_value):
            add(
                selected,
                used,
                "point-10",
                make_discard_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    "point-10",
                    riichi_discard_indices,
                ),
                score_value,
            )

    if naga != actual:
        score_value = gap
        if actual_d is not None and naga_d is not None:
            score_value += abs(actual_d - naga_d) / 3
        if wants_candidate(selected, "point-12", score_value):
            add(
                selected,
                used,
                "point-12",
                make_discard_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    "point-12",
                    riichi_discard_indices,
                ),
                score_value,
            )

    if actual_cls == "honor":
        threats = yakuhai_cleanup_threats(start, target, melds, actual)
        actual_count = sum(1 for tile in hands[target] if tile_id(tile) == tile_id(actual))
        visible_count = public_visible[tile_id(actual)]
        danger_ok = actual_d is None or naga_d is None or actual_d <= naga_d + 0.02
        own_discards = len(discards[target])
        first_row = own_discards < 6
        if first_row and threats and actual_count == 1 and visible_count <= 1 and danger_ok:
            score_value = 100 - own_discards + gap + (0.3 if naga_cls != "honor" else 0.0)
            if wants_candidate(selected, "point-13", score_value):
                case = make_yakuhai_cleanup_case(
                    row,
                    kyoku_index,
                    pos,
                    start,
                    state,
                    hands,
                    discards,
                    melds,
                    reached,
                    dora_markers,
                    threats,
                    riichi_discard_indices,
                )
                add_best(selected, used, scores, "point-13", case, score_value)

    if start.get("end_msgs") and start["end_msgs"][0].get("type") != "hora":
        delta = sum((m.get("deltas") or [0, 0, 0, 0])[target] for m in start.get("end_msgs") or [])
        if delta > 0 and stage == "late":
            score_value = gap + delta / 10000 + 0.15 * active_threats
            if wants_candidate(selected, "point-11", score_value):
                add(
                    selected,
                    used,
                    "point-11",
                    make_simple_discard_case(
                        row,
                        kyoku_index,
                        pos,
                        start,
                        state,
                        hands,
                        discards,
                        melds,
                        reached,
                        dora_markers,
                        "point-11",
                        riichi_discard_indices,
                    ),
                    score_value,
                )


def try_call_points(
    selected,
    used,
    row,
    kyoku_index,
    pos,
    start,
    state,
    hands,
    discards,
    melds,
    reached,
    dora_markers,
    previous_state=None,
    riichi_discard_indices=None,
):
    msg = state.get("info", {}).get("msg", {})
    if msg.get("actor") != row["actor"] or msg.get("type") not in base.HURO_TYPES:
        return
    active_threats = sum(1 for value in reached if value)
    left = msg.get("left_hai_num") or 0
    post_discard = msg.get("real_dahai")
    exposed_bonus = 0.2 if msg.get("type") == "pon" else 0.1
    terminal_or_honor_exit = post_discard and base.tile_class(post_discard) in {"honor", "terminal"}
    call_case = make_call_case(
        row,
        kyoku_index,
        pos,
        start,
        state,
        hands,
        discards,
        melds,
        reached,
        dora_markers,
        "point-03",
        previous_state,
        riichi_discard_indices,
    )

    score_value = exposed_bonus + max(0.0, (70 - left) / 100) + call_score_adjustment(call_case or {})
    if call_has_teaching_disagreement(call_case) and wants_candidate(selected, "point-03", score_value):
        add(
            selected,
            used,
            "point-03",
            call_case,
            score_value,
        )

    if active_threats or terminal_or_honor_exit:
        call_case = make_call_case(
            row,
            kyoku_index,
            pos,
            start,
            state,
            hands,
            discards,
            melds,
            reached,
            dora_markers,
            "point-04",
            previous_state,
            riichi_discard_indices,
        )
        score_value = 0.4 + 0.2 * active_threats + (0.2 if terminal_or_honor_exit else 0.0) + call_score_adjustment(call_case or {})
        if call_has_teaching_disagreement(call_case) and wants_candidate(selected, "point-04", score_value):
            add(
                selected,
                used,
                "point-04",
                call_case,
                score_value,
            )


def collect_examples():
    selected = {}
    scores = {}
    used = {}
    for row in base.parse_rows():
        # The public teaching set is intentionally evaluation-domain matched. Lower-room
        # games remain in aggregate/source-scope counts, but not in the default examples.
        if row.get("room") != "Tokujou":
            continue
        target = row["actor"]
        data = base.fetch_report(row["report_id"])
        base.normalize_report(data)
        for kyoku_index, kyoku in enumerate(data["pred"]):
            start = kyoku[0].get("info", {}).get("msg", {})
            hands = [list(h) for h in start.get("tehais", [[], [], [], []])]
            discards = [[], [], [], []]
            melds = [[], [], [], []]
            open_melds = [0, 0, 0, 0]
            reached = [False, False, False, False]
            pending_riichi_discard = [False, False, False, False]
            riichi_discard_indices = [None, None, None, None]
            dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []

            for pos, state in enumerate(kyoku):
                msg = state.get("info", {}).get("msg", {})
                actor = msg.get("actor")
                msg_type = msg.get("type")

                if msg_type == "dora" and msg.get("dora_marker"):
                    dora_markers.append(msg["dora_marker"])

                if msg_type == "tsumo":
                    hands[actor].append(msg["pai"])
                    if actor == target and "dahai_pred" in state and msg.get("real_dahai") not in (None, "?"):
                        next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
                        actual_declares_reach = next_msg.get("type") == "reach" and next_msg.get("actor") == actor
                        try_discard_points(
                            selected,
                            used,
                            scores,
                            row,
                            kyoku_index,
                            pos,
                            start,
                            state,
                            hands,
                            discards,
                            melds,
                            reached,
                            dora_markers,
                            open_melds,
                            riichi_discard_indices,
                            actual_declares_reach=actual_declares_reach,
                        )
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type in base.HURO_TYPES:
                    previous_state = kyoku[pos - 1] if pos > 0 else None
                    try_call_points(
                        selected,
                        used,
                        row,
                        kyoku_index,
                        pos,
                        start,
                        state,
                        hands,
                        discards,
                        melds,
                        reached,
                        dora_markers,
                        previous_state,
                        riichi_discard_indices,
                    )
                    consumed = msg.get("consumed", [])
                    call_tiles = consumed + ([msg.get("pai")] if msg.get("pai") else [])
                    melds[actor].append(make_meld(call_tiles, msg.get("pai"), rel_seat(msg.get("target"), actor), msg_type))
                    open_melds[actor] += 1
                    for tile in consumed:
                        remove_tile(hands[actor], tile)
                    discard = msg.get("real_dahai")
                    if discard and discard != "?":
                        remove_tile(hands[actor], discard)

                elif msg_type == "ankan":
                    consumed = msg.get("consumed", [])
                    melds[actor].append(make_meld(consumed, kind=msg_type))
                    open_melds[actor] += 1
                    for tile in consumed:
                        remove_tile(hands[actor], tile)

                elif msg_type == "kakan":
                    tile = msg.get("pai")
                    if tile:
                        melds[actor].append(make_meld([tile], kind=msg_type))
                        remove_tile(hands[actor], tile)

                elif msg_type == "reach":
                    if actor is not None:
                        reached[actor] = True
                        pending_riichi_discard[actor] = True

                elif msg_type == "dahai":
                    tile = msg.get("pai")
                    if actor is not None and tile:
                        discards[actor].append(tile)
                        if pending_riichi_discard[actor]:
                            riichi_discard_indices[actor] = len(discards[actor]) - 1
                            pending_riichi_discard[actor] = False

    return selected


def refresh_evidence_tiers():
    """Refresh badges after the final Mortal pass without reselecting examples."""
    data = json.loads(OUT.read_text(encoding="utf-8"))
    changed = 0
    for rows in data.values():
        for case in rows:
            tier = example_evidence_tier(case)
            if case.get("evidence_tier") != tier:
                case["evidence_tier"] = tier
                changed += 1
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"refreshed evidence tiers in {OUT}; changed={changed}")


def refresh_commentary():
    """Attach data/replay_commentary.json to the selected replays, in its reading order, without reselecting."""
    data = json.loads(OUT.read_text(encoding="utf-8"))
    for point_key, rows in data.items():
        for case in rows:
            attach_example_guides(case)
        if rows and all(case.get("reading_order") for case in rows):
            rows.sort(key=lambda case: case["reading_order"])
        for index, case in enumerate(rows, 1):
            case["example_index"] = index
            case.pop("reading_order", None)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"attached commentary in {OUT}; replays without it: {len(MISSING_COMMENTARY)}")
    for key in MISSING_COMMENTARY:
        print(f"  missing: {key}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--refresh-evidence-only",
        action="store_true",
        help="update evidence badges from the final Mortal artifact without reselecting frames",
    )
    parser.add_argument(
        "--refresh-commentary",
        action="store_true",
        help="attach the written replay commentary without reselecting frames",
    )
    args = parser.parse_args()
    if args.refresh_evidence_only:
        refresh_evidence_tiers()
        return
    if args.refresh_commentary:
        refresh_commentary()
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = finalize_examples(collect_examples())
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [key for key in sorted(POINT_TEXT) if key not in data]
    counts = {key: len(value) for key, value in data.items()}
    print(f"wrote {OUT}; points={len(data)} examples={sum(counts.values())} missing={missing}")
    if MISSING_COMMENTARY:
        print(f"replays without written commentary ({len(MISSING_COMMENTARY)}): {', '.join(MISSING_COMMENTARY)}")


if __name__ == "__main__":
    main()
