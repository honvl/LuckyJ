"""Recompute every figure the book's "Against the humans" section cites and write them to one JSON.

Run from the working directory that holds the extractor outputs (hands_lj.json, hands_houou.json,
tenpai_lj.jsonl, tenpai_hou.jsonl, mortal_disc.parquet, man/*.json and the miner rows under rows/):

    python export_figures.py OUT.json

Groups are always listed Tokujou, Houou, LuckyJ. The figures feed tests/test_table_contrast.py.
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import tenhou_replay as tr  # noqa: E402

GROUPS = ("Tokujou", "Houou", "LuckyJ")
MINER_GROUP = {"Tokujou": "opp", "Houou": "hou", "LuckyJ": "lj"}


def r1(x):
    return round(float(x), 1)


def r2(x):
    return round(float(x), 2)


def miner_rows(miner, group, key="rows"):
    rows = []
    for f in sorted(glob.glob(f"rows/{miner}__{MINER_GROUP[group]}_[0-9]*.json")):
        rows += json.load(open(f))[key]
    return rows


def diff_se(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return round(float(a.mean() - b.mean())), round(float(np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))))


def ledger():
    a = pd.DataFrame(json.load(open("hands_lj.json")))
    a["who"] = np.where(a.lj, "LuckyJ", "Tokujou")
    b = pd.DataFrame(json.load(open("hands_houou.json")))
    b["who"] = "Houou"
    df = pd.concat([a, b], ignore_index=True)
    df["state"] = [(sb[-1] if (d and sb) else None) for sb, d in zip(df.shanten_by_turn, df.dealt_in)]
    out = {"hands": {g: int((df.who == g).sum()) for g in GROUPS}}
    per = lambda sel: [r1(100 * (sel & (df.who == g)).sum() / (df.who == g).sum()) for g in GROUPS]
    out["dealin_tenpai_per100"] = per(df.dealt_in & (df.state == 0))
    out["dealin_not_tenpai_per100"] = per(df.dealt_in & (df.state >= 1))
    out["win_rate_pct"] = [r1(100 * df.loc[df.who == g, "won"].mean()) for g in GROUPS]
    out["net_gap_luckyj_over_tablemates"] = round(float(a.loc[a.lj, "net"].mean() - a.loc[~a.lj, "net"].mean()))
    lost = lambda into: [round(float(-df.loc[(df.who == g) & df.dealt_in & (df.state >= 1) & (df.deal_in_into == into), "deal_pts"].sum()
                                    / (df.who == g).sum())) for g in GROUPS]
    out["points_lost_not_tenpai_into_riichi"] = lost("riichi")
    out["points_lost_not_tenpai_into_open"] = lost("open hand")
    riichi = df[df.riichi_turn.notna()]
    out["riichi_win_pct"] = [r1(100 * riichi.loc[riichi.who == g, "won"].mean()) for g in GROUPS]
    return out


def pairs():
    ron, value, hands = {}, {}, 0
    for g in json.load(open("man/lj_all.json")):
        hero = g["hero_seat"]
        for log in json.load(open(g["file"]))["log"]:
            hands += 1
            for dl, det in tr.result_blocks(log[-1]):
                w, l = det[0], det[1]
                if w == l:
                    continue
                key = ("LJ" if w == hero else "H", "LJ" if l == hero else "H")
                ron[key] = ron.get(key, 0) + 1
                value[key] = value.get(key, 0) + dl[w]
    return {
        "human_into_luckyj_per100": r2(100 * ron[("LJ", "H")] / (3 * hands)),
        "human_into_human_per100": r2(100 * ron[("H", "H")] / (6 * hands)),
        "luckyj_ron_value": round(value[("LJ", "H")] / ron[("LJ", "H")]),
        "human_ron_value": round(value[("H", "H")] / ron[("H", "H")]),
    }


def callers():
    out = {"live_cut_2sh_no_dora": {}, "caller_tenpai_pct": {}}
    tells = lambda r: sum(bool(r[k]) for k in ("late_call", "two_calls", "tsumogiri2"))
    for g in GROUPS:
        rows = miner_rows("mine_caller_tells", g)
        base = [r for r in rows if r["dora"] == 0 and r["held_safe"] <= 1 and r["sh"] == 2]
        rate = lambda sel: r1(100 * sum(r["danger"] >= 2 for r in base if sel(r)) / sum(1 for r in base if sel(r)))
        out["live_cut_2sh_no_dora"][g] = {"no_tells": rate(lambda r: tells(r) == 0), "two_plus": rate(lambda r: tells(r) >= 2)}
        if g in ("LuckyJ", "Houou"):  # the LuckyJ-hero rows describe the callers at LuckyJ's (Tokujou) tables
            table = "Tokujou tables" if g == "LuckyJ" else "Houou tables"
            out["caller_tenpai_pct"][table] = {str(n): r1(100 * np.mean([r["tenpai"] for r in rows if tells(r) == n])) for n in range(4)}
    return out


def far():
    out = {"unsafe_tenpai_pct": [], "unsafe_2sh_pct": [], "unsafe_3sh_pct": [], "dealin_3sh_per100": [], "unsafe_far_by_turn8_pct": []}
    for g in GROUPS:
        d = pd.DataFrame(miner_rows("mine_riichi_folds", g))
        out["unsafe_tenpai_pct"].append(r1(100 * d[d.best == 0].push.mean()))
        out["unsafe_2sh_pct"].append(r1(100 * d[d.best == 2].push.mean()))
        out["unsafe_3sh_pct"].append(r1(100 * d[d.best >= 3].push.mean()))
        out["dealin_3sh_per100"].append(r2(100 * d[d.best >= 3].dealt.mean()))
        out["unsafe_far_by_turn8_pct"].append(r1(100 * d[(d.best >= 2) & (d.turn <= 8)].push.mean()))
    return out


def tenpai_table():
    frames = []
    for src, who in (("tenpai_lj.jsonl", None), ("tenpai_hou.jsonl", "Houou")):
        d = pd.DataFrame([json.loads(line) for line in open(src)])
        d["who"] = np.where(d.lj, "LuckyJ", "Tokujou") if who is None else who
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["ch"] = [next((o for o in opts if o["b"] == cut), None) for opts, cut in zip(df.opts, df.cut)]
    t = df[df["first"] & df.kept & (df.nr == 0)].copy()
    for k in ("live", "dama_max", "dama_min", "fur"):
        t[k] = t.ch.map(lambda o: o[k])
    return t[~t.fur]


def riichi():
    t = tenpai_table()
    c = t[~t.dl & (t.dama_min > 0) & t.dama_max.isin([1, 2])]
    bins = {"3 or fewer": c.live <= 3, "4 to 6": c.live.between(4, 6), "7 or more": c.live >= 7}
    out = {"declare_pct": {}, "riichi_minus_dama": {}}
    for name, sel in bins.items():
        out["declare_pct"][name] = [r1(100 * c[sel & (c.who == g)].riichi.mean()) for g in GROUPS]
        h = c[sel & (c.who != "LuckyJ")]
        out["riichi_minus_dama"][name] = list(diff_se(h[h.riichi].net, h[~h.riichi].net))
    m = pd.read_parquet("mortal_disc.parquet")
    j = c[c.who == "Tokujou"].merge(m[["g", "li", "s", "t", "m_reach"]], on=["g", "li", "s", "t"], how="inner")
    out["mortal_prefers_riichi_pct"] = r1(100 * (j.m_reach > 0.5).mean())
    out["mortal_spots"] = int(len(j))
    return out


def dora():
    out = {"tanyao_call_pct": {"no dora": [], "two or more": []}, "value_pair_pon_2sh_pct": [], "three_plus_dora_any_route_pct": {}}
    pooled = []
    for g in GROUPS:
        d = pd.DataFrame(miner_rows("mine_call_chances", g))
        two = d[(d["from"] == 2) & ~d.riichi_out]
        tan = two[two.route == "tanyao"]
        out["tanyao_call_pct"]["no dora"].append(r1(100 * tan[tan.dora == 0].took.mean()))
        out["tanyao_call_pct"]["two or more"].append(r1(100 * tan[tan.dora >= 2].took.mean()))
        out["value_pair_pon_2sh_pct"].append(r1(100 * two[two.route == "yakuhai pon"].took.mean()))
        nonyh = two[(two.route != "yakuhai pon") & (two.dora >= 3)]
        out["three_plus_dora_any_route_pct"][g] = r1(100 * nonyh.took.mean())
        if g != "LuckyJ":
            pooled.append(tan[tan["first"]])
    h = pd.concat(pooled)
    out["humans_call_minus_pass"] = {}
    for name, sel in (("no dora", h.dora == 0), ("one dora", h.dora == 1), ("two or more", h.dora >= 2)):
        x = h[sel]
        out["humans_call_minus_pass"][name] = list(diff_se(x[x.took].net, x[~x.took].net))
    return out


def flush():
    wins = {g: 0 for g in GROUPS}
    hands = {g: 0 for g in GROUPS}
    for man, grp in (("man/lj_all.json", "lj"), ("man/houou_games.json", "houou")):
        seen = set()
        for g in json.load(open(man)):
            if g["file"] in seen:
                continue
            seen.add(g["file"])
            for log in json.load(open(g["file"]))["log"]:
                game = tr.replay(log)
                who = lambda s: ("LuckyJ" if s == g["hero_seat"] else "Tokujou") if grp == "lj" else "Houou"
                for s in range(4):
                    hands[who(s)] += 1
                for _, det in tr.result_blocks(log[-1]):
                    p = game["players"][det[0]]
                    tiles = [tr.base(t) for t in p["hand"]] + [tr.base(t) for m in p["melds"] for t in m["tiles"]]
                    if len({t // 10 for t in tiles if t < 41}) == 1:
                        wins[who(det[0])] += 1
    out = {"flush_wins_per100": [r2(100 * wins[g] / hands[g]) for g in GROUPS], "fast_start_pct": {}, "humans_fast_minus_slow": {}}
    frames = []
    for g in GROUPS:
        d = pd.DataFrame(miner_rows("mine_shape_plans", g))
        d["who"] = g
        frames.append(d)
    df = pd.concat(frames, ignore_index=True)
    df["net"] = df.value - df.cost
    df["fast"] = df.first3_off >= 2
    for name, sel in (("nine with a value pair", (df.fit == 9) & df.value_pair), ("ten or more with a value pair", (df.fit >= 10) & df.value_pair)):
        out["fast_start_pct"][name] = [r1(100 * df[sel & (df.who == g)].fast.mean()) for g in GROUPS]
        h = df[sel & (df.who != "LuckyJ")]
        out["humans_fast_minus_slow"][name] = list(diff_se(h[h.fast].net, h[~h.fast].net))
    return out


def main():
    figures = {
        "groups": list(GROUPS),
        "source": "scripts/contrast/report/export_figures.py; method in analysis/table-contrast-2026-09-25.md",
        "ledger": ledger(),
        "pairs": pairs(),
        "callers": callers(),
        "far": far(),
        "riichi": riichi(),
        "dora": dora(),
        "flush": flush(),
    }
    Path(sys.argv[1]).write_text(json.dumps(figures, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(figures, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
