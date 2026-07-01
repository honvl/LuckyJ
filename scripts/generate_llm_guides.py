#!/usr/bin/env python3
import json
import urllib.request
import os
import argparse
import subprocess
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

API_KEY = os.environ.get("CLIPROXY_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("CLIPROXY_MODEL", "gemini-3.5-flash-low")
URL = "http://localhost:8317/v1/chat/completions"
REQUEST_TIMEOUT = int(os.environ.get("CLIPROXY_TIMEOUT", "180"))
PROMPT_VERSION = "yaku-skeleton-v2"
CACHE_PATH = Path("data/llm_guides_cache.json")
EXAMPLES_PATH = Path("site/point-examples.json")
STRATEGY_EN_PATH = Path("site/strategy-guides.json")
STRATEGY_JA_PATH = Path("site/strategy-guides.ja.json")

SYSTEM_PROMPT = """You are an expert Mahjong commentator and tutor for the LuckyJ Mahjong playbook.
Your task is to analyze a specific Mahjong decision where the AI agent "LuckyJ" differs from another engine "Nishiki" (or NAGA).
You will be provided with the game state, candidate decisions, shape facts, threat levels, active yakuhai tiles, and the core human strategic commentary.
Your goal is to output an analysis block in Alternative 2 style in both English and Japanese that is intelligent, human-written, and directly connects this specific match example to the core strategic concept.

Strict Mahjong Rules & Constraints:
1. Only refer to wind tiles as "yaku tiles", "yakuhai", or "yaku switches" if they are listed in the 'Active Yakuhai for Self' list. Guest winds (non-yakuhai winds) do NOT carry yaku value for self.
2. Evaluate the potential hand value and speed accurately based on the actual tiles. Do NOT assume a hand is a "1,000-point hand" or "cheap" unless it is an open hand with only one 1-han yaku and no dora. As a dealer, hands automatically gain a 1.5x value bonus, and hands with dora or yaku pairs often carry substantial value.
3. Use the human strategic commentary ONLY for high-level conceptual reference. Do NOT copy its literal details (such as "1,000 point hand", "West", "South", "East") unless they are 100% true for the current example hand.
4. Named yaku routes must come from the supplied "Plausible Route Facts". Do NOT invent toitoi, chiitoitsu, pinfu, honitsu, tanyao, or any other yaku because a hand has some pairs or sequences. If a route is listed under "Do Not Claim", do not mention it as kept alive or available. If a route is described as distant, background, or not foreground, translate it into plain shape language instead of naming the yaku.
5. Triplet check: A triplet (koutsu) requires 3 identical tiles. A quad (kantsu) requires 4. If the "Visible on Board" count for a tile is 3 (with 1 in your hand and 2 on the table/discards), it is mathematically IMPOSSIBLE to form a triplet of that tile. Do NOT describe such a tile as a "potential triplet" or "potential yaku triplet". If the visible count is 4, it is impossible to even form a pair.
6. For call examples, the supplied "NAGA Call Model Heads" and "NAGA Post-Call Discard Heads" are authoritative. If a model backs LuckyJ's exact call line, NEVER say that model skipped the call, declined, or preferred staying closed. If the call action matches but the post-call discard differs, describe the disagreement as a post-call discard split, not a call-versus-no-call split.
7. For call examples, a model can choose the same call type but a different call line. Treat that as a real discrepancy, not agreement with LuckyJ.
8. Never quote raw audit field names or model weights in reader-facing prose. Translate them into natural Mahjong commentary.
9. The "Teaching Fit for This Point" section is authoritative. It explains why this exact example belongs under the playbook point. Do not move the example to a different lesson, and do not invent a current riichi/open-hand threat when the teaching fit says the example is pre-threat or has no opponent riichi.
10. For call examples, "Post-Call Shape Facts" is authoritative. If the post-call shanten is 0, the hand is tenpai after the call and discard; NEVER describe LuckyJ's resulting hand as 1-shanten, one-away, or still trying to reach tenpai. If the post-call shanten is 1, describe it as 1-shanten, not tenpai.
11. Do not describe a triplet or duplicated number tiles as a defensive reserve merely because there are multiple copies. Only call a tile a defensive reserve when the supplied safety facts show target-specific safety; otherwise describe the real next discard or shape plan.

Style Guidelines for English (Alternative 2 style):
- Start with first-person plural: "We are in [Round] [Dealer/Player status], holding [Score] points. [Context about board/opponents, e.g. 'With opponents already showing active melds' or 'With an opponent already declaring riichi']."
- Ask a question about the hand state/threats: e.g. "how do we value our hand shape?" or "how do we balance our hand's value against the danger on the board?"
- Describe LuckyJ's play, mentioning the block being broken or removed when the data supports it. Use the supplied shanten facts exactly: "LuckyJ breaks the [[6m]][[7m]] block by cutting [[6m]]." or "LuckyJ takes tenpai after the call by discarding [[4s]]." Use double brackets [[tile]] format for tiles (e.g., [[6m]]).
- Explain why it is safe or why it is a threat buy, citing safety metrics from the data: "Because [[6m]] is genbutsu to toimen and suji to kamicha/shimocha, this discard offers excellent safety across the board." or "While Nishiki's path avoids immediate risk, it kills the hand's potential..."
- Compare with Nishiki's choice only when the supplied data shows a different choice. If Nishiki agrees with LuckyJ, say so directly and do not invent a false contrast.
- Summarize the strategic trade-off: "However, LuckyJ prioritizes defense over speed here. Discarding [[6m]] leaves [[7m]] floating..." or "LuckyJ pushes here, valuing the dealer equity over a passive fold."
- Do not use generic placeholders.

Style Guidelines for Japanese:
- Produce a high-quality Japanese translation of the English analysis, matching the natural terminology of professional Japanese Mahjong commentators (e.g. テンパイ, シャンテン, 現物, 筋, 押し引き, 親番, 役牌, 客風, ピンフ, チートイツ, トイトイ, etc.).

Drill Question and Answer:
- prompt_en: A drill question testing the user's understanding of the situation (e.g., safety status of a tile, seat of the dealer, who is in lead).
- answer_en: The correct short answer to the question.
- prompt_ja: The Japanese translation of the drill question.
- answer_ja: The Japanese translation of the answer.

You MUST respond with a JSON object in the following format:
{
  "read_en": "...",
  "prompt_en": "...",
  "answer_en": "...",
  "read_ja": "...",
  "prompt_ja": "...",
  "answer_ja": "..."
}
"""

def clean_and_parse_json(content):
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    return json.loads(content.strip())

def make_llm_request(prompt):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"}
    }
    
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        },
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as res:
        response_data = json.loads(res.read().decode("utf-8"))
        content = response_data["choices"][0]["message"]["content"]
        return clean_and_parse_json(content)


