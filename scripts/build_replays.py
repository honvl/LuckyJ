#!/usr/bin/env python3
"""Build the site's own replays of Honver's Mahjong Soul games (``site/replays/``).

Each game in ``data/self_games/majsoul/index.json`` (a tenhou.net/6 log fetched by tensoul)
becomes ``site/replays/<uuid>.json``: every hand as an ordered event stream that
``site/replay.js`` steps through, and, for each of Honver's decisions, the local Mortal
policy's probability for every legal action (the same model and weights as
``scripts/build_mortal_analysis.py``). ``site/replays/index.json`` lists the games.

Opponents appear by seat and Mahjong Soul rank only; their account names are left out.

Every hand is checked before it is written: each seat's draw and discard columns must be used
up exactly, every discarded or called tile must be in the hand, and the scores after the hand
must equal the scores the next hand starts with. Mortal's own game state (libriichi) then
replays the hero's seat, which rejects any event that could not have happened.

Event encoding (one short array per event, seats are absolute 0-3 with 0 the first dealer)::

    ["t", seat, tile]                 draw; a fourth element 1 marks a replacement draw after a kan
    ["d", seat, tile, tsumogiri]      discard; tsumogiri is 1 when the drawn tile was cut
    ["r", seat]                       riichi declared (its discard follows)
    ["ra", seat]                      riichi stick placed (the declaration tile was not ronned)
    ["c"|"p"|"m", seat, from, tile, consumed]   chi, pon, open kan of another seat's discard
    ["a", seat, tiles]                closed kan
    ["k", seat, tile, pon_tiles]      added kan onto a pon
    ["dora", indicator]               a new dora indicator is turned

Usage::

    .venv/bin/python scripts/build_replays.py              # every game, with Mortal
    .venv/bin/python scripts/build_replays.py --no-mortal  # event streams only
    .venv/bin/python scripts/build_replays.py --only 260928-50d32e06
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tenhou_replay as tr  # noqa: E402
from build_personal_guide import YAKU_EN, site_tile  # noqa: E402
from review_win_speed import HAN_RE  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/self_games/majsoul/index.json"
OUT_DIR = ROOT / "site/replays"
PAIFU_URL = "https://mahjongsoul.game.yo-star.com/?paipu={uuid}"
FORMAT_VERSION = 1

ROUND_WIND = ["E", "S", "W", "N"]
RANK_EN = {"初心": "Novice", "雀士": "Adept", "雀傑": "Expert", "雀豪": "Master", "雀聖": "Saint", "魂天": "Celestial"}
DRAW_EN = {
    "流局": "Exhaustive draw",
    "全員聴牌": "Exhaustive draw",
    "全員不聴": "Exhaustive draw",
    "流し満貫": "Nagashi mangan",
    "九種九牌": "Nine terminals abortive draw",
    "四風連打": "Four winds abortive draw",
    "四家立直": "Four riichi abortive draw",
    "四槓散了": "Four kans abortive draw",
    "三家和了": "Triple ron abortive draw",
}
LIMIT_EN = {"満貫": "mangan", "跳満": "haneman", "倍満": "baiman", "三倍満": "sanbaiman", "役満": "yakuman"}

# Mortal's action space: 0-36 discard a tile (34-36 are the red fives), then the rest.
ACTION_TILES = [
    "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
    "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
    "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s",
    "E", "S", "W", "N", "P", "F", "C", "5mr", "5pr", "5sr",
]
ACTION_NAMES = {37: "riichi", 38: "chi-low", 39: "chi-mid", 40: "chi-high", 41: "pon", 42: "kan", 43: "win", 44: "draw", 45: "pass"}
# Tile probabilities under this are dropped from the file; the hero's own choice and every action
# that is not a discard (riichi, calls, a win, passing) are always kept.
MIN_PROB = 0.0005


class Inconsistent(Exception):
    """The log cannot be replayed with this reading of an ambiguous call."""


# ---------------------------------------------------------------- one hand

def _take(hand: list[int], tile: int) -> None:
    try:
        hand.remove(tile)
    except ValueError as exc:
        raise Inconsistent(f"tile {tile} not in hand {sorted(hand)}") from exc


def _simulate(log: list, plan: list[int], branches: list[int]) -> list[list]:
    """Linearise one tenhou.net/6 hand into events.

    ``plan`` picks an option at each discard that more than one pending call token could
    claim (the default 0 is the pon or kan, then the chi, then nobody); ``branches`` records
    how many options each such discard had, so the caller can search the other readings.
    """
    kyoku = log[0][0]
    dora = list(log[2])
    players = [
        {"hand": list(log[4 + 3 * s]), "draws": log[5 + 3 * s], "discards": log[6 + 3 * s], "di": 0, "ci": 0}
        for s in range(4)
    ]
    events: list[list] = []
    shown = 1  # dora indicators turned so far
    pending = 0  # open kans whose indicator turns after the next discard

    def turn_dora() -> None:
        nonlocal shown
        if shown < len(dora):
            events.append(["dora", site_tile(dora[shown])])
            shown += 1

    def flush_pending() -> None:
        nonlocal pending
        while pending:
            turn_dora()
            pending -= 1

    cur = kyoku % 4
    for _ in range(1000):
        p = players[cur]
        if p["di"] >= len(p["draws"]):
            break  # ron on the previous discard, an exhaustive draw or an abortive draw
        entry = p["draws"][p["di"]]
        p["di"] += 1
        drawn = None
        if isinstance(entry, str):
            meld = tr.parse_meld(entry)
            src = (cur + meld["from_offset"]) % 4
            consumed = list(meld["tiles"])
            consumed.remove(meld["called"])
            for t in consumed:
                _take(p["hand"], t)
            if meld["kind"] not in ("c", "p", "m"):
                raise Inconsistent(f"call token {entry!r} in a draw column")
            events.append([meld["kind"], cur, src, site_tile(meld["called"]), [site_tile(t) for t in consumed]])
            if meld["kind"] == "m":
                if p["ci"] < len(p["discards"]) and p["discards"][p["ci"]] == 0:
                    p["ci"] += 1
                if p["di"] >= len(p["draws"]):
                    raise Inconsistent("open kan without a replacement draw")
                drawn = p["draws"][p["di"]]
                p["di"] += 1
                if isinstance(drawn, str):
                    raise Inconsistent("call token where a replacement draw belongs")
                p["hand"].append(drawn)
                events.append(["t", cur, site_tile(drawn), 1])
                pending += 1
        else:
            drawn = entry
            p["hand"].append(drawn)
            events.append(["t", cur, site_tile(drawn)])

        ended = False
        riichi = False
        while True:
            if p["ci"] >= len(p["discards"]):
                ended = True  # tsumo, a nine-terminals draw, or a win off a replacement tile
                break
            entry = p["discards"][p["ci"]]
            p["ci"] += 1
            if isinstance(entry, str) and entry.startswith("r"):
                riichi = True
                entry = int(entry[1:])
            if not isinstance(entry, str):
                break
            meld = tr.parse_meld(entry)
            flush_pending()
            if meld["kind"] == "k":
                added = meld["called"]
                pon = list(meld["tiles"])
                pon.remove(added)
                _take(p["hand"], added)
                events.append(["k", cur, site_tile(added), [site_tile(t) for t in pon]])
                pending += 1
            elif meld["kind"] == "a":
                for t in meld["tiles"]:
                    _take(p["hand"], t)
                events.append(["a", cur, [site_tile(t) for t in meld["tiles"]]])
                turn_dora()
            else:
                raise Inconsistent(f"call token {entry!r} in a discard column")
            if p["di"] >= len(p["draws"]):
                ended = True  # robbed kan, or the hand ended on the kan
                break
            drawn = p["draws"][p["di"]]
            p["di"] += 1
            if isinstance(drawn, str):
                raise Inconsistent("call token where a replacement draw belongs")
            p["hand"].append(drawn)
            events.append(["t", cur, site_tile(drawn), 1])
        if ended:
            break

        tsumogiri = entry == tr.TSUMOGIRI
        tile = drawn if tsumogiri else entry
        if tile is None:
            raise Inconsistent("tsumogiri right after a call")
        _take(p["hand"], tile)
        if riichi:
            events.append(["r", cur])
        events.append(["d", cur, site_tile(tile), 1 if tsumogiri else 0])
        flush_pending()
        if riichi:
            events.append(["ra", cur])

        # Who takes the tile: a seat whose next draw token calls this tile from this seat.
        pon_caller = chi_caller = None
        for offset in (1, 2, 3):
            q = players[(cur + offset) % 4]
            if q["di"] < len(q["draws"]) and isinstance(q["draws"][q["di"]], str):
                meld = tr.parse_meld(q["draws"][q["di"]])
                if meld["called"] == tile and ((cur + offset) + meld["from_offset"]) % 4 == cur:
                    if meld["kind"] == "c":
                        chi_caller = (cur + offset) % 4
                    elif meld["kind"] in ("p", "m"):
                        pon_caller = (cur + offset) % 4
        options = [s for s in (pon_caller, chi_caller) if s is not None]
        if options:
            options.append(None)  # a matching token can belong to a later copy of the tile
            k = len(branches)
            branches.append(len(options))
            choice = plan[k] if k < len(plan) else 0
            nxt = options[choice]
        else:
            nxt = None
        cur = nxt if nxt is not None else (cur + 1) % 4
    else:
        raise Inconsistent("hand did not end")

    for s, q in enumerate(players):
        if q["di"] != len(q["draws"]) or q["ci"] != len(q["discards"]):
            raise Inconsistent(f"seat {s} left draws or discards unused")
    return events


def linearise(log: list) -> list[list]:
    """The hand's events, searching the readings of any call token that could claim two discards."""
    stack: list[list[int]] = [[]]
    tried = 0
    last_error: Exception | None = None
    while stack and tried < 5000:
        plan = stack.pop()
        tried += 1
        branches: list[int] = []
        try:
            return _simulate(log, plan, branches)
        except Inconsistent as exc:
            last_error = exc
        # Try the other options at each ambiguous discard met beyond the fixed prefix.
        for k in range(len(branches) - 1, len(plan) - 1, -1):
            for alt in range(branches[k] - 1, 0, -1):
                stack.append(plan + [0] * (k - len(plan)) + [alt])
    raise Inconsistent(f"no consistent reading: {last_error}")


