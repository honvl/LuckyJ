#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

import analyze_luckyj as base
from extract_case_studies import (
    counts_34,
    hand_string,
    remove_tile,
    round_name,
    safety_read,
    score_band,
    ukeire_after_discard,
)
from mahjong.shanten import Shanten


OUT = Path("site/point-examples.json")
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
EXAMPLES_PER_POINT = 10
POOL_PER_POINT = 120
SHANTEN = Shanten()
MODEL_KEYS = ["nishiki", "hibakari", "kagashi"]
MODEL_LABELS = {"nishiki": "Nishiki", "hibakari": "Hibakari", "kagashi": "Kagashi"}
MODEL_LABELS_JA = {"nishiki": "ニシキ", "hibakari": "ヒバカリ", "kagashi": "カガシ"}
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
        "lesson": "When the score is already good enough, the hand does not need to chase every point. A controlled fold or low-risk continuation can beat a prettier immediate shape.",
        "prompt": "Before choosing, say whether this hand needs more points or whether protecting the current position is already enough.",
        "answer": "Copy the score job first. Lower the ambition, keep safe tiles, and push only if the next draw makes the hand worth it.",
    },
    "point-02": {
        "title": "Keep the branch point alive",
        "lesson": "LuckyJ often keeps tiles that still serve yaku, value, or safety, even when that makes the current shanten number look worse.",
        "prompt": "List the live routes before cutting: closed riichi, open yaku, value upgrade, chiitoi, and fold.",
        "answer": "Keep multiple live routes until the table forces a commitment.",
    },
    "point-03": {
        "title": "Bad closed shapes buy calls",
        "lesson": "The call is valuable when the closed route is mostly imaginary and the open hand creates yaku, tempo, or real tenpai pressure.",
        "prompt": "Before calling, say what the call creates: yaku, tenpai, real 1-shanten, denial, or safe draw equity.",
        "answer": "Call poor closed shapes when the exposed hand has a clear purpose and still leaves a way to stop.",
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
    "point-07": {
        "title": "Call for tempo with a purpose",
        "lesson": "The call has a job beyond completing blocks: speed up a poor hand, contest the table, break a bonus window, or preserve draw equity.",
        "prompt": "Name the purpose before exposing the hand.",
        "answer": "A good tempo call changes the round's clock and keeps you prepared for the next threat.",
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
        "title": "Clean yakuhai against unproven open hands",
        "lesson": "When another player calls with an unclear yaku, singleton dragons and live value winds can become their missing yaku condition. LuckyJ often removes those tiles before they turn into the price of continuing.",
        "prompt": "After an opponent opens, ask which yakuhai still lets that hand win.",
        "answer": "When your hand is too slow to punish them and the yakuhai has no strong job, clean it before the open hand gets to use it.",
    },
    "point-14": {
        "title": "Keep genbutsu and suji tiles on purpose",
        "lesson": "LuckyJ often keeps a tile because it is already genbutsu or suji against an opponent river, especially before spending safer tiles would make the next threat impossible to answer.",
        "prompt": "Before discarding a flexible tile, count which tiles in your hand are genbutsu or suji to each opponent and which of them are still useful next turn.",
        "answer": "Keep the safe tile while it buys future choice; spend it only when the hand has become worth the risk or the draw-point/fold route is already decided.",
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
    "point-17": {
        "title": "Every kept safe tile needs a target",
        "lesson": "Genbutsu and suji only matter when they answer a specific opponent and a specific future decision.",
        "prompt": "For each kept safe tile, complete the sentence: safe against X if Y happens.",
        "answer": "Keep the tile when it covers the live threat. If the named target is vague or quiet, the tile is probably clutter.",
    },
    "point-18": {
        "title": "Honor tiles need role labels",
        "lesson": "An honor can be self value, an opponent yaku condition, dead material, or a defensive tile. Those are different tiles in review.",
        "prompt": "Before cutting or keeping an honor, label its current job.",
        "answer": "Cut loose honors when their only live job helps an opponent or when they are dead; keep honors that are value, route, or target-specific defensive tiles.",
    },
    "point-19": {
        "title": "Leader safety is a qualifier",
        "lesson": "A lead lowers the ambition needed to end the hand, while each discard still needs to reduce real danger or preserve the next turn.",
        "prompt": "When leading, ask what concrete risk the safer-looking discard removes.",
        "answer": "Use the lead to lower the risk budget while still calculating shape, danger, and future safe tiles.",
    },
}


PREFERRED_CASES = {
    "point-15": [{"game": 352, "kyoku_index": 0, "left": 43, "actual": "5m", "naga": "P"}],
    "point-16": [{"game": 107, "kyoku_index": 7, "left": 16, "actual": "1s", "naga": "2s"}],
    "point-17": [{"game": 5, "kyoku_index": 5, "left": 19, "actual": "3p", "naga": "6m"}],
    "point-18": [{"game": 584, "kyoku_index": 6, "left": 27, "actual": "N", "naga": "1s"}],
    "point-19": [{"game": 472, "kyoku_index": 13, "left": 12, "actual": "9m", "naga": "6m"}],
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


def meld_text(meld):
    return " ".join(meld_tiles(meld))


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


def table_context(start, target, hands, discards, melds, reached, dora_markers, state=None):
    rendered_hands = [sorted(hand, key=lambda tile: (tile_id(tile), tile)) for hand in hands]
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


def common_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    score = start.get("scores", [0, 0, 0, 0])[target]
    text = POINT_TEXT[point_key]
    return {
        "point": point_key,
        "title": text["title"],
        "lesson": text["lesson"],
        "prompt": text["prompt"],
        "answer": text["answer"],
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
        "table": table_context(start, target, hands, discards, melds, reached, dora_markers, state),
        "outcome": end_summary(start, target),
    }


def make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key):
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
    case = common_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key)
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
            "kept_tile_safety": safety_read(naga, target, discards, reached, open_counts),
        }
    )
    return case


def make_yakuhai_cleanup_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, threats):
    case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-13")
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