def cache_entry_is_current(entry):
    return (entry or {}).get("meta", {}).get("prompt_version") == PROMPT_VERSION


FALSE_TENPAI_CALL_SHAPE_PATTERNS = [
    re.compile(r"\bLuckyJ\b[^.。]{0,180}\b(?:1-shanten|one[- ]?away)\b", re.I),
    re.compile(r"\b(?:This call|The call|After the call|By discarding|By calling)\b[^.。]{0,180}\b(?:1-shanten|one[- ]?away)\b", re.I),
    re.compile(r"(?:LuckyJ|この鳴き|鳴いた後|切ることで)[^。]{0,180}(?:一向聴|1シャンテン|テンパイまであと一歩)", re.I),
]


def cache_entry_text(entry):
    return " ".join(
        str((entry.get(section) or {}).get(field, ""))
        for section in ("guide", "guide_ja")
        for field in ("read", "prompt", "answer")
    )


def cached_guide_conflicts(case, entry):
    if not entry:
        return False
    shape = case.get("post_call_eval") or {}
    if case.get("kind") == "call" and shape.get("shanten") is not None and shape.get("shanten") <= 0:
        text = cache_entry_text(entry)
        return any(pattern.search(text) for pattern in FALSE_TENPAI_CALL_SHAPE_PATTERNS)
    return False

def get_winds_and_yakuhai(case):
    round_str = case.get("round", "")
    prevalent_wind = round_str[0] if round_str else "?"
    
    seat_wind = "?"
    players = case.get("table", {}).get("scores", [])
    for p in players:
        if p.get("seat") == "self":
            seat_wind = p.get("wind", "?")
            break
            
    dragons = ["P", "F", "C"]
    active_yakuhai = [prevalent_wind, seat_wind] + dragons
    active_yakuhai = list(set([w for w in active_yakuhai if w != "?"]))
    
    all_winds = ["E", "S", "W", "N"]
    guest_winds = [w for w in all_winds if w not in active_yakuhai]
    
    return prevalent_wind, seat_wind, active_yakuhai, guest_winds

def calculate_visible_tiles(case):
    visible = Counter()
    hand_str = case.get("hand", "")
    for tile in hand_str.split():
        visible[base_tile(tile)] += 1
        
    players = case.get("table", {}).get("players", [])
    for p in players:
        for tile in p.get("discards", []):
            visible[base_tile(tile)] += 1
        for meld in p.get("melds", []):
            for tile in meld.get("tiles", []):
                visible[base_tile(tile)] += 1
                
    return visible


def base_tile(tile):
    return str(tile or "").replace("r", "")


def tile_suit_rank(tile):
    tile = base_tile(tile)
    if len(tile) < 2 or tile[-1] not in {"m", "p", "s"}:
        return None, None
    try:
        return tile[-1], int(tile[:-1])
    except ValueError:
        return None, None


def hand_counts(case):
    return Counter(base_tile(tile) for tile in case.get("hand", "").split())


def sequence_block_summary(counts):
    completed = []
    adjacent = []
    gaps = []
    for suit in "mps":
        for rank in range(1, 8):
            if counts[f"{rank}{suit}"] and counts[f"{rank + 1}{suit}"] and counts[f"{rank + 2}{suit}"]:
                completed.append(f"{rank}{suit} {rank + 1}{suit} {rank + 2}{suit}")
        for rank in range(1, 9):
            if counts[f"{rank}{suit}"] and counts[f"{rank + 1}{suit}"]:
                adjacent.append(f"{rank}{suit} {rank + 1}{suit}")
        for rank in range(1, 8):
            if counts[f"{rank}{suit}"] and counts[f"{rank + 2}{suit}"]:
                gaps.append(f"{rank}{suit} {rank + 2}{suit}")
    return completed, adjacent, gaps


def sequence_seed_for(counts, suit, start):
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
    return {"suit": suit, "start": start, "tiles": tiles, "present": present, "missing": missing, "kind": kind}


