#!/usr/bin/env python3
"""Build site/honver-guide.json, the table states behind the personal guide page.

The spots and their commentary live in ``data/personal_guide_spots.json``. Each spot
names a game (a uuid prefix from the Mahjong Soul manifest), a round such as
``East 4-1`` and one or more of the player's turns. This script replays the game,
rebuilds the table at each turn in the format ``site/app.js`` renders
(``renderMahjongTable``), and attaches what the decision looked like: every discard
option with the shanten and acceptance it leaves, and how safe it was against each
live threat at that moment.

Two details differ from the older review scripts on purpose:

- a called tile is counted once when acceptance is measured (the river and the meld
  both hold it, and counting both undercounts what is still live);
- safety uses the table as it stood at that turn, including tiles passed after a
  riichi, and a lone honor with all three other copies showing is labelled dead.

Usage::

    .venv/bin/python scripts/build_personal_guide.py          # write the JSON
    .venv/bin/python scripts/build_personal_guide.py --show   # print every frame for review
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_win_speed as ws  # noqa: E402
import tenhou_replay as tr  # noqa: E402
from tenhou_replay import base, is_honor, is_red, is_terminal  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SPOTS = ROOT / "data/personal_guide_spots.json"
MANIFEST = ROOT / "data/self_games/majsoul/index.json"
OUT = ROOT / "site/honver-guide.json"
PAIFU_URL = "https://mahjongsoul.game.yo-star.com/?paipu={uuid}"

REL = {0: "self", 1: "shimocha", 2: "toimen", 3: "kamicha"}
REL_NAME = {"self": "you", "shimocha": "Shimocha", "toimen": "Toimen", "kamicha": "Kamicha"}
WIND = {41: "E", 42: "S", 43: "W", 44: "N"}
SITE_HONOR = {41: "E", 42: "S", 43: "W", 44: "N", 45: "P", 46: "F", 47: "C"}
MELD_KIND = {"c": "chi", "p": "pon", "m": "daiminkan", "k": "pon", "a": "ankan"}
DANGER = {
    "genbutsu": 0, "dead": 0, "suji": 1, "honor, 2 seen": 1,
    "live honor": 2, "live terminal": 2, "live 2-3-7-8": 3, "live 4-5-6": 4,
}
YAKU_EN = {
    "立直": "riichi", "ダブル立直": "double riichi", "一発": "ippatsu", "門前清自摸和": "menzen tsumo",
    "断幺九": "tanyao", "平和": "pinfu", "一盃口": "iipeikou", "二盃口": "ryanpeikou",
    "役牌 白": "haku", "役牌 發": "hatsu", "役牌 中": "chun", "役牌:自風牌": "seat wind",
    "役牌:場風牌": "round wind", "混一色": "honitsu", "清一色": "chinitsu", "対々和": "toitoi",
    "七対子": "chiitoitsu", "三色同順": "sanshoku", "一気通貫": "ittsu", "混全帯幺九": "chanta",
    "純全帯幺九": "junchan", "三暗刻": "sanankou", "小三元": "shousangen", "混老頭": "honroutou",
    "三槓子": "sankantsu", "三色同刻": "sanshoku doukou", "海底摸月": "haitei", "河底撈魚": "houtei",
    "嶺上開花": "rinshan", "槍槓": "chankan", "ドラ": "dora", "赤ドラ": "red five", "裏ドラ": "ura dora",
}


# ---------------------------------------------------------------- tiles

def site_tile(code: int) -> str:
    """Replay tile code to the site's tile string (``5pr`` for a red five, ``P`` for haku)."""
    if is_red(code):
        return f"5{'mps'[base(code) // 10 - 1]}r"
    if code >= 41:
        return SITE_HONOR[code]
    return f"{code % 10}{'mps'[code // 10 - 1]}"


