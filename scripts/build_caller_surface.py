#!/usr/bin/env python3
"""Draw the personal guide's caller grid (chapter 18) from ``analysis/caller-surface-2026-09-29.json``.

The grid is a heat table: one row per number of calls and run of tiles drawn and thrown, one column per
discard the caller has made, each cell the fitted share of those callers who could win off a discard
(tenpai with a yaku). A green line in each block of rows marks LuckyJ's fold line from
``analysis/caller-fold-line-2026-09-29.json`` (``scripts/mine_caller_fold_line.py``): the first caller
discard at which LuckyJ, from two-shanten or worse and choosing between a safe tile and a live one at least
as good for its hand, cut the live tile less than half the time.

Two switches above the grid, radio buttons that need no script, turn it into the share of LuckyJ's real
choices, a safe tile against a live one at least as good for its hand, on which it folded in each
square, from two-shanten or worse or from one-shanten, with that hand's line. It is written into
``site/honver.html``, and with Japanese labels into ``site/honver-ja.html``, between the ``caller-surface``
markers; ``--check`` exits non-zero when a page and the data disagree.

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
HANDS = ("far", "one")
ORDINALS = {5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth",
            13: "thirteenth", 14: "fourteenth", 15: "fifteenth", 16: "sixteenth"}
# paper to deep vermilion for the callers who could win, paper to deep jade for LuckyJ's folds: the site's tokens
LOW = (0xF4, 0xF0, 0xE6)
MID = (0xF5, 0xA5, 0x83)
HIGH = (0x8E, 0x2A, 0x15)
RAMPS = {"win": (LOW, MID, HIGH), "fold": (LOW, (0x8E, 0xDB, 0xB8), (0x0C, 0x2F, 0x22))}


def shade(pct: float, ramp: str = "win") -> str:
    """Background colour for a share: paper at 0, the vermilion felt at 50, deep vermilion at 100; the fold
    views run paper, jade felt, deep felt, so a square never reads as a caller's tenpai."""
    low, mid, high = RAMPS[ramp]
    x = max(0.0, min(1.0, pct / 100))
    a, b, t = (low, mid, x / 0.5) if x <= 0.5 else (mid, high, (x - 0.5) / 0.5)
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


def fold_value(cell: dict, max_half_band: float) -> float | None:
    """A fold square is shown where its fit's 95% band lies within max_half_band points of the fit."""
    if "fit" not in cell or (cell["hi"] - cell["lo"]) / 2 > max_half_band:
        return None
    return cell["fit"]


def fold_lines(fold: dict, hand: str = "far") -> dict[int, int | None]:
    """The discard each block of the grid (1, 2, 3 calls) draws LuckyJ's fold line at, for one of its hands."""
    blocks = fold["shanten"][hand]["blocks"]
    return {1: blocks["1"]["line"], 2: blocks["2+"]["line"], 3: blocks["2+"]["line"]}


def blank_blocks(fold: dict, hand: str) -> list[int]:
    """The blocks of a fold view with no square at all."""
    grid, band = fold["shanten"][hand]["grid"], fold["grid_max_half_band"]
    return [c for c in (1, 2, 3)
            if all(fold_value(cell, band) is None for r in (0, 1, 2, 3) for cell in grid[f"{c}-{r}"]["cells"].values())]


def _fold_caption_en(fold: dict, hand: str) -> str:
    entry, lines, blank = fold["shanten"][hand], fold_lines(fold, hand), blank_blocks(fold, hand)
    costly, band = entry["costly"], fold["grid_max_half_band"]
    if hand == "far":
        text = ("Share of LuckyJ&#8217;s real choices on which it folded, from two-shanten or worse, against a single caller "
                "with nobody in riichi, in its 1,079 Tokujou games: a safe tile (the caller&#8217;s genbutsu, a full suji, or "
                "an honor with two showing) kept its shanten, and so did a live tile with at least as much acceptance, and "
                "it threw the safe tile. Turns where the safe tile was the best tile for the hand anyway, or the only one "
                "that kept the shanten, are left out.")
    else:
        text = ("Share of LuckyJ&#8217;s real choices on which it folded from one-shanten, counted the same way as from "
                "two-shanten or worse. It starts a little higher, because early ties between two equally good tiles go to "
                "the safe one more often from one-shanten, then rises more slowly than the far hand&#8217;s and passes half "
                "later.")
    text += f" A blank square is one LuckyJ met too rarely to pin the share within {band} points either way"
    text += f"; against {('two', 'three')[min(blank) - 2]} or more calls, that is every square." if blank else "."
    text += (f" The green line is where the share passes half, all runs together: the {ORDINALS[lines[1]]} discard "
             f"against one call and the {ORDINALS[lines[2]]} against two or more.")
    cost = "a shanten" if hand == "far" else "the one-shanten"
    text += f" When every safe tile would have cost {cost}, LuckyJ threw one on {costly['folded']}% of {costly['spots']:,} turns."
    if hand == "one":
        tenpai = fold["shanten"]["tenpai"]
        text += (f" At tenpai LuckyJ met a real choice only {tenpai['folded']['spots']} times against a single caller, too "
                 f"few for the grid; it took the safe tile on {round(tenpai['folded']['folded'])}% of them, and broke a "
                 f"tenpai for safety on {tenpai['costly']['folded']}% of the {tenpai['costly']['spots']:,} turns where "
                 "every safe tile would have broken it.")
    return text


