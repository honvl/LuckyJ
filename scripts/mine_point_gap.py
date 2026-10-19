#!/usr/bin/env python3
"""The figures behind guide chapter 47: the point gap to LuckyJ before and after the guide's dora chapters.

The user's 216 Jade games since 1 January, split at the first commit of the guide (22 September, 14:17 Eastern): 80
games before it and 136 after, beside the other players at their tables and LuckyJ's 1,079 Tokujou games.

- where a game's points come from (``mine_rank_drain``), the edge over the humans at the same tables, before and after;
- the size of the wins by kind (riichi, dama, open);
- the hands dealt a dora or a red five: tenpai, wins, points won a hand, the win rate of the tenpais, the riichis
  declared at the first closed tenpai, the live tiles of the first tenpai, and what the wins are made of (a shape yaku, a
  flush, the han from dora kept to the win), against the hands dealt none.

usage: mine_point_gap.py OUT.json
"""

from __future__ import annotations

import datetime
import json
import math
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))

import mine_climb_check as cc  # noqa: E402
import mine_costly_run as mc  # noqa: E402
import mine_rank_drain as rd  # noqa: E402

GUIDE = "2026-09-22 14:17"  # the first commit of the guide, Eastern time, as the games' dates are
SHAPE = {"pinfu", "tanyao", "iipeikou", "honitsu", "chinitsu", "toitoi", "sanshoku", "ittsu", "chanta", "junchan", "chiitoi", "sanankou", "shousangen"}
JP = {"ドラ": "dora", "赤ドラ": "red", "裏ドラ": "ura", "立直": "riichi", "ダブル立直": "riichi", "一発": "ippatsu", "門前清自摸和": "tsumo", "平和": "pinfu", "断幺九": "tanyao",
      "役牌 中": "yakuhai", "役牌 白": "yakuhai", "役牌 發": "yakuhai", "役牌:自風牌": "yakuhai", "役牌:場風牌": "yakuhai", "混一色": "honitsu", "清一色": "chinitsu",
      "一盃口": "iipeikou", "七対子": "chiitoi", "三色同順": "sanshoku", "対々和": "toitoi", "混全帯幺九": "chanta", "一気通貫": "ittsu", "三暗刻": "sanankou",
      "海底摸月": "haitei", "河底撈魚": "houtei", "純全帯幺九": "junchan", "嶺上開花": "rinshan", "小三元": "shousangen", "三色同刻": "sanshoku"}
ID = {52: "dora", 54: "red", 53: "ura", 1: "riichi", 21: "riichi", 2: "ippatsu", 0: "tsumo", 7: "pinfu", 8: "tanyao", 9: "iipeikou", 22: "chiitoi", 23: "chanta", 24: "ittsu",
      25: "sanshoku", 26: "sanshoku", 28: "toitoi", 29: "sanankou", 30: "shousangen", 33: "junchan", 34: "honitsu", 35: "chinitsu", 5: "haitei", 6: "houtei", 4: "rinshan",
      3: "chankan", **{i: "yakuhai" for i in range(10, 21)}}


def parse_yaku(detail: list) -> list[tuple[str, int]]:
    """``(yaku, han)`` pairs of one win from the log's detail strings: Mahjong Soul writes Japanese names, Tenhou ``yaku`` numbers."""
    out = []
    for y in detail[4:]:
        m = re.match(r"(.*?)\((\d+)飜\)", y) if isinstance(y, str) else None
        if not m:
            continue
        ident = re.match(r"yaku(\d+)$", m.group(1))
        out.append((ID.get(int(ident.group(1)), "other") if ident else JP.get(m.group(1), "other"), int(m.group(2))))
    return out


def win_rows(job) -> list[dict]:
    """Every win of a game with its yaku, the kind of hand and the dora in the deal."""
    import review_win_speed as ws
    import tenhou_replay as tr

    g, hero_seat = job
    out = []
    for log in tr.load_logs(str(ROOT / g["file"])):
        recs = {r["seat"]: r for r in ws.hand_records(log, set())}
        for deltas, detail in tr.result_blocks(log[-1]):
            s = detail[0]
            if s not in recs:
                continue
            r = recs[s]
            out.append({"game": g["uuid"].split("#")[0], "hero": s == hero_seat, "yaku": parse_yaku(detail), "points": deltas[s], "haipai_dora": r["haipai_dora"],
                        "kind": "riichi" if r["riichi_turn"] is not None else "open" if r["open"] else "dama"})
    return out


