#!/usr/bin/env python3
"""Turn-by-turn safe-tile retention for Point 14.

Replays every cached NAGA report in kyoku where LuckyJ is not dealer. At each LuckyJ
discard decision it records, by LuckyJ's own turn number (1 = first discard):

- how many held tile classes already sit in at least one opponent's river ("safe tiles");
- the per-tile discard rate of safe tiles versus non-safe tiles, split by tile kind;
- the share of turns where LuckyJ cut a non-safe tile while holding at least one safe tile.

Split by table state: quiet (no opponent riichi, no opponent at 2+ melds) versus threat.

It also records, at each turn where the hand held two floaters of the same kind (guest winds,
terminals or isolated middle tiles), one already in an opponent's river and one in none, which one
LuckyJ cut and which one NAGA's Nishiki head picked. The same-kind restriction removes tile-type
composition: early safe floaters are mostly guest winds, which LuckyJ cuts first regardless.

Outputs analysis/safe-tile-timing-<date>.json, with the banded figures the book cites under
"summary_bands". Rebuild the bands from an existing file with --summarize PATH.
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_luckyj as base  # noqa: E402
import mine_rx2_defense as rx2  # noqa: E402

OUT = Path(f"analysis/safe-tile-timing-{date.today().isoformat()}.json")
HURO_TYPES = base.HURO_TYPES
MAX_TURN = 18


def pct(num: float, den: float) -> float | None:
    return round(100.0 * num / den, 1) if den else None


def ci95(num: int, den: int) -> float | None:
    if not den:
        return None
    p = num / den
    return round(196.0 * math.sqrt(p * (1 - p) / den), 2)


def tile_class(tile: str) -> str:
    return tile.replace("r", "")


def tile_kind(tile: str) -> str:
    t = tile_class(tile)
    if len(t) == 1:
        return "honor"
    return "terminal" if int(t[0]) in (1, 9) else "middle"


SUIT_ORDER = "mps"
WIND_SEATS = ["E", "S", "W", "N"]


def floater_classes(hand: list[str], own_wind: str, round_wind: str) -> set[str]:
    """Held tile classes with no pair and no same-suit neighbor within two ranks.

    Value honors (dragons, own seat wind, round wind) are excluded because LuckyJ keeps
    them for yaku, which would look like defensive retention.
    """
    counts: dict[str, int] = {}
    for t in hand:
        c = tile_class(t)
        counts[c] = counts.get(c, 0) + 1
    out = set()
    for c, n in counts.items():
        if n != 1:
            continue
        if len(c) == 1:
            if c in ("P", "F", "C") or c == own_wind or c == round_wind:
                continue
            out.add(c)
            continue
        rank, suit = int(c[0]), c[1]
        if any(f"{r}{suit}" in counts for r in range(rank - 2, rank + 3) if r != rank and 1 <= r <= 9):
            continue
        out.add(c)
    return out


class Rate:
    def __init__(self) -> None:
        self.n = 0
        self.hit = 0

    def add(self, hit: bool) -> None:
        self.n += 1
        self.hit += 1 if hit else 0

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "hits": self.hit, "rate_pct": pct(self.hit, self.n), "ci95_half_width_pp": ci95(self.hit, self.n)}


class Mean:
    def __init__(self) -> None:
        self.n = 0
        self.total = 0.0

    def add(self, v: float) -> None:
        self.n += 1
        self.total += v

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "mean": round(self.total / self.n, 2) if self.n else None}


def new_turn_table() -> dict[str, Any]:
    return {
        "states": 0,
        "safe_classes_held": Mean(),
        "holds_any_safe": Rate(),
        "kept_safe_cut_live": Rate(),
        "floater_choice": {
            "turns_with_both": 0,
            "safe_share_of_floaters": Mean(),
            "picked_safe_floater": Rate(),
            "picked_live_floater": Rate(),
            "naga_picked_safe_floater": Rate(),
            "naga_picked_live_floater": Rate(),
            "by_kind": {
                kind: {
                    "safe_share": Mean(),
                    "picked_safe": Rate(),
                    "picked_live": Rate(),
                    "naga_picked_safe": Rate(),
                    "naga_picked_live": Rate(),
                }
                for kind in ("honor", "terminal", "middle")
            },
        },
        "discard_rate": {
            status: {kind: Rate() for kind in ("honor", "terminal", "middle", "all")}
            for status in ("safe", "not_safe")
        },
    }


BANDS = ((1, 2), (3, 5), (6, 8), (9, 12), (13, 18))
KINDS = ("honor", "terminal", "middle")


def band_label(lo: int, hi: int) -> str:
    return f"{lo}-{hi}"


def summarize(out: dict[str, Any]) -> dict[str, Any]:
    """Pool the per-turn same-kind floater choices into turn bands.

    For each band the figure is the share of cuts (of either floater) that went to the live one:
    live / (safe + live). Above 50 means the safe tile was kept; below 50 means it went first.
    """
    by_turn = out["by_turn"]

    def pooled(split: str, kind: str, who: str, lo: int, hi: int) -> dict[str, Any]:
        safe_key = "picked_safe" if who == "LuckyJ" else "naga_picked_safe"
        live_key = "picked_live" if who == "LuckyJ" else "naga_picked_live"
        spots = safe = live = 0
        for turn in range(lo, hi + 1):
            fc = by_turn[split][str(turn)]["floater_choice"]
            if kind == "any":
                block = {
                    "picked_safe": fc["picked_safe_floater"], "picked_live": fc["picked_live_floater"],
                    "naga_picked_safe": fc["naga_picked_safe_floater"], "naga_picked_live": fc["naga_picked_live_floater"],
                }
            else:
                block = fc["by_kind"][kind]
            spots += block[safe_key]["n"]
            safe += block[safe_key]["hits"]
            live += block[live_key]["hits"]
        cuts = safe + live
        return {"spots": spots, "cuts": cuts, "live_cuts": live, "live_share_pct": pct(live, cuts)}

    bands = {}
    for split in ("quiet", "threat"):
        bands[split] = {}
        for kind in KINDS + ("any",):
            bands[split][kind] = {
                band_label(lo, hi): {who: pooled(split, kind, who, lo, hi) for who in ("LuckyJ", "NAGA")}
                for lo, hi in BANDS
            }
    threat_share = {}
    for turn in range(1, MAX_TURN + 1):
        quiet = by_turn["quiet"][str(turn)]["states"]
        threat = by_turn["threat"][str(turn)]["states"]
        threat_share[str(turn)] = {"states": quiet + threat, "threat_pct": pct(threat, quiet + threat)}
    return {
        "definition": "same-kind floater pairs, one safe and one live; live_share_pct = share of cuts of either tile that went to the live one",
        "bands": bands,
        "threat_share_by_turn": threat_share,
    }


def main() -> None:
    if len(sys.argv) == 3 and sys.argv[1] == "--summarize":
        path = Path(sys.argv[2])
        out = json.loads(path.read_text())
        out["summary_bands"] = summarize(out)
        path.write_text(json.dumps(out, indent=2))
        print("summarized", path)
        return

    raw_rows = base.parse_rows()
    rows, seen = [], set()
    for row in raw_rows:
        rid = row.get("report_id")
        if rid in seen:
            continue
        seen.add(rid)
        rows.append(row)

    tables: dict[str, dict[int, dict[str, Any]]] = {
        "quiet": defaultdict(new_turn_table),
        "threat": defaultdict(new_turn_table),
    }
    summary = {"reports": 0, "child_kyoku": 0, "dealer_kyoku_skipped": 0, "errors": []}

    for i, row in enumerate(rows, 1):
        if i % 200 == 0:
            print(f"{i}/{len(rows)}", flush=True)
        target = row.get("actor")
        if target is None or not (0 <= target < 4):
            continue
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
            summary["reports"] += 1
        except Exception as exc:  # noqa: BLE001
            summary["errors"].append(repr(exc))
            continue

        for kyoku in data.get("pred") or []:
            try:
                start = (kyoku[0].get("info", {}).get("msg", {}) if kyoku else {}) or {}
                oya = start.get("oya")
                if oya is None:
                    continue
                if int(oya) == target:
                    summary["dealer_kyoku_skipped"] += 1
                    continue
                summary["child_kyoku"] += 1
                opponents = [s for s in range(4) if s != target]
                own_wind = WIND_SEATS[(target - int(oya)) % 4]
                round_wind = start.get("bakaze") or "E"

                start_hands = start.get("tehais") or [[], [], [], []]
                hand = list(start_hands[target]) if target < len(start_hands) else []
                discards: list[list[str]] = [[], [], [], []]
                open_melds = [0, 0, 0, 0]
                reached = [False, False, False, False]
                own_turn = 0

                for state in kyoku:
                    msg = state.get("info", {}).get("msg", {}) or {}
                    actor = msg.get("actor")
                    mtype = msg.get("type")

                    if mtype == "tsumo":
                        if actor == target and msg.get("pai"):
                            hand.append(msg["pai"])
                        actual = msg.get("real_dahai")
                        is_decision = actor == target and actual not in (None, "?") and "dahai_pred" in state
                        if is_decision:
                            own_turn += 1
                            if own_turn <= MAX_TURN and not reached[target]:
                                any_riichi = any(reached[s] for s in opponents)
                                max_open = max(open_melds[s] for s in opponents)
                                split = "quiet" if (not any_riichi and max_open <= 1) else "threat"
                                table = tables[split][own_turn]
                                table["states"] += 1
                                rivers = set()
                                for s in opponents:
                                    rivers.update(tile_class(t) for t in discards[s])
                                held = {tile_class(t) for t in hand}
                                safe = held & rivers
                                a_cls = tile_class(actual)
                                table["safe_classes_held"].add(len(safe))
                                table["holds_any_safe"].add(bool(safe))
                                if safe:
                                    table["kept_safe_cut_live"].add(a_cls not in rivers)
                                floaters = floater_classes(hand, own_wind, round_wind)
                                safe_fl = floaters & rivers
                                live_fl = floaters - rivers
                                if safe_fl and live_fl:
                                    fc = table["floater_choice"]
                                    fc["turns_with_both"] += 1
                                    fc["safe_share_of_floaters"].add(len(safe_fl) / len(floaters))
                                    fc["picked_safe_floater"].add(a_cls in safe_fl)
                                    fc["picked_live_floater"].add(a_cls in live_fl)
                                    naga_cls = None
                                    preds = state.get("dahai_pred") or []
                                    if preds and len(preds[0]) >= 34:
                                        naga_cls = tile_class(base.top_tile(preds[0])[0])
                                        fc["naga_picked_safe_floater"].add(naga_cls in safe_fl)
                                        fc["naga_picked_live_floater"].add(naga_cls in live_fl)
                                    for kind in ("honor", "terminal", "middle"):
                                        ks = {c for c in safe_fl if tile_kind(c) == kind}
                                        kl = {c for c in live_fl if tile_kind(c) == kind}
                                        if not (ks and kl):
                                            continue
                                        bk = fc["by_kind"][kind]
                                        bk["safe_share"].add(len(ks) / (len(ks) + len(kl)))
                                        bk["picked_safe"].add(a_cls in ks)
                                        bk["picked_live"].add(a_cls in kl)
                                        if naga_cls is not None:
                                            bk["naga_picked_safe"].add(naga_cls in ks)
                                            bk["naga_picked_live"].add(naga_cls in kl)
                                for cls in held:
                                    status = "safe" if cls in rivers else "not_safe"
                                    kind = tile_kind(cls)
                                    hit = cls == a_cls
                                    table["discard_rate"][status][kind].add(hit)
                                    table["discard_rate"][status]["all"].add(hit)
                        if actor == target and actual not in (None, "?"):
                            rx2.remove_tile(hand, actual)

                    elif mtype in HURO_TYPES:
                        if actor is not None:
                            open_melds[actor] += 1
                            if actor == target:
                                for t in msg.get("consumed") or []:
                                    rx2.remove_tile(hand, t)
                                d = msg.get("real_dahai")
                                if d and d != "?":
                                    rx2.remove_tile(hand, d)
                                    own_turn += 1

                    elif mtype == "ankan":
                        if actor is not None:
                            open_melds[actor] += 1
                            if actor == target:
                                for t in msg.get("consumed") or []:
                                    rx2.remove_tile(hand, t)

                    elif mtype == "kakan":
                        if actor == target and msg.get("pai"):
                            rx2.remove_tile(hand, msg["pai"])

                    elif mtype == "reach":
                        if actor is not None:
                            reached[actor] = True

                    elif mtype == "dahai":
                        tile = msg.get("pai")
                        if actor is not None and tile:
                            discards[actor].append(tile)
            except Exception as exc:  # noqa: BLE001
                if len(summary["errors"]) < 20:
                    summary["errors"].append(repr(exc))

    def dump(table: dict[str, Any]) -> dict[str, Any]:
        return {
            "states": table["states"],
            "safe_classes_held": table["safe_classes_held"].to_dict(),
            "holds_any_safe": table["holds_any_safe"].to_dict(),
            "kept_safe_cut_live": table["kept_safe_cut_live"].to_dict(),
            "floater_choice": {
                "turns_with_both": table["floater_choice"]["turns_with_both"],
                "safe_share_of_floaters": table["floater_choice"]["safe_share_of_floaters"].to_dict(),
                "picked_safe_floater": table["floater_choice"]["picked_safe_floater"].to_dict(),
                "picked_live_floater": table["floater_choice"]["picked_live_floater"].to_dict(),
                "naga_picked_safe_floater": table["floater_choice"]["naga_picked_safe_floater"].to_dict(),
                "naga_picked_live_floater": table["floater_choice"]["naga_picked_live_floater"].to_dict(),
                "by_kind": {
                    kind: {name: stat.to_dict() for name, stat in stats.items()}
                    for kind, stats in table["floater_choice"]["by_kind"].items()
                },
            },
            "discard_rate": {
                status: {kind: r.to_dict() for kind, r in kinds.items()}
                for status, kinds in table["discard_rate"].items()
            },
        }

    out = {
        "scope": "kyoku where LuckyJ is not dealer; LuckyJ's own discard number 1..18; own-riichi states excluded",
        "definitions": {
            "safe": "held tile class already present in at least one opponent's river at decision time",
            "quiet": "no opponent riichi and no opponent with 2+ melds",
            "kept_safe_cut_live": "among turns holding at least one safe class, share where the discard was not in any opponent river",
            "floater": "held singleton with no same-suit neighbor within two ranks; dragons, own seat wind and round wind excluded",
            "naga": "Nishiki head top pick, dahai_pred[0], at the same decision",
            "by_kind": "same comparison restricted to turns holding a safe and a live floater of the same kind (honor, terminal, middle), which removes tile-type composition",
            "floater_choice": "turns holding at least one safe floater and one live floater: which kind LuckyJ discarded, against the safe share of floaters as the indifference baseline",
        },
        "summary": summary,
        "by_turn": {
            split: {str(turn): dump(tables[split][turn]) for turn in range(1, MAX_TURN + 1)}
            for split in ("quiet", "threat")
        },
    }
    out["summary_bands"] = summarize(out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