def _fold_caption_ja(fold: dict, hand: str) -> str:
    entry, lines, blank = fold["shanten"][hand], fold_lines(fold, hand), blank_blocks(fold, hand)
    costly, band = entry["costly"], fold["grid_max_half_band"]
    if hand == "far":
        text = ("2シャンテン以上のLuckyJが、本当に選べた場面でオリた割合。副露者が1人だけで誰もリーチしていないとき、"
                "シャンテン数を保つ安全牌（副露者の現物、筋、2枚見えの字牌）があり、受け入れが同じか広い生牌もシャンテン数を"
                "保てる場面で、安全牌を切った割合を、LuckyJの特上卓1,079半荘で測った。安全牌がもともと手に一番いい牌だった場面と、"
                "安全牌しかシャンテン数を保てない場面は除いた。")
    else:
        text = ("1シャンテンのLuckyJが、本当に選べた場面でオリた割合。数え方は2シャンテン以上と同じ。序盤は、同じ価値の2枚から"
                "安全牌を選ぶことが1シャンテンのほうが多いので少し高いが、その後は2シャンテン以上よりゆっくり上がり、半分を超えるのも遅い。")
    text += f"空欄は、LuckyJがその場面に出会った回数が少なく、割合を上下{band}ポイント以内に絞れないマス"
    text += f"で、{min(blank)}副露以上ではすべてのマスが空欄になる。" if blank else "。"
    text += (f"緑の線は、ツモ切りの連続をまとめて割合が半分を超える位置で、1副露に対して{lines[1]}打目、"
             f"2副露以上に対して{lines[2]}打目。")
    cost = "シャンテン数が落ちる" if hand == "far" else "1シャンテンが崩れる"
    text += f"安全牌を切ると{cost}場面で、LuckyJが安全牌を切ったのは{costly['spots']:,}回中{costly['folded']}%。"
    if hand == "one":
        tenpai = fold["shanten"]["tenpai"]
        text += (f"テンパイで本当に選べた場面は、副露者が1人のとき{tenpai['folded']['spots']}回しかなく、表にするには少ない。"
                 f"安全牌を選んだのはその{round(tenpai['folded']['folded'])}%で、安全牌を切るとテンパイが崩れる"
                 f"{tenpai['costly']['spots']:,}回では、テンパイを崩したのは{tenpai['costly']['folded']}%だった。")
    return text


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
            "<mark id=\"fix-18-line\" class=\"guide-changed\"><span class=\"cs-fold-key\">The green line</span> is "
            "LuckyJ&#8217;s fold line: from two-shanten or worse, choosing between a safe tile and a live one at least as "
            "good for its hand, it cut the live tile less than half the time from the {one} discard against one call "
            "and from the {more} against two or more</mark> (<a href=\"#fold-line\">chapter 19</a>)."
        ),
        "discard": lambda n: ORDINALS[n],
        "show": "Squares show",
        "views": {"win": "Callers who could win", "fold": "LuckyJ folded"},
        "hand": "LuckyJ&#8217;s hand",
        "hands": {"far": "Two-shanten or worse", "one": "One-shanten"},
        "win_label": "Share of callers who could win off your discard",
        "fold_label": lambda hand: f"Share of turns LuckyJ folded, {hand.lower()}",
        "fold_caption": _fold_caption_en,
    },
    "ja": {
        "corner": "副露数と直近の捨て牌",
        "rows": ("一段目", "二段目", "三段目"),
        "calls": {1: "1副露", 2: "2副露", 3: "3〜4副露"},
        "runs": {0: "最後は手出し", 1: "最後の1枚がツモ切り", 2: "ツモ切りが2回続く", 3: "ツモ切りが3回以上続く"},
        "folds": "ここからLuckyJはオリる",
        "caption": (
            "あなたの打牌でアガれる副露者（役ありのテンパイ）の割合を、上に並べた副露者の打牌数ごとに、LuckyJの対局で"
            "測った。空欄は観測が{minimum}回未満。<mark id=\"fix-18-line\" class=\"guide-changed\"><span "
            "class=\"cs-fold-key\">緑の線</span>はLuckyJのオリライン。2シャンテン以上で、安全牌と、手にとって同じか"
            "より良い生牌のどちらも選べるとき、生牌を切った割合が半分を下回ったのは、1副露に対して{one}から、"
            "2副露以上に対して{more}からである</mark>（<a href=\"#fold-line\">第19章</a>）。"
        ),
        "discard": lambda n: f"{n}打目",
        "show": "マスの表示",
        "views": {"win": "アガれる副露者", "fold": "LuckyJがオリた割合"},
        "hand": "LuckyJの手",
        "hands": {"far": "2シャンテン以上", "one": "1シャンテン"},
        "win_label": "あなたの打牌でアガれる副露者の割合",
        "fold_label": lambda hand: f"LuckyJがオリた割合（{hand}）",
        "fold_caption": _fold_caption_ja,
    },
}