# ---------------------------------------------------------------- results

def points_text(text: str) -> str:
    """``30符3飜3900点∀`` -> ``30 fu 3 han, 3,900 all``."""
    all_pay = text.endswith("∀")
    body = text.rstrip("∀").removesuffix("点")
    limit = ""
    for jp, en in LIMIT_EN.items():
        if body.startswith(jp):
            limit, body = en, body[len(jp):]
            break
    if not limit:
        fu, rest = body.split("符", 1)
        han, body = rest.split("飜", 1)
        limit = f"{fu} fu {han} han"
    if "-" in body:
        lo, hi = body.split("-")
        pay = f"{int(lo):,}/{int(hi):,}"
    else:
        pay = f"{int(body):,}" + (" all" if all_pay else "")
    return f"{limit}, {pay}"


def yaku_list(entries: list[str]) -> list[list]:
    out = []
    for entry in entries:
        name = entry.split("(")[0].strip()
        m = HAN_RE.search(entry)
        han = int(m.group(1)) if m else None
        if han == 0:
            continue
        out.append([YAKU_EN.get(name, name), han if han is not None else "yakuman"])
    return out


def hand_end(log: list, events: list[list]) -> dict:
    result = log[-1]
    label = result[0]
    blocks = tr.result_blocks(result)
    if label == "和了":
        wins = []
        for deltas, d in blocks:
            winner, source = d[0], d[1]
            wins.append({
                "seat": winner,
                "from": source,
                "deltas": deltas,
                "value": points_text(d[3]),
                "yaku": yaku_list(d[4:]),
            })
        return {"kind": "win", "wins": wins, "ura": [site_tile(t) for t in log[3]]}
    deltas = result[1] if len(result) > 1 and isinstance(result[1], list) else [0, 0, 0, 0]
    return {"kind": "draw", "label": DRAW_EN.get(label, label), "deltas": deltas}


