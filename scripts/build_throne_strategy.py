#!/usr/bin/env python3
"""Draw chapter 55's figures and table from ``analysis/throne-strategy-2026-11-23.json`` (``mine_throne_strategy.py report``).

Three pieces go into ``site/honver.html`` and, with Japanese labels, ``site/honver-ja.html``, each between its own
markers:

- ``throne-push``: tenpai against a riichi with no safe tile that keeps the tenpai, by the hand's value and wait: how
  often you pushed, how often Mortal-S42 pushes in the same spots, and how often Celestials pushed in the Throne games.
- ``throne-place``: the same push rates by your place at the start of the hand.
- ``throne-room``: how the Throne room differs from the Jade room: speed, who stays in, callers, open hands.

``--check`` exits non-zero when a page and the data disagree.

    .venv/bin/python scripts/build_throne_strategy.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "throne-strategy-2026-11-23.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
PARTS = ("throne-push", "throne-place", "throne-room")

WORDS = {
    "en": {
        "push_title": "Tenpai against a riichi: how often each side keeps the tenpai",
        "push_sub": ("Spots where every tile that keeps the tenpai is unsafe against the riichi. Each row is a kind of "
                     "hand; the dots are push rates. The right-hand figure is how often pushing paid in Celestial points "
                     "at your spots of that kind."),
        "place_title": "The same push rates by your place at the start of the hand",
        "place_sub": "Celestials and the Throne-trained Mortal push from third as often as from fourth. You fold there.",
        "you": "You", "s42": "Mortal-S42", "cel": "Celestials, Throne games",
        "axis": "Share of spots pushed", "pays": "pays",
        "cells": {"1-2 han, 4+ live": "1-2 han, 4+ live tiles", "1-2 han, 3 or fewer live": "1-2 han, 3 or fewer",
                  "3 han, 4+ live": "3 han, 4+ live tiles", "3 han, 3 or fewer live": "3 han, 3 or fewer",
                  "4+ han, 4+ live": "4+ han, 4+ live tiles", "4+ han, 3 or fewer live": "4+ han, 3 or fewer"},
        "places": ["In 1st", "In 2nd", "In 3rd", "In 4th"],
        "aria_push": "Push rates by hand: you, Mortal-S42, Celestials. ",
        "aria_place": "Push rates by place: you, Mortal-S42, Celestials. ",
        "push_caption": ("Your {you:,} spots since January, all in the Jade room; Mortal-S42 rated on the same spots; "
                         "{cel} spots of Celestials and Throne Saints in {games} random Throne games of 18 to 23 November."),
        "th": ["", "Jade room", "Throne room"],
        "rows": [("Turn a player first reaches tenpai", "tenpai_turn"),
                 ("Discard of the first riichi at the table", "first_riichi"),
                 ("Someone in riichi before a player is tenpai", "riichi_before"),
                 ("Tenpai at the draw (players&#8217; statistics)", "tenpai_at_draw"),
                 ("Riichis that win (players&#8217; statistics)", "riichi_win"),
                 ("A caller tenpai after the first call", "call1"),
                 ("&#8230; after the second call", "call2"),
                 ("&#8230; after the third call", "call3"),
                 ("An open hand&#8217;s win, average paid", "open_paid"),
                 ("Open-hand wins of mangan or more", "open_mangan")],
    },
    "ja": {
        "push_title": "立直に対する聴牌：聴牌を保つ割合",
        "push_sub": "聴牌を保つ牌がどれも立直に危険な局面。行は手の種類、点は押した割合。右端の数字は、その種類のあなたの局面で押しが魂天のポイントで得だった割合。",
        "place_title": "局の開始時の順位別の押す割合",
        "place_sub": "魂天と王座の間で学んだMortalは、3位からも4位と同じくらい押す。あなたはそこで降りている。",
        "you": "あなた", "s42": "Mortal-S42", "cel": "魂天（王座の間の対局）",
        "axis": "押した局面の割合", "pays": "得",
        "cells": {"1-2 han, 4+ live": "1-2翻・生き4枚以上", "1-2 han, 3 or fewer live": "1-2翻・3枚以下",
                  "3 han, 4+ live": "3翻・生き4枚以上", "3 han, 3 or fewer live": "3翻・3枚以下",
                  "4+ han, 4+ live": "4翻以上・生き4枚以上", "4+ han, 3 or fewer live": "4翻以上・3枚以下"},
        "places": ["1位のとき", "2位のとき", "3位のとき", "4位のとき"],
        "aria_push": "手の種類別の押す割合：あなた、Mortal-S42、魂天。",
        "aria_place": "順位別の押す割合：あなた、Mortal-S42、魂天。",
        "push_caption": "あなたの1月以降の{you:,}局面（すべて玉の間）、同じ局面でのMortal-S42の評価、11月18日から23日の王座の間の無作為な{games}半荘での魂天と雀聖の{cel}局面。",
        "th": ["", "玉の間", "王座の間"],
        "rows": [("初めて聴牌する巡目", "tenpai_turn"),
                 ("卓で最初の立直が出る打牌", "first_riichi"),
                 ("聴牌する前に誰かが立直している", "riichi_before"),
                 ("流局時の聴牌（成績データ）", "tenpai_at_draw"),
                 ("立直の和了率（成績データ）", "riichi_win"),
                 ("最初の副露の直後に聴牌", "call1"),
                 ("2回目の副露の直後", "call2"),
                 ("3回目の副露の直後", "call3"),
                 ("副露手の和了の平均打点", "open_paid"),
                 ("副露手の和了のうち満貫以上", "open_mangan")],
    },
}


def f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def dot_plot(rows: list[tuple[str, float, float, float, str | None]], lang: str, title: str, sub: str, aria: str,
             fig_id: str, caption: str | None) -> str:
    """Rows of (label, you, s42, celestials, right-hand note); three dots per row on a 0-100% axis."""
    w = WORDS[lang]
    L, R, T = 150, 410, 24
    step = 30
    B = T + step * len(rows)
    x = lambda v: L + (R - L) * v / 100  # noqa: E731
    o, said = [], []
    for k in range(0, 101, 25):
        o.append(f'                <line class="timing-grid" x1="{f(x(k))}" x2="{f(x(k))}" y1="{T - 8}" y2="{B - 10}" />')
        o.append(f'                <text class="timing-axis" x="{f(x(k))}" y="{B + 6}">{k}%</text>')
    o.append(f'                <text class="timing-axis" x="{(L + R) // 2}" y="{B + 24}">{w["axis"]}</text>')
    for i, (label, you, s42, cel, note) in enumerate(rows):
        y = T + step * i
        o.append(f'                <text class="timing-cat tier-row" x="{L - 10}" y="{y + 4}">{label}</text>')
        lo, hi = min(you, s42, cel), max(you, s42, cel)
        o.append(f'                <line class="throne-move" x1="{f(x(lo))}" x2="{f(x(hi))}" y1="{y}" y2="{y}" />')
        for cls, v, name in (("ms", s42, w["s42"]), ("th", cel, w["cel"]), ("you-dot", you, w["you"])):
            dot = "tier-you" if cls == "you-dot" else f"tier-dot {cls}"
            o.append(f'                <circle class="{dot}" cx="{f(x(v))}" cy="{y}" r="5"><title>{label}: {name} {round(v)}%</title></circle>')
        if note:
            o.append(f'                <text class="timing-note is-start" x="{R + 12}" y="{y + 4}">{note}</text>')
        said.append(f"{label} {round(you)}%, {round(s42)}%, {round(cel)}%")
    head = f'              <svg viewBox="0 0 470 {B + 30}" role="img" aria-label="{aria}{"; ".join(said)}.">'
    parts = [
        f'            <figure class="timing-figure is-single tier-figure" id="{fig_id}"' + (f' aria-labelledby="{fig_id}-caption">' if caption else ">"),
        '              <div class="timing-plate">',
        f'                <p class="timing-title">{title}</p>',
        f'                <p class="timing-sub">{sub}</p>',
        f'                <p class="timing-legend"><span class="timing-key tier-youkey">{w["you"]}</span><span class="timing-key tier-ms">{w["s42"]}</span>'
        f'<span class="timing-key tier-th">{w["cel"]}</span></p>',
        '                <div class="timing-plot">',
        head,
        *o,
        "              </svg>",
        "                </div>",
        "              </div>",
    ]
    if caption:
        parts.append(f'              <figcaption id="{fig_id}-caption">{caption}</figcaption>')
    parts.append("            </figure>")
    return "\n".join(parts)


def push(data: dict, lang: str) -> str:
    w = WORDS[lang]
    rows = [(w["cells"][c["cell"]], c["you"]["pct"], c["s42"], c["celestials"]["pct"], f'{w["pays"]} {round(c["push_right_pct"])}%')
            for c in data["cells"]]
    sp = data["sources"]["spots"]
    cap = w["push_caption"].format(you=sp["you"], cel=sp["throne"], games=data["sources"]["throne_games"])
    return dot_plot(rows, lang, w["push_title"], w["push_sub"], w["aria_push"], "throne-push-figure", cap)


def place(data: dict, lang: str) -> str:
    w = WORDS[lang]
    rows = [(w["places"][i], data["places"][str(i + 1)]["you"]["pct"], data["places"][str(i + 1)]["s42"],
             data["places"][str(i + 1)]["celestials"]["pct"], None) for i in range(4)]
    return dot_plot(rows, lang, w["place_title"], w["place_sub"], w["aria_place"], "throne-place-figure", None)


def room(data: dict, lang: str) -> str:
    w = WORDS[lang]
    sp, fd, ca, ow = data["speed"], data["field"], data["callers"], data["open_wins"]
    pct = lambda v: f"{v:.1f}%"  # noqa: E731
    pts = lambda v: f"{v:,}"  # noqa: E731
    cells = {
        "tenpai_turn": (f"{sp['jade_field']['tenpai_turn']:.2f}", f"{sp['throne']['tenpai_turn']:.2f}"),
        "first_riichi": (f"{sp['jade_field']['first_riichi_discard']:.1f}", f"{sp['throne']['first_riichi_discard']:.1f}"),
        "riichi_before": (pct(sp["jade_field"]["riichi_before_tenpai"]["pct"]), pct(sp["throne"]["riichi_before_tenpai"]["pct"])),
        "tenpai_at_draw": (pct(fd["tenpai_at_draw"]["jade_saint3"]["mean"] * 100), pct(fd["tenpai_at_draw"]["celestial"]["mean"] * 100)),
        "riichi_win": (pct(fd["riichi_win"]["jade_saint3"]["mean"] * 100), pct(fd["riichi_win"]["celestial"]["mean"] * 100)),
        "call1": (pct(ca["jade_field"]["call 1"]["pct"]), pct(ca["throne"]["call 1"]["pct"])),
        "call2": (pct(ca["jade_field"]["call 2"]["pct"]), pct(ca["throne"]["call 2"]["pct"])),
        "call3": (pct(ca["jade_field"]["call 3"]["pct"]), pct(ca["throne"]["call 3"]["pct"])),
        "open_paid": (pts(ow["jade_field"]["open_paid"]), pts(ow["throne"]["open_paid"])),
        "open_mangan": (pct(ow["jade_field"]["open_mangan"]["pct"]), pct(ow["throne"]["open_mangan"]["pct"])),
    }
    body = [f'                  <tr><td>{label}</td><td>{cells[key][0]}</td><td>{cells[key][1]}</td></tr>' for label, key in w["rows"]]
    return "\n".join([
        '            <div class="guide-data-scroll">',
        '              <table class="guide-data throne-room-table">',
        "                <thead>",
        "                  <tr>" + "".join(f"<th>{h}</th>" for h in w["th"]) + "</tr>",
        "                </thead>",
        "                <tbody>",
        *body,
        "                </tbody>",
        "              </table>",
        "            </div>",
    ])


RENDER = {"throne-push": push, "throne-place": place, "throne-room": room}


def render(data: dict, part: str, lang: str = "en") -> str:
    return RENDER[part](data, lang)


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    check = "--check" in sys.argv
    for lang, page in PAGES.items():
        html = page.read_text(encoding="utf-8")
        for part in PARTS:
            start, end = f"<!-- {part} -->", f"<!-- /{part} -->"
            if start not in html or end not in html:
                sys.exit(f"{page.name} has no {part} markers")
            head, rest = html.split(start, 1)
            old, tail = rest.split(end, 1)
            new = "\n" + render(data, part, lang) + "\n            "
            if check and old != new:
                sys.exit(f"{page.name}'s {part} does not match {DATA.name}; run scripts/build_throne_strategy.py")
            html = head + start + new + end + tail
        if not check:
            page.write_text(html, encoding="utf-8")
    print("checked" if check else "written")


if __name__ == "__main__":
    main()