def make_simple_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    actual = msg.get("real_dahai")
    model_head_rows = model_rows(state, actual)
    rows = [(row["top"], row["top_prob"], row["actual_prob"]) for row in model_head_rows]
    if not rows:
        return None
    naga = rows[0][0]
    open_counts = [len(player_melds) for player_melds in melds]
    case = common_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key)
    case.update(
        {
            "kind": "draw-tenpai",
            "hand": hand_string(hands[target]),
            "draw": msg.get("pai"),
            "actual": actual,
            "naga": naga,
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
            "kept_tile_safety": safety_read(naga, target, discards, reached, open_counts),
        }
    )
    return case


def make_reach_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers):
    reach_prob = max((p / 10000.0 for p in state.get("reach", [])), default=0.0)
    if reach_prob < 0.5:
        return None
    case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-08")
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


def make_call_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key, previous_state=None):
    msg = state.get("info", {}).get("msg", {})
    target = row["actor"]
    if msg.get("actor") != target or msg.get("type") not in base.HURO_TYPES:
        return None
    case = common_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, point_key)
    consumed = msg.get("consumed", [])
    shape = post_call_eval(hands[target], consumed, msg.get("real_dahai"))
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
    return case


def tile_token(tile):
    return f"[[{tile}]]" if tile else "the tile"


def tile_plain(tile):
    return str(tile or "?")


def tile_plain_english(tile):
    if not tile:
        return "?"
    mapping = {
        "E": "East",
        "S": "South",
        "W": "West",
        "N": "North",
        "P": "White Dragon",
        "F": "Green Dragon",
        "C": "Red Dragon"
    }
    return mapping.get(tile, tile)


def format_percent(value):
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def format_int(value):
    if value is None:
        return "n/a"
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def seat_label(seat, lang):
    labels = SEAT_LABELS_JA if lang == "ja" else SEAT_LABELS_EN
    return labels.get(seat, seat or "unknown")


def danger_gap_phrase(case, lang):
    actual = case.get("actual_danger")
    naga = case.get("naga_danger")
    if actual is None or naga is None:
        return "NAGA脅威を比べにくい。" if lang == "ja" else "The NAGA threat comparison is unclear."
    gap = actual - naga
    if lang == "ja":
        if abs(gap) < 0.03:
            return f"NAGA脅威は近い。LuckyJ {format_percent(actual)}、ニシキ {format_percent(naga)}。"
        if gap < 0:
            return f"LuckyJ はNAGA脅威を下げている。LuckyJ {format_percent(actual)}、ニシキ {format_percent(naga)}。"
        return f"LuckyJ はNAGA脅威を余分に受け入れている。LuckyJ {format_percent(actual)}、ニシキ {format_percent(naga)}。"
    if abs(gap) < 0.03:
        return f"The NAGA threat numbers are close: LuckyJ {format_percent(actual)}, Nishiki {format_percent(naga)}."
    if gap < 0:
        return f"LuckyJ lowers the NAGA threat reading: LuckyJ {format_percent(actual)}, Nishiki {format_percent(naga)}."
    return f"LuckyJ accepts a higher NAGA threat reading now: LuckyJ {format_percent(actual)}, Nishiki {format_percent(naga)}."


def threat_peak_text(profile, lang):
    if not profile or profile.get("max") is None:
        return "n/a"
    head = profile.get("peak_head") or "danger"
    return f"{head} {format_percent(profile.get('max'))}"


def threat_case_sentence(case, lang):
    actual_profile = case.get("actual_threat") or {}
    naga_profile = case.get("naga_threat") or {}
    actual_max = actual_profile.get("max")
    naga_max = naga_profile.get("max")
    if actual_max is None or naga_max is None:
        return ""
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    gap = actual_max - naga_max
    actual_detail = f"{actual} peaks at {threat_peak_text(actual_profile, lang)}"
    naga_detail = f"{naga} peaks at {threat_peak_text(naga_profile, lang)}"
    if lang == "ja":
        actual_detail = f"{actual} は {threat_peak_text(actual_profile, lang)} が最大"
        naga_detail = f"{naga} は {threat_peak_text(naga_profile, lang)} が最大"
        if abs(gap) < 0.03:
            if max(actual_max, naga_max) < 0.08:
                return f"修正後の脅威バーでは両候補とも静か。{actual_detail}、{naga_detail}。この例は危険差ではなく、形・役割・着順で読む。"
            return f"修正後の脅威バーでは両候補が近い。{actual_detail}、{naga_detail}。危険差だけでは説明できない分岐である。"
        if gap < 0:
            return f"修正後の脅威バーではニシキ候補の方が熱い。{actual_detail}、{naga_detail}。LuckyJ は単に危険を払っているのではなく、熱い候補を避けながら別の価値を残している。"
        return f"修正後の脅威バーではLuckyJの打牌の方が熱い。{actual_detail}、{naga_detail}。この例は安全寄せではなく、追加脅威を払ってでも残す形・価値・着順理由があるかを見る。"
    if abs(gap) < 0.03:
        if max(actual_max, naga_max) < 0.08:
            return f"With the corrected bars, both candidates are quiet: {actual_detail}; {naga_detail}. This example should be read through shape, role, and placement rather than a danger gap."
        return f"With the corrected bars, the two candidate threats are close: {actual_detail}; {naga_detail}. The disagreement is not explained by threat alone."
    if gap < 0:
        return f"With the corrected bars, Nishiki's candidate is the hotter tile: {actual_detail}; {naga_detail}. LuckyJ is not simply paying more danger here; it is avoiding that hotter candidate while preserving a different job."
    return f"With the corrected bars, LuckyJ's discard is the hotter tile: {actual_detail}; {naga_detail}. This is a real threat-buy, so the local shape, value, or placement reason has to carry the example."