def drop_ronned_declaration(events: list[list], end: dict) -> None:
    """A riichi whose declaration tile is ronned never puts its stick down."""
    if end["kind"] != "win":
        return
    last_discard = max((i for i, e in enumerate(events) if e[0] == "d"), default=None)
    if last_discard is None:
        return
    seat = events[last_discard][1]
    if any(w["from"] == seat and w["seat"] != seat for w in end["wins"]):
        for i in range(len(events) - 1, last_discard, -1):
            if events[i][0] == "ra" and events[i][1] == seat:
                del events[i]


def scores_after(start: list[int], events: list[list], end: dict) -> list[int]:
    scores = list(start)
    for e in events:
        if e[0] == "ra":
            scores[e[1]] -= 1000
    if end["kind"] == "win":
        for w in end["wins"]:
            for s in range(4):
                scores[s] += w["deltas"][s]
    else:
        for s in range(4):
            scores[s] += end["deltas"][s]
    return scores


def check_hand(log: list, events: list[list]) -> None:
    """Each seat keeps 13 tiles (plus melds) between turns."""
    hands = [len(log[4 + 3 * s]) for s in range(4)]
    for e in events:
        kind = e[0]
        if kind == "t":
            hands[e[1]] += 1
        elif kind == "d":
            hands[e[1]] -= 1
        elif kind in ("c", "p", "m"):
            hands[e[1]] -= len(e[4])
        elif kind == "a":
            hands[e[1]] -= 4
        elif kind == "k":
            hands[e[1]] -= 1
    for s, n in enumerate(hands):
        melds = sum(1 for e in events if e[0] in ("c", "p", "m", "a") and e[1] == s)
        if n + 3 * melds not in (13, 14):
            raise Inconsistent(f"seat {s} ends with {n} tiles in hand and {melds} melds")


