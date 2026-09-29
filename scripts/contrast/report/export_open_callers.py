"""Recompute every figure the book's "When to fold to open callers" section cites and write them to one JSON.

Run from the working directory that holds the vs_callers.py outputs (callers_lj.* from man/lj_all.json with
GROUP lj, callers_hou.* from man/houou_games.json), mortal_disc.parquet, mortal_halfwait.jsonl (mortal_spots.py
run on every half-wait dilemma in callers_lj.tenpai.jsonl), riichi_open_lj.jsonl and riichi_open_hou.jsonl
(riichi_danger.py on the same two manifests), mortal_riichi_open.jsonl (mortal_spots.py on their riichi dilemmas in
LuckyJ's and the Houou games), choices_lj.jsonl, choices_opp.jsonl and choices_hou.jsonl (choices.py on
man/lj_all.json, man/opp_all.json and man/houou_all.json) and the man/ manifests:

    python export_open_callers.py OUT.json

A "free hold" is a discard against a single caller where a tile that is safe against them (genbutsu, suji,
an honor with two copies out) keeps the hand's best shanten. The first version of the section took every
free hold as a choice; ``real_choices`` keeps only those where a live tile also keeps the shanten with at
least as much acceptance, so that throwing the safe tile was defense, not shape.
Groups are always listed Tokujou, Houou, LuckyJ. The figures feed tests/test_open_callers.py.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts"))
import mine_caller_fold_line as fold  # noqa: E402
import mine_safe_tile_timing as timing  # noqa: E402
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
    out["closed_safe_pct"] = {g: pct(late[(late.who == g) & late.closed].safe) for g in GROUPS}
    out["closed_n_luckyj"] = int(((late.who == "LuckyJ") & late.closed).sum())
    out["open_safe_pct_luckyj"] = pct(late[(late.who == "LuckyJ") & ~late.closed].safe)
    out["third_row_two_tells_safe_pct_luckyj"] = pct(d[(d.who == "LuckyJ") & (d.row == "third") & (d.tells_main >= 2)].safe)
    out["live_tile_on_wait_pct_by_row"] = [pct(d[d.row == r].wide_on_wait) for r in ROWS]
    out["live_tile_on_wait_pct_third_row_two_tells"] = pct(d[(d.row == "third") & (d.tells_main >= 2)].wide_on_wait)
    h = d[(d.who != "LuckyJ") & d.chose.isin(["wide", "safe"])]
    out["humans_net_by_row"] = {ch: [round(float(h[(h.row == r) & (h.chose == ch)].net.mean())) for r in ROWS] for ch in ("wide", "safe")}
    h3 = h[h.row == "third"]
    out["humans_third_row_two_tells_pct"] = {ch: pct(h3[h3.chose == ch].tells_main >= 2) for ch in ("wide", "safe")}
    # Mortal's own choice at the same spots of LuckyJ's games (mortal_spots.py): its top action, and when that
    # is riichi, the tile it declares with
    mh = pd.DataFrame([json.loads(line) for line in open("mortal_halfwait.jsonl")])
    m = d[d.who != "Houou"].merge(mh, on=["g", "li", "s", "t"], how="inner")

    def top_tile(r):
        tiles = {int(k): v for k, v in r.act.items() if k != "reach"}
        top = max(tiles, key=tiles.get)
        if r.act.get("reach", 0) > tiles[top] and isinstance(r.reach_tile, dict):
            declare = {int(k): v for k, v in r.reach_tile.items()}
            top = max(declare, key=declare.get)
        return top

    m["m_tile"] = m.apply(top_tile, axis=1)
    m["m_safe"] = [t in tiles for t, tiles in zip(m.m_tile, m.safe_tiles)]
    m["m_class"] = np.select([m.m_safe, [t in tiles for t, tiles in zip(m.m_tile, m.wide_tiles)]], ["safe", "wide"], "other")
    out["mortal_safe_pct_by_row"] = [pct(m[m.row == r].m_safe) for r in ROWS]
    out["mortal_n_by_row"] = [int((m.row == r).sum()) for r in ROWS]
    ml = m[m.row != "first"]
    out["mortal_closed_with_yaku_safe_pct"] = pct(ml[ml.closed & (ml.value != "no yaku")].m_safe)
    out["mortal_closed_with_yaku_n"] = int((ml.closed & (ml.value != "no yaku")).sum())
    lj = m[m.who == "LuckyJ"]
    out["mortal_agrees_with_luckyj_pct"] = pct(lj.m_class == np.where(lj.chose.isin(["wide", "safe"]), lj.chose, "other"))
    lc = late[(late.who == "LuckyJ") & late.closed & (late.value != "no yaku")]
    out["closed_with_yaku_safe_pct_luckyj"] = pct(lc.safe)
    out["closed_with_yaku_n_luckyj"] = int(len(lc))
    return out


def riichi_open():
    """Closed first tenpais that may declare, facing callers with nobody in riichi (riichi_danger.py rows), where every
    widest-wait discard is live against a caller and a safe discard keeps a narrower, non-furiten tenpai."""
    rows = [json.loads(line) for name in ("riichi_open_lj.jsonl", "riichi_open_hou.jsonl") for line in open(name)]
    spots, fresh_live = [], []
    for r in rows:
        if r["nr"] or not r["nc"] or not r["riichi_ok"] or r["was_tenpai"]:
            continue
        ok = [o for o in r["opts"] if not o["fur"]]
        widest = max((o["live"] for o in ok), default=0)
        if widest == 0:
            continue
        wide = [o for o in ok if o["live"] == widest]
        live = all(o["dc"] >= 2 for o in wide)
        fresh_live.append({"who": r["who"], "live": live, "riichi": r["riichi"]})
        safe = [o for o in ok if o["dc"] <= 1 and 1 <= o["live"] < widest]
        if not live or not safe:
            continue
        wb, sb = {o["b"] for o in wide}, {o["b"] for o in safe}
        chose = "wide" if r["cut"] in wb else "safe" if r["cut"] in sb else "other"
        spots.append({"g": r["g"], "li": r["li"], "s": r["s"], "t": r["t"], "who": r["who"], "chose": chose, "riichi": r["riichi"],
                      "keep": max(o["live"] for o in safe) / widest, "wide_tiles": wb, "safe_tiles": sb, "net": r["net"],
                      "wide_on": any(o["on_c"] for o in wide)})
    d = pd.DataFrame(spots)
    fl = pd.DataFrame(fresh_live)
    out = {"spots": {g: int((d.who == g).sum()) for g in GROUPS}}
    out["declared_pct"] = {g: pct(d[d.who == g].riichi) for g in GROUPS}
    decl = d[d.riichi & d.chose.isin(["wide", "safe"])]
    out["declared_wide_pct"] = {g: pct(decl[decl.who == g].chose == "wide") for g in GROUPS}
    out["declared_n"] = {g: int((decl.who == g).sum()) for g in GROUPS}
    out["share_pct"] = {g: {f"{c} {'riichi' if r else 'dama'}": pct((d[d.who == g].chose == c) & (d[d.who == g].riichi == r))
                            for c in ("wide", "safe") for r in (True, False)} for g in GROUPS}
    out["riichi_pct_widest_live"] = {g: pct(fl[(fl.who == g) & fl.live].riichi) for g in GROUPS}
    out["riichi_pct_widest_safe"] = {g: pct(fl[(fl.who == g) & ~fl.live].riichi) for g in GROUPS}
    h = d[d.who != "LuckyJ"]
    out["humans_net"] = {f"{c} {'riichi' if r else 'dama'}": round(float(h[(h.chose == c) & (h.riichi == r)].net.mean()))
                         for c in ("wide", "safe") for r in (True, False)}
    mo = pd.DataFrame([json.loads(line) for line in open("mortal_riichi_open.jsonl")])
    m = d.merge(mo, on=["g", "li", "s", "t"], how="inner")

    def mortal_choice(r):
        tiles = {int(k): v for k, v in r.act.items() if k != "reach"}
        top = max(tiles, key=tiles.get)
        declares = r.act.get("reach", 0) > tiles[top]
        if declares:
            declare = {int(k): v for k, v in r.reach_tile.items()}
            top = max(declare, key=declare.get)
        return declares, "wide" if top in r.wide_tiles else "safe" if top in r.safe_tiles else "other"

    m[["m_riichi", "m_chose"]] = m.apply(mortal_choice, axis=1, result_type="expand")
    out["mortal_n"] = int(len(m))
    out["mortal_declared_pct"] = pct(m.m_riichi)
    md = m[m.m_riichi & m.m_chose.isin(["wide", "safe"])]
    out["mortal_declared_wide_pct"] = pct(md.m_chose == "wide")
    keep = np.select([md.keep <= 0.34, md.keep <= 0.67], ["a third or less", "about half"], "two thirds or more")
    out["mortal_declared_safe_pct_by_keep"] = [pct(md[keep == k].m_chose == "safe") for k in ("a third or less", "about half", "two thirds or more")]
    out["live_tile_on_wait_pct"] = pct(d.wide_on)
    return out


KINDS = ("tie", "safe tile costs acceptance", "safe tile is the best tile", "only safe tiles keep shanten")
COUNTS = {"real": KINDS[:2], "tie": KINDS[:1], "costly": KINDS[1:2], "free hold": KINDS}
HANDS = {"far": lambda sh: sh >= 2, "one_shanten": lambda sh: sh == 1}
BLOCKS = {"1": (1,), "2+": (2, 3, 4)}
CHOICE_FILES = ("choices_lj.jsonl", "choices_opp.jsonl", "choices_hou.jsonl")
CHOICE_KEY = re.compile(r'^\{"g": "([^"]+)", "s": (\d), "li": (\d+), "t": (\d+),')


def acceptance(keys):
    """Every candidate's acceptance on the given (g, li, s, t) turns, from choices.py over man/lj_all.json,
    man/opp_all.json (the same games with a human's seat as hero) and man/houou_all.json (every Houou seat)."""
    out = {}
    for name in CHOICE_FILES:
        with open(name) as f:
            for line in f:
                m = CHOICE_KEY.match(line)
                key = (m[1], int(m[3]), int(m[2]), int(m[4]))
                if key in keys:
                    out[key] = {c["b"]: c["uk"] for c in json.loads(line)["cands"]}
    return out


def with_kinds(c):
    """The free-hold spots, each with what throwing the safe tile meant (mine_caller_fold_line.kind): a tie, a safe
    tile that costs acceptance (these two are real choices), the safe tile as the best tile, or only safe tiles
    keeping the shanten."""
    free = c[c.main & (c.n_callers == 1) & (c.keep_safe <= 1)].copy()
    keys = list(zip(free.g, free.li, free.s, free.t))
    uk = acceptance(set(keys))
    free["kind"] = [fold.kind([(d, sh, uk[k][b]) for b, d, sh, _ in opts]) for k, opts in zip(keys, free.opts)]
    return free


def live_curve(x, live, grid=False):
    """The share of live cuts by the caller's discards, fitted as in mine_caller_fold_line.fold_curve (discards 1 to
    18, those with 40 spots or more); the line is the first discard whose fitted share is below half."""
    points = []
    for d in range(1, fold.MAX_DISCARD + 1):
        y = live[x.q_turn == d]
        points.append({"turn": d, "lj_k": int(y.sum()), "lj_n": int(len(y)), "naga_k": 0, "naga_n": 0})
    span = timing._longest_run(list(range(1, fold.MAX_DISCARD + 1)), {p["turn"]: p["lj_n"] for p in points}, fold.MIN_SPOTS)
    out = {"spots": int(sum(p["lj_n"] for p in points)), "k": [p["lj_k"] for p in points], "n": [p["lj_n"] for p in points],
           "range": None, "df": None, "crossings_50": [], "line": None, "fit": {}}
    if not span or span[1] - span[0] < 3:
        return out
    fit = timing.fit_series(points, "lj", span[0], span[1])
    at = {round(g[0], 1): g for g in fit["grid"]}
    down = [c["turn"] for c in fit["crossings_50"] if c["direction"] == "down"]
    first = at[float(span[0])][1]
    out.update({"range": list(span), "df": fit["df"], "crossings_50": fit["crossings_50"],
                "line": int(np.ceil(down[0])) if down and first >= 50 else None,
                "fit": {str(d): [r1(at[float(d)][1]), r1(at[float(d)][2]), r1(at[float(d)][3])] for d in range(span[0], span[1] + 1)}})
    if grid:
        out["grid"] = [[g[0], r1(g[1]), r1(g[2]), r1(g[3])] for g in fit["grid"]]
    return out


def real_choices(c, f):
    """The fold line again, counting only real choices: a live tile keeps the shanten with at least as much acceptance
    as the best safe tile. Ties (the two exactly as good) and costly turns (the safe tile gives up acceptance) are also
    given apart. Groups: LuckyJ, the Tokujou humans at its tables, the Houou players, both human groups pooled, and
    Mortal's top choice on the spots of LuckyJ's games (every seat)."""
    free = with_kinds(c)
    f = f.merge(free[["g", "li", "s", "t", "kind"]], on=["g", "li", "s", "t"], how="left")
    who = {"LuckyJ": free.who == "LuckyJ", "Tokujou": free.who == "Tokujou", "Houou": free.who == "Houou",
           "humans": free.who != "LuckyJ"}
    out = {"definition": "Single caller, nobody in riichi, a safe tile (danger 1 or less) keeps the best shanten. A real "
                         "choice: a live tile keeps it too, with at least as much acceptance as the best safe tile. A tie: "
                         "exactly as much. Costly: the safe tile keeps less. Live share = discards that were a live tile.",
           "kinds": {}, "bands": {}, "lines": {}, "mortal": {}, "dora_pon": {}, "early_honors_terminals_pct": {}}
    for hand, keep in HANDS.items():
        h = free[keep(free.best_sh)]
        out["kinds"][hand] = {g: {k: {"spots": int(((h.kind == k) & who[g][h.index]).sum()),
                                      "live_pct": pct(h[(h.kind == k) & who[g][h.index]].live)} for k in KINDS}
                              for g in ("LuckyJ", "Tokujou", "Houou")}
        out["bands"][hand], out["lines"][hand] = {}, {}
        for count, kinds in COUNTS.items():
            x = h[h.kind.isin(kinds)]
            out["bands"][hand][count] = {}
            for m in (1, 2, 3):
                y = x[x.n_melds == m]
                out["bands"][hand][count][str(m)] = {
                    g: {"live_pct": [pct(y[(y.qt == b) & who[g][y.index]].live) for b in BANDS],
                        "n": [int(((y.qt == b) & who[g][y.index]).sum()) for b in BANDS]} for g in who}
            out["lines"][hand][count] = {}
            for block, calls in BLOCKS.items():
                y = x[x.n_melds.isin(calls)]
                # the fine fit grid only for what the book's chart draws (scripts/build_open_callers_figure.py)
                drawn = hand == "far" and count in ("tie", "costly")
                curves = {g: live_curve(y[who[g][y.index]], y[who[g][y.index]].live, grid=drawn and g in ("LuckyJ", "humans"))
                          for g in who}
                z = f[f.kind.isin(kinds) & keep(f.best_sh) & f.n_melds.isin(calls)]
                curves["Mortal"] = live_curve(z, z.m_live)
                out["lines"][hand][count][block] = curves
        # Mortal against LuckyJ and the Tokujou humans on the same spots, by how likely the caller was to be tenpai
        z = f[f.kind.isin(COUNTS["real"]) & keep(f.best_sh)]
        z = z.assign(ob=pd.cut(z.odds, [0, 0.15, 0.75, 1.01], labels=["under 15%", "middle", "over 75%"]))
        out["mortal"][hand] = {band: {"Mortal": pct(z[z.ob == band].m_live),
                                      "LuckyJ": pct(z[(z.ob == band) & (z.who == "LuckyJ")].live),
                                      "Tokujou": pct(z[(z.ob == band) & (z.who == "Tokujou")].live),
                                      "n": int((z.ob == band).sum()),
                                      "n_luckyj": int(((z.ob == band) & (z.who == "LuckyJ")).sum())}
                               for band in ("under 15%", "over 75%")}
        # early against one call: how much of each group's discards were live honors and terminals, live 2 to 8
        e = h[h.kind.isin(COUNTS["real"]) & (h.n_melds == 1) & (h.q_turn <= 6)]
        out["early_honors_terminals_pct"][hand] = {
            g: {"live_honor_or_terminal": pct(e[who[g][e.index]].live & e[who[g][e.index]].tclass.isin(["honor", "term"])),
                "live_number": pct(e[who[g][e.index]].live & ~e[who[g][e.index]].tclass.isin(["honor", "term"])),
                "n": int(who[g][e.index].sum())} for g in who}
    # the dora pon, first nine discards, one-shanten or further, on real choices
    x = free[free.kind.isin(COUNTS["real"]) & (free.q_turn <= 9) & (free.best_sh >= 1)]
    dp = x.q_meld_dora >= 3
    far = x.best_sh >= 2
    out["dora_pon"] = {"live_cut_pct": {g: [pct(x[~dp & who[g][x.index]].live), pct(x[dp & who[g][x.index]].live)] for g in who},
                       "far_live_cut_pct": {g: [pct(x[far & ~dp & who[g][x.index]].live), pct(x[far & dp & who[g][x.index]].live)] for g in who},
                       "n": {g: [int((~dp & who[g][x.index]).sum()), int((dp & who[g][x.index]).sum())] for g in who}}
    m = f[f.kind.isin(COUNTS["real"]) & (f.q_turn <= 9) & (f.best_sh >= 1)]
    out["dora_pon"]["mortal_live_cut_pct"] = [pct(m[m.q_meld_dora < 3].m_live), pct(m[m.q_meld_dora >= 3].m_live)]
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
        "riichi_open": riichi_open(),
        "real_choices": real_choices(c, f),
    }
    Path(sys.argv[1]).write_text(json.dumps(figures, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps({k: v for k, v in figures.items() if k != "real_choices"}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