def parse_tile(text: str) -> int:
    """Accept the spot file's tile names: ``3s``, ``0p``/``5pr`` for red, ``E``, ``haku``/``P``."""
    t = text.strip()
    honors = {"E": 41, "S": 42, "W": 43, "N": 44, "P": 45, "F": 46, "C": 47,
              "haku": 45, "hatsu": 46, "chun": 47}
    if t in honors:
        return honors[t]
    if t.endswith("r") and len(t) == 3:
        return {"m": 51, "p": 52, "s": 53}[t[1]]
    num, suit = int(t[0]), "mps".index(t[1]) + 1
    if num == 0:
        return {1: 51, 2: 52, 3: 53}[suit]
    return suit * 10 + num


def hand_string(tiles) -> str:
    return " ".join(site_tile(t) for t in tiles)


def sort_key(code: int) -> tuple:
    b = base(code)
    return (b, 0 if is_red(code) else 1)


# ---------------------------------------------------------------- table state

def locate(spot: dict, manifest: list[dict]):
    rows = [m for m in manifest if m["uuid"].startswith(spot["game"])]
    if len(rows) != 1:
        raise SystemExit(f"{spot['id']}: game prefix {spot['game']!r} matched {len(rows)} games")
    row = rows[0]
    for log in tr.load_logs(ROOT / row["file"]):
        game = tr.replay(log)
        if game["round_name"] == spot["round"]:
            return row, log, game
    raise SystemExit(f"{spot['id']}: no {spot['round']} in {row['uuid']}")


def meld_snapshots(game: dict, upto: int) -> dict[int, list[list[int]]]:
    """Each seat's melds as of event ``upto`` (from that seat's latest event)."""
    snap = {s: [] for s in range(4)}
    for ev in game["events"][: upto + 1]:
        snap[ev["seat"]] = ev["melds"]
    return snap


def draws_so_far(game: dict, upto: int) -> int:
    """Tiles drawn from the wall through event ``upto``.

    An event records one drawn tile, but a closed or added kan inside it also takes a
    replacement tile, and every kan shortens the live wall by one.
    """
    draws = 0
    fours = {s: 0 for s in range(4)}
    for ev in game["events"][: upto + 1]:
        if ev["drawn"] is not None:
            draws += 1
        now = sum(1 for tiles in ev["melds"] if len(tiles) == 4)
        new_kans = max(0, now - fours[ev["seat"]])
        if ev["called"] is not None and ev["called"]["kind"] == "m":
            new_kans -= 1  # an open kan replaces the draw; its replacement is the recorded tile
        draws += max(0, new_kans)
        fours[ev["seat"]] = now
    return draws


def concealed_hands(game: dict, upto: int) -> dict[int, list[int]]:
    hands = {s: list(game["players"][s]["haipai"]) for s in range(4)}
    for ev in game["events"][:upto]:
        hands[ev["seat"]] = list(ev["hand_after"])
    return hands


def visible_counter(hand, e, players, snap, indicators) -> Counter:
    """Copies of each tile the player can see, with a called tile counted once."""
    c = Counter(base(t) for t in hand)
    for s in range(4):
        for t in e["rivers"][s]:
            c[base(t)] += 1
        for tiles in snap[s]:
            for t in tiles:
                c[base(t)] += 1
        for meld in players[s]["melds"][: len(snap[s])]:
            if meld["kind"] in ("c", "p", "m", "k"):
                c[base(meld["called"])] -= 1
    for t in indicators:
        c[base(t)] += 1
    return c


def safety(tile: int, q: int, e: dict, game: dict, seen: Counter) -> str:
    """How safe ``tile`` is against seat ``q`` at event ``e``; ``seen`` excludes the tile itself."""
    b = base(tile)
    if any(base(x) == b for x in e["rivers"][q]):
        return "genbutsu"
    r = e["riichi_seats"][q]
    if r is not None and any(base(ev["tile"]) == b for ev in game["events"][r + 1: e["index"]]):
        return "genbutsu"
    if is_honor(tile):
        others = seen[b]
        if others >= 3:
            return "dead"
        return "honor, 2 seen" if others == 2 else "live honor"
    if tr_suji(tile, e["rivers"][q]):
        return "suji"
    if is_terminal(tile):
        return "live terminal"
    return "live 2-3-7-8" if b % 10 in (2, 3, 7, 8) else "live 4-5-6"


