"""Recompute every figure the book's "When to fold to open callers" section cites and write them to one JSON.

Run from the working directory that holds the vs_callers.py outputs (callers_lj.* from man/lj_all.json with
GROUP lj, callers_hou.* from man/houou_games.json), mortal_disc.parquet and the man/ manifests:

    python export_open_callers.py OUT.json

A "free hold" is a discard against a single caller where a tile that is safe against them (genbutsu, suji,
an honor with two copies out) keeps the hand's best shanten, so cutting a live tile instead was a choice.
Groups are always listed Tokujou, Houou, LuckyJ. The figures feed tests/test_open_callers.py.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import review_win_speed as ws  # noqa: E402
import tenhou_replay as tr  # noqa: E402

GROUPS = ("Tokujou", "Houou", "LuckyJ")
BANDS = ("1-6", "7-9", "10-12", "13+")
ROWS = ("first", "second", "third")


def r1(x):
    return round(float(x), 1)


def pct(s):
    return r1(100 * s.mean())


def load(name, drop=()):
    rows = []
    with open(name) as f:
        for line in f:
            r = json.loads(line)
            for k in drop:
                r.pop(k, None)
            rows.append(r)
    return pd.DataFrame(rows)


def cuts():
    c = pd.concat([load("callers_lj.cuts.jsonl", drop=("scores",)), load("callers_hou.cuts.jsonl", drop=("scores",))], ignore_index=True)
    c["qt"] = pd.cut(c.q_turn, [0, 6, 9, 12, 30], labels=list(BANDS))
    odds = c.groupby(["n_melds", "qt"], observed=True).q_tenpai.mean().rename("odds")
    c = c.join(odds, on=["n_melds", "qt"])
    c["live"] = c.danger >= 2
    return c, odds


def fold_line(c, odds):
    one = c[c.main & (c.n_callers == 1)]
    free = one[one.keep_safe <= 1]
    out = {"bands": list(BANDS), "caller_tenpai_pct": {}, "far": {}, "one_shanten": {}}
    for m in (1, 2, 3):
        out["caller_tenpai_pct"][str(m)] = [r1(100 * odds[(m, b)]) for b in BANDS]
        for key, sel in (("far", free.best_sh >= 2), ("one_shanten", free.best_sh == 1)):
            x = free[sel & (free.n_melds == m)]
            cell = {g: [] for g in ("LuckyJ", "humans") + GROUPS[:2]}
            n = {g: [] for g in ("LuckyJ", "humans")}
            for b in BANDS:
                y = x[x.qt == b]
                for g in GROUPS[:2]:
                    cell[g].append(pct(y[y.who == g].live))
                cell["LuckyJ"].append(pct(y[y.who == "LuckyJ"].live))
                cell["humans"].append(pct(y[y.who != "LuckyJ"].live))
                n["LuckyJ"].append(int((y.who == "LuckyJ").sum()))
                n["humans"].append(int((y.who != "LuckyJ").sum()))
            out[key][str(m)] = {**cell, "n": n}
    return out


def mortal_free(c):
    """Mortal's top discard on the free-hold spots of LuckyJ's games (every seat), live or safe."""
    one = c[c.main & (c.n_callers == 1) & (c.keep_safe <= 1) & (c.who != "Houou")]
    mo = pd.read_parquet("mortal_disc.parquet", columns=["g", "li", "s", "t", "m_dist"])
    f = one.merge(mo, on=["g", "li", "s", "t"], how="inner")

    def top_live(r):
        dist = {int(k): v for k, v in json.loads(r.m_dist).items()}
        return max(r.opts, key=lambda o: dist.get(o[0], 0))[1] >= 2

    f["m_live"] = f.apply(top_live, axis=1)
    return f


def mortal_line(f):
    f = f.assign(ob=pd.cut(f.odds, [0, 0.15, 0.75, 1.01], labels=["under 15%", "middle", "over 75%"]))
    out = {}
    for key, sel in (("far", f.best_sh >= 2), ("one_shanten", f.best_sh == 1)):
        x = f[sel]
        out[key] = {}
        for band in ("under 15%", "over 75%"):
            y = x[x.ob == band]
            out[key][band] = {"Mortal": pct(y.m_live), "LuckyJ": pct(y[y.who == "LuckyJ"].live),
                              "Tokujou": pct(y[y.who == "Tokujou"].live), "n": int(len(y))}
    return out


def dora_pon(c, f):
    one = c[c.main & (c.n_callers == 1)]
    free = one[(one.keep_safe <= 1) & (one.q_turn <= 9) & (one.best_sh >= 1)]
    dp = free.q_meld_dora >= 3
    out = {"live_cut_pct": {g: [pct(free[~dp & (free.who == g)].live), pct(free[dp & (free.who == g)].live)] for g in GROUPS},
           "n": {g: [int((~dp & (free.who == g)).sum()), int((dp & (free.who == g)).sum())] for g in GROUPS},
           "far_live_cut_pct": {}, "caller_tenpai_pct": [pct(free[~dp].q_tenpai), pct(free[dp].q_tenpai)]}
    far = free[free.best_sh >= 2]
    fdp = far.q_meld_dora >= 3
    out["far_live_cut_pct"] = {g: [pct(far[~fdp & (far.who == g)].live), pct(far[fdp & (far.who == g)].live)] for g in GROUPS}
    m = f[(f.q_turn <= 9) & (f.best_sh >= 1)]
    out["mortal_live_cut_pct"] = [pct(m[m.q_meld_dora < 3].m_live), pct(m[m.q_meld_dora >= 3].m_live)]
    wins = one[one.q_won].groupby(["g", "li", "q"]).agg(gain=("q_gain", "first"), shown=("q_meld_dora", "max"))
    out["caller_win_value"] = [round(float(wins[wins.shown < 3].gain.mean())), round(float(wins[wins.shown >= 3].gain.mean()))]
    dealt = one[one.dealt]
    out["deal_in_cost"] = [round(float(-dealt[dealt.q_meld_dora < 3].my_net.mean())), round(float(-dealt[dealt.q_meld_dora >= 3].my_net.mean()))]
    out["dora_pon_share_pct"] = dora_pon_share()
    return out


def dora_pon_share():
    """Of the callers whose melds first show three dora, the share that got there with a pon or kan of the dora."""
    pon = other = 0
    for man in ("man/lj_all.json", "man/houou_games.json"):
        seen = set()
        for g in json.load(open(man)):
            if g["file"] in seen:
                continue
            seen.add(g["file"])
            for log in json.load(open(g["file"]))["log"]:
                game = tr.replay(log)
                dset = {ws.dora_from_indicator(t) for t in game["dora_indicators"][:1]}
                for p in game["players"]:
                    shown = []
                    for m in (m for m in p["melds"] if m["kind"] != "a"):
                        shown.append(m)
                        if sum(1 for mm in shown for t in mm["tiles"] if tr.base(t) in dset or tr.is_red(t)) >= 3:
                            if any(mm["kind"] in ("p", "m", "k") and tr.base(mm["called"]) in dset for mm in shown):
                                pon += 1
                            else:
                                other += 1
                            break
    return r1(100 * pon / (pon + other))


def passed(c):
    one = c[c.main & (c.n_callers == 1) & (c.best_sh >= 1) & (c.odds > 0.3)].copy()
    one["window"] = [any(p and d >= 2 and sh == b for _, d, sh, p in o) for o, b in zip(one.opts, one.best_sh)]
    x = one[one.window]
    out = {"cut_pct": {g: pct(x[x.who == g].passed) for g in GROUPS}, "n": {g: int((x.who == g).sum()) for g in GROUPS}}
    mo = pd.read_parquet("mortal_disc.parquet", columns=["g", "li", "s", "t", "m_dist"])
    m = x[x.who != "Houou"].merge(mo, on=["g", "li", "s", "t"], how="inner")

    def cuts_passed(r):
        dist = {int(k): v for k, v in json.loads(r.m_dist).items()}
        top = max(r.opts, key=lambda o: dist.get(o[0], 0))
        return bool(top[3] and top[1] >= 2)

    out["mortal_cut_pct"] = pct(m.apply(cuts_passed, axis=1))
    out["mortal_n"] = int(len(m))
    allp = c[c.passed]
    out["cuts"] = int(len(allp))
    out["deal_ins"] = int(allp.dealt.sum())
    return out


def half_wait():
    t = pd.concat([load("callers_lj.tenpai.jsonl"), load("callers_hou.tenpai.jsonl")], ignore_index=True)
    d = t[t.dilemma].copy()
    d["row"] = np.select([d.t <= 6, d.t <= 12], ["first", "second"], "third")
    d["safe"] = d.chose == "safe"
    keep = d.best_safe_live / d.widest
    d["keep"] = np.select([keep <= 0.34, keep <= 0.67], ["a third or less", "about half"], "two thirds or more")
    d["value"] = np.select([d.wide_han >= 3, d.wide_han >= 1], ["three han or more", "one or two han"], "no yaku")
    out = {"dilemmas": {g: int((d.who == g).sum()) for g in GROUPS},
           "tenpai_decisions": {g: int((t.who == g).sum()) for g in GROUPS}}
    out["safe_pct_by_row"] = {g: [pct(d[(d.who == g) & (d.row == r)].safe) for r in ROWS] for g in GROUPS}
    out["n_by_row"] = {g: [int(((d.who == g) & (d.row == r)).sum()) for r in ROWS] for g in GROUPS}
    late = d[d.row != "first"]
    out["safe_pct_by_keep"] = {g: [pct(late[(late.who == g) & (late.keep == k)].safe) for k in ("a third or less", "about half", "two thirds or more")] for g in GROUPS}
    out["safe_pct_by_value"] = {g: [pct(late[(late.who == g) & (late.value == v)].safe) for v in ("three han or more", "one or two han", "no yaku")] for g in GROUPS}
    out["n_by_value_luckyj"] = [int(((late.who == "LuckyJ") & (late.value == v)).sum()) for v in ("three han or more", "one or two han", "no yaku")]
    out["dama_safe_pct"] = {g: pct(late[(late.who == g) & late.closed].safe) for g in GROUPS}
    out["dama_n_luckyj"] = int(((late.who == "LuckyJ") & late.closed).sum())
    out["open_safe_pct_luckyj"] = pct(late[(late.who == "LuckyJ") & ~late.closed].safe)
    out["third_row_two_tells_safe_pct_luckyj"] = pct(d[(d.who == "LuckyJ") & (d.row == "third") & (d.tells_main >= 2)].safe)
    out["live_tile_on_wait_pct_by_row"] = [pct(d[d.row == r].wide_on_wait) for r in ROWS]
    out["live_tile_on_wait_pct_third_row_two_tells"] = pct(d[(d.row == "third") & (d.tells_main >= 2)].wide_on_wait)
    h = d[(d.who != "LuckyJ") & d.chose.isin(["wide", "safe"])]
    out["humans_net_by_row"] = {ch: [round(float(h[(h.row == r) & (h.chose == ch)].net.mean())) for r in ROWS] for ch in ("wide", "safe")}
    h3 = h[h.row == "third"]
    out["humans_third_row_two_tells_pct"] = {ch: pct(h3[h3.chose == ch].tells_main >= 2) for ch in ("wide", "safe")}
    mo = pd.read_parquet("mortal_disc.parquet", columns=["g", "li", "s", "t", "m_dist"])
    m = d[d.who != "Houou"].merge(mo, on=["g", "li", "s", "t"], how="inner")

    def prefers_safe(r):
        dist = {int(k): v for k, v in json.loads(r.m_dist).items()}
        return sum(dist.get(k, 0) for k in r.safe_tiles) > sum(dist.get(k, 0) for k in r.wide_tiles)

    m["m_safe"] = m.apply(prefers_safe, axis=1)
    out["mortal_safe_pct_by_row"] = [pct(m[m.row == r].m_safe) for r in ROWS]
    out["mortal_n_by_row"] = [int((m.row == r).sum()) for r in ROWS]
    ml = m[m.row != "first"]
    out["mortal_dama_with_yaku_safe_pct"] = pct(ml[ml.closed & (ml.value != "no yaku")].m_safe)
    out["mortal_dama_with_yaku_n"] = int((ml.closed & (ml.value != "no yaku")).sum())
    lj = m[m.who == "LuckyJ"]
    out["mortal_agrees_with_luckyj_pct"] = pct(lj.m_safe == lj.safe)
    return out


def main():
    c, odds = cuts()
    f = mortal_free(c)
    figures = {
        "groups": list(GROUPS),
        "source": "scripts/contrast/report/export_open_callers.py; method in analysis/open-callers-2026-09-27.md",
        "cuts": {g: int((c.who == g).sum()) for g in GROUPS},
        "discards": {g: int((c.drop_duplicates(["g", "li", "s", "t"]).who == g).sum()) for g in GROUPS},
        "fold_line": fold_line(c, odds),
        "mortal_fold_line": mortal_line(f),
        "dora_pon": dora_pon(c, f),
        "passed": passed(c),
        "half_wait": half_wait(),
    }
    Path(sys.argv[1]).write_text(json.dumps(figures, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(figures, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
