#!/usr/bin/env python3
"""Draw the personal guide's caller grid (chapter 18) from ``analysis/caller-surface-2026-09-29.json``.

The grid is a heat table: one row per number of calls and run of tiles drawn and thrown, one column per
discard the caller has made, each cell the fitted share of those callers who could win off a discard
(tenpai with a yaku). A green line in each block of rows marks LuckyJ's fold line from
``analysis/caller-fold-line-2026-09-29.json`` (``scripts/mine_caller_fold_line.py``): the first caller
discard at which LuckyJ, from two-shanten or worse, cut a live tile less than half the time. It is
written into ``site/honver.html``, and with Japanese labels into ``site/honver-ja.html``, between the
``caller-surface`` markers; ``--check`` exits non-zero when a page and the data disagree.

usage: build_caller_surface.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "caller-surface-2026-09-29.json"
FOLD = ROOT / "analysis" / "caller-fold-line-2026-09-29.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
START = "<!-- caller-surface -->"
END = "<!-- /caller-surface -->"
MAX_DISCARD = 18
ROW_START = ' class="cs-row-start"'
ORDINALS = {5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth"}
WORDS = {
    "en": {
        "corner": "Calls, and their latest discards",
        "rows": ("First row", "Second row", "Third row"),
        "calls": {1: "One call", 2: "Two calls", 3: "Three or four calls"},
        "runs": {0: "last tile from hand", 1: "last one from the wall", 2: "two in a row from the wall",
                 3: "three or more from the wall"},
        "folds": "LuckyJ folds from here",
        "caption": (
            "Share of callers who could win off your discard (tenpai with a yaku), after their discard number at "
            "the top, in LuckyJ&#8217;s games. A blank square has fewer than {minimum} readings. "
            "<span class=\"cs-fold-key\">The green line</span> is LuckyJ&#8217;s fold line: from two-shanten or "
            "worse, holding a safe tile that keeps its shanten, it cut a live tile less than half the time from "
            "the {one} discard against one call and from the {more} against two or more "
            "(<a href=\"#fold-line\">chapter 19</a>)."
        ),
        "discard": lambda n: ORDINALS[n],
    },
    "ja": {
        "corner": "副露数と直近の捨て牌",
        "rows": ("一段目", "二段目", "三段目"),
        "calls": {1: "1副露", 2: "2副露", 3: "3〜4副露"},
        "runs": {0: "最後は手出し", 1: "最後の1枚がツモ切り", 2: "ツモ切りが2回続く", 3: "ツモ切りが3回以上続く"},
        "folds": "ここからLuckyJはオリる",
        "caption": (
            "あなたの打牌でアガれる副露者（役ありのテンパイ）の割合を、上に並べた副露者の打牌数ごとに、LuckyJの対局で"
            "測った。空欄は観測が{minimum}回未満。<span class=\"cs-fold-key\">緑の線</span>はLuckyJのオリライン。"
            "2シャンテン以上でシャンテン数を落とさない安全牌を持つとき、生牌を切った割合が半分を下回ったのは、"
            "1副露に対して{one}から、2副露以上に対して{more}からである（<a href=\"#fold-line\">第19章</a>）。"
        ),
        "discard": lambda n: f"{n}打目",
    },
}
# paper to deep vermilion, the site's tokens
LOW = (0xF4, 0xF0, 0xE6)
MID = (0xF5, 0xA5, 0x83)
HIGH = (0x8E, 0x2A, 0x15)


def shade(pct: float) -> str:
    """Background colour for a share: paper at 0, the vermilion felt at 50, deep vermilion at 100."""
    x = max(0.0, min(1.0, pct / 100))
    a, b, t = (LOW, MID, x / 0.5) if x <= 0.5 else (MID, HIGH, (x - 0.5) / 0.5)
    rgb = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#%02x%02x%02x" % rgb


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def text_for(background: str) -> str:
    """White or the page ink, whichever reads better on this square."""
    bg = _luminance(background)
    white = 1.05 / (bg + 0.05)
    ink = (bg + 0.05) / (_luminance("#1e1a14") + 0.05)
    return "#fff" if white > ink else "var(--ink)"


def value(cell: dict, minimum: int) -> float | None:
    if "fit" in cell:
        return cell["fit"]
    if cell["n"] >= minimum and cell["raw"] is not None:
        return cell["raw"]
    return None


def fold_lines(fold: dict) -> dict[int, int]:
    """The discard each block of the grid (1, 2, 3 calls) draws LuckyJ's fold line at."""
    return {1: fold["blocks"]["1"]["line"], 2: fold["blocks"]["2+"]["line"], 3: fold["blocks"]["2+"]["line"]}


