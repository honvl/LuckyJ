#!/usr/bin/env python3
"""The figures behind guide chapter 30: does the user deal in more because they spend fewer safe tiles than LuckyJ?

The window is the user's games after chapter 29's ten, 7 October 18:25 to 10 October 14:43. It is set beside chapter 29's
ten games (3 October 14:11 to 7 October 15:27), the games before them, and LuckyJ:

- hands: the same hand table as chapter 29 (``mine_costly_run.hand_summary`` over ``contrast/hands_all.py``); the
  other columns are read from ``analysis/costly-run-2026-10-07.json``;
- riichi: from ``mine_riichi_folds.py compute`` rows, the live cuts when a safe tile kept the shanten, by the best
  shanten, and, when the cut was safe, how often it was a weaker kind of safe tile than the best one kept;
- callers: real choices against a single caller (``mine_caller_fold_line.kind`` over ``contrast/vs_callers.py`` and
  ``contrast/choices.py --callers``), the user's live share against LuckyJ's fitted curves at the same discards
  (chapter 28's one-call curves by dealer, chapter 19's two-or-more-call curves);
- safe tiles held: from ``mine_early_safe_tiles.py riichi`` rows, the safe tiles and genbutsu the user held when an
  opponent declared, against LuckyJ's average at the same declarer discard;
- deal-ins: each one rated by Mortal's weight on the user's choice (``mine_costly_run.deal_ins_and_riichis``), with
  Mortal's top choice;
- rank points: the amae-koromo records, anchored as chapter 27 was (6,700 before the 3 October 14:11 game).

usage: mine_defense_check.py RF_YOU RF_LJ ESR_YOU ESR_LJ VC_YOU_CUTS CHOICES_YOU OUT.json
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import hands_all  # noqa: E402
import mine_caller_fold_line as fl  # noqa: E402
import mine_costly_run as mc  # noqa: E402
from mine_dealer_callers import acceptance, cut_rows  # noqa: E402

MANIFEST = ROOT / "data/self_games/majsoul/index.json"
AMAE = ROOT / "data/self_games/majsoul/amae-koromo-records.json"
COSTLY = ROOT / "analysis/costly-run-2026-10-07.json"
DEALER = ROOT / "analysis/dealer-callers-2026-10-04.json"
FOLD = ROOT / "analysis/caller-fold-line-2026-09-29.json"
REPLAYS = ROOT / "site/replays"
CH29_FIRST, CH29_LAST = "261004-3d4685b3", "261008-ce956cd8"
NEW_LAST = "261011-285cf167"
ACCOUNT = 120182062
ANCHOR = 6700  # chapter 27's rank points before the 3 October 14:11 game
ORDER = ["genbutsu", "honor 2 seen", "suji", "nakasuji", "virtual nakasuji", "live honor", "live terminal", "half suji",
         "live 2-8"]
BANDS = {"tenpai": lambda b: b == 0, "one": lambda b: b == 1, "two_or_more": lambda b: b >= 2}


def windows(manifest: list[dict]) -> dict[str, str]:
    first = next(k for k, g in enumerate(manifest) if g["uuid"].startswith(CH29_FIRST))
    last = next(k for k, g in enumerate(manifest) if g["uuid"].startswith(CH29_LAST))
    end = next(k for k, g in enumerate(manifest) if g["uuid"].startswith(NEW_LAST))
    out = {}
    for k, g in enumerate(manifest[:end + 1]):
        out[g["uuid"]] = "before" if k < first else "ch29" if k <= last else "new"
    return out


def riichi(rows: list[dict]) -> dict:
    out = {}
    for name, keep in BANDS.items():
        s = [r for r in rows if r["keep_safe"] and keep(r["best"])]
        out[name] = {"turns": len(s), "live": round(100 * sum(r["push"] for r in s) / len(s), 1) if s else None}
    folds = [r for r in rows if r["keep_safe"] and not r["push"] and r.get("best_keep_class") and r.get("cut_class")]
    weaker = [r for r in folds if ORDER.index(r["cut_class"]) > ORDER.index(r["best_keep_class"])]
    out["safe_cuts"] = len(folds)
    out["weaker_kind"] = round(100 * len(weaker) / len(folds), 1)
    out["suji_over_genbutsu"] = sum(1 for r in weaker if (r["cut_class"], r["best_keep_class"]) == ("suji", "genbutsu"))
    out["discards"] = len(rows)
    return out


def caller_expected(r: dict, dealer: dict, fold: dict) -> float | None:
    hand = "far" if r["best_sh"] >= 2 else "one" if r["best_sh"] == 1 else None
    if hand is None:
        return None
    if r["n_melds"] == 1:
        at = dealer["curves"][hand]["dealer" if r["q_dealer"] else "other"]["at"].get(str(r["q_turn"]))
        return at[0] if at else None
    cell = fold["shanten"][hand]["blocks"]["2+"]["cells"].get(str(r["q_turn"]))
    return cell.get("fit") if cell else None


def held(you: list[dict], lj: list[dict]) -> dict:
    by_turn = defaultdict(list)
    for r in lj:
        by_turn[min(r["r_turn"], 15)].append(r)
    mean = lambda rs, f: sum(f(x) for x in rs) / len(rs)
    expect = lambda f: sum(mean(by_turn[min(r["r_turn"], 15)], f) for r in you) / len(you)
    return {"riichis": len(you),
            "safe": round(mean(you, lambda r: r["n_safe"]), 2), "safe_luckyj": round(expect(lambda r: r["n_safe"]), 2),
            "genbutsu": round(mean(you, lambda r: r["n_gen"]), 2), "genbutsu_luckyj": round(expect(lambda r: r["n_gen"]), 2),
            "none": sum(1 for r in you if r["n_safe"] == 0),
            "none_rate": round(100 * mean(you, lambda r: r["n_safe"] == 0), 1),
            "none_rate_luckyj": round(100 * expect(lambda r: r["n_safe"] == 0), 1)}


def top_choice(game: str, round_name: str) -> list:
    d = json.loads((REPLAYS / f"{game}.json").read_text(encoding="utf-8"))
    hero = d["hero"]
    h = next(h for h in d["hands"] if h["round"] == round_name)
    ais = {a["i"]: a for a in h["ai"]}
    last = max(i for i, x in enumerate(h["ev"]) if x[0] == "d" and x[1] == hero)
    a = ais.get(last - 1) or ais.get(last)
    return [[t, round(p, 3)] for t, p in sorted(a["p"], key=lambda x: -x[1])[:3]] if a else []


def rank_path(new_ids: set[str]) -> dict:
    recs = sorted(json.loads(AMAE.read_text())["records"], key=lambda r: r[1])
    start = next(k for k, r in enumerate(recs) if r[0].startswith(CH29_FIRST))
    score, before_new, path = ANCHOR, None, []
    for r in recs[start:]:
        if r[0] in new_ids and before_new is None:
            before_new = score
        score += next(p for p in r[4] if p[0] == ACCOUNT)[4]
        path.append(score)
        if r[0].startswith(NEW_LAST):
            break
    return {"before_new": before_new, "after_new": score, "change": score - before_new}


def main(rf_you: str, rf_lj: str, esr_you: str, esr_lj: str, vc_you: str, choices_you: str, out: str) -> None:
    os.chdir(ROOT)
    manifest = sorted(json.loads(MANIFEST.read_text(encoding="utf-8")), key=lambda g: g["start_time"])
    win = windows(manifest)
    new = [g for g in manifest if win.get(g["uuid"]) == "new"]
    new_ids = {g["uuid"] for g in new}
    rows = [r for g in new for r in hands_all.work(dict(g, grp="me", lj_seat=g["hero_seat"]))]
    costly = json.loads(COSTLY.read_text())
    result = {
        "window": {"first": new[0]["date"], "last": new[-1]["date"], "games": len(new)},
        "places": {"new": mc.placements(new), "ch29": costly["places"]["recent"], "before": costly["places"]["before"]},
        "hands": {"new": mc.hand_summary(mc.hero_rows(rows, new)), "ch29": costly["hands"]["recent"],
                  "before": costly["hands"]["before"], "luckyj": costly["hands"]["luckyj"]},
        "rank_points": rank_path(new_ids),
    }

    rf = json.loads(Path(rf_you).read_text())["rows"]
    result["riichi"] = {w: riichi([r for r in rf if win.get(r["game"]) == w]) for w in ("before", "ch29", "new")}
    result["riichi"]["luckyj"] = riichi(json.loads(Path(rf_lj).read_text())["rows"])
    for w in ("before", "ch29", "new"):
        s = [r for r in rf if win.get(r["game"]) == w]
        result["riichi"][w]["no_safe_tile"] = round(100 * sum(not r["any_safe"] for r in s) / len(s), 1)

    dealer, fold = json.loads(DEALER.read_text()), json.loads(FOLD.read_text())
    spots = [r for r in cut_rows(vc_you, "You", acceptance(choices_you)) if r["kind"] in fl.CHOICE]
    every = cut_rows(vc_you, "You")
    result["callers"] = {}
    for w in ("before", "ch29", "new"):
        rs = [r for r in every if win.get(r["g"]) == w]
        result["callers"][w] = {"discards": len({(r["g"], r["li"], r["t"]) for r in rs}),
                                "dealt": len({(r["g"], r["li"], r["t"]) for r in rs if r["dealt"] and r["on_wait"]})}
        for hand, keep in (("far", lambda b: b >= 2), ("one", lambda b: b == 1)):
            s = [(r, caller_expected(r, dealer, fold)) for r in spots if win.get(r["g"]) == w and keep(r["best_sh"])]
            s = [(r, e) for r, e in s if e is not None]
            result["callers"][w][hand] = {"turns": len(s), "live": round(100 * sum(r["live"] for r, _ in s) / len(s), 1),
                                          "luckyj": round(sum(e for _, e in s) / len(s), 1)}

    ey = [r for r in json.loads(Path(esr_you).read_text())["rows"] if r["lj_X"]]
    el = [r for r in json.loads(Path(esr_lj).read_text())["rows"] if r["lj_X"]]
    result["held"] = {w: held([r for r in ey if win.get(r["game"]) == w], el) for w in ("before", "ch29", "new")}
    result["held"]["luckyj_riichis"] = len(el)

    replays = [g for g in json.loads((REPLAYS / "index.json").read_text())["games"] if g["id"] in new_ids]
    deals, riichis = mc.deal_ins_and_riichis(replays)
    for d in deals:
        d["mortal_top"] = top_choice(d["game"], d["round"]) if d["kind"] == "cut" else []
    result["mortal"] = mc.rate(replays)
    result["deal_ins"] = sorted(deals, key=lambda d: (d["date"], d["game"]))
    result["deal_in_summary"] = {
        "total": len(deals), "paid": sum(d["paid"] for d in deals),
        "mortal_half": sum(1 for d in deals if d["mortal"] is not None and d["mortal"] >= 0.5),
        "mortal_low": sum(1 for d in deals if d["mortal"] is not None and d["mortal"] < mc.LOW),
    }
    result["riichis"] = {"count": len(riichis), "mortal_low": sum(1 for r in riichis if r["riichi"] < mc.LOW)}
    Path(out + ".tmp").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.replace(out + ".tmp", out)
    for k in ("window", "places", "rank_points", "riichi", "callers", "held", "mortal", "deal_in_summary", "riichis"):
        print(k, json.dumps(result[k], ensure_ascii=False))
    print("hands new", json.dumps(result["hands"]["new"]))
    for d in result["deal_ins"]:
        print(" ", d["date"], d["game"][:15], d["round"], d["kind"], d["tile"], d["paid"], d["mortal"], d["mortal_top"])


if __name__ == "__main__":
    main(*sys.argv[1:8])
