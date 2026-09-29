#!/usr/bin/env python3
"""Chapter 22: what your extra folds follow. Fear of the other hand, a recent deal-in, the round, or your own hand?

The turns are chapter 20's costly turns: draw turns facing exactly one riichi (or callers with nobody in
riichi) where every safe tile (genbutsu, a full suji, an honor with two showing) leaves the hand a shanten
short of the best hand the draw allows. On each one the hand either folds (throws a safe tile) or keeps
going. The benchmark is Mortal's policy on the same turn: its weight on the safe tiles is how often it
would fold there. Your turns read Mortal from the site's replays (``site/replays``); LuckyJ's from the
local Mortal run over its Tokujou games (``scripts/contrast/mortal_run.py``). "Extra folds" are the folds
beyond Mortal's weight, per 100 turns.

Each test splits the turns two ways and asks whether the split moves your extra folds more than it moves
LuckyJ's: the size of the other hand (a dealer's riichi or a dealer caller against a child's), a deal-in
on the hand before, the round (South against East), and your own hand (two or more dora against none,
and being the dealer). Standard errors come from resampling whole games (``BOOT`` resamples, fixed seed).

It also counts first closed tenpais where riichi was available (declared, and Mortal's weight on riichi),
the one-shanten folds against a riichi by dora and turn, and the example turns the chapter shows.

usage: mine_fold_motives.py YOUR_CHOICES YOUR_CUTS YOUR_TENPAI LJ_CHOICES LJ_CUTS LJ_TENPAI LJ_MORTAL LJ_MANIFEST OUT.json

YOUR_* come from ``scripts/contrast/choices.py``, ``vs_callers.py`` (group self) and ``tenpai.py`` on
``data/self_games/majsoul/index.json``; LJ_* from the same scripts and ``mortal_run.py`` on LuckyJ's
Tokujou manifest. Run it from the main checkout, where the manifest's log paths resolve.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
REPLAYS = ROOT / "site" / "replays"
SAFE_CLASS = 2  # choices.py's CLASS_OF: genbutsu/dead 0, honor with two seen 1, suji/nakasuji 2
SAFE_DANGER = 1  # vs_callers.py's DANGER, the same tiles
REVIEWS_BEGAN = "2026-09-20"
BOOT = 2000
SEED = 22
HONORS = {41: "E", 42: "S", 43: "W", 44: "N", 45: "P", 46: "F", 47: "C"}
MORTAL_TILES = ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
                "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "E", "S", "W", "N", "P", "F", "C", "5m", "5p", "5s"]
MORTAL_RIICHI = 37
# The turns the chapter shows: (game, hand index, your turn).
EXAMPLES = [
    ("260923-275bb855-c2db-43a4-b555-b1c52a836ccd", 12, 4),
    ("260920-9d667586-3125-40f9-9989-9b14743d5967", 8, 7),
    ("260921-7b8a8c7c-94f0-47c6-84ba-1638af253b8d", 11, 13),
]


def tile_name(b: int) -> str:
    return HONORS.get(b) or f"{b % 10}{'mps'[b // 10 - 1]}"


def tile_code(name: str) -> int:
    name = name.replace("r", "")
    for code, honor in HONORS.items():
        if honor == name:
            return code
    return {"m": 10, "p": 20, "s": 30}[name[1]] + int(name[0])


def hand_of(shanten: int) -> str:
    return "tenpai" if shanten == 0 else "one" if shanten == 1 else "far"


# --- costly turns -------------------------------------------------------------------------------------

def riichi_turn(row: dict) -> dict | None:
    """A choices.py row facing exactly one riichi, as a costly turn, or None when it is not one."""
    if row.get("nr") != 1 or row.get("rd") or row.get("called"):
        return None
    cands, best = row["cands"], row["bs"]
    safe = [c for c in cands if c["safe"] is not None and c["safe"] <= SAFE_CLASS]
    if not safe or min(c["sh"] for c in safe) <= best:
        return None  # no safe tile at all, or a safe tile reaches the best hand: not a costly turn
    cut = next(c for c in cands if c["b"] == row["cut"])
    return {"g": row["g"], "li": row["li"], "t": row["t"], "threat": "riichi", "hand": hand_of(best),
            "dora": row["hd"], "me_dealer": row["dl"], "threat_dealer": row["rdealer"], "folded": cut["safe"] <= SAFE_CLASS,
            "cut": row["cut"], "safe": sorted({c["b"] for c in safe})}


def caller_turns(rows: list[dict]) -> dict | None:
    """The vs_callers.py rows of one draw turn (one per caller) as a costly turn, or None."""
    first = rows[0]
    if first["prev_sh"] is None:
        return None
    danger, after = defaultdict(int), {}
    for r in rows:
        for tile, d, sh, _ in r["opts"]:
            danger[tile] = max(danger[tile], d)
            after[tile] = sh
    best = first["best_sh"]
    safe = [t for t in after if danger[t] <= SAFE_DANGER]
    if not safe or min(after[t] for t in safe) <= best:
        return None
    return {"g": first["g"], "li": first["li"], "t": first["t"], "threat": "callers", "hand": hand_of(best),
            "dora": first["my_dora"], "me_dealer": first["me_dealer"], "threat_dealer": any(r["q_dealer"] for r in rows),
            "folded": danger[first["tile"]] <= SAFE_DANGER, "cut": first["tile"], "safe": sorted(safe)}


def read_riichi_turns(path: str, keep: set[str] | None = None) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            if keep is not None and row["g"] not in keep:
                continue
            turn = riichi_turn(row)
            if turn:
                out.append(turn)
    return out


def read_caller_turns(path: str, who: str) -> list[dict]:
    turns = defaultdict(list)
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["who"] == who:
                turns[(r["g"], r["li"], r["s"], r["t"])].append(r)
    return [t for rows in turns.values() if (t := caller_turns(rows))]


# --- your side: Mortal and the table from the site's replays ------------------------------------------

_games: dict[str, dict] = {}


def replay(g: str) -> dict:
    if g not in _games:
        _games[g] = json.loads((REPLAYS / f"{g}.json").read_text())
    return _games[g]


def turn_marks(hand: dict, hero: int) -> list[int]:
    """Your turn at each event: a draw from the wall or a call starts one, as in the replays' turn count."""
    turn, marks = 0, []
    for e in hand["ev"]:
        if e[1] == hero and ((e[0] == "t" and len(e) < 4) or e[0] in ("c", "p", "m")):
            turn += 1
        marks.append(turn)
    return marks


