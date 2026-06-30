#!/usr/bin/env python3
import json
import urllib.request
import os
import argparse
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
URL = "http://localhost:8317/v1/chat/completions"
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
4. Pinfu and Chiitoitsu MUST be closed (menzen). When describing multiple potential yaku paths for a hand that has both sequences and pairs, you MUST explicitly list 'toitoi', 'chiitoitsu', and 'closed pinfu' as the potential development paths, but NEVER place the word "open" next to or immediately after "pinfu" or "chiitoitsu" (e.g. do NOT say "keeps pinfu open" or "keeps chiitoitsu open"). Use phrasing like "keeps options like toitoi, chiitoitsu, or closed pinfu available" or "keeps these paths active".
5. Triplet check: A triplet (koutsu) requires 3 identical tiles. A quad (kantsu) requires 4. If the "Visible on Board" count for a tile is 3 (with 1 in your hand and 2 on the table/discards), it is mathematically IMPOSSIBLE to form a triplet of that tile. Do NOT describe such a tile as a "potential triplet" or "potential yaku triplet". If the visible count is 4, it is impossible to even form a pair.

Style Guidelines for English (Alternative 2 style):
- Start with first-person plural: "We are in [Round] [Dealer/Player status], holding [Score] points. [Context about board/opponents, e.g. 'With opponents already showing active melds' or 'With an opponent already declaring riichi']."
- Ask a question about the hand state/threats: e.g. "how do we value our hand shape?" or "how do we balance our hand's value against the danger on the board?"
- Describe LuckyJ's play, mentioning the block being broken or removed: "LuckyJ breaks the [[6m]][[7m]] block by cutting [[6m]]." or "LuckyJ discards the dangerous [[4s]] to preserve the 1-shanten hand shape." Use double brackets [[tile]] format for tiles (e.g., [[6m]]).
- Explain why it is safe or why it is a threat buy, citing safety metrics from the data: "Because [[6m]] is genbutsu to toimen and suji to kamicha/shimocha, this discard offers excellent safety across the board." or "While Nishiki's path avoids immediate risk, it kills the hand's potential..."
- Compare with Nishiki's choice: "Nishiki preserves that block by cutting [[9s]] to maintain a faster, more efficient path to tenpai." or "Nishiki plays defensively, discarding the safe [[9s]] (genbutsu) and breaking the [[8s]][[9s]] block."
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
        "model": "gemini-3.5-flash-low",
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
    
    with urllib.request.urlopen(req, timeout=45) as res:
        response_data = json.loads(res.read().decode("utf-8"))
        content = response_data["choices"][0]["message"]["content"]
        return clean_and_parse_json(content)

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
        visible[tile] += 1
        
    players = case.get("table", {}).get("players", [])
    for p in players:
        for tile in p.get("discards", []):
            visible[tile] += 1
        for meld in p.get("melds", []):
            for tile in meld.get("tiles", []):
                visible[tile] += 1
                
    return visible

def make_prompt(case, guide_en, guide_ja):
    is_call = case.get("kind") == "call"
    prevalent_wind, seat_wind, active_yakuhai, guest_winds = get_winds_and_yakuhai(case)
    is_dealer_self = case.get("table", {}).get("dealer") == "self"
    visible = calculate_visible_tiles(case)
    
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
        count = visible[tile]
        in_hand = hand_list.count(tile)
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

"""

    if is_call:
        prompt += f"""Decisions Comparison:
- LuckyJ Call Action: Called {case.get('call')} on [[{case.get('called_tile')}]] from the {case.get('called_from', '')}, then discarded [[{case.get('discard_after_call')}]].
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
                if key in cache:
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
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of examples to generate")
    parser.add_argument("--force", action="store_true", help="Force LLM generation even if cached")
    args = parser.parse_args()
    
    if not API_KEY:
        print("Error: ANTHROPIC_API_KEY environment variable is not set.")
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
        for example in examples:
            all_examples.append(example)
            
    print(f"Loaded {len(all_examples)} examples across {len(data)} points.")
    
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
        if key not in cache or args.force:
            examples_to_process.append(example)
            
    print(f"Found {len(examples_to_process)} examples to generate (already cached: {len(all_examples) - len(examples_to_process)}).")
    
    if args.limit:
        examples_to_process = examples_to_process[:args.limit]
        print(f"Limited to first {len(examples_to_process)} examples.")
        
    # Process concurrent requests
    new_generations = 0
    if examples_to_process:
        with ThreadPoolExecutor(max_workers=5) as executor:
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
