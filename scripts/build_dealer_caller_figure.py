#!/usr/bin/env python3
"""Draw the personal guide's chapter 28 chart from ``analysis/dealer-callers-2026-10-04.json``.

Two small charts, a hand two-shanten or worse and a one-shanten hand, of LuckyJ's real choices against a caller
with one call (a safe tile and a live tile both keep the shanten): how often it cut the live tile at each of the
caller's discards when the caller was the dealer (one jade dot per discard, sized by its turns, under the fitted
curve and its 95% band) and the fitted curve when anyone else called, in gray. It is drawn like the main book's
fold-line chart (``scripts/build_open_callers_figure.py``) and shares the safe-tile timing styles and hover layer.
The figure goes into ``site/honver.html`` and, with Japanese words, ``site/honver-ja.html`` between the
``dealer-figure`` markers. ``--check`` exits non-zero when a page and the data disagree.

usage: build_dealer_caller_figure.py [--check]
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_safe_tile_timing_figures as tf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "dealer-callers-2026-10-04.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
START = "<!-- dealer-figure -->"
END = "<!-- /dealer-figure -->"
HANDS = ("far", "one")
X_TICKS = (1, 3, 6, 9, 12, 15, 18)

TEXT = {
    "en": {
        "title": "Against one call: how often LuckyJ cut the live tile",
        "sub": "Turns where a safe tile and a live tile both kept LuckyJ&#8217;s shanten, by the caller&#8217;s discards so "
               "far. Each dot is one discard against the dealer, sized by LuckyJ&#8217;s turns there; the lines are fitted "
               "curves.",
        "legend_dealer": "The dealer called, per discard and fitted",
        "legend_band": "95% range of the fit",
        "legend_other": "Anyone else called, fitted",
        "legend_wash": "below 50%, the safe tile goes first",
        "hands": {"far": ("Two-shanten or worse", "LuckyJ&#8217;s hand far from ready"),
                  "one": ("One-shanten", "LuckyJ&#8217;s hand one tile from ready")},
        "axis": "The caller&#8217;s discards so far",
        "cross": ("50% between", "discards {a} and {b}"),
        "dealer": "dealer",
        "other": "anyone else",
        "turns": "{n} turns against the dealer",
        "tip_turn": "Discard {turn}",
        "tip_fit": "fitted {pct}",
        "aria": "{title}, {sub}: against the dealer, LuckyJ&#8217;s fitted rate of cutting the live tile is {points}.{cross}",
        "aria_point": "{pct} at discard {turn}",
        "aria_cross": " It crosses 50% between discards {a} and {b}.",
        "caption": "LuckyJ&#8217;s 1,079 Tokujou games, against a single caller with one call while nobody is in riichi. "
                   "A safe tile is genbutsu, a full suji or an honor with two copies showing; a turn counts when a "
                   "safe tile keeps LuckyJ&#8217;s best shanten and so does a live tile with at least as many tiles to "
                   "improve the hand. Each curve is fitted over the discards with at least 25 such turns.",
        "table_summary": "The numbers as a table",
        "table_note": "Each cell: LuckyJ against the dealer, then against anyone else, then its turns against the "
                      "dealer. Discards with no turns are blank.",
        "table_discard": "Discard",
    },
    "ja": {
        "title": "1副露に対して、LuckyJが生牌を切った割合",
        "sub": "安全牌と生牌のどちらを切ってもLuckyJのシャンテン数が変わらない巡目を、副露者のそれまでの捨て牌の数で分けた。点は親に対する1打ごとの値で、大きさはそこでのLuckyJの巡目の数。線は当てはめ曲線。",
        "legend_dealer": "親が鳴いた（1打ごとの値と曲線）",
        "legend_band": "曲線の95%範囲",
        "legend_other": "子が鳴いた（曲線）",
        "legend_wash": "50%未満は安全牌が先に出る",
        "hands": {"far": ("2シャンテン以上", "LuckyJの手がテンパイから遠い"),
                  "one": ("1シャンテン", "LuckyJの手があと1枚でテンパイ")},
        "axis": "副露者のそれまでの捨て牌の数",
        "cross": ("{a}打目と{b}打目の間で50%",),
        "dealer": "親",
        "other": "子",
        "turns": "親に対して{n}巡目",
        "tip_turn": "{turn}打目",
        "tip_fit": "曲線 {pct}",
        "aria": "{title}、{sub}：親に対してLuckyJが生牌を切った割合の曲線は、{points}。{cross}",
        "aria_point": "{turn}打目で{pct}",
        "aria_cross": "{a}打目と{b}打目の間で50%を横切る。",
        "caption": "LuckyJの特上卓1,079半荘。誰もリーチしていない場面で、1副露の副露者1人に対する巡目。安全牌は現物、筋、2枚見えの字牌。安全牌を切ってもLuckyJの最良のシャンテン数が保て、生牌も同じシャンテン数で有効牌が同じ以上に残るときだけを数えた。各曲線は、そうした巡目が25以上ある打牌の範囲で当てはめた。",
        "table_summary": "数字を表で見る",
        "table_note": "各マスは、親に対するLuckyJ、子に対するLuckyJ、親に対する巡目の数の順。巡目のない打牌は空欄。",
        "table_discard": "打牌",
    },
}


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8"))


def raw(curve: dict, turn: int) -> float | None:
    n = curve["n"][turn - 1]
    return 100 * curve["k"][turn - 1] / n if n else None


def fitted_at(curve: dict, turn: int) -> float | None:
    got = curve["at"].get(str(turn))
    return got[0] if got else None


def panel(lang: str, hand: str, curves: dict) -> str:
    t = TEXT[lang]
    title, sub = t["hands"][hand]
    dealer, other = curves["dealer"], curves["other"]
    lo, hi = dealer["range"]
    fitted = {round(g[0], 1): g for g in dealer["grid"]}
    svg = tf.frame(t["axis"], [(tf.x_turn(n), str(n)) for n in X_TICKS])
    upper = [f"{tf.r2(tf.x_turn(g[0]))},{tf.r2(tf.y_pct(g[3]))}" for g in dealer["grid"]]
    lower = [f"{tf.r2(tf.x_turn(g[0]))},{tf.r2(tf.y_pct(g[2]))}" for g in reversed(dealer["grid"])]
    svg.append(f'<polygon class="timing-band" points="{" ".join(upper + lower)}" />')
    svg.append(f'<line class="timing-cross" x1="0" x2="0" y1="{tf.M["t"]}" y2="{tf.M["t"] + tf.PH}" />')
    for key, curve in (("humans", other), ("lj", dealer)):
        points = " ".join(f"{tf.r2(tf.x_turn(g[0]))},{tf.r2(tf.y_pct(g[1]))}" for g in curve["grid"])
        svg.append(f'<polyline class="timing-fit {key}" points="{points}" />')
    for turn in range(lo, hi + 1):
        pct = raw(dealer, turn)
        svg.append(
            f'<circle class="timing-dot lj" cx="{tf.r2(tf.x_turn(turn))}" cy="{tf.r2(tf.y_pct(pct))}" '
            f'r="{tf.dot_radius(dealer["n"][turn - 1])}" data-turn="{turn}" data-pct="{pct:.1f}" data-n="{dealer["n"][turn - 1]}" />'
        )
    cross_aria = ""
    for c in dealer["crossings_50"]:
        a, b = tf.crossing_pair(c["turn"])
        x = tf.x_turn(c["turn"])
        svg.append(f'<circle class="timing-switch" cx="{tf.r2(x)}" cy="{tf.r2(tf.y_pct(50))}" r="4" data-turn="{c["turn"]:.2f}" />')
        # the curve comes down from the upper left, so the note goes under the half line, left of the crossing,
        # where the washed half is still empty
        note = t["cross"]
        tspans = "".join(f'<tspan x="{tf.r2(x - 7)}" dy="{0 if i == 0 else 13}">{line.format(a=a, b=b)}</tspan>'
                         for i, line in enumerate(note))
        svg.append(f'<text class="timing-note is-end" x="{tf.r2(x - 7)}" y="{tf.r2(tf.y_pct(50) + 18)}">{tspans}</text>')
        cross_aria += t["aria_cross"].format(a=a, b=b)

    # the right end's value sits just right of the last dot, in the empty part of the panel
    value = fitted[float(hi)][1]
    radius = tf.dot_radius(dealer["n"][hi - 1])
    svg.append(f'<text class="timing-label is-start" x="{tf.r2(tf.x_turn(hi) + radius + 5)}" '
               f'y="{tf.r2(tf.y_pct(value) + 4)}">{tf.half_up(value)}%</text>')
    step = tf.PW / (tf.TURNS[-1] - tf.TURNS[0])
    first, last = min(lo, other["range"][0]), max(hi, other["range"][1])
    for turn in range(first, last + 1):
        rows = []
        if lo <= turn <= hi:
            rows.append(["lj", tf.fmt_pct(raw(dealer, turn)), t["dealer"]])
        o = fitted_at(other, turn)
        if o is not None:
            rows.append(["humans", f"{tf.half_up(o)}%", t["other"]])
        if lo <= turn <= hi:
            foot = f'{t["turns"].format(n=f"{dealer["n"][turn - 1]:,}")} · {t["tip_fit"].format(pct=f"{tf.half_up(fitted[float(turn)][1])}%")}'
        else:
            foot = ""
        payload = {"head": t["tip_turn"].format(turn=turn), "rows": rows, "foot": foot}
        label = f'{t["tip_turn"].format(turn=turn)}: ' + ", ".join(f"{r[2]} {r[1]}" for r in rows) + (f", {foot}" if foot else "")
        svg.append(
            f'<rect class="timing-hit" x="{tf.r2(tf.x_turn(turn) - step / 2)}" y="{tf.M["t"]}" width="{tf.r2(step)}" '
            f'height="{tf.PH + 24}" tabindex="0" data-x="{tf.r2(tf.x_turn(turn))}" data-tip="{tf.tip_attr(payload)}" '
            f'aria-label="{html.escape(label, quote=True)}" />'
        )
    aria_points = ", ".join(t["aria_point"].format(pct=f"{tf.half_up(fitted[float(n)][1])}%", turn=n) for n in range(lo, hi + 1))
    aria = t["aria"].format(title=title, sub=sub, points=aria_points, cross=cross_aria)
    body = "\n                    ".join(svg)
    return f'''                <div class="timing-panel" data-panel="dealer-{hand}">
                  <p class="timing-panel-title"><b>{title}</b><span>{sub}</span></p>
                  <div class="timing-plot">
                    <svg viewBox="0 0 {tf.W} {tf.H}" role="img" aria-label="{html.escape(aria, quote=True)}">
                    {body}
                    </svg>
                  </div>
                </div>'''


def table(lang: str, curves: dict) -> str:
    t = TEXT[lang]
    head = "".join(f'<th scope="col">{t["hands"][h][0]}</th>' for h in HANDS)
    body = []
    for turn in tf.TURNS:
        cells = []
        for hand in HANDS:
            dealer, other = curves[hand]["dealer"], curves[hand]["other"]
            if not dealer["n"][turn - 1]:
                cells.append("<td></td>")
                continue
            o = raw(other, turn)
            cells.append(f'<td><b>{tf.fmt_pct(raw(dealer, turn))}</b><span>{tf.fmt_pct(o) if o is not None else ""}</span>'
                         f'<small>{dealer["n"][turn - 1]:,}</small></td>')
        if any(c != "<td></td>" for c in cells):
            body.append(f'<tr><th scope="row">{turn}</th>{"".join(cells)}</tr>')
    rows = "\n                      ".join(body)
    return f'''              <details class="timing-table">
                <summary>{t["table_summary"]}</summary>
                <p>{t["table_note"]}</p>
                <div class="timing-table-scroll">
                  <table>
                    <thead><tr><th scope="col">{t["table_discard"]}</th>{head}</tr></thead>
                    <tbody>
                      {rows}
                    </tbody>
                  </table>
                </div>
              </details>'''


def render(data: dict, lang: str) -> str:
    t = TEXT[lang]
    curves = data["curves"]
    drawn = "\n".join(panel(lang, hand, curves[hand]) for hand in HANDS)
    return (
        f"{START}\n"
        '            <figure class="timing-figure dealer-figure" id="dealer-figure" aria-labelledby="dealer-figure-caption">\n'
        '              <div class="timing-plate">\n'
        f'                <p class="timing-title">{t["title"]}</p>\n'
        f'                <p class="timing-sub">{t["sub"]}</p>\n'
        f'                <p class="timing-legend"><span class="timing-key lj">{t["legend_dealer"]}</span>'
        f'<span class="timing-key band">{t["legend_band"]}</span><span class="timing-key humans">{t["legend_other"]}</span>'
        f'<span class="timing-key wash">{t["legend_wash"]}</span></p>\n'
        '                <div class="timing-panels">\n'
        f"{drawn}\n"
        "                </div>\n"
        "              </div>\n"
        f'              <figcaption id="dealer-figure-caption">{t["caption"]}</figcaption>\n'
        f"{table(lang, curves)}\n"
        "            </figure>\n"
        f"            {END}"
    )


def main() -> None:
    data = load()
    for lang, path in PAGES.items():
        page = path.read_text(encoding="utf-8")
        start, end = page.index(START), page.index(END) + len(END)
        new = page[:start] + render(data, lang) + page[end:]
        name = path.relative_to(ROOT)
        if "--check" in sys.argv:
            if new != page:
                sys.exit(f"{name}'s chapter 28 chart does not match {DATA.relative_to(ROOT)}; run build_dealer_caller_figure.py")
            print(f"{name}: chapter 28 chart matches")
            continue
        path.write_text(new, encoding="utf-8")
        print(f"wrote the chapter 28 chart into {name}")


if __name__ == "__main__":
    main()