def decision(hand: dict, hero: int, t: int) -> dict | None:
    """Mortal's entry for your draw decision on turn t (riichi is one of its options), or None."""
    marks = turn_marks(hand, hero)
    for a in hand["ai"]:
        if marks[a["i"]] == t and a["p"][0][0] != "pass" and not a["p"][0][0].startswith(("chi", "pon", "kan")):
            return a
    return None


def dealt_in(hand: dict, hero: int) -> bool:
    end = hand["end"]
    return end.get("kind") == "win" and any(w["from"] == hero and w["seat"] != hero for w in end["wins"])


def rank(scores: list[int], seat: int) -> int:
    return sorted(range(4), key=lambda q: (-scores[q], q)).index(seat) + 1


def your_context(turn: dict) -> dict | None:
    game = replay(turn["g"])
    hero, hands = game["hero"], game["hands"]
    hand = hands[turn["li"]]
    a = decision(hand, hero, turn["t"])
    if a is None:
        return None
    safe = {tile_name(b) for b in turn["safe"]}
    return {"mortal_safe": sum(p for act, p in a["p"] if act.replace("r", "") in safe),
            "mortal_cut_match": a["you"].replace("r", "") == tile_name(turn["cut"]),
            "south": hand["round"].startswith("South"), "rank": rank(hand["scores"], hero),
            "prev_dealt": turn["li"] > 0 and dealt_in(hands[turn["li"] - 1], hero), "date": game["date"]}


# --- LuckyJ's side: Mortal from mortal_run.py, the table from its logs --------------------------------

