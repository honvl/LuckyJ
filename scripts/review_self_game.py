#!/usr/bin/env python3
"""Review your own games against LuckyJ's mined habits.

Reads Tenhou-format logs (majsoul-to-naga output, or ``tenhou.net/5/#json=``
links) and reports where the hero seat's decisions diverge from the child-only
baselines in ``analysis/rx3-*.json`` -- the same numbers the Prescriptions
section of the book publishes.

    .venv/bin/python scripts/review_self_game.py data/self_games/<file>.json
    .venv/bin/python scripts/review_self_game.py links.txt --hero 0 --json out.json

Every rate printed beside a LuckyJ figure is a descriptive rate over this
corpus, not a correctness score. The flags are review prompts, not verdicts.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tenhou_replay import (  # noqa: E402
    DRAGONS, base, is_honor, load_logs, name, names, replay,
    result_blocks, result_deltas, round_wind, seat_wind, shanten, waits, yakuhai_for,
)

ROOT = Path(__file__).resolve().parents[1]
RX = {
    "honors": ROOT / "analysis/rx3-honors-2026-07-05.json",
    "defense": ROOT / "analysis/rx3-defense-2026-07-05.json",
    "riichi": ROOT / "analysis/rx3-riichi-2026-07-05.json",
    "calls": ROOT / "analysis/rx3-calls-2026-07-05.json",
}

SAFE_KINDS = {"genbutsu", "suji", "dead"}
# A lone honor with two or more copies already showing sits under the 5% danger
# line the defense baselines use, so releasing one is a fold, not a push.
NOT_A_PUSH = SAFE_KINDS | {"quiet-honor"}


def dig(data, *path, default=None):
    cur = data
    for key in path:
        if isinstance(cur, dict) and key in cur:
            cur = cur[key]
        else:
            return default
    return cur


def load_baselines() -> dict:
    """Pull the published child-only thresholds straight from the mined artifacts."""
    raw = {k: json.loads(p.read_text(encoding="utf-8")) for k, p in RX.items()}
    d, r, c, h = raw["defense"], raw["riichi"], raw["calls"], raw["honors"]
    push = dig(d, "child_only_baselines", "vs_riichi_push_by_closed_shanten", default={})
    genb = dig(d, "child_only_baselines", "first_discard_after_riichi_genbutsu_by_closed_shanten", default={})
    declare = dig(r, "child_dealer_baselines", "child", "riichi_first_opportunity", "by_unseen_waits", default={})
    declare_oya = dig(r, "child_dealer_baselines", "dealer", "riichi_first_opportunity", "by_unseen_waits", default={})
    dragon = dig(h, "child_only_baselines", "lone_yakuhai_cleanup_timing",
                 "summary_by_kind_and_opponent_open", "dragon", default={})
    return {
        "push_vs_riichi": {k: dig(v, "child", "push_rate_pct") for k, v in push.items()},
        "first_answer_genbutsu": {k: dig(v, "child", "genbutsu_rate_pct") for k, v in genb.items()},
        "declare_by_waits": {k: dig(v, "declare_rate_pct") for k, v in declare.items()},
        "declare_by_waits_dealer": {k: dig(v, "declare_rate_pct") for k, v in declare_oya.items()},
        "yakuhai_pon": dig(c, "baselines", "yakuhai_pon", "overall", "child", "pon_rate_pct"),
        "yakuhai_pon_first_copy": dig(c, "baselines", "yakuhai_pon", "first_copy", "child", "pon_rate_pct"),
        "chi_closed": dig(c, "baselines", "chi", "closed_to_open", "child", "chi_rate_pct"),
        "chi_open": dig(c, "baselines", "chi", "already_open", "child", "chi_rate_pct"),
        "lone_dragon_median_turn": dig(dragon, "discard_turn_all", "median"),
        "lone_dragon_paired_pct": dig(dragon, "paired_before_cut_pct", "pct"),
    }


# ---------------------------------------------------------------- safety

def visible_count(tile, event, players, extra=()):
    b = base(tile)
    n = sum(1 for s in range(4) for t in event["rivers"][s] if base(t) == b)
    n += sum(1 for p in players for t in p["meld_tiles"] if base(t) == b)
    n += sum(1 for t in extra if base(t) == b)
    return n


def suji(tile, river):
    b = base(tile)
    suit, num = divmod(b, 10)
    if suit > 3:
        return False
    seen = {base(x) for x in river}
    if num <= 3:
        return suit * 10 + num + 3 in seen
    if num >= 7:
        return suit * 10 + num - 3 in seen
    return (suit * 10 + num - 3 in seen) and (suit * 10 + num + 3 in seen)


def tile_safety(tile, seat, event, players, hand=()):
    """genbutsu / dead / suji / live-*, from the hero's point of view."""
    b = base(tile)
    if any(base(x) == b for x in event["rivers"][seat]):
        return "genbutsu"
    if is_honor(tile):
        seen = visible_count(tile, event, players, hand)
        if seen >= 4:
            return "dead"
        if seen >= 2:
            return "quiet-honor"
        return "live-honor"
    if suji(tile, event["rivers"][seat]):
        return "suji"
    num = base(tile) % 10
    if num in (1, 9):
        return "live-terminal"
    return "live-outer" if num in (2, 3, 7, 8) else "live-middle"