def tr_suji(tile, river) -> bool:
    b = base(tile)
    suit, num = divmod(b, 10)
    seen = {base(x) for x in river}
    if num <= 3:
        return suit * 10 + num + 3 in seen
    if num >= 7:
        return suit * 10 + num - 3 in seen
    return suit * 10 + num - 3 in seen and suit * 10 + num + 3 in seen


def site_melds(game: dict, seat: int, snap_tiles: list[list[int]]) -> list[dict]:
    out = []
    for meld, tiles in zip(game["players"][seat]["melds"], snap_tiles):
        kind = MELD_KIND[meld["kind"]]
        rel = {1: "shimocha", 2: "toimen", 3: "kamicha"}.get((meld["src"] - seat) % 4, "")
        if meld["kind"] == "a":
            out.append({"tiles": [site_tile(t) for t in sorted(tiles, key=sort_key)], "kind": "ankan"})
            continue
        three = list(tiles)[:3] if meld["kind"] == "k" else list(tiles)
        entry = {"tiles": [site_tile(t) for t in three], "called_tile": site_tile(meld["called"]),
                 "called_from": rel, "kind": "daiminkan" if meld["kind"] == "m" else kind}
        out.append(entry)
        if meld["kind"] == "k" and len(tiles) == 4:
            out.append({"tiles": [site_tile(tiles[3])], "kind": "kakan"})
    return out


def build_table(row: dict, log: list, game: dict, e: dict, hero_hand: list[int], hero_melds: list[list[int]]) -> dict:
    hero = row["hero_seat"]
    kyoku = game["kyoku"]
    snap = meld_snapshots(game, e["index"] - 1)
    snap[hero] = hero_melds
    hands = concealed_hands(game, e["index"])
    kans = sum(1 for s in range(4) for tiles in snap[s] if len(tiles) == 4)
    indicators = game["dora_indicators"][: 1 + kans]
    scores = []
    now = {}
    for s in range(4):
        r = e["riichi_seats"][s]
        now[s] = game["start_scores"][s] - (1000 if r is not None and r < e["index"] else 0)
    order = sorted(range(4), key=lambda s: (-now[s], s))
    players = []
    for s in range(4):
        rel = REL[(s - hero) % 4]
        wind = WIND[tr.seat_wind(s, kyoku)]
        scores.append({"seat": rel, "wind": wind, "score": now[s], "rank": order.index(s) + 1,
                       "dealer": s == game["dealer"]})
        r = e["riichi_seats"][s]
        river = e["rivers"][s]
        riichi_index = None
        if r is not None and r < e["index"]:
            riichi_index = sum(1 for ev in game["events"][: r + 1] if ev["seat"] == s) - 1
        concealed = hero_hand if s == hero else sorted(hands[s], key=sort_key)
        players.append({
            "seat": rel, "wind": wind, "hand": hand_string(concealed), "tile_threats": [],
            "discards": [site_tile(t) for t in river],
            "melds": site_melds(game, s, snap[s]),
            "reached": riichi_index is not None, "riichi_discard_index": riichi_index,
        })
    return {"round": game["round_name"], "dealer": REL[(game["dealer"] - hero) % 4],
            "dora_markers": [site_tile(t) for t in indicators], "scores": scores, "players": players}, snap, indicators