def mortal_rows(path: str, seats: dict[str, int], wanted: set[tuple]) -> dict[tuple, dict]:
    """Mortal's discard decisions for LuckyJ's seat, keyed (g, li, t) with t its n-th discard decision."""
    out = {}
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if r["kind"] != "discard" or seats.get(r["g"]) != r["s"]:
                continue
            key = (r["g"], r["li"], r["n"])
            if key not in wanted:
                continue
            p = {int(k): v for k, v in r["p"].items()}
            tiles = defaultdict(float)
            for a, v in p.items():
                if a < len(MORTAL_TILES):
                    tiles[tile_code(MORTAL_TILES[a])] += v
            out[key] = {"tiles": dict(tiles), "riichi": p.get(MORTAL_RIICHI, 0.0), "next": r.get("next_pai")}
    return out


def tenhou_dealt_in(result: list, seat: int) -> bool:
    if result[0] != "和了":
        return False
    return any(result[i + 1][1] == seat and result[i + 1][0] != seat for i in range(1, len(result), 2))


def luckyj_context(turn: dict, mortal: dict, logs: dict, seats: dict) -> dict | None:
    m = mortal.get((turn["g"], turn["li"], turn["t"]))
    if m is None:
        return None
    total = sum(m["tiles"].values()) + m["riichi"]
    log = logs[turn["g"]]
    hand, seat = log[turn["li"]], seats[turn["g"]]
    return {"mortal_safe": sum(v for b, v in m["tiles"].items() if b in set(turn["safe"])) / total,
            "mortal_cut_match": m["next"] is not None and tile_code(m["next"]) == turn["cut"],
            "south": hand[0][0] >= 4, "rank": rank(hand[1], seat),
            "prev_dealt": turn["li"] > 0 and tenhou_dealt_in(log[turn["li"] - 1][-1], seat), "date": None}


# --- summaries ----------------------------------------------------------------------------------------

def cell(turns: list[dict]) -> dict:
    n = len(turns)
    if not n:
        return {"turns": 0, "folded": None, "mortal": None, "extra": None}
    folded = sum(t["folded"] for t in turns)
    mortal = sum(t["mortal_safe"] for t in turns)
    return {"turns": n, "folded": round(100 * folded / n, 1), "mortal": round(100 * mortal / n, 1),
            "extra": round(100 * (folded - mortal) / n, 1)}


def game_sums(turns: list[dict], test) -> tuple[list[str], np.ndarray]:
    """Per game: extra folds and turns in group a, then in group b (test(turn) is True, False or None)."""
    games = sorted({t["g"] for t in turns})
    index = {g: i for i, g in enumerate(games)}
    sums = np.zeros((len(games), 4))
    for t in turns:
        side = test(t)
        if side is None:
            continue
        col = 0 if side else 2
        sums[index[t["g"]], col] += t["folded"] - t["mortal_safe"]
        sums[index[t["g"]], col + 1] += 1
    return games, sums


def contrast(sums: np.ndarray, weights: np.ndarray | None = None) -> np.ndarray:
    w = np.ones((1, len(sums))) if weights is None else weights
    tot = w @ sums
    with np.errstate(invalid="ignore", divide="ignore"):
        return 100 * (tot[:, 0] / tot[:, 1] - tot[:, 2] / tot[:, 3])


def bootstrap_se(sums: np.ndarray, rng: np.random.Generator, draws: int = BOOT) -> float:
    """Standard error of the contrast from resampling whole games."""
    weights = rng.multinomial(len(sums), np.full(len(sums), 1 / len(sums)), size=draws).astype(float)
    return float(np.nanstd(contrast(sums, weights)))


TESTS = {
    "threat_dealer": ("the other hand is the dealer's", lambda t: t["threat_dealer"]),
    "prev_dealt": ("you dealt in on the hand before", lambda t: t["prev_dealt"]),
    "south": ("the South round", lambda t: t["south"]),
    "dora": ("two or more dora in your hand, against none", lambda t: True if t["dora"] >= 2 else False if t["dora"] == 0 else None),
    "me_dealer": ("you are the dealer", lambda t: t["me_dealer"]),
}


