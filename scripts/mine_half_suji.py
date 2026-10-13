#!/usr/bin/env python3
"""Guide chapter 40: how LuckyJ reads a half-suji against a riichi.

Every discard of a live number tile (half suji, live 2-3-7-8, live 4-5-6, live terminal) into a lone riichi, by any
player at the user's tables and LuckyJ's, is recorded with what the discarder could see about that tile and whether
it was one of the riichi's winning tiles (from the declarer's real hand):

- the riichi player's own discards before the declaration at each distance from the tile (one to three ranks, either
  side), early (first six) or late, from the hand or straight from the draw;
- the walls: copies visible of the tiles one and two ranks away, and of the tile itself;
- which suji partner is covered (genbutsu, the riichi's furiten included) and whether only other players' passes cover
  it, the declaration tile's distance, the dora's distance, the turns since the declaration, the riichi's discards in
  the suit, and the tile's rank;
- the context: whether the throw kept the player tenpai, whether a genbutsu was in hand, and for a half-suji thrown,
  every other half-suji the player held then, described the same way (the choice the player made).

``report`` gives, for LuckyJ, the human players at its tables and at the user's, and the user: how often their
half-suji hit, by context (kept tenpai, folding with or without a genbutsu in hand); in the throws where the player
held another half-suji, how often the one thrown and the ones kept hit, and what a random pick and the chapter's
checklist would have hit; the hit rates of the cues the checklist uses, over every half-suji thrown or held; how often
LuckyJ and the humans followed those cues when their two half-suji differed on one; and a danger model (logistic,
ridge) over every live number tile, checked on games held out, asked whether it sees LuckyJ's half-suji as safer.

usage: mine_half_suji.py compute YOUR_MANIFEST.json ROWS_OUT.json
       mine_half_suji.py report ROWS.json OUT.json
"""

from __future__ import annotations

import json
import math
import os
import sys
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
NUMBER = ("half suji", "live 2-3-7-8", "live 4-5-6", "live terminal")
OFFSETS = (-3, -2, -1, 1, 2, 3)
EARLY = 6
RIDGE = 2.0