def detect_sanshoku_routes(counts):
    routes = []
    for start in range(1, 8):
        seeds = [sequence_seed_for(counts, suit, start) for suit in "mps"]
        if all(len(seed["present"]) >= 2 for seed in seeds):
            route_tiles = f"{start}{start + 1}{start + 2}"
            parts = []
            missing = []
            complete_count = 0
            for seed in seeds:
                if seed["kind"] == "complete":
                    complete_count += 1
                    parts.append(f"{' '.join(seed['present'])} complete")
                else:
                    parts.append(f"{' '.join(seed['present'])} needs {'/'.join(seed['missing'])}")
                    missing.extend(seed["missing"])
            strength = "strong" if complete_count or len(missing) <= 3 else "speculative"
            routes.append(
                {
                    "name": f"{route_tiles} sanshoku doujun",
                    "strength": strength,
                    "description": f"{route_tiles} sanshoku doujun seed: " + "; ".join(parts),
                    "missing": missing,
                }
            )
    return routes


def tile_is_terminal(tile):
    _suit, rank = tile_suit_rank(tile)
    return rank in {1, 9}


def tile_is_honor(tile):
    suit, _rank = tile_suit_rank(tile)
    return suit is None


def tile_is_simple(tile):
    suit, rank = tile_suit_rank(tile)
    return suit is not None and rank not in {1, 9}


def suited_tile_count(counts, suit):
    return sum(counts[f"{rank}{suit}"] for rank in range(1, 10))


def honor_tile_count(counts):
    return sum(counts[tile] for tile in ["E", "S", "W", "N", "P", "F", "C"])


def total_tile_count(counts):
    return sum(counts.values())


def route_line(name, detail):
    return f"{name}: {detail}"


def detect_flush_routes(counts):
    routes = []
    total = total_tile_count(counts)
    honors = honor_tile_count(counts)
    for suit in "mps":
        suited = suited_tile_count(counts, suit)
        off_suit = total - suited - honors
        non_suit = total - suited
        if suited >= 8 and honors == 0 and off_suit == 0:
            routes.append(route_line("chinitsu", f"all {total} tiles are in {suit}"))
        elif suited + honors >= 10 and suited >= 5 and off_suit == 0 and honors:
            routes.append(route_line("honitsu", f"{suited} {suit}-suit tiles plus {honors} honors, no off-suit tiles"))
        elif suited + honors >= 10 and suited >= 6 and off_suit <= 2 and honors:
            routes.append(route_line("honitsu strong candidate", f"{suited} {suit}-suit tiles plus {honors} honors; {off_suit} off-suit tile(s) remain"))
        elif suited + honors >= 10 and suited >= 5 and off_suit <= 3 and honors:
            routes.append(route_line("honitsu skeleton", f"{suited} {suit}-suit tiles plus {honors} honors; {off_suit} off-suit tile(s) to clean"))
        if suited >= 10 and non_suit <= 2:
            routes.append(route_line("chinitsu strong candidate", f"{suited} {suit}-suit tiles; {non_suit} non-suit tile(s) remain"))
        elif suited >= 9 and non_suit <= 3:
            routes.append(route_line("chinitsu skeleton", f"{suited} {suit}-suit tiles; {non_suit} non-suit tile(s) to clean"))
    return routes


def detect_ittsu_routes(counts):
    routes = []
    for suit in "mps":
        seeds = [sequence_seed_for(counts, suit, start) for start in (1, 4, 7)]
        if all(len(seed["present"]) >= 2 for seed in seeds):
            parts = []
            for seed in seeds:
                if seed["kind"] == "complete":
                    parts.append(f"{' '.join(seed['present'])} complete")
                else:
                    parts.append(f"{' '.join(seed['present'])} needs {'/'.join(seed['missing'])}")
            routes.append(route_line("ittsu", f"{suit}-suit 123/456/789 seed: " + "; ".join(parts)))
    return routes


def detect_identical_sequence_routes(counts):
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


def detect_triplet_family_routes(counts):
    routes = []
    pair_tiles = [tile for tile, count in counts.items() if count >= 2]
    triplet_tiles = [tile for tile, count in counts.items() if count >= 3]
    triplet_seed_count = len(pair_tiles) + len(triplet_tiles)
    if triplet_seed_count >= 4:
        routes.append(route_line("toitoi", f"{triplet_seed_count} pair/triplet seed(s): {' '.join(pair_tiles[:8])}"))

    for rank in range(1, 10):
        seeds = [f"{rank}{suit}" for suit in "mps" if counts[f"{rank}{suit}"] >= 2]
        if len(seeds) == 3:
            routes.append(route_line("sanshoku dokou", f"triplet seeds across suits at {rank}: {' '.join(seeds)}"))

    dragons = [tile for tile in ["P", "F", "C"] if counts[tile] >= 2]
    dragon_triplets = [tile for tile in ["P", "F", "C"] if counts[tile] >= 3]
    if len(dragon_triplets) == 3:
        routes.append(route_line("daisangen", "all three dragon triplets are present"))
    elif len(dragons) >= 2:
        routes.append(route_line("shousangen/daisangen seed", f"dragon pair/triplet seeds: {' '.join(dragons)}"))

    winds = [tile for tile in ["E", "S", "W", "N"] if counts[tile] >= 2]
    wind_triplets = [tile for tile in ["E", "S", "W", "N"] if counts[tile] >= 3]
    if len(wind_triplets) == 4:
        routes.append(route_line("daisuushi", "all four wind triplets are present"))
    elif len(winds) >= 3:
        routes.append(route_line("shousuushi/daisuushi seed", f"wind pair/triplet seeds: {' '.join(winds)}"))

    return routes