def shanten_bucket(s):
    return "0" if s == 0 else "1" if s == 1 else "2" if s == 2 else "3+"


def wait_bucket(n):
    return "8+" if n >= 8 else "4-7" if n >= 4 else "<=3"


# ---------------------------------------------------------------- review

def review_hand(log, hero, stats, findings):
    g = replay(log)
    kyoku = g["kyoku"]
    hero_is_dealer = g["dealer"] == hero
    my_yakuhai = yakuhai_for(hero, kyoku)
    my_riichi = g["players"][hero]["riichi_event"]
    rnd = g["round_name"]
    delta = result_deltas(g["result"])[hero]
    if my_riichi is not None:
        delta -= 1000  # the declarer's own stick is not in the result deltas
    stats["score_delta"] += delta

    def unseen(tile, event, hand):
        return max(0, 4 - visible_count(tile, event, g["players"], hand))

    declared = False
    honor_first_seen, honor_cut_turn = {}, {}
    for t in g["players"][hero]["haipai"]:
        if base(t) in my_yakuhai:
            honor_first_seen.setdefault(base(t), 0)

    for i, e in enumerate(g["events"]):
        locked = my_riichi is not None and i > my_riichi
        if e["seat"] != hero:
            # --- call opportunities on an opponent discard ---
            if locked:
                continue
            prev = [x for x in g["events"][:i] if x["seat"] == hero]
            if not prev:
                continue
            mine = prev[-1]
            nxt = [x for x in g["events"][i + 1:] if x["seat"] == hero]
            took = bool(nxt and nxt[0]["called"] and nxt[0]["called"]["tile"] == e["tile"])
            hand, mt, closed = mine["hand_after"], mine["meld_tiles"], mine["closed"]
            sh = shanten(hand, mt, closed)
            tile = e["tile"]
            if base(tile) in my_yakuhai and sum(1 for x in hand if base(x) == base(tile)) >= 2:
                stats["yakuhai_pon_chances"] += 1
                stats["yakuhai_pon_taken"] += took
                if not took:
                    findings.append({
                        "kind": "passed-yakuhai-pon", "round": rnd, "turn": e["turn"],
                        "text": f"passed a pon on {name(tile)} at {sh}-shanten "
                                f"(LuckyJ pons the first copy {stats['bl']['yakuhai_pon_first_copy']}% of the time)",
                    })
            if closed and (hero - e["seat"]) % 4 == 1 and not is_honor(tile):
                suit, num = divmod(base(tile), 10)
                hb = [base(x) for x in hand]
                combos = [(-2, -1), (-1, 1), (1, 2)]
                if any(all(1 <= num + d <= 9 and suit * 10 + num + d in hb for d in combo) for combo in combos):
                    stats["chi_chances"] += 1
                    stats["chi_taken"] += took
                    if took and sh > 1:
                        findings.append({
                            "kind": "loose-chi", "round": rnd, "turn": e["turn"],
                            "text": f"chi on {name(tile)} opened the hand at {sh}-shanten "
                                    f"(LuckyJ's first chi from closed is {stats['bl']['chi_closed']}%, "
                                    f"and only 2.4% when the call does not reach 1-shanten)",
                        })
            continue

        # --- my own discard ---
        sh = shanten(e["hand_after"], e["meld_tiles"], e["closed"])
        threats = [s for s, v in e["riichi_seats"].items() if v is not None and s != hero]
        opens = [s for s, n in e["meld_counts"].items() if n and s != hero]

        # honor cleanup timing (skip turns where my own riichi locks the discard)
        if not locked:
            t = base(e["tile"])
            if t in my_yakuhai and t not in honor_cut_turn:
                held = sum(1 for x in e["hand_before"] if base(x) == t)
                if held == 1:
                    honor_cut_turn[t] = e["turn"]
                    under_fire = bool(threats) or any(g["events"][i]["meld_counts"][s] >= 2
                                                      for s in range(4) if s != hero)
                    if e["turn"] > 6 and under_fire:
                        findings.append({
                            "kind": "late-honor", "round": rnd, "turn": e["turn"],
                            "text": f"carried a lone {name(t)} to turn {e['turn']} and spent it with a "
                                    f"threat already on the table (LuckyJ's median for a lone value "
                                    f"honor is turn {stats['bl']['lone_dragon_median_turn']}, "
                                    f"turn 6 once someone has opened)",
                        })

        # riichi declaration
        if e["closed"] and not locked and sh == 0 and not declared:
            w = waits(e["hand_after"], (), True)
            live = sum(unseen(t, e, e["hand_after"]) for t in w)
            bucket = wait_bucket(live)
            stats["declare_chances"][bucket] += 1
            stats["declare_taken"][bucket] += e["riichi"]
            declared = True
            if e["riichi"]:
                table = stats["bl"]["declare_by_waits_dealer" if hero_is_dealer else "declare_by_waits"]
                if bucket == "<=3":
                    findings.append({
                        "kind": "thin-riichi", "round": rnd, "turn": e["turn"],
                        "text": f"riichi on {'/'.join(name(t) for t in w)} with only {live} live tile(s); "
                                f"LuckyJ declares a <=3 wait {table.get('<=3')}% of the time"
                                f"{' as dealer' if hero_is_dealer else ''}",
                    })

        if locked:
            continue

        # push / fold against a live riichi
        if threats:
            kinds = [tile_safety(e["tile"], s, e, g["players"], e["hand_before"]) for s in threats]
            pushed = not all(k in NOT_A_PUSH for k in kinds)
            b = shanten_bucket(sh)
            stats["push_chances"][b] += 1
            stats["push_taken"][b] += pushed
            if stats["first_answer"].get(rnd) is None:
                stats["first_answer"][rnd] = kinds
                stats["first_answer_bucket"][b] += 1
                stats["first_answer_genbutsu"][b] += all(k == "genbutsu" for k in kinds)
            if pushed:
                held_safe = {}
                for s in threats:
                    safe_tiles = [t for t in e["hand_before"]
                                  if t != e["tile"]
                                  and tile_safety(t, s, e, g["players"], e["hand_before"]) == "genbutsu"]
                    if safe_tiles:
                        held_safe[s] = safe_tiles
                if sh >= 2:
                    findings.append({
                        "kind": "far-push", "round": rnd, "turn": e["turn"],
                        "text": f"cut live {name(e['tile'])} at {sh}-shanten against riichi from "
                                f"{', '.join('p%d' % s for s in threats)} "
                                f"(LuckyJ takes a dangerous discard {stats['bl']['push_vs_riichi'].get(b)}% "
                                f"of the time this far out)",
                    })
                if len(held_safe) == len(threats) and held_safe:
                    detail = "; ".join(f"p{s}: {names(set(v))}" for s, v in held_safe.items())
                    findings.append({
                        "kind": "unnamed-safety", "round": rnd, "turn": e["turn"],
                        "text": f"cut live {name(e['tile'])} while holding a genbutsu for every threat ({detail})",
                    })

        # feeding an open hand while far from tenpai
        if opens and not threats and sh >= 2:
            kinds = [tile_safety(e["tile"], s, e, g["players"], e["hand_before"]) for s in opens]
            if not all(k in NOT_A_PUSH for k in kinds):
                stats["open_push_chances"] += 1
                stats["open_push_taken"] += 1
            else:
                stats["open_push_chances"] += 1

    stats["honor_cut_turns"].extend(honor_cut_turn.values())

    for deltas, detail in result_blocks(g["result"]):
        winner, loser = detail[0], detail[1]
        if loser != hero or winner == hero:
            continue
        last = [x for x in g["events"] if x["seat"] == hero][-1]
        sh = shanten(last["hand_after"], last["meld_tiles"], last["closed"])
        findings.append({
            "kind": "deal-in", "round": rnd, "turn": last["turn"],
            "text": f"dealt {name(last['tile'])} into p{winner} for {deltas[hero]} at {sh}-shanten",
        })
    return g


