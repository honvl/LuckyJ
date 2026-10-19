#!/usr/bin/env python3
"""Riichis with five or fewer live tiles: what the waits look like to the table, and what happens to them.

At every riichi declaration, at every seat of the user's Jade games and LuckyJ's Tokujou games, this records:

- the waits after the declaration discard: each winning tile, the copies unseen from the declarer's seat (``live`` is
  their sum), and how safe that tile looks to the other players against the declarer's river, including the
  declaration tile (``build_personal_guide.suji_label``: suji, nakasuji, half suji, a live 4-5-6, an honor...);
- how many tiles one or two ranks from each wait tile the other players had thrown (``near``);
- the shape, whether the wait is furiten, the discards that would also have left tenpai and the most live tiles among
  them;
- how many of those unseen copies the other players held in their closed hands at that moment (``held``; the rest are
  in the wall, live or dead), and how many of the other players were tenpai then (``opp_tenpai``, ``opp_shanten``);
- the table: riichis already out, the most calls at any other seat, the dealer, the turn, the wall left;
- the exposures: every discard by another player after the declaration up to the hand's end or the first discard of a
  winning tile, and the wait tiles among them;
- the outcome: whether the declarer won (by ron or tsumo), dealt in, and the points moved.

``report`` turns those rows into the chapter's figures: thin (five or fewer live tiles) and wide riichis for the four
groups, a logistic model of winning fitted on the humans at both tables (live tiles, turn, dealer, calls, opponents
tenpai) against each group, the tile choices (the best wait taken at the first tenpai, a cut that gave up live tiles
at the declaration, a wait changed to fewer live tiles while dama; the last two from ``contrast/tenpai.py`` rows),
where the wait tiles were, how often the table threw them, furiten riichis, and what the gap costs in points and rank
points a game (rank points per 1,000 points from a straight-line fit over the user's amae-koromo records).

usage: mine_thin_riichi.py compute YOUR_MANIFEST.json OUT.json
       mine_thin_riichi.py report RIICHIS.json TENPAI_YOU.jsonl TENPAI_LJ.jsonl OUT.json
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

LJ_MANIFEST = ROOT / "data/local_sources/luckyj_tenhou/index.json"
SAFE_LOOKING = ("suji", "nakasuji", "virtual nakasuji", "live honor", "honor, 2 seen")


def wait_label(w: int, e: dict, river: list[int], public) -> str:
    """How safe the winning tile ``w`` looks to the other players against the declarer's river."""
    from build_personal_guide import SOTOGAWA_EARLY, suji_label
    from tenhou_replay import is_honor, is_terminal

    ref = set(river)
    if w in ref:
        return "furiten"
    if is_honor(w):
        n = public[w]
        return "dead" if n >= 3 else "honor, 2 seen" if n == 2 else "live honor"
    label = suji_label(w, ref, set(river[:SOTOGAWA_EARLY]))
    if label:
        return label
    if is_terminal(w):
        return "live terminal"
    return "live 2-3-7-8" if w % 10 in (2, 3, 7, 8) else "live 4-5-6"