def detect_outside_and_simple_routes(counts, completed, adjacent, gaps):
    routes = []
    tiles = list(counts.elements())
    total = len(tiles)
    honors = honor_tile_count(counts)
    terminals = sum(count for tile, count in counts.items() if tile_is_terminal(tile))
    simples = sum(count for tile, count in counts.items() if tile_is_simple(tile))
    outside = honors + terminals

    if total and simples == total:
        routes.append(route_line("tanyao", "all current tiles are simples"))
    elif total and simples >= 10 and outside <= 2:
        routes.append(route_line("tanyao candidate", f"{simples} simple tiles with {outside} terminal/honor tile(s) to clean"))

    if outside == total and total:
        routes.append(route_line("honroutou", "all current tiles are terminals or honors"))
    elif outside >= 10:
        routes.append(route_line("honroutou/chanta candidate", f"{outside} terminal/honor tiles"))

    outside_blocks = [block for block in completed + adjacent + gaps if any(part[0] in {"1", "9"} for part in block.split())]
    if outside >= 7 and outside_blocks:
        routes.append(route_line("chanta candidate", f"{outside} terminal/honor tiles with outside block(s): {'; '.join(outside_blocks[:4])}"))
    if honors == 0 and terminals >= 6 and outside_blocks:
        routes.append(route_line("junchan candidate", f"{terminals} terminal tiles, no honors, outside block(s): {'; '.join(outside_blocks[:4])}"))

    return routes


def detect_rare_shape_routes(counts):
    routes = []
    terminals_honors = ["1m", "9m", "1p", "9p", "1s", "9s", "E", "S", "W", "N", "P", "F", "C"]
    unique_orphans = [tile for tile in terminals_honors if counts[tile]]
    pair_orphans = [tile for tile in terminals_honors if counts[tile] >= 2]
    if len(unique_orphans) >= 10:
        detail = f"{len(unique_orphans)}/13 unique terminals/honors"
        if pair_orphans:
            detail += f", pair candidate {'/'.join(pair_orphans)}"
        routes.append(route_line("kokushi musou seed", detail))

    honors = honor_tile_count(counts)
    if honors >= 10:
        routes.append(route_line("tsuuiisou seed", f"{honors} honor tiles"))

    terminal_count = sum(count for tile, count in counts.items() if tile_is_terminal(tile))
    if terminal_count >= 10 and honors == 0:
        routes.append(route_line("chinroutou seed", f"{terminal_count} terminal tiles and no honors"))

    green_tiles = {"2s", "3s", "4s", "6s", "8s", "F"}
    green_count = sum(counts[tile] for tile in green_tiles)
    off_green = total_tile_count(counts) - green_count
    if green_count >= 10 and off_green <= 2:
        routes.append(route_line("ryuuiisou seed", f"{green_count} green tiles, {off_green} off-green tile(s)"))

    for suit in "mps":
        suited = suited_tile_count(counts, suit)
        honors = honor_tile_count(counts)
        off_suit = total_tile_count(counts) - suited - honors
        if suited >= 10 and honors == 0 and off_suit == 0 and counts[f"1{suit}"] >= 2 and counts[f"9{suit}"] >= 2:
            routes.append(route_line("chuuren poutou seed", f"{suited} tiles in {suit} with terminal density"))

    return routes


def detect_sequence_routes(counts):
    routes = []
    routes.extend(route["description"] for route in detect_sanshoku_routes(counts))
    routes.extend(detect_ittsu_routes(counts))
    routes.extend(detect_identical_sequence_routes(counts))
    return routes


def plausible_route_facts(case, active_yakuhai, visible):
    counts = hand_counts(case)
    pair_tiles = [tile for tile, count in counts.items() if count >= 2]
    triplet_tiles = [tile for tile, count in counts.items() if count >= 3]
    completed, adjacent, gaps = sequence_block_summary(counts)
    sequence_routes = detect_sequence_routes(counts)
    triplet_routes = detect_triplet_family_routes(counts)
    flush_routes = detect_flush_routes(counts)
    outside_simple_routes = detect_outside_and_simple_routes(counts, completed, adjacent, gaps)
    rare_routes = detect_rare_shape_routes(counts)
    self_open_melds = len(next((p for p in case.get("table", {}).get("players", []) if p.get("seat") == "self"), {}).get("melds", []))

    plausible = []
    do_not_claim = []
    notes = []

    live_yakuhai = []
    dead_or_blocked_honors = []
    for tile in sorted(set(active_yakuhai)):
        in_hand = counts[tile]
        if not in_hand:
            continue
        remaining = 4 - visible[tile]
        if in_hand >= 2 and remaining >= 1:
            live_yakuhai.append(f"[[{tile}]] pair can still become a yakuhai triplet")
        elif in_hand == 1 and remaining >= 2:
            live_yakuhai.append(f"single [[{tile}]] can still pair/triplet, but it is speculative")
        else:
            dead_or_blocked_honors.append(f"[[{tile}]] has {visible[tile]} visible, so it cannot become a triplet from the current hand")
    if live_yakuhai:
        plausible.append("yakuhai or riichi route through live value honors")
        notes.extend(live_yakuhai)
    if dead_or_blocked_honors:
        notes.extend(dead_or_blocked_honors)

    for route in sequence_routes + triplet_routes + flush_routes + outside_simple_routes + rare_routes:
        plausible.append(route)

    if len(completed) + len(adjacent) + len(gaps) >= 4:
        plausible.append("ordinary closed-hand development through loose sequence blocks")

    if len(pair_tiles) >= 4:
        plausible.append("chiitoitsu route through four or more current pairs")
    elif len(pair_tiles) == 3:
        do_not_claim.append("chiitoitsu is only a distant three-pair skeleton here; describe pair density or safety instead of naming chiitoitsu")
    else:
        do_not_claim.append(f"chiitoitsu is not a live plan now: only {len(pair_tiles)} pair(s) are present")

    if len(pair_tiles) + len(triplet_tiles) < 3:
        do_not_claim.append(f"toitoi is not a live plan now: only {len(pair_tiles)} pair/triplet seed(s) are present")
    elif len(pair_tiles) + len(triplet_tiles) == 3:
        do_not_claim.append("toitoi is only a distant three-seed skeleton here; describe pair/triplet density instead of naming toitoi")

    value_pair_tiles = [tile for tile in pair_tiles if tile in active_yakuhai]
    if self_open_melds:
        do_not_claim.append("pinfu is impossible after opening")
    elif len(completed) + len(adjacent) >= 4 and not value_pair_tiles:
        notes.append("ordinary closed sequence development is available, but do not foreground pinfu unless the final wait and non-value pair are the actual lesson")
    else:
        reason = "not enough sequence structure"
        if value_pair_tiles:
            reason = f"value-honor pair(s) {', '.join(f'[[{tile}]]' for tile in value_pair_tiles)} dominate the current shape"
        do_not_claim.append(f"pinfu is not supported by the current hand: {reason}")

    if not plausible:
        plausible.append("no named yaku route is clearly established; describe shape, safety, and future flexibility instead")

    return {
        "pairs": pair_tiles,
        "triplets": triplet_tiles,
        "completed_sequences": completed,
        "adjacent_blocks": adjacent,
        "gap_blocks": gaps,
        "sequence_routes": sequence_routes,
        "triplet_routes": triplet_routes,
        "flush_routes": flush_routes,
        "outside_simple_routes": outside_simple_routes,
        "rare_routes": rare_routes,
        "plausible": plausible,
        "do_not_claim": do_not_claim,
        "notes": notes,
    }


