#!/usr/bin/env python3
"""Build static Mortal cross-checks for the LuckyJ online book.

The script uses local-only assets:
  - Equim-chan Mortal/libriichi installed in the project venv
  - downloaded Mortal policy files under ~/Downloads/mortal_model_policy
  - local Mjai logs under ~/Downloads/mjlog_combined_local_mjai

Only the compact model outputs and commentary are written to site/mortal-analysis.json.
Raw logs, weights, and local source files stay outside the repository.
"""

from __future__ import annotations

import argparse
import copy
import gzip
import importlib.util
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLES = ROOT / "site" / "point-examples.json"
DEFAULT_OUTPUT = ROOT / "site" / "mortal-analysis.json"
DEFAULT_LOG_DIR = Path.home() / "Downloads" / "mjlog_combined_local_mjai"
DEFAULT_MODEL = Path.home() / "Downloads" / "mortal_model_policy" / "model.py"

TILE_BY_ACTION = [
    "1m",
    "2m",
    "3m",
    "4m",
    "5m",
    "6m",
    "7m",
    "8m",
    "9m",
    "1p",
    "2p",
    "3p",
    "4p",
    "5p",
    "6p",
    "7p",
    "8p",
    "9p",
    "1s",
    "2s",
    "3s",
    "4s",
    "5s",
    "6s",
    "7s",
    "8s",
    "9s",
    "E",
    "S",
    "W",
    "N",
    "P",
    "F",
    "C",
    "5mr",
    "5pr",
    "5sr",
]

ACTION_LABELS = {
    37: "Reach",
    38: "Chi low",
    39: "Chi middle",
    40: "Chi high",
    41: "Pon",
    42: "Kan",
    43: "Win",
    44: "Abortive draw",
    45: "Pass",
}


@dataclass(frozen=True)
class Opportunity:
    log_id: str
    kyoku_index: int
    event_index: int
    trigger: dict[str, Any]
    left: int | None
    kind: str
    reaction: dict[str, Any] | None
    actual_events: list[dict[str, Any]]
    post_call_reaction: dict[str, Any] | None = None


def read_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def log_id_from_paifu(paifu: str) -> str:
    match = re.search(r"log=([^&]+)", paifu)
    if not match:
        raise ValueError(f"could not parse Tenhou log id from {paifu!r}")
    return match.group(1)


def tw_from_paifu(paifu: str) -> int | None:
    match = re.search(r"[?&]tw=(\d+)", paifu)
    return int(match.group(1)) if match else None


def install_libriichi_aliases() -> None:
    """Expose maturin's dynamic submodules at the import paths model.py uses."""
    import libriichi

    for name in ["mjai", "consts", "dataset", "state", "arena", "stat"]:
        if hasattr(libriichi, name):
            sys.modules[f"libriichi.{name}"] = getattr(libriichi, name)


