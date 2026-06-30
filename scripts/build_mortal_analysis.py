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


def commentary_for(point: str, model: dict[str, Any], actual: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[str, str]:
    top = candidates[0]["probability"] if candidates else None
    second = candidates[1]["probability"] if len(candidates) > 1 else None
    close = top is not None and second is not None and top - second < 0.12
    model_label = model["label"]
    actual_label = actual["label"]

    specific = {
        "point-01": (
            "Mortal checks whether the first-turn honor cut is merely cosmetic or a real plan choice. In this dealer-lead spot, agreement with LuckyJ means the model also values keeping the hand's value core over making the cleanest outside-honor trim.",
            "For play, copy the ordering: score job first, then discard. Do not spend a dora/seat-wind plan just to make the hand look locally tidy on turn one.",
        ),
        "point-02": (
            "This is the controlled-ambiguity test. Mortal's preferred action shows whether the messy hand should keep the dragon/yakuhai switch or simplify immediately. If the top two probabilities are close, treat the spot as a branch-management exercise rather than a simple error.",
            "In play, name the live routes before cutting: open yaku, pair hand, red-five value, and safety. The model split matters less than whether your discard kills a route you still need.",
        ),
        "point-03": (
            "This is a call-contract test: Mortal is judging the pon before seeing the later hand result. A call preference means the model accepts that the closed hand is structurally fake; a pass preference means the hand still lacks enough reward or safety.",
            "When copying, do not say 'bad hand, so call.' Say exactly what the call buys: yaku, clock, and a discard plan after the call.",
        ),
        "point-04": (
            "This is the second-call discipline check. Mortal's call/pass preference matters, but the conditional post-call discard matters just as much: an open hand that cannot stop is not LuckyJ-style pressure.",
            "After every second call, ask what tile remains as the brake. If you cannot name it, the call is too expensive unless the hand is already worth forcing.",
        ),
        "point-05": (
            "This tests future-danger pricing. Mortal is asked whether the useful-looking side tile should leave before the table grows louder, or whether the outside tile should be cleaned first.",
            "For your own games, identify the tile whose danger will age badly. Slow hands should throw future liabilities before those liabilities become mandatory pushes.",
        ),
        "point-06": (
            "This is an early value-class test. Mortal's choice tells whether the isolated terminal is expendable enough to keep the honor switch while the red-five hand is still forming.",
            "Do not chase the cheapest version of a hand that needs points. Keep the tile that can still become value or a stop, but only when the cost tile is genuinely low-purpose.",
        ),
        "point-07": (
            "This is a tempo-call test after the hand is already open. Mortal helps separate a call that actually changes the round clock from a call that only exposes more tiles.",
            "Copy the call only when it creates a real next discard and a real path to completion. Tempo without a contract is just impatience.",
        ),
        "point-08": (
            "This is the riichi-conversion test. Mortal's top action shows whether the hand should turn into table pressure immediately or stay quiet for refinement.",
            "At the table, ask whether riichi changes opponents' behavior enough to justify losing flexibility. If yes, convert; if not, the same discard without riichi can be the better move.",
        ),
        "point-09": (
            "This is the expiring-push test. Mortal evaluates the current draw after the open dora-side threat appears, so it is useful for checking whether LuckyJ's safer discard is real discipline or too timid.",
            "Do not label a hand 'push' once and stop thinking. Every call and draw reprices the next required discard.",
        ),
        "point-10": (
            "This is the late-row precision test. Mortal is valuable here because late LuckyJ disagreements are the least copyable; the model cross-check keeps the analysis from inventing certainty.",
            "In late rows, replace vague upside with exact goals: win, safe tenpai, forced push, or fold. If the model split is close, your river read decides the hand.",
        ),
        "point-11": (
            "This is the safe-tenpai test. Mortal checks whether the visible dragon discard is a legitimate way to preserve draw payments against the live open hand.",
            "Treat noten payments as real equity, but only when the path is safe. A tenpai chase through a live dangerous tile is not the same idea.",
        ),
        "point-12": (
            "This first-discard spot is a calibration case. Mortal helps decide whether the NAGA/LuckyJ split is a meaningful strategic disagreement or just a model-ordering preference in a low-danger position.",
            "Use spots like this to practice humility: when strong models split early, write the claims each tile makes instead of forcing a heroic explanation.",
        ),
        "point-13": (
            "This is the open-hand contract test. Mortal is useful here because the discard is not only about LuckyJ's hand shape; it asks whether the live yakuhai should be cleaned before the opponent's exposed hand can use it as a yaku.",
            "After an opponent opens without a visible yaku, mark dragons, round wind, and that player's seat wind as contract tiles. Keep them only when they are doing real work for your own hand or defense.",
        ),
        "point-14": (
            "This is the defensive-inventory test. Mortal agreeing with LuckyJ over NAGA means the kept river-safe tile is not just a human story: a second model also prefers spending shape while preserving the clearer exit.",
            "When your hand is behind but not ready, count the safe exits before cutting them. A genbutsu tile against multiple opponents can be worth more than two extra visible ukeire if it keeps the next threat playable.",
        ),
    }
    read, use = specific.get(
        point,
        (
            f"Mortal's top action is {model_label}; LuckyJ played {actual_label}. The cross-check is useful because it gives a second model view on whether the disagreement has strategic weight.",
            "Use the model result as a review prompt, not as a command. Copy the move only after the point, route, and danger logic all agree.",
        ),
    )
    if close:
        read += " The top probabilities are close, so this should be studied as a sensitive border spot rather than a one-answer rule."
    return read, use


def build(args: argparse.Namespace) -> dict[str, Any]:
    examples: dict[str, dict[str, Any]] = read_json(args.examples)
    log_ids = sorted({log_id_from_paifu(example["paifu"]) for example in examples.values()})
    engine = load_mortal_engine(args.model)

    opportunities_by_log: dict[str, list[Opportunity]] = {}
    for log_id in log_ids:
        path = args.log_dir / f"{log_id}.json.gz"
        events = load_log(path)
        fallback = next((tw_from_paifu(example["paifu"]) for example in examples.values() if log_id_from_paifu(example["paifu"]) == log_id), None)
        actor = actor_for_luckyj(events, fallback)
        opportunities_by_log[log_id] = replay_opportunities(log_id, events, actor, engine)

    output: dict[str, Any] = {
        "meta": {
            "model": "Mortal policy model, local downloaded weights",
            "library": "Equim-chan Mortal/libriichi local replay",
            "source": "Generated from local Mjai logs; raw logs and weights are intentionally not included.",
        },
        "points": {},
    }

    for point, example in examples.items():
        log_id = log_id_from_paifu(example["paifu"])
        opp = choose_opportunity(opportunities_by_log[log_id], example)
        model = model_choice(opp.reaction)
        actual = actual_choice(opp.actual_events, example)
        candidates = decode_candidates(opp.reaction)[:6]
        post_call_model = model_choice(opp.post_call_reaction) if opp.post_call_reaction else None
        post_call_candidates = decode_candidates(opp.post_call_reaction)[:5] if opp.post_call_reaction else []
        read, use = commentary_for(point, model, actual, candidates)
        actual_discard_after_call = actual.get("discard_after_call")
        post_call_agrees = (
            post_call_model is not None
            and post_call_model["type"] == "dahai"
            and post_call_model.get("tile") == actual_discard_after_call
        )

        output["points"][point] = {
            "point": point,
            "log_id": log_id,
            "kyoku_index": opp.kyoku_index,
            "event_index": opp.event_index,
            "left": opp.left,
            "trigger": compact_event(opp.trigger),
            "actual": actual,
            "mortal": model,
            "mortal_agrees_luckyj": agrees_with_luckyj(model, actual, example),
            "mortal_agrees_naga": agrees_with_naga(model, example),
            "top_candidates": candidates,
            "post_call_mortal": post_call_model,
            "post_call_agrees_luckyj": post_call_agrees if post_call_model else None,
            "post_call_candidates": post_call_candidates,
            "read": read,
            "how_to_use": use,
        }

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