def yaku_rows(manifest: list[dict]) -> list[dict]:
    seen = {}
    for g in manifest:
        seen.setdefault(g["file"], g)
    with Pool(10) as pool:
        res = pool.map(win_rows, [(g, g["hero_seat"]) for g in seen.values()], chunksize=6)
    return [r for chunk in res for r in chunk]


def dora_wins(rows: list[dict]) -> dict:
    """What the wins in hands dealt a dora are made of."""
    n = len(rows)
    if not n:
        return {"wins": 0}
    han = lambda r, names: sum(h for c, h in r["yaku"] if c in names)  # noqa: E731
    return {"wins": n, "shape_yaku_pct": round(100 * sum(1 for r in rows if any(c in SHAPE for c, _ in r["yaku"])) / n, 1),
            "flush_pct": round(100 * sum(1 for r in rows if any(c in ("honitsu", "chinitsu") for c, _ in r["yaku"])) / n, 1),
            "han": round(float(np.mean([sum(h for _, h in r["yaku"]) for r in rows])), 2), "dora_han": round(float(np.mean([han(r, ("dora", "red")) for r in rows])), 2),
            "mangan_or_more_pct": round(100 * sum(r["points"] >= 7700 for r in rows) / n, 1),
            "kept_all_dealt_pct": round(100 * sum(han(r, ("dora", "red")) >= r["haipai_dora"] for r in rows) / n)}


def deal_state(rows: list[dict], at_least: int | None = None, exactly: int | None = None) -> dict:
    """One line for the hands dealt a given number of dora: tenpai, wins and what a hand earns."""
    pick = (lambda r: r["haipai_dora"] >= at_least) if at_least is not None else (lambda r: r["haipai_dora"] == exactly)
    s = [r for r in rows if pick(r)]
    n = len(s)
    wins = [r for r in s if r["won"]]
    tenpai = [r for r in s if r["tenpai_turn"] is not None]
    first = [r for r in s if r["first_closed_tenpai"] and not r["first_closed_tenpai"]["threat"]]
    live = [r for r in tenpai if r["tenpai_live"] is not None]
    return {"hands": n, "tenpai_pct": round(100 * len(tenpai) / n, 1), "won_pct": round(100 * len(wins) / n, 1),
            "won_of_tenpai_pct": round(100 * sum(r["won"] for r in tenpai) / len(tenpai), 1), "average_win": round(float(np.mean([r["win_pts"] for r in wins]))),
            "average_win_se": round(float(np.std([r["win_pts"] for r in wins], ddof=1) / math.sqrt(len(wins)))),
            "win_points_a_hand": round(sum(r["win_pts"] for r in s) / n), "win_points_a_hand_se": round(float(np.std([r["win_pts"] for r in s], ddof=1) / math.sqrt(n))),
            "hands_a_game": round(n / len({(r["game"], r["seat"]) for r in rows}), 2), "first_tenpais_with_a_quiet_table": len(first),
            "declared_pct": round(100 * sum(r["first_closed_tenpai"]["declared"] for r in first) / len(first), 1),
            "live_tiles_at_the_first_tenpai": round(float(np.mean([r["tenpai_live"] for r in live])), 2)}