def _table(words: dict, view: str, label: str, cells_for, pick, lines: dict, ramp: str = "win") -> str:
    head_rows = (
        f'<tr><th class="cs-corner" rowspan="2" scope="col">{words["corner"]}</th>'
        + "".join(f'<th class="cs-group" colspan="6" scope="colgroup">{row}</th>' for row in words["rows"])
        + "</tr>"
        "<tr>" + "".join(f'<th scope="col"{ROW_START if d in (7, 13) else ""}>{d}</th>' for d in range(1, MAX_DISCARD + 1)) + "</tr>"
    )
    body = []
    for calls in (1, 2, 3):
        line = lines[calls]
        if line:
            body.append(f'<tr class="cs-calls"><th scope="rowgroup">{words["calls"][calls]}</th><td colspan="{line - 1}"></td>'
                        f'<td class="cs-fold cs-fold-label" colspan="{MAX_DISCARD - line + 1}">{words["folds"]}</td></tr>')
        else:
            body.append(f'<tr class="cs-calls"><th scope="rowgroup">{words["calls"][calls]}</th><td colspan="{MAX_DISCARD}"></td></tr>')
        for run in (0, 1, 2, 3):
            cells = cells_for(calls, run)
            tds = []
            for d in range(1, MAX_DISCARD + 1):
                v = pick(cells[str(d)])
                classes = (["cs-row-start"] if d in (7, 13) else []) + (["cs-fold"] if d == line else []) + (["cs-empty"] if v is None else [])
                attr = f' class="{" ".join(classes)}"' if classes else ""
                if v is None:
                    tds.append(f"<td{attr}></td>")
                    continue
                tds.append(f'<td{attr} style="background:{shade(v, ramp)};color:{text_for(shade(v, ramp))}">{round(v)}</td>')
            body.append(f'<tr><th scope="row">{words["runs"][run]}</th>{"".join(tds)}</tr>')
    return f'<table class="cs-grid" data-view="{view}" aria-label="{label}"><thead>{head_rows}</thead><tbody>{"".join(body)}</tbody></table>'


def render(data: dict, fold: dict, lang: str = "en") -> str:
    words = WORDS[lang]
    win_lines = fold_lines(fold)
    minimum = data["min_readings"]
    tables = [_table(words, "win", words["win_label"], lambda c, r: data["grid"]["can_win"][f"{c}-{r}"]["cells"],
                     lambda cell: value(cell, minimum), win_lines)]
    for hand in HANDS:
        tables.append(_table(words, f"fold-{hand}", words["fold_label"](words["hands"][hand]),
                             lambda c, r, hand=hand: fold["shanten"][hand]["grid"][f"{c}-{r}"]["cells"],
                             lambda cell: fold_value(cell, fold["grid_max_half_band"]), fold_lines(fold, hand), "fold"))
    legend = lambda ramp: '<span class="cs-legend">' + "".join(
        f'<span style="background:{shade(p, ramp)};color:{text_for(shade(p, ramp))}">{p}%</span>' for p in (0, 10, 25, 50, 75, 90)) + "</span> "
    win_caption = words["caption"].format(minimum=minimum, one=words["discard"](win_lines[1]), more=words["discard"](win_lines[2]))
    captions = f'<span data-view="win">{legend("win")}{win_caption}</span>' + "".join(
        f'<span data-view="fold-{hand}">{legend("fold")}{words["fold_caption"](fold, hand)}</span>' for hand in HANDS)
    inputs = (
        '<input class="cs-switch-input" type="radio" name="cs-view" id="cs-view-win" checked />'
        '<input class="cs-switch-input" type="radio" name="cs-view" id="cs-view-fold" />'
        + "".join(f'<input class="cs-switch-input" type="radio" name="cs-hand" id="cs-hand-{hand}"{" checked" if hand == "far" else ""} />'
                  for hand in HANDS)
    )
    switches = (
        f'<div class="cs-switch"><span class="cs-switch-label">{words["show"]}</span>'
        + "".join(f'<label for="cs-view-{view}">{name}</label>' for view, name in words["views"].items()) + "</div>\n"
        f'              <div class="cs-switch cs-hands"><span class="cs-switch-label">{words["hand"]}</span>'
        + "".join(f'<label for="cs-hand-{hand}">{words["hands"][hand]}</label>' for hand in HANDS) + "</div>"
    )
    return (
        f"{START}\n"
        '            <figure class="caller-surface">\n'
        f"              {inputs}\n"
        f"              {switches}\n"
        '              <div class="guide-data-scroll">\n'
        + "".join(f"                {t}\n" for t in tables)
        + "              </div>\n"
        f'              <figcaption>{captions}</figcaption>\n'
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
