#!/usr/bin/env python3
"""What would have happened after another discard: Mortal plays out the hand and the rest of the game.

One of the hero's discards in a recorded Mahjong Soul game is replaced, and the local Mortal policy plays all four
seats from there. Each sample plays both the recorded discard and the other one:

- sample 0 finishes the hand on the real wall (the raw record's wall, from tmp/tensoul/fetch_wall.js);
- the other samples finish it on a reshuffle of the tiles nobody had seen (the rest of the live wall and the dead
  wall but its open indicators), with every hand as it really was;
- every sample then plays the rest of the game on fresh walls, the same walls for both lines.

Mortal plays by its argmax, so a line on a given wall has one answer. The game ends as a Mahjong Soul ranked south
game does: South 4 ends the game when someone has 30,000 and the dealer did not repeat (or repeated by winning as the
top), West hands are sudden death, and below zero ends it. Rank points are the Saint 3 Jade-room values read off the
hero's own results: (score - 30,000) / 1000 plus 130, 65, 0 or -250, rounded up.

usage: mortal_whatif.py run GAME_UUID ROUND TURN TILE WALL.json OUT.json [--samples N] [--procs P]
       mortal_whatif.py report OUT.json
  ROUND like S1-1 (South 1, one honba); TURN is the hero's discard number in that hand; TILE is the other discard.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "contrast"))

KINDS = [f"{n}{s}" for s in "mps" for n in range(1, 10)] + list("ESWNPFC")
TILES = [t for t in KINDS for _ in range(4)]
for _red in ("5m", "5p", "5s"):
    TILES[TILES.index(_red)] = _red + "r"
PAISHAN = {"0m": "5mr", "0p": "5pr", "0s": "5sr", "1z": "E", "2z": "S", "3z": "W", "4z": "N", "5z": "P", "6z": "F",
           "7z": "C"}
# Mahjong Soul's raw wall: the deal is tiles 0-51 and the draws start at 52. The first dora and ura indicators
# (131, 130) were checked on ten hands; the later indicators and the kan draws are assumed.
LIVE = (52, 122)
DORA_AT = (131, 129, 127, 125, 123)
URA_AT = (130, 128, 126, 124, 122)
RINSHAN_AT = (132, 133, 134, 135)
UMA = (130, 65, 0, -250)
ENGINE = None


def kind(t: str) -> int:
    return KINDS.index(t[:2] if t.endswith("r") else t)


def rank_points(score: int, place: int) -> int:
    return math.ceil((score - 30000) / 1000 + UMA[place])


def to136(tiles, used):
    """mjai tiles to the mahjong library's ids; copy 0 of each five is the red one."""
    ids = []
    for t in tiles:
        k = kind(t)
        if t.endswith("r"):
            ids.append(4 * k)
            continue
        start = 1 if k < 27 and t[0] == "5" else 0
        ids.append(4 * k + start + used[k])
        used[k] += 1
    return ids


def tenpai(hand) -> bool:
    from mahjong.shanten import Shanten

    counts = [0] * 34
    for t in hand:
        counts[kind(t)] += 1
    closed = len(hand) == 13
    return Shanten().calculate_shanten(counts, use_chiitoitsu=closed, use_kokushi=closed) == 0


_CALC = None


def hand_value(hand13, win, melds, seat, oya, bakaze, doras, uras, **flags):
    """(han, fu, cost dict, yaku names) of a win; the cost leaves out honba and sticks."""
    global _CALC
    from mahjong.hand_calculating.hand import HandCalculator
    from mahjong.hand_calculating.hand_config import HandConfig, OptionalRules
    from mahjong.meld import Meld

    if _CALC is None:
        _CALC = HandCalculator()
    used = Counter()
    mo = []
    for m in melds:
        ids = sorted(to136(m["tiles"], used))
        mtype = {"chi": Meld.CHI, "pon": Meld.PON}.get(m["type"], Meld.KAN)
        mo.append(Meld(meld_type=mtype, tiles=ids, opened=m["type"] != "ankan"))
    hid = to136(list(hand13) + [win], used)
    cfg = HandConfig(player_wind=27 + (seat - oya) % 4, round_wind=27 + "ESWN".index(bakaze),
                     options=OptionalRules(has_open_tanyao=True, has_aka_dora=True), **flags)
    res = _CALC.estimate_hand_value(hid + [t for m in mo for t in m.tiles], hid[-1], melds=mo,
                                    dora_indicators=[4 * kind(t) + 3 for t in doras],
                                    ura_dora_indicators=[4 * kind(t) + 3 for t in uras] if uras else None, config=cfg)
    if res.error:
        raise ValueError(f"no score for {hand13} + {win} {melds}: {res.error}")
    return res.han, res.fu, res.cost, [str(y) for y in res.yaku]