def main() -> None:
    out_path = sys.argv[1]
    per_1000 = json.loads(rd.THIN.read_text())["cost"]["rank_points_per_1000_points"]
    manifest = sorted([g for g in json.loads(cc.MANIFEST.read_text(encoding="utf-8")) if g["date"] >= cc.SINCE], key=lambda g: g["start_time"])
    lj_manifest = [g for g in json.loads(cc.LJ_MANIFEST.read_text(encoding="utf-8")) if g["mode"] == "tenhou-tokujou"]
    guide = datetime.datetime.strptime(GUIDE, "%Y-%m-%d %H:%M").timestamp()
    stretch = {g["uuid"].split("#")[0]: "before" if g["start_time"] < guide else "since" for g in manifest}
    hero_you = {g["uuid"].split("#")[0]: g["hero_seat"] for g in manifest}
    hero_lj = {g["uuid"].split("#")[0]: g["hero_seat"] for g in lj_manifest}

    rows_you, rows_lj = mc.hand_rows(manifest, "me"), mc.hand_rows(lj_manifest, "lj")
    mine = [r for r in rows_you if r["seat"] == hero_you[r["game"]]]
    jade = [r for r in rows_you if r["seat"] != hero_you[r["game"]]]
    lucky = [r for r in rows_lj if r["seat"] == hero_lj[r["game"]]]
    by = lambda rows, name: [r for r in rows if stretch[r["game"]] == name]  # noqa: E731

    # --- where the points come from, before and after the guide ---------------------------------------------
    sg_you, sg_lj = rd.seat_games(rows_you, hero_you), rd.seat_games(rows_lj, hero_lj)
    comp = {f"{who}_{name}": rd.components(sg_you, lambda k, c, who=who, name=name: c["hero"] == (who == "you") and stretch[k[0]] == name) for who in ("you", "jade") for name in ("before", "since")}
    comp["luckyj"] = rd.components(sg_lj, lambda k, c: c["hero"])
    comp["tokujou_human"] = rd.components(sg_lj, lambda k, c: not c["hero"])
    edges = {name: rd.edge(comp[f"you_{name}"], comp[f"jade_{name}"], per_1000) for name in ("before", "since")}
    edges["luckyj"] = rd.edge(comp["luckyj"], comp["tokujou_human"], per_1000)
    gap = {}
    for name in ("before", "since"):
        points = edges["luckyj"]["win"]["points"] - edges[name]["win"]["points"]
        gap[name] = {"wins_points": points, "se": round(math.hypot(edges[name]["win"]["se"], edges["luckyj"]["win"]["se"])), "rank_points": round(points * per_1000 / 1000, 1),
                     "deal_ins_points": edges["luckyj"]["deal_ins"]["points"] - edges[name]["deal_ins"]["points"]}

    wins = {name: rd.win_sizes(by(mine, name)) for name in ("before", "since")}
    wins["luckyj"] = rd.win_sizes(lucky)
    wins["jade_human"] = rd.win_sizes(jade)

    # --- hands dealt dora -------------------------------------------------------------------------------------
    dealt = {}
    for label, rows in (("you_before", by(mine, "before")), ("you_since", by(mine, "since")), ("you", mine), ("jade_human", jade), ("luckyj", lucky)):
        dealt[label] = {"no_dora": deal_state(rows, exactly=0), "dora": deal_state(rows, at_least=1), "two_or_more": deal_state(rows, at_least=2)}
    wr = yaku_rows(manifest) + yaku_rows(lj_manifest)
    lj_ids = {g["uuid"].split("#")[0] for g in lj_manifest}
    sel = lambda pred: [r for r in wr if r["haipai_dora"] >= 1 and pred(r)]  # noqa: E731
    shape = {"you_before": dora_wins(sel(lambda r: r["game"] in stretch and r["hero"] and stretch[r["game"]] == "before")),
             "you_since": dora_wins(sel(lambda r: r["game"] in stretch and r["hero"] and stretch[r["game"]] == "since")),
             "jade_human": dora_wins(sel(lambda r: r["game"] in stretch and not r["hero"])), "luckyj": dora_wins(sel(lambda r: r["game"] in lj_ids and r["hero"]))}
    kept = {}
    for k, who in (("you", lambda r: r["game"] in stretch and r["hero"]), ("jade_human", lambda r: r["game"] in stretch and not r["hero"]), ("luckyj", lambda r: r["game"] in lj_ids and r["hero"])):
        kept[k] = {}
        for lab, cond in (("one", lambda r: r["haipai_dora"] == 1), ("two_or_more", lambda r: r["haipai_dora"] >= 2)):
            s = [r for r in wr if who(r) and cond(r)]
            kept[k][lab] = {"wins": len(s), "kept_all_pct": round(100 * sum(sum(h for c, h in r["yaku"] if c in ("dora", "red")) >= r["haipai_dora"] for r in s) / len(s))}

    d_you, d_lj = dealt["you_since"]["dora"], dealt["luckyj"]["dora"]
    per_hand = d_lj["win_points_a_hand"] - d_you["win_points_a_hand"]
    a_game = round(per_hand * d_you["hands_a_game"])
    gap_dora = {"points_a_hand": per_hand, "se_a_hand": round(math.hypot(d_you["win_points_a_hand_se"], d_lj["win_points_a_hand_se"])), "points_a_game": a_game,
                "se_a_game": round(math.hypot(d_you["win_points_a_hand_se"], d_lj["win_points_a_hand_se"]) * d_you["hands_a_game"]),
                "rank_points_a_game": round(a_game * per_1000 / 1000, 1)}
    out = {"guide": GUIDE, "games": {n: sum(1 for v in stretch.values() if v == n) for n in ("before", "since")}, "rank_points_per_1000_points": per_1000,
           "components": comp, "edges": edges, "gap_on_wins": gap, "gap_on_dora_hands": gap_dora, "wins": wins, "dealt": dealt, "dora_wins": shape, "kept": kept,
           "six_cuts": {"points": 68200, "games": 67, "points_a_game": round(68200 / 67), "rank_points_a_game": round(68200 / 67 * per_1000 / 1000, 1)}}
    Path(out_path).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
