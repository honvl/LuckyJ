#!/usr/bin/env python3
"""Draw the personal guide's chapter 25 grid from ``analysis/riichi-placement-2026-10-01.json``.

The grid is chapter 24's chart with a third dimension: for each stage of the game (East, South 1 to 3, the last
hand), one table with a block of rows per hand value, a row per place at the start of the hand, and a column per
turn, each square LuckyJ's fitted share of riichi for a non-dealer. Radio buttons ahead of the tables switch the
stage with no script, as chapter 18's grid does, and the squares are shaded on that grid's jade ramp.

Above the tables the same numbers stand as a surface, turn and place on the floor and the share as the height,
with a plane at one half: honver.js draws it on a canvas from the JSON written here (``surface_data``), turns it
when the reader drags sideways, reads out the point under a tap, and switches value and stage with buttons. It is
written into ``site/honver.html`` and ``site/honver-ja.html`` between the ``riichi-placement-figure`` markers;
``--check`` exits non-zero when a page and the data disagree.

usage: build_riichi_placement_figure.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_caller_surface import shade, text_for  # noqa: E402

DATA = ROOT / "analysis" / "riichi-placement-2026-10-01.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
START = "<!-- riichi-placement-figure -->"
END = "<!-- /riichi-placement-figure -->"
STAGES = ("East", "South", "All-last")
DEFAULT = "South"
SURFACE_DEFAULT = "4"
CLASSES = ("no yaku", "1-2", "3 pinfu", "4", "5+")
RAMP = "fold"  # paper, jade felt, deep felt: LuckyJ's own choices, as on chapter 18's fold views

WORDS = {
    "en": {
        "stage_label": "Stage of the game",
        "stages": {"East": "East", "South": "South 1 to 3", "All-last": "All-last"},
        "corner": "Hand, and your place",
        "classes": {"no yaku": "No yaku", "1-2": "1 or 2 han", "3 pinfu": "3 han pinfu, two-sided",
                    "4": "4 han, two-sided", "5+": "5 han or more, two-sided"},
        "places": {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"},
        "turns": "Your turn",
        "surface": {
            "hand": "Hand", "stage": "Stage", "turn": "Your turn", "place": "Your place", "share": "Riichi",
            "half": "Half the time", "places": ["1st", "2nd", "3rd", "4th"],
            "classes": {"no yaku": "No yaku", "1-2": "1 or 2 han", "3 pinfu": "3 han pinfu", "4": "4 han", "5+": "5 han or more"},
            "stages": {"East": "East", "South": "South 1 to 3", "All-last": "All-last"},
            "readout": "{stage}, {hand}, {place}, turn {turn}: LuckyJ declares {value}%",
            "hint": "Drag sideways to turn the surface; tap it to read a point.",
            "aria": "A surface of LuckyJ&#8217;s share of riichi by your turn and your place, with a plane at one half. "
                    "The grid below gives the same numbers.",
        },
        "caption": "LuckyJ&#8217;s fitted share of riichi on its first closed tenpai, as a non-dealer with nobody in "
                   "riichi, in its 1,079 Tokujou games, by the hand&#8217;s value without riichi, its place at the start of "
                   "the hand and its turn. One model holds a turn curve for each value and one shift for each place and "
                   "stage; the 4-han and 5-han rows rest on {n4} and {n5} hands. A hatched square is a turn outside the "
                   "middle 90% of that value&#8217;s tenpais.",
    },
    "ja": {
        "stage_label": "局面",
        "stages": {"East": "東場", "South": "南1〜3局", "All-last": "オーラス"},
        "corner": "手と着順",
        "classes": {"no yaku": "役なし", "1-2": "1〜2翻", "3 pinfu": "3翻平和、両面待ち",
                    "4": "4翻、両面待ち", "5+": "5翻以上、両面待ち"},
        "places": {1: "1位", 2: "2位", 3: "3位", 4: "4位"},
        "turns": "巡目",
        "surface": {
            "hand": "手", "stage": "局面", "turn": "巡目", "place": "着順", "share": "リーチ",
            "half": "半分", "places": ["1位", "2位", "3位", "4位"],
            "classes": {"no yaku": "役なし", "1-2": "1〜2翻", "3 pinfu": "3翻平和", "4": "4翻", "5+": "5翻以上"},
            "stages": {"East": "東場", "South": "南1〜3局", "All-last": "オーラス"},
            "readout": "{stage}、{hand}、{place}、{turn}巡目：LuckyJのリーチは{value}%",
            "hint": "横にドラッグすると回転し、タップするとその点の値が出る。",
            "aria": "巡目と着順ごとのLuckyJのリーチの割合を表す曲面で、半分の高さに面がある。下の表に同じ数字がある。",
        },
        "caption": "LuckyJの特上卓1,079半荘で、誰もリーチしていない場面の子の最初の門前テンパイについて、リーチなしの手の価値、"
                   "局の開始時の着順、巡目ごとに当てはめたリーチの割合。一つのモデルが、価値ごとの巡目の曲線と、着順と局面ごとの"
                   "ずれを持つ。4翻と5翻以上の行は{n4}回と{n5}回の手による。斜線のマスは、その価値のテンパイの中央90%から外れる巡目。",
    },
}


def turns(data: dict) -> list[int]:
    lo = min(data["ranges"][c][0] for c in CLASSES)
    hi = max(data["ranges"][c][1] for c in CLASSES)
    return list(range(lo, hi + 1))


def table(data: dict, lang: str, stage: str) -> str:
    w = WORDS[lang]
    cols = turns(data)
    head = (f'<tr><th class="cs-corner" scope="col">{w["corner"]}</th>'
            + "".join(f'<th scope="col">{t}</th>' for t in cols) + "</tr>")
    body = []
    for cls in CLASSES:
        body.append(f'<tr class="cs-calls"><th scope="rowgroup" colspan="{len(cols) + 1}">{w["classes"][cls]}</th></tr>')
        for rank in (1, 2, 3, 4):
            cells = data["grid"][f"{cls}|{rank} {stage}"]
            tds = []
            for t in cols:
                v = cells.get(str(t))
                if v is None:
                    tds.append('<td class="cs-empty"></td>')
                    continue
                bg = shade(v, RAMP)
                tds.append(f'<td style="background:{bg};color:{text_for(bg)}">{int(v + 0.5)}</td>')
            body.append(f'<tr><th scope="row">{w["places"][rank]}</th>{"".join(tds)}</tr>')
    return (f'<table class="cs-grid rp-grid" data-stage="{stage}" aria-label="{w["stages"][stage]}">'
            f'<thead>{head}</thead><tbody>{"".join(body)}</tbody></table>')


def surface_data(data: dict, lang: str) -> dict:
    """What honver.js needs to draw the surface: the words, the turns and every fitted square."""
    cols = turns(data)
    return {
        "words": WORDS[lang]["surface"],
        "turns": [cols[0], cols[-1]],
        "default": {"hand": SURFACE_DEFAULT, "stage": DEFAULT},
        "grid": {f"{c}|{s}": [[data["grid"][f"{c}|{r} {s}"].get(str(t)) for t in cols] for r in (1, 2, 3, 4)]
                 for c in CLASSES for s in STAGES},
    }


def surface(data: dict, lang: str) -> str:
    w = WORDS[lang]["surface"]
    payload = json.dumps(surface_data(data, lang), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    hands = "".join(f'<button type="button" data-hand="{c}" aria-pressed="{"true" if c == SURFACE_DEFAULT else "false"}">'
                    f'{w["classes"][c]}</button>' for c in CLASSES)
    stages = "".join(f'<button type="button" data-stage="{s}" aria-pressed="{"true" if s == DEFAULT else "false"}">'
                     f'{w["stages"][s]}</button>' for s in STAGES)
    return (
        '<div class="rp-3d">\n'
        f'                <div class="cs-switch rp-3d-hands"><span class="cs-switch-label">{w["hand"]}</span>{hands}</div>\n'
        f'                <div class="cs-switch rp-3d-stages"><span class="cs-switch-label">{w["stage"]}</span>{stages}</div>\n'
        f'                <canvas class="rp-3d-canvas" role="img" aria-label="{w["aria"]}"></canvas>\n'
        '                <p class="rp-3d-readout" aria-live="polite"></p>\n'
        f'                <p class="rp-3d-hint">{w["hint"]}</p>\n'
        f'                <script type="application/json" class="rp-3d-data">{payload}</script>\n'
        "              </div>"
    )


def render(data: dict, lang: str) -> str:
    w = WORDS[lang]
    inputs = "".join(f'<input class="cs-switch-input" type="radio" name="rp-stage" id="rp-stage-{s.lower()}"'
                     f'{" checked" if s == DEFAULT else ""} />' for s in STAGES)
    switch = (f'<div class="cs-switch"><span class="cs-switch-label">{w["stage_label"]}</span>'
              + "".join(f'<label for="rp-stage-{s.lower()}">{w["stages"][s]}</label>' for s in STAGES) + "</div>")
    legend = '<span class="cs-legend">' + "".join(
        f'<span style="background:{shade(p, RAMP)};color:{text_for(shade(p, RAMP))}">{p}%</span>' for p in (0, 10, 25, 50, 75, 90)) + "</span> "
    caption = w["caption"].format(n4=sum(data["raw"][f"4|{r} {s}"][1] for r in (1, 2, 3, 4) for s in STAGES),
                                  n5=sum(data["raw"][f"5+|{r} {s}"][1] for r in (1, 2, 3, 4) for s in STAGES))
    return (
        f"{START}\n"
        '            <figure class="caller-surface rp-surface" id="placement-grid">\n'
        f"              {surface(data, lang)}\n"
        f"              {inputs}\n"
        f"              {switch}\n"
        '              <div class="guide-data-scroll">\n'
        + "".join(f"                {table(data, lang, s)}\n" for s in STAGES)
        + "              </div>\n"
        f"              <figcaption>{legend}{caption}</figcaption>\n"
        "            </figure>\n"
        f"            {END}"
    )


def main() -> None:
    data = json.loads(DATA.read_text())
    for lang, path in PAGES.items():
        page = path.read_text(encoding="utf-8")
        start, end = page.index(START), page.index(END) + len(END)
        new = page[:start] + render(data, lang) + page[end:]
        name = path.relative_to(ROOT)
        if "--check" in sys.argv:
            if new != page:
                sys.exit(f"{name}'s chapter 25 grid does not match {DATA.relative_to(ROOT)}; run build_riichi_placement_figure.py")
            print(f"{name}: chapter 25 grid matches")
            continue
        path.write_text(new, encoding="utf-8")
        print(f"wrote the chapter 25 grid into {name}")


if __name__ == "__main__":
    main()