def eval_summary(item, lang):
    if not item:
        return "形の数値は薄い。" if lang == "ja" else "There is no detailed shape count for this branch."
    effective = item.get("effective") or []
    waits = ", ".join(tile_token(tile) for tile in effective[:5])
    if not waits:
        waits = "なし" if lang == "ja" else "none listed"
    if lang == "ja":
        return f"{format_int(item.get('shanten'))}シャンテン、見えている受け入れ{format_int(item.get('ukeire'))}枚、主な受け {waits}"
    return f"{format_int(item.get('shanten'))}-shanten, {format_int(item.get('ukeire'))} visible ukeire, main accepts {waits}"


def safety_read_sentence(read, lang):
    if not read or not (read.get("kind") or read.get("has_sotogawa")):
        return ""
    target = (read.get("against") or [{}])[0]
    kind = read.get("kind")
    parts = []
    if lang == "ja":
        if kind:
            parts.append({"genbutsu": "現物", "suji": "筋"}.get(kind, kind))
        if read.get("has_sotogawa"):
            parts.append("外側牌（ソト側）")
        threat = "リーチ" if target.get("reached") else f"{target.get('open_melds')}副露" if target.get("open_melds") else "静かな相手"
        return f"残る {tile_token(read.get('tile'))} は {seat_label(target.get('seat_label'), lang)} に対して{'かつ'.join(parts)}で、相手の状態は{threat}。"
    if kind:
        parts.append({"genbutsu": "genbutsu", "suji": "suji"}.get(kind, kind))
    if read.get("has_sotogawa"):
        parts.append("an outside tile (sotogawa)")
    threat = "riichi" if target.get("reached") else f"{target.get('open_melds')} calls" if target.get("open_melds") else "no called threat"
    return f"The kept {tile_token(read.get('tile'))} is {' and '.join(parts)} against the {seat_label(target.get('seat_label'), lang)} ({threat})."


def call_model_sentence(case, lang):
    heads = case.get("call_model_heads") or []
    if not heads:
        if lang == "ja":
            return "この鳴き例は手牌進行と鳴き後の打牌を中心に読む。"
        return "This call example is read through hand progress and the planned post-call discard."
    nishiki = model_head(heads, "nishiki")
    hibakari = model_head(heads, "hibakari")
    actual = case.get("call", "call")
    if lang == "ja":
        parts = []
        if nishiki:
            parts.append(f"ニシキは {nishiki['top_action']} {format_percent(nishiki['top_prob'])}、実戦の {actual} 重み {format_percent(nishiki['actual_kind_prob'])}")
        if hibakari:
            if hibakari.get("supports_call"):
                parts.append("ヒバカリもこの鳴きを第一候補にしている")
            elif hibakari.get("prefers_pass"):
                parts.append(f"ヒバカリはスルー寄り ({format_percent(hibakari['pass_prob'])})")
            else:
                parts.append(f"ヒバカリは別の {hibakari['top_action']} 寄り")
        return "。".join(parts) + "。"
    parts = []
    if nishiki:
        parts.append(
            f"Nishiki top action is {nishiki['top_action']} ({format_percent(nishiki['top_prob'])}); "
            f"the actual {actual} weight is {format_percent(nishiki['actual_kind_prob'])}"
        )
    if hibakari:
        if hibakari.get("supports_call"):
            parts.append("Hibakari also makes this call its top action")
        elif hibakari.get("prefers_pass"):
            parts.append(f"Hibakari prefers passing ({format_percent(hibakari['pass_prob'])})")
        else:
            parts.append(f"Hibakari prefers a different {hibakari['top_action']} line")
    return ". ".join(parts) + "."


def case_model_head(case, key):
    return next((head for head in case.get("model_heads") or [] if head.get("key") == key), None)


def hibakari_read_sentence(case, lang):
    head = case_model_head(case, "hibakari")
    if not head:
        return ""
    top = tile_token(head.get("top"))
    actual = tile_token(case.get("actual"))
    nishiki = tile_token(case.get("naga"))
    if lang == "ja":
        if head.get("matches_luckyj"):
            return f"ヒバカリも {actual} を第一候補にしており、この例は LuckyJ/ヒバカリ対ニシキの分岐として読む。"
        if head.get("matches_nishiki"):
            return f"ヒバカリもニシキと同じ {nishiki} 寄りなので、これは守備寄り基準にも逆らう例。条件がそろう時だけ真似する。"
        return f"ヒバカリは第三候補の {top} を選ぶ。表面の牌より、三者が何を守ろうとしているかを見る。"
    if head.get("matches_luckyj"):
        return f"Hibakari also chooses {actual}, so read this as LuckyJ/Hibakari versus Nishiki, not LuckyJ against every NAGA head."
    if head.get("matches_nishiki"):
        return f"Hibakari also leans to Nishiki's {nishiki}, so this is a harder example: LuckyJ is beating the defensive baseline only if the local condition is exact."
    return f"Hibakari chooses a third line, {top}; read the example as a three-way split and copy the reason, not the surface tile."


def yakuhai_threat_sentence(case, lang):
    threats = case.get("yakuhai_cleanup", {}).get("threats") or []
    if not threats:
        return ""
    rows = []
    for threat in threats:
        melds = "; ".join(meld_text(meld) for meld in (threat.get("melds") or []))
        wind = tile_token(threat.get("wind"))
        if lang == "ja":
            rows.append(f"{seat_label(threat.get('seat'), lang)} ({wind}場風/自風, 副露 {melds or 'なし'})")
        else:
            rows.append(f"{seat_label(threat.get('seat'), lang)} ({wind} seat wind, melds {melds or 'none'})")
    if lang == "ja":
        return f"{tile_token(case.get('actual'))} は {'、'.join(rows)} に対してまだ役牌条件になり得る。"
    return f"{tile_token(case.get('actual'))} is still a yaku condition against {', '.join(rows)}."


