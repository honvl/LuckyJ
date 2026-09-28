"""Figures for chapter 16 of the personal guide: the Mortal disagreements that are Honver's and not LuckyJ's.

usage: fold_later.py REPLAYS_DIR LJ_MANIFEST SELF_MANIFEST

Reads from the working directory ``choices_you.jsonl`` and ``choices_lj.jsonl`` (``choices.py`` over Honver's
games and LuckyJ's) and ``mortal_lj.jsonl`` (``mortal_run.py`` over LuckyJ's games). Honver's Mortal
probabilities come from the site's replay files (``scripts/build_replays.py``), which store them for every one of
his decisions. Riichi declarations are left out of the discard figures.
"""
import collections
import datetime
import glob
import json
import math
import sys

TILES = ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
         "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "E", "S", "W", "N", "P", "F", "C", "5mr", "5pr", "5sr"]


def code(t):
    t = t[:2] if t.endswith("r") else t
    if t[0].isdigit():
        return {"m": 10, "p": 20, "s": 30}[t[1]] + int(t[0])
    return 41 + "ESWNPFC".index(t)


def tile_probs(pairs):
    out = collections.defaultdict(float)
    for a, p in pairs:
        if isinstance(a, int):
            if a <= 36:
                out[code(TILES[a])] += p
        elif a[0].isdigit() or a in "ESWNPFC":
            out[code(a)] += p
    tot = sum(out.values()) or 1
    return {b: p / tot for b, p in out.items()}


def load_choices(path):
    return {(r["g"], r["li"], r["t"]): r for r in map(json.loads, open(path))}


def honver_rows(replays):
    ch, rows = load_choices("choices_you.jsonl"), []
    for f in sorted(glob.glob(f"{replays}/2*.json")):
        d = json.load(open(f))
        hero = d["hero"]
        for li, h in enumerate(d["hands"]):
            turn, turns = 0, []
            for e in h["ev"]:
                if e[1] == hero and ((e[0] == "t" and len(e) < 4) or e[0] in ("c", "p", "m")):
                    turn += 1
                turns.append(turn)
            for a in h["ai"]:
                e = h["ev"][a["i"]]
                if e[1] != hero or e[0] not in ("t", "c", "p") or a["you"] in ("win", "kan", "riichi"):
                    continue
                r = ch.get((d["id"], li, turns[a["i"]]))
                if r and not r["rd"]:
                    rows.append(dict(r, P=tile_probs(a["p"])))
    return rows


def luckyj_rows(manifest):
    ch, rows = load_choices("choices_lj.jsonl"), []
    hero = {m["uuid"].split("#")[0]: m["hero_seat"] for m in json.load(open(manifest))}
    for r in map(json.loads, open("mortal_lj.jsonl")):
        if r["kind"] != "discard" or r["g"] not in hero or r["s"] != hero[r["g"]] or r["next"] != "dahai":
            continue
        c = ch.get((r["g"], r["li"], r["n"]))
        if c and not c["rd"]:
            rows.append(dict(c, P=tile_probs([(int(a), p) for a, p in r["p"].items()])))
    return rows


def ctx(r):
    return "a riichi" if r["nr"] else "two or more calls" if r["mo"] >= 2 else "one call" if r["mo"] == 1 else "nobody"


def cand(r, b):
    return next(x for x in r["cands"] if x["b"] == b)


def mortal_push_spot(r):
    """Mortal puts 60% or more on one tile and a safer tile is in hand: (took a safer tile Mortal gives <10%,
    that safer tile cost shape)."""
    if len(r["P"]) < 2:
        return None
    M = max(r["P"], key=r["P"].get)
    m = cand(r, M)
    if r["P"][M] < 0.6 or m["safe"] is None or not any(x["safe"] < m["safe"] for x in r["cands"]):
        return None
    h = cand(r, r["cut"])
    over = h["safe"] < m["safe"] and r["P"].get(r["cut"], 0) < 0.1
    return over, over and (h["sh"] > m["sh"] or h["uk"] < m["uk"])


def first_row(r):
    """Two or more calls, first six discards of the caller: ('tie', cut the safe one) or ('costly', paid)."""
    c = r["cands"]
    if any(x["safe"] is None for x in c):
        return None
    bs = min(x["sh"] for x in c)
    cut = cand(r, r["cut"])
    best = [x for x in c if x["sh"] == bs]
    top = max(x["uk"] for x in best)
    safe = [x for x in best if x["safe"] <= 1 and x["uk"] >= top - 1]
    live = [x for x in best if x["safe"] >= 3 and x["uk"] >= top - 1]
    if safe and live and cut["sh"] == bs:
        return "tie", cut["safe"] <= 1
    push = max(best, key=lambda x: (x["uk"], -x["safe"]))
    if push["safe"] == min(x["safe"] for x in c):
        return None
    return "costly", cut["safe"] < push["safe"] and (cut["sh"] > bs or cut["uk"] < push["uk"])


