#!/usr/bin/env python3
import csv
import gzip
import json
import math
import re
import statistics
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


SHEET_CSV = Path("data/LuckyJ.csv")
CACHE_DIR = Path("data/report_cache")
OUT_PATH = Path("data/luckyj_analysis.json")

TILES = [
    "1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m",
    "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
    "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s",
    "E", "S", "W", "N", "P", "F", "C",
]
IDX = {tile: idx for idx, tile in enumerate(TILES)}
IDX.update({"5mr": IDX["5m"], "5pr": IDX["5p"], "5sr": IDX["5s"]})
HURO_TYPES = {"chi", "pon", "daiminkan"}


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def pct(num, den):
    return 100.0 * num / den if den else None


def parse_float(row, key):
    value = (row.get(key) or "").strip()
    return float(value) if value else None


def parse_rows():
    rows = []
    with SHEET_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                idx = int(float((row.get("#") or "").strip()))
                rank = int(float((row.get("Rank") or "").strip()))
                actor = int(float((row.get("Actor") or "").strip()))
            except ValueError:
                continue
            report = row.get("NAGA Report") or ""
            if not report.startswith("http"):
                continue
            report_id = report_id_from_url(report)
            score_match = re.search(r"ⓝLuckyJ\(([+\-]?[0-9.]+)\)", row.get("Players") or "")
            rows.append(
                {
                    "idx": idx,
                    "date": row.get("Date") or "",
                    "rank": rank,
                    "actor": actor,
                    "score": float(score_match.group(1)) if score_match else None,
                    "moves": int(float(row["Moves"])) if row.get("Moves") else None,
                    "report": report,
                    "paifu": row.get("Paifu") or "",
                    "report_id": report_id,
                    "n_match": parse_float(row, "N-Match"),
                    "n_rating": parse_float(row, " N-Rating"),
                    "n_bad": parse_float(row, "N-Bad"),
                    "h_match": parse_float(row, "H-Match"),
                    "h_rating": parse_float(row, "H-Rating"),
                    "h_bad": parse_float(row, "H-Bad"),
                    "k_match": parse_float(row, "K-Match"),
                    "k_rating": parse_float(row, "K-Rating"),
                    "k_bad": parse_float(row, "K-Bad"),
                }
            )
    return rows


