#!/usr/bin/env python3
"""Convert a tenhou.net/6 game (such as the tensoul output of a Mahjong Soul game) to mjai events.

The Mortal policy (libriichi's Bot) reads mjai. The Tenhou archive already is mjai; Honver's Mahjong Soul games
are tenhou.net/6, so this rebuilds the event stream the same way ``tenhou_replay`` rebuilds a hand: draws, calls,
kans with their replacement draws and dora flips, riichi declarations, and the hand's result.

    .venv/bin/python scripts/tenhou6_to_mjai.py GAME.json OUT.jsonl
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tenhou_replay import TSUMOGIRI, parse_meld, result_blocks  # noqa: E402

HONORS = {41: "E", 42: "S", 43: "W", 44: "N", 45: "P", 46: "F", 47: "C"}


def pai(t: int) -> str:
    if t in (51, 52, 53):
        return "5" + "mps"[t - 51] + "r"
    if t >= 41:
        return HONORS[t]
    return f"{t % 10}{'mps'[t // 10 - 1]}"


def _kyoku(log: list, prefer_chi: list[bool]) -> tuple[list[dict], bool]:
    (kyoku, honba, sticks), scores = log[0], log[1]
    dora, ura, result = list(log[2]), list(log[3]), log[-1]
    dealer = kyoku % 4
    players = [{"hand": list(log[4 + 3 * i]), "draws": log[5 + 3 * i], "discards": log[6 + 3 * i], "di": 0, "ci": 0}
               for i in range(4)]
    events = [{"type": "start_kyoku", "bakaze": "ESWN"[kyoku // 4], "dora_marker": pai(dora[0]), "kyoku": kyoku % 4 + 1,
               "honba": honba, "kyotaku": sticks, "oya": dealer, "scores": list(scores),
               "tehais": [[pai(t) for t in p["hand"]] for p in players]}]
    flipped = 1
    rons = {det[1] for _, det in result_blocks(result) if det[0] != det[1]}
    ambiguous = 0

    def flip():
        nonlocal flipped
        if flipped < len(dora):
            events.append({"type": "dora", "dora_marker": pai(dora[flipped])})
            flipped += 1

    def draw(seat):
        p = players[seat]
        t = p["draws"][p["di"]]
        p["di"] += 1
        p["hand"].append(t)
        events.append({"type": "tsumo", "actor": seat, "pai": pai(t)})
        return t

    cur = dealer
    for _ in range(400):
        p = players[cur]
        if p["di"] >= len(p["draws"]):
            break
        entry = p["draws"][p["di"]]
        drawn = None
        if isinstance(entry, str):
            p["di"] += 1
            meld = parse_meld(entry)
            src = (cur + meld["from_offset"]) % 4
            rest = list(meld["tiles"])
            rest.remove(meld["called"])
            for t in rest:
                p["hand"].remove(t)
            kind = {"c": "chi", "p": "pon", "m": "daiminkan"}[meld["kind"]]
            events.append({"type": kind, "actor": cur, "target": src, "pai": pai(meld["called"]),
                           "consumed": [pai(t) for t in rest]})
            if meld["kind"] == "m":
                if p["ci"] < len(p["discards"]) and p["discards"][p["ci"]] == 0:
                    p["ci"] += 1
                if p["di"] >= len(p["draws"]):
                    break
                drawn = draw(cur)
                flip()
        else:
            drawn = draw(cur)
        ended = False
        riichi = False
        while True:
            if p["ci"] >= len(p["discards"]):
                ended = True  # a tsumo win or an abortive draw ends the hand on this draw
                break
            entry = p["discards"][p["ci"]]
            p["ci"] += 1
            if isinstance(entry, str) and entry.startswith("r"):
                riichi = True
                entry = int(entry[1:])
            if not isinstance(entry, str):
                break
            meld = parse_meld(entry)
            if meld["kind"] == "k":
                p["hand"].remove(meld["called"])
                rest = list(meld["tiles"])
                rest.remove(meld["called"])
                events.append({"type": "kakan", "actor": cur, "pai": pai(meld["called"]), "consumed": [pai(t) for t in rest]})
                if p["di"] >= len(p["draws"]):
                    ended = True
                    break
                drawn = draw(cur)
                flip()
            else:
                for t in meld["tiles"]:
                    p["hand"].remove(t)
                events.append({"type": "ankan", "actor": cur, "consumed": [pai(t) for t in meld["tiles"]]})
                flip()
                if p["di"] >= len(p["draws"]):
                    ended = True
                    break
                drawn = draw(cur)
        if ended:
            break
        tile = drawn if entry == TSUMOGIRI else entry
        p["hand"].remove(tile)
        if riichi:
            events.append({"type": "reach", "actor": cur})
        events.append({"type": "dahai", "actor": cur, "pai": pai(tile), "tsumogiri": entry == TSUMOGIRI})
        last_discard = p["ci"] >= len(p["discards"])
        if riichi and not (last_discard and cur in rons):
            events.append({"type": "reach_accepted", "actor": cur})
        chi_caller = pon_caller = None
        for offset in (1, 2, 3):
            q = players[(cur + offset) % 4]
            if q["di"] < len(q["draws"]) and isinstance(q["draws"][q["di"]], str):
                meld = parse_meld(q["draws"][q["di"]])
                if meld["called"] == tile and ((cur + offset) % 4 + meld["from_offset"]) % 4 == cur:
                    if meld["kind"] == "c":
                        chi_caller = (cur + offset) % 4
                    else:
                        pon_caller = (cur + offset) % 4
        if chi_caller is not None and pon_caller is not None:
            nxt = chi_caller if (ambiguous < len(prefer_chi) and prefer_chi[ambiguous]) else pon_caller
            ambiguous += 1
        else:
            nxt = pon_caller if pon_caller is not None else chi_caller
        cur = nxt if nxt is not None else (cur + 1) % 4
    blocks = result_blocks(result)
    if blocks:
        for deltas, det in blocks:
            events.append({"type": "hora", "actor": det[0], "target": det[1], "deltas": list(deltas),
                           "ura_markers": [pai(t) for t in ura]})
    else:
        deltas = result[1] if len(result) > 1 and isinstance(result[1], list) else [0, 0, 0, 0]
        events.append({"type": "ryukyoku", "deltas": list(deltas)})
    events.append({"type": "end_kyoku"})
    consistent = all(p["di"] >= len(p["draws"]) and p["ci"] >= len(p["discards"]) for p in players)
    return events, consistent


def convert(game: dict, names: list[str] | None = None) -> list[dict]:
    out = [{"type": "start_game", "names": names or game.get("name", ["A", "B", "C", "D"]), "kyoku_first": 0, "aka_flag": True}]
    for log in game["log"]:
        events, ok = _kyoku(log, [])
        if not ok:
            for mask in range(1, 16):
                cand, ok = _kyoku(log, [bool(mask >> k & 1) for k in range(4)])
                if ok:
                    events = cand
                    break
        out += events
    out.append({"type": "end_game"})
    return out


if __name__ == "__main__":
    game = json.load(open(sys.argv[1]))
    with open(sys.argv[2], "w") as f:
        for ev in convert(game):
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