def point_focus_en(point_key, case):
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    kept = tile_token(case.get("naga"))
    score_band_text = case.get("score_band", "the current score band")
    if point_key == "point-01":
        rank = ordinal_en(case.get("current_rank")) if case.get("current_rank") else "a protected seat"
        score = format_int(case.get("score"))
        return f"On {score} points and currently {rank}, this hand does not need to chase extra points. LuckyJ lets it become a controlled fold unless the next draw makes pushing clearly worth it."
    if point_key == "point-02":
        return f"Cutting {actual} keeps {kept} as a branch point. The hand stays able to choose value, safety, or a different yaku route after the table gives more information."
    if point_key == "point-05":
        return f"{actual} is the liability LuckyJ is willing to remove now. Waiting can force the same tile out after riichi or another call, when it costs more."
    if point_key == "point-06":
        return f"LuckyJ spends some easy acceptance to keep the hand worth playing. The score job asks for more than a cheap future."
    if point_key == "point-08":
        return f"Riichi is part of the value calculation. With a declaration probability of {format_percent(case.get('reach_prob'))}, LuckyJ treats pressure as a real output of the discard."
    if point_key == "point-09":
        return f"The next required discard matters more than this turn alone. LuckyJ chooses {actual} because the route through {naga} can become expensive on the following draw."
    if point_key == "point-10":
        return f"This is late enough that vague improvement has mostly expired. LuckyJ's {actual} cut should be read as win, safe tenpai, or controlled defense."
    if point_key == "point-11":
        return f"The hand result matters: {case.get('outcome')}. LuckyJ is playing for drawn-hand equity as well as direct wins."
    if point_key == "point-12":
        return f"The disagreement is the review prompt. First decide whether {actual} buys safety, value, route count, pressure, or placement before calling it right or wrong."
    if point_key == "point-13":
        return yakuhai_threat_sentence(case, "en") or f"LuckyJ cleans {actual} before it turns into another player's yaku condition."
    if point_key == "point-14":
        return f"By cutting {actual}, LuckyJ keeps {kept} as a named defensive tile with a target."
    if point_key == "point-15":
        return f"This is a spend-the-safe-tile example. {actual} may look safe, but LuckyJ treats that safety as stale or off-target once the live route needs space."
    if point_key == "point-16":
        return f"The outside cut {actual} preserves the middle connection represented by {naga}. It looks defensive, but the point is keeping the real route alive."
    if point_key == "point-17":
        return f"The kept {kept} needs a target. When it covers the active opponent, keeping it is a plan; vague targets make it clutter."
    if point_key == "point-18":
        return f"Honor tiles split into roles. Here {actual} is being treated as loose material or an opponent condition."
    if point_key == "point-19":
        return f"The lead lowers the ambition and keeps the calculation active. LuckyJ checks whether {actual} reduces risk or preserves the next turn."
    return f"LuckyJ cuts {actual} while Nishiki prefers {naga}; the lesson is in the future each tile leaves behind."


def point_focus_ja(point_key, case):
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    score_band_text = case.get("score_band", "この点数状況")
    if point_key == "point-01":
        rank = f"現在{case.get('current_rank')}着" if case.get("current_rank") else "守る着順"
        return f"{format_int(case.get('score'))}点で {rank} なので、加点を追いすぎる局面ではない。次のツモで押す価値がはっきり出なければ、LuckyJ はこの手を無理せず降りやすい形へ寄せている。"
    if point_key == "point-02":
        return f"{actual} を切ることで {naga} を分岐点として残す。価値、安全、別ルートをまだ選べる形にしている。"
    if point_key == "point-05":
        return f"{actual} は後で切らされると高くつく負債。リーチや副露が入る前に先に処理している。"
    if point_key == "point-06":
        return "LuckyJ は受け入れを少し払って、手の価値を残している。安すぎる未来を避ける判断である。"
    if point_key == "point-08":
        return f"リーチ自体が価値になる局面。宣言確率 {format_percent(case.get('reach_prob'))} を含めて、圧力を打牌の成果として見ている。"
    if point_key == "point-09":
        return f"今の一打と次に切る牌まで読む。{naga} 経由の道が次巡に高くつくため、LuckyJ は {actual} を選んでいる。"
    if point_key == "point-10":
        return f"終盤なので曖昧な改良はかなり小さい。{actual} は和了、安全テンパイ、撤退のどれかとして読む。"
    if point_key == "point-11":
        return f"結果は {case.get('outcome')}。直撃の和了に加えて、流局テンパイの価値を取りに行っている。"
    if point_key == "point-12":
        return f"この不一致そのものが復習点。{actual} が安全、価値、ルート数、圧力、着順のどれを買っているかを先に言う。"
    if point_key == "point-13":
        return yakuhai_threat_sentence(case, "ja") or f"LuckyJ は {actual} が相手の役条件になる前に処理している。"
    if point_key == "point-14":
        return f"{actual} を切って {naga} を明確な守備牌として残す。対象のある安全牌として扱っている。"
    if point_key == "point-15":
        return f"安全牌を使う例。{actual} は安全に見えても、守る相手がずれたら手順の邪魔になる。"
    if point_key == "point-16":
        return f"外側の {actual} 切りは、中の {naga} 周りのルートを残す攻めの支払いとして読む。"
    if point_key == "point-17":
        return f"残す {naga} には対象が必要。生きている相手に効くなら計画で、対象がなければただの手牌圧迫。"
    if point_key == "point-18":
        return f"字牌には役割がある。ここでの {actual} は浮き牌か相手条件として扱われている。"
    if point_key == "point-19":
        return f"トップ目でも計算は続ける。{actual} が危険を減らし、次巡を残すかを見ている。"
    return f"LuckyJ は {actual}、ニシキは {naga}。どちらがどの未来を残すかを見る。"