def build_report(logs, hero):
    bl = load_baselines()
    stats = {
        "bl": bl, "score_delta": 0,
        "push_chances": Counter(), "push_taken": Counter(),
        "first_answer": {}, "first_answer_bucket": Counter(), "first_answer_genbutsu": Counter(),
        "declare_chances": Counter(), "declare_taken": Counter(),
        "yakuhai_pon_chances": 0, "yakuhai_pon_taken": 0,
        "chi_chances": 0, "chi_taken": 0,
        "open_push_chances": 0, "open_push_taken": 0,
        "honor_cut_turns": [],
    }
    findings: list[dict] = []
    hands = [review_hand(log, hero, stats, findings) for log in logs]
    return hands, stats, findings


def pct(num, den):
    return None if not den else round(100 * num / den, 1)


def print_report(hands, stats, findings, hero):
    bl = stats["bl"]
    print("=" * 78)
    print(f"SELF-GAME REVIEW vs LuckyJ baselines   seat p{hero}   {len(hands)} hands")
    print("=" * 78)
    start = hands[0]["start_scores"][hero]
    print(f"score {start:+d} -> {start + stats['score_delta']:+d}   net {stats['score_delta']:+d}")
    print()

    print("Push rate against a live riichi (dangerous discard, by your shanten)")
    print(f"  {'hand':<12}{'spots':>7}{'you':>9}{'LuckyJ':>9}")
    for b, label in [("0", "tenpai"), ("1", "1-shanten"), ("2", "2-shanten"), ("3+", "3+ shanten")]:
        n = stats["push_chances"][b]
        if not n:
            continue
        print(f"  {label:<12}{n:>7}{pct(stats['push_taken'][b], n):>8}%{bl['push_vs_riichi'].get(b, '-'):>8}%")

    print("\nFirst answer to a fresh riichi was genbutsu")
    for b, label in [("0", "tenpai"), ("1", "1-shanten"), ("2", "2-shanten"), ("3+", "3+ shanten")]:
        n = stats["first_answer_bucket"][b]
        if not n:
            continue
        print(f"  {label:<12}{n:>7}{pct(stats['first_answer_genbutsu'][b], n):>8}%"
              f"{bl['first_answer_genbutsu'].get(b, '-'):>8}%")

    print("\nRiichi declared at your first tenpai, by live wait tiles")
    for b in ("8+", "4-7", "<=3"):
        n = stats["declare_chances"][b]
        if not n:
            continue
        print(f"  {b:<12}{n:>7}{pct(stats['declare_taken'][b], n):>8}%{bl['declare_by_waits'].get(b, '-'):>8}%")

    print("\nCalls")
    if stats["yakuhai_pon_chances"]:
        print(f"  {'yakuhai pon':<12}{stats['yakuhai_pon_chances']:>7}"
              f"{pct(stats['yakuhai_pon_taken'], stats['yakuhai_pon_chances']):>8}%{bl['yakuhai_pon']:>8}%")
    if stats["chi_chances"]:
        print(f"  {'chi (closed)':<12}{stats['chi_chances']:>7}"
              f"{pct(stats['chi_taken'], stats['chi_chances']):>8}%{bl['chi_closed']:>8}%")
    if stats["honor_cut_turns"]:
        print(f"  lone value honor released: median turn "
              f"{statistics.median(stats['honor_cut_turns']):.0f}"
              f"   LuckyJ turn {bl['lone_dragon_median_turn']}")

    print("\n" + "=" * 78)
    print("FLAGGED DECISIONS")
    print("=" * 78)
    order = ["deal-in", "unnamed-safety", "far-push", "thin-riichi", "passed-yakuhai-pon", "loose-chi", "late-honor"]
    grouped = defaultdict(list)
    for f in findings:
        grouped[f["kind"]].append(f)
    if not findings:
        print("  nothing flagged")
    for kind in order:
        for f in grouped.get(kind, []):
            print(f"  [{kind}] {f['round']} T{f['turn']}: {f['text']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="path to a log JSON file, or a text file of tenhou.net/5 links")
    ap.add_argument("--hero", type=int, default=0, help="seat to review (default 0)")
    ap.add_argument("--json", dest="json_out", help="also write the findings to this path")
    args = ap.parse_args()

    logs = load_logs(args.source)
    hands, stats, findings = build_report(logs, args.hero)
    print_report(hands, stats, findings, args.hero)

    if args.json_out:
        payload = {
            "hero": args.hero,
            "hands": len(hands),
            "score_delta": stats["score_delta"],
            "push_vs_riichi": {b: pct(stats["push_taken"][b], stats["push_chances"][b])
                               for b in stats["push_chances"]},
            "luckyj_push_vs_riichi": stats["bl"]["push_vs_riichi"],
            "declare_by_waits": {b: pct(stats["declare_taken"][b], stats["declare_chances"][b])
                                 for b in stats["declare_chances"]},
            "yakuhai_pon_rate": pct(stats["yakuhai_pon_taken"], stats["yakuhai_pon_chances"]),
            "chi_closed_rate": pct(stats["chi_taken"], stats["chi_chances"]),
            "findings": findings,
        }
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json_out}")


if __name__ == "__main__":
    main()