# ---------------------------------------------------------------- games

def rank_en(dan: str) -> str:
    for jp, en in RANK_EN.items():
        if dan.startswith(jp):
            stars = dan[len(jp):].lstrip("★")
            return f"{en} {stars}".strip()
    return dan


def round_name(kyoku: int, honba: int) -> str:
    return f"{tr.ROUND_NAMES[kyoku]}-{honba}"


def build_game(row: dict) -> dict:
    game = json.loads((ROOT / row["file"]).read_text(encoding="utf-8"))
    hero = row["hero_seat"]
    hands = []
    for log in game["log"]:
        kyoku, honba, sticks = log[0]
        events = linearise(log)
        check_hand(log, events)
        end = hand_end(log, events)
        drop_ronned_declaration(events, end)
        hands.append({
            "round": round_name(kyoku, honba),
            "kyoku": kyoku,
            "honba": honba,
            "sticks": sticks,
            "scores": list(log[1]),
            "dora": site_tile(log[2][0]),
            "haipai": [[site_tile(t) for t in log[4 + 3 * s]] for s in range(4)],
            "ev": events,
            "end": end,
        })
    for a, b in zip(hands, hands[1:]):
        after = scores_after(a["scores"], a["ev"], a["end"])
        if after != b["scores"]:
            raise Inconsistent(f"{a['round']}: scores after {after} but {b['round']} starts with {b['scores']}")
        a["after"] = after
    hands[-1]["after"] = scores_after(hands[-1]["scores"], hands[-1]["ev"], hands[-1]["end"])

    sc = game["sc"]
    final = [sc[2 * s] for s in range(4)]
    points = [sc[2 * s + 1] for s in range(4)]
    order = sorted(range(4), key=lambda s: (-final[s], s))
    placement = [order.index(s) + 1 for s in range(4)]
    return {
        "v": FORMAT_VERSION,
        "id": row["uuid"],
        "date": row["date"],
        "room": "Jade South" if row.get("mode") == "jade-south" else game.get("rule", {}).get("disp", ""),
        "hero": hero,
        "players": [
            {"name": row.get("hero_name", "Honver") if s == hero else None, "rank": rank_en(game["dan"][s])}
            for s in range(4)
        ],
        "final": final,
        "points": points,
        "placement": placement,
        "source": PAIFU_URL.format(uuid=row["uuid"]),
        "hands": hands,
    }