def copy_rule_en(point_key, case):
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    if point_key == "point-01":
        return "Copy the score job: when your position is already good enough, lower the ambition, keep safe tiles, and let the hand fold unless a later draw makes it worth pushing."
    if point_key == "point-13":
        return f"Copy this when {actual} is live yakuhai for an opened hand and your own hand is too slow to punish that player immediately."
    if point_key in {"point-14", "point-17"}:
        return f"Copy the target: keep {naga} when it answers a named opponent on a believable future bad draw."
    if point_key == "point-15":
        return f"Copy this only after naming why the safe-looking {actual} has expired and what later safe tile remains."
    if point_key == "point-18":
        return f"Copy the role label: cut {actual} when its main job helps someone else's condition."
    if point_key == "point-19":
        return "Copy the reduced ambition of the leader seat, but still count danger, shape, and the next discard."
    if point_key == "point-08":
        return "Copy the pressure only when riichi changes opponent behavior and the wait is good enough to make that pressure matter."
    if point_key == "point-11":
        return "Copy this when a safe path to tenpai has measurable value even if the hand is unlikely to win outright."
    return f"Copy the reason: if cutting {actual} keeps the hand's real job clearer than the Nishiki line through {naga}, the choice is reproducible."


def copy_rule_ja(point_key, case):
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    if point_key == "point-01":
        return "点数状況を真似する。今の着順を守れば十分なら、目標を下げて安全牌を残し、次のツモで押す価値が出るまで無理しない。"
    if point_key == "point-13":
        return f"{actual} が副露手の生きた役牌で、自分がすぐ罰せない時だけ真似する。"
    if point_key in {"point-14", "point-17"}:
        return f"対象を真似する。{naga} が次の悪いツモで誰に効くかを言える時だけ残す。"
    if point_key == "point-15":
        return f"安全そうな {actual} がなぜ期限切れか、次の安全牌が何かを言えた時だけ真似する。"
    if point_key == "point-18":
        return f"役割ラベルを真似する。{actual} が自分の価値でなく相手条件に近いなら切る。"
    if point_key == "point-19":
        return "トップ目の低い目標を真似してよいが、危険度、形、次巡の打牌はまだ数える。"
    if point_key == "point-08":
        return "リーチで相手の行動が変わり、待ちも最低限ある時だけ圧力を真似する。"
    if point_key == "point-11":
        return "和了が薄くても、安全にテンパイへ行ける価値がある時に真似する。"
    return f"{actual} 切りが {naga} 経由より手の仕事をはっきり残すなら、その理由を真似できる。"


def limit_rule_en(point_key, case):
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    if point_key == "point-01":
        return "Do not copy the fold posture when you actually need points, when the hand is already worth pushing, or when the safer line has no real safe tile."
    if point_key == "point-13":
        return "Clean honors by role. Your pair, your value tile, and a dead caller tile use different rules."
    if point_key == "point-08":
        return "Declare with a reason. Bad waits, huge placement punishment, or a clear upgrade can still make damaten correct."
    if point_key in {"point-14", "point-17"}:
        return f"Keep {naga} when it actually covers a live threat."
    if point_key == "point-15":
        return f"Spend {actual} only when another real answer to the active threat remains."
    if point_key == "point-16":
        return f"If {actual} is the only safe tile or the inside route is fantasy, the outside cut is just a fold."
    return "Copy the surface tile only when the score job, threat level, and next discard chain match."


def limit_rule_ja(point_key, case):
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    if point_key == "point-01":
        return "加点が必要な時、すでに押す価値がある手、または安全牌のない安全寄せでは真似しない。"
    if point_key == "point-13":
        return "字牌は役割で分ける。対子、自分の役、相手にもう生きていない牌は別判断である。"
    if point_key == "point-08":
        return "リーチには理由を持たせる。悪形、着順罰、明確な改良があればダマも残る。"
    if point_key in {"point-14", "point-17"}:
        return f"{naga} が生きた脅威に通る時に残す。"
    if point_key == "point-15":
        return f"{actual} が現役の脅威への唯一の答えなら、安全牌として残す。"
    if point_key == "point-16":
        return f"{actual} が唯一の安全牌、または中のルートが幻想なら、防御寄りの打牌として扱う。"
    return "表面の牌を真似する条件は、点数状況、脅威、次に切る牌がそろう時である。"


def why_naga_tempting_en(case):
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    actual_eval = case.get("actual_eval")
    naga_eval = case.get("naga_eval")
    if actual_eval and naga_eval:
        if case.get("point") == "point-01":
            return f"The Nishiki line through {naga} is the efficiency temptation because it leaves {eval_summary(naga_eval, 'en')}. LuckyJ's {actual} line leaves {eval_summary(actual_eval, 'en')}. That extra acceptance matters less when the score job is to protect the current position, not manufacture more points. {danger_gap_phrase(case, 'en')}"
        return f"The Nishiki line through {naga} is tempting because it leaves {eval_summary(naga_eval, 'en')}. LuckyJ's {actual} line leaves {eval_summary(actual_eval, 'en')}. {danger_gap_phrase(case, 'en')}"
    if case.get("point") == "point-01":
        return f"Nishiki's top line {naga} is tempting because it has the highest model weight here: Nishiki {format_percent(case.get('naga_prob'))}, LuckyJ {format_percent(case.get('actual_prob'))}. In this score spot, that model weight is not enough by itself; the hand first has to justify risking the lead. {danger_gap_phrase(case, 'en')}"
    return f"Nishiki's top line {naga} is tempting because it has the highest model weight here: Nishiki {format_percent(case.get('naga_prob'))}, LuckyJ {format_percent(case.get('actual_prob'))}. {danger_gap_phrase(case, 'en')}"


def why_naga_tempting_ja(case):
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    actual_eval = case.get("actual_eval")
    naga_eval = case.get("naga_eval")
    if actual_eval and naga_eval:
        if case.get("point") == "point-01":
            return f"ニシキの {naga} は {eval_summary(naga_eval, 'ja')} を残すので、効率面では魅力がある。LuckyJ の {actual} は {eval_summary(actual_eval, 'ja')}。ただしこの点数状況では、加点を作ることより今の着順を守ることが先に来る。{danger_gap_phrase(case, 'ja')}"
        return f"ニシキの {naga} は {eval_summary(naga_eval, 'ja')} を残すので魅力がある。LuckyJ の {actual} は {eval_summary(actual_eval, 'ja')}。{danger_gap_phrase(case, 'ja')}"
    if case.get("point") == "point-01":
        return f"ニシキ第一候補の {naga} はこの局面で重みが高い ({format_percent(case.get('naga_prob'))}、LuckyJ は {format_percent(case.get('actual_prob'))})。ただしこの点数状況では、その重みだけでリードを危険にさらす理由にはならない。{danger_gap_phrase(case, 'ja')}"
    return f"ニシキ第一候補の {naga} はこの局面で重みが高い ({format_percent(case.get('naga_prob'))}、LuckyJ は {format_percent(case.get('actual_prob'))})。{danger_gap_phrase(case, 'ja')}"