def report_id_from_url(url):
    match = re.search(r"report_id=([^&]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"/htmls/([^/?]+)\.html", url)
    if match:
        return match.group(1)
    raise ValueError(f"cannot parse report id: {url}")


def fetch_report(report_id):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{report_id}.json.gz"
    if cache_path.exists() and cache_path.stat().st_size > 0:
        raw = cache_path.read_bytes()
    else:
        url = f"https://naga.dmv.nico/reports/{report_id}.json.gz"
        req = urllib.request.Request(url, headers={"User-Agent": "Codex analysis", "Accept-Encoding": "gzip"})
        with urllib.request.urlopen(req, timeout=60) as response:
            raw = response.read()
        cache_path.write_bytes(raw)
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def normalize_report(data):
    pred = data["pred"]
    first = pred[0][1] if len(pred[0]) > 1 else {}
    old_dahai = first.get("dahai_pred") and first["dahai_pred"] and not isinstance(first["dahai_pred"][0], list)
    if old_dahai:
        for kyoku in pred:
            for state in kyoku:
                if "dahai_pred" in state:
                    state["dahai_pred"] = [state["dahai_pred"]]
                msg = state.get("info", {}).get("msg", {})
                if "pred_dahai" in msg and (not msg["pred_dahai"] or not isinstance(msg["pred_dahai"], list)):
                    msg["pred_dahai"] = [msg["pred_dahai"]]
                if "huro" in state:
                    for seat in list(state["huro"]):
                        if state["huro"][seat] and isinstance(state["huro"][seat], dict):
                            state["huro"][seat] = [state["huro"][seat]]
                if "kan" in state and state["kan"] and isinstance(state["kan"], dict):
                    state["kan"] = [state["kan"]]
                if "reach" in state and not isinstance(state["reach"], list):
                    state["reach"] = [state["reach"]]
    if "naga_types" in data and data["naga_types"]:
        return [data["naga_types"].get(str(i), str(i)) for i in range(len(data["naga_types"]))]
    return ["NAGA"]


def tile_index(tile):
    return IDX[tile]


def tile_class(tile):
    base = tile.replace("r", "")
    if base in {"E", "S", "W", "N", "P", "F", "C"}:
        return "honor"
    if base[0] in {"1", "9"}:
        return "terminal"
    return "simple"


def tile_base(tile):
    return tile.replace("r", "")


def suited_rank(tile):
    base = tile_base(tile)
    if len(base) != 2 or base[1] not in {"m", "p", "s"}:
        return None
    return int(base[0]), base[1]


def suji_source_tiles(tile):
    parsed = suited_rank(tile)
    if not parsed:
        return []
    rank, suit = parsed
    sources = []
    if rank - 3 >= 1:
        sources.append(f"{rank - 3}{suit}")
    if rank + 3 <= 9:
        sources.append(f"{rank + 3}{suit}")
    return sources


def defensive_tile_read(tile, target, discards, reached=None, open_melds=None):
    reached = reached or [False, False, False, False]
    open_melds = open_melds or [0, 0, 0, 0]
    partners = set(suji_source_tiles(tile))
    tile_idx = tile_index(tile)
    against = []

    for seat, river in enumerate(discards or []):
        if seat == target:
            continue
        genbutsu_sources = []
        suji_sources = []
        for pos, discarded in enumerate(river or [], 1):
            if tile_index(discarded) == tile_idx:
                genbutsu_sources.append({"tile": discarded, "position": pos})
            if tile_base(discarded) in partners:
                suji_sources.append({"tile": discarded, "position": pos})
        if genbutsu_sources or suji_sources:
            against.append(
                {
                    "seat": seat,
                    "kind": "genbutsu" if genbutsu_sources else "suji",
                    "genbutsu_sources": genbutsu_sources,
                    "suji_sources": suji_sources,
                    "reached": bool(seat < len(reached) and reached[seat]),
                    "open_melds": open_melds[seat] if seat < len(open_melds) else 0,
                }
            )

    has_genbutsu = any(item["genbutsu_sources"] for item in against)
    has_suji = any(item["suji_sources"] for item in against)
    safe_against_threat = any(item["reached"] or item["open_melds"] for item in against)
    return {
        "tile": tile,
        "kind": "genbutsu" if has_genbutsu else "suji" if has_suji else None,
        "has_genbutsu": has_genbutsu,
        "has_suji": has_suji,
        "safe_against_threat": safe_against_threat,
        "opponents": len(against),
        "against": against,
    }


def top_tile(probs):
    idx = max(range(34), key=lambda i: probs[i])
    return TILES[idx], probs[idx] / 10000.0


def prob_for(probs, tile):
    return probs[tile_index(tile)] / 10000.0


def danger_for(state, target, tile):
    idx = tile_index(tile)
    danger = state.get("danger_k") or state.get("danger_t") or state.get("danger_s")
    if not danger:
        return None
    vals = []
    for seat, arr in enumerate(danger):
        if seat == target:
            continue
        if idx < len(arr):
            vals.append(arr[idx] / 10000.0)
    return max(vals) if vals else None


def round_delta(end_msgs, target):
    total = 0
    for msg in end_msgs or []:
        deltas = msg.get("deltas")
        if deltas and target < len(deltas):
            total += deltas[target]
    return total


def round_result(end_msgs, target):
    result = {"win": 0, "ron_win": 0, "tsumo_win": 0, "deal_in": 0, "draw": 0}
    if not end_msgs:
        return result
    if end_msgs[0].get("type") == "hora":
        for msg in end_msgs:
            if msg.get("actor") == target:
                result["win"] += 1
                if msg.get("actor") == msg.get("target"):
                    result["tsumo_win"] += 1
                else:
                    result["ron_win"] += 1
            elif msg.get("target") == target:
                result["deal_in"] += 1
    else:
        result["draw"] = 1
    return result


def stage_from_left(left):
    if left is None:
        return "unknown"
    if left >= 50:
        return "early"
    if left >= 25:
        return "middle"
    return "late"


def analyze_report(row):
    target = row["actor"]
    data = fetch_report(row["report_id"])
    naga_types = normalize_report(data)
    n_models = len(naga_types)
    pred = data["pred"]
    game = {
        "idx": row["idx"],
        "rank": row["rank"],
        "score": row["score"],
        "moves": row["moves"],
        "actor": target,
        "report_id": row["report_id"],
        "naga_types": naga_types,
        "rounds": len(pred),
        "round_wins": 0,
        "ron_wins": 0,
        "tsumo_wins": 0,
        "deal_ins": 0,
        "draws": 0,
        "draw_tenpai_plus": 0,
        "riichi": 0,
        "calls": 0,
        "call_rounds": 0,
        "decision_count": 0,
        "mismatch_count": 0,
        "bad_count": 0,
        "big_mismatch_count": 0,
        "safer_deviation": 0,
        "riskier_deviation": 0,
        "same_danger_deviation": 0,
        "actual_more_outside": 0,
        "actual_more_inside": 0,
        "stage": defaultdict(lambda: Counter(decisions=0, mismatch=0, bad=0, big=0)),
        "start_rank": defaultdict(lambda: Counter(decisions=0, mismatch=0, safer=0, riskier=0, big=0)),
        "reach_opportunities": 0,
        "riichi_when_naga_no": 0,
        "no_riichi_when_naga_yes": 0,
        "call_opportunities": 0,
        "call_when_naga_skip": 0,
        "skip_when_naga_call": 0,
        "deviation_outcomes": defaultdict(lambda: Counter(n=0, delta=0, wins=0, deal_ins=0)),
    }
    for kyoku in pred:
        start_msg = kyoku[0].get("info", {}).get("msg", {})
        end_msgs = start_msg.get("end_msgs") or []
        delta = round_delta(end_msgs, target)
        result = round_result(end_msgs, target)
        game["round_wins"] += result["win"]
        game["ron_wins"] += result["ron_win"]
        game["tsumo_wins"] += result["tsumo_win"]
        game["deal_ins"] += result["deal_in"]
        game["draws"] += result["draw"]
        if result["draw"] and delta > 0:
            game["draw_tenpai_plus"] += 1
        start_rank = None
        if "seat2rank" in start_msg and target < len(start_msg["seat2rank"]):
            start_rank = start_msg["seat2rank"][target] + 1
        called_this_round = False
        for pos, state in enumerate(kyoku):
            msg = state.get("info", {}).get("msg", {})
            actor = msg.get("actor")
            msg_type = msg.get("type")
            left = msg.get("left_hai_num")
            stage = stage_from_left(left)
            if actor == target and msg_type == "reach_accepted":
                game["riichi"] += 1
            if actor == target and msg_type in HURO_TYPES:
                game["calls"] += 1
                called_this_round = True
            if actor == target and "reach" in state:
                next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
                actual_reach = next_msg.get("type") == "reach" and next_msg.get("actor") == target
                model_says_reach = [p / 10000.0 > 0.5 for p in state["reach"]]
                game["reach_opportunities"] += 1
                if actual_reach and not any(model_says_reach):
                    game["riichi_when_naga_no"] += 1
                if not actual_reach and any(model_says_reach) and next_msg.get("type") != "ankan":
                    game["no_riichi_when_naga_yes"] += 1
            if msg_type == "dahai" and "huro" in state and str(target) in state["huro"]:
                next_msg = kyoku[pos + 1].get("info", {}).get("msg", {}) if pos + 1 < len(kyoku) else {}
                actual_called = next_msg.get("actor") == target and next_msg.get("type") in HURO_TYPES
                actual_kind = next_msg.get("kind") if actual_called else 0
                other_pon = next_msg.get("type") == "pon" and next_msg.get("actor") != target
                game["call_opportunities"] += 1
                bests = []
                for opts in state["huro"][str(target)]:
                    opts = {int(k): v / 10000.0 for k, v in opts.items()}
                    best = max(opts, key=lambda k: opts[k])
                    bests.append(best)
                if actual_called and all(best == 0 for best in bests):
                    game["call_when_naga_skip"] += 1
                if (not actual_called) and (not other_pon) and any(best != 0 for best in bests):
                    game["skip_when_naga_call"] += 1
            if actor != target or msg_type not in {"tsumo", "chi", "pon"}:
                continue
            actual = msg.get("real_dahai")
            if not actual or actual == "?" or msg.get("reached") or "dahai_pred" not in state:
                continue
            game["decision_count"] += 1
            game["stage"][stage]["decisions"] += 1
            if start_rank:
                game["start_rank"][str(start_rank)]["decisions"] += 1
            actual_idx = tile_index(actual)
            model_rows = []
            for model_idx in range(min(n_models, len(state["dahai_pred"]))):
                probs = state["dahai_pred"][model_idx]
                top, top_prob = top_tile(probs)
                actual_prob = prob_for(probs, actual)
                diff = top_prob - actual_prob if top != actual else 0.0
                model_rows.append((top, top_prob, actual_prob, diff))
            if not model_rows:
                continue
            mismatch = any(top != actual for top, _, _, _ in model_rows)
            avg_diff = mean([diff for *_, diff in model_rows]) or 0.0
            actual_prob_min = min(actual_prob for _, _, actual_prob, _ in model_rows)
            if mismatch:
                game["mismatch_count"] += 1
                game["stage"][stage]["mismatch"] += 1
                if start_rank:
                    game["start_rank"][str(start_rank)]["mismatch"] += 1
                actual_danger = danger_for(state, target, actual)
                top_dangers = [danger_for(state, target, top) for top, _, _, _ in model_rows]
                top_dangers = [d for d in top_dangers if d is not None]
                top_danger = mean(top_dangers)
                category = "other_deviation"
                if actual_danger is not None and top_danger is not None:
                    if actual_danger + 0.05 < top_danger:
                        game["safer_deviation"] += 1
                        category = "safer_than_naga"
                        if start_rank:
                            game["start_rank"][str(start_rank)]["safer"] += 1
                    elif actual_danger > top_danger + 0.05:
                        game["riskier_deviation"] += 1
                        category = "riskier_than_naga"
                        if start_rank:
                            game["start_rank"][str(start_rank)]["riskier"] += 1
                    else:
                        game["same_danger_deviation"] += 1
                actual_cls = tile_class(actual)
                top_classes = [tile_class(top) for top, _, _, _ in model_rows]
                if actual_cls in {"honor", "terminal"} and all(cls == "simple" for cls in top_classes):
                    game["actual_more_outside"] += 1
                if actual_cls == "simple" and all(cls in {"honor", "terminal"} for cls in top_classes):
                    game["actual_more_inside"] += 1
                bucket = game["deviation_outcomes"][category]
                bucket["n"] += 1
                bucket["delta"] += delta
                bucket["wins"] += result["win"]
                bucket["deal_ins"] += result["deal_in"]
            if actual_prob_min < 0.05 and mismatch:
                game["bad_count"] += 1
                game["stage"][stage]["bad"] += 1
            if avg_diff >= 0.5 and mismatch:
                game["big_mismatch_count"] += 1
                game["stage"][stage]["big"] += 1
                if start_rank:
                    game["start_rank"][str(start_rank)]["big"] += 1
        if called_this_round:
            game["call_rounds"] += 1
    return game


def collapse_games(rows, games, errors):
    by_rank = {}
    for rank in [1, 2, 3, 4]:
        sub = [r for r in rows if r["rank"] == rank]
        by_rank[str(rank)] = {
            "n": len(sub),
            "avg_score": mean([r["score"] for r in sub]),
            "avg_n_rating": mean([r["n_rating"] for r in sub]),
            "avg_n_bad": mean([r["n_bad"] for r in sub]),
        }
    totals = Counter()
    nested_stage = defaultdict(Counter)
    nested_rank = defaultdict(Counter)
    deviation_outcomes = defaultdict(Counter)
    for game in games:
        for key, value in game.items():
            if isinstance(value, (int, float)) and key not in {"idx", "rank", "score", "moves", "actor"}:
                totals[key] += value
        for stage, counter in game["stage"].items():
            nested_stage[stage].update(counter)
        for rank, counter in game["start_rank"].items():
            nested_rank[rank].update(counter)
        for category, counter in game["deviation_outcomes"].items():
            deviation_outcomes[category].update(counter)
    summary = {
        "rows": len(rows),
        "games_analyzed": len(games),
        "errors": errors,
        "rank_counts": dict(Counter(r["rank"] for r in rows)),
        "avg_rank": mean([r["rank"] for r in rows]),
        "avg_score": mean([r["score"] for r in rows]),
        "avg_n_rating": mean([r["n_rating"] for r in rows]),
        "avg_n_bad": mean([r["n_bad"] for r in rows]),
        "avg_h_rating": mean([r["h_rating"] for r in rows]),
        "avg_h_bad": mean([r["h_bad"] for r in rows]),
        "avg_k_rating": mean([r["k_rating"] for r in rows]),
        "avg_k_bad": mean([r["k_bad"] for r in rows]),
        "by_rank": by_rank,
        "totals": dict(totals),
        "stage": {k: dict(v) for k, v in nested_stage.items()},
        "start_rank": {k: dict(v) for k, v in nested_rank.items()},
        "deviation_outcomes": {k: dict(v) for k, v in deviation_outcomes.items()},
        "sheet_rows": rows,
        "game_features": games,
    }
    return summary


def main():
    rows = parse_rows()
    games = []
    errors = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(analyze_report, row): row for row in rows}
        for done, future in enumerate(as_completed(futures), 1):
            row = futures[future]
            try:
                games.append(future.result())
            except Exception as exc:
                errors.append({"idx": row["idx"], "report_id": row["report_id"], "error": repr(exc)})
            if done % 50 == 0:
                elapsed = time.time() - start
                print(f"processed {done}/{len(rows)} reports in {elapsed:.1f}s; errors={len(errors)}", flush=True)
    games.sort(key=lambda g: g["idx"])
    summary = collapse_games(rows, games, errors)
    OUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT_PATH} with {len(games)} games; errors={len(errors)}")


if __name__ == "__main__":
    main()
