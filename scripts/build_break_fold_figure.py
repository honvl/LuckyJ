#!/usr/bin/env python3
"""Draw the personal guide's chapter 20 chart from ``analysis/break-folds-2026-09-29.json``.

One chart: from each of LuckyJ's hands (tenpai, one-shanten, two-shanten or worse), the share of break
spots on which it broke its hand to throw a safe tile, over the callers' threat read from chapter 18's
grid. One dot per whole percent of threat, sized by its spots, under each hand's fitted curve and its 95%
band; at the right, the same hands against one riichi. It is static SVG in the book's safe-tile timing
style (app.js adds the crosshair and the tooltip from each hit column's data-tip), with a folded table of
the fitted shares, written into ``site/honver.html`` and, with Japanese labels, ``site/honver-ja.html``
between the ``break-fold-figure`` markers. ``--check`` exits non-zero when a page and the data disagree.

usage: build_break_fold_figure.py [--check]
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "break-folds-2026-09-29.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
START = "<!-- break-fold-figure -->"
END = "<!-- /break-fold-figure -->"
HANDS = ("far", "one", "tenpai")  # drawn in this order, the loudest curve on top of the band stack
Y_MAX = 100
W, H = 470, 280
M = {"l": 40, "r": 92, "t": 14, "b": 50}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]
RIICHI_X = M["l"] + PW + 56  # the riichi column, set apart to the right of the callers' axis
TABLE_STEPS = (10, 20, 30, 40, 50, 60, 70, 80, 90)

TEXT = {
    "en": {
        "title": "How often LuckyJ broke its hand to fold",
        "sub": "Turns where every safe tile would leave LuckyJ&#8217;s hand further from tenpai than it stood before the draw. "
               "Each dot is one whole percent of the callers&#8217; square, sized by its turns; the lines are fitted curves.",
        "hands": {"far": "2-shanten or worse", "one": "1-shanten", "tenpai": "Tenpai"},
        "legend_band": "95% range of each fit",
        "legend_riichi": "the same hands against one riichi",
        "axis": "Callers&#8217; square: the chance one can win off your tile",
        "riichi": "One riichi",
        "tip_head": "Square {x}%",
        "tip_riichi": "One riichi",
        "tip_foot": "{n} turns at this square, fitted shares",
        "tip_riichi_foot": "Share of turns, {n} in all",
        "aria": "{title}. Against callers, fitted at a square of 20%, 50% and 80%: {rows}. Against one riichi: {riichi}.",
        "aria_row": "{hand} {a}, {b} and {c}",
        "aria_join": "; ",
        "riichi_join": ", ",
        "riichi_item": "{hand} {pct}",
        "caption": "LuckyJ&#8217;s draw turns in its 1,079 Tokujou games, nobody in riichi for the callers&#8217; side. A tile is "
                   "safe when it is genbutsu, a full suji or an honor with two showing against every caller. The square is "
                   "chapter 18&#8217;s; with two or more callers, the chance that at least one of them can win. Each curve is "
                   "fitted between the 2nd and 98th percentiles of its turns&#8217; squares.",
        "table_summary": "The fitted shares in a table",
        "table_square": "Square",
        "table_riichi": "One riichi",
        "pct": "{v}%",
    },
    "ja": {
        "title": "LuckyJが手を崩してオリた割合",
        "sub": "どの安全牌を切っても、ツモの前より手がテンパイから遠くなる巡目だけを数えた。点は副露者のマスの値1%ごとで、"
               "巡目の数に合わせた大きさ。線は当てはめ曲線。",
        "hands": {"far": "2シャンテン以上", "one": "1シャンテン", "tenpai": "テンパイ"},
        "legend_band": "各当てはめの95%範囲",
        "legend_riichi": "同じ手でリーチ1人を相手にしたとき",
        "axis": "副露者のマスの値：あなたの牌でアガれる確率",
        "riichi": "リーチ1人",
        "tip_head": "マスの値 {x}%",
        "tip_riichi": "リーチ1人",
        "tip_foot": "このマスの巡目 {n}回、当てはめた割合",
        "tip_riichi_foot": "巡目の割合、全{n}回",
        "aria": "{title}。副露者に対して、マスの値20%、50%、80%での当てはめ：{rows}。リーチ1人に対して：{riichi}。",
        "aria_row": "{hand}は{a}、{b}、{c}",
        "aria_join": "。",
        "riichi_join": "、",
        "riichi_item": "{hand}は{pct}",
        "caption": "LuckyJの特上卓1,079半荘でのツモ番。副露者の側は、誰もリーチしていない場面。安全牌は、すべての副露者に対して"
                   "現物、筋、2枚見えの字牌であるもの。マスの値は第18章の表のもので、副露者が2人以上なら、少なくとも1人がアガれる"
                   "確率。各曲線は、その巡目のマスの値の2パーセンタイルから98パーセンタイルの範囲で当てはめた。",
        "table_summary": "当てはめた割合の表",
        "table_square": "マスの値",
        "table_riichi": "リーチ1人",
        "pct": "{v}%",
    },
}


def r2(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def x_of(threat: float) -> float:
    return M["l"] + PW * threat / 100


def y_of(pct: float) -> float:
    return M["t"] + PH * (1 - min(pct, Y_MAX) / Y_MAX)


def dot_radius(n: int) -> float:
    return round(min(4.5, max(1.3, 0.9 + 0.32 * n ** 0.5)), 2)


def half_up(v: float) -> int:
    return int(v + 0.5)


def fitted_at(curve: dict, x: int) -> float | None:
    got = curve["at"].get(str(x))
    return got[0] if got else None


def riichi_rate(data: dict, hand: str) -> tuple[float, int]:
    cell = data["kinds"]["LuckyJ"]["one riichi"][hand]["break"]
    return cell["pct"], cell["spots"]


def tip(payload: dict) -> str:
    return html.escape(json.dumps(payload, ensure_ascii=False), quote=True)


def chart(data: dict, lang: str) -> str:
    t = TEXT[lang]
    curves = data["curves"]
    svg = []
    for tick in (0, 25, 50, 75, 100):
        y = y_of(tick)
        svg.append(f'<line class="timing-grid" x1="{M["l"]}" x2="{RIICHI_X + 22}" y1="{r2(y)}" y2="{r2(y)}" />')
        svg.append(f'<text class="timing-tick" x="{M["l"] - 8}" y="{r2(y + 4)}">{tick}%</text>')
    for tick in (0, 25, 50, 75, 100):
        svg.append(f'<text class="timing-cat" x="{r2(x_of(tick))}" y="{M["t"] + PH + 18}">{tick}%</text>')
    svg.append(f'<text class="timing-axis" x="{r2(M["l"] + PW / 2)}" y="{H - 8}">{t["axis"]}</text>')
    svg.append(f'<line class="bf-divider" x1="{r2(M["l"] + PW + 24)}" x2="{r2(M["l"] + PW + 24)}" y1="{M["t"]}" y2="{M["t"] + PH}" />')
    svg.append(f'<text class="timing-cat" x="{RIICHI_X}" y="{M["t"] + PH + 18}">{t["riichi"]}</text>')
    for hand in HANDS:
        grid = curves[hand]["grid"]
        upper = [f"{r2(x_of(g[0]))},{r2(y_of(g[3]))}" for g in grid]
        lower = [f"{r2(x_of(g[0]))},{r2(y_of(g[2]))}" for g in reversed(grid)]
        svg.append(f'<polygon class="bf-band bf-{hand}" points="{" ".join(upper + lower)}" />')
    svg.append(f'<line class="timing-cross" x1="0" x2="0" y1="{M["t"]}" y2="{M["t"] + PH}" />')
    for hand in HANDS:
        for x, k, n in curves[hand]["points"]:
            svg.append(f'<circle class="bf-dot bf-{hand}" cx="{r2(x_of(x + 0.5))}" cy="{r2(y_of(100 * k / n))}" r="{dot_radius(n)}" />')
    for hand in HANDS:
        points = " ".join(f"{r2(x_of(g[0]))},{r2(y_of(g[1]))}" for g in curves[hand]["grid"])
        svg.append(f'<polyline class="bf-fit bf-{hand}" points="{points}" />')
    riichi_aria = []
    for hand in HANDS:
        pct, n = riichi_rate(data, hand)
        cx, cy = RIICHI_X, y_of(pct)
        svg.append(f'<path class="bf-riichi bf-{hand}" d="M{r2(cx)} {r2(cy - 6)}L{r2(cx + 6)} {r2(cy)}L{r2(cx)} {r2(cy + 6)}L{r2(cx - 6)} {r2(cy)}Z" />')
        svg.append(f'<text class="bf-end bf-{hand}" x="{r2(cx + 10)}" y="{r2(cy + 4)}">{half_up(pct)}%</text>')
        riichi_aria.append(t["riichi_item"].format(hand=t["hands"][hand], pct=f"{half_up(pct)}%"))
    # hover columns, one per whole percent where any curve is fitted, and one for the riichi column
    lo = min(curves[h]["range"][0] for h in HANDS)
    hi = max(curves[h]["range"][1] for h in HANDS)
    counts = {}
    for hand in HANDS:
        for x, _, n in curves[hand]["points"]:
            counts[x] = counts.get(x, 0) + n
    step = PW / 100
    for x in range(lo, hi + 1):
        rows = []
        for hand in HANDS:
            v = fitted_at(curves[hand], x)
            if v is not None:
                rows.append([f"bf-{hand}", t["pct"].format(v=r2(round(v, 1))), t["hands"][hand]])
        payload = {"head": t["tip_head"].format(x=x), "rows": rows, "foot": t["tip_foot"].format(n=f"{counts.get(x, 0):,}")}
        label = t["tip_head"].format(x=x) + ": " + ", ".join(f"{r[2]} {r[1]}" for r in rows)
        svg.append(f'<rect class="timing-hit" x="{r2(x_of(x) - step / 2)}" y="{M["t"]}" width="{r2(step)}" height="{PH + 24}" '
                   f'tabindex="0" data-x="{r2(x_of(x))}" data-tip="{tip(payload)}" aria-label="{html.escape(label, quote=True)}" />')
    total = sum(riichi_rate(data, h)[1] for h in HANDS)
    payload = {"head": t["tip_riichi"], "rows": [[f"bf-{h}", t["pct"].format(v=r2(riichi_rate(data, h)[0])), t["hands"][h]] for h in HANDS],
               "foot": t["tip_riichi_foot"].format(n=f"{total:,}")}
    svg.append(f'<rect class="timing-hit" x="{r2(RIICHI_X - 20)}" y="{M["t"]}" width="40" height="{PH + 24}" tabindex="0" '
               f'data-x="{RIICHI_X}" data-tip="{tip(payload)}" aria-label="{html.escape(t["tip_riichi"], quote=True)}" />')
    rows_aria = t["aria_join"].join(t["aria_row"].format(hand=t["hands"][h], a=f"{half_up(fitted_at(curves[h], 20) or 0)}%",
                                               b=f"{half_up(fitted_at(curves[h], 50) or 0)}%", c=f"{half_up(fitted_at(curves[h], 80) or 0)}%")
                          for h in HANDS)
    aria = t["aria"].format(title=t["title"], rows=rows_aria, riichi=t["riichi_join"].join(riichi_aria))
    body = "\n                ".join(svg)
    return f'''<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(aria, quote=True)}">
                {body}
              </svg>'''


def table(data: dict, lang: str) -> str:
    t = TEXT[lang]
    curves = data["curves"]
    head = "".join(f'<th scope="col">{t["hands"][h]}</th>' for h in HANDS)
    rows = []
    for x in TABLE_STEPS:
        cells = "".join(f'<td>{t["pct"].format(v=r2(round(v, 1))) if (v := fitted_at(curves[h], x)) is not None else ""}</td>' for h in HANDS)
        rows.append(f'<tr><th scope="row">{x}%</th>{cells}</tr>')
    cells = "".join(f'<td>{t["pct"].format(v=r2(riichi_rate(data, h)[0]))}</td>' for h in HANDS)
    rows.append(f'<tr><th scope="row">{t["table_riichi"]}</th>{cells}</tr>')
    body = "\n                  ".join(rows)
    return f'''<details class="timing-table">
                <summary>{t["table_summary"]}</summary>
                <div class="timing-table-scroll">
                  <table>
                    <thead><tr><th scope="col">{t["table_square"]}</th>{head}</tr></thead>
                    <tbody>
                  {body}
                    </tbody>
                  </table>
                </div>
              </details>'''


def render(data: dict, lang: str) -> str:
    t = TEXT[lang]
    keys = "".join(f'<span class="timing-key bf-{h}">{t["hands"][h]}</span>' for h in HANDS)
    return (
        f"{START}\n"
        '            <figure class="timing-figure is-single break-figure" id="break-figure" aria-labelledby="break-figure-caption">\n'
        '              <div class="timing-plate">\n'
        f'                <p class="timing-title">{t["title"]}</p>\n'
        f'                <p class="timing-sub">{t["sub"]}</p>\n'
        f'                <p class="timing-legend">{keys}<span class="timing-key band">{t["legend_band"]}</span>'
        f'<span class="timing-key bf-riichi-key">{t["legend_riichi"]}</span></p>\n'
        '                <div class="timing-plot">\n'
        f"              {chart(data, lang)}\n"
        "                </div>\n"
        "              </div>\n"
        f'              <figcaption id="break-figure-caption">{t["caption"]}</figcaption>\n'
        f"              {table(data, lang)}\n"
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
                sys.exit(f"{name}'s chapter 20 chart does not match {DATA.relative_to(ROOT)}; run build_break_fold_figure.py")
            print(f"{name}: chapter 20 chart matches")
            continue
        path.write_text(new, encoding="utf-8")
        print(f"wrote the chapter 20 chart into {name}")


if __name__ == "__main__":
    main()