def build_discard_guide(case, lang):
    point_key = case["point"]
    actual = tile_token(case.get("actual"))
    naga = tile_token(case.get("naga"))
    draw = tile_token(case.get("draw"))
    rank = case.get("current_rank") or case.get("rank")
    safety = safety_read_sentence(case.get("kept_tile_safety"), lang)
    hibakari = hibakari_read_sentence(case, lang)
    threat = threat_case_sentence(case, lang)
    if lang == "ja":
        focus = point_focus_ja(point_key, case)
        read = " ".join(part for part in [focus, threat, safety, hibakari] if part).strip()
        rank_text = f"現在{rank}着" if rank else "現在着順不明"
        prompt = (
            f"残り{case.get('left')}枚で {actual} と {naga} のどちらを切るか。先に加点が必要か、今の着順を守れば十分かを言う。"
            if point_key == "point-01"
            else f"残り{case.get('left')}枚で {actual} と {naga} のどちらを切るか。先に {naga} が何を残しているかを言う。"
        )
        return {
            "caption": f"LuckyJ {tile_plain(case.get('actual'))}、ニシキ {tile_plain(case.get('naga'))}",
            "situation": f"{case.get('round')}、{case.get('stage')}、残り{case.get('left')}枚。{case.get('score_band')}、{format_int(case.get('score'))}点、{rank_text}。LuckyJ は {draw} ツモから {actual} を切り、ニシキ第一候補は {naga}。結果: {case.get('outcome')}",
            "read": read,
            "whyNot": why_naga_tempting_ja(case),
            "copy": copy_rule_ja(point_key, case),
            "limit": limit_rule_ja(point_key, case),
            "prompt": prompt,
            "answer": f"LuckyJ は {actual} を選ぶ。理由は {focus}",
        }
    focus = point_focus_en(point_key, case)
    read = " ".join(part for part in [focus, threat, safety, hibakari] if part).strip()
    rank_text = f"currently {ordinal_en(rank)}" if rank else "current rank unknown"
    prompt = (
        f"With {case.get('left')} tiles left, would you cut {actual} or {naga}? First say whether you need more points or can protect the current position."
        if point_key == "point-01"
        else f"With {case.get('left')} tiles left, would you cut {actual} or {naga}? First name what {naga} is preserving."
    )
    return {
        "caption": f"LuckyJ {tile_plain_english(case.get('actual'))}, Nishiki {tile_plain_english(case.get('naga'))}",
        "situation": f"{case.get('round')}, {case.get('stage')} hand, {case.get('left')} tiles left. LuckyJ has {format_int(case.get('score'))} points ({case.get('score_band')}), {rank_text}. After drawing {draw}, LuckyJ cuts {actual}; Nishiki's top line is {naga}. Result: {case.get('outcome')}",
        "read": read,
        "whyNot": why_naga_tempting_en(case),
        "copy": copy_rule_en(point_key, case),
        "limit": limit_rule_en(point_key, case),
        "prompt": prompt,
        "answer": f"LuckyJ chooses {actual}. The reproducible reason is: {focus}",
    }


def build_call_guide(case, lang):
    point_key = case["point"]
    called = tile_token(case.get("called_tile"))
    discard = tile_token(case.get("discard_after_call"))
    call = case.get("call", "call")
    from_seat = seat_label(case.get("called_from"), lang)
    meld = " ".join(case.get("consumed") or [])
    shape = case.get("post_call_eval") or {}
    post_shape = shanten_text(shape.get("shanten"), lang)
    model_read = call_model_sentence(case, lang)
    rank = case.get("current_rank") or case.get("rank")
    if lang == "ja":
        if point_key == "point-04":
            focus = f"副露後の {discard} まで先に見えていることが大事。開いた後も次の安全牌を残している。"
        elif point_key == "point-07":
            focus = f"{call} は速度を買うための副露。残り{case.get('left')}枚で、閉じたまま待つより局面の時計を進めている。"
        elif shape.get("shanten") is not None and shape.get("shanten") > 0 and (case.get("left") or 0) <= 1:
            focus = f"これは手牌完成の鳴きではなく、終局直前のテンポ鳴き。{discard} を切った後も {post_shape} なので、普通の和了形に近づいた例としては読まない。"
        elif shape.get("shanten") is not None and shape.get("shanten") <= 0:
            focus = f"閉じた手が間に合いにくい局面で、{call} 後の {discard} まで決めると {post_shape} になる。"
        else:
            focus = f"閉じた手が間に合いにくい局面で、{call} 後の {discard} まで決めると {post_shape} まで進む。"
        rank_text = f"現在{rank}着" if rank else "現在着順不明"
        return {
            "caption": f"{call} して {tile_plain(case.get('discard_after_call'))}",
            "situation": f"{case.get('round')}、{case.get('stage')}、残り{case.get('left')}枚。{case.get('score_band')}、{format_int(case.get('score'))}点、{rank_text}。LuckyJ は {from_seat} から {called} を {call} し、{discard} を切る。結果: {case.get('outcome')}",
            "read": f"{focus} {model_read}".strip(),
            "whyNot": f"門前維持は自然な選択。ただしこの局面では残り枚数と手牌 {meld or 'なし'} から、門前の理想形を待つ余裕が薄い。",
            "copy": f"{call} が役、速度、テンパイ、または相手への圧力を作る時だけ真似する。鳴いた後の最初の打牌 {discard} まで先に決める。",
            "limit": "鳴いた後の安全牌や次の方針まで言える時に、LuckyJ 型のテンポになる。",
            "prompt": f"{called} を {call} するか。答える前に、鳴いた後に何を切るかを言う。",
            "answer": f"最初に見るのは鳴き後の打牌で、この例では {discard} まで見えている。{focus} {model_read}",
        }
    if point_key == "point-04":
        focus = f"The important tile is the post-call {discard}. LuckyJ opens while keeping the first safe tile and the next concrete plan."
    elif point_key == "point-07":
        focus = f"The {call} buys tempo with {case.get('left')} tiles left. LuckyJ is changing the round clock and completing a useful set."
    elif shape.get("shanten") is not None and shape.get("shanten") > 0 and (case.get("left") or 0) <= 1:
        focus = f"This is a last-turn tempo call, not a hand-completion call. After {discard}, the hand is still {post_shape}, so do not read this as a normal pon that makes a winning shape."
    elif shape.get("shanten") is not None and shape.get("shanten") <= 0:
        focus = f"The closed route is running out of practical turns; after the {call} and {discard}, the hand reaches {post_shape}."
    else:
        focus = f"The closed route is running out of practical turns; after the {call} and {discard}, the hand reaches {post_shape}."
    rank_text = f"currently {ordinal_en(rank)}" if rank else "current rank unknown"
    return {
        "caption": f"{call.capitalize()} on {tile_plain_english(case.get('called_tile'))}, discard {tile_plain_english(case.get('discard_after_call'))}",
        "situation": f"{case.get('round')}, {case.get('stage')} hand, {case.get('left')} tiles left. LuckyJ has {format_int(case.get('score'))} points ({case.get('score_band')}), {rank_text}. LuckyJ calls {call} on {called} from the {from_seat}, then cuts {discard}. Result: {case.get('outcome')}",
        "read": f"{focus} {model_read}".strip(),
        "whyNot": f"Passing is tempting because it keeps the hand closed. With {case.get('left')} tiles left, the closed ideal may run out of useful turns.",
        "copy": f"Copy the {call} only when it creates yaku, speed, tenpai pressure, or denial, and when the first post-call discard {discard} is already planned.",
        "limit": "The call needs a named post-call discard and a next defensive tile to become LuckyJ-style tempo.",
        "prompt": f"Would you {call} on {called}? Before answering, name the discard after the call.",
        "answer": f"The first check is the post-call discard: {discard} is already the release tile. {focus} {model_read}",
    }