def threats_at(game: dict, e: dict, hero: int, snap) -> list[dict]:
    out = []
    for q in range(4):
        if q == hero:
            continue
        r = e["riichi_seats"][q]
        calls = sum(1 for m in game["players"][q]["melds"][: len(snap[q])] if m["kind"] != "a")
        if r is not None and r < e["index"]:
            turn = game["events"][r]["turn"]
            out.append({"seat": q, "rel": REL[(q - hero) % 4], "kind": "riichi", "label": f"{REL_NAME[REL[(q - hero) % 4]]} riichi (turn {turn})"})
        elif calls:
            out.append({"seat": q, "rel": REL[(q - hero) % 4], "kind": "open",
                        "label": f"{REL_NAME[REL[(q - hero) % 4]]} {calls} call{'s' if calls > 1 else ''}"})
    return out


def options_for(hand14, meld_tiles, closed, e, game, threats, visible, dora_set) -> list[dict]:
    out = []
    for tile in sorted({t for t in hand14}, key=sort_key):
        rest = list(hand14)
        rest.remove(tile)
        s, acc, kinds = ws.acceptance(rest, meld_tiles, closed, visible)
        seen = visible.copy()
        seen[base(tile)] -= 1
        labels = [safety(tile, t["seat"], e, game, seen) for t in threats]
        out.append({
            "tile": site_tile(tile), "shanten": s, "accept": acc,
            "waits": [site_tile(k) for k in kinds] if s == 0 else [],
            "safety": labels, "danger": max((DANGER[l] for l in labels), default=None),
            "dora_kept": sum(1 for t in rest + list(meld_tiles) if base(t) in dora_set or is_red(t)),
        })
    out.sort(key=lambda o: (o["shanten"], -o["accept"], o["danger"] if o["danger"] is not None else 0))
    return out


def result_summary(log: list, game: dict, hero: int) -> dict:
    blocks = tr.result_blocks(log[-1])
    delta = tr.result_deltas(log[-1])[hero] - 1000 * tr.riichi_sticks_paid(log)[hero]
    wins = []
    for deltas, d in blocks:
        winner, source = d[0], d[1]
        yaku = []
        for entry in d[4:]:
            nm = entry.split("(")[0].strip()
            m = ws.HAN_RE.search(entry)
            if m and int(m.group(1)) == 0:
                continue
            yaku.append(YAKU_EN.get(nm, nm))
        paid = -deltas[source] if winner != source else sum(-x for i, x in enumerate(deltas) if i != winner and x < 0)
        wins.append({"winner": REL[(winner - hero) % 4], "from": REL[(source - hero) % 4] if winner != source else None,
                     "tsumo": winner == source, "points": paid, "yaku": yaku})
    return {"wins": wins, "draw": not blocks, "hero_delta": delta}


# ---------------------------------------------------------------- frames

