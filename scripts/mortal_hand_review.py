#!/usr/bin/env python3
"""Walk Honver's seat through chosen hands of a Mahjong Soul game with the local Mortal policy.

Every decision the seat faced in those hands is printed with what was played, Mortal's top three actions with
their probabilities, and the probability Mortal gave the action that was played. Decisions where Mortal's first
choice differs are marked.

    .venv/bin/python scripts/mortal_hand_review.py 260928-90620418 S2-0 S4-0 [--json OUT.json]
    .venv/bin/python scripts/mortal_hand_review.py 260928-90620418            # every hand of the game

The game is found by uuid prefix in data/self_games/majsoul/index.json; hands are named like the guide (East 4-2
as E4-2). The Mortal model and libriichi come from scripts/contrast/mortal_run.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "contrast"))
import mortal_run  # noqa: E402
from tenhou6_to_mjai import convert  # noqa: E402

TILES = ["1m", "2m", "3m", "4m", "5m", "6m", "7m", "8m", "9m", "1p", "2p", "3p", "4p", "5p", "6p", "7p", "8p", "9p",
         "1s", "2s", "3s", "4s", "5s", "6s", "7s", "8s", "9s", "E", "S", "W", "N", "P", "F", "C", "5mr", "5pr", "5sr"]
LABELS = {37: "riichi", 38: "chi (called tile lowest)", 39: "chi (called tile middle)", 40: "chi (called tile highest)",
          41: "pon", 42: "kan", 43: "win", 44: "abortive draw", 45: "pass"}


def label(a: int) -> str:
    return TILES[a] if a <= 36 else LABELS[a]


def num(p: str) -> int:
    return int(p[0]) if p[0].isdigit() else 0


def chi_action(called: str, consumed: list[str]) -> int:
    n = num(called)
    a, b = sorted(num(x) for x in consumed)
    return 38 if n < a else 39 if n < b else 40


def actual_action(events: list[dict], idx: int, seat: int, kind: str) -> int | None:
    """The action the seat took in answer to event ``idx``."""
    if kind == "call":
        # a call or ron answers the discard at once; anything else means the seat passed
        nxt = next((e for e in events[idx + 1:] if e["type"] != "reach_accepted"), None)
        if nxt is None or nxt.get("actor") != seat:
            return 45
        t = nxt["type"]
        if t == "chi":
            return chi_action(nxt["pai"], nxt["consumed"])
        return {"pon": 41, "daiminkan": 42, "hora": 43}.get(t, 45)
    nxt = next((e for e in events[idx + 1:] if e.get("actor") == seat or e["type"] in ("hora", "ryukyoku", "end_kyoku")), None)
    if nxt is None:
        return None
    t = nxt["type"]
    if t == "dahai":
        return TILES.index(nxt["pai"])
    return {"reach": 37, "ankan": 42, "kakan": 42, "hora": 43, "ryukyoku": 44}.get(t)


def review(prefix: str, hands: list[str]) -> list[dict]:
    mortal_run.init()  # loads the model and registers the libriichi submodules
    from libriichi.mjai import Bot

    manifest = json.loads((ROOT / "data/self_games/majsoul/index.json").read_text())
    g = next(x for x in manifest if x["uuid"].startswith(prefix))
    path = Path(g["file"]) if Path(g["file"]).is_absolute() else ROOT / g["file"]
    events = convert(json.loads(path.read_text()))
    seat = g["hero_seat"]
    bot = Bot(mortal_run.ENGINE, seat)
    out = []
    hand_name = None
    my_hand: list[str] = []
    turn = 0
    for idx, ev in enumerate(events):
        if ev["type"] == "start_kyoku":
            hand_name = f"{ev['bakaze']}{ev['kyoku']}-{ev['honba']}"
            my_hand = list(ev["tehais"][seat])
            turn = 0
        active = not hands or hand_name in hands
        kind = None
        if ev.get("actor") == seat and ev["type"] in ("tsumo", "chi", "pon", "daiminkan"):
            kind = "discard"
        elif ev.get("actor") == seat and ev["type"] == "reach":
            kind = "riichi discard"
        elif ev["type"] == "dahai" and ev["actor"] != seat:
            kind = "call"
        if ev.get("actor") == seat:
            if ev["type"] == "tsumo":
                my_hand.append(ev["pai"])
            elif ev["type"] in ("chi", "pon", "daiminkan", "ankan"):
                for t in ev["consumed"]:
                    my_hand.remove(t)
            elif ev["type"] == "kakan":
                my_hand.remove(ev["pai"])
        raw = bot.react(json.dumps(ev, ensure_ascii=False), can_act=active and kind is not None)
        if ev.get("actor") == seat and ev["type"] == "dahai":
            my_hand.remove(ev["pai"])
            turn += 1
        if not (active and kind and raw):
            continue
        probs = mortal_run.probs_of(json.loads(raw))
        if not probs or len(probs) == 1:
            continue
        actual = actual_action(events, idx, seat, "call" if kind == "call" else "discard")
        top = sorted(probs.items(), key=lambda kv: -kv[1])[:3]
        out.append({
            "hand": hand_name, "turn": turn + (1 if kind != "call" else 0), "kind": kind,
            "trigger": f"{ev['type']} {ev.get('pai', '')}".strip() + (f" by seat {ev['actor']}" if kind == "call" else ""),
            "hand_tiles": " ".join(sorted(my_hand, key=lambda p: (p[-1] if p[0].isdigit() else "z", p))),
            "played": label(actual) if actual is not None else None,
            "p_played": round(probs.get(actual, 0.0), 3) if actual is not None else None,
            "mortal": [(label(a), round(p, 3)) for a, p in top],
            "differs": actual is not None and top[0][0] != actual,
        })
    return out


def main() -> None:
    argv = sys.argv[1:]
    out_json = None
    if "--json" in argv:
        i = argv.index("--json")
        out_json = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    prefix, hands = argv[0], argv[1:]
    rows = review(prefix, hands)
    for r in rows:
        mark = "<<" if r["differs"] else "  "
        print(f"{mark} {r['hand']} T{r['turn']:>2} {r['kind']:<14} {r['trigger']:<22} played {r['played']} "
              f"(Mortal {r['p_played']:.0%})  Mortal: " + ", ".join(f"{a} {p:.0%}" for a, p in r["mortal"])
              + (f"   hand {r['hand_tiles']}" if r["kind"] != "call" else ""))
    if out_json:
        Path(out_json).write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