def route_facts_text(facts):
    sections = [
        ("Current pairs", facts["pairs"] or ["none"]),
        ("Completed sequences", facts["completed_sequences"] or ["none"]),
        ("Adjacent two-tile blocks", facts["adjacent_blocks"] or ["none"]),
        ("Gap blocks", facts["gap_blocks"] or ["none"]),
        ("Sequence yaku seeds", facts["sequence_routes"] or ["none"]),
        ("Triplet/pair yaku seeds", facts["triplet_routes"] or ["none"]),
        ("Flush yaku seeds", facts["flush_routes"] or ["none"]),
        ("Outside/simple yaku seeds", facts["outside_simple_routes"] or ["none"]),
        ("Rare/yakuman seeds", facts["rare_routes"] or ["none"]),
        ("Plausible routes", facts["plausible"]),
        ("Do Not Claim", facts["do_not_claim"]),
        ("Honor notes", facts["notes"] or ["none"]),
    ]
    return "\n".join(f"- {label}: {', '.join(values)}" for label, values in sections)


def call_model_heads_text(case):
    heads = case.get("call_model_heads") or []
    if not heads:
        return "- Not supplied"
    lines = ["- If a head chooses the same call type but not the exact call line, treat that as a real disagreement."]
    for head in heads:
        label = head.get("label") or head.get("key")
        action = head.get("top_action") or "unknown"
        if head.get("supports_call"):
            line = f"- {label}: backs LuckyJ's exact {action} line."
        elif head.get("prefers_pass"):
            line = f"- {label}: would not call."
        else:
            line = f"- {label}: chooses a different {action} line."
        lines.append(line)
    return "\n".join(lines)


def post_call_discard_heads_text(case):
    heads = case.get("post_call_model_heads") or []
    if not heads:
        return "- Not supplied"
    lines = []
    for head in heads:
        label = head.get("label") or head.get("key")
        top = head.get("top")
        if head.get("matches_luckyj"):
            lines.append(f"- {label}: after calling, discards LuckyJ's [[{top}]].")
        else:
            lines.append(f"- {label}: after calling, would discard [[{top}]] instead.")
    return "\n".join(lines)


def opponents(case):
    return [p for p in case.get("table", {}).get("players", []) if p.get("seat") != "self"]


def opponent_riichi_count(case):
    return sum(1 for p in opponents(case) if p.get("reached"))


def opponent_meld_count(case):
    return sum(len(p.get("melds") or []) for p in opponents(case))


def active_threat_count(case):
    return sum(1 for p in opponents(case) if p.get("reached") or p.get("melds"))


def tile_class(tile):
    tile = base_tile(tile)
    if tile in {"E", "S", "W", "N", "P", "F", "C"}:
        return "honor"
    _suit, rank = tile_suit_rank(tile)
    if rank in {1, 9}:
        return "terminal"
    if rank is None:
        return "unknown"
    return "simple"


def eval_fact_text(label, item):
    if not item:
        return f"{label}: no shape data"
    safety = item.get("kept_safety") or {}
    return (
        f"{label}: shanten {item.get('shanten')}, visible ukeire {item.get('ukeire')}, "
        f"kept honors {item.get('kept_honors')}, kept terminals {item.get('kept_terminals')}, "
        f"kept live safety tiles {safety.get('against_threat', 0)}"
    )