def riichi_one_shanten(r):
    """A riichi out, 1-shanten, the safest tile breaks the shanten: 'broke', 'suji' (kept it with suji or a 2-seen
    honor) or 'live' (kept it with a live tile)."""
    c = r["cands"]
    if r["bs"] != 1 or any(x["safe"] is None for x in c):
        return None
    smin = min(x["safe"] for x in c)
    if min(x["sh"] for x in c if x["safe"] == smin) <= 1:
        return None
    cut = cand(r, r["cut"])
    return "broke" if cut["sh"] > 1 else "suji" if cut["safe"] <= 2 else "live"


def pct(k, n):
    return f"{k}/{n} {100 * k / max(n, 1):.1f}%"


def z(k1, n1, k2, n2):
    p1, p2 = k1 / n1, k2 / n2
    return (p1 - p2) / (math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2) or 1)


def main():
    replays, lj_manifest, self_manifest = sys.argv[1:4]
    D = {"you": honver_rows(replays), "lj": luckyj_rows(lj_manifest)}
    start = {m["uuid"]: m["start_time"] for m in json.load(open(self_manifest))}
    cut24 = datetime.datetime(2026, 9, 24).timestamp()

    print("Mortal's first choice, and choices it gives under 10% per 100 discards, by threat")
    for who, rows in D.items():
        rows = [r for r in rows if len(r["P"]) >= 2]
        first = sum(max(r["P"], key=r["P"].get) == r["cut"] for r in rows)
        by = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            by[ctx(r)][0] += 1
            by[ctx(r)][1] += r["P"].get(r["cut"], 0) < 0.1 and max(r["P"], key=r["P"].get) != r["cut"]
        print(f"  {who}: {len(rows)} discards, first choice {100 * first / len(rows):.1f}%; "
              + "; ".join(f"{k} {100 * v[1] / v[0]:.1f} ({v[0]})" for k, v in sorted(by.items())))

    print("Spots where Mortal pushes with 60%+ and a safer tile is in hand: took a safer tile it gives under 10%")
    for k in ("a riichi", "two or more calls", "one call"):
        cells = {}
        for who, rows in D.items():
            s = [mortal_push_spot(r) for r in rows if ctx(r) == k]
            s = [x for x in s if x]
            cells[who] = (sum(x[0] for x in s), len(s))
        (ky, ny), (kl, nl) = cells["you"], cells["lj"]
        print(f"  {k}: you {pct(ky, ny)}, LuckyJ {pct(kl, nl)} (z {z(ky, ny, kl, nl):+.1f})")
    for label, sel in (("before 24 Sep", lambda r: start[r["g"]] < cut24), ("24 Sep on", lambda r: start[r["g"]] >= cut24)):
        s = [x for x in (mortal_push_spot(r) for r in D["you"] if ctx(r) == "two or more calls" and sel(r)) if x]
        print(f"    two or more calls, you {label}: {pct(sum(x[0] for x in s), len(s))}")
    for who, rows in D.items():
        s = [x for x in (mortal_push_spot(r) for r in rows if ctx(r) == "a riichi" and r["hd"] >= 2) if x]
        costly = [x for x in s if x[0] == x[1]]
        print(f"    a riichi, two dora or more, {who}: paid shape for the safer tile {pct(sum(x[1] for x in s), len(s))}")

    print("Two or more calls, by the caller's pond (behavior only)")
    for kind in ("tie", "costly"):
        for rows_sel, label in ((lambda r: r["pond"] <= 6, "first row (1-6)"), (lambda r: r["pond"] >= 7, "7 and on")):
            cells = {}
            for who, rows in D.items():
                v = [first_row(r) for r in rows if ctx(r) == "two or more calls" and rows_sel(r)]
                v = [x[1] for x in v if x and x[0] == kind]
                cells[who] = (sum(v), len(v))
            (ky, ny), (kl, nl) = cells["you"], cells["lj"]
            print(f"  {kind}, {label}: you {pct(ky, ny)}, LuckyJ {pct(kl, nl)} (z {z(ky, ny, kl, nl):+.1f})")
    for label, sel in (("before 24 Sep", lambda r: start[r["g"]] < cut24), ("24 Sep on", lambda r: start[r["g"]] >= cut24)):
        v = [first_row(r) for r in D["you"] if ctx(r) == "two or more calls" and r["pond"] <= 6 and sel(r)]
        v = [x[1] for x in v if x and x[0] == "costly"]
        print(f"    costly, first row, you {label}: {pct(sum(v), len(v))}")

    print("A riichi out, 1-shanten, the safest tile breaks it (behavior only)")
    for who, rows in D.items():
        cnt = collections.defaultdict(collections.Counter)
        for r in rows:
            if ctx(r) != "a riichi":
                continue
            v = riichi_one_shanten(r)
            if v:
                cnt[("turn 13 on" if r["t"] >= 13 else "before turn 13", "2+ dora" if r["hd"] >= 2 else "0-1 dora")][v] += 1
        for k in sorted(cnt):
            n = sum(cnt[k].values())
            print(f"  {who} {k}: {n}, " + ", ".join(f"{v} {100 * cnt[k][v] / n:.0f}%" for v in ("broke", "suji", "live")))


if __name__ == "__main__":
    main()