def test_table(you: list[dict], lj: list[dict], rng: np.random.Generator) -> dict:
    out = {}
    for key, (label, test) in TESTS.items():
        entry = {"label": label}
        for who, turns in (("You", you), ("LuckyJ", lj)):
            _, sums = game_sums(turns, test)
            a = [t for t in turns if test(t) is True]
            b = [t for t in turns if test(t) is False]
            entry[who] = {"a": cell(a), "b": cell(b), "contrast": round(float(contrast(sums)[0]), 1),
                          "se": round(bootstrap_se(sums, rng), 1)}
        entry["difference"] = round(entry["You"]["contrast"] - entry["LuckyJ"]["contrast"], 1)
        entry["difference_se"] = round(float(np.hypot(entry["You"]["se"], entry["LuckyJ"]["se"])), 1)
        out[key] = entry
    return out


def dora_band(n: int) -> str:
    return "0" if n == 0 else "1" if n == 1 else "2+"


def turn_band(t: int) -> str:
    return "1-9" if t <= 9 else "10-12" if t <= 12 else "13+"


def one_shanten(turns: list[dict]) -> dict:
    ones = [t for t in turns if t["threat"] == "riichi" and t["hand"] == "one"]
    return {"by_dora": {d: cell([t for t in ones if dora_band(t["dora"]) == d]) for d in ("0", "1", "2+")},
            "two_dora_by_turn": {b: cell([t for t in ones if t["dora"] >= 2 and turn_band(t["t"]) == b])
                                 for b in ("1-9", "10-12", "13+")}}


# --- riichi or dama -----------------------------------------------------------------------------------

def first_tenpais(path: str, keep: set[str] | None = None) -> list[dict]:
    """First closed tenpai kept with riichi available (4+ tiles left, 1,000 points, a wait that is not furiten)."""
    out = []
    with open(path) as f:
        for line in f:
            r = json.loads(line)
            if not r["lj"] or not r["first"] or not r["kept"] or r["left"] < 4 or r["score"] < 1000:
                continue
            if keep is not None and r["g"] not in keep:
                continue
            opt = next((o for o in r["opts"] if o["b"] == r["cut"]), None)
            if opt is None or opt["fur"]:
                continue
            out.append({"g": r["g"], "li": r["li"], "s": r["s"], "t": r["t"], "declared": bool(r["riichi"]), "han": opt["dama_max"],
                        "live": opt["live"], "south": r["k"] >= 4})
    return out


def riichi_cell(rows: list[dict]) -> dict:
    n = len(rows)
    return {"tenpais": n, "declared": round(100 * sum(r["declared"] for r in rows) / n, 1),
            "mortal": round(100 * sum(r["mortal_riichi"] for r in rows) / n, 1)}


# --- the example turns --------------------------------------------------------------------------------

def example(turn: dict) -> dict:
    game = replay(turn["g"])
    hero, hand = game["hero"], game["hands"][turn["li"]]
    a = decision(hand, hero, turn["t"])
    marks = turn_marks(hand, hero)
    riichi_seat = declared_on = None
    discards = defaultdict(int)
    for e, mark in zip(hand["ev"], marks):
        if mark >= turn["t"] and e[1] == hero and e[0] == "d":
            break
        if e[0] == "d":
            discards[e[1]] += 1
        if e[0] == "r" and e[1] != hero:
            riichi_seat, declared_on = e[1], discards[e[1]] + 1
    scores = hand["scores"]
    top = max(a["p"], key=lambda x: x[1])
    return {"g": turn["g"], "li": turn["li"], "t": turn["t"], "round": hand["round"], "date": game["date"],
            "scores": scores, "you": scores[hero], "rank": rank(scores, hero),
            "riichi_from": {1: "shimocha", 2: "toimen", 3: "kamicha"}[(riichi_seat - hero) % 4],
            "riichi_on_discard": declared_on, "dealer": hand["kyoku"] % 4 == hero, "hand": turn["hand"], "dora": turn["dora"],
            "you_threw": a["you"], "mortal_top": top[0], "mortal_top_weight": round(100 * top[1], 1),
            "mortal_safe": round(100 * turn["mortal_safe"], 1), "result": hand["end"]}


