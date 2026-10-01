#!/usr/bin/env python3
"""Draw the personal guide's chapter 24 chart from ``analysis/dama-value-2026-10-01.json``.

One chart: how often LuckyJ declared a two-sided first tenpai whose cheapest ron pays 3,900 (3 han pinfu),
7,700 (4 han pinfu), or a mangan or more, by its own turn, out to the 18th, the last a player draws. One dot per turn, sized by its hands, under each value's fitted curve and its 95%
band. It is static SVG in the book's safe-tile timing style (app.js adds the crosshair and the tooltip from
each hit column's data-tip), with a folded table of the fitted shares, written into ``site/honver.html``
and, with Japanese labels, ``site/honver-ja.html`` between the ``dama-value-figure`` markers. ``--check``
exits non-zero when a page and the data disagree.

usage: build_dama_value_figure.py [--check]
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "dama-value-2026-10-01.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
START = "<!-- dama-value-figure -->"
END = "<!-- /dama-value-figure -->"
SERIES = ("3", "4", "5")  # drawn in this order, the made mangan on top
X_MIN, X_MAX = 3, 18
W, H = 470, 280
M = {"l": 40, "r": 16, "t": 14, "b": 50}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]
ARIA_TURNS = (6, 9, 12)

TEXT = {
    "en": {
        "title": "How often LuckyJ declares a big two-sided tenpai",
        "sub": "Its first closed tenpais with a two-sided wait and a yaku on every winning tile, with nobody in riichi, "
               "by what the cheapest ron pays without riichi and by its own turn. Each dot is one turn, sized by its "
               "hands; the lines are fitted curves.",
        "series": {"3": "3,900: 3 han pinfu", "4": "7,700: 4 han pinfu", "5": "A mangan or more"},
        "legend_band": "95% range of each fit",
        "axis": "LuckyJ&#8217;s turn when it reached tenpai",
        "tip_head": "Turn {x}",
        "tip_foot": "{n} hands at this turn, fitted shares",
        "aria": "{title}. Fitted share of riichi on turns 6, 9 and 12: {rows}.",
        "aria_row": "{name} {a}, {b} and {c}",
        "aria_join": "; ",
        "caption": "LuckyJ&#8217;s 1,079 Tokujou games: {n3} such tenpais whose ron pays 3,900, {n4} paying 7,700 and {n5} "
                   "paying a mangan or more, that is 5 han, or 4 han at 40 fu or more. Each hand counts at its cheapest "
                   "winning tile, without riichi, dora and red fives included, at non-dealer prices. Each curve is fitted "
                   "between the 5th and 95th percentiles of its turns; with fewer than 100 hands, as for 7,700 and for a "
                   "mangan, the fit is a straight line on the logit scale.",
        "table_summary": "The fitted shares in a table",
        "table_turn": "Turn",
        "pct": "{v}%",
    },
    "ja": {
        "title": "LuckyJが大きな両面テンパイでリーチする割合",
        "sub": "誰もリーチしていない場面で、両面待ちかつ、どの和了牌にも役がある最初の門前テンパイを、リーチなしで最も安いロンの点数と"
               "LuckyJ自身の巡目で分けた。点は巡目ごとで、手の数に合わせた大きさ。線は当てはめ曲線。",
        "series": {"3": "3,900点：3翻平和", "4": "7,700点：4翻平和", "5": "満貫以上"},
        "legend_band": "各当てはめの95%範囲",
        "axis": "テンパイしたときのLuckyJの巡目",
        "tip_head": "{x}巡目",
        "tip_foot": "この巡目の手 {n}回、当てはめた割合",
        "aria": "{title}。6巡目、9巡目、12巡目での当てはめ：{rows}。",
        "aria_row": "{name}は{a}、{b}、{c}",
        "aria_join": "。",
        "caption": "LuckyJの特上卓1,079半荘。ロンで3,900点のテンパイが{n3}回、7,700点が{n4}回、満貫以上（5翻か、40符以上の4翻）が"
                   "{n5}回。どの手も、リーチなしで最も安い和了牌で数え、ドラと赤5を含み、子の点数で見た。各曲線は、その巡目の"
                   "5パーセンタイルから95パーセンタイルの範囲で当てはめた。手が100回に満たない7,700点と満貫以上は、ロジット上の直線で当てはめた。",
        "table_summary": "当てはめた割合の表",
        "table_turn": "巡目",
        "pct": "{v}%",
    },
}


def r2(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def x_of(turn: float) -> float:
    return M["l"] + PW * (turn - X_MIN) / (X_MAX - X_MIN)


def y_of(pct: float) -> float:
    return M["t"] + PH * (1 - min(max(pct, 0), 100) / 100)


def dot_radius(n: int) -> float:
    return round(min(5.5, max(1.6, 1.0 + 0.9 * n ** 0.5)), 2)


def half_up(v: float) -> int:
    return int(v + 0.5)


def fitted_at(curve: dict, turn: int) -> float | None:
    got = curve["at"].get(str(turn))
    return got[0] if got else None


def tip(payload: dict) -> str:
    return html.escape(json.dumps(payload, ensure_ascii=False), quote=True)


def chart(data: dict, lang: str) -> str:
    t = TEXT[lang]
    curves = data["curves"]
    svg = []
    for tick in (0, 25, 50, 75, 100):
        y = y_of(tick)
        cls = "timing-mid" if tick == 50 else "timing-grid"
        svg.append(f'<line class="{cls}" x1="{M["l"]}" x2="{M["l"] + PW}" y1="{r2(y)}" y2="{r2(y)}" />')
        svg.append(f'<text class="timing-tick" x="{M["l"] - 8}" y="{r2(y + 4)}">{tick}%</text>')
    for turn in range(X_MIN, X_MAX + 1):
        svg.append(f'<text class="timing-cat" x="{r2(x_of(turn))}" y="{M["t"] + PH + 18}">{turn}</text>')
    svg.append(f'<text class="timing-axis" x="{r2(M["l"] + PW / 2)}" y="{H - 8}">{t["axis"]}</text>')
    for key in SERIES:
        grid = curves[key]["grid"]
        upper = [f"{r2(x_of(g[0]))},{r2(y_of(g[3]))}" for g in grid]
        lower = [f"{r2(x_of(g[0]))},{r2(y_of(g[2]))}" for g in reversed(grid)]
        svg.append(f'<polygon class="dv-band dv-{key}" points="{" ".join(upper + lower)}" />')
    svg.append(f'<line class="timing-cross" x1="0" x2="0" y1="{M["t"]}" y2="{M["t"] + PH}" />')
    for key in SERIES:
        for turn, k, n in curves[key]["points"]:
            if X_MIN <= turn <= X_MAX:
                svg.append(f'<circle class="dv-dot dv-{key}" cx="{r2(x_of(turn))}" cy="{r2(y_of(100 * k / n))}" r="{dot_radius(n)}" />')
    for key in SERIES:
        points = " ".join(f"{r2(x_of(g[0]))},{r2(y_of(g[1]))}" for g in curves[key]["grid"])
        svg.append(f'<polyline class="dv-fit dv-{key}" points="{points}" />')
    counts = {}
    for key in SERIES:
        for turn, _, n in curves[key]["points"]:
            counts[turn] = counts.get(turn, 0) + n
    step = PW / (X_MAX - X_MIN)
    for turn in range(X_MIN, X_MAX + 1):
        rows = []
        for key in SERIES:
            v = fitted_at(curves[key], turn)
            if v is not None:
                rows.append([f"dv-{key}", t["pct"].format(v=r2(round(v, 1))), t["series"][key]])
        if not rows:
            continue
        payload = {"head": t["tip_head"].format(x=turn), "rows": rows, "foot": t["tip_foot"].format(n=f"{counts.get(turn, 0):,}")}
        label = t["tip_head"].format(x=turn) + ": " + ", ".join(f"{r[2]} {r[1]}" for r in rows)
        svg.append(f'<rect class="timing-hit" x="{r2(x_of(turn) - step / 2)}" y="{M["t"]}" width="{r2(step)}" height="{PH + 24}" '
                   f'tabindex="0" data-x="{r2(x_of(turn))}" data-tip="{tip(payload)}" aria-label="{html.escape(label, quote=True)}" />')
    rows_aria = t["aria_join"].join(
        t["aria_row"].format(name=t["series"][key], **{k: f"{half_up(fitted_at(curves[key], turn) or 0)}%" for k, turn in zip("abc", ARIA_TURNS)})
        for key in SERIES)
    aria = t["aria"].format(title=t["title"], rows=rows_aria)
    body = "\n                ".join(svg)
    return f'''<svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(aria, quote=True)}">
                {body}
              </svg>'''


def table(data: dict, lang: str) -> str:
    t = TEXT[lang]
    curves = data["curves"]
    head = "".join(f'<th scope="col">{t["series"][key]}</th>' for key in SERIES)
    lo = min(curves[key]["range"][0] for key in SERIES)
    hi = max(curves[key]["range"][1] for key in SERIES)
    rows = []
    for turn in range(lo, hi + 1):
        cells = "".join(f'<td>{t["pct"].format(v=r2(round(v, 1))) if (v := fitted_at(curves[key], turn)) is not None else ""}</td>'
                        for key in SERIES)
        rows.append(f'<tr><th scope="row">{turn}</th>{cells}</tr>')
    body = "\n                  ".join(rows)
    return f'''<details class="timing-table">
                <summary>{t["table_summary"]}</summary>
                <div class="timing-table-scroll">
                  <table>
                    <thead><tr><th scope="col">{t["table_turn"]}</th>{head}</tr></thead>
                    <tbody>
                  {body}
                    </tbody>
                  </table>
                </div>
              </details>'''


def render(data: dict, lang: str) -> str:
    t = TEXT[lang]
    keys = "".join(f'<span class="timing-key dv-{key}">{t["series"][key]}</span>' for key in SERIES)
    caption = t["caption"].format(**{f"n{key}": data["curves"][key]["hands"] for key in SERIES})
    return (
        f"{START}\n"
        '            <figure class="timing-figure is-single dama-figure" id="dama-figure" aria-labelledby="dama-figure-caption">\n'
        '              <div class="timing-plate">\n'
        f'                <p class="timing-title">{t["title"]}</p>\n'
        f'                <p class="timing-sub">{t["sub"]}</p>\n'
        f'                <p class="timing-legend">{keys}<span class="timing-key band">{t["legend_band"]}</span></p>\n'
        '                <div class="timing-plot">\n'
        f"              {chart(data, lang)}\n"
        "                </div>\n"
        "              </div>\n"
        f'              <figcaption id="dama-figure-caption">{caption}</figcaption>\n'
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
                sys.exit(f"{name}'s chapter 24 chart does not match {DATA.relative_to(ROOT)}; run build_dama_value_figure.py")
            print(f"{name}: chapter 24 chart matches")
            continue
        path.write_text(new, encoding="utf-8")
        print(f"wrote the chapter 24 chart into {name}")


if __name__ == "__main__":
    main()