# ---------------------------------------------------------------- Mortal

def mjai_events(game: dict) -> list[tuple[int | None, int | None, dict]]:
    """``(hand index, event index, mjai event)`` for the whole game, in order."""
    out: list[tuple[int | None, int | None, dict]] = [(None, None, {"type": "start_game", "names": ["", "", "", ""]})]
    for h, hand in enumerate(game["hands"]):
        kyoku = hand["kyoku"]
        out.append((h, None, {
            "type": "start_kyoku", "bakaze": ROUND_WIND[kyoku // 4], "dora_marker": hand["dora"],
            "kyoku": kyoku % 4 + 1, "honba": hand["honba"], "kyotaku": hand["sticks"], "oya": kyoku % 4,
            "scores": hand["scores"], "tehais": hand["haipai"],
        }))
        for i, e in enumerate(hand["ev"]):
            kind = e[0]
            if kind == "t":
                ev = {"type": "tsumo", "actor": e[1], "pai": e[2]}
            elif kind == "d":
                ev = {"type": "dahai", "actor": e[1], "pai": e[2], "tsumogiri": bool(e[3])}
            elif kind == "r":
                ev = {"type": "reach", "actor": e[1]}
            elif kind == "ra":
                ev = {"type": "reach_accepted", "actor": e[1]}
            elif kind in ("c", "p", "m"):
                ev = {"type": {"c": "chi", "p": "pon", "m": "daiminkan"}[kind], "actor": e[1], "target": e[2],
                      "pai": e[3], "consumed": e[4]}
            elif kind == "a":
                ev = {"type": "ankan", "actor": e[1], "consumed": e[2]}
            elif kind == "k":
                ev = {"type": "kakan", "actor": e[1], "pai": e[2], "consumed": e[3]}
            elif kind == "dora":
                ev = {"type": "dora", "dora_marker": e[1]}
            else:
                raise ValueError(kind)
            out.append((h, i, ev))
        end = hand["end"]
        if end["kind"] == "win":
            for w in end["wins"]:
                out.append((h, None, {"type": "hora", "actor": w["seat"], "target": w["from"], "deltas": w["deltas"],
                                      "ura_markers": end["ura"]}))
        else:
            out.append((h, None, {"type": "ryukyoku", "deltas": end["deltas"]}))
        out.append((h, None, {"type": "end_kyoku"}))
    out.append((None, None, {"type": "end_game"}))
    return out


def chi_kind(called: str, consumed: list[str]) -> str:
    num = lambda t: int(t[0])  # noqa: E731
    lo = min(num(t) for t in consumed)
    if num(called) < lo:
        return "chi-low"
    if num(called) > max(num(t) for t in consumed):
        return "chi-high"
    return "chi-mid"


def actual_action(hand: dict, i: int, hero: int) -> str:
    """What the hero did at the decision that follows event ``i``."""
    events = hand["ev"]
    trigger = events[i]
    own_turn = trigger[1] == hero and trigger[0] in ("t", "c", "p", "r")
    for e in events[i + 1:]:
        if e[0] in ("dora", "ra"):
            continue
        if own_turn:
            if e[1] != hero:
                break
            if e[0] == "d":
                return e[2]
            if e[0] == "r":
                return "riichi"
            if e[0] in ("a", "k"):
                return "kan"
            break
        # Another seat's discard or kan: did the hero claim it?
        if e[1] == hero and e[0] in ("c", "p", "m"):
            return chi_kind(e[3], e[4]) if e[0] == "c" else "pon" if e[0] == "p" else "kan"
        return "pass"
    end = hand["end"]
    if end["kind"] == "win" and any(w["seat"] == hero for w in end["wins"]):
        return "win"
    if own_turn and end["kind"] == "draw" and end["label"].startswith("Nine terminals"):
        return "draw"
    return "pass"


def decode(reaction: dict) -> list[list]:
    meta = reaction.get("meta") or {}
    q = meta.get("q_values") or []
    mask = int(meta.get("mask_bits") or 0)
    legal = [a for a in range(46) if (mask >> a) & 1]
    out = []
    for action, prob in zip(legal, q):
        name = ACTION_TILES[action] if action < 37 else ACTION_NAMES[action]
        out.append([name, float(prob)])
    out.sort(key=lambda item: -item[1])
    return out


def load_engine():
    import build_mortal_analysis as bma

    import torch

    torch.set_num_threads(2)
    return bma.load_mortal_engine(bma.DEFAULT_MODEL)


def annotate(game: dict, engine) -> None:
    """Attach Mortal's probabilities to each of the hero's decisions with a real choice."""
    from libriichi.mjai import Bot

    hero = game["hero"]
    bot = Bot(engine, hero)
    for hand in game["hands"]:
        hand["ai"] = []
    for h, i, ev in mjai_events(game):
        raw = bot.react(json.dumps(ev, ensure_ascii=False), can_act=True)
        if not raw or i is None:
            continue
        probs = decode(json.loads(raw))
        if len(probs) < 2:
            continue
        hand = game["hands"][h]
        you = actual_action(hand, i, hero)
        total = sum(p for _, p in probs)
        if abs(total - 1) > 0.01:
            raise RuntimeError(f"Mortal probabilities sum to {total}")
        kept = [[a, round(p, 3)] for a, p in probs if p >= MIN_PROB or a == you or a in ACTION_NAMES.values()]
        if you not in {a for a, _ in probs}:
            raise Inconsistent(f"{hand['round']} event {i}: the hero's {you!r} is not among Mortal's legal actions {probs}")
        hand["ai"].append({"i": i, "p": kept, "you": you})


# A choice Mortal gives less than this is flagged in the viewer and counted in the index.
FLAG_BELOW = 0.05


def summarise(game: dict) -> dict:
    hero = game["hero"]
    summary = {
        "id": game["id"],
        "date": game["date"],
        "room": game["room"],
        "placement": game["placement"][hero],
        "score": game["final"][hero],
        "points": game["points"][hero],
        "hands": len(game["hands"]),
        "rank": game["players"][hero]["rank"],
    }
    turns, calls = [], []
    for hand in game["hands"]:
        for d in hand.get("ai", []):
            (turns if hand["ev"][d["i"]][1] == hero else calls).append(d)
    if not turns and not calls:
        return summary

    def matched(d):
        return d["p"][0][0] == d["you"]

    def prob(d):
        return next((p for a, p in d["p"] if a == d["you"]), 0.0)

    summary.update({
        "turns": len(turns),
        "turns_matched": sum(1 for d in turns if matched(d)),
        "calls": len(calls),
        "calls_matched": sum(1 for d in calls if matched(d)),
        "flagged": sum(1 for d in turns + calls if prob(d) < FLAG_BELOW),
    })
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--only", help="uuid prefix of one game")
    ap.add_argument("--no-mortal", action="store_true", help="write the event streams without Mortal")
    ap.add_argument("--since", default="2026-01-01", help="first date to include (YYYY-MM-DD)")
    args = ap.parse_args()

    rows = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = [r for r in rows if r["date"] >= args.since]
    if args.only:
        rows = [r for r in rows if r["uuid"].startswith(args.only)]
    rows.sort(key=lambda r: r["start_time"], reverse=True)
    engine = None if args.no_mortal else load_engine()
    args.out.mkdir(parents=True, exist_ok=True)

    index_path = args.out / "index.json"
    previous = {}
    if args.only and index_path.exists():
        previous = {g["id"]: g for g in json.loads(index_path.read_text(encoding="utf-8"))["games"]}

    for n, row in enumerate(rows, 1):
        game = build_game(row)
        if engine is not None:
            annotate(game, engine)
        path = args.out / f"{row['uuid']}.json"
        path.write_text(json.dumps(game, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        previous[row["uuid"]] = summarise(game)
        print(f"[{n}/{len(rows)}] {row['uuid']} {len(game['hands'])} hands", file=sys.stderr)

    games = sorted(previous.values(), key=lambda g: g["date"], reverse=True)
    index = {"v": FORMAT_VERSION, "generated": datetime.date.today().isoformat(), "player": "Honver",
             "model": "Mortal policy model (local weights)", "games": games}
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} games to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