def safety_read_text(label, read):
    if not read:
        return f"{label}: not supplied"
    parts = [
        f"{label}: [[{read.get('tile')}]]",
        f"kind={read.get('kind') or 'none'}",
        f"sotogawa={'yes' if read.get('has_sotogawa') else 'no'}",
        f"safe_against_live_threat={'yes' if read.get('safe_against_threat') else 'no'}",
        f"opponents={read.get('opponents', 0)}",
    ]
    targets = []
    for item in read.get("against") or []:
        sources = []
        if item.get("genbutsu_sources"):
            sources.append("genbutsu")
        if item.get("suji_sources"):
            sources.append("suji")
        if item.get("sotogawa_sources"):
            sources.append("sotogawa")
        if sources:
            threat = "riichi" if item.get("reached") else f"{item.get('open_melds', 0)} open meld(s)"
            targets.append(f"{item.get('seat_label')} ({'/'.join(sources)}, {threat})")
    if targets:
        parts.append("targets=" + "; ".join(targets))
    return ", ".join(parts)


def self_hand_tile_threats_text(case, remaining_tiles=None):
    players = case.get("table", {}).get("players", [])
    self_player = next((p for p in players if p.get("seat") == "self"), None)
    if not self_player:
        return "No self hand tile threat data supplied."

    remaining = Counter(remaining_tiles or [])
    rows_by_tile = {}
    for threat in self_player.get("tile_threats", []):
        tile = threat.get("tile")
        if remaining and remaining.get(tile, 0) <= 0:
            continue
        bars = threat.get("bars", [])
        values = [b.get("danger") for b in bars if b.get("danger") is not None]
        max_danger = max(values) if values else None
        bars_desc = ", ".join(f"{b.get('label')}: {b.get('danger')}" for b in bars)
        rows_by_tile[tile] = {
            "tile": tile,
            "count": remaining.get(tile, 1) if remaining else 1,
            "max_danger": max_danger,
            "bars": bars_desc,
        }

    if not rows_by_tile:
        return "No matching tile threat data supplied for the remaining hand."

    rows = sorted(rows_by_tile.values(), key=lambda row: (row["max_danger"] is None, row["max_danger"] or 0, row["tile"]))
    return "\n".join(
        f"- [[{row['tile']}]] x{row['count']}: max danger {row['max_danger']}; {row['bars']}"
        for row in rows
    )


def model_split_text(case):
    heads = case.get("model_heads") or []
    if not heads:
        return "No discard model-head data supplied."
    lines = []
    for head in heads:
        line = f"{head.get('label') or head.get('key')}: top [[{head.get('top')}]] {head.get('top_prob')}, LuckyJ [[{case.get('actual')}]] {head.get('actual_prob')}"
        if head.get("matches_luckyj"):
            line += ", matches LuckyJ"
        elif head.get("matches_nishiki"):
            line += ", matches Nishiki"
        lines.append(line)
    return "; ".join(lines)


def teaching_fit_text(case):
    point = case.get("point")
    actual = case.get("actual")
    naga = case.get("naga")
    actual_eval = case.get("actual_eval") or {}
    naga_eval = case.get("naga_eval") or {}
    lines = [
        f"Point: {point} - {case.get('title', '')}",
        f"Candidate classes: LuckyJ actual [[{actual}]] is {tile_class(actual)}, Nishiki top [[{naga}]] is {tile_class(naga)}",
        f"Opponent state: {opponent_riichi_count(case)} opponent riichi, {opponent_meld_count(case)} total opponent meld(s), {active_threat_count(case)} active threat opponent(s)",
        eval_fact_text("LuckyJ branch after actual discard", actual_eval),
        eval_fact_text("Nishiki branch after top discard", naga_eval),
        safety_read_text("Actual discarded tile safety", case.get("actual_tile_safety")),
        safety_read_text("Kept Nishiki tile safety", case.get("kept_tile_safety")),
    ]

    if point == "point-01":
        lines.append("Teaching fit: leader/large-score example. Explain reduced ambition plus concrete danger or retained-safety advantage, not generic efficiency.")
    elif point == "point-02":
        lines.append("Teaching fit: early branch-point preservation. Explain what the kept honor/terminal still does as value, safety, pair, or route flexibility.")
    elif point == "point-03":
        lines.append("Teaching fit: call example with a real NAGA call/post-call discrepancy. Do not describe call versus no-call unless the call heads actually avoid the call.")
    elif point == "point-04":
        lines.append("Teaching fit: open-hand safety example. After the call, name the post-call discard plus the real next safe tile or release plan. Do not invent a defensive reserve if the remaining shortened hand lacks one.")
    elif point == "point-05":
        lines.append("Teaching fit: pre-threat future-liability cleanup. This point excludes reached examples: no opponent should already be in riichi. Explain why carrying the actual simple tile is bad before a future riichi or second call appears.")
    elif point == "point-06":
        lines.append("Teaching fit: early value tradeoff. LuckyJ gives up visible ukeire because the score job/value or retained honor/terminal/safety route matters more.")
    elif point == "point-07":
        lines.append("Teaching fit: tempo call with a named purpose. State what the call creates or contests before praising speed.")
    elif point == "point-08":
        lines.append("Teaching fit: riichi declaration example. Explain declaration pressure only when LuckyJ actually reaches.")
    elif point == "point-09":
        lines.append("Teaching fit: repricing after the draw. Explain the current discard plus the next likely discard chain, not this tile in isolation.")
    elif point == "point-10":
        lines.append("Teaching fit: late precision. Frame the decision as win, safe tenpai, or fold because speculative routes have expired.")
    elif point == "point-11":
        lines.append("Teaching fit: drawn-hand equity. Explain safe tenpai/draw payment, not just direct winning.")
    elif point == "point-12":
        lines.append(f"Teaching fit: model disagreement review prompt. Use the model split as evidence: {model_split_text(case)}")
    elif point == "point-13":
        lines.append("Teaching fit: yakuhai cleanup against an open hand. Explain why the honor is still an opponent yaku condition.")
    elif point == "point-14":
        lines.append("Teaching fit: keep a named genbutsu/suji tile. Name the exact target opponent for the kept safe tile.")
    elif point == "point-15":
        lines.append("Teaching fit: stale safe-tile spend. The actual discarded tile has some safety label but is not safe against the live threat, and the hand retains another live safety answer.")
    elif point == "point-16":
        lines.append("Teaching fit: outside/terminal cut preserving the inside route. Explain the connector kept by not following Nishiki.")
    elif point == "point-17":
        lines.append("Teaching fit: every kept safe tile needs a live target. Name who the kept tile answers and why that target matters now.")
    elif point == "point-18":
        lines.append("Teaching fit: honor role label. Say whether the honor is self-value, opponent condition, dead material, or defensive material.")
    elif point == "point-19":
        lines.append("Teaching fit: leader safety qualifier. Explain reduced ambition while still checking concrete danger, shape, and next-turn safety.")
    return "\n".join(f"- {line}" for line in lines)