# --- main ---------------------------------------------------------------------------------------------

def main(your_choices: str, your_cuts: str, your_tenpai: str, lj_choices: str, lj_cuts: str, lj_tenpai: str,
         lj_mortal: str, lj_manifest: str, out: str) -> None:
    rng = np.random.default_rng(SEED)
    manifest = json.loads(Path(lj_manifest).read_text())
    seats = {g["uuid"]: g["hero_seat"] for g in manifest}
    keep = set(seats)

    you = read_riichi_turns(your_choices) + read_caller_turns(your_cuts, "You")
    for turn in you:
        turn.update(your_context(turn) or {"mortal_safe": None})
    you_all = len(you)
    you = [t for t in you if t["mortal_safe"] is not None]

    lj = read_riichi_turns(lj_choices, keep) + read_caller_turns(lj_cuts, "LuckyJ")
    logs = {g["uuid"]: json.loads(Path(g["file"]).read_text())["log"] for g in manifest}
    lj_tenpai = first_tenpais(lj_tenpai, keep)
    wanted = {(t["g"], t["li"], t["t"]) for t in lj} | {(r["g"], r["li"], r["t"]) for r in lj_tenpai}
    mortal = mortal_rows(lj_mortal, seats, wanted)
    for turn in lj:
        turn.update(luckyj_context(turn, mortal, logs, seats) or {"mortal_safe": None})
    lj_all = len(lj)
    lj = [t for t in lj if t["mortal_safe"] is not None]

    result = {
        "definition": __doc__.split("\n\n")[1].strip(),
        "games": {"You": len({t["g"] for t in you}), "LuckyJ": len(seats)},
        "joined": {"You": [len(you), you_all], "LuckyJ": [len(lj), lj_all]},
        "mortal_cut_match": {who: round(100 * sum(t["mortal_cut_match"] for t in turns) / len(turns), 1)
                             for who, turns in (("You", you), ("LuckyJ", lj))},
        "overall": {}, "by_hand": {}, "tests": {}, "before_after": {},
    }
    for threat in ("riichi", "callers"):
        yt = [t for t in you if t["threat"] == threat]
        lt = [t for t in lj if t["threat"] == threat]
        result["overall"][threat] = {"You": cell(yt), "LuckyJ": cell(lt)}
        result["by_hand"][threat] = {h: {"You": cell([t for t in yt if t["hand"] == h]), "LuckyJ": cell([t for t in lt if t["hand"] == h])}
                                     for h in ("tenpai", "one", "far")}
        result["tests"][threat] = test_table(yt, lt, rng)
        _, sums = game_sums(yt, lambda t: t["date"] >= REVIEWS_BEGAN)
        result["before_after"][threat] = {
            "before": cell([t for t in yt if t["date"] < REVIEWS_BEGAN]), "since": cell([t for t in yt if t["date"] >= REVIEWS_BEGAN]),
            "contrast": round(float(contrast(sums)[0]), 1), "se": round(bootstrap_se(sums, rng), 1)}
    result["one_shanten"] = {"You": one_shanten(you), "LuckyJ": one_shanten(lj)}
    result["tenpai_two_dora"] = {who: cell([t for t in turns if t["threat"] == "riichi" and t["hand"] == "tenpai" and t["dora"] >= 2])
                                 for who, turns in (("You", you), ("LuckyJ", lj))}
    result["south_by_rank"] = {who: {str(r): {rd: cell([t for t in turns if t["threat"] == "riichi" and t["rank"] == r and t["south"] == (rd == "South")])
                                             for rd in ("East", "South")} for r in (1, 2, 3, 4)}
                               for who, turns in (("You", you), ("LuckyJ", lj))}

    your_tenpai = first_tenpais(your_tenpai)
    for r in your_tenpai:
        game = replay(r["g"])
        a = decision(game["hands"][r["li"]], game["hero"], r["t"])
        r["mortal_riichi"] = None if a is None else dict(a["p"]).get("riichi", 0.0)
        r["aligned"] = a is not None and ((a["you"] == "riichi") == r["declared"])
    your_tenpai = [r for r in your_tenpai if r["mortal_riichi"] is not None]
    for r in lj_tenpai:
        m = mortal.get((r["g"], r["li"], r["t"]))
        r["mortal_riichi"] = None if m is None else m["riichi"] / (sum(m["tiles"].values()) + m["riichi"])
    lj_tenpai = [r for r in lj_tenpai if r["mortal_riichi"] is not None]
    result["riichi_or_dama"] = {
        who: {"all": riichi_cell(rows), "East": riichi_cell([r for r in rows if not r["south"]]),
              "South": riichi_cell([r for r in rows if r["south"]])}
        for who, rows in (("You", your_tenpai), ("LuckyJ", lj_tenpai))}
    result["riichi_or_dama"]["aligned"] = round(100 * sum(r["aligned"] for r in your_tenpai) / len(your_tenpai), 1)
    # the same South test on declarations: riichi beyond Mortal's weight, South against East
    south = {}
    for who, rows in (("You", your_tenpai), ("LuckyJ", lj_tenpai)):
        _, sums = game_sums([{"g": r["g"], "folded": r["declared"], "mortal_safe": r["mortal_riichi"], "south": r["south"]} for r in rows],
                            lambda t: t["south"])
        south[who] = {"contrast": round(float(contrast(sums)[0]), 1), "se": round(bootstrap_se(sums, rng), 1)}
    south["difference"] = round(south["You"]["contrast"] - south["LuckyJ"]["contrast"], 1)
    south["difference_se"] = round(float(np.hypot(south["You"]["se"], south["LuckyJ"]["se"])), 1)
    result["riichi_or_dama"]["south_test"] = south

    by_key = {(t["g"], t["li"], t["t"]): t for t in you if t["threat"] == "riichi"}
    result["examples"] = [example(by_key[key]) for key in EXAMPLES]
    Path(out).write_text(json.dumps(result, indent=1, ensure_ascii=False))
    report(result)


