#!/usr/bin/env python3
"""Why are my wins slow? Speed and efficiency review of your own games.

Replays every hand of the games listed in ``data/self_games/majsoul/index.json``
(the manifest ``fetch_majsoul_games.py`` writes) and measures, for you and for
the three opponents in the same games, how fast hands reach tenpai, how much
acceptance each discard throws away, how riichi and calls are timed, and what
happens between tenpai and the end of the hand. Opponents at the same table are
the baseline: same rooms, same rules, same day.

    .venv/bin/python scripts/review_win_speed.py                  # all games in the manifest
    .venv/bin/python scripts/review_win_speed.py --since 2026-01-01 --json analysis/win-speed.json
    .venv/bin/python scripts/review_win_speed.py --log data/self_games/2026-09-07-hanchan.json --hero 0

Definitions:

- turn: the seat's own discard count, so "tenpai on turn 6" means tenpai after
  the sixth discard. A win is scored on the turn of the next draw: discards + 1.
- acceptance (ukeire): unseen copies of every tile type that lowers the
  13-tile hand's shanten. Shanten and acceptance are compared with the best
  discard available from the same 14 tiles, so the loss is what the choice
  cost, not what the deal cost.
- efficiency is only scored on pre-tenpai discards made before any opponent has
  declared riichi, so folding is never counted as inefficiency.

Every number is descriptive. Small cells are printed with their ``n``.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mahjong.constants import EAST  # noqa: E402
from mahjong.hand_calculating.hand import HandCalculator  # noqa: E402
from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules  # noqa: E402
from mahjong.tile import TilesConverter  # noqa: E402

from tenhou_replay import (  # noqa: E402
    TILE_ORDER, _ST, base, counts34, is_honor, is_red, is_terminal, load_logs, names, replay,
    result_blocks, round_wind, seat_wind, waits, yakuhai_for,
)

_CALC = HandCalculator()
_RULES = OptionalRules(has_open_tanyao=True, has_aka_dora=True)


def ron_has_yaku(hand13, win_tile, seat, kyoku) -> bool:
    """Would a ron on ``win_tile`` score a yaku without riichi? Closed hands only."""
    parts = {"man": "", "pin": "", "sou": "", "honors": ""}
    for t in list(hand13) + [win_tile]:
        b = base(t)
        if b >= 41:
            parts["honors"] += str(b - 40)
        else:
            parts[{1: "man", 2: "pin", 3: "sou"}[b // 10]] += str(b % 10)
    tiles = TilesConverter.string_to_136_array(**parts)
    idx = TILE_ORDER.index(base(win_tile))
    win = next(t for t in tiles if t // 4 == idx)
    cfg = HandConfig(is_tsumo=False, is_riichi=False, options=_RULES,
                     player_wind=EAST + seat_wind(seat, kyoku) - 41,
                     round_wind=EAST + round_wind(kyoku) - 41)
    return _CALC.estimate_hand_value(tiles, win, config=cfg).error is None


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "self_games" / "majsoul" / "index.json"
REFERENCE = ROOT / "data" / "self_games" / "majsoul" / "amae-koromo-window.json"
WAIT_SHAPES = sorted((ROOT / "analysis").glob("riichi-wait-shapes-*.json"))
RX_RIICHI = ROOT / "analysis" / "rx3-riichi-2026-07-05.json"

ABORTIVE = {"九種九牌", "四風連打", "四家立直", "三家和了", "四槓散了", "流し満貫"}
HAN_RE = re.compile(r"(\d+)飜")
LIMIT_HAN = {"満貫": 5, "跳満": 6, "倍満": 8, "三倍満": 11, "役満": 13}
# Tenhou yaku ids (NAGA conversions write "yaku<id>(<han>飜)") and names (tensoul)
DORA_IDS, RIICHI_IDS = {"52", "53", "54"}, {"1", "2", "21"}
TENHOU_YAKU = {
    0: "門前清自摸和", 1: "立直", 2: "一発", 3: "槍槓", 4: "嶺上開花", 5: "海底摸月", 6: "河底撈魚", 7: "平和",
    8: "断幺九", 9: "一盃口", 10: "役牌:自風牌", 11: "役牌:自風牌", 12: "役牌:自風牌", 13: "役牌:自風牌",
    14: "役牌:場風牌", 15: "役牌:場風牌", 16: "役牌:場風牌", 17: "役牌:場風牌", 18: "役牌 白", 19: "役牌 發",
    20: "役牌 中", 21: "ダブル立直", 22: "七対子", 23: "混全帯幺九", 24: "一気通貫", 25: "三色同順", 26: "三色同刻",
    27: "三槓子", 28: "対々和", 29: "三暗刻", 30: "小三元", 31: "混老頭", 32: "二盃口", 33: "純全帯幺九",
    34: "混一色", 35: "清一色", 52: "ドラ", 53: "裏ドラ", 54: "赤ドラ",
}


def yaku_names(detail: list) -> list[str]:
    """Yaku in a win, with NAGA's numeric ids mapped to Tenhou's names; zero-han dora dropped."""
    out = []
    for entry in detail[4:]:
        name = entry.split("(")[0].strip()
        if name.startswith("yaku") and name[4:].isdigit():
            name = TENHOU_YAKU.get(int(name[4:]), name)
        m = HAN_RE.search(entry)
        if m and int(m.group(1)) == 0 and "ドラ" in name:
            continue
        out.append(name)
    return out


def han_breakdown(detail: list) -> dict:
    """Total han of a win split into dora, riichi-family and shape yaku."""
    out = {"dora": 0, "riichi": 0, "yaku": 0}
    for entry in detail[4:]:
        m = HAN_RE.search(entry)
        if not m:
            if "役満" in entry:
                out["yaku"] += 13
            continue
        han = int(m.group(1))
        name = entry.split("(")[0].strip()
        ident = name[4:] if name.startswith("yaku") else None
        if "ドラ" in name or ident in DORA_IDS:
            out["dora"] += han
        elif name in ("立直", "一発", "ダブル立直") or ident in RIICHI_IDS:
            out["riichi"] += han
        else:
            out["yaku"] += han
    total = sum(out.values())
    if not total:
        head = detail[3] if len(detail) > 3 else ""
        m = HAN_RE.search(head)
        total = int(m.group(1)) if m else next((v for k, v in LIMIT_HAN.items() if k in head), 0)
        out["yaku"] = total
    out["total"] = total
    return out


# --------------------------------------------------------------- shanten

@lru_cache(maxsize=None)
def _shanten_arr(arr: tuple[int, ...], closed: bool) -> int:
    if closed:
        return _ST.calculate_shanten(list(arr))
    return _ST.calculate_shanten_for_regular_hand(list(arr))


def hand_shanten(tiles, meld_tiles=(), closed=True) -> int:
    return _shanten_arr(tuple(counts34(list(tiles) + list(meld_tiles))), closed)


def acceptance(hand13, meld_tiles, closed, visible: Counter) -> tuple[int, int, list[int]]:
    """(shanten, unseen accepting copies, accepting tile codes) for a 13-tile hand."""
    arr = counts34(list(hand13) + list(meld_tiles))
    s = _shanten_arr(tuple(arr), closed)
    total, kinds = 0, []
    for idx, code in enumerate(TILE_ORDER):
        if arr[idx] >= 4:
            continue
        arr[idx] += 1
        better = _shanten_arr(tuple(arr), closed) < s
        arr[idx] -= 1
        if better:
            left = 4 - visible.get(code, 0)
            if left > 0:
                total += left
                kinds.append(code)
    return s, total, kinds


def dora_from_indicator(code: int) -> int:
    b = base(code)
    if b < 41:
        return b - 8 if b % 10 == 9 else b + 1
    if b <= 44:
        return 41 + (b - 41 + 1) % 4
    return 45 + (b - 45 + 1) % 3


def is_yaochuu(code: int) -> bool:
    return is_honor(code) or is_terminal(code)


def deal_shape(haipai, yakuhai: set[int], dora: set[int]) -> dict:
    """Shape of the 13-tile deal, as far as tanyao is concerned."""
    counts = Counter(base(t) for t in haipai)
    iso = conn = 0
    for suit in (10, 20, 30):
        for num, nb in ((1, (2, 3)), (9, (7, 8))):
            t = suit + num
            if counts[t]:
                if counts[t] >= 2 or any(counts[suit + k] for k in nb):
                    conn += counts[t]
                else:
                    iso += counts[t]
    return {
        "honor_pairs": sum(1 for t in range(41, 48) if counts[t] >= 2),
        "lone_value": sum(1 for t in yakuhai if counts[t] == 1),
        "iso_terminals": iso, "conn_terminals": conn,
        "dora": sum(1 for t in haipai if base(t) in dora or is_red(t)),
        "shanten": hand_shanten(haipai),
    }


def hand_features(hand13, yakuhai: set[int], dora: set[int]) -> dict:
    """What a 13-tile hand keeps that a pure acceptance count ignores."""
    counts = Counter(base(t) for t in hand13)
    return {
        "dora": sum(1 for t in hand13 if base(t) in dora or is_red(t)),
        "value_honors": frozenset(t for t in yakuhai if counts[t]),
        "guest_winds": frozenset(t for t in (41, 42, 43, 44) if t not in yakuhai and counts[t]),
        "yaochuu": sum(n for t, n in counts.items() if is_yaochuu(t)),
    }


def preserves(cand: dict, actual: dict) -> bool:
    """True when the candidate keeps everything the actual discard kept."""
    return (cand["dora"] >= actual["dora"]
            and cand["value_honors"] >= actual["value_honors"]
            and cand["guest_winds"] >= actual["guest_winds"]
            and cand["yaochuu"] <= actual["yaochuu"])


def best_discard(hand14, meld_tiles, closed, visible: Counter, yakuhai=frozenset(), dora=frozenset()) -> dict:
    """Best shanten reachable from 14 tiles and the widest acceptance at that shanten.

    ``features`` per candidate lets the caller measure the loss against only the
    alternatives that preserve the same dora, honors and tanyao potential.
    """
    # `visible` already counts all 14 tiles, so every candidate discard is
    # public in the count and nothing is added per candidate.
    out, feats = {}, {}
    for tile in {base(t): t for t in hand14}.values():
        rest = list(hand14)
        rest.remove(tile)
        out[base(tile)] = acceptance(rest, meld_tiles, closed, visible)
        feats[base(tile)] = hand_features(rest, yakuhai, dora)
    best_s = min(v[0] for v in out.values())
    best_u = max(v[1] for v in out.values() if v[0] == best_s)
    return {"shanten": best_s, "ukeire": best_u, "by_tile": out, "features": feats}


def aware_loss(best: dict, actual_tile: int) -> tuple[int, int]:
    """(shanten loss, acceptance loss) against alternatives that preserve what the cut kept."""
    a_s, a_u, _ = best["by_tile"][actual_tile]
    a_f = best["features"][actual_tile]
    adm = [t for t, f in best["features"].items() if preserves(f, a_f)]
    s_adm = min(best["by_tile"][t][0] for t in adm)
    if a_s > s_adm:
        return a_s - s_adm, 0
    u_adm = max(best["by_tile"][t][1] for t in adm if best["by_tile"][t][0] == s_adm)
    return 0, max(0, u_adm - a_u)


def tile_class(code: int, yakuhai: set[int]) -> str:
    if is_honor(code):
        return "value honor" if base(code) in yakuhai else "guest wind"
    return "terminal" if is_terminal(code) else "simple"


# ---------------------------------------------------------------- replay

def meld_snapshots(game: dict, upto: int) -> dict[int, list[list[int]]]:
    """Each seat's meld tiles as they stood at event ``upto``, from that seat's latest event.

    ``hand_records`` keeps the same state (``melds_now``) as it walks the events.
    """
    snap = {s: [] for s in range(4)}
    for ev in game["events"][: upto + 1]:
        snap[ev["seat"]] = ev["melds"]
    return snap


def visible_counter(hand, rivers, melds_now, indicators, players) -> Counter:
    """Copies of each tile the seat can see: ``hand``, every river and meld, the indicators.

    ``melds_now`` holds each seat's meld tiles at that moment. A called tile sits in
    the discarder's river and in the caller's meld, so it is counted once;
    ``players`` is the replay's player list, whose melds come in call order and
    name the called tile.
    """
    c = Counter()
    for t in hand:
        c[base(t)] += 1
    for river in rivers.values():
        for t in river:
            c[base(t)] += 1
    for seat, melds in melds_now.items():
        for meld in melds:
            for t in meld:
                c[base(t)] += 1
        for meld in players[seat]["melds"][: len(melds)]:
            if meld["kind"] != "a":  # a closed kan never passed through a river
                c[base(meld["called"])] -= 1
    for t in indicators:
        c[base(t)] += 1
    return c


def hand_records(log: list, score_efficiency: set[int]) -> list[dict]:
    """One record per seat for this hand."""
    g = replay(log)
    result = g["result"]
    kind = result[0]
    events = g["events"]
    indicators = g["dora_indicators"][:1]

    winners, dealt_in, win_value, win_han, win_turn = set(), None, {}, {}, {}
    for deltas, detail in result_blocks(result):
        who, frm = detail[0], detail[1]
        winners.add(who)
        if who != frm:
            dealt_in = frm
        win_value[who] = deltas[who]
        win_han[who] = han_breakdown(detail)
        win_han[who]["names"] = yaku_names(detail)

    recs = []
    for seat in range(4):
        p = g["players"][seat]
        recs.append({
            "seat": seat, "dealer": seat == g["dealer"], "round": g["round_name"],
            "haipai_shanten": hand_shanten(p["haipai"]),
            "shanten_by_turn": [], "tenpai_turn": None, "first_1sh_turn": None,
            "riichi_turn": None, "riichi_live": None, "riichi_kinds": None,
            "riichi_at_first_tenpai": None,
            "first_call_turn": None, "open": bool(p["melds"]),
            "won": seat in winners, "tsumo": None, "win_turn": None,
            "win_value": win_value.get(seat),
            "win_han": win_han[seat]["total"] if seat in win_han else None,
            "win_han_parts": win_han.get(seat),
            "dealt_in": seat == dealt_in, "deal_in_turn": None,
            "result_kind": kind, "draw_tenpai": None,
            "turns": 0, "turns_in_tenpai": 0, "turns_in_1sh": 0,
            "eff_events": 0, "eff_shanten_loss": 0, "eff_ukeire_loss": 0, "eff_ukeire_lost_total": 0,
            "eff_closed_events": 0, "eff_closed_ukeire_lost_total": 0, "eff_closed_ukeire_loss": 0,
            "eff_examples": [], "tenpai_live": None, "tenpai_kinds": None,
            "eff_by_turn": Counter(), "eff_lost_by_turn": Counter(), "eff_kept": Counter(),
            "lone_honors": [], "first_closed_tenpai": None, "first_call": None, "no_win_reason": None,
            "aware_closed_ukeire_lost_total": 0, "aware_closed_ukeire_loss": 0, "aware_closed_shanten_loss": 0,
            "aware_lost_by_turn": Counter(), "eff_explained": Counter(),
            "haipai_yaochuu": None, "haipai_dora": None, "yakuhai_pair_at_deal": None,
            "clean_turn": None, "honors_gone_turn": None, "terminals_gone_turn": None, "won_tanyao": False,
            "deal_shape": None, "deal_in_into": None,
            "tenpai_after_riichi": None,
            "final_shanten": None,
        })

    melds_now = {s: [] for s in range(4)}
    lone = {s: {} for s in range(4)}  # seat -> yakuhai tile -> first turn seen as a single
    yakuhai = {s: yakuhai_for(s, g["kyoku"]) for s in range(4)}
    dora_set = frozenset(dora_from_indicator(t) for t in indicators)
    for s in range(4):
        haipai = g["players"][s]["haipai"]
        counts = Counter(base(t) for t in haipai)
        for t in yakuhai[s]:
            if counts[t] == 1:
                lone[s][t] = 0
        recs[s]["haipai_yaochuu"] = sum(n for t, n in counts.items() if is_yaochuu(t))
        recs[s]["haipai_dora"] = sum(1 for t in haipai if base(t) in dora_set or is_red(t))
        recs[s]["yakuhai_pair_at_deal"] = any(counts[t] >= 2 for t in yakuhai[s])
        recs[s]["deal_shape"] = deal_shape(haipai, yakuhai[s], dora_set)
        recs[s]["won_tanyao"] = s in win_han and "断幺九" in win_han[s]["names"]
    for i, e in enumerate(events):
        seat = e["seat"]
        r = recs[seat]
        melds_now[seat] = e["melds"]
        r["turns"] = e["turn"]

        s_after = hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"])
        r["shanten_by_turn"].append(s_after)
        s_before = r["shanten_by_turn"][-2] if len(r["shanten_by_turn"]) > 1 else None

        threats = [q for q, v in e["riichi_seats"].items() if v is not None and q != seat]

        if e["called"] and r["first_call_turn"] is None:
            r["first_call_turn"] = e["turn"]
            call_kind = e["called"]["kind"]
            r["first_call"] = {
                "turn": e["turn"], "kind": call_kind,
                "yakuhai": call_kind == "p" and base(e["called"]["tile"]) in yakuhai[seat],
                "shanten_before": s_before, "shanten_after": s_after,
                "threat": bool(threats),
            }

        # tanyao shape: when the hand (with its melds) last holds an honor, a terminal, either
        all_tiles = list(e["hand_after"]) + list(e["meld_tiles"])
        if r["honors_gone_turn"] is None and not any(is_honor(t) for t in all_tiles):
            r["honors_gone_turn"] = e["turn"]
        if r["terminals_gone_turn"] is None and not any(is_terminal(t) for t in all_tiles):
            r["terminals_gone_turn"] = e["turn"]
        if r["clean_turn"] is None and not any(is_yaochuu(t) for t in all_tiles):
            r["clean_turn"] = e["turn"]

        # lone value honors: when a single copy leaves the hand, and whether it paired first
        counts = Counter(base(t) for t in e["hand_after"])
        for t in yakuhai[seat]:
            if t in lone[seat]:
                if counts[t] == 0:
                    r["lone_honors"].append({"tile": t, "first": lone[seat][t], "cut": e["turn"],
                                             "outcome": "cut", "threat": bool(threats)})
                    del lone[seat][t]
                elif counts[t] >= 2:
                    r["lone_honors"].append({"tile": t, "first": lone[seat][t], "cut": e["turn"],
                                             "outcome": "paired", "threat": bool(threats)})
                    del lone[seat][t]
            elif counts[t] == 1 and not any(base(x) == t for x in e["meld_tiles"]):
                lone[seat][t] = e["turn"]
        if s_after == 0 and r["tenpai_turn"] is None:
            r["tenpai_turn"] = e["turn"]
            r["tenpai_after_riichi"] = bool(threats)
        if s_after == 1 and r["first_1sh_turn"] is None:
            r["first_1sh_turn"] = e["turn"]
        if s_before == 0:
            r["turns_in_tenpai"] += 1
        if s_before == 1:
            r["turns_in_1sh"] += 1

        # everything the seat can see: its 14 tiles, every river and meld, the indicator
        vis = visible_counter(e["hand_before"], e["rivers"], melds_now, indicators, g["players"])
        if s_after == 0 and r["tenpai_turn"] == e["turn"] and r["tenpai_live"] is None:
            _, live, kinds = acceptance(e["hand_after"], e["meld_tiles"], e["closed"], vis)
            r["tenpai_live"], r["tenpai_kinds"] = live, len(kinds)
        if s_after == 0 and e["closed"] and r["first_closed_tenpai"] is None:
            _, live, kinds = acceptance(e["hand_after"], e["meld_tiles"], e["closed"], vis)
            winning = waits(e["hand_after"])
            yakuless = not any(ron_has_yaku(e["hand_after"], w, seat, g["kyoku"]) for w in winning)
            r["first_closed_tenpai"] = {"turn": e["turn"], "declared": e["riichi"], "live": live,
                                        "kinds": len(kinds), "threat": bool(threats), "yakuless": yakuless}
        if e["riichi"]:
            r["riichi_turn"] = e["turn"]
            r["riichi_at_first_tenpai"] = r["tenpai_turn"] == e["turn"]
            _, live, kinds = acceptance(e["hand_after"], e["meld_tiles"], e["closed"], vis)
            r["riichi_live"], r["riichi_kinds"] = live, len(kinds)

        # efficiency: pre-tenpai, no live riichi against us, not locked by our own riichi
        locked = e["riichi_seats"][seat] is not None and e["riichi_seats"][seat] < i
        if (seat in score_efficiency and not threats and not locked
                and (s_before is None or s_before > 0)):
            best = best_discard(e["hand_before"], e["meld_tiles"], e["closed"], vis, yakuhai[seat], dora_set)
            actual = best["by_tile"][base(e["tile"])]
            r["eff_events"] += 1
            sh_loss = actual[0] - best["shanten"]
            uk_loss = (best["ukeire"] - actual[1]) if sh_loss == 0 else 0
            aw_sh, aw_uk = aware_loss(best, base(e["tile"]))
            if sh_loss > 0:
                r["eff_shanten_loss"] += 1
            if uk_loss > 0:
                r["eff_ukeire_loss"] += 1
                r["eff_ukeire_lost_total"] += uk_loss
            if e["closed"]:
                r["eff_closed_events"] += 1
                r["eff_closed_ukeire_lost_total"] += uk_loss
                r["eff_closed_ukeire_loss"] += uk_loss > 0
                bucket = "1-3" if e["turn"] <= 3 else "4-6" if e["turn"] <= 6 else "7-9" if e["turn"] <= 9 else "10+"
                r["eff_by_turn"][bucket] += 1
                r["eff_lost_by_turn"][bucket] += uk_loss
                r["aware_closed_ukeire_lost_total"] += aw_uk
                r["aware_closed_ukeire_loss"] += aw_uk > 0
                r["aware_closed_shanten_loss"] += aw_sh > 0
                r["aware_lost_by_turn"][bucket] += aw_uk
                if uk_loss > 0:
                    r["eff_explained"]["explained" if aw_uk == 0 and aw_sh == 0 else "unexplained"] += uk_loss
                if uk_loss > 0:
                    # what the widest discard would have cut, versus what was cut
                    widest = [t for t, v in best["by_tile"].items()
                              if v[0] == best["shanten"] and v[1] == best["ukeire"]]
                    yk = yakuhai_for(seat, g["kyoku"])
                    r["eff_kept"][(tile_class(widest[0], yk), tile_class(e["tile"], yk))] += 1
            # open hands are skipped here: the metric is yaku-blind and most
            # flagged open-hand discards are avoiding a yakuless tenpai
            if e["closed"] and (sh_loss > 0 or uk_loss >= 4):
                better = [t for t, v in best["by_tile"].items()
                          if v[0] == best["shanten"] and v[1] == best["ukeire"]]
                r["eff_examples"].append({
                    "round": g["round_name"], "turn": e["turn"],
                    "hand": names(e["hand_before"]), "melds": [names(m) for m in e["melds"]],
                    "discard": names([e["tile"]]), "shanten_after": actual[0], "ukeire_after": actual[1],
                    "best_discard": names(better[:3]), "best_shanten": best["shanten"],
                    "best_ukeire": best["ukeire"], "shanten_loss": sh_loss, "ukeire_loss": uk_loss,
                })

    blocks = result_blocks(result)
    for seat in range(4):
        r = recs[seat]
        p = g["players"][seat]
        n_disc = sum(1 for e in events if e["seat"] == seat)
        for t, first in lone[seat].items():
            r["lone_honors"].append({"tile": t, "first": first, "cut": None, "outcome": "held", "threat": None})
        if r["tenpai_turn"] is not None and seat not in winners:
            if kind != "和了":
                r["no_win_reason"] = "draw"
            elif seat == dealt_in:
                r["no_win_reason"] = "dealt in"
            elif any(d[0] == d[1] for _, d in blocks):
                r["no_win_reason"] = "opponent tsumo"
            else:
                r["no_win_reason"] = "opponent ron elsewhere"
        if r["won"]:
            r["win_turn"] = n_disc + 1
            blocks = result_blocks(result)
            r["tsumo"] = any(d[0] == seat and d[1] == seat for _, d in blocks)
        if r["dealt_in"]:
            r["deal_in_turn"] = n_disc
            winner = next(d[0] for _, d in blocks if d[1] == seat)
            wp = g["players"][winner]
            r["deal_in_into"] = ("riichi" if wp["riichi_event"] is not None
                                 else "open hand" if wp["melds"] else "dama")
        if kind == "流局":
            r["draw_tenpai"] = hand_shanten(p["hand"], p["meld_tiles"], not p["melds"]) == 0
        r["final_shanten"] = hand_shanten(p["hand"], p["meld_tiles"], not p["melds"]) if len(p["hand"]) == 13 else None
        # tenpai order: who was tenpai first this hand
    tenpai_turns = {s: recs[s]["tenpai_turn"] for s in range(4) if recs[s]["tenpai_turn"] is not None}
    # absolute order uses the event index of the tenpai discard
    first_tenpai_idx = {}
    for i, e in enumerate(events):
        s = e["seat"]
        if recs[s]["tenpai_turn"] == e["turn"] and s not in first_tenpai_idx:
            first_tenpai_idx[s] = i
    for seat in range(4):
        r = recs[seat]
        if seat in first_tenpai_idx:
            r["tenpai_first"] = all(first_tenpai_idx[seat] <= v for v in first_tenpai_idx.values())
            r["opponents_tenpai_before"] = sum(1 for s, v in first_tenpai_idx.items() if s != seat and v < first_tenpai_idx[seat])
        else:
            r["tenpai_first"] = None
            r["opponents_tenpai_before"] = None
    return recs


# ------------------------------------------------------------- aggregate

def pct(num, den, nd=1):
    return None if not den else round(100 * num / den, nd)


def mean(xs, nd=2):
    xs = [x for x in xs if x is not None]
    return None if not xs else round(statistics.mean(xs), nd)


def median(xs):
    xs = [x for x in xs if x is not None]
    return None if not xs else statistics.median(xs)


def summarize(recs: list[dict]) -> dict:
    n = len(recs)
    won = [r for r in recs if r["won"]]
    tenpai = [r for r in recs if r["tenpai_turn"] is not None]
    riichi = [r for r in recs if r["riichi_turn"] is not None]
    opened = [r for r in recs if r["open"]]
    closed_hands = [r for r in recs if not r["open"]]
    draws = [r for r in recs if r["result_kind"] == "流局"]
    eff_events = sum(r["eff_events"] for r in recs)
    closed_tenpai_no_riichi = [r for r in tenpai if not r["open"] and r["riichi_turn"] is None]

    def by_waits(rs):
        out = {}
        for label, lo, hi in (("<=3", 0, 3), ("4-7", 4, 7), ("8+", 8, 99)):
            cell = [r for r in rs if r["riichi_live"] is not None and lo <= r["riichi_live"] <= hi]
            out[label] = {"n": len(cell), "win_rate_pct": pct(sum(r["won"] for r in cell), len(cell)),
                          "deal_in_rate_pct": pct(sum(r["dealt_in"] for r in cell), len(cell))}
        return out

    def tenpai_type(r):
        if r["riichi_turn"] is not None:
            return "riichi"
        return "open" if r["open"] else "dama"

    conversion = {}
    for kind in ("riichi", "dama", "open"):
        cell = [r for r in tenpai if tenpai_type(r) == kind]
        conversion[kind] = {
            "n": len(cell), "share_of_tenpai_pct": pct(len(cell), len(tenpai)),
            "win_rate_pct": pct(sum(r["won"] for r in cell), len(cell)),
            "deal_in_rate_pct": pct(sum(r["dealt_in"] for r in cell), len(cell)),
            "avg_live_waits_at_tenpai": mean([r["tenpai_live"] for r in cell]),
            "narrow_wait_pct": pct(sum(1 for r in cell if r["tenpai_live"] is not None and r["tenpai_live"] <= 3), len(cell)),
            "avg_tenpai_turn": mean([r["tenpai_turn"] for r in cell]),
            "avg_win_value": mean([r["win_value"] for r in cell if r["won"]], 0),
        }
    eff_closed = sum(r["eff_closed_events"] for r in recs)

    honors = [h for r in recs for h in r["lone_honors"] if h["first"] <= 2]
    cut = [h for h in honors if h["outcome"] == "cut"]
    early_honors = {
        "n": len(honors),
        "median_cut_turn": median([h["cut"] for h in cut]),
        "cut_by_turn_3_pct": pct(sum(1 for h in cut if h["cut"] <= 3), len(honors)),
        "cut_by_turn_6_pct": pct(sum(1 for h in cut if h["cut"] <= 6), len(honors)),
        "paired_pct": pct(sum(1 for h in honors if h["outcome"] == "paired"), len(honors)),
        "held_to_end_pct": pct(sum(1 for h in honors if h["outcome"] == "held"), len(honors)),
        "cut_under_threat_pct": pct(sum(1 for h in cut if h["threat"]), len(cut)),
    }

    fct = [r["first_closed_tenpai"] for r in recs if r["first_closed_tenpai"]]
    riichi_decision = {}
    for label, lo, hi in (("<=3", 0, 3), ("4-7", 4, 7), ("8+", 8, 99)):
        for threat in (False, True):
            cell = [(d, r) for r in recs for d in [r["first_closed_tenpai"]]
                    if d and lo <= d["live"] <= hi and d["threat"] == threat]
            declared = [r for d, r in cell if d["declared"]]
            declined = [r for d, r in cell if not d["declared"]]
            riichi_decision[f"{label}{' threat' if threat else ''}"] = {
                "n": len(cell), "declared_pct": pct(len(declared), len(cell)),
                "win_declared_pct": pct(sum(r["won"] for r in declared), len(declared)),
                "win_declined_pct": pct(sum(r["won"] for r in declined), len(declined)),
                "deal_in_declared_pct": pct(sum(r["dealt_in"] for r in declared), len(declared)),
                "deal_in_declined_pct": pct(sum(r["dealt_in"] for r in declined), len(declined)),
            }
    late_riichi = [r for r in recs if r["riichi_turn"] is not None and r["first_closed_tenpai"]
                   and r["riichi_turn"] > r["first_closed_tenpai"]["turn"]]
    declined = [r for r in recs if r["first_closed_tenpai"] and not r["first_closed_tenpai"]["declared"]]
    declined_yakuless = [r for r in declined if r["first_closed_tenpai"]["yakuless"]]
    stayed_dama = [r for r in declined if r["riichi_turn"] is None]
    dama_decision = {
        "declined_n": len(declined),
        "declined_yakuless_pct": pct(len(declined_yakuless), len(declined)),
        "declined_yakuless_win_pct": pct(sum(r["won"] for r in declined_yakuless), len(declined_yakuless)),
        "declined_yakuless_tsumo_pct": pct(sum(1 for r in declined_yakuless if r["won"] and r["tsumo"]), len(declined_yakuless)),
        "declined_with_yaku_win_pct": pct(sum(r["won"] for r in declined if not r["first_closed_tenpai"]["yakuless"]),
                                          len(declined) - len(declined_yakuless)),
        "stayed_dama_pct": pct(len(stayed_dama), len(declined)),
        "declined_avg_turn": mean([r["first_closed_tenpai"]["turn"] for r in declined]),
        "declined_late_pct": pct(sum(1 for r in declined if r["first_closed_tenpai"]["turn"] >= 12), len(declined)),
    }

    calls = [r["first_call"] for r in recs if r["first_call"]]
    first_call = {
        "n": len(calls),
        "yakuhai_pon_pct": pct(sum(1 for c in calls if c["yakuhai"]), len(calls)),
        "chi_pct": pct(sum(1 for c in calls if c["kind"] == "c"), len(calls)),
        "from_3plus_shanten_pct": pct(sum(1 for c in calls if (c["shanten_before"] or 0) >= 3), len(calls)),
        "from_2_shanten_pct": pct(sum(1 for c in calls if c["shanten_before"] == 2), len(calls)),
        "reaches_1sh_or_tenpai_pct": pct(sum(1 for c in calls if c["shanten_after"] <= 1), len(calls)),
        "avg_turn": mean([c["turn"] for c in calls]),
        "under_threat_pct": pct(sum(1 for c in calls if c["threat"]), len(calls)),
    }
    open_win_by_call_shanten = {}
    for label, lo, hi in (("0-1", 0, 1), ("2", 2, 2), ("3+", 3, 9)):
        cell = [r for r in recs if r["first_call"] and lo <= (r["first_call"]["shanten_before"] or 0) <= hi]
        open_win_by_call_shanten[label] = {"n": len(cell), "win_rate_pct": pct(sum(r["won"] for r in cell), len(cell)),
                                          "avg_win_value": mean([r["win_value"] for r in cell if r["won"]], 0)}

    reasons = Counter(r["no_win_reason"] for r in tenpai if not r["won"])
    no_win = {k: {"n": v, "share_pct": pct(v, len(tenpai))} for k, v in reasons.items()}
    by_turn, lost_by_turn, kept, aware_by_turn, explained = Counter(), Counter(), Counter(), Counter(), Counter()
    for r in recs:
        by_turn.update(r["eff_by_turn"])
        lost_by_turn.update(r["eff_lost_by_turn"])
        aware_by_turn.update(r["aware_lost_by_turn"])
        kept.update(r["eff_kept"])
        explained.update(r["eff_explained"])
    eff_turn = {b: {"n": by_turn[b],
                    "lost_per_100": None if not by_turn[b] else round(100 * lost_by_turn[b] / by_turn[b], 1),
                    "aware_lost_per_100": None if not by_turn[b] else round(100 * aware_by_turn[b] / by_turn[b], 1)}
                for b in ("1-3", "4-6", "7-9", "10+")}
    aware = {
        "ukeire_lost_per_100": None if not eff_closed else round(
            100 * sum(r["aware_closed_ukeire_lost_total"] for r in recs) / eff_closed, 1),
        "narrower_pct": pct(sum(r["aware_closed_ukeire_loss"] for r in recs), eff_closed),
        "shanten_loss_pct": pct(sum(r["aware_closed_shanten_loss"] for r in recs), eff_closed),
        "explained_share_pct": pct(explained["explained"], explained["explained"] + explained["unexplained"]),
    }

    def yaochuu_bucket(k):
        return "0-2" if k <= 2 else "3-4" if k <= 4 else "5-6" if k <= 6 else "7+"

    tanyao_by_deal = {}
    for b in ("0-2", "3-4", "5-6", "7+"):
        cell = [r for r in recs if r["haipai_yaochuu"] is not None and yaochuu_bucket(r["haipai_yaochuu"]) == b]
        tanyao_by_deal[b] = {
            "n": len(cell), "share_pct": pct(len(cell), n),
            "tanyao_win_pct": pct(sum(r["won_tanyao"] for r in cell), len(cell)),
            "win_rate_pct": pct(sum(r["won"] for r in cell), len(cell)),
            "clean_pct": pct(sum(1 for r in cell if r["clean_turn"] is not None), len(cell)),
            "clean_by_6_pct": pct(sum(1 for r in cell if r["clean_turn"] is not None and r["clean_turn"] <= 6), len(cell)),
            "avg_win_value": mean([r["win_value"] for r in cell if r["won"]], 0),
        }
    b34 = [r for r in recs if r["haipai_yaochuu"] is not None and 3 <= r["haipai_yaochuu"] <= 4]

    def shape_cell(sel):
        c = [r for r in b34 if sel(r["deal_shape"])]
        return {"n": len(c), "share_pct": pct(len(c), len(b34)),
                "clean_by_6_pct": pct(sum(1 for r in c if r["clean_turn"] is not None and r["clean_turn"] <= 6), len(c)),
                "tanyao_win_pct": pct(sum(r["won_tanyao"] for r in c), len(c)),
                "win_rate_pct": pct(sum(r["won"] for r in c), len(c))}
    ready = lambda d: d["honor_pairs"] == 0 and d["conn_terminals"] == 0  # noqa: E731
    deal_shapes = {
        "all 3-4 yaochuu deals": shape_cell(lambda d: True),
        "has an honor pair": shape_cell(lambda d: d["honor_pairs"] >= 1),
        "lone honors, some 12/89 terminal": shape_cell(lambda d: d["honor_pairs"] == 0 and d["conn_terminals"] >= 1),
        "lone honors, isolated terminals": shape_cell(ready),
        "  with a lone value honor": shape_cell(lambda d: ready(d) and d["lone_value"] >= 1),
        "  with no value honor": shape_cell(lambda d: ready(d) and d["lone_value"] == 0),
        "  and shanten 3 or better": shape_cell(lambda d: ready(d) and d["shanten"] <= 3),
        "  and dora 0": shape_cell(lambda d: ready(d) and d["dora"] == 0),
        "  and dora 2+": shape_cell(lambda d: ready(d) and d["dora"] >= 2),
    }
    deal_ins = Counter(r["deal_in_into"] for r in recs if r["dealt_in"])
    deal_in_into = {k: {"n": deal_ins[k], "per_100_hands": pct(deal_ins[k], n)} for k in ("riichi", "open hand", "dama")}

    tanyao_wins = [r for r in won if r["won_tanyao"]]
    cleaned = [r for r in recs if r["clean_turn"] is not None]
    pair_cell = [r for r in recs if r["haipai_yaochuu"] is not None and r["haipai_yaochuu"] <= 4 and r["yakuhai_pair_at_deal"]]
    tanyao = {
        "wins_n": len(tanyao_wins), "share_of_wins_pct": pct(len(tanyao_wins), len(won)),
        "open_pct": pct(sum(r["open"] for r in tanyao_wins), len(tanyao_wins)),
        "avg_dora_han": mean([r["win_han_parts"]["dora"] for r in tanyao_wins]),
        "avg_han": mean([r["win_han"] for r in tanyao_wins]),
        "avg_value": mean([r["win_value"] for r in tanyao_wins], 0),
        "avg_win_turn": mean([r["win_turn"] for r in tanyao_wins]),
        "first_call_chi_pct": pct(sum(1 for r in tanyao_wins if r["first_call"] and r["first_call"]["kind"] == "c"),
                                  sum(1 for r in tanyao_wins if r["first_call"])),
        "avg_haipai_yaochuu_of_tanyao_wins": mean([r["haipai_yaochuu"] for r in tanyao_wins]),
        "avg_haipai_dora_of_tanyao_wins": mean([r["haipai_dora"] for r in tanyao_wins]),
        "cleaned_pct": pct(len(cleaned), n),
        "clean_avg_turn": mean([r["clean_turn"] for r in cleaned]),
        "honors_gone_avg_turn": mean([r["honors_gone_turn"] for r in cleaned]),
        "terminals_gone_avg_turn": mean([r["terminals_gone_turn"] for r in cleaned]),
        "cleaned_win_rate_pct": pct(sum(r["won"] for r in cleaned), len(cleaned)),
        "cleaned_tanyao_win_pct": pct(sum(r["won_tanyao"] for r in cleaned), len(cleaned)),
        "pair_cell_n": len(pair_cell),
        "pair_cell_tanyao_win_pct": pct(sum(r["won_tanyao"] for r in pair_cell), len(pair_cell)),
        "pair_cell_yakuhai_win_pct": pct(sum(1 for r in pair_cell if r["won"] and any("役牌" in y for y in r["win_han_parts"]["names"])), len(pair_cell)),
        "pair_cell_win_rate_pct": pct(sum(r["won"] for r in pair_cell), len(pair_cell)),
        "by_deal": tanyao_by_deal,
        "deal_shapes": deal_shapes,
    }
    kept_total = sum(kept.values())
    eff_kept = {f"kept {w}, cut {a}": {"n": c, "share_pct": pct(c, kept_total)}
                for (w, a), c in kept.most_common() if w != a}

    return {
        "hands": n,
        "tenpai_conversion": conversion,
        "eff_closed_events": eff_closed,
        "eff_closed_by_turn": eff_turn,
        "eff_closed_kept": eff_kept,
        "eff_aware": aware,
        "tanyao": tanyao,
        "deal_in_into": deal_in_into,
        "early_lone_honors": early_honors,
        "riichi_decision": riichi_decision,
        "riichi_after_first_tenpai_n": len(late_riichi),
        "dama_decision": dama_decision,
        "first_call": first_call,
        "open_win_by_call_shanten": open_win_by_call_shanten,
        "tenpai_no_win": no_win,
        "eff_closed_ukeire_loss_pct": pct(sum(r["eff_closed_ukeire_loss"] for r in recs), eff_closed),
        "eff_closed_ukeire_lost_per_100": None if not eff_closed else round(
            100 * sum(r["eff_closed_ukeire_lost_total"] for r in recs) / eff_closed, 1),
        "win_rate_pct": pct(len(won), n),
        "tsumo_share_pct": pct(sum(1 for r in won if r["tsumo"]), len(won)),
        "deal_in_rate_pct": pct(sum(r["dealt_in"] for r in recs), n),
        "avg_win_turn": mean([r["win_turn"] for r in won]),
        "avg_win_value": mean([r["win_value"] for r in won], 0),
        "avg_win_han": mean([r["win_han"] for r in won]),
        "avg_win_han_dora": mean([r["win_han_parts"]["dora"] for r in won]),
        "avg_win_han_riichi": mean([r["win_han_parts"]["riichi"] for r in won]),
        "avg_win_han_yaku": mean([r["win_han_parts"]["yaku"] for r in won]),
        "wins_with_no_dora_pct": pct(sum(1 for r in won if r["win_han_parts"]["dora"] == 0), len(won)),
        "mangan_plus_share_pct": pct(sum(1 for r in won if (r["win_han"] or 0) >= 5), len(won)),
        "one_han_share_pct": pct(sum(1 for r in won if r["win_han"] == 1), len(won)),
        "yaku_share_pct": {name: pct(cnt, len(won)) for name, cnt in Counter(
            y for r in won for y in set(r["win_han_parts"]["names"])).most_common()},
        "draw_rate_pct": pct(len(draws), n),
        "draw_tenpai_rate_pct": pct(sum(1 for r in draws if r["draw_tenpai"]), len(draws)),
        "haipai_shanten": mean([r["haipai_shanten"] for r in recs]),
        "tenpai_rate_pct": pct(len(tenpai), n),
        "tenpai_by_turn_6_pct": pct(sum(1 for r in tenpai if r["tenpai_turn"] <= 6), n),
        "tenpai_by_turn_9_pct": pct(sum(1 for r in tenpai if r["tenpai_turn"] <= 9), n),
        "tenpai_by_turn_12_pct": pct(sum(1 for r in tenpai if r["tenpai_turn"] <= 12), n),
        "avg_tenpai_turn": mean([r["tenpai_turn"] for r in tenpai]),
        "median_tenpai_turn": median([r["tenpai_turn"] for r in tenpai]),
        "avg_first_1sh_turn": mean([r["first_1sh_turn"] for r in recs]),
        "avg_turns_in_1sh_before_tenpai": mean([r["tenpai_turn"] - r["first_1sh_turn"] for r in tenpai
                                              if r["first_1sh_turn"] is not None and r["first_1sh_turn"] <= r["tenpai_turn"]]),
        "avg_turns_stuck_1sh_no_tenpai": mean([r["turns_in_1sh"] for r in recs if r["tenpai_turn"] is None]),
        "win_rate_given_tenpai_pct": pct(sum(r["won"] for r in tenpai), len(tenpai)),
        "avg_turns_in_tenpai": mean([r["turns_in_tenpai"] for r in tenpai]),
        "tenpai_first_rate_pct": pct(sum(1 for r in tenpai if r["tenpai_first"]), len(tenpai)),
        "tenpai_after_opp_riichi_pct": pct(sum(1 for r in tenpai if r["tenpai_after_riichi"]), len(tenpai)),
        "win_rate_tenpai_first_pct": pct(sum(r["won"] for r in tenpai if r["tenpai_first"]),
                                         sum(1 for r in tenpai if r["tenpai_first"])),
        "win_rate_tenpai_second_pct": pct(sum(r["won"] for r in tenpai if r["tenpai_first"] is False),
                                          sum(1 for r in tenpai if r["tenpai_first"] is False)),
        "riichi_rate_pct": pct(len(riichi), n),
        "avg_riichi_turn": mean([r["riichi_turn"] for r in riichi]),
        "riichi_at_first_tenpai_pct": pct(sum(1 for r in riichi if r["riichi_at_first_tenpai"]), len(riichi)),
        "riichi_win_rate_pct": pct(sum(r["won"] for r in riichi), len(riichi)),
        "riichi_deal_in_rate_pct": pct(sum(r["dealt_in"] for r in riichi), len(riichi)),
        "avg_riichi_live_waits": mean([r["riichi_live"] for r in riichi]),
        "riichi_by_waits": by_waits(riichi),
        "closed_tenpai_dama_pct": pct(len(closed_tenpai_no_riichi), len([r for r in tenpai if not r["open"]])),
        "dama_win_rate_pct": pct(sum(r["won"] for r in closed_tenpai_no_riichi), len(closed_tenpai_no_riichi)),
        "open_rate_pct": pct(len(opened), n),
        "avg_first_call_turn": mean([r["first_call_turn"] for r in opened]),
        "open_tenpai_rate_pct": pct(sum(1 for r in opened if r["tenpai_turn"] is not None), len(opened)),
        "open_avg_tenpai_turn": mean([r["tenpai_turn"] for r in opened if r["tenpai_turn"] is not None]),
        "closed_avg_tenpai_turn": mean([r["tenpai_turn"] for r in closed_hands if r["tenpai_turn"] is not None]),
        "open_win_rate_pct": pct(sum(r["won"] for r in opened), len(opened)),
        "closed_win_rate_pct": pct(sum(r["won"] for r in closed_hands), len(closed_hands)),
        "open_avg_win_value": mean([r["win_value"] for r in opened if r["won"]], 0),
        "closed_avg_win_value": mean([r["win_value"] for r in closed_hands if r["won"]], 0),
        "open_deal_in_rate_pct": pct(sum(r["dealt_in"] for r in opened), len(opened)),
        "eff_events": eff_events,
        "eff_shanten_loss_pct": pct(sum(r["eff_shanten_loss"] for r in recs), eff_events),
        "eff_ukeire_loss_pct": pct(sum(r["eff_ukeire_loss"] for r in recs), eff_events),
        "eff_ukeire_lost_per_100": None if not eff_events else round(
            100 * sum(r["eff_ukeire_lost_total"] for r in recs) / eff_events, 1),
    }


# ----------------------------------------------------------------- report

def load_reference() -> dict:
    if REFERENCE.exists():
        return json.loads(REFERENCE.read_text(encoding="utf-8"))
    return {}


def luckyj_riichi_reference() -> dict:
    """Riichi win rate by wait category from the wait-shape miner, weighted overall."""
    out = {}
    if WAIT_SHAPES:
        data = json.loads(WAIT_SHAPES[-1].read_text(encoding="utf-8"))
        cats = data.get("all_seats", {}).get("by_wait_category", {})
        n = sum(v["n"] for v in cats.values())
        if n:
            out["riichi_win_rate_pct"] = round(sum(v["n"] * v["win_rate_pct"] for v in cats.values()) / n, 1)
            out["riichi_deal_in_rate_pct"] = round(sum(v["n"] * v["deal_in_rate_pct"] for v in cats.values()) / n, 1)
            out["riichi_n"] = n
    if RX_RIICHI.exists():
        data = json.loads(RX_RIICHI.read_text(encoding="utf-8"))
        cell = data.get("child_dealer_baselines", {}).get("child", {}).get("riichi_first_opportunity", {})
        out["declare_by_waits_child"] = {k: v.get("declare_rate_pct") for k, v in cell.get("by_unseen_waits", {}).items()}
    return out


def fmt(v, suffix=""):
    return "-" if v is None else f"{v}{suffix}"


def print_report(hero: dict, opp: dict, ref: dict, lj: dict, games: int, hero_name: str, examples: list[dict],
                 opp_label: str = "opponents", opp_desc: str = "hands at the same tables"):
    w = 34
    print("=" * 78)
    print(f"WIN-SPEED REVIEW   {hero_name}   {games} games   {hero['hands']} hands   "
          f"({opp_label}: {opp['hands']} {opp_desc})")
    print("=" * 78)

    def row(label, key, suffix="", refkey=None):
        r = ""
        if refkey and refkey in ref:
            r = f"{ref[refkey]}{suffix}"
        print(f"  {label:<{w}}{fmt(hero.get(key), suffix):>9}{fmt(opp.get(key), suffix):>11}{r:>12}")

    print(f"  {'':<{w}}{'you':>9}{opp_label:>11}{'amae-koromo':>12}")
    print("Outcomes")
    row("win rate", "win_rate_pct", "%", "win_rate_pct")
    row("  tsumo share of wins", "tsumo_share_pct", "%", "tsumo_share_pct")
    row("deal-in rate", "deal_in_rate_pct", "%", "deal_in_rate_pct")
    row("average win turn", "avg_win_turn", "", "avg_win_turn")
    row("average win value", "avg_win_value", "", "avg_win_value")
    row("average han per win", "avg_win_han")
    row("  of which dora (incl. red, ura)", "avg_win_han_dora")
    row("  of which riichi/ippatsu", "avg_win_han_riichi")
    row("  of which other yaku", "avg_win_han_yaku")
    row("wins with no dora at all", "wins_with_no_dora_pct", "%")
    row("one-han wins", "one_han_share_pct", "%")
    row("mangan+ share of wins", "mangan_plus_share_pct", "%")
    if hero.get("deal_in_into"):
        for k in ("riichi", "open hand", "dama"):
            h = hero["deal_in_into"][k]; o = (opp.get("deal_in_into") or {}).get(k, {})
            print(f"  {'  dealt into ' + k + ' (per 100 hands)':<{w}}{fmt(h['per_100_hands']):>9}{fmt(o.get('per_100_hands')):>11}")
    row("exhaustive draws", "draw_rate_pct", "%", "draw_rate_pct")
    row("  tenpai at draw", "draw_tenpai_rate_pct", "%", "draw_tenpai_rate_pct")

    if hero.get("yaku_share_pct"):
        print(f"  {'yaku, share of wins (3%+ for either)':<{w}}{'you':>9}{opp_label:>11}")
        oy = opp.get("yaku_share_pct") or {}
        for name in sorted(set(hero["yaku_share_pct"]) | set(oy), key=lambda k: -(oy.get(k) or 0)):
            a, b = hero["yaku_share_pct"].get(name, 0.0), oy.get(name, 0.0)
            if max(a or 0, b or 0) >= 3:
                print(f"    {name:<{w - 2}}{fmt(a, '%'):>9}{fmt(b, '%'):>11}")

    print("\nSpeed to tenpai")
    row("starting shanten (13 tiles)", "haipai_shanten")
    row("reached tenpai", "tenpai_rate_pct", "%")
    row("  by turn 6", "tenpai_by_turn_6_pct", "%")
    row("  by turn 9", "tenpai_by_turn_9_pct", "%")
    row("  by turn 12", "tenpai_by_turn_12_pct", "%")
    row("average tenpai turn", "avg_tenpai_turn")
    row("median tenpai turn", "median_tenpai_turn")
    row("first 1-shanten turn", "avg_first_1sh_turn")
    row("turns from 1-shanten to tenpai", "avg_turns_in_1sh_before_tenpai")
    row("turns stuck at 1-shanten (no tenpai)", "avg_turns_stuck_1sh_no_tenpai")

    print("\nDiscard efficiency (pre-tenpai, no riichi on the table; yaku-blind)")
    row("discards scored", "eff_events")
    row("lost shanten vs best discard", "eff_shanten_loss_pct", "%")
    row("narrower than best (same shanten)", "eff_ukeire_loss_pct", "%")
    row("acceptance lost per 100 discards", "eff_ukeire_lost_per_100")
    row("  closed hands only: discards", "eff_closed_events")
    row("  closed hands: narrower than best", "eff_closed_ukeire_loss_pct", "%")
    row("  closed hands: acceptance lost /100", "eff_closed_ukeire_lost_per_100")
    if hero.get("eff_aware"):
        ha, oa = hero["eff_aware"], opp.get("eff_aware") or {}
        print("  value-aware (against alternatives keeping the same dora, honors, tanyao potential):")
        for label, key, suffix in (("acceptance lost /100, nothing kept for it", "ukeire_lost_per_100", ""),
                                   ("narrower with nothing kept for it", "narrower_pct", "%"),
                                   ("lost shanten with nothing kept for it", "shanten_loss_pct", "%"),
                                   ("blind loss explained by dora/honors/tanyao", "explained_share_pct", "%")):
            print(f"    {label:<{w - 2}}{fmt(ha.get(key), suffix):>9}{fmt(oa.get(key), suffix):>11}")
    if hero.get("eff_closed_events"):
        print(f"  {'closed hands, lost /100 by turn (blind / aware)':<{w}}{'you':>9}{opp_label:>11}")
        for b in ("1-3", "4-6", "7-9", "10+"):
            h = hero["eff_closed_by_turn"][b]
            o = opp["eff_closed_by_turn"].get(b, {}) if opp.get("eff_closed_by_turn") else {}
            print(f"    turns {b:<{w - 10}}{fmt(h['lost_per_100']) + ' / ' + fmt(h.get('aware_lost_per_100')):>15}"
                  f"{fmt(o.get('lost_per_100')) + ' / ' + fmt(o.get('aware_lost_per_100')):>16}   (n {h['n']}/{o.get('n', '-')})")
        print(f"  {'when narrower, what was kept':<{w}}{'you':>9}{opp_label:>11}")
        keys = list(hero["eff_closed_kept"].keys())[:6]
        for k in keys:
            h = hero["eff_closed_kept"][k]
            o = (opp.get("eff_closed_kept") or {}).get(k, {})
            print(f"    {k:<{w - 2}}{fmt(h['share_pct'], '%'):>9}{fmt(o.get('share_pct'), '%'):>11}")

    print("\nAfter tenpai")
    row("win rate once tenpai", "win_rate_given_tenpai_pct", "%")
    print(f"  {'tenpai hands by type':<{w}}{'n':>5}{'share':>7}{'win':>7}{'deal-in':>9}{'waits':>7}{'<=3':>6}{'value':>7}")
    for kind in ("riichi", "dama", "open"):
        for who, summ in (("you", hero), (opp_label[:3], opp)):
            c = summ["tenpai_conversion"][kind]
            label = f"  {kind} ({who})"
            print(f"  {label:<{w}}{c['n']:>5}{fmt(c['share_of_tenpai_pct'], '%'):>7}{fmt(c['win_rate_pct'], '%'):>7}"
                  f"{fmt(c['deal_in_rate_pct'], '%'):>9}{fmt(c['avg_live_waits_at_tenpai']):>7}{fmt(c['narrow_wait_pct'], '%'):>6}"
                  f"{fmt(c['avg_win_value']):>7}")
    row("turns spent in tenpai", "avg_turns_in_tenpai")
    row("tenpai before every opponent", "tenpai_first_rate_pct", "%")
    row("  win rate when first", "win_rate_tenpai_first_pct", "%")
    row("  win rate when not first", "win_rate_tenpai_second_pct", "%")
    row("tenpai only after an opp riichi", "tenpai_after_opp_riichi_pct", "%")

    print("\nRiichi")
    row("riichi rate", "riichi_rate_pct", "%", "riichi_rate_pct")
    row("average riichi turn", "avg_riichi_turn")
    row("declared at first tenpai", "riichi_at_first_tenpai_pct", "%")
    row("won after riichi", "riichi_win_rate_pct", "%")
    row("dealt in after riichi", "riichi_deal_in_rate_pct", "%")
    row("live winning tiles at riichi", "avg_riichi_live_waits")
    row("closed tenpai kept dama", "closed_tenpai_dama_pct", "%")
    row("  dama win rate", "dama_win_rate_pct", "%")
    if lj:
        print(f"  LuckyJ riichi win {lj.get('riichi_win_rate_pct')}%, deal-in {lj.get('riichi_deal_in_rate_pct')}% "
              f"over {lj.get('riichi_n')} riichi (all seats)")
    print(f"  {'riichi by live waits':<{w}}{'n':>5}{'win':>8}{'deal-in':>9}   {opp_label} n/win/deal-in")
    for k in ("<=3", "4-7", "8+"):
        h, o = hero["riichi_by_waits"][k], opp["riichi_by_waits"][k]
        print(f"    {k:<{w - 2}}{h['n']:>5}{fmt(h['win_rate_pct'], '%'):>8}{fmt(h['deal_in_rate_pct'], '%'):>9}"
              f"   {o['n']}/{fmt(o['win_rate_pct'], '%')}/{fmt(o['deal_in_rate_pct'], '%')}")

    print("\nCalls")
    row("opened the hand", "open_rate_pct", "%", "call_rate_pct")
    row("first call turn", "avg_first_call_turn")
    row("open hands reaching tenpai", "open_tenpai_rate_pct", "%")
    row("tenpai turn, open hands", "open_avg_tenpai_turn")
    row("tenpai turn, closed hands", "closed_avg_tenpai_turn")
    row("win rate, open hands", "open_win_rate_pct", "%")
    row("win rate, closed hands", "closed_win_rate_pct", "%")
    row("win value, open hands", "open_avg_win_value")
    row("win value, closed hands", "closed_avg_win_value")
    row("deal-in rate, open hands", "open_deal_in_rate_pct", "%")

    print("\nTanyao")
    th, to = hero["tanyao"], opp.get("tanyao") or {}
    for label, key, suffix in (("tanyao wins", "wins_n", ""), ("  share of wins", "share_of_wins_pct", "%"),
                               ("  open", "open_pct", "%"), ("  first call was chi", "first_call_chi_pct", "%"),
                               ("  han / dora han / value", "han", ""),
                               ("  terminals+honors at the deal", "avg_haipai_yaochuu_of_tanyao_wins", ""),
                               ("  dora+red at the deal", "avg_haipai_dora_of_tanyao_wins", ""),
                               ("hands that became all-simples", "cleaned_pct", "%"),
                               ("  turn last honor left", "honors_gone_avg_turn", ""),
                               ("  turn last terminal left", "terminals_gone_avg_turn", ""),
                               ("  turn fully clean", "clean_avg_turn", ""),
                               ("  win rate / tanyao win rate", "cleanwin", ""),
                               ("<=4 yaochuu at deal with a yakuhai pair", "pair_cell_n", ""),
                               ("  won with tanyao / with yakuhai", "pairwin", "")):
        if key == "han":
            hv = f"{fmt(th.get('avg_han'))}/{fmt(th.get('avg_dora_han'))}/{fmt(th.get('avg_value'))}"
            ov = f"{fmt(to.get('avg_han'))}/{fmt(to.get('avg_dora_han'))}/{fmt(to.get('avg_value'))}"
        elif key == "cleanwin":
            hv = f"{fmt(th.get('cleaned_win_rate_pct'), '%')}/{fmt(th.get('cleaned_tanyao_win_pct'), '%')}"
            ov = f"{fmt(to.get('cleaned_win_rate_pct'), '%')}/{fmt(to.get('cleaned_tanyao_win_pct'), '%')}"
        elif key == "pairwin":
            hv = f"{fmt(th.get('pair_cell_tanyao_win_pct'), '%')}/{fmt(th.get('pair_cell_yakuhai_win_pct'), '%')}"
            ov = f"{fmt(to.get('pair_cell_tanyao_win_pct'), '%')}/{fmt(to.get('pair_cell_yakuhai_win_pct'), '%')}"
        else:
            hv, ov = fmt(th.get(key), suffix), fmt(to.get(key), suffix)
        print(f"  {label:<{w}}{hv:>14}{ov:>16}")
    print(f"  {'by terminals+honors at the deal':<{w}}{'share':>7}{'tanyao':>8}{'win':>7}{'clean':>7}{'by T6':>7}   {opp_label} share/tanyao/win/clean/by T6")
    for b in ("0-2", "3-4", "5-6", "7+"):
        h = th["by_deal"][b]; o = (to.get("by_deal") or {}).get(b, {})
        print(f"    {b:<{w - 2}}{fmt(h['share_pct'], '%'):>7}{fmt(h['tanyao_win_pct'], '%'):>8}{fmt(h['win_rate_pct'], '%'):>7}"
              f"{fmt(h['clean_pct'], '%'):>7}{fmt(h['clean_by_6_pct'], '%'):>7}   "
              f"{fmt(o.get('share_pct'), '%')}/{fmt(o.get('tanyao_win_pct'), '%')}/{fmt(o.get('win_rate_pct'), '%')}/{fmt(o.get('clean_pct'), '%')}/{fmt(o.get('clean_by_6_pct'), '%')}")

    if th.get("deal_shapes"):
        print(f"  {'3-4 yaochuu deals by shape':<{w}}{'share':>7}{'by T6':>7}{'tanyao':>8}{'win':>7}   {opp_label} share/by T6/tanyao/win")
        for k, h in th["deal_shapes"].items():
            o = (to.get("deal_shapes") or {}).get(k, {})
            print(f"    {k:<{w - 2}}{fmt(h['share_pct'], '%'):>7}{fmt(h['clean_by_6_pct'], '%'):>7}{fmt(h['tanyao_win_pct'], '%'):>8}{fmt(h['win_rate_pct'], '%'):>7}"
                  f"   {fmt(o.get('share_pct'), '%')}/{fmt(o.get('clean_by_6_pct'), '%')}/{fmt(o.get('tanyao_win_pct'), '%')}/{fmt(o.get('win_rate_pct'), '%')}  (n {h['n']}/{o.get('n', '-')})")

    print("\nLone value honors held from the deal (single copy at turn 0-2)")
    eh, eo = hero["early_lone_honors"], opp["early_lone_honors"]
    for label, key, suffix in (("instances", "n", ""), ("median cut turn", "median_cut_turn", ""),
                               ("cut by turn 3", "cut_by_turn_3_pct", "%"), ("cut by turn 6", "cut_by_turn_6_pct", "%"),
                               ("paired or ponned before cut", "paired_pct", "%"),
                               ("still in hand at the end", "held_to_end_pct", "%"),
                               ("cut with a riichi already out", "cut_under_threat_pct", "%")):
        print(f"  {label:<{w}}{fmt(eh.get(key), suffix):>9}{fmt(eo.get(key), suffix):>11}")

    print("\nRiichi or dama at the first closed tenpai (by live waits; win/deal-in of each choice)")
    print(f"  {'':<{w}}{'n':>5}{'riichi':>8}{'win r':>7}{'win d':>7}{'in r':>7}{'in d':>7}")
    for k in ("<=3", "<=3 threat", "4-7", "4-7 threat", "8+", "8+ threat"):
        for who, summ in (("you", hero), (opp_label[:3], opp)):
            c = summ["riichi_decision"][k]
            if not c["n"]:
                continue
            print(f"  {k + ' (' + who + ')':<{w}}{c['n']:>5}{fmt(c['declared_pct'], '%'):>8}{fmt(c['win_declared_pct'], '%'):>7}"
                  f"{fmt(c['win_declined_pct'], '%'):>7}{fmt(c['deal_in_declared_pct'], '%'):>7}{fmt(c['deal_in_declined_pct'], '%'):>7}")
    print(f"  {'riichi declared after the first tenpai turn':<{w}}{hero['riichi_after_first_tenpai_n']:>9}{opp['riichi_after_first_tenpai_n']:>11}")
    dh, do = hero["dama_decision"], opp.get("dama_decision", {})
    print("  declined riichi at first closed tenpai:")
    for label, key, suffix in (("hands", "declined_n", ""), ("average turn of that tenpai", "declined_avg_turn", ""),
                               ("tenpai on turn 12 or later", "declined_late_pct", "%"),
                               ("never riichi afterwards", "stayed_dama_pct", "%"),
                               ("no yaku for a ron (tsumo only)", "declined_yakuless_pct", "%"),
                               ("  win rate of those", "declined_yakuless_win_pct", "%"),
                               ("  won by tsumo", "declined_yakuless_tsumo_pct", "%"),
                               ("win rate when a ron yaku existed", "declined_with_yaku_win_pct", "%")):
        print(f"    {label:<{w - 2}}{fmt(dh.get(key), suffix):>9}{fmt(do.get(key), suffix):>11}")

    print("\nFirst call of the hand")
    fh, fo = hero["first_call"], opp["first_call"]
    for label, key, suffix in (("hands with a call", "n", ""), ("average turn", "avg_turn", ""),
                               ("yakuhai pon", "yakuhai_pon_pct", "%"), ("chi", "chi_pct", "%"),
                               ("made from 3+ shanten", "from_3plus_shanten_pct", "%"),
                               ("made from 2-shanten", "from_2_shanten_pct", "%"),
                               ("lands at 1-shanten or tenpai", "reaches_1sh_or_tenpai_pct", "%"),
                               ("made with a riichi already out", "under_threat_pct", "%")):
        print(f"  {label:<{w}}{fmt(fh.get(key), suffix):>9}{fmt(fo.get(key), suffix):>11}")
    print(f"  {'open hands by shanten at first call':<{w}}{'n':>5}{'win':>8}{'value':>8}   {opp_label} n/win/value")
    for k in ("0-1", "2", "3+"):
        h, o = hero["open_win_by_call_shanten"][k], opp["open_win_by_call_shanten"][k]
        print(f"    {k:<{w - 2}}{h['n']:>5}{fmt(h['win_rate_pct'], '%'):>8}{fmt(h['avg_win_value']):>8}"
              f"   {o['n']}/{fmt(o['win_rate_pct'], '%')}/{fmt(o['avg_win_value'])}")

    print("\nTenpai hands that did not win (share of all tenpai hands)")
    for k in ("opponent ron elsewhere", "opponent tsumo", "dealt in", "draw"):
        h = hero["tenpai_no_win"].get(k, {}); o = opp["tenpai_no_win"].get(k, {})
        print(f"  {k:<{w}}{fmt(h.get('share_pct'), '%'):>9}{fmt(o.get('share_pct'), '%'):>11}")

    if examples:
        print("\n" + "=" * 78)
        print("COSTLIEST CLOSED-HAND DISCARDS (shanten lost, or 4+ acceptance lost; pre-tenpai, no riichi out)")
        print("=" * 78)
        for ex in examples:
            melds = f"  melds {' / '.join(ex['melds'])}" if ex["melds"] else ""
            print(f"  {ex['game']} {ex['round']} T{ex['turn']}: cut {ex['discard']} "
                  f"-> {ex['shanten_after']}-shanten, {ex['ukeire_after']} acceptance; "
                  f"best {ex['best_discard']} -> {ex['best_shanten']}-shanten, {ex['best_ukeire']}")
            print(f"      hand {ex['hand']}{melds}")


# ------------------------------------------------------------------- main

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--since", help="only games starting on or after this date (YYYY-MM-DD)")
    ap.add_argument("--log", type=Path, help="review one log file instead of the manifest")
    ap.add_argument("--hero", type=int, default=0, help="seat to review with --log")
    ap.add_argument("--all-seats-efficiency", action="store_true",
                    help="score discard efficiency for opponents too (slower)")
    ap.add_argument("--baseline", type=Path,
                    help="a summary JSON from an earlier run; its hero column replaces the opponents column")
    ap.add_argument("--baseline-label", default="LuckyJ")
    ap.add_argument("--examples", type=int, default=12, help="how many costly discards to list")
    ap.add_argument("--json", dest="json_out", type=Path, help="write the summary here")
    args = ap.parse_args()

    if args.log:
        games = [{"file": str(args.log), "hero_seat": args.hero, "hero_name": f"p{args.hero}",
                  "uuid": args.log.stem, "date": ""}]
    else:
        games = json.loads(args.manifest.read_text(encoding="utf-8"))
        if args.since:
            cutoff = datetime.strptime(args.since, "%Y-%m-%dT%H:%M" if "T" in args.since else "%Y-%m-%d").timestamp()
            games = [g for g in games if g["start_time"] >= cutoff]
    if not games:
        sys.exit("no games selected")

    hero_recs, opp_recs, examples = [], [], []
    for game in games:
        hero = game["hero_seat"]
        logs = load_logs(ROOT / game["file"] if not Path(game["file"]).is_absolute() else game["file"])
        scored = set(range(4)) if args.all_seats_efficiency else {hero}
        for log in logs:
            recs = hand_records(log, scored)
            for r in recs:
                (hero_recs if r["seat"] == hero else opp_recs).append(r)
                if r["seat"] == hero:
                    for ex in r["eff_examples"]:
                        examples.append({"game": game["uuid"][:13], **ex})
    hero_sum, opp_sum = summarize(hero_recs), summarize(opp_recs)
    if not args.all_seats_efficiency:
        for k in ("eff_events", "eff_shanten_loss_pct", "eff_ukeire_loss_pct", "eff_ukeire_lost_per_100",
                  "eff_closed_events", "eff_closed_ukeire_loss_pct", "eff_closed_ukeire_lost_per_100"):
            opp_sum[k] = None
    examples.sort(key=lambda e: (-e["shanten_loss"], -e["ukeire_loss"]))
    ref = load_reference()
    lj = luckyj_riichi_reference()
    hero_name = games[0].get("hero_name") or f"p{games[0]['hero_seat']}"
    opp_label, opp_desc = "opponents", "hands at the same tables"
    if args.baseline:
        base_payload = json.loads(args.baseline.read_text(encoding="utf-8"))
        opp_sum = base_payload["hero"]
        opp_label = args.baseline_label
        opp_desc = f"hands from {base_payload['games']} games, same code"
    print_report(hero_sum, opp_sum, ref.get("values", {}), lj, len(games), hero_name, examples[:args.examples],
                 opp_label, opp_desc)

    if args.json_out:
        payload = {
            "games": len(games), "since": args.since,
            "hero": hero_sum, "opponents" if not args.baseline else "baseline": opp_sum,
            "baseline_label": opp_label if args.baseline else None,
            "amae_koromo_reference": ref, "luckyj_reference": lj,
            "costly_discards": examples,
        }
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
