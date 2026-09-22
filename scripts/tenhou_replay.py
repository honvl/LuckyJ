#!/usr/bin/env python3
"""Replay Tenhou-format JSON hand logs into per-decision records.

Accepts the log format produced by majsoul-to-naga and by Tenhou's own
``https://tenhou.net/5/#json=...`` links, so a self-game can be reviewed with
``scripts/review_self_game.py`` without going through a NAGA report.

The public entry points are :func:`load_logs` and :func:`replay`.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path

from mahjong.shanten import Shanten

_ST = Shanten()

ROUND_NAMES = [
    "East 1", "East 2", "East 3", "East 4",
    "South 1", "South 2", "South 3", "South 4",
    "West 1", "West 2", "West 3", "West 4",
]
SEAT_WINDS = ["East", "South", "West", "North"]
DRAGONS = (45, 46, 47)
TSUMOGIRI = 60

# 34-index order, used to turn a shanten-array index back into a tile code.
TILE_ORDER = [
    11, 12, 13, 14, 15, 16, 17, 18, 19,
    21, 22, 23, 24, 25, 26, 27, 28, 29,
    31, 32, 33, 34, 35, 36, 37, 38, 39,
    41, 42, 43, 44, 45, 46, 47,
]

_NAMES = {}
for _suit, _ch in enumerate("mps", 1):
    for _n in range(1, 10):
        _NAMES[_suit * 10 + _n] = f"{_n}{_ch}"
_NAMES.update({51: "0m", 52: "0p", 53: "0s"})
for _i, _nm in enumerate(["E", "S", "W", "N", "haku", "hatsu", "chun"], 1):
    _NAMES[40 + _i] = _nm

_RED_TO_NORMAL = {51: 15, 52: 25, 53: 35}


def base(code: int) -> int:
    """Red fives collapse onto their normal tile code."""
    return _RED_TO_NORMAL.get(code, code)


def is_red(code: int) -> bool:
    return code in _RED_TO_NORMAL


def name(code: int) -> str:
    return _NAMES[code]


def names(codes) -> str:
    return " ".join(name(c) for c in sorted(codes, key=base))


def tile34(code: int) -> int:
    code = base(code)
    suit, num = divmod(code, 10)
    return (suit - 1) * 9 + (num - 1) if suit <= 3 else 27 + (num - 1)


def counts34(codes) -> list[int]:
    arr = [0] * 34
    for c in codes:
        arr[tile34(c)] += 1
    return arr


def is_honor(code: int) -> bool:
    return base(code) >= 41


def is_terminal(code: int) -> bool:
    code = base(code)
    return code < 41 and code % 10 in (1, 9)


def shanten(concealed, meld_tiles=(), closed=True) -> int:
    """Shanten of a 13-tile hand. Meld tiles are folded in as complete sets."""
    arr = counts34(list(concealed) + list(meld_tiles))
    if closed:
        return _ST.calculate_shanten(arr)
    return _ST.calculate_shanten_for_regular_hand(arr)


def waits(concealed, meld_tiles=(), closed=True) -> list[int]:
    """Tile codes that complete the hand. Empty when the hand is not tenpai."""
    out = []
    for idx, code in enumerate(TILE_ORDER):
        arr = counts34(list(concealed) + list(meld_tiles))
        if arr[idx] >= 4:
            continue
        arr[idx] += 1
        s = _ST.calculate_shanten(arr) if closed else _ST.calculate_shanten_for_regular_hand(arr)
        if s == -1:
            out.append(code)
    return out


_MELD_RE = re.compile(r"^(\d*)([cpmka])(\d+)$")


def parse_meld(token: str) -> dict:
    """Decode a Tenhou meld token such as ``c212223`` or ``34p3434``.

    The letter sits immediately before the called tile, and the called tile's
    position in the sequence says which player it came from.
    """
    m = _MELD_RE.match(token)
    if not m:
        raise ValueError(f"unrecognised meld token: {token!r}")
    pre, letter, post = m.group(1), m.group(2), m.group(3)
    pre_tiles = [int(pre[i:i + 2]) for i in range(0, len(pre), 2)]
    post_tiles = [int(post[i:i + 2]) for i in range(0, len(post), 2)]
    # Tiles before the letter say who fed the call: none is the left player,
    # one is across, and the rest (two for a pon, three for an open kan) is the
    # right player.
    return {
        "kind": letter,
        "called": post_tiles[0],
        "tiles": pre_tiles + post_tiles,
        "from_offset": 3 - min(len(pre_tiles), 2),
    }


def load_logs(source) -> list[list]:
    """Load hand logs from a path, a URL, or raw text holding either.

    Accepts a ``.json`` file containing a list of logs or a full Tenhou game
    object, a text file of ``tenhou.net/5/#json=`` links (one per line), or the
    link text itself.
    """
    if isinstance(source, (str, Path)) and Path(source).exists():
        text = Path(source).read_text(encoding="utf-8")
    else:
        text = str(source)

    text = text.strip()
    logs: list[list] = []

    if text.startswith("[") or text.startswith("{"):
        data = json.loads(text)
        if isinstance(data, dict):
            return list(data["log"])
        if data and isinstance(data[0], dict):
            for game in data:
                logs.extend(game["log"])
            return logs
        return list(data)

    for line in text.splitlines():
        line = line.strip()
        if not line or "json=" not in line:
            continue
        payload = urllib.parse.unquote(line.split("json=", 1)[1])
        logs.extend(json.loads(payload)["log"])
    if not logs:
        raise ValueError("no Tenhou logs found in input")
    return logs


def replay(log: list) -> dict:
    """Rebuild one hand, returning an event per discard.

    Each event records the acting seat, the tile released, the hand and melds
    left afterwards, and every player's river and threat state at that moment,
    which is what the review script needs to price the decision.

    When a discard matches both the next seat's pending chi token and another
    seat's pending pon or kan token, one of the two belongs to a later copy of
    the same tile. The pon is tried first; if the hand then fails to reconcile,
    the other reading is used.
    """
    ambiguous: list[int] = []
    game = _replay(log, [], ambiguous)
    if _consistent(game) or not ambiguous:
        return game
    n = len(ambiguous)
    for mask in range(1, 2 ** n):
        choices = [bool(mask >> k & 1) for k in range(n)]
        seen: list[int] = []
        try:
            candidate = _replay(log, choices, seen)
        except ValueError:
            continue
        if _consistent(candidate):
            return candidate
    return game


def _consistent(game: dict) -> bool:
    return all(p["ci"] == len(p["discards"]) and p["di"] >= len(p["draws"]) - 1 and len(p["hand"]) <= 13
               for p in game["players"])


def _replay(log: list, prefer_chi: list[bool], ambiguous: list[int]) -> dict:
    kyoku, honba, sticks = log[0]
    dealer = kyoku % 4
    players = []
    for i in range(4):
        players.append({
            "seat": i,
            "hand": list(log[4 + 3 * i]),
            "haipai": list(log[4 + 3 * i]),
            "draws": log[5 + 3 * i],
            "discards": log[6 + 3 * i],
            "di": 0, "ci": 0,
            "river": [], "melds": [], "meld_tiles": [],
            "riichi_event": None,
        })

    events: list[dict] = []
    cur = dealer
    turn = [0, 0, 0, 0]

    for _ in range(400):
        p = players[cur]
        if p["di"] >= len(p["draws"]) or p["ci"] >= len(p["discards"]):
            break

        drawn = None
        called = None
        while True:
            entry = p["draws"][p["di"]]
            p["di"] += 1
            if isinstance(entry, str):
                meld = parse_meld(entry)
                src = (cur + meld["from_offset"]) % 4
                rest = list(meld["tiles"])
                rest.remove(meld["called"])
                for t in rest:
                    if t in p["hand"]:
                        p["hand"].remove(t)
                p["melds"].append({**meld, "src": src})
                p["meld_tiles"].extend(meld["tiles"][:3])
                called = {"kind": meld["kind"], "tile": meld["called"], "src": src}
                if meld["kind"] == "m":
                    # daiminkan: the discard stream holds a 0 placeholder for the
                    # turn with no discard, then a replacement tile is drawn
                    if p["ci"] < len(p["discards"]) and p["discards"][p["ci"]] == 0:
                        p["ci"] += 1
                    continue
                break
            drawn = entry
            p["hand"].append(entry)
            break

        turn[cur] += 1
        riichi = False
        ended = False
        while True:
            if p["ci"] >= len(p["discards"]):
                # a kan was the last action: rinshan win or abortive end
                ended = True
                break
            entry = p["discards"][p["ci"]]
            p["ci"] += 1
            if isinstance(entry, str) and entry.startswith("r"):
                riichi = True
                entry = int(entry[1:])
            if not isinstance(entry, str):
                break
            # ankan or kakan declared from hand, then a replacement draw
            meld = parse_meld(entry)
            if meld["kind"] == "k":  # added kan upgrades an existing pon
                p["hand"].remove(meld["called"])
                for m in p["melds"]:
                    if m["kind"] == "p" and base(m["called"]) == base(meld["called"]):
                        m["kind"] = "k"
                        m["tiles"] = meld["tiles"]
                        break
            else:  # closed kan takes all four from hand
                for t in meld["tiles"]:
                    if t in p["hand"]:
                        p["hand"].remove(t)
                p["melds"].append({**meld, "src": cur})
                p["meld_tiles"].extend(meld["tiles"][:3])
            if p["ci"] >= len(p["discards"]):
                # the replacement draw ends the hand; keep the hand at 13 like any tsumo win
                ended = True
                break
            drawn = p["draws"][p["di"]]
            p["di"] += 1
            p["hand"].append(drawn)
        if ended:
            break

        tile = drawn if entry == TSUMOGIRI else entry
        p["hand"].remove(tile)
        closed = not p["melds"]
        events.append({
            "index": len(events),
            "turn": turn[cur],
            "seat": cur,
            "drawn": drawn,
            "called": called,
            "tile": tile,
            "tsumogiri": entry == TSUMOGIRI,
            "riichi": riichi,
            "hand_before": sorted(p["hand"] + [tile], key=base),
            "hand_after": sorted(p["hand"], key=base),
            "meld_tiles": list(p["meld_tiles"]),
            "melds": [list(m["tiles"]) for m in p["melds"]],
            "closed": closed,
            "rivers": {q["seat"]: list(q["river"]) for q in players},
            "riichi_seats": {q["seat"]: q["riichi_event"] for q in players},
            "meld_counts": {q["seat"]: len(q["melds"]) for q in players},
        })
        p["river"].append(tile)
        if riichi:
            p["riichi_event"] = len(events) - 1

        # who takes the discard: at most one seat can really call it now; a
        # second matching token belongs to a later copy of the same tile
        chi_caller = pon_caller = None
        for offset in (1, 2, 3):
            q = players[(cur + offset) % 4]
            if q["di"] < len(q["draws"]) and isinstance(q["draws"][q["di"]], str):
                meld = parse_meld(q["draws"][q["di"]])
                if meld["called"] == tile and (q["seat"] + meld["from_offset"]) % 4 == cur:
                    if meld["kind"] == "c":
                        chi_caller = q["seat"]
                    else:
                        pon_caller = q["seat"]
        if chi_caller is not None and pon_caller is not None:
            k = len(ambiguous)
            ambiguous.append(len(events))
            nxt = chi_caller if (k < len(prefer_chi) and prefer_chi[k]) else pon_caller
        else:
            nxt = pon_caller if pon_caller is not None else chi_caller
        cur = nxt if nxt is not None else (cur + 1) % 4

    return {
        "kyoku": kyoku,
        "honba": honba,
        "sticks": sticks,
        "round_name": f"{ROUND_NAMES[kyoku]}-{honba}",
        "dealer": dealer,
        "start_scores": list(log[1]),
        "dora_indicators": list(log[2]),
        "ura_indicators": list(log[3]),
        "result": log[-1],
        "events": events,
        "players": players,
    }


def result_blocks(result: list) -> list[tuple[list, list]]:
    """``(deltas, detail)`` pairs. A double ron produces more than one."""
    out = []
    i = 1
    while i + 1 < len(result):
        deltas, detail = result[i], result[i + 1]
        if isinstance(deltas, list) and len(deltas) == 4 and isinstance(detail, list):
            out.append((deltas, detail))
        i += 2
    return out


def result_deltas(result: list) -> list[int]:
    """Point movement for the hand, summed across every winner."""
    total = [0, 0, 0, 0]
    blocks = result_blocks(result)
    if blocks:
        for deltas, _ in blocks:
            for i in range(4):
                total[i] += deltas[i]
    elif len(result) > 1 and isinstance(result[1], list):
        for i in range(4):
            total[i] += result[1][i]
    return total


def riichi_sticks_paid(log: list) -> list[int]:
    """Riichi sticks each seat actually paid in this hand.

    The result deltas carry the sticks a winner collects but not the 1000 a
    declarer puts down, so reconciling scores needs this. A riichi whose
    declaration tile is ronned is not established and costs nothing.
    """
    paid = [0, 0, 0, 0]
    ronned_declarers = set()
    for _, detail in result_blocks(log[-1]):
        winner, source = detail[0], detail[1]
        if winner != source:
            discards = log[6 + 3 * source]
            if discards and isinstance(discards[-1], str) and discards[-1].startswith("r"):
                ronned_declarers.add(source)
    for seat in range(4):
        declared = any(isinstance(d, str) and d.startswith("r") for d in log[6 + 3 * seat])
        if declared and seat not in ronned_declarers:
            paid[seat] = 1
    return paid


def seat_wind(seat: int, kyoku: int) -> int:
    """Tile code of a seat's own wind in this round."""
    return 41 + ((seat - (kyoku % 4)) % 4)


def round_wind(kyoku: int) -> int:
    return 41 + (kyoku // 4)


def yakuhai_for(seat: int, kyoku: int) -> set[int]:
    return set(DRAGONS) | {seat_wind(seat, kyoku), round_wind(kyoku)}