LLM_CACHE_PATH = Path("data/llm_guides_cache.json")
LLM_CACHE = None

def load_llm_cache():
    global LLM_CACHE
    if LLM_CACHE is not None:
        return LLM_CACHE
    if LLM_CACHE_PATH.exists():
        try:
            with open(LLM_CACHE_PATH, "r", encoding="utf-8") as f:
                LLM_CACHE = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load LLM cache: {e}")
            LLM_CACHE = {}
    else:
        LLM_CACHE = {}
    return LLM_CACHE


def attach_example_guides(case):
    attach_shape_facts(case)
    if case.get("kind") == "call":
        case["guide"] = build_call_guide(case, "en")
        case["guide_ja"] = build_call_guide(case, "ja")
    else:
        case["guide"] = build_discard_guide(case, "en")
        case["guide_ja"] = build_discard_guide(case, "ja")
        
    cache = load_llm_cache()
    key = f"{case.get('point')}_{case.get('game')}_{case.get('kyoku_index')}_{case.get('position')}"
    if key in cache:
        cached_entry = cache[key]
        if "guide" in cached_entry:
            case["guide"]["read"] = cached_entry["guide"].get("read", case["guide"]["read"])
            case["guide"]["prompt"] = cached_entry["guide"].get("prompt", case["guide"]["prompt"])
            case["guide"]["answer"] = cached_entry["guide"].get("answer", case["guide"]["answer"])
        if "guide_ja" in cached_entry:
            case["guide_ja"]["read"] = cached_entry["guide_ja"].get("read", case["guide_ja"]["read"])
            case["guide_ja"]["prompt"] = cached_entry["guide_ja"].get("prompt", case["guide_ja"]["prompt"])
            case["guide_ja"]["answer"] = cached_entry["guide_ja"].get("answer", case["guide_ja"]["answer"])
            
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


def add(selected, used, point_key, candidate, score=0.0):
    sig = candidate_signature(candidate)
    if not candidate or not sig:
        return
    score += baseline_example_bonus(candidate)
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


def finalize_examples(selected):
    output = {}
    for point_key in sorted(POINT_TEXT):
        rows = selected.get(point_key, [])
        rows = sorted(rows, key=lambda row: row["score"], reverse=True)
        examples = []
        for index, row in enumerate(rows[:EXAMPLES_PER_POINT], 1):
            case = row["case"]
            case["example_index"] = index
            case["example_score"] = round(row["score"], 4)
            attach_example_guides(case)
            examples.append(case)
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


def ordinal_en(value):
    if value is None:
        return "unknown"
    value = int(value)
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


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