def game_rows(job) -> list[dict]:
    g, table = job
    import review_win_speed as ws
    import tenhou_replay as tr
    from build_personal_guide import draws_so_far, meld_snapshots, visible_counter
    from tenhou_replay import base
    from tenpai import wait_shape

    hero, out = g["hero_seat"], []
    for li, log in enumerate(tr.load_logs(str(ROOT / g["file"]))):
        game = tr.replay(log)
        events, players = game["events"], game["players"]
        indicators = game["dora_indicators"][:1]
        blocks = tr.result_blocks(log[-1])
        winners = {d[0]: d[1] != d[0] for _, d in blocks}  # winner -> won by ron
        losers = {d[1] for _, d in blocks if d[0] != d[1]}
        deltas, paid = tr.result_deltas(log[-1]), tr.riichi_sticks_paid(log)
        for k, e in enumerate(events):
            if not e["riichi"]:
                continue
            s = e["seat"]
            hand13 = e["hand_after"]
            waits = sorted({base(w) for w in tr.waits(hand13, e["meld_tiles"], True)})
            if not waits:
                continue
            snap = meld_snapshots(game, e["index"] - 1)
            snap[s] = e["melds"]
            vis = visible_counter(hand13, e, players, snap, indicators)
            vis[base(e["tile"])] += 1
            public = visible_counter([], e, players, snap, indicators)
            public[base(e["tile"])] += 1
            river = [base(x) for x in e["rivers"][s]] + [base(e["tile"])]
            others = [base(x) for q in range(4) if q != s for x in e["rivers"][q]]
            tiles = [{"tile": w, "unseen": max(0, 4 - vis[w]), "label": wait_label(w, e, river, public),
                      "near": sum(1 for x in others if w < 40 and x < 40 and x // 10 == w // 10 and abs(x - w) in (1, 2))} for w in waits]
            # how many of the unseen copies the other players were holding in their closed hands at the declaration
            held, opp_tenpai, opp_shanten = 0, 0, []
            for q in range(4):
                if q == s:
                    continue
                last = next((x for x in reversed(events[:k + 1]) if x["seat"] == q), None)
                hand_q = last["hand_after"] if last is not None else players[q]["haipai"]
                held += sum(1 for x in hand_q if base(x) in waits)
                if last is not None:
                    sh = ws.hand_shanten(hand_q, last["meld_tiles"], last["closed"])
                    opp_shanten.append(sh)
                    opp_tenpai += sh == 0
            # the other discards that would have left tenpai
            hb = e["hand_before"]
            alts = []
            vis_before = visible_counter(hb, e, players, snap, indicators)
            for t in {base(x): x for x in hb}.values():
                rest = list(hb)
                rest.remove(t)
                if base(t) == base(e["tile"]) or ws.hand_shanten(rest, e["meld_tiles"], True) != 0:
                    continue
                aw = sorted({base(w) for w in tr.waits(rest, e["meld_tiles"], True)})
                alts.append(sum(max(0, 4 - vis_before[w]) for w in aw))
            # what the other players discarded after the declaration
            exposures, released = 0, 0
            for j in range(k + 1, len(events)):
                o = events[j]
                if o["seat"] == s or o.get("tile") is None:
                    continue
                exposures += 1
                if base(o["tile"]) in waits and not any(t["label"] == "furiten" for t in tiles if t["tile"] == base(o["tile"])):
                    released += 1
                    break
            rseats = [q for q in range(4) if q != s and e["riichi_seats"][q] is not None and e["riichi_seats"][q] < e["index"]]
            opens = [sum(1 for m in players[q]["melds"][: e["meld_counts"][q]] if m["kind"] != "a") for q in range(4) if q != s]
            who = ("luckyj" if s == hero else "tokujou_human") if table == "tenhou" else ("you" if s == hero else "jade_human")
            out.append({"game": g["uuid"], "li": li, "round": game["round_name"], "who": who, "seat": s, "turn": e["turn"],
                        "left": 70 - draws_so_far(game, e["index"]), "dealer": s == game["dealer"],
                        "waits": tiles, "live": sum(t["unseen"] for t in tiles), "shape": wait_shape(hand13, waits),
                        "held": held, "opp_tenpai": opp_tenpai, "opp_shanten": opp_shanten, "furiten": any(t["label"] == "furiten" for t in tiles), "alt_live_max": max(alts) if alts else None,
                        "riichis_out": len(rseats), "max_calls": max(opens), "exposures": exposures, "released": released,
                        "won": s in winners, "ron": winners.get(s) is True, "tsumo": winners.get(s) is False, "dealt": s in losers,
                        "net": deltas[s] - 1000 * paid[s]})
    return out


def compute(your_manifest: str, out: str) -> None:
    os.chdir(ROOT)
    you = json.load(open(your_manifest))
    lj = json.loads(LJ_MANIFEST.read_text(encoding="utf-8"))
    jobs = [(g, "jade") for g in you] + [(g, "tenhou") for g in lj]
    rows = []
    with Pool(12) as pool:
        for part in pool.imap(game_rows, jobs, chunksize=4):
            rows.extend(part)
    Path(out).write_text(json.dumps(rows) + "\n")
    print(f"wrote {out}: {len(rows)} riichi declarations")


GROUPS = ("you", "jade_human", "luckyj", "tokujou_human")
HUMANS = ("jade_human", "tokujou_human")
THIN = 5


def pct(k: float, n: float, digits: int = 1) -> float | None:
    return round(100 * k / n, digits) if n else None


def stats(rows: list[dict]) -> dict:
    n = len(rows)
    return {"n": n, "won": pct(sum(r["won"] for r in rows), n), "ron": pct(sum(r["ron"] for r in rows), n),
            "tsumo": pct(sum(r["tsumo"] for r in rows), n), "dealt": pct(sum(r["dealt"] for r in rows), n),
            "net": round(sum(r["net"] for r in rows) / n) if n else None}


def features(r: dict) -> list[float]:
    return [1.0, min(r["live"], 10) - 5, max(0, r["live"] - 10), r["turn"] - 9, max(0, r["turn"] - 12), float(r["dealer"]),
            float(r["max_calls"] >= 1), float(r["max_calls"] >= 2), min(r["opp_tenpai"], 2)]


def fit_logistic(rows: list[dict]):
    import numpy as np

    x = np.array([features(r) for r in rows])
    y = np.array([float(r["won"]) for r in rows])
    beta = np.zeros(x.shape[1])
    for _ in range(100):
        mu = 1 / (1 + np.exp(-(x @ beta)))
        step = np.linalg.solve((x.T * (mu * (1 - mu))) @ x + 1e-3 * np.eye(x.shape[1]), x.T @ (y - mu) - 1e-3 * beta)
        beta += step
        if np.max(np.abs(step)) < 1e-9:
            break
    return beta


def model_check(alone: list[dict]) -> dict:
    import numpy as np

    beta = fit_logistic([r for r in alone if r["who"] in HUMANS])
    out = {"fitted_on": sum(1 for r in alone if r["who"] in HUMANS),
           "terms": dict(zip(("constant", "live tiles to 10", "live tiles over 10", "turn from 9", "turns past 12", "dealer",
                              "a caller", "two callers", "opponents tenpai"), [round(float(b), 2) for b in beta]))}
    for name, keep in (("thin", lambda r: r["live"] <= THIN), ("thin from turn 8", lambda r: r["live"] <= THIN and r["turn"] >= 8),
                       ("six or more live", lambda r: r["live"] > THIN)):
        out[name] = {}
        for who in GROUPS:
            s = [r for r in alone if r["who"] == who and keep(r)]
            p = 1 / (1 + np.exp(-(np.array([features(r) for r in s]) @ beta)))
            actual = float(np.mean([r["won"] for r in s]))
            sd = float(np.sqrt((p * (1 - p)).sum()) / len(s))
            out[name][who] = {"n": len(s), "actual": pct(actual, 1), "model": pct(float(p.mean()), 1), "sd": round((actual - float(p.mean())) / sd, 1),
                              "wins": sum(r["won"] for r in s), "expected_wins": round(float(p.sum()), 1)}
    return out


SAFE_HALF = (("suji", "nakasuji", "virtual nakasuji", "live honor", "honor, 2 seen"), ("half suji", "live terminal"))


def label_shares(r: dict) -> list[float]:
    live = max(1, r["live"])
    return [sum(t["unseen"] for t in r["waits"] if t["label"] in group) / live for group in SAFE_HALF]


def near_per_tile(r: dict) -> float:
    return sum(t["near"] * t["unseen"] for t in r["waits"]) / max(1, r["live"])


def extra_checks(alone: list[dict]) -> dict:
    """What the model gains from how safe the wait tiles look to the table, and from the tiles thrown beside the wait."""
    import numpy as np

    def fit(rows, make):
        x = np.array([make(r) for r in rows])
        y = np.array([float(r["won"]) for r in rows])
        beta = np.zeros(x.shape[1])
        for _ in range(100):
            mu = 1 / (1 + np.exp(-(x @ beta)))
            h = (x.T * (mu * (1 - mu))) @ x + 1e-3 * np.eye(x.shape[1])
            step = np.linalg.solve(h, x.T @ (y - mu) - 1e-3 * beta)
            beta += step
            if np.max(np.abs(step)) < 1e-9:
                break
        mu = 1 / (1 + np.exp(-(x @ beta)))
        se = np.sqrt(np.diag(np.linalg.inv((x.T * (mu * (1 - mu))) @ x)))
        return beta, se

    humans = [r for r in alone if r["who"] in HUMANS]
    with_labels = lambda r: features(r) + label_shares(r)
    beta, _ = fit(humans, with_labels)
    out = {"labels": {}}
    base_beta = fit_logistic(humans)
    for who in ("you", "luckyj"):
        s = [r for r in alone if r["who"] == who and r["live"] <= THIN and r["turn"] >= 8]
        out["labels"][who] = {"without": pct(float(np.mean(1 / (1 + np.exp(-(np.array([features(r) for r in s]) @ base_beta))))), 1),
                              "with": pct(float(np.mean(1 / (1 + np.exp(-(np.array([with_labels(r) for r in s]) @ beta))))), 1)}
    out["safe_looking_share_of_live_tiles"] = {w: pct(sum(label_shares(r)[0] * r["live"] for r in alone if r["who"] == w and r["live"] <= THIN),
                                                      sum(r["live"] for r in alone if r["who"] == w and r["live"] <= THIN)) for w in GROUPS}
    thin = [r for r in humans if r["live"] <= THIN]
    b, se = fit(thin, lambda r: [1.0, r["live"] - 4, r["turn"] - 9, near_per_tile(r)])
    out["near"] = {"coefficient": round(float(b[3]), 3), "se": round(float(se[3]), 3), "riichis": len(thin)}
    return out


def tenpai_choices(you_path: str, lj_path: str) -> dict:
    """The first tenpai, the cut that kept the most live tiles, and the wait changed while dama (contrast/tenpai.py rows)."""
    from collections import defaultdict

    sets = {"you": (you_path, True), "jade_human": (you_path, False), "luckyj": (lj_path, True), "tokujou_human": (lj_path, False)}
    cache: dict[str, list[dict]] = {}
    out = {}
    for who, (path, hero) in sets.items():
        if path not in cache:
            cache[path] = [json.loads(line) for line in open(path)]
        rows = [r for r in cache[path] if r["lj"] == hero]
        chosen = lambda r: next((o for o in r["opts"] if o["b"] == r["cut"]), None)
        first = [r for r in rows if r["first"] and r["nr"] == 0 and r["kept"] and chosen(r)]
        best = [max(o["live"] for o in r["opts"]) for r in first]
        taken = [chosen(r)["live"] for r in first]
        seqs = defaultdict(list)
        for r in rows:
            seqs[(r["g"], r["li"], r["s"])].append(r)
        same = fewer = more = total = 0
        for seq in seqs.values():
            prev = None
            for r in seq:
                c = chosen(r)
                if prev is not None and prev["kept"] and not prev["riichi"] and chosen(prev) is not None and c is not None:
                    keep = next((o for o in r["opts"] if o["waits"] == chosen(prev)["waits"]), None)
                    if keep is not None:
                        total += 1
                        if c["waits"] == chosen(prev)["waits"]:
                            same += 1
                        elif c["live"] < keep["live"]:
                            fewer += 1
                        elif c["live"] > keep["live"]:
                            more += 1
                prev = r
        out[who] = {"first_tenpais": len(first), "best_available_live": round(sum(best) / len(best), 2), "taken_live": round(sum(taken) / len(taken), 2),
                    "dama_decisions": total, "kept_wait_pct": pct(same, total), "to_more_live_pct": pct(more, total), "to_fewer_live_pct": pct(fewer, total)}
    return out


def report(riichis_path: str, you_path: str, lj_path: str, out: str) -> None:
    import numpy as np

    os.chdir(ROOT)
    rows = json.loads(Path(riichis_path).read_text())
    manifest = [g for g in json.loads((ROOT / "data/self_games/majsoul/index.json").read_text(encoding="utf-8")) if g["date"] >= "2026-01-01"]
    alone = [r for r in rows if r["riichis_out"] == 0 and not r["furiten"]]
    result = {"riichis": len(rows), "games": len(manifest), "alone": {w: sum(1 for r in alone if r["who"] == w) for w in GROUPS}}
    result["thin"] = {w: {"all": stats([r for r in alone if r["who"] == w and r["live"] <= THIN]),
                          "from_turn_8": stats([r for r in alone if r["who"] == w and r["live"] <= THIN and r["turn"] >= 8])} for w in GROUPS}
    result["wide"] = {w: stats([r for r in alone if r["who"] == w and r["live"] > THIN]) for w in GROUPS}
    result["model"] = model_check(alone)
    result["model"]["extra"] = extra_checks(alone)
    result["opponents_tenpai"] = {
        "humans_thin_win": {str(k): {"n": len(s), "won": pct(sum(r["won"] for r in s), len(s))} for k in (0, 1, 2)
                            for s in [[r for r in alone if r["who"] in HUMANS and r["live"] <= THIN and min(r["opp_tenpai"], 2) == k]]},
        "none_tenpai_share": {w: pct(sum(1 for r in alone if r["who"] == w and r["live"] <= THIN and r["opp_tenpai"] == 0),
                                     sum(1 for r in alone if r["who"] == w and r["live"] <= THIN)) for w in GROUPS}}
    thin8 = {w: [r for r in alone if r["who"] == w and r["live"] <= THIN and r["turn"] >= 8] for w in GROUPS}
    result["luck"] = {w: {"unseen_copies": sum(r["live"] for r in thin8[w]), "held_by_opponents": sum(r["held"] for r in thin8[w]),
                          "held_pct": pct(sum(r["held"] for r in thin8[w]), sum(r["live"] for r in thin8[w])),
                          "in_the_wall_per_riichi": round(sum(r["live"] - r["held"] for r in thin8[w]) / len(thin8[w]), 2)} for w in GROUPS}
    result["released"] = {}
    for w in GROUPS:
        rel = sum(r["released"] for r in thin8[w])
        x = sum(r["held"] * r["exposures"] for r in thin8[w])
        result["released"][w] = {"releases": rel, "per_100_held_copy_discards": round(100 * rel / x, 2)}
    humans = [r for w in HUMANS for r in thin8[w]]
    h = sum(r["released"] for r in humans) / sum(r["held"] * r["exposures"] for r in humans)
    yours = sum(r["held"] * r["exposures"] for r in thin8["you"])
    result["released"]["expected_for_you_at_the_humans_rate"] = round(h * yours, 1)
    result["choices"] = tenpai_choices(you_path, lj_path)
    gave_up = {}
    for w in GROUPS:
        thin = [r for r in rows if r["who"] == w and r["live"] <= THIN and not r["furiten"]]
        gave_up[w] = {"declarations": len(thin), "better_cut_existed": sum(1 for r in thin if (r["alt_live_max"] or 0) > r["live"])}
    result["choices"]["gave_up_live_tiles_at_the_declaration"] = gave_up
    result["furiten"] = {w: {"riichis": sum(1 for r in rows if r["who"] == w), "furiten": sum(1 for r in rows if r["who"] == w and r["furiten"]),
                             "won": sum(1 for r in rows if r["who"] == w and r["furiten"] and r["won"])} for w in GROUPS}
    # what the gap is worth
    amae = json.loads((ROOT / "data/self_games/majsoul/amae-koromo-records.json").read_text())["records"]
    score, delta = [], []
    for rec in amae:
        me = next(p for p in rec[4] if p[0] == 120182062)
        score.append(me[3])
        delta.append(me[4])
    slope = float(np.polyfit(np.array(score, float), np.array(delta, float), 1)[0]) * 1000
    t8 = result["thin"]
    humans_net = sum(t8[w]["from_turn_8"]["net"] * t8[w]["from_turn_8"]["n"] for w in HUMANS) / sum(t8[w]["from_turn_8"]["n"] for w in HUMANS)
    n_you = t8["you"]["from_turn_8"]["n"]
    sd = float(np.std([r["net"] for r in thin8["you"]]))
    result["cost"] = {"rank_points_per_1000_points": round(slope, 1), "records_fitted": len(score), "your_riichis_per_game": round(n_you / len(manifest), 2),
                      "net_per_riichi": {"you": t8["you"]["from_turn_8"]["net"], "humans": round(humans_net), "luckyj": t8["luckyj"]["from_turn_8"]["net"]},
                      "standard_error_of_yours": round(sd / n_you ** 0.5),
                      "points_a_game_against_humans": round((t8["you"]["from_turn_8"]["net"] - humans_net) * n_you / len(manifest)),
                      "points_a_game_against_luckyj": round((t8["you"]["from_turn_8"]["net"] - t8["luckyj"]["from_turn_8"]["net"]) * n_you / len(manifest))}
    result["cost"]["rank_points_a_game_against_humans"] = round(result["cost"]["points_a_game_against_humans"] * slope / 1000, 1)
    result["cost"]["rank_points_a_game_against_luckyj"] = round(result["cost"]["points_a_game_against_luckyj"] * slope / 1000, 1)
    examples = {}
    for key, game, rnd in (("wait_held", "261008-ce956cd8", "East 1-1"), ("wall_empty", "261003-d9683a26", "South 4-0")):
        r = next(x for x in rows if x["who"] == "you" and x["game"].startswith(game) and x["round"] == rnd and x["live"] <= THIN and x["turn"] >= 8)
        examples[key] = {"game": r["game"], "round": r["round"], "turn": r["turn"], "live": r["live"], "held": r["held"], "in_the_wall": r["live"] - r["held"],
                         "won": r["won"], "dealt": r["dealt"], "net": r["net"], "waits": [t["tile"] for t in r["waits"]]}
    result["examples"] = examples
    Path(out).write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        compute(*sys.argv[2:4])
    else:
        report(*sys.argv[2:6])