def build_frame(spot: dict, fspec: dict, row: dict, log: list, game: dict) -> dict:
    hero = row["hero_seat"]
    kind = fspec.get("kind", "discard")
    evs = [e for e in game["events"] if e["seat"] == hero and e["turn"] == fspec["turn"]]
    if len(evs) != 1:
        raise SystemExit(f"{spot['id']}: turn {fspec['turn']} matched {len(evs)} events")
    e = evs[0]
    p = game["players"][hero]
    kyoku = game["kyoku"]
    dora_ind_first = game["dora_indicators"][:1]
    frame = {"turn": e["turn"], "kind": kind, "note": fspec.get("note", "")}

    if kind == "call":
        if e["called"] is None:
            raise SystemExit(f"{spot['id']}: turn {fspec['turn']} has no call")
        meld = p["melds"][len(e["melds"]) - 1]
        rest = list(meld["tiles"])
        rest.remove(meld["called"])
        hand13 = sorted(list(e["hand_before"]) + rest, key=sort_key)
        melds_before = e["melds"][:-1]
        table, snap, indicators = build_table(row, log, game, e, hand13, melds_before)
        dora_set = frozenset(ws.dora_from_indicator(t) for t in indicators)
        meld_tiles_before = [t for tiles in melds_before for t in tiles[:3]]
        visible = visible_counter(hand13, e, game["players"], snap, indicators)
        s_pass, acc_pass, _ = ws.acceptance(hand13, meld_tiles_before, not melds_before, visible)
        s_call = ws.hand_shanten(e["hand_after"], e["meld_tiles"], False)
        frame.update({
            "table": table,
            "call_from": REL[(meld["src"] - hero) % 4],
            "you": {"action": MELD_KIND[meld["kind"]], "tile": site_tile(meld["called"]),
                    "meld": [site_tile(t) for t in meld["tiles"]], "then_cut": site_tile(e["tile"]),
                    "shanten": s_call},
            "better": {"action": "pass", "shanten": s_pass, "accept": acc_pass},
            "dora_in_hand": sum(1 for t in hand13 + meld_tiles_before if base(t) in dora_set or is_red(t)),
        })
        frame["left"] = 70 - draws_so_far(game, e["index"] - 1)
        return frame, e

    drawn = e["drawn"] if e["called"] is None else None
    hand14 = list(e["hand_before"])
    if drawn is not None:
        rest = list(hand14)
        rest.remove(drawn)
        shown = sorted(rest, key=sort_key) + [drawn]
    else:
        shown = sorted(hand14, key=sort_key)
    table, snap, indicators = build_table(row, log, game, e, shown, e["melds"])
    dora_set = frozenset(ws.dora_from_indicator(t) for t in indicators)
    visible = visible_counter(hand14, e, game["players"], snap, indicators)
    threats = threats_at(game, e, hero, snap)
    opts = options_for(hand14, e["meld_tiles"], e["closed"], e, game, threats, visible, dora_set)
    actual = site_tile(e["tile"])
    if fspec.get("expect_cut") and site_tile(parse_tile(fspec["expect_cut"])) != actual:
        raise SystemExit(f"{spot['id']} T{fspec['turn']}: expected cut {fspec['expect_cut']}, replay has {actual}")
    better = site_tile(parse_tile(fspec["better"])) if fspec.get("better") else None
    by_tile = {o["tile"]: o for o in opts}
    if better and better not in by_tile:
        raise SystemExit(f"{spot['id']} T{fspec['turn']}: better tile {better} is not in the hand")
    cut_index = len(shown) - 1 if e["tsumogiri"] and drawn is not None else next(
        i for i, t in enumerate(shown) if site_tile(t) == actual)
    better_index = next((i for i, t in enumerate(shown) if site_tile(t) == better), None) if better else None
    frame.update({
        "table": table, "threats": [{"rel": t["rel"], "kind": t["kind"], "label": t["label"]} for t in threats],
        "drawn": site_tile(drawn) if drawn is not None else None,
        "you": {**by_tile[actual], "tsumogiri": e["tsumogiri"], "riichi": e["riichi"]},
        "better": dict(by_tile[better]) if better else None,
        "options": opts, "cut_index": cut_index, "better_index": better_index,
        "dora_in_hand": sum(1 for t in hand14 + list(e["meld_tiles"]) if base(t) in dora_set or is_red(t)),
    })
    if kind == "riichi":
        rest = list(hand14)
        rest.remove(e["tile"])
        frame["ron_yaku_without_riichi"] = bool(
            [w for w in tr.waits(rest, e["meld_tiles"], e["closed"]) if ws.ron_has_yaku(rest, w, hero, kyoku)])
        frame["you"]["action"] = "riichi" if e["riichi"] else "dama"
        frame["better"] = {**by_tile[actual], "action": "riichi" if not e["riichi"] else "dama"}
        frame["better_index"] = cut_index
    frame["left"] = 70 - draws_so_far(game, e["index"])
    return frame, e