def report(result: dict) -> None:
    print("games", result["games"], "joined", result["joined"], "Mortal's next tile matches the cut", result["mortal_cut_match"])
    for threat in ("riichi", "callers"):
        o = result["overall"][threat]
        print(f"== {threat}: You {o['You']}  LuckyJ {o['LuckyJ']}")
        for hand, c in result["by_hand"][threat].items():
            print(f"   {hand:6s} You {c['You']}  LuckyJ {c['LuckyJ']}")
        for key, e in result["tests"][threat].items():
            print(f"   {key:14s} You {e['You']['contrast']:+5.1f}±{e['You']['se']:.1f}  LuckyJ {e['LuckyJ']['contrast']:+5.1f}±{e['LuckyJ']['se']:.1f}"
                  f"  difference {e['difference']:+5.1f}±{e['difference_se']:.1f}   ({e['label']})")
            print(f"   {'':14s} You b {e['You']['b']} a {e['You']['a']}")
            print(f"   {'':14s} LuckyJ b {e['LuckyJ']['b']} a {e['LuckyJ']['a']}")
        b = result["before_after"][threat]
        print(f"   before/since {REVIEWS_BEGAN}: {b['before']} / {b['since']}  contrast {b['contrast']:+.1f}±{b['se']:.1f}")
    print("one-shanten by dora:", json.dumps(result["one_shanten"]))
    print("tenpai, 2+ dora:", result["tenpai_two_dora"])
    print("riichi or dama:", json.dumps(result["riichi_or_dama"]))
    print("South by rank:", json.dumps(result["south_by_rank"]))
    for e in result["examples"]:
        print("example:", {k: v for k, v in e.items() if k != "result"})


if __name__ == "__main__":
    main(*sys.argv[1:10])