def make_prompt(case, guide_en, guide_ja):
    is_call = case.get("kind") == "call"
    prevalent_wind, seat_wind, active_yakuhai, guest_winds = get_winds_and_yakuhai(case)
    is_dealer_self = case.get("table", {}).get("dealer") == "self"
    visible = calculate_visible_tiles(case)
    route_facts = plausible_route_facts(case, active_yakuhai, visible)
    
    # Honors and candidate visible counts
    tracked_tiles = ["E", "S", "W", "N", "P", "F", "C"]
    actual = case.get("actual")
    naga = case.get("naga")
    if actual and actual not in tracked_tiles:
        tracked_tiles.append(actual)
    if naga and naga not in tracked_tiles:
        tracked_tiles.append(naga)
        
    visible_lines = []
    hand_list = case.get("hand", "").split()
    for tile in tracked_tiles:
        tile = base_tile(tile)
        count = visible[tile]
        in_hand = sum(1 for item in hand_list if base_tile(item) == tile)
        in_discards = count - in_hand
        visible_lines.append(f"- [[{tile}]]: {count} visible on board (your hand: {in_hand}, table/discards: {in_discards})")
    visible_str = "\n".join(visible_lines)

    # Opponent rivers & melds
    players = case.get("table", {}).get("players", [])
    rivers_str = ""
    for p in players:
        seat = p.get("seat", "")
        if seat == "self":
            continue
        discards = " ".join(f"[[{t}]]" for t in p.get("discards", []))
        melds = []
        for meld in p.get("melds", []):
            melds.append("".join(f"[[{t}]]" for t in meld.get("tiles", [])))
        melds_str = ", ".join(melds) if melds else "None"
        rivers_str += f"- {seat.capitalize()}: River: {discards} | Open Melds: {melds_str}\n"

    prompt = f"""Mahjong Playbook Point: {case['point']}
Title: {case.get('title', '')}
Lesson: {case.get('lesson', '')}

Core Playbook Concept (Human Strategic Reference):
- English Concept: {guide_en.get('read', '')}
- Japanese Concept: {guide_ja.get('read', '')}

Teaching Fit for This Point:
{teaching_fit_text(case)}

Mahjong Rules Context for Self:
- Prevalent Wind: {prevalent_wind}
- Seat Wind: {seat_wind} (Is dealer: {"Yes" if is_dealer_self else "No"})
- Active Yakuhai for Self: {", ".join(active_yakuhai)}
- Guest Winds (no yaku value) for Self: {", ".join(guest_winds)}

Visible Tile Counts on Board:
{visible_str}

Opponent Rivers & Melds:
{rivers_str}

Match Situation:
- Round: {case.get('round', '')}
- Stage: {case.get('stage', '')} (early/middle/late)
- Tiles remaining in wall: {case.get('left', '')}
- Score: {case.get('score', '')} (Band: {case.get('score_band', '')})
- Current Rank: {case.get('current_rank', '')}
- Outcome: {case.get('outcome', '')}

Player Hand: {case.get('hand', '')}

Plausible Route Facts:
{route_facts_text(route_facts)}

"""

    if is_call:
        shape = case.get("post_call_eval") or {}
        shanten = shape.get("shanten")
        shanten_meaning = "tenpai" if shanten == 0 else ("complete hand" if shanten is not None and shanten < 0 else f"{shanten}-shanten" if shanten is not None else "unknown")
        prompt += f"""Decisions Comparison:
- LuckyJ Call Action: Called {case.get('call')} on [[{case.get('called_tile')}]] from the {case.get('called_from', '')}, then discarded [[{case.get('discard_after_call')}]].

Post-Call Shape Facts (AUTHORITATIVE):
- Post-call shanten after LuckyJ's call and discard: {shanten} ({shanten_meaning}).
- Concealed hand after call/discard: {shape.get('hand_after', '')}.
- Pair-like tiles left after call/discard: {shape.get('pair_like_tiles')}.
- If this says 0/tenpai, describe LuckyJ as already tenpai after the call and discard. Do not call LuckyJ's resulting hand 1-shanten or one-away.

NAGA Call Model Heads:
{call_model_heads_text(case)}

NAGA Post-Call Discard Heads:
{post_call_discard_heads_text(case)}

Remaining Concealed Tile Safety After Call/Discard (lower max danger is safer; do not infer safety from duplicates alone):
{self_hand_tile_threats_text(case, shape.get('hand_after', '').split())}
"""
    else:
        # Threat metrics
        threats_str = ""
        players = case.get("table", {}).get("players", [])
        self_player = next((p for p in players if p.get("seat") == "self"), None)
        if self_player:
            for threat in self_player.get("tile_threats", []):
                t_tile = threat.get("tile")
                if t_tile in [case.get("actual"), case.get("naga")]:
                    bars = threat.get("bars", [])
                    bars_desc = ", ".join(f"{b.get('label')}: {b.get('danger')}" for b in bars)
                    threats_str += f"- Tile [[{t_tile}]] threat levels: {bars_desc}\n"
                    
        prompt += f"""Decisions Comparison:
- LuckyJ Actual Discard: [[{case.get('actual')}]]
- Nishiki Model Top Discard: [[{case.get('naga')}]]

Shape Facts:
{chr(10).join("- " + note for note in case.get('shape_facts', {}).get('notes', []))}

Safety/Threat context:
{threats_str}- Kept tile safety: [[{case.get('kept_tile_safety', {}).get('tile')}]] is {case.get('kept_tile_safety', {}).get('kind')} against {case.get('kept_tile_safety', {}).get('opponents')} opponents.
"""
    return prompt