class Hand:
    """One hand, run as an mjai server for four libriichi bots."""

    def __init__(self, bots, bakaze, kyoku, honba, kyotaku, scores, haipai, live, dora, ura, rinshan):
        self.bots = bots
        self.bakaze, self.kyoku, self.oya = bakaze, kyoku, kyoku - 1
        self.honba, self.kyotaku, self.scores = honba, kyotaku, list(scores)
        self.haipai = [list(h) for h in haipai]
        self.hands = [list(h) for h in haipai]
        self.melds = [[] for _ in range(4)]
        self.live, self.dora, self.ura, self.rinshan = list(live), list(dora), list(ura), list(rinshan)
        self.draws = self.kans = 0
        self.ndora = 1
        self.kan_pending = self.rinshan_turn = False
        self.kan_by = []
        self.riichi = [False] * 4
        self.double = [False] * 4
        self.ippatsu = [False] * 4
        self.declared_first = [False] * 4
        self.discards = [[] for _ in range(4)]
        self.called = False
        self.log = []

    def left(self) -> int:
        return len(self.live) - self.draws - self.kans

    # --- events
    def apply(self, ev):
        typ, a = ev["type"], ev.get("actor")
        if typ == "tsumo":
            self.rinshan_turn = self.kan_pending
            if self.kan_pending:
                self.kans += 1
                self.kan_pending = False
            else:
                self.draws += 1
            self.hands[a].append(ev["pai"])
            self.last_draw = (a, ev["pai"])
        elif typ == "dahai":
            self.hands[a].remove(ev["pai"])
            self.discards[a].append(ev["pai"])
            self.ippatsu[a] = False
            self.rinshan_turn = False
        elif typ in ("chi", "pon", "daiminkan", "ankan"):
            for t in ev["consumed"]:
                self.hands[a].remove(t)
            tiles = list(ev["consumed"]) + ([ev["pai"]] if "pai" in ev else [])
            self.melds[a].append({"type": typ, "tiles": tiles})
            self.ippatsu = [False] * 4
            self.called = True
            if typ in ("daiminkan", "ankan"):
                self.kan_pending = True
                self.kan_by.append(a)
        elif typ == "kakan":
            self.hands[a].remove(ev["pai"])
            m = next(m for m in self.melds[a] if m["type"] == "pon" and kind(m["tiles"][0]) == kind(ev["pai"]))
            m["type"] = "kakan"
            m["tiles"].append(ev["pai"])
            self.ippatsu = [False] * 4
            self.kan_pending = True
            self.kan_by.append(a)
        elif typ == "dora":
            self.ndora += 1
        elif typ == "reach":
            self.declared_first[a] = not self.discards[a] and not self.called
        elif typ == "reach_accepted":
            self.riichi[a] = True
            self.double[a] = self.declared_first[a]
            self.ippatsu[a] = True
            self.scores[a] -= 1000
            self.kyotaku += 1

    def emit(self, ev, act=True):
        """Apply an event, show it to every bot, and return the actions they answer with."""
        self.apply(ev)
        self.log.append(ev)
        out = {}
        for s, bot in enumerate(self.bots):
            seen = ev
            if ev["type"] == "start_kyoku":
                seen = dict(ev, tehais=[h if i == s else ["?"] * 13 for i, h in enumerate(ev["tehais"])])
            elif ev["type"] == "tsumo" and ev["actor"] != s:
                seen = dict(ev, pai="?")
            raw = bot.react(json.dumps(seen), can_act=act)
            if raw:
                r = json.loads(raw)
                if r.get("type") not in (None, "none"):
                    r.pop("meta", None)
                    out[s] = r
        return out

    def start(self, act=False):
        return self.emit({"type": "start_kyoku", "bakaze": self.bakaze, "dora_marker": self.dora[0],
                          "kyoku": self.kyoku, "honba": self.honba, "kyotaku": self.kyotaku, "oya": self.oya,
                          "scores": list(self.scores), "tehais": self.haipai}, act=act)

    # --- play
    def play(self, actor=None, act=None):
        """Play until the hand ends; with ``act``, ``actor`` has drawn and plays ``act`` first."""
        if actor is None:
            self.start()
            actor = self.oya
        while True:
            if act is None:
                if self.left() == 0:
                    return self.exhaustive()
                act = self.emit({"type": "tsumo", "actor": actor, "pai": self.live[self.draws]}).get(actor)
            out = self.turn(actor, act)
            if isinstance(out, dict):
                return out
            actor, act = out, None

    def kan_draw(self, actor, dora_after):
        act = self.emit({"type": "tsumo", "actor": actor, "pai": self.rinshan[self.kans]}).get(actor)
        if dora_after:
            act = self.emit({"type": "dora", "dora_marker": self.dora[self.ndora]}).get(actor) or act
        return act

    def turn(self, actor, act):
        """Resolve one seat's action and what follows it; returns the next seat to draw or the hand's result."""
        while True:
            typ = act["type"]
            if typ == "hora":
                return self.win([actor], actor, self.last_draw[1], tsumo=True, rinshan=self.rinshan_turn)
            if typ == "ryukyoku":
                return self.abort("nine terminals")
            if typ == "ankan":
                self.emit({"type": "ankan", "actor": actor, "consumed": act["consumed"]})
                self.emit({"type": "dora", "dora_marker": self.dora[self.ndora]})
                act = self.kan_draw(actor, dora_after=False)
                continue
            if typ == "kakan":
                resp = self.emit({"type": "kakan", "actor": actor, "pai": act["pai"], "consumed": act["consumed"]})
                rons = [s for s, r in resp.items() if s != actor and r["type"] == "hora"]
                if rons:
                    return self.win(rons, actor, act["pai"], chankan=True)
                act = self.kan_draw(actor, dora_after=True)
                continue
            declared = typ == "reach"
            if declared:
                act = self.emit({"type": "reach", "actor": actor})[actor]
            pai = act["pai"]
            resp = self.emit({"type": "dahai", "actor": actor, "pai": pai, "tsumogiri": act.get("tsumogiri", False)})
            rons = [s for s, r in resp.items() if s != actor and r["type"] == "hora"]
            if len(rons) == 3:
                return self.abort("three rons")
            if rons:
                return self.win(rons, actor, pai, houtei=self.left() == 0)
            if declared:
                self.emit({"type": "reach_accepted", "actor": actor})
                if all(self.riichi):
                    return self.abort("four riichi")
            firsts = [d[0] for d in self.discards if len(d) == 1]
            if not self.called and len(firsts) == 4 and len(set(firsts)) == 1 and firsts[0] in "ESWN":
                return self.abort("four winds")
            if self.kans == 4 and len(set(self.kan_by)) > 1:
                return self.abort("four kans")
            calls = [(s, r) for s, r in resp.items() if r["type"] in ("pon", "daiminkan")] or \
                    [(s, r) for s, r in resp.items() if r["type"] == "chi"]
            if not calls:
                if self.left() == 0:
                    return self.exhaustive()
                return (actor + 1) % 4
            s, r = calls[0]
            ev = {"type": r["type"], "actor": s, "target": actor, "pai": pai, "consumed": r["consumed"]}
            got = self.emit(ev)
            actor = s
            act = self.kan_draw(s, dora_after=True) if r["type"] == "daiminkan" else got[s]

    # --- results
    def win(self, winners, loser, pai, tsumo=False, rinshan=False, chankan=False, houtei=False):
        winners = sorted(winners, key=lambda s: (s - loser) % 4 or 4)
        deltas = [0] * 4
        wins = []
        for i, w in enumerate(winners):
            hand = list(self.hands[w])
            if tsumo:
                hand.remove(pai)
            uras = self.ura[:self.ndora] if self.riichi[w] else []
            han, fu, cost, yaku = hand_value(
                hand, pai, self.melds[w], w, self.oya, self.bakaze, self.dora[:self.ndora], uras,
                is_tsumo=tsumo, is_riichi=self.riichi[w], is_daburu_riichi=self.double[w], is_ippatsu=self.ippatsu[w],
                is_rinshan=rinshan, is_chankan=chankan, is_haitei=tsumo and not rinshan and self.left() == 0,
                is_houtei=houtei)
            bonus = self.honba if i == 0 else 0
            if tsumo:
                for s in range(4):
                    if s != w:
                        pay = (cost["main"] if s == self.oya or w == self.oya else cost["additional"]) + 100 * bonus
                        deltas[s] -= pay
                        deltas[w] += pay
            else:
                pay = cost["main"] + 300 * bonus
                deltas[loser] -= pay
                deltas[w] += pay
            wins.append({"winner": w, "han": han, "fu": fu, "yaku": yaku, "points": cost["main"] if not tsumo else
                         cost["main"] + 2 * cost["additional"] if w != self.oya else 3 * cost["main"]})
        deltas[winners[0]] += 1000 * self.kyotaku
        for w in winners:
            self.emit({"type": "hora", "actor": w, "target": loser, "deltas": deltas}, act=False)
        self.emit({"type": "end_kyoku"}, act=False)
        return {"kind": "tsumo" if tsumo else "ron", "winners": winners, "loser": loser, "pai": pai, "wins": wins,
                "deltas": deltas, "sticks": self.kyotaku, "renchan": self.oya in winners, "scores": self.scores}

    def exhaustive(self):
        ready = [tenpai(h) for h in self.hands]
        n = sum(ready)
        deltas = [0] * 4
        if 0 < n < 4:
            deltas = [3000 // n if r else -3000 // (4 - n) for r in ready]
        self.emit({"type": "ryukyoku", "deltas": deltas}, act=False)
        self.emit({"type": "end_kyoku"}, act=False)
        return {"kind": "draw", "tenpai": ready, "deltas": deltas, "renchan": ready[self.oya], "scores": self.scores}

    def abort(self, why):
        self.emit({"type": "ryukyoku", "deltas": [0] * 4}, act=False)
        self.emit({"type": "end_kyoku"}, act=False)
        return {"kind": "abort", "why": why, "deltas": [0] * 4, "renchan": True, "scores": self.scores}


def random_wall(rng):
    w = list(TILES)
    rng.shuffle(w)
    return [w[13 * s:13 * s + 13] for s in range(4)], w[52:122], w[122:127], w[127:132], w[132:136]


def settle(state, res):
    """Score a finished hand and move the game on; returns True when the game is over."""
    k = state["k"]
    oya = k % 4
    scores = [s + d for s, d in zip(res["scores"], res["deltas"])]
    state["scores"] = scores
    won = res["kind"] in ("ron", "tsumo")
    state["kyotaku"] = 0 if won else res.get("kyotaku", state["kyotaku"])
    top = max(scores)
    over = min(scores) < 0
    if k >= 7 and not over:
        if res["renchan"]:
            over = won and scores[oya] == top and scores.count(top) == 1 and top >= 30000
        else:
            over = top >= 30000 or k == 11
    if res["renchan"]:
        state["honba"] += 1
    else:
        state["honba"] = 0 if won else state["honba"] + 1
        state["k"] = k + 1
    state["hands"] += 1
    return over


def finish(state):
    scores = list(state["scores"])
    order = sorted(range(4), key=lambda s: (-scores[s], s))
    scores[order[0]] += 1000 * state["kyotaku"]
    return scores, [order.index(s) for s in range(4)]


def play_game(bots, state, rng):
    while True:
        k = state["k"]
        haipai, live, dora, ura, rinshan = random_wall(rng)
        hand = Hand(bots, "ESWN"[k // 4], k % 4 + 1, state["honba"], state["kyotaku"], state["scores"], haipai, live,
                    dora, ura, rinshan)
        res = hand.play()
        res["kyotaku"] = hand.kyotaku
        if settle(state, res):
            return finish(state)


# --- the recorded hand
def load_case(uuid, round_name, turn, wall_file):
    import tenhou6_to_mjai as t2m

    g = next(x for x in json.load(open(HERE.parent / "data/self_games/majsoul/index.json"))
             if x["uuid"].startswith(uuid))
    events = t2m.convert(json.load(open(HERE.parent / g["file"])))
    bakaze, rest = round_name[0], round_name[1:]
    kyoku, honba = (int(x) for x in rest.split("-"))
    starts = [i for i, e in enumerate(events) if e["type"] == "start_kyoku"] + [len(events)]
    a, b = next((a, b) for a, b in zip(starts, starts[1:])
                if (events[a]["bakaze"], events[a]["kyoku"], events[a]["honba"]) == (bakaze, kyoku, honba))
    hero = g["hero_seat"]
    hand_events = events[a:b]
    cuts = [i for i, e in enumerate(hand_events) if e["type"] == "dahai" and e["actor"] == hero]
    cut = cuts[turn - 1]
    chang = "ESW".index(bakaze)
    rnd = next(r for r in json.load(open(wall_file))["rounds"]
               if (r["chang"], r["ju"] + 1, r["ben"]) == (chang, kyoku, honba))
    s = rnd["paishan"]
    wall = [PAISHAN.get(s[i:i + 2], s[i:i + 2]) for i in range(0, len(s), 2)]
    return {"game": g, "hero": hero, "events": hand_events, "cut": cut, "wall": wall,
            "k": 4 * chang + kyoku - 1, "names": g["names"]}


def recorded_hand(case, bots, shuffle_seed=None):
    """Replay the hand up to the hero's discard; return the Hand and the hero's draw response."""
    start, wall = case["events"][0], list(case["wall"])
    dora = [wall[i] for i in DORA_AT]
    ura = [wall[i] for i in URA_AT]
    rinshan = [wall[i] for i in RINSHAN_AT]
    hand = Hand(bots, start["bakaze"], start["kyoku"], start["honba"], start["kyotaku"], start["scores"],
                start["tehais"], wall[LIVE[0]:LIVE[1]], dora, ura, rinshan)
    hand.start()
    prefix = case["events"][1:case["cut"]]
    for i, ev in enumerate(prefix):
        if ev["type"] == "tsumo" and not hand.kan_pending:
            assert ev["pai"] == hand.live[hand.draws], (ev, hand.live[hand.draws])
        last = i == len(prefix) - 1
        got = hand.emit(ev, act=last)
    if shuffle_seed is not None:
        # everything nobody has seen: the rest of the live wall and the dead wall but its open indicators
        rng = random.Random(shuffle_seed)
        unseen = hand.live[hand.draws:] + hand.dora[hand.ndora:] + hand.ura + hand.rinshan
        rng.shuffle(unseen)
        n_live = len(hand.live) - hand.draws
        hand.live[hand.draws:] = unseen[:n_live]
        rest = unseen[n_live:]
        k = 5 - hand.ndora
        hand.dora[hand.ndora:], hand.ura, hand.rinshan = rest[:k], rest[k:k + 5], rest[k + 5:]
    return hand, got.get(case["hero"])


def sample(job):
    import traceback

    try:
        return play_sample(*job)
    except Exception:
        return {"i": job[1], "error": traceback.format_exc()}


def play_sample(case, i, tiles):
    from libriichi.mjai import Bot

    out = {"i": i}
    for tile in tiles:
        bots = [Bot(ENGINE, s) for s in range(4)]
        for b in bots:
            b.react(json.dumps({"type": "start_game", "names": case["names"], "kyoku_first": 0, "aka_flag": True}),
                    can_act=False)
        hand, mortal = recorded_hand(case, bots, shuffle_seed=None if i == 0 else 1000 + i)
        hero = case["hero"]
        drawn = hand.last_draw[1] if hand.last_draw[0] == hero else None
        res = hand.play(hero, {"type": "dahai", "pai": tile, "tsumogiri": tile == drawn})
        res["kyotaku"] = hand.kyotaku
        line = {"hand": {k: v for k, v in res.items() if k != "scores"}, "mortal": mortal.get("pai")}
        if i == 0:
            line["log"] = hand.log
        state = {"k": case["k"], "honba": hand.honba, "kyotaku": hand.kyotaku, "scores": list(res["scores"]),
                 "hands": 0}
        if settle(state, res):
            scores, places = finish(state)
        else:
            scores, places = play_game(bots, state, random.Random(i))
        line.update(after_hand=[s + d for s, d in zip(res["scores"], res["deltas"])], scores=scores, places=places,
                    hands=state["hands"])
        out[tile] = line
    return out


def init():
    global ENGINE
    import mortal_run

    mortal_run.init()
    ENGINE = mortal_run.ENGINE


def run(argv):
    uuid, round_name, turn, tile, wall_file, out = argv[:6]
    opts = dict(zip(argv[6::2], argv[7::2]))
    n, procs = int(opts.get("--samples", 200)), int(opts.get("--procs", 12))
    case = load_case(uuid, round_name, int(turn), wall_file)
    played = case["events"][case["cut"]]["pai"]
    tiles = [played, tile]
    jobs = [(case, i, tiles) for i in range(n)]
    rows = []
    with Pool(procs, initializer=init) as pool:
        for r in pool.imap_unordered(sample, jobs):
            rows.append(r)
            if len(rows) % 20 == 0:
                print(f"{len(rows)}/{n}", flush=True)
    errors = [r for r in rows if "error" in r]
    for r in errors[:3]:
        print(r["error"])
    rows = sorted((r for r in rows if "error" not in r), key=lambda r: r["i"])
    data = {"game": case["game"]["uuid"], "round": round_name, "turn": int(turn), "hero": case["hero"],
            "names": case["names"], "played": played, "other": tile, "errors": len(errors), "samples": rows}
    Path(out + ".tmp").write_text(json.dumps(data, ensure_ascii=False))
    os.replace(out + ".tmp", out)
    report(out)


def report(path):
    d = json.loads(Path(path).read_text())
    hero, rows = d["hero"], d["samples"]
    print(f"== {d['game']} {d['round']} discard {d['turn']}: played {d['played']}, other {d['other']}; "
          f"{len(rows)} samples (sample 0 = the real wall), {d.get('errors', 0)} failed")
    for tile in (d["played"], d["other"]):
        r0 = rows[0][tile]
        h = r0["hand"]
        print(f"-- {tile}: real wall: {h['kind']} winners {h.get('winners')} loser {h.get('loser')} "
              f"deltas {h['deltas']} {[(w['han'], w['fu'], w['yaku']) for w in h.get('wins', [])]}")
        print(f"   after the hand {r0['after_hand']}  final {r0['scores']}  hero place {r0['places'][hero] + 1}")
        hs = [r[tile]["hand"] for r in rows]
        kinds = Counter()
        for h in hs:
            if h["kind"] in ("ron", "tsumo"):
                if hero in h["winners"]:
                    kinds["hero wins"] += 1
                elif h["kind"] == "ron" and h["loser"] == hero:
                    kinds["hero deals in"] += 1
                elif h["kind"] == "tsumo":
                    kinds["other tsumo"] += 1
                else:
                    kinds["other ron"] += 1
            else:
                kinds[h["kind"]] += 1
        n = len(rows)
        print("   hand: " + ", ".join(f"{k} {100 * v / n:.0f}%" for k, v in kinds.most_common())
              + f"; hero's change {sum(h['deltas'][hero] for h in hs) / n:+.0f}")
        places = Counter(r[tile]["places"][hero] for r in rows)
        pts = [rank_points(r[tile]["scores"][hero], r[tile]["places"][hero]) for r in rows]
        mean = sum(pts) / n
        sd = (sum((p - mean) ** 2 for p in pts) / (n - 1)) ** 0.5
        print("   places " + " / ".join(f"{100 * places[p] / n:.0f}%" for p in range(4))
              + f"; rank points {mean:+.1f} (± {sd / n ** 0.5:.1f}); final score "
              f"{sum(r[tile]['scores'][hero] for r in rows) / n:,.0f}")
    diff = [rank_points(r[d["other"]]["scores"][hero], r[d["other"]]["places"][hero])
            - rank_points(r[d["played"]]["scores"][hero], r[d["played"]]["places"][hero]) for r in rows]
    m = sum(diff) / len(diff)
    sd = (sum((x - m) ** 2 for x in diff) / (len(diff) - 1)) ** 0.5
    print(f"-- {d['other']} minus {d['played']}: {m:+.1f} rank points per game (± {sd / len(diff) ** 0.5:.1f}, "
          "paired by wall)")


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2:])
    else:
        report(sys.argv[2])