def load_mortal_engine(model_py: Path):
    install_libriichi_aliases()
    spec = importlib.util.spec_from_file_location("downloaded_mortal_policy_model", model_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {model_py}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_engine()


def load_log(path: Path) -> list[dict[str, Any]]:
    with gzip.open(path, "rt") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def actor_for_luckyj(events: list[dict[str, Any]], fallback: int | None) -> int:
    names = events[0].get("names", [])
    for idx, name in enumerate(names):
        if "LuckyJ" in str(name):
            return idx
    if fallback is not None:
        return fallback
    raise ValueError("could not identify LuckyJ actor")


def parse_reaction(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    return json.loads(raw)


def own_actual_after(events: list[dict[str, Any]], start: int, actor: int) -> list[dict[str, Any]]:
    actual: list[dict[str, Any]] = []
    for event in events[start + 1 :]:
        if event["type"] in {"tsumo", "end_kyoku", "end_game"}:
            break
        if event.get("actor") == actor:
            actual.append(event)
            if event["type"] == "dahai":
                break
    return actual


def call_actual_after(events: list[dict[str, Any]], start: int, actor: int) -> list[dict[str, Any]]:
    actual: list[dict[str, Any]] = []
    for event in events[start + 1 :]:
        if event["type"] in {"tsumo", "end_kyoku", "end_game"}:
            break
        if event.get("actor") == actor:
            actual.append(event)
            if event["type"] == "dahai":
                break
    return actual


def replay_opportunities(log_id: str, events: list[dict[str, Any]], actor: int, engine) -> list[Opportunity]:
    from libriichi.mjai import Bot

    bot = Bot(engine, actor)
    opportunities: list[Opportunity] = []
    kyoku_index = -1
    tsumo_count = 0
    pending_call_idx: int | None = None
    post_call_reaction: dict[str, Any] | None = None

    for index, event in enumerate(events):
        if event["type"] == "start_kyoku":
            kyoku_index += 1
            tsumo_count = 0
            pending_call_idx = None
            post_call_reaction = None

        if event["type"] == "tsumo":
            tsumo_count += 1

        reaction = parse_reaction(bot.react(json.dumps(event, ensure_ascii=False), can_act=True))

        if event["type"] == "dahai" and event.get("actor") != actor and reaction is not None:
            actual = call_actual_after(events, index, actor)
            opp = Opportunity(
                log_id=log_id,
                kyoku_index=kyoku_index,
                event_index=index,
                trigger=event,
                left=70 - tsumo_count,
                kind="call",
                reaction=reaction,
                actual_events=actual,
            )
            opportunities.append(opp)
            if actual and actual[0]["type"] in {"chi", "pon", "daiminkan"}:
                pending_call_idx = len(opportunities) - 1
            else:
                pending_call_idx = None
            post_call_reaction = None
            continue

        if event.get("actor") == actor and event["type"] in {"chi", "pon", "daiminkan"} and reaction is not None:
            post_call_reaction = reaction
            if pending_call_idx is not None:
                prev = opportunities[pending_call_idx]
                opportunities[pending_call_idx] = Opportunity(
                    log_id=prev.log_id,
                    kyoku_index=prev.kyoku_index,
                    event_index=prev.event_index,
                    trigger=prev.trigger,
                    left=prev.left,
                    kind=prev.kind,
                    reaction=prev.reaction,
                    actual_events=prev.actual_events,
                    post_call_reaction=post_call_reaction,
                )
            continue

        if event["type"] == "tsumo" and event.get("actor") == actor and reaction is not None:
            opportunities.append(
                Opportunity(
                    log_id=log_id,
                    kyoku_index=kyoku_index,
                    event_index=index,
                    trigger=event,
                    left=70 - tsumo_count,
                    kind="draw",
                    reaction=reaction,
                    actual_events=own_actual_after(events, index, actor),
                )
            )

    return opportunities


def action_id_to_label(action_id: int) -> str:
    if 0 <= action_id < len(TILE_BY_ACTION):
        return f"Discard {TILE_BY_ACTION[action_id]}"
    return ACTION_LABELS.get(action_id, f"Action {action_id}")


def decode_candidates(reaction: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not reaction:
        return []
    meta = reaction.get("meta") or {}
    q_values = meta.get("q_values") or []
    mask_bits = int(meta.get("mask_bits") or 0)
    legal = [idx for idx in range(46) if (mask_bits >> idx) & 1]
    candidates = []
    for action_id, probability in zip(legal, q_values):
        item: dict[str, Any] = {
            "action_id": action_id,
            "label": action_id_to_label(action_id),
            "probability": round(float(probability), 6),
        }
        if 0 <= action_id < len(TILE_BY_ACTION):
            item["type"] = "dahai"
            item["tile"] = TILE_BY_ACTION[action_id]
        elif action_id in ACTION_LABELS:
            item["type"] = ACTION_LABELS[action_id].lower().replace(" ", "_")
        candidates.append(item)
    return sorted(candidates, key=lambda item: item["probability"], reverse=True)


def model_choice(reaction: dict[str, Any] | None) -> dict[str, Any]:
    if not reaction:
        return {"type": "none", "label": "No action"}
    typ = reaction.get("type")
    if typ == "dahai":
        return {"type": "dahai", "tile": reaction.get("pai"), "label": f"Discard {reaction.get('pai')}"}
    if typ == "reach":
        return {"type": "reach", "label": "Reach"}
    if typ in {"chi", "pon", "daiminkan", "ankan", "kakan"}:
        label = typ.capitalize()
        if reaction.get("pai"):
            label += f" {reaction['pai']}"
        return {
            "type": typ,
            "tile": reaction.get("pai"),
            "consumed": reaction.get("consumed"),
            "label": label,
        }
    if typ == "hora":
        return {"type": "hora", "label": "Win"}
    if typ == "ryukyoku":
        return {"type": "ryukyoku", "label": "Abortive draw"}
    if typ == "none":
        return {"type": "none", "label": "Pass"}
    return {"type": typ or "none", "label": typ or "No action"}


def actual_choice(events: list[dict[str, Any]], example: dict[str, Any]) -> dict[str, Any]:
    if example.get("kind") == "call":
        call = next((event for event in events if event["type"] in {"chi", "pon", "daiminkan"}), None)
        discard = next((event for event in events if event["type"] == "dahai"), None)
        return {
            "type": call["type"] if call else "none",
            "tile": call.get("pai") if call else None,
            "discard_after_call": discard.get("pai") if discard else None,
            "label": f"{(call['type'].capitalize() if call else 'Pass')} {call.get('pai') if call else ''}".strip(),
        }
    if example.get("kind") == "reach":
        reached = any(event["type"] == "reach" for event in events)
        discard = next((event for event in events if event["type"] == "dahai"), None)
        return {
            "type": "reach" if reached else "dahai",
            "tile": discard.get("pai") if discard else None,
            "label": f"{'Reach, discard' if reached else 'Discard'} {discard.get('pai') if discard else ''}".strip(),
        }
    discard = next((event for event in events if event["type"] == "dahai"), None)
    return {
        "type": "dahai",
        "tile": discard.get("pai") if discard else example.get("actual"),
        "label": f"Discard {discard.get('pai') if discard else example.get('actual')}",
    }


def matches_example(opp: Opportunity, example: dict[str, Any]) -> bool:
    if opp.kyoku_index != example["kyoku_index"]:
        return False

    if example.get("kind") == "call":
        if opp.kind != "call":
            return False
        call = next((event for event in opp.actual_events if event["type"] in {"chi", "pon", "daiminkan"}), None)
        discard = next((event for event in opp.actual_events if event["type"] == "dahai"), None)
        return bool(
            call
            and call["type"] == str(example.get("call", "")).lower()
            and call.get("pai") == example.get("called_tile")
            and (not example.get("discard_after_call") or (discard and discard.get("pai") == example["discard_after_call"]))
        )

    if opp.kind != "draw":
        return False
    actual = actual_choice(opp.actual_events, example)
    if example.get("kind") == "reach":
        return actual["type"] == "reach" and actual.get("tile") == example.get("actual")
    return actual.get("tile") == example.get("actual")


def choose_opportunity(opportunities: list[Opportunity], example: dict[str, Any]) -> Opportunity:
    matches = [opp for opp in opportunities if matches_example(opp, example)]
    if not matches:
        raise RuntimeError(f"no Mortal opportunity matched {example['point']}")
    target_left = example.get("left")
    return min(matches, key=lambda opp: abs((opp.left or target_left or 0) - (target_left or 0)))


def agrees_with_luckyj(model: dict[str, Any], actual: dict[str, Any], example: dict[str, Any]) -> bool:
    if example.get("kind") == "call":
        return model["type"] == actual["type"] and model.get("tile") == actual.get("tile")
    if example.get("kind") == "reach":
        return model["type"] == "reach"
    return model["type"] == "dahai" and model.get("tile") == actual.get("tile")


def agrees_with_naga(model: dict[str, Any], example: dict[str, Any]) -> bool | None:
    naga = example.get("naga")
    if not naga:
        return None
    if example.get("kind") == "reach":
        return model["type"] == "reach" or (model["type"] == "dahai" and model.get("tile") == naga)
    return model["type"] == "dahai" and model.get("tile") == naga


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    keep = ["type", "actor", "target", "pai", "consumed", "tsumogiri"]
    return {key: event[key] for key in keep if key in event}


def example_signature(point: str, example: dict[str, Any]) -> tuple[Any, ...]:
    kind = example.get("kind")
    if kind == "call":
        action_type = str(example.get("call", "")).lower()
        action_tile = example.get("called_tile")
        post_discard = example.get("discard_after_call")
    elif kind == "reach":
        action_type = "reach"
        action_tile = example.get("actual")
        post_discard = None
    else:
        action_type = "dahai"
        action_tile = example.get("actual")
        post_discard = None
    return (
        point,
        log_id_from_paifu(example["paifu"]),
        example.get("kyoku_index"),
        example.get("left"),
        action_type,
        action_tile,
        post_discard,
    )


def output_signature(item: dict[str, Any]) -> tuple[Any, ...] | None:
    if item.get("input_signature"):
        return tuple(item["input_signature"])
    actual = item.get("actual") or {}
    if item.get("mortal", {}).get("label") == "Mortal replay unavailable":
        return None
    action_type = actual.get("type")
    action_tile = actual.get("tile")
    post_discard = actual.get("discard_after_call")
    return (
        item.get("point"),
        item.get("log_id"),
        item.get("kyoku_index"),
        item.get("left"),
        action_type,
        action_tile,
        post_discard,
    )


def existing_mortal_cache(path: Path) -> dict[tuple[Any, ...], dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except (OSError, json.JSONDecodeError):
        return {}
    cache: dict[tuple[Any, ...], dict[str, Any]] = {}
    for rows in (data.get("points") or {}).values():
        row_list = rows if isinstance(rows, list) else [rows]
        for item in row_list:
            sig = output_signature(item)
            if sig:
                cache[sig] = item
    return cache


def build(args: argparse.Namespace) -> dict[str, Any]:
    raw_examples: dict[str, Any] = read_json(args.examples)
    examples: list[tuple[str, int, dict[str, Any]]] = []
    for point, rows in raw_examples.items():
        if isinstance(rows, list):
            examples.extend((point, idx, example) for idx, example in enumerate(rows, 1) if example)
        elif rows:
            examples.append((point, int(rows.get("example_index") or 1), rows))

    cache = existing_mortal_cache(args.output)
    uncached = [(point, index, example) for point, index, example in examples if example_signature(point, example) not in cache]
    log_ids = sorted({log_id_from_paifu(example["paifu"]) for _, _, example in uncached})

    opportunities_by_log: dict[str, list[Opportunity]] = {}
    if uncached:
        engine = load_mortal_engine(args.model)
        for log_id in log_ids:
            path = args.log_dir / f"{log_id}.json.gz"
            events = load_log(path)
            fallback = next((tw_from_paifu(example["paifu"]) for _, _, example in uncached if log_id_from_paifu(example["paifu"]) == log_id), None)
            actor = actor_for_luckyj(events, fallback)
            opportunities_by_log[log_id] = replay_opportunities(log_id, events, actor, engine)

    output: dict[str, Any] = {
        "meta": {
            "model": "Mortal policy model, local downloaded weights",
            "library": "Equim-chan Mortal/libriichi local replay",
            "source": "Generated from local Mjai logs; raw logs and weights stay local.",
        },
        "points": {},
    }

    missing: list[dict[str, Any]] = []
    for point, index, example in examples:
        sig = example_signature(point, example)
        cached = cache.get(sig)
        if cached:
            item = copy.deepcopy(cached)
            item["point"] = point
            item["example_index"] = index
            item["input_signature"] = list(sig)
            item.setdefault("kind", example.get("kind"))
            # The replay commentary is written by hand now; Mortal's rows carry only its verdict.
            for field in ("read", "how_to_use", "read_ja", "how_to_use_ja"):
                item.pop(field, None)
            output["points"].setdefault(point, []).append(item)
            continue

        log_id = log_id_from_paifu(example["paifu"])
        point_rows = output["points"].setdefault(point, [])
        try:
            opp = choose_opportunity(opportunities_by_log[log_id], example)
            model = model_choice(opp.reaction)
            actual = actual_choice(opp.actual_events, example)
            candidates = decode_candidates(opp.reaction)
            top_candidates = candidates[:1]
            post_call_model = model_choice(opp.post_call_reaction) if opp.post_call_reaction else None
            actual_discard_after_call = actual.get("discard_after_call")
            post_call_agrees = (
                post_call_model is not None
                and post_call_model["type"] == "dahai"
                and post_call_model.get("tile") == actual_discard_after_call
            )

            point_rows.append(
                {
                    "point": point,
                    "example_index": index,
                    "kind": example.get("kind"),
                    "input_signature": list(sig),
                    "log_id": log_id,
                    "kyoku_index": opp.kyoku_index,
                    "event_index": opp.event_index,
                    "left": opp.left,
                    "trigger": compact_event(opp.trigger),
                    "actual": actual,
                    "mortal": model,
                    "mortal_agrees_luckyj": agrees_with_luckyj(model, actual, example),
                    "mortal_agrees_naga": agrees_with_naga(model, example),
                    "top_candidates": top_candidates,
                    "post_call_mortal": post_call_model,
                    "post_call_agrees_luckyj": post_call_agrees if post_call_model else None,
                    "post_call_candidates": [],
                }
            )
        except Exception as exc:
            missing.append({"point": point, "example_index": index, "log_id": log_id, "error": str(exc)})
            point_rows.append(
                {
                    "point": point,
                    "example_index": index,
                    "kind": example.get("kind"),
                    "input_signature": list(sig),
                    "log_id": log_id,
                    "left": example.get("left"),
                    "actual": {"type": example.get("kind"), "tile": example.get("actual"), "label": "LuckyJ action"},
                    "mortal": {"type": "none", "label": "Mortal replay unavailable"},
                    "mortal_agrees_luckyj": None,
                    "mortal_agrees_naga": None,
                    "top_candidates": [],
                    "post_call_mortal": None,
                    "post_call_agrees_luckyj": None,
                    "post_call_candidates": [],
                    "error": str(exc),
                }
            )

    output["meta"]["examples"] = len(examples)
    output["meta"]["matched"] = len(examples) - len(missing)
    output["meta"]["reused_cached"] = len(examples) - len(uncached)
    output["meta"]["replayed"] = len(uncached)
    output["meta"]["missing"] = missing

    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = build(args)
    write_json(args.output, data)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