def shanten_text(value, lang):
    if value is None:
        return "shape unclear" if lang == "en" else "形は判定しにくい"
    if lang == "ja":
        if value < 0:
            return "和了形"
        if value == 0:
            return "テンパイ"
        return f"{value}シャンテン"
    if value < 0:
        return "a complete hand"
    if value == 0:
        return "tenpai"
    return f"{value}-shanten"


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
                make_reach_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers),
                score_value,
            )

    if score >= 35000 and actual_d is not None and naga_d is not None and actual_d <= naga_d:
        score_value = gap + max(0.0, naga_d - actual_d) + (0.2 if stage in {"middle", "late"} else 0.0)
        if wants_candidate(selected, "point-01", score_value):
            add(
                selected,
                used,
                "point-01",
                make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-01"),
                score_value,
            )

    if stage == "early" and actual_cls == "simple" and naga_cls in {"honor", "terminal"}:
        score_value = gap + (0.25 if naga_read["kind"] else 0.0) + (0.2 if tile_count(hands[target], naga) >= 2 else 0.0)
        if wants_candidate(selected, "point-02", score_value):
            add(
                selected,
                used,
                "point-02",
                make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-02"),
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
                make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-05"),
                score_value,
            )

    if stage == "early" and naga != actual:
        score_value = gap + (0.2 if score < 25000 else 0.0)
        if wants_candidate(selected, "point-06", score_value):
            case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-06")
            if case and case["actual_eval"]["ukeire"] < case["naga_eval"]["ukeire"] and case["actual_eval"]["kept_honors"] >= case["naga_eval"]["kept_honors"]:
                add(selected, used, "point-06", case, score_value)

    if actual_d is not None and naga_d is not None and actual_d < 0.02 and naga_d > 0.08:
        score_value = gap + (naga_d - actual_d) + 0.15 * active_threats
        if wants_candidate(selected, "point-09", score_value):
            add(
                selected,
                used,
                "point-09",
                make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-09"),
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
                make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-14"),
                score_value,
            )

    if naga != actual and actual_read["kind"] and not naga_read["kind"]:
        score_value = preferred_bonus("point-15", row, kyoku_index, left, actual, naga) + gap
        if actual_d is not None and naga_d is not None:
            score_value += max(0.0, naga_d - actual_d)
        if active_threats:
            score_value += 0.2
        if wants_candidate(selected, "point-15", score_value):
            case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-15")
            add_best(selected, used, scores, "point-15", case, score_value)

    if naga != actual and actual_cls == "terminal" and naga_cls == "simple" and stage in {"middle", "late"}:
        score_value = preferred_bonus("point-16", row, kyoku_index, left, actual, naga) + gap
        if stage == "late":
            score_value += 0.3
        if actual_d is not None and naga_d is not None:
            score_value += max(0.0, naga_d - actual_d)
        if wants_candidate(selected, "point-16", score_value):
            case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-16")
            add_best(selected, used, scores, "point-16", case, score_value)

    if naga != actual and naga_read["kind"] and naga_read["safe_against_threat"]:
        score_value = preferred_bonus("point-17", row, kyoku_index, left, actual, naga) + gap + 0.2 * active_threats
        if stage in {"middle", "late"}:
            score_value += 0.2
        if wants_candidate(selected, "point-17", score_value):
            case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-17")
            add_best(selected, used, scores, "point-17", case, score_value)

    if naga != actual and actual_cls == "honor" and naga_cls == "simple" and tile_count(hands[target], actual) == 1:
        score_value = preferred_bonus("point-18", row, kyoku_index, left, actual, naga) + gap
        if actual_d is not None and naga_d is not None:
            score_value += max(0.0, naga_d - actual_d)
        if active_threats:
            score_value += 0.1
        if wants_candidate(selected, "point-18", score_value):
            case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-18")
            add_best(selected, used, scores, "point-18", case, score_value)

    if naga != actual and score >= 35000 and (actual_d is None or naga_d is None or actual_d <= naga_d + 0.02):
        score_value = preferred_bonus("point-19", row, kyoku_index, left, actual, naga) + gap
        if actual_d is not None and naga_d is not None:
            score_value += max(0.0, naga_d - actual_d)
        if stage in {"middle", "late"}:
            score_value += 0.2
        if wants_candidate(selected, "point-19", score_value):
            case = make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-19")
            add_best(selected, used, scores, "point-19", case, score_value)

    if stage == "late" and naga != actual:
        score_value = gap + 0.1 * active_threats
        if actual_d is not None and naga_d is not None:
            score_value += abs(actual_d - naga_d) / 2
        if wants_candidate(selected, "point-10", score_value):
            add(
                selected,
                used,
                "point-10",
                make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-10"),
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
                make_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-12"),
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
                case = make_yakuhai_cleanup_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, threats)
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
                    make_simple_discard_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-11"),
                    score_value,
                )


def try_call_points(selected, used, row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, previous_state=None):
    msg = state.get("info", {}).get("msg", {})
    if msg.get("actor") != row["actor"] or msg.get("type") not in base.HURO_TYPES:
        return
    active_threats = sum(1 for value in reached if value)
    left = msg.get("left_hai_num") or 0
    post_discard = msg.get("real_dahai")
    exposed_bonus = 0.2 if msg.get("type") == "pon" else 0.1
    terminal_or_honor_exit = post_discard and base.tile_class(post_discard) in {"honor", "terminal"}
    call_case = make_call_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-03", previous_state)

    score_value = exposed_bonus + max(0.0, (70 - left) / 100) + call_score_adjustment(call_case or {})
    if wants_candidate(selected, "point-03", score_value):
        add(
            selected,
            used,
            "point-03",
            call_case,
            score_value,
        )

    if active_threats or terminal_or_honor_exit:
        call_case = make_call_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-04", previous_state)
        score_value = 0.4 + 0.2 * active_threats + (0.2 if terminal_or_honor_exit else 0.0) + call_score_adjustment(call_case or {})
        if wants_candidate(selected, "point-04", score_value):
            add(
                selected,
                used,
                "point-04",
                call_case,
                score_value,
            )

    call_case = make_call_case(row, kyoku_index, pos, start, state, hands, discards, melds, reached, dora_markers, "point-07", previous_state)
    score_value = 0.3 + exposed_bonus + (0.2 if left <= 40 else 0.0) + call_score_adjustment(call_case or {})
    if wants_candidate(selected, "point-07", score_value):
        add(
            selected,
            used,
            "point-07",
            call_case,
            score_value,
        )


def collect_examples():
    selected = {}
    scores = {}
    used = {}
    for row in base.parse_rows():
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
                            actual_declares_reach,
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

                elif msg_type == "dahai":
                    tile = msg.get("pai")
                    if actor is not None and tile:
                        discards[actor].append(tile)

    return selected


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = finalize_examples(collect_examples())
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    missing = [key for key in sorted(POINT_TEXT) if key not in data]
    counts = {key: len(value) for key, value in data.items()}
    print(f"wrote {OUT}; points={len(data)} examples={sum(counts.values())} missing={missing}")


if __name__ == "__main__":
    main()