def build(spec: dict, manifest: list[dict]) -> dict:
    out = {"self_name": spec.get("self_name", "Honver"), "generated": datetime.date.today().isoformat(), "chapters": {}}
    for spot in spec["spots"]:
        row, log, game = locate(spot, manifest)
        frames = []
        for fspec in spot["frames"]:
            frame, _ = build_frame(spot, fspec, row, log, game)
            frames.append(frame)
        example = {
            "id": spot["id"], "title": spot.get("title", ""),
            "game": {"date": row["date"], "uuid": row["uuid"], "placement": row["placement"],
                     "final_score": row["final_scores"][row["hero_seat"]], "url": PAIFU_URL.format(uuid=row["uuid"])},
            "round": game["round_name"], "frames": frames,
            "text": {k: spot.get(k, "") for k in ("situation", "did", "luckyj", "fix")},
            "result": result_summary(log, game, row["hero_seat"]),
            "verdict": spot.get("verdict", "mistake"),
        }
        out["chapters"].setdefault(spot["chapter"], []).append(example)
    return out


def show(data: dict) -> None:
    for chapter, examples in data["chapters"].items():
        print(f"######## {chapter}")
        for ex in examples:
            g = ex["game"]
            print(f"== {ex['id']}: {g['date']} {g['uuid'][:15]} place {g['placement']} | {ex['round']} | result {json.dumps(ex['result'], ensure_ascii=False)}")
            for f in ex["frames"]:
                tb = f["table"]
                me = next(p for p in tb["players"] if p["seat"] == "self")
                sc = {s["seat"]: f"{s['wind']}{s['score']}({s['rank']})" for s in tb["scores"]}
                print(f"  T{f['turn']} [{f['kind']}] left {f['left']} dora {tb['dora_markers']} dealer {tb['dealer']} scores {sc} dora-in-hand {f.get('dora_in_hand')}")
                print(f"    hand {me['hand']}  melds {[m['tiles'] for m in me['melds']]}  drawn {f.get('drawn')}")
                for p in tb["players"]:
                    if p["seat"] == "self":
                        continue
                    ms = " / ".join(" ".join(m["tiles"]) for m in p["melds"])
                    print(f"    {p['seat']:<8} {'RIICHI@' + str(p['riichi_discard_index']) if p['reached'] else '':<9} river {' '.join(p['discards'])}{'  melds ' + ms if ms else ''}  | hand {p['hand']}")
                if f["kind"] == "call":
                    print(f"    YOU {f['you']}  BETTER {f['better']}  from {f['call_from']}")
                    continue
                print(f"    threats {[t['label'] for t in f['threats']]}")
                print(f"    YOU    {f['you']['tile']}: {f['you']['shanten']}sh/{f['you']['accept']} {f['you']['safety']} waits {f['you']['waits']} dora_kept {f['you']['dora_kept']} tsumogiri {f['you']['tsumogiri']} {f['you'].get('action', '')}")
                if f.get("better"):
                    b = f["better"]
                    print(f"    BETTER {b['tile']}: {b['shanten']}sh/{b['accept']} {b['safety']} waits {b['waits']} dora_kept {b['dora_kept']} {b.get('action', '')}")
                if f["kind"] == "riichi":
                    print(f"    ron yaku without riichi: {f['ron_yaku_without_riichi']}")
                print("    options " + "  ".join(f"{o['tile']}:{o['shanten']}/{o['accept']}/{','.join(o['safety']) or '-'}" for o in f["options"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spots", type=Path, default=SPOTS)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--show", action="store_true", help="print every frame instead of writing the JSON")
    args = ap.parse_args()
    spec = json.loads(args.spots.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    data = build(spec, manifest)
    if args.show:
        show(data)
        return
    args.out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    n = sum(len(v) for v in data["chapters"].values())
    shown = args.out.resolve()
    shown = shown.relative_to(ROOT) if shown.is_relative_to(ROOT) else shown
    print(f"wrote {shown}: {n} examples in {len(data['chapters'])} chapters")


if __name__ == "__main__":
    main()