def render(data: dict, fold: dict, lang: str = "en") -> str:
    words = WORDS[lang]
    grid = data["grid"]["can_win"]
    minimum = data["min_readings"]
    lines = fold_lines(fold)
    head_rows = (
        f'<tr><th class="cs-corner" rowspan="2" scope="col">{words["corner"]}</th>'
        + "".join(f'<th class="cs-group" colspan="6" scope="colgroup">{row}</th>' for row in words["rows"])
        + "</tr>"
        "<tr>" + "".join(f'<th scope="col"{ROW_START if d in (7, 13) else ""}>{d}</th>' for d in range(1, MAX_DISCARD + 1)) + "</tr>"
    )
    body = []
    for calls in (1, 2, 3):
        line = lines[calls]
        body.append(f'<tr class="cs-calls"><th scope="rowgroup">{words["calls"][calls]}</th><td colspan="{line - 1}"></td>'
                    f'<td class="cs-fold cs-fold-label" colspan="{MAX_DISCARD - line + 1}">{words["folds"]}</td></tr>')
        for run in (0, 1, 2, 3):
            cells = grid[f"{calls}-{run}"]["cells"]
            tds = []
            for d in range(1, MAX_DISCARD + 1):
                v = value(cells[str(d)], minimum)
                classes = (["cs-row-start"] if d in (7, 13) else []) + (["cs-fold"] if d == line else []) + (["cs-empty"] if v is None else [])
                attr = f' class="{" ".join(classes)}"' if classes else ""
                if v is None:
                    tds.append(f"<td{attr}></td>")
                    continue
                tds.append(f'<td{attr} style="background:{shade(v)};color:{text_for(shade(v))}">{round(v)}</td>')
            body.append(f'<tr><th scope="row">{words["runs"][run]}</th>{"".join(tds)}</tr>')
    legend = "".join(f'<span style="background:{shade(p)};color:{text_for(shade(p))}">{p}%</span>' for p in (0, 10, 25, 50, 75, 90))
    return (
        f"{START}\n"
        '            <figure class="caller-surface">\n'
        '              <div class="guide-data-scroll">\n'
        f'                <table class="cs-grid"><thead>{head_rows}</thead><tbody>{"".join(body)}</tbody></table>\n'
        "              </div>\n"
        f'              <figcaption><span class="cs-legend">{legend}</span> '
        + words["caption"].format(minimum=minimum, one=words["discard"](lines[1]), more=words["discard"](lines[2]))
        + "</figcaption>\n"
        "            </figure>\n"
        f"            {END}"
    )


def main() -> None:
    data = json.loads(DATA.read_text())
    fold = json.loads(FOLD.read_text())
    for lang, path in PAGES.items():
        page = path.read_text(encoding="utf-8")
        start, end = page.index(START), page.index(END) + len(END)
        new = page[:start] + render(data, fold, lang) + page[end:]
        name = path.relative_to(ROOT)
        if "--check" in sys.argv:
            if new != page:
                sys.exit(f"{name}'s caller grid does not match analysis/caller-surface-2026-09-29.json and "
                         "caller-fold-line-2026-09-29.json; run build_caller_surface.py")
            print(f"{name}: caller grid matches")
            continue
        path.write_text(new, encoding="utf-8")
        print(f"wrote the caller grid into {name}")


if __name__ == "__main__":
    main()
