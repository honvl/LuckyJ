#!/usr/bin/env python3
"""The figures behind guide chapter 42: folding more since the peak, and still losing.

Four stretches of the user's 2026 Jade games: before the climb, the climb, and since the peak (chapter 33's
boundaries, from ``mine_climb_check.rank_path``), with the games since chapter 38 (13 October 18:02, the first of the
chapters that told the user to fold a little more) inside the last.

- places and rank points a game, and the fourths against the user's career rate from amae-koromo's player stats;
- hands (``contrast/hands_all.py`` rows through ``mine_costly_run``): wins, deal-ins, big deal-ins (7,000 or more),
  points a hand, riichis; deal-ins by the user's state; LuckyJ's 1,079 Tokujou games beside them;
- defense against a riichi (``mine_riichi_folds.py`` rows) and tenpai push-or-fold (``mine_tenpai_push.py`` rows),
  LuckyJ's from all 1,255 of its games, as in chapter 33;
- riichi at the first closed tenpai against chapter 33's fit of LuckyJ's own rate, and what the tenpais LuckyJ
  declares at 70% or more earned when the user declared and when they kept dama;
- from the site's replays, every hand where Mortal's first rating of riichi reached 90%: how often the user declared
  there;
- the games since chapter 38: every deal-in and every hand kept dama against Mortal's 90% riichi, with Mortal's ratings.

usage: mine_slide_check.py RF_YOU RF_LJ TP_YOU TP_LJ TENPAI_YOU TENPAI_LJ OUT.json
  The same inputs as ``mine_climb_check.py``, over the user's games since 1 January and LuckyJ's games.
"""

from __future__ import annotations

import datetime
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import mine_climb_check as cc  # noqa: E402
import mine_costly_run as mc  # noqa: E402

NEW_SINCE = "2026-10-13 18:02"  # chapter 38's commit
REPLAYS = ROOT / "site" / "replays"
PERIODS = ("before", "climb", "since")
STRONG = 0.9


def career() -> dict:
    """The newest of amae-koromo's player-stats snapshots: the games counted and the rate of fourths."""
    stats = json.loads(cc.AMAE.read_text())["stats"]
    body = [s["body"] for s in stats if s["body"].get("rank_rates")][-1]
    return {"games": body["count"], "fourths": body["rank_rates"][3]}


def placements(career: dict) -> dict:
    rank_rate = career["fourths"]
    recs = sorted(json.loads(cc.AMAE.read_text())["records"], key=lambda r: r[1])
    rank = cc.rank_path()
    start = next(k for k, r in enumerate(recs) if r[0] == rank["start"]["game"])
    peak = next(k for k, r in enumerate(recs) if r[0] == rank["peak"]["game"])
    since = datetime.datetime.fromisoformat(cc.SINCE).timestamp()
    new = datetime.datetime.strptime(NEW_SINCE, "%Y-%m-%d %H:%M").timestamp()
    spans = {"before": [k for k in range(start) if recs[k][1] >= since], "climb": list(range(start, peak + 1)),
             "since": list(range(peak + 1, len(recs))), "new": [k for k in range(len(recs)) if recs[k][1] >= new],
             "2026": [k for k in range(len(recs)) if recs[k][1] >= since]}
    out = {}
    for name, ks in spans.items():
        me = [next(p for p in recs[k][4] if p[0] == cc.ACCOUNT) for k in ks]
        places = [sorted(recs[k][4], key=lambda p: -p[3]).index(m) + 1 for k, m in zip(ks, me)]
        n = len(places)
        fourths = places.count(4)
        sd = math.sqrt(n * rank_rate * (1 - rank_rate))
        out[name] = {"games": n, "places": [places.count(i) for i in (1, 2, 3, 4)],
                     "points_a_game": round(sum(m[4] for m in me) / n, 1), "points": sum(m[4] for m in me),
                     "fourths_expected": round(n * rank_rate, 1), "fourths_sd": round((fourths - n * rank_rate) / sd, 1)}
    return {"career_games": career["games"], "career_fourths": round(100 * rank_rate, 1), "rank": rank, "periods": out}


