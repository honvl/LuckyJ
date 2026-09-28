"""Figures for chapter 15 of the personal guide: Mortal's replay of Honver's games, and two LuckyJ baselines.

usage: mortal_review.py REVIEW_DIR LJ_MANIFEST

REVIEW_DIR holds one ``scripts/mortal_hand_review.py GAME --json REVIEW_DIR/GAME.json`` file per game. From the
working directory it also reads ``mortal_lj.jsonl`` (``mortal_run.py`` over LuckyJ's games, every seat),
``calls_lj.jsonl`` and ``calls_you.jsonl`` (``calls.py`` over LuckyJ's games and over Honver's), and
``tenpai_lj.jsonl`` (``tenpai.py`` over LuckyJ's games).
"""
import collections
import glob
import json
import sys
from pathlib import Path

TILES = ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
         "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "E", "S", "W", "N", "P", "F", "C", "5mr", "5pr", "5sr"]


def plain(t):
    return t[:2] if isinstance(t, str) and t.endswith("r") else t


def honver_agreement(review_dir, deal_ins):
    rows = []
    for f in sorted(glob.glob(f"{review_dir}/*.json")):
        game = Path(f).stem[:15]
        rows += [dict(r, game=game) for r in json.load(open(f)) if r["played"] is not None]
    for name, keep in (("discards", lambda r: r["kind"] != "call"), ("call chances", lambda r: r["kind"] == "call")):
        for part, sel in (("all hands", lambda r: True), ("deal-in hands", lambda r: (r["game"], r["hand"]) in deal_ins)):
            xs = [r for r in rows if keep(r) and sel(r)]
            same = sum(plain(r["mortal"][0][0]) == plain(r["played"]) for r in xs)
            low = sum(r["differs"] and r["p_played"] < 0.1 for r in xs)
            print(f"Honver {name}, {part}: {len(xs)}, Mortal's first choice {100 * same / len(xs):.1f}%, under 10%: {low}")


def luckyj_agreement(manifest):
    hero = {m["uuid"].split("#")[0]: m["hero_seat"] for m in json.load(open(manifest))}
    cnt = collections.defaultdict(lambda: [0, 0])
    for line in open("mortal_lj.jsonl"):
        r = json.loads(line)
        if r["kind"] != "discard" or r["g"] not in hero or r["next"] not in ("dahai", "reach"):
            continue
        dist = collections.defaultdict(float)
        for a, v in r["p"].items():
            a = int(a)
            dist[plain(TILES[a]) if a <= 36 else a] += v
        if len(dist) < 2:
            continue
        act = 37 if r["next"] == "reach" else plain(r["next_pai"])
        c = cnt["LuckyJ" if r["s"] == hero[r["g"]] else "humans at its tables"]
        c[0] += 1
        c[1] += max(dist, key=dist.get) == act
    for who, (n, same) in cnt.items():
        print(f"{who}: {n} discards, Mortal's first choice {100 * same / n:.1f}%")


def idle_pons(path, who):
    """Pons of a number tile, nobody in riichi, that would not bring the hand closer to tenpai."""
    cells = collections.defaultdict(lambda: [0, 0, 0, 0, 0])
    for line in open(path):
        r = json.loads(line)
        if not r["lj"] or r["nr"] or r["tile"] > 40:
            continue
        pon = next((o for o in r["opts"] if o["k"] == "p"), None)
        if pon is None or pon["s2"] < r["sh"]:
            continue
        took = r["took"] and r["took_used"] == [r["tile"], r["tile"]]
        c = cells[("open" if r["nm"] else "closed", "dora" if r["tdora"] else "plain")]
        c[0] += 1
        c[1] += took
        if took:
            c[2] += r["won"]
            c[3] += r["dealt"]
            c[4] += r["net"]
    for key in sorted(cells):
        n, t, w, d, net = cells[key]
        tail = f", won {w}, dealt in {d}, {net / t:+.0f} a hand" if t else ""
        print(f"{who} idle pon, {key[0]} hand, {key[1]} tile: {n} chances, pon {t} ({100 * t / n:.1f}%){tail}")


def yakuless_chase():
    """First tenpai with no yaku on 4 or fewer live tiles, against one riichi."""
    rows = [json.loads(line) for line in open("tenpai_lj.jsonl")]
    rows = [r for r in rows if r["lj"] and r["nr"] == 1 and r["first"]
            and all(o["dama_max"] == 0 for o in r["opts"]) and max(o["live"] for o in r["opts"]) <= 4]
    for label, sel in (("declared", lambda r: r["riichi"] and r["kept"]), ("did not", lambda r: not (r["riichi"] and r["kept"]))):
        xs = [r for r in rows if sel(r)]
        print(f"LuckyJ yakuless narrow tenpai against a riichi, {label}: {len(xs)} of {len(rows)}, "
              f"won {sum(r['won'] for r in xs)}, dealt in {sum(r['dealt'] for r in xs)}, "
              f"{sum(r['net'] for r in xs) / len(xs):+.0f} a hand")
    lead = [r for r in rows if r["k"] >= 4 and r["sc"][r["s"]] - max(x for i, x in enumerate(r["sc"]) if i != r["s"]) >= 8000]
    print(f"  leading by 8,000 or more in the South: declared {sum(r['riichi'] and r['kept'] for r in lead)} of {len(lead)}")


if __name__ == "__main__":
    deal_ins = {("260928-7c1ee667", "E4-2"), ("260928-5a0260b7", "E2-0"), ("260928-90620418", "S1-0"),
                ("260928-90620418", "S2-0"), ("260928-90620418", "S4-0"), ("260928-50d32e06", "S2-0")}
    honver_agreement(sys.argv[1], deal_ins)
    luckyj_agreement(sys.argv[2])
    idle_pons("calls_lj.jsonl", "LuckyJ")
    idle_pons("calls_you.jsonl", "Honver")
    yakuless_chase()