def process_example(case, guide_en, guide_ja, force):
    key = f"{case['point']}_{case.get('game')}_{case.get('kyoku_index')}_{case.get('position')}"
    
    # Check cache
    if CACHE_PATH.exists() and not force:
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
                if key in cache and cache_entry_is_current(cache[key]) and not cached_guide_conflicts(case, cache[key]):
                    return key, cache[key], True
        except Exception:
            pass
            
    prompt = make_prompt(case, guide_en, guide_ja)
    retries = 3
    for attempt in range(retries):
        try:
            res_json = make_llm_request(prompt)
            # Structure into the cache format
            cache_entry = {
                "guide": {
                    "read": res_json["read_en"],
                    "prompt": res_json["prompt_en"],
                    "answer": res_json["answer_en"]
                },
                "guide_ja": {
                    "read": res_json["read_ja"],
                    "prompt": res_json["prompt_ja"],
                    "answer": res_json["answer_ja"]
                },
                "meta": {
                    "prompt_version": PROMPT_VERSION,
                    "model": MODEL
                }
            }
            return key, cache_entry, False
        except Exception as e:
            if attempt == retries - 1:
                print(f"Error processing {key}: {e}")
                return key, None, False
            continue

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--point", help="Only generate examples for one point key, e.g. point-02")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of examples to generate")
    parser.add_argument("--force", action="store_true", help="Force LLM generation even if cached")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent LLM requests")
    parser.add_argument("--no-rebuild", action="store_true", help="Skip rebuilding site/point-examples.json after generation")
    args = parser.parse_args()
    
    if not API_KEY:
        print("Error: CLIPROXY_API_KEY or ANTHROPIC_API_KEY environment variable is not set.")
        return

    # Load strategy guides
    if not STRATEGY_EN_PATH.exists() or not STRATEGY_JA_PATH.exists():
        print("Error: strategy guides paths are missing.")
        return
        
    with open(STRATEGY_EN_PATH, "r", encoding="utf-8") as f:
        strategy_en = json.load(f)
    with open(STRATEGY_JA_PATH, "r", encoding="utf-8") as f:
        strategy_ja = json.load(f)

    # Load examples
    if not EXAMPLES_PATH.exists():
        print(f"Error: {EXAMPLES_PATH} does not exist.")
        return
        
    with open(EXAMPLES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    all_examples = []
    for point_key, examples in data.items():
        if args.point and point_key != args.point:
            continue
        for example in examples:
            all_examples.append(example)
            
    print(f"Loaded {len(all_examples)} examples.")
    
    # Load cache
    cache = {}
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception as e:
            print(f"Warning: could not load cache: {e}")
            
    # Filter examples to process
    examples_to_process = []
    for example in all_examples:
        key = f"{example['point']}_{example.get('game')}_{example.get('kyoku_index')}_{example.get('position')}"
        if args.force or not cache_entry_is_current(cache.get(key)) or cached_guide_conflicts(example, cache.get(key)):
            examples_to_process.append(example)
            
    print(
        f"Found {len(examples_to_process)} examples to generate "
        f"(current cache entries: {len(all_examples) - len(examples_to_process)})."
    )
    
    if args.limit:
        examples_to_process = examples_to_process[:args.limit]
        print(f"Limited to first {len(examples_to_process)} examples.")
        
    # Process concurrent requests
    new_generations = 0
    if examples_to_process:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    process_example, 
                    case, 
                    strategy_en.get(case["point"], {}), 
                    strategy_ja.get(case["point"], {}), 
                    args.force
                ): case for case in examples_to_process
            }
            for future in as_completed(futures):
                key, result, was_cached = future.result()
                if result:
                    cache[key] = result
                    if not was_cached:
                        new_generations += 1
                        print(f"Generated LLM guide for {key} ({new_generations}/{len(examples_to_process)})")
                        # Write cache incrementally
                        with open(CACHE_PATH, "w", encoding="utf-8") as f:
                            json.dump(cache, f, ensure_ascii=False, indent=2)
                            
    print(f"Finished generation. Total new generated: {new_generations}. Total cached: {len(cache)}.")
    
    if not args.no_rebuild:
        # Run build point examples script to regenerate point-examples.json with merged guides
        print("Running scripts/build_point_examples.py to rebuild examples JSON...")
        res = subprocess.run([".venv/bin/python", "scripts/build_point_examples.py"], capture_output=True, text=True)
        if res.returncode == 0:
            print("Success:")
            print(res.stdout)
        else:
            print("Error rebuilding examples:")
            print(res.stderr)

if __name__ == "__main__":
    main()