def mortal_riichi(period: dict[str, str]) -> dict:
    """Per hand, the first decision where Mortal rated riichi at 90% or more: did the user declare there."""
    out = {p: [0, 0] for p in PERIODS}
    dama = []
    for path in sorted(REPLAYS.glob("26*.json")):
        g = json.loads(path.read_text(encoding="utf-8"))
        p = period.get(g["id"])
        if p is None:
            continue
        for h in g["hands"]:
            strong = [a for a in h["ai"] if dict((x, q) for x, q in a.get("p", [])).get("riichi", 0) >= STRONG]
            if not strong:
                continue
            out[p][0] += 1
            out[p][1] += strong[0]["you"] == "riichi"
            if strong[0]["you"] != "riichi":
                dama.append({"game": g["id"], "round": h["round"], "period": p,
                             "riichi": round(dict((x, q) for x, q in strong[0]["p"])["riichi"], 2)})
    return {"hands": {p: {"hands": n, "declared": k, "declared_pct": cc.pct(k, n)} for p, (n, k) in out.items()}, "dama": dama}


def new_games(manifest: list[dict]) -> dict:
    """The games since chapter 38: places, and every deal-in with Mortal's rating of the tile thrown."""
    import tenhou_replay as tr

    import review_win_speed as ws
    from build_personal_guide import meld_snapshots, safety, visible_counter
    from tenhou_replay import base

    new = datetime.datetime.strptime(NEW_SINCE, "%Y-%m-%d %H:%M").timestamp()
    games, folds = [], Counter()
    fold_deal_ins = []
    for g in manifest:
        if g["start_time"] < new:
            continue
        rep = json.loads((REPLAYS / f"{g['uuid']}.json").read_text(encoding="utf-8"))
        hero = g["hero_seat"]
        deal_ins = []
        for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
            game = tr.replay(log)
            h = rep["hands"][li]
            # real folds against a lone riichi: the discard leaves the hand further from tenpai than the best one would
            events = game["events"]
            waits = {e["seat"]: {base(w) for w in tr.waits(e["hand_after"], e["meld_tiles"], e["closed"])} for e in events if e["riichi"]}
            for e in events:
                reached = [q for q in range(4) if q != hero and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
                if e["seat"] != hero or e.get("tile") is None or len(reached) != 1 or e["riichi_seats"][hero] is not None:
                    continue
                hb = e["hand_before"]
                best = min(ws.hand_shanten(hb[:k] + hb[k + 1:], e["meld_tiles"], e["closed"]) for k in range(len(hb)))
                if ws.hand_shanten(e["hand_after"], e["meld_tiles"], e["closed"]) <= best:
                    continue
                q = reached[0]
                snap = meld_snapshots(game, e["index"] - 1)
                snap[hero] = e["melds"]
                seen = visible_counter(hb, e, game["players"], snap, game["dora_indicators"][:1])
                seen[base(e["tile"])] -= 1
                label = safety(e["tile"], q, e, game, seen)
                folds[label] += 1
                if base(e["tile"]) in waits.get(q, set()):
                    fold_deal_ins.append({"game": g["uuid"], "round": game["round_name"], "turn": e["turn"], "label": label})
            win = next((w for w in h["end"].get("wins", []) if w["from"] == hero and w["seat"] != hero), None)
            if not win:
                continue
            last = [e for e in game["events"] if e["seat"] == hero and e.get("tile") is not None][-1]
            turn, tmap = 0, {}
            for i, e in enumerate(h["ev"]):
                if e[1] == hero and ((e[0] == "t" and not (len(e) > 3 and e[3])) or e[0] in ("c", "p", "m")):
                    turn += 1
                tmap[i] = turn
            ai = [a for a in h["ai"] if a.get("p") and tmap.get(a["i"]) == last["turn"] and a["you"] not in ("pass", "riichi")][-1]
            probs = dict(ai["p"])
            riichi = [e["seat"] for e in game["events"] if e["riichi"] and e["index"] < last["index"]]
            deal_ins.append({"round": game["round_name"], "turn": last["turn"],
                             "points": -h["end"]["wins"][0]["deltas"][hero] if len(h["end"]["wins"]) == 1 else None,
                             "value": win["value"], "into": "riichi" if win["seat"] in riichi else "no riichi",
                             "ippatsu": any(y[0] == "ippatsu" for y in win["yaku"]), "mortal_you": round(probs.get(ai["you"], 0.0), 2),
                             "mortal_top": [ai["p"][0][0], round(ai["p"][0][1], 2)], "you": ai["you"]})
        games.append({"game": g["uuid"], "date": g["date"], "placement": rep["placement"][hero] if isinstance(rep["placement"], list) else rep["placement"],
                      "final": rep["final"][hero], "deal_ins": deal_ins})
    return {"games": games, "real_folds": dict(folds), "real_fold_deal_ins": fold_deal_ins}


def main() -> None:
    rf_you, rf_lj, tp_you, tp_lj, tenpai_you, tenpai_lj, out_path = sys.argv[1:8]
    manifest = sorted([g for g in json.loads(cc.MANIFEST.read_text(encoding="utf-8")) if g["date"] >= cc.SINCE],
                      key=lambda g: g["start_time"])
    place = placements(career())
    per = cc.period_of(manifest, place["rank"])
    by = lambda rows, p, key="game": [r for r in rows if per.get(r[key]) == p]

    mine = mc.hero_rows(mc.hand_rows(manifest, "me"), manifest)
    lj_manifest = [g for g in json.loads(cc.LJ_MANIFEST.read_text(encoding="utf-8")) if g["mode"] == "tenhou-tokujou"]
    lj_hands = [r for r in mc.hand_rows(lj_manifest, "lj") if r["lj"]]
    rf, rfl = json.load(open(rf_you))["rows"], json.load(open(rf_lj))["rows"]
    tp, tpl = json.load(open(tp_you))["rows"], json.load(open(tp_lj))["rows"]

    lj_first = [r for r in cc.first_tenpais(tenpai_lj) if r["nr"] == 0]
    beta, _ = cc.fit(lj_first)
    rate = lambda r: float(1 / (1 + np.exp(-np.dot(cc.features(r), beta))))
    you_first = [r for r in cc.first_tenpais(tenpai_you) if r["nr"] == 0]

    riichi = {}
    for p in PERIODS:
        rows = [r for r in you_first if per.get(r["g"]) == p]
        cells = {}
        for name, keep in (("luckyj declares 70% or more", lambda r: rate(r) >= 0.7), ("luckyj declares less", lambda r: rate(r) < 0.7)):
            for how, dec in (("riichi", True), ("dama", False)):
                s = [r for r in rows if keep(r) and bool(r["riichi"]) == dec]
                cells[f"{name}, {how}"] = {"tenpais": len(s), "won": cc.pct(sum(r["won"] for r in s), len(s), 0),
                                           "net": round(sum(r["net"] for r in s) / len(s)) if s else None}
        riichi[p] = dict(cc.declared(rows, rate), outcomes=cells)

    out = {
        "placements": place,
        "hands": {**{p: cc.hands(by(mine, p)) for p in PERIODS}, "luckyj": cc.hands(lj_hands)},
        "deal_ins": {p: cc.deal_ins(by(mine, p)) for p in PERIODS},
        "defense": {"riichi": {**{p: cc.riichi_defense(by(rf, p)) for p in PERIODS}, "luckyj": cc.riichi_defense(rfl)},
                    "tenpai_push": {**{p: cc.tenpai_push(by(tp, p)) for p in PERIODS}, "luckyj": cc.tenpai_push(tpl)}},
        "riichi": riichi,
        "mortal_riichi": mortal_riichi(per),
        "new": new_games(manifest),
    }
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
