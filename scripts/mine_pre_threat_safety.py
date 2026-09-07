#!/usr/bin/env python3
"""Pre-threat safety checks for Point 14.

Replays every cached NAGA report and measures, in kyoku where LuckyJ is not dealer:

1. who becomes the threat: dealer share of opponent riichi and of first 2-meld opponents;
2. deal-in price: LuckyJ's mean loss when dealing into a dealer versus a child;
3. pre-declaration genbutsu: how often LuckyJ already holds a tile from the future
   riichi player's river at the moment of declaration, and whether the first reaction
   discard is one of those pre-held tiles;
4. quiet-table retention: at LuckyJ decision states with no riichi and no 2+ meld
   opponent, the discard rate of held tiles that sit in exactly one opponent's river,
   split by whether that opponent is the dealer;
5. river tells: riichi rate of an opponent by early-river features.

Outputs analysis/pre-threat-safety-<date>.json.
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

OUT = Path(f"analysis/pre-threat-safety-{date.today().isoformat()}.json")
HURO_TYPES = base.HURO_TYPES


def pct(num: float, den: float) -> float | None:
    return round(100.0 * num / den, 1) if den else None


def ci95(num: int, den: int) -> float | None:
    if not den:
        return None
    p = num / den
    return round(196.0 * math.sqrt(p * (1 - p) / den), 2)


def tile_kind(tile: str) -> str:
    t = tile.replace("r", "")
    if len(t) == 1:
        return "honor"
    rank = int(t[0])
    return "terminal" if rank in (1, 9) else "middle"


def tile_class(tile: str) -> str:
    return tile.replace("r", "")


def is_honor(tile: str) -> bool:
    return len(tile.replace("r", "")) == 1


def suited_rank(tile: str) -> int | None:
    t = tile.replace("r", "")
    return int(t[0]) if len(t) == 2 else None


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
        self.values: list[float] = []

    def add(self, v: float) -> None:
        self.values.append(v)

    def to_dict(self) -> dict[str, Any]:
        n = len(self.values)
        if not n:
            return {"n": 0, "mean": None}
        m = sum(self.values) / n
        sd = math.sqrt(sum((v - m) ** 2 for v in self.values) / n) if n > 1 else 0.0
        return {"n": n, "mean": round(m, 1), "median": sorted(self.values)[n // 2], "sd": round(sd, 1)}


def main() -> None:
    raw_rows = base.parse_rows()
    rows, seen = [], set()
    for row in raw_rows:
        rid = row.get("report_id")
        if rid in seen:
            continue
        seen.add(rid)
        rows.append(row)

    # 1. threat source
    riichi_by_role = {"dealer": 0, "child": 0}
    two_meld_by_role = {"dealer": 0, "child": 0}
    riichi_rate_by_role = {"dealer": Rate(), "child": Rate()}  # per opponent-kyoku
    # 2. price
    dealin_loss = {"dealer": Mean(), "child": Mean()}
    dealin_count = {"dealer": 0, "child": 0}
    # 3. pre-declaration genbutsu
    holds_pre_genbutsu = {"dealer": Rate(), "child": Rate(), "all": Rate()}
    pre_genbutsu_count = {"dealer": Mean(), "child": Mean(), "all": Mean()}
    reaction_kind = defaultdict(int)  # first reaction discard classification
    reaction_pre_held_when_available = Rate()
    # 4. quiet retention
    quiet_discard = {role: {kind: Rate() for kind in ("honor", "terminal", "middle", "all")} for role in ("dealer", "child")}
    quiet_states = 0
    # 5. river tells
    tells: dict[str, dict[str, Rate]] = {
        "early_honors_first6": defaultdict(Rate),
        "middle_tile_first3": defaultdict(Rate),
        "tedashi_count_discards4to6": defaultdict(Rate),
        "dora_cut_first6": defaultdict(Rate),
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
                role_of = {s: ("dealer" if s == int(oya) else "child") for s in range(4)}
                opponents = [s for s in range(4) if s != target]

                # deal-in price from end messages
                for em in start.get("end_msgs") or []:
                    if em.get("type") == "hora" and em.get("target") == target and em.get("actor") != target:
                        deltas = em.get("deltas")
                        winner = em.get("actor")
                        role = role_of[winner]
                        dealin_count[role] += 1
                        if isinstance(deltas, list) and len(deltas) == 4:
                            dealin_loss[role].add(-float(deltas[target]))

                start_hands = start.get("tehais") or [[], [], [], []]
                hand = list(start_hands[target]) if target < len(start_hands) else []
                discards: list[list[str]] = [[], [], [], []]
                tsumogiri_flags: list[list[bool]] = [[], [], [], []]
                open_melds = [0, 0, 0, 0]
                reached = [False, False, False, False]
                declared_riichi = set()
                counted_two_meld = set()
                dora_markers = [start.get("dora_marker")] if start.get("dora_marker") else []
                pending_reaction: dict[int, dict[str, Any]] = {}
                pre_hand_before_draw: list[str] = []

                for state in kyoku:
                    msg = state.get("info", {}).get("msg", {}) or {}
                    actor = msg.get("actor")
                    mtype = msg.get("type")

                    if mtype == "dora":
                        if msg.get("dora_marker"):
                            dora_markers.append(msg["dora_marker"])
                        continue

                    if mtype == "tsumo":
                        if actor == target:
                            pre_hand_before_draw = list(hand)
                            if msg.get("pai"):
                                hand.append(msg["pai"])
                        actual = msg.get("real_dahai")
                        is_decision = actor == target and actual not in (None, "?") and "dahai_pred" in state
                        if is_decision:
                            # 3b. first reaction after riichi
                            if pending_reaction:
                                a_cls = tile_class(actual)
                                for rs in sorted(pending_reaction):
                                    info = pending_reaction.pop(rs)
                                    pre_river = info["pre_river"]
                                    river_now = {tile_class(t) for t in discards[rs]}
                                    genbutsu = a_cls in river_now
                                    held_before = a_cls in {tile_class(t) for t in pre_hand_before_draw}
                                    if not genbutsu:
                                        reaction_kind["not_genbutsu"] += 1
                                    elif held_before and a_cls in pre_river:
                                        reaction_kind["genbutsu_pre_held_pre_river"] += 1
                                    elif held_before:
                                        reaction_kind["genbutsu_pre_held_declaration_tile"] += 1
                                    else:
                                        reaction_kind["genbutsu_just_drawn"] += 1
                                    if info["pre_held_count"] > 0:
                                        reaction_pre_held_when_available.add(genbutsu and held_before and a_cls in pre_river)
                            # 4. quiet retention
                            any_riichi = any(reached[s] for s in opponents)
                            max_open = max(open_melds[s] for s in opponents)
                            if not any_riichi and max_open <= 1:
                                quiet_states += 1
                                rivers = {s: {tile_class(t) for t in discards[s]} for s in opponents}
                                a_cls = tile_class(actual)
                                for cls in {tile_class(t) for t in hand}:
                                    owners = [s for s in opponents if cls in rivers[s]]
                                    if len(owners) != 1:
                                        continue
                                    role = role_of[owners[0]]
                                    kind = tile_kind(cls)
                                    hit = cls == a_cls
                                    quiet_discard[role][kind].add(hit)
                                    quiet_discard[role]["all"].add(hit)
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
                            elif open_melds[actor] == 2 and actor not in counted_two_meld:
                                counted_two_meld.add(actor)
                                two_meld_by_role[role_of[actor]] += 1

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
                        if actor is not None and actor != target and actor not in declared_riichi:
                            declared_riichi.add(actor)
                            reached[actor] = True
                            role = role_of[actor]
                            riichi_by_role[role] += 1
                            pre_river = {tile_class(t) for t in discards[actor]}
                            held = {tile_class(t) for t in hand}
                            pre_held = held & pre_river
                            for key in (role, "all"):
                                holds_pre_genbutsu[key].add(bool(pre_held))
                                pre_genbutsu_count[key].add(len(pre_held))
                            pending_reaction[actor] = {"pre_river": pre_river, "pre_held_count": len(pre_held)}
                        elif actor == target:
                            reached[actor] = True

                    elif mtype == "dahai":
                        tile = msg.get("pai")
                        if actor is not None and tile:
                            discards[actor].append(tile)
                            tsumogiri_flags[actor].append(bool(msg.get("tsumogiri")))

                # per opponent-kyoku outcomes: riichi rate by role, river tells
                for s in opponents:
                    did_riichi = s in declared_riichi
                    riichi_rate_by_role[role_of[s]].add(did_riichi)
                    river = discards[s]
                    if len(river) >= 6:
                        honors6 = sum(1 for t in river[:6] if is_honor(t))
                        tells["early_honors_first6"]["3+" if honors6 >= 3 else ("2" if honors6 == 2 else "0-1")].add(did_riichi)
                        mid3 = any((suited_rank(t) or 0) in (4, 5, 6) for t in river[:3])
                        tells["middle_tile_first3"]["yes" if mid3 else "no"].add(did_riichi)
                        ted = sum(1 for f in tsumogiri_flags[s][3:6] if not f)
                        tells["tedashi_count_discards4to6"]["3" if ted == 3 else ("2" if ted == 2 else "0-1")].add(did_riichi)
                        dora_tiles = {tile_class(rx2.marker_to_dora(m)) for m in dora_markers[:1] if rx2.marker_to_dora(m)}
                        if dora_tiles:
                            cut = any(tile_class(t) in dora_tiles for t in river[:6])
                            tells["dora_cut_first6"]["yes" if cut else "no"].add(did_riichi)
            except Exception as exc:  # noqa: BLE001
                if len(summary["errors"]) < 20:
                    summary["errors"].append(repr(exc))

    def role_share(counts: dict[str, int]) -> dict[str, Any]:
        total = sum(counts.values())
        return {"dealer": counts["dealer"], "child": counts["child"], "dealer_share_pct": pct(counts["dealer"], total), "uniform_expectation_pct": 33.3}

    out = {
        "scope": "kyoku where LuckyJ is not dealer; all cached NAGA reports",
        "summary": summary,
        "threat_source": {
            "opponent_riichi_declarations": role_share(riichi_by_role),
            "first_time_opponent_reaches_2_melds": role_share(two_meld_by_role),
            "riichi_rate_per_opponent_kyoku": {k: v.to_dict() for k, v in riichi_rate_by_role.items()},
        },
        "deal_in_price": {
            "count": dealin_count,
            "loss_points": {k: v.to_dict() for k, v in dealin_loss.items()},
        },
        "pre_declaration_genbutsu": {
            "definition": "at the moment an opponent declares riichi, LuckyJ's 13-tile hand already contains a tile class present in that player's river before the declaration tile",
            "holds_at_least_one": {k: v.to_dict() for k, v in holds_pre_genbutsu.items()},
            "count_held": {k: v.to_dict() for k, v in pre_genbutsu_count.items()},
            "first_reaction_discard": dict(reaction_kind),
            "first_reaction_uses_pre_held_when_available": reaction_pre_held_when_available.to_dict(),
        },
        "quiet_table_retention": {
            "definition": "LuckyJ decision states with no opponent riichi and no opponent at 2+ melds; for each held tile class present in exactly one opponent's river, whether LuckyJ discarded it this turn",
            "quiet_states": quiet_states,
            "discard_rate_by_owner_role_and_tile_kind": {role: {kind: r.to_dict() for kind, r in kinds.items()} for role, kinds in quiet_discard.items()},
        },
        "river_tells": {name: {k: v.to_dict() for k, v in sorted(groups.items())} for name, groups in tells.items()},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