def game_rows(g: dict) -> list[dict]:
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import meld_snapshots, safety, visible_counter
    from tenhou_replay import base

    hero, rows = g["hero_seat"], []
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        events = game["events"]
        indicators = game["dora_indicators"][:1]
        dora = {base(ws.dora_from_indicator(x)) for x in indicators}
        waits, decl, rturn = {}, {}, {}
        for e in events:
            if e["riichi"]:
                q = e["seat"]
                waits[q] = {base(w) for w in tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])}
                decl[q], rturn[q] = base(e["tile"]), e["turn"]
        for e in events:
            s = e["seat"]
            reached = [q for q in range(4) if q != s and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            if len(reached) != 1 or e["riichi_seats"][s] is not None or e.get("tile") is None or not waits.get(reached[0]):
                continue
            q = reached[0]
            snap = meld_snapshots(game, e["index"] - 1)
            snap[s] = e["melds"]
            visible = visible_counter(e["hand_before"], e, game["players"], snap, indicators)
            r = e["riichi_seats"][q]
            passed = {base(x["tile"]) for x in events[r + 1: e["index"]] if x.get("tile") is not None}
            ref = {base(x) for x in e["rivers"][q]} | passed
            own = [x for x in events if x["seat"] == q and x["index"] <= r and x.get("tile") is not None]  # the declaration tile too
            own_bases = {base(x["tile"]) for x in own}

            def describe(tile: int) -> dict | None:
                t = base(tile)
                if t >= 40:
                    return None
                seen = visible.copy()
                seen[t] -= 1
                label = safety(tile, q, e, game, seen)
                if label not in NUMBER:
                    return None
                suit, n = divmod(t, 10)
                river = {}
                for k, x in enumerate(own):
                    b = base(x["tile"])
                    if b // 10 == suit and b < 40 and 1 <= abs(b - t) <= 3:
                        key = f"{b - t:+d}|{'early' if k < EARLY else 'late'}|{'draw' if x.get('tsumogiri') else 'hand'}"
                        river[key] = 1
                d = decl[q]
                cover = [t + o for o in (-3, 3) if (t + o) in ref]
                return {
                    "label": label, "n": n, "low_ref": (t - 3) in ref, "high_ref": (t + 3) in ref,
                    "covered_by_others_only": bool(cover) and not any(c in own_bases for c in cover),
                    "seen": {f"{o:+d}": seen[t + o] for o in (-2, -1, 1, 2) if 1 <= n + o <= 9}, "tile_seen": seen[t],
                    "river": river, "decl": (d - t) if d // 10 == suit and d < 40 and abs(d - t) <= 3 else None,
                    "dora": min((abs(x - t) for x in dora if x // 10 == suit and x < 40), default=None),
                    "since": e["turn"] - rturn[q], "riichi_turn": rturn[q],
                    "suit_discards": sum(1 for x in own if base(x["tile"]) // 10 == suit and base(x["tile"]) < 40),
                    "hit": t in waits[q], "base": t,
                }

            thrown = describe(e["tile"])
            if thrown is None:
                continue
            tenpai_after = ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) == 0
            had_genbutsu = any(base(x) in ref for x in e["hand_before"])
            row = dict(thrown, game=g["uuid"], round=game["round_name"], turn=e["turn"], who="hero" if s == hero else "other",
                       tenpai_after=tenpai_after, had_genbutsu=had_genbutsu)
            if thrown["label"] == "half suji":
                # the other half-suji the player held: the choice set
                kept = []
                for x in {base(y): y for y in e["hand_before"]}.values():
                    if base(x) == thrown["base"]:
                        continue
                    k = describe(x)
                    if k and k["label"] == "half suji":
                        kept.append(k)
                row["kept_half_suji"] = kept
            rows.append(row)
    return rows


def compute(your_manifest: str, out: str) -> None:
    os.chdir(ROOT)
    you = json.load(open(your_manifest))
    lj = json.loads(LJ_MANIFEST.read_text(encoding="utf-8"))
    with Pool(12) as pool:
        jade = [dict(r, table="jade") for c in pool.map(game_rows, you, chunksize=2) for r in c]
        tenhou = [dict(r, table="tenhou") for c in pool.map(game_rows, lj, chunksize=4) for r in c]
    Path(out).write_text(json.dumps({"rows": jade + tenhou}))
    print(f"wrote {out}: {len(jade)} discards at your tables, {len(tenhou)} at LuckyJ's")


# --- the model ---------------------------------------------------------------------------------------------

def mirror(r: dict) -> dict:
    """Describe the tile with its covered side (if any) as 'low', so 4-with-1 and 6-with-9 read alike."""
    flip = r["high_ref"] and not r["low_ref"]
    sign = -1 if flip else 1
    river = {}
    for key in r["river"]:
        off, when, how = key.split("|")
        river[f"{sign * int(off):+d}|{when}|{how}"] = 1
    seen = {f"{sign * int(k):+d}": v for k, v in r["seen"].items()}
    decl = None if r["decl"] is None else sign * r["decl"]
    n = 10 - r["n"] if flip else r["n"]
    return dict(r, river=river, seen=seen, decl=decl, n=n)


def features(r: dict) -> dict[str, float]:
    m = mirror(r)
    f = {f"label: {m['label']}": 1.0, f"rank {m['n']}": 1.0}
    for o in OFFSETS:
        for when in ("early", "late"):
            for how in ("hand", "draw"):
                key = f"{o:+d}|{when}|{how}"
                if key in m["river"]:
                    f[f"riichi threw the tile {o:+d} away, {when}, from the {how}"] = 1.0
    for o in ("-2", "-1", "+1", "+2"):
        v = m["seen"].get(o)
        if v is not None:
            f[f"copies visible {o} away: 3+"] = float(v >= 3)
            f[f"copies visible {o} away"] = v / 4
    f["copies of the tile visible"] = m["tile_seen"] / 3
    if m["decl"] is not None:
        f[f"declaration tile {m['decl']:+d} away"] = 1.0
    if m["dora"] is not None and m["dora"] <= 2:
        f[f"dora {m['dora']} away"] = 1.0
    f["turns since the riichi (per 5)"] = min(m["since"], 15) / 5
    f["riichi declared late (turn 12+)"] = float(m["riichi_turn"] >= 12)
    f["riichi's discards in the suit (per 3)"] = min(m["suit_discards"], 9) / 3
    return f


def design(rows: list[dict], names: list[str]) -> np.ndarray:
    index = {k: i for i, k in enumerate(names)}
    x = np.zeros((len(rows), len(names) + 1))
    x[:, 0] = 1.0
    for i, r in enumerate(rows):
        for k, v in features(r).items():
            if k in index:
                x[i, index[k] + 1] = v
    return x


def fit(x: np.ndarray, y: np.ndarray, ridge: float = RIDGE) -> np.ndarray:
    b = np.zeros(x.shape[1])
    pen = ridge * np.eye(len(b))
    pen[0, 0] = 0
    for _ in range(60):
        mu = 1 / (1 + np.exp(-(x @ b)))
        step = np.linalg.solve((x.T * (mu * (1 - mu))) @ x + pen, x.T @ (y - mu) - pen @ b)
        b += step
        if np.abs(step).max() < 1e-8:
            break
    return b


def held_out(row: dict) -> bool:
    return zlib.crc32(row["game"].encode()) % 5 == 0


def checklist(c: dict) -> int:
    """The chapter's checklist: lower is safer."""
    m = mirror(c)
    wall = max(m["seen"].get("+1", 0), m["seen"].get("+2", 0))
    open_side = any(int(k.split("|")[0]) > 0 for k in m["river"])
    trap = any(int(k.split("|")[0]) == -3 and k.split("|")[1:] == ["late", "hand"] for k in m["river"])
    dora = m["dora"] is not None and 1 <= m["dora"] <= 2
    return -2 * (wall >= 4) - 1 * (wall == 3) - 1 * open_side + 1 * trap + 1 * dora


def ryanmen_combos(c: dict) -> int:
    m = mirror(c)
    return max(0, 4 - m["seen"].get("+1", 4)) * max(0, 4 - m["seen"].get("+2", 4))


def pct(k: float, n: int) -> float | None:
    return round(100 * k / n, 1) if n else None


def report(rows_path: str, out: str) -> None:
    rows = json.load(open(rows_path))["rows"]
    groups = {"luckyj": lambda r: r["table"] == "tenhou" and r["who"] == "hero",
              "tokujou_humans": lambda r: r["table"] == "tenhou" and r["who"] == "other",
              "jade_players": lambda r: r["table"] == "jade" and r["who"] == "other",
              "you": lambda r: r["table"] == "jade" and r["who"] == "hero"}
    half = {g: [r for r in rows if keep(r) and r["label"] == "half suji"] for g, keep in groups.items()}
    humans = half["tokujou_humans"] + half["jade_players"] + half["you"]

    # 1. how often each side's half-suji hit, in each context
    sides = {}
    for g, hs in half.items():
        ctx = {"kept tenpai": [r for r in hs if r["tenpai_after"]],
               "folding, genbutsu in hand": [r for r in hs if not r["tenpai_after"] and r["had_genbutsu"]],
               "folding, no genbutsu in hand": [r for r in hs if not r["tenpai_after"] and not r["had_genbutsu"]]}
        sets = [[r] + r["kept_half_suji"] for r in hs if r.get("kept_half_suji")]
        kept = [k for s in sets for k in s[1:]]
        pick = []
        for s in sets:
            sc = [checklist(c) for c in s]
            chosen = [c for c, v in zip(s, sc) if v == min(sc)]
            pick.append(sum(c["hit"] for c in chosen) / len(chosen))
        sides[g] = {"throws": len(hs), "hit": pct(sum(r["hit"] for r in hs), len(hs)),
                    "contexts": {k: [len(v), pct(sum(r["hit"] for r in v), len(v))] for k, v in ctx.items()},
                    "choices": {"sets": len(sets), "thrown_hit": pct(sum(s[0]["hit"] for s in sets), len(sets)),
                                "kept": len(kept), "kept_hit": pct(sum(k["hit"] for k in kept), len(kept)),
                                "random_pick": pct(sum(sum(c["hit"] for c in s) / len(s) for s in sets), len(sets)),
                                "checklist_pick": pct(sum(pick), len(pick))}}
    human_sets = sum(sides[g]["choices"]["sets"] for g in ("tokujou_humans", "jade_players", "you"))
    pooled = lambda key: round(sum(sides[g]["choices"][key] * sides[g]["choices"]["sets"] for g in ("tokujou_humans", "jade_players", "you")) / human_sets, 1)
    humans_pooled = {"sets": human_sets, "thrown_hit": pooled("thrown_hit"), "checklist_pick": pooled("checklist_pick"),
                     "random_pick": pooled("random_pick")}

    # 2. the cues: how often a half-suji with each hit, over every half-suji thrown or held in a choice
    candidates = [c for r in rows if r["label"] == "half suji" for c in [r] + r.get("kept_half_suji", [])]

    def rate(keep) -> list:
        s = [c for c in candidates if keep(c)]
        return [len(s), pct(sum(c["hit"] for c in s), len(s))]

    m = mirror
    cues = {
        "every half-suji": rate(lambda c: True),
        "open two-sided wait impossible (no-chance)": rate(lambda c: ryanmen_combos(c) == 0),
        "a wall on the open side (3+ copies of a tile it needs)": rate(lambda c: max(m(c)["seen"].get("+1", 0), m(c)["seen"].get("+2", 0)) >= 3),
        "no wall on the open side": rate(lambda c: max(m(c)["seen"].get("+1", 0), m(c)["seen"].get("+2", 0)) < 3),
        "riichi threw a tile 1-3 away on the open side, early": rate(lambda c: any(int(k.split("|")[0]) > 0 and k.split("|")[1] == "early" for k in m(c)["river"])),
        "riichi threw a tile 1-3 away on the open side, late": rate(lambda c: any(int(k.split("|")[0]) > 0 and k.split("|")[1] == "late" for k in m(c)["river"])),
        "nothing thrown 1-3 away on the open side": rate(lambda c: not any(int(k.split("|")[0]) > 0 for k in m(c)["river"])),
        "covering tile thrown late from the hand": rate(lambda c: any(int(k.split("|")[0]) == -3 and k.split("|")[1:] == ["late", "hand"] for k in m(c)["river"])),
        "dora 1-2 away": rate(lambda c: m(c)["dora"] is not None and 1 <= m(c)["dora"] <= 2),
    }

    # 3. does LuckyJ follow those cues more than humans? when its thrown and a kept half-suji differ on one
    def prefer(keep_group, cue) -> list:
        diff = took = 0
        for r in rows:
            if not keep_group(r) or r["label"] != "half suji" or not r.get("kept_half_suji"):
                continue
            for k in r["kept_half_suji"]:
                a, b = cue(r), cue(k)
                if a != b:
                    diff += 1
                    took += a
        return [diff, pct(took, diff)]

    cue_fns = {
        "a wall on the open side": lambda c: max(m(c)["seen"].get("+1", 0), m(c)["seen"].get("+2", 0)) >= 3,
        "an early discard on the open side": lambda c: any(int(k.split("|")[0]) > 0 and k.split("|")[1] == "early" for k in m(c)["river"]),
        "fewer open two-sided combinations": None,
    }
    preferences = {}
    for name, fn in cue_fns.items():
        if fn is None:
            continue
        preferences[name] = {g: prefer(groups[g], fn) for g in ("luckyj", "tokujou_humans")}
    combo = {}
    for g in ("luckyj", "tokujou_humans"):
        diff = lower = 0
        for r in rows:
            if not groups[g](r) or r["label"] != "half suji" or not r.get("kept_half_suji"):
                continue
            for k in r["kept_half_suji"]:
                if ryanmen_combos(r) != ryanmen_combos(k):
                    diff += 1
                    lower += ryanmen_combos(r) < ryanmen_combos(k)
        combo[g] = [diff, pct(lower, diff)]
    preferences["fewer open two-sided combinations"] = combo

    # 4. a danger model over every live number tile: does it see what LuckyJ sees?
    names = sorted({k for r in rows for k in features(r)})
    test, train = [r for r in rows if held_out(r)], [r for r in rows if not held_out(r)]
    b = fit(design(train, names), np.array([float(r["hit"]) for r in train]))
    p_test = 1 / (1 + np.exp(-(design(test, names) @ b)))
    y_test = np.array([float(r["hit"]) for r in test])
    auc = float((p_test[y_test == 1][:, None] > p_test[y_test == 0][None, :]).mean())
    b = fit(design(rows, names), np.array([float(r["hit"]) for r in rows]))
    model = {"discards": len(rows), "held_out": len(test), "auc": round(auc, 2),
             "half_suji": {g: round(100 * float((1 / (1 + np.exp(-(design(hs, names) @ b)))).mean()), 1) for g, hs in half.items()}}

    data = {"by_table": {t: sum(r["table"] == t for r in rows) for t in ("jade", "tenhou")}, "sides": sides,
            "humans_pooled": humans_pooled, "cues": cues, "preferences": preferences, "model": model}
    Path(out).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(*sys.argv[2:4])
    else:
        report(*sys.argv[2:4])
