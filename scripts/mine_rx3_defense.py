#!/usr/bin/env python3
"""Third-pass defense mining: child-only LuckyJ danger-taking proxies.

This pass keeps scripts/mine_rx_defense.py and scripts/mine_rx2_defense.py intact and
reuses their parsing/state helpers.  It splits LuckyJ decision states by whether LuckyJ
was dealer in the kyoku, then recomputes the prescription baselines and selected
condition effects for child-only rounds.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import analyze_luckyj as base
import mine_rx2_defense as rx2

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "analysis" / "rx3-defense-2026-07-05.json"

SHANTEN_ORDER = ["0", "1", "2", "3+"]
TURN_BUCKET_ORDER = ["1-6", "7-12", "13+"]
MELD_ORDER = ["2", "3+"]
YES_NO_UNKNOWN = ["yes", "no", "unknown"]
GENBUTSU_ORDER = ["0", "1", "2+"]
OPEN_OWN_SHANTEN_ORDER = ["<=1", "2+", "unknown"]
MIN_CELL_N = 150

PUBLISHED = {
    "vs_riichi_push_by_closed_shanten": {"0": 61.3, "1": 33.6, "2": 20.3, "3+": 14.2},
    "last20_vs_riichi_push_by_closed_shanten": {"0": 54.3, "1": 22.9, "2": 13.4, "3+": 8.4},
    "first_discard_after_riichi_genbutsu_by_closed_shanten": {"0": 32.6, "1": 55.5, "2": 64.3, "3+": 68.1},
    # Prompt supplied rounded published open-hand turn buckets: 2 meld = 54/44/39, 3+ meld = 57/42/33.
    "open_hand_push_by_meld_count_and_turn": {
        "2": {"1-6": 54.0, "7-12": 44.0, "13+": 39.0},
        "3+": {"1-6": 57.0, "7-12": 42.0, "13+": 33.0},
    },
}

# Published modifier numbers currently cited from rx2 proposed modifiers.  The
# tenpai + LuckyJ-is-dealer ~=68% modifier is intentionally omitted because child-only
# prescriptions definitionally exclude own-dealer rounds.
PUBLISHED_CONDITION_NUMBERS = [
    {"scope": "tenpai_vs_riichi", "condition": "dora_count", "value": "2", "published_rate_pct": 67.3, "published_delta_pp": 7.7},
    {"scope": "one_shanten_vs_riichi", "condition": "genbutsu_zero", "value": "yes", "published_rate_pct": 55.8, "published_delta_pp": 26.4},
    {"scope": "tenpai_vs_riichi", "condition": "genbutsu_count", "value": "2+", "published_rate_pct": 56.2, "published_delta_pp": -14.3},
    {"scope": "tenpai_vs_riichi", "condition": "second_threat_present", "value": "no", "published_rate_pct": 63.4, "published_delta_pp": 8.1},
    {"scope": "tenpai_vs_riichi", "condition": "tiles_left_le20", "value": "yes", "published_rate_pct": 54.3, "published_delta_pp": -11.7},
    {"scope": "open_hand_turn7plus", "condition": "own_shanten_bucket", "value": "<=1", "published_rate_pct": 48.2, "published_delta_pp": 20.4},
    {"scope": "open_hand_turn7plus", "condition": "own_shanten_bucket", "value": "2+", "published_rate_pct": 27.8, "published_delta_pp": -20.4},
]


class PropStats:
    """Simple proportion with Wald 95% CI half-width in percentage points."""

    def __init__(self) -> None:
        self.n = 0
        self.count = 0

    def add(self, success: bool) -> None:
        self.n += 1
        if success:
            self.count += 1

    @property
    def rate_pct(self) -> float | None:
        return round(100.0 * self.count / self.n, 1) if self.n else None

    @property
    def ci95_half_width_pp(self) -> float | None:
        if not self.n:
            return None
        p = self.count / self.n
        return 1.96 * math.sqrt(p * (1.0 - p) / self.n) * 100.0

    def to_dict(self, count_key: str = "count", rate_key: str = "rate_pct") -> dict[str, Any]:
        return {
            "n": self.n,
            count_key: self.count,
            rate_key: self.rate_pct,
            "ci95_half_width_pp": round(self.ci95_half_width_pp, 2) if self.ci95_half_width_pp is not None else None,
        }


def round1(value: float | None) -> float | None:
    return round(value, 1) if value is not None else None


def dealer_split_key(start: dict[str, Any], target: int) -> str:
    try:
        return "dealer" if int(start.get("oya")) == target else "child"
    except (TypeError, ValueError):
        return "unknown"


def top_pred_tile(dahai_pred: Any) -> str | None:
    if not isinstance(dahai_pred, list) or not dahai_pred:
        return None
    head = dahai_pred[0]
    if not isinstance(head, list) or not head:
        return None
    limit = min(34, len(head))
    if limit <= 0:
        return None
    try:
        top_idx = max(range(limit), key=lambda idx: float(head[idx]))
    except (TypeError, ValueError):
        return None
    return base.TILES[top_idx]


def same_tile(a: str | None, b: str | None) -> bool:
    ai = rx2.tile_index(a)
    bi = rx2.tile_index(b)
    return ai is not None and ai == bi


def get_bin(root: dict[str, Any], *keys: str) -> rx2.BinStats:
    node = root
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    final = keys[-1]
    stat = node.get(final)
    if stat is None:
        stat = rx2.BinStats()
        node[final] = stat
    return stat


def get_prop(root: dict[str, Any], *keys: str) -> PropStats:
    node = root
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    final = keys[-1]
    stat = node.get(final)
    if stat is None:
        stat = PropStats()
        node[final] = stat
    return stat


def bin_dict(root: dict[str, Any], *keys: str) -> dict[str, Any]:
    node: Any = root
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return rx2.BinStats().to_dict()
        node = node[key]
    if isinstance(node, rx2.BinStats):
        return node.to_dict()
    return rx2.BinStats().to_dict()


def prop_dict(root: dict[str, Any], *keys: str, count_key: str, rate_key: str) -> dict[str, Any]:
    node: Any = root
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return PropStats().to_dict(count_key=count_key, rate_key=rate_key)
        node = node[key]
    if isinstance(node, PropStats):
        return node.to_dict(count_key=count_key, rate_key=rate_key)
    return PropStats().to_dict(count_key=count_key, rate_key=rate_key)


def side_by_side_push(child_stat: dict[str, Any], dealer_stat: dict[str, Any], published_pct: float | None) -> dict[str, Any]:
    child_rate = child_stat.get("push_rate_pct")
    dealer_rate = dealer_stat.get("push_rate_pct")
    return {
        "published_pct": published_pct,
        "child": child_stat,
        "dealer_only": dealer_stat,
        "child_delta_pp_vs_published": round1(child_rate - published_pct) if child_rate is not None and published_pct is not None else None,
        "dealer_delta_pp_vs_published": round1(dealer_rate - published_pct) if dealer_rate is not None and published_pct is not None else None,
        "dealer_minus_child_pp": round1(dealer_rate - child_rate) if dealer_rate is not None and child_rate is not None else None,
    }


def side_by_side_prop(child_stat: dict[str, Any], dealer_stat: dict[str, Any], published_pct: float | None, rate_key: str) -> dict[str, Any]:
    child_rate = child_stat.get(rate_key)
    dealer_rate = dealer_stat.get(rate_key)
    return {
        "published_pct": published_pct,
        "child": child_stat,
        "dealer_only": dealer_stat,
        "child_delta_pp_vs_published": round1(child_rate - published_pct) if child_rate is not None and published_pct is not None else None,
        "dealer_delta_pp_vs_published": round1(dealer_rate - published_pct) if dealer_rate is not None and published_pct is not None else None,
        "dealer_minus_child_pp": round1(dealer_rate - child_rate) if dealer_rate is not None and child_rate is not None else None,
    }


def find_effect(condition_effects: dict[str, Any], condition: str, value: str) -> dict[str, Any] | None:
    payload = condition_effects.get(condition) or {}
    for effect in payload.get("values_sorted_by_abs_delta_pp", []):
        if effect.get("value") == value:
            return effect
    return None


def append_baseline_changes(changed: list[dict[str, Any]], metric: str, key_path: list[str], row: dict[str, Any]) -> None:
    published = row.get("published_pct")
    child = row.get("child", {})
    rate = child.get("push_rate_pct", child.get("genbutsu_rate_pct"))
    delta = row.get("child_delta_pp_vs_published")
    if rate is not None and published is not None and delta is not None and abs(delta) >= 2.0:
        changed.append({
            "kind": "baseline_rate",
            "metric": metric,
            "key_path": key_path,
            "published_pct": published,
            "child_only_pct": rate,
            "delta_pp": delta,
            "n": child.get("n"),
        })


def append_condition_changes(changed: list[dict[str, Any]], condition_outputs: dict[str, Any]) -> None:
    scope_map = {
        "tenpai_vs_riichi": condition_outputs["vs_riichi_closed_shanten"]["0"]["conditions"],
        "one_shanten_vs_riichi": condition_outputs["vs_riichi_closed_shanten"]["1"]["conditions"],
        "open_hand_turn7plus": condition_outputs["open_hand_turn7plus"]["conditions"],
    }
    for spec in PUBLISHED_CONDITION_NUMBERS:
        effect = find_effect(scope_map[spec["scope"]], spec["condition"], spec["value"])
        if not effect:
            continue
        rate = effect.get("push_rate_pct")
        delta = effect.get("delta_pp_vs_complement")
        pub_rate = spec.get("published_rate_pct")
        pub_delta = spec.get("published_delta_pp")
        if rate is not None and pub_rate is not None and abs(rate - pub_rate) >= 2.0:
            changed.append({
                "kind": "condition_rate",
                "scope": spec["scope"],
                "condition": spec["condition"],
                "value": spec["value"],
                "published_pct": pub_rate,
                "child_only_pct": rate,
                "delta_pp": round1(rate - pub_rate),
                "n": effect.get("n"),
            })
        if delta is not None and pub_delta is not None and abs(delta - pub_delta) >= 2.0:
            changed.append({
                "kind": "condition_delta_pp",
                "scope": spec["scope"],
                "condition": spec["condition"],
                "value": spec["value"],
                "published_delta_pp": pub_delta,
                "child_only_delta_pp": delta,
                "movement_pp": round1(delta - pub_delta),
                "n": effect.get("n"),
            })


def main() -> None:
    raw_rows = base.parse_rows()
    rows = []
    seen_report_ids: set[str] = set()
    duplicate_report_rows = []
    for row in raw_rows:
        report_id = row.get("report_id")
        if report_id in seen_report_ids:
            duplicate_report_rows.append({
                "idx": row.get("idx"),
                "report_id": report_id,
                "actor": row.get("actor"),
                "paifu": row.get("paifu"),
            })
            continue
        seen_report_ids.add(report_id)
        rows.append(row)

    match_stats: dict[str, PropStats] = defaultdict(PropStats)
    vs_riichi_by_split: dict[str, dict[str, rx2.BinStats]] = {"child": defaultdict(rx2.BinStats), "dealer": defaultdict(rx2.BinStats), "unknown": defaultdict(rx2.BinStats)}
    vs_riichi_last20_by_split: dict[str, dict[str, rx2.BinStats]] = {"child": defaultdict(rx2.BinStats), "dealer": defaultdict(rx2.BinStats), "unknown": defaultdict(rx2.BinStats)}
    immediate_by_split: dict[str, dict[str, PropStats]] = {"child": defaultdict(PropStats), "dealer": defaultdict(PropStats), "unknown": defaultdict(PropStats)}
    open_by_split: dict[str, Any] = {"child": {}, "dealer": {}, "unknown": {}}

    vs_condition_observations: dict[str, list[dict[str, Any]]] = {"0": [], "1": []}
    open_condition_observations: list[dict[str, Any]] = []

    summary: dict[str, Any] = {
        "n_rows_from_sheet": len(raw_rows),
        "n_unique_report_ids": len(rows),
        "n_duplicate_report_rows_skipped": len(duplicate_report_rows),
        "duplicate_report_rows_skipped": duplicate_report_rows[:20],
        "n_reports_processed": 0,
        "n_reports_failed": 0,
        "n_kyoku_seen": 0,
        "n_child_kyoku_seen": 0,
        "n_dealer_kyoku_seen": 0,
        "n_luckyj_tsumo_decision_states_all_for_match": 0,
        "n_child_luckyj_tsumo_decision_states": 0,
        "n_dealer_luckyj_tsumo_decision_states": 0,
        "n_child_vs_riichi_closed_shanten_decisions": 0,
        "n_child_open_hand_turn7plus_observations": 0,
        "n_child_immediate_riichi_reactions": 0,
        "n_errors_in_kyoku": 0,
        "errors": [],
    }

    for row_index, row in enumerate(rows, 1):
        if row_index % 200 == 0:
            print(f"processed {row_index}/{len(rows)} reports", flush=True)
        target = row.get("actor")
        if target is None or not (0 <= target < 4):
            continue
        try:
            data = base.fetch_report(row["report_id"])
            base.normalize_report(data)
            summary["n_reports_processed"] += 1
        except Exception as exc:
            summary["n_reports_failed"] += 1
            if len(summary["errors"]) < 30:
                summary["errors"].append({"report_id": row.get("report_id"), "error": repr(exc)})
            continue

        for kyoku_index, kyoku in enumerate(data.get("pred") or []):
            summary["n_kyoku_seen"] += 1
            try:
                start = (kyoku[0].get("info", {}).get("msg", {}) if kyoku else {}) or {}
                split = dealer_split_key(start, target)
                if split == "child":
                    summary["n_child_kyoku_seen"] += 1
                elif split == "dealer":
                    summary["n_dealer_kyoku_seen"] += 1

                start_hands = start.get("tehais") or [[], [], [], []]
                hands = [list(start_hands[i]) if i < len(start_hands) else [] for i in range(4)]
                discards: list[list[str]] = [[], [], [], []]
                open_melds = [0, 0, 0, 0]
                melds: list[list[list[str]]] = [[], [], [], []]
                reached = [False, False, False, False]
                safe_tiles_vs_riichi: list[set[int]] = [set(), set(), set(), set()]
                pending_riichi_discard = [False, False, False, False]
                pending_reaction: dict[int, dict[str, Any]] = {}
                dora_markers: list[str] = []
                rx2.append_dora_marker(dora_markers, start.get("dora_marker"))

                for pos, state in enumerate(kyoku):
                    msg = state.get("info", {}).get("msg", {}) or {}
                    actor = msg.get("actor")
                    msg_type = msg.get("type")

                    if msg_type == "dora":
                        rx2.append_dora_marker(dora_markers, msg.get("dora_marker"))
                        continue

                    if msg_type == "tsumo":
                        if actor is not None and 0 <= actor < 4:
                            pai = msg.get("pai")
                            if pai:
                                hands[actor].append(pai)

                        actual = msg.get("real_dahai")
                        is_luckyj_decision = actor == target and actual not in (None, "?") and "dahai_pred" in state

                        if is_luckyj_decision:
                            summary["n_luckyj_tsumo_decision_states_all_for_match"] += 1
                            if split == "child":
                                summary["n_child_luckyj_tsumo_decision_states"] += 1
                            elif split == "dealer":
                                summary["n_dealer_luckyj_tsumo_decision_states"] += 1
                            top_tile = top_pred_tile(state.get("dahai_pred"))
                            if top_tile is not None:
                                match_stats[split].add(same_tile(top_tile, actual))

                            own_reached = bool(msg.get("reached") or (target < len(reached) and reached[target]))
                            closed_shanten_value = rx2.compute_closed_shanten_if_closed(hands[target], open_melds, target) if not own_reached else None
                            closed_shanten = rx2.closed_shanten_bucket_from_value(closed_shanten_value) if closed_shanten_value is not None else None
                            actual_danger = rx2.discard_danger(state, target, actual)
                            threat = rx2.classify_table_threat(target, open_melds, reached, discards, state)
                            threat_cat = threat["category"]
                            lb = rx2.left_bucket(msg.get("left_hai_num"))
                            tiles_left_le20 = rx2.yes_no(lb == "<=20") if lb != "unknown" else "unknown"

                            if threat_cat in {"single_riichi", "riichi_plus_more"}:
                                if closed_shanten is not None:
                                    vs_riichi_by_split[split][closed_shanten].add(actual_danger)
                                    if lb == "<=20":
                                        vs_riichi_last20_by_split[split][closed_shanten].add(actual_danger)
                                    if split == "child":
                                        summary["n_child_vs_riichi_closed_shanten_decisions"] += 1

                                if split == "child" and closed_shanten in {"0", "1"}:
                                    riichi_seat = threat.get("max_opponent_seat")
                                    riichi_dealer = rx2.dealer_bucket(start, riichi_seat)
                                    safe_set = safe_tiles_vs_riichi[riichi_seat] if isinstance(riichi_seat, int) and 0 <= riichi_seat < 4 else set()
                                    genbutsu_count = rx2.count_safe_tiles_in_hand(hands[target], safe_set)
                                    dora_count = rx2.hand_dora_count(hands[target], dora_markers)
                                    obs = {
                                        "danger": actual_danger,
                                        "tiles_left_le20": tiles_left_le20,
                                        "second_threat_present": rx2.yes_no(threat_cat == "riichi_plus_more"),
                                        "dora_count": rx2.dora_count_bucket(dora_count),
                                        "riichi_is_dealer": riichi_dealer,
                                    }
                                    if closed_shanten == "0":
                                        obs["genbutsu_count"] = rx2.genbutsu_count_bucket(genbutsu_count)
                                    else:
                                        obs["genbutsu_zero"] = rx2.yes_no(genbutsu_count == 0)
                                    vs_condition_observations[closed_shanten].append(obs)

                            if threat_cat in {"2_meld_opponent", "3plus_meld_opponent"}:
                                opponent = threat.get("max_opponent_seat")
                                meld_key = "3+" if (threat.get("max_opponent_melds") or 0) >= 3 else "2"
                                turn_key = threat.get("max_opponent_turn_bucket") or "unknown"
                                if turn_key in TURN_BUCKET_ORDER:
                                    get_bin(open_by_split[split], meld_key, turn_key).add(actual_danger)
                                opponent_turn = threat.get("max_opponent_turn")
                                if split == "child" and isinstance(opponent, int) and opponent_turn is not None and opponent_turn >= 7:
                                    open_condition_observations.append({
                                        "danger": actual_danger,
                                        "own_shanten_bucket": rx2.own_shanten_leq1_bucket(hands[target]),
                                        "opponent_is_dealer": rx2.dealer_bucket(start, opponent),
                                    })
                                    summary["n_child_open_hand_turn7plus_observations"] += 1

                            if pending_reaction:
                                actual_idx = rx2.tile_index(actual)
                                for riichi_seat in sorted(list(pending_reaction)):
                                    if riichi_seat == target:
                                        continue
                                    safe_tiles = pending_reaction[riichi_seat].get("safe_tile_indices", set())
                                    genbutsu = actual_idx is not None and actual_idx in safe_tiles
                                    reaction_shanten = closed_shanten if closed_shanten is not None else "unknown"
                                    if reaction_shanten in SHANTEN_ORDER:
                                        immediate_by_split[split][reaction_shanten].add(genbutsu)
                                        if split == "child":
                                            summary["n_child_immediate_riichi_reactions"] += 1
                                    pending_reaction.pop(riichi_seat, None)

                        if actor is not None and 0 <= actor < 4:
                            discard = msg.get("real_dahai")
                            if discard and discard != "?":
                                rx2.remove_tile(hands[actor], discard)

                    elif msg_type in rx2.HURO_TYPES:
                        if actor is not None and 0 <= actor < 4:
                            open_melds[actor] += 1
                            consumed = list(msg.get("consumed") or [])
                            called = msg.get("pai")
                            meld_tiles = consumed + ([called] if called else [])
                            melds[actor].append(meld_tiles)
                            for tile in consumed:
                                rx2.remove_tile(hands[actor], tile)
                            discard = msg.get("real_dahai")
                            if discard and discard != "?":
                                rx2.remove_tile(hands[actor], discard)

                    elif msg_type == "ankan":
                        if actor is not None and 0 <= actor < 4:
                            open_melds[actor] += 1
                            consumed = list(msg.get("consumed") or [])
                            melds[actor].append(consumed)
                            for tile in consumed:
                                rx2.remove_tile(hands[actor], tile)

                    elif msg_type == "kakan":
                        if actor is not None and 0 <= actor < 4:
                            pai = msg.get("pai")
                            rx2.remove_tile(hands[actor], pai)
                            pai_idx = rx2.tile_index(pai)
                            attached = False
                            if pai_idx is not None:
                                for meld in melds[actor]:
                                    if sum(1 for tile in meld if rx2.tile_index(tile) == pai_idx) >= 3:
                                        meld.append(pai)
                                        attached = True
                                        break
                            if not attached and pai:
                                melds[actor].append([pai])

                    elif msg_type == "reach":
                        if actor is not None and 0 <= actor < 4:
                            reached[actor] = True
                            pending_riichi_discard[actor] = True
                            existing_safe = {idx for idx in (rx2.tile_index(tile) for tile in discards[actor]) if idx is not None}
                            safe_tiles_vs_riichi[actor] = set(existing_safe)
                            if actor != target:
                                pending_reaction[actor] = {
                                    "kyoku_index": kyoku_index,
                                    "pos": pos,
                                    "riichi_seat": actor,
                                    "safe_tile_indices": set(existing_safe),
                                }

                    elif msg_type == "dahai":
                        tile = msg.get("pai")
                        if actor is not None and 0 <= actor < 4 and tile:
                            idx = rx2.tile_index(tile)
                            discards[actor].append(tile)
                            if idx is not None:
                                if reached[actor]:
                                    safe_tiles_vs_riichi[actor].add(idx)
                                for reaction in pending_reaction.values():
                                    if reaction.get("riichi_seat") == actor:
                                        reaction.setdefault("safe_tile_indices", set()).add(idx)
                            if pending_riichi_discard[actor]:
                                pending_riichi_discard[actor] = False

            except Exception as exc:
                summary["n_errors_in_kyoku"] += 1
                if len(summary["errors"]) < 30:
                    summary["errors"].append({"report_id": row.get("report_id"), "kyoku_index": kyoku_index, "error": repr(exc)})
                continue

    dealer_vs_child_match = {
        key: match_stats[key].to_dict(count_key="top_discard_matches", rate_key="match_rate_pct")
        for key in ["dealer", "child", "unknown"]
    }
    if dealer_vs_child_match["dealer"]["match_rate_pct"] is not None and dealer_vs_child_match["child"]["match_rate_pct"] is not None:
        dealer_vs_child_match["dealer_minus_child_pp"] = round1(
            dealer_vs_child_match["dealer"]["match_rate_pct"] - dealer_vs_child_match["child"]["match_rate_pct"]
        )

    baseline_vs_riichi = {
        sh: side_by_side_push(
            vs_riichi_by_split["child"][sh].to_dict(),
            vs_riichi_by_split["dealer"][sh].to_dict(),
            PUBLISHED["vs_riichi_push_by_closed_shanten"][sh],
        )
        for sh in SHANTEN_ORDER
    }
    baseline_last20 = {
        sh: side_by_side_push(
            vs_riichi_last20_by_split["child"][sh].to_dict(),
            vs_riichi_last20_by_split["dealer"][sh].to_dict(),
            PUBLISHED["last20_vs_riichi_push_by_closed_shanten"][sh],
        )
        for sh in SHANTEN_ORDER
    }
    baseline_immediate = {
        sh: side_by_side_prop(
            immediate_by_split["child"][sh].to_dict(count_key="genbutsu_count", rate_key="genbutsu_rate_pct"),
            immediate_by_split["dealer"][sh].to_dict(count_key="genbutsu_count", rate_key="genbutsu_rate_pct"),
            PUBLISHED["first_discard_after_riichi_genbutsu_by_closed_shanten"][sh],
            "genbutsu_rate_pct",
        )
        for sh in SHANTEN_ORDER
    }
    baseline_open = {
        meld: {
            turn: side_by_side_push(
                bin_dict(open_by_split["child"], meld, turn),
                bin_dict(open_by_split["dealer"], meld, turn),
                PUBLISHED["open_hand_push_by_meld_count_and_turn"][meld][turn],
            )
            for turn in TURN_BUCKET_ORDER
        }
        for meld in MELD_ORDER
    }

    tenpai_specs = [
        ("genbutsu_count", GENBUTSU_ORDER),
        ("tiles_left_le20", YES_NO_UNKNOWN),
        ("dora_count", ["0", "1", "2", "3+"]),
        ("second_threat_present", YES_NO_UNKNOWN),
    ]
    one_shanten_specs = [
        ("genbutsu_zero", YES_NO_UNKNOWN),
        ("tiles_left_le20", YES_NO_UNKNOWN),
        ("riichi_is_dealer", YES_NO_UNKNOWN),
    ]
    open_specs = [
        ("own_shanten_bucket", OPEN_OWN_SHANTEN_ORDER),
        ("opponent_is_dealer", YES_NO_UNKNOWN),
    ]

    tenpai_conditions = rx2.finalize_condition_effects(vs_condition_observations["0"], tenpai_specs)
    one_conditions = rx2.finalize_condition_effects(vs_condition_observations["1"], one_shanten_specs)
    open_conditions = rx2.finalize_condition_effects(open_condition_observations, open_specs)

    def overall_from_observations(observations: list[dict[str, Any]]) -> dict[str, Any]:
        stat = rx2.BinStats()
        for obs in observations:
            stat.add(obs.get("danger"))
        return stat.to_dict()

    condition_outputs = {
        "vs_riichi_closed_shanten": {
            "0": {
                "scope": "child-only closed tenpai decisions while facing at least one riichi",
                "overall": overall_from_observations(vs_condition_observations["0"]),
                "conditions": tenpai_conditions,
            },
            "1": {
                "scope": "child-only closed 1-shanten decisions while facing at least one riichi",
                "overall": overall_from_observations(vs_condition_observations["1"]),
                "conditions": one_conditions,
            },
        },
        "open_hand_turn7plus": {
            "scope": "child-only no-riichi states classified as 2_meld_opponent or 3plus_meld_opponent, selected opponent turn >= 7",
            "overall": overall_from_observations(open_condition_observations),
            "conditions": open_conditions,
        },
    }
    condition_outputs["significant_effects"] = {
        "tenpai_vs_riichi": rx2.flatten_significant_effects(tenpai_conditions, shanten="0", scope="tenpai_vs_riichi"),
        "one_shanten_vs_riichi": rx2.flatten_significant_effects(one_conditions, shanten="1", scope="one_shanten_vs_riichi"),
        "open_hand_turn7plus": rx2.flatten_significant_effects(open_conditions, scope="open_hand_turn7plus"),
    }

    changed: list[dict[str, Any]] = []
    for sh, row in baseline_vs_riichi.items():
        append_baseline_changes(changed, "vs_riichi_push_by_closed_shanten", [sh], row)
    for sh, row in baseline_last20.items():
        append_baseline_changes(changed, "last20_vs_riichi_push_by_closed_shanten", [sh], row)
    for sh, row in baseline_immediate.items():
        append_baseline_changes(changed, "first_discard_after_riichi_genbutsu_by_closed_shanten", [sh], row)
    for meld, by_turn in baseline_open.items():
        for turn, row in by_turn.items():
            append_baseline_changes(changed, "open_hand_push_by_meld_count_and_turn", [meld, turn], row)
    append_condition_changes(changed, condition_outputs)
    changed.sort(key=lambda item: abs(item.get("delta_pp", item.get("movement_pp", 0)) or 0), reverse=True)

    output: dict[str, Any] = {
        "definitions": {
            "scope": "rx3 restricts prescription baselines and condition effects to kyoku where LuckyJ is not dealer; dealer-only numbers are shown only as side-by-side diagnostics.",
            "hypothesis_check_scope": "All LuckyJ tsumo states with real_dahai and dahai_pred are counted before any push/fold filtering; dahai_pred[0] is treated as Nishiki head model.",
            "nishiki_top_discard_match": "top 34-tile index in state['dahai_pred'][0] equals real_dahai by 34-tile class.",
            "danger": "For LuckyJ's actual discard, max(state[danger_s/t/k][LuckyJ seat][tile_index] / 10000), reused from scripts/mine_rx2_defense.py.",
            "push": "Legacy field name: actual discard danger > 0.05. This is a danger-threshold proxy, not a strategic push/fold classifier.",
            "closed_shanten": "No own melds and not own riichi; shanten is mahjong.shanten over LuckyJ's current 14-tile hand. Buckets 0/1/2/3+.",
            "vs_riichi_scope": "States classified as single_riichi or riichi_plus_more by scripts/mine_rx2_defense.py classifier.",
            "last20": "left_hai_num <= 20.",
            "first_discard_after_riichi_genbutsu": "For each opponent riichi declaration, LuckyJ's next tsumo discard is genbutsu if its tile index is in that riichi player's own river, including the declaration discard.",
            "open_hand_scope": "No-riichi states classified as 2_meld_opponent or 3plus_meld_opponent, using the selected max-open opponent and turn bucket.",
            "condition_effect_delta": "above-5%-danger rate(condition value) minus the rate for all other values. significant=true only when value and complement both have n>=150 and |delta| exceeds the combined 95% CI half-width.",
            "excluded_published_modifier": "The published tenpai + LuckyJ-is-dealer ~=68% modifier is definitionally excluded from child-only prescriptions.",
        },
        "summary": summary,
        "dealer_vs_child_naga_match": dealer_vs_child_match,
        "child_only_baselines": {
            "vs_riichi_push_by_closed_shanten": baseline_vs_riichi,
            "last20_vs_riichi_push_by_closed_shanten": baseline_last20,
            "first_discard_after_riichi_genbutsu_by_closed_shanten": baseline_immediate,
            "open_hand_push_by_meld_count_and_turn": baseline_open,
        },
        "condition_effects_child_only": condition_outputs,
        "published_reference": {
            "baselines": PUBLISHED,
            "condition_numbers_compared": PUBLISHED_CONDITION_NUMBERS,
            "own_dealer_modifier_excluded": "tenpai + LuckyJ-is-dealer ~=68%",
        },
        "changed_vs_published": changed,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}", flush=True)
    print(json.dumps({
        "dealer_vs_child_naga_match": output["dealer_vs_child_naga_match"],
        "changed_vs_published": output["changed_vs_published"],
        "summary": output["summary"],
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
