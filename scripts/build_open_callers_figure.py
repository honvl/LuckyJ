#!/usr/bin/env python3
"""Draw the fold-line chart of the "Open callers" section from its analysis artifact.

The section in site/points.html and site/ja.html carries the chart between marker comments that this
script fills:

  <!-- fold-figure:line -->   four small charts of LuckyJ's real choices from two-shanten or worse
                              against a single caller (a safe tile and a live tile both keep the
                              shanten): how often it cut the live tile at each of the caller's
                              discards (one dot per discard, sized by its turns) with a fitted curve
                              and its 95% band, and the humans' fitted curve in gray. Columns: the two
                              tiles equally good for the hand, and the safe tile costing acceptance;
                              rows: one call, and two or more

It is drawn like the safe-tile timing charts (scripts/build_safe_tile_timing_figures.py) and shares their
styles and hover layer. The caption is prose, kept in the page.

usage: build_open_callers_figure.py [--check]
  --check  exit 1 if the pages do not match what the script would write
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_safe_tile_timing_figures as tf  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "analysis/open-callers-2026-09-27.json"
PAGES = {"en": ROOT / "site/points.html", "ja": ROOT / "site/ja.html"}
PANELS = (("1", "tie"), ("1", "costly"), ("2+", "tie"), ("2+", "costly"))
X_TICKS = (1, 3, 6, 9, 12, 15, 18)

TEXT = {
    "en": {
        "title": "Where LuckyJ stops cutting live tiles",
        "sub": "Two-shanten or worse against one caller, holding a safe tile and a live tile that both keep the shanten: how often the discard was the live tile, by the caller&#8217;s discards so far. Each dot is one discard, sized by LuckyJ&#8217;s turns there; the lines are fitted curves.",
        "legend_lj": "LuckyJ, per discard and fitted",
        "legend_band": "95% range of the fit",
        "legend_humans": "the humans at Tokujou and Houou, fitted",
        "legend_wash": "below 50%, the safe tile goes first",
        "blocks": {"1": "One call", "2+": "Two or three calls"},
        "counts": {"tie": "The two tiles equally good for the hand", "costly": "The safe tile costs acceptance"},
        "axis": "The caller&#8217;s discards so far",
        "cross": ("50% between", "discards {a} and {b}"),
        "table_summary": "The numbers as a table",
        "table_note": "Each cell: LuckyJ, then the humans, then LuckyJ&#8217;s number of turns. Discards where LuckyJ had no turns are blank.",
        "table_discard": "Discard",
        "turns": "{n} turns",
        "tip_turn": "Discard {turn}",
        "tip_fit": "fitted {pct}",
        "humans": "humans",
        "aria": "{title}, {sub}: LuckyJ&#8217;s fitted rate of cutting the live tile is {points}.{cross}",
        "aria_point": "{pct} at discard {turn}",
        "aria_cross": " It crosses 50% between discards {a} and {b}.",
    },
    "ja": {
        "title": "LuckyJ が生牌を切るのをやめる場所",
        "sub": "副露者一人に対して2シャンテン以上、シャンテン数を保てる安全牌と生牌の両方を持っている時、生牌を切った割合（副露者のそれまでの捨て牌の数別）。点は1打ごとの値で、大きさはそこでの LuckyJ の局面数を表す。線は当てはめた曲線。",
        "legend_lj": "LuckyJ（1打ごとの値と曲線）",
        "legend_band": "曲線の95%範囲",
        "legend_humans": "特上と鳳凰卓の人間（曲線）",
        "legend_wash": "50%未満は安全牌が先に出る",
        "blocks": {"1": "鳴き1回", "2+": "鳴き2回か3回"},
        "counts": {"tie": "2枚が手にとって同じだけ良い", "costly": "安全牌を切ると受け入れが減る"},
        "axis": "副露者のそれまでの捨て牌の数",
        "cross": ("{a}打目と{b}打目の間で50%",),
        "table_summary": "数字を表で見る",
        "table_note": "各マスは LuckyJ、人間、LuckyJ の局面数の順。LuckyJ の局面がない打牌は空欄。",
        "table_discard": "打牌",
        "turns": "{n}局面",
        "tip_turn": "{turn}打目",
        "tip_fit": "曲線 {pct}",
        "humans": "人間",
        "aria": "{title}、{sub}：LuckyJ が生牌を切った割合の曲線は、{points}。{cross}",
        "aria_point": "{turn}打目で{pct}",
        "aria_cross": "{a}打目と{b}打目の間で50%を横切る。",
    },
}


def load() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def raw(curve: dict, turn: int) -> float | None:
    n = curve["n"][turn - 1]
    return 100 * curve["k"][turn - 1] / n if n else None


def panel(lang: str, block: str, count: str, curves: dict) -> str:
    t = TEXT[lang]
    title, sub = t["blocks"][block], t["counts"][count]
    lj, humans = curves["LuckyJ"], curves["humans"]
    lo, hi = lj["range"]
    fitted = {round(g[0], 1): g for g in lj["grid"]}
    svg = tf.frame(t["axis"], [(tf.x_turn(n), str(n)) for n in X_TICKS])
    # the fit's 95% band, then the humans' curve, then LuckyJ's curve and its dots on top
    upper = [f"{tf.r2(tf.x_turn(g[0]))},{tf.r2(tf.y_pct(g[3]))}" for g in lj["grid"]]
    lower = [f"{tf.r2(tf.x_turn(g[0]))},{tf.r2(tf.y_pct(g[2]))}" for g in reversed(lj["grid"])]
    svg.append(f'<polygon class="timing-band" points="{" ".join(upper + lower)}" />')
    svg.append(f'<line class="timing-cross" x1="0" x2="0" y1="{tf.M["t"]}" y2="{tf.M["t"] + tf.PH}" />')
    for key, curve in (("humans", humans), ("lj", lj)):
        points = " ".join(f"{tf.r2(tf.x_turn(g[0]))},{tf.r2(tf.y_pct(g[1]))}" for g in curve["grid"])
        svg.append(f'<polyline class="timing-fit {key}" points="{points}" />')
    for turn in range(lo, hi + 1):
        pct = raw(lj, turn)
        svg.append(
            f'<circle class="timing-dot lj" cx="{tf.r2(tf.x_turn(turn))}" cy="{tf.r2(tf.y_pct(pct))}" '
            f'r="{tf.dot_radius(lj["n"][turn - 1])}" data-turn="{turn}" data-pct="{pct:.1f}" data-n="{lj["n"][turn - 1]}" />'
        )
    cross_aria = ""
    for c in lj["crossings_50"]:
        a, b = tf.crossing_pair(c["turn"])
        x = tf.x_turn(c["turn"])
        svg.append(f'<circle class="timing-switch" cx="{tf.r2(x)}" cy="{tf.r2(tf.y_pct(50))}" r="4" data-turn="{c["turn"]:.2f}" />')
        # the curve falls through 50% here, so the note goes above and to the right, clear of it, on as many
        # lines as it needs to stay inside the plot on a phone
        note = t["cross"]
        tspans = "".join(f'<tspan x="{tf.r2(x + 7)}" dy="{0 if i == 0 else 13}">{line.format(a=a, b=b)}</tspan>' for i, line in enumerate(note))
        y = tf.y_pct(50) - 14 - 13 * len(note)
        svg.append(f'<text class="timing-note is-start" x="{tf.r2(x + 7)}" y="{tf.r2(y)}">{tspans}</text>')
        cross_aria += t["aria_cross"].format(a=a, b=b)

    def end_label(turn: int, neighbour: float, at_start: bool) -> str:
        value = fitted[float(turn)][1]
        dot = raw(lj, turn)
        radius = tf.dot_radius(lj["n"][turn - 1])
        # as in the timing charts: below the curve when it moves away upward from this end, above when downward
        top, bottom = min(tf.y_pct(value), tf.y_pct(dot)), max(tf.y_pct(value), tf.y_pct(dot))
        y = bottom + radius + 14 if neighbour > value else top - radius - 6
        if y > tf.M["t"] + tf.PH - 4:
            y = top - radius - 6
        if y < tf.M["t"] + 10:
            y = bottom + radius + 14
        anchor, dx = ("is-start", 6) if at_start else ("is-end", -6)
        return f'<text class="timing-label {anchor}" x="{tf.r2(tf.x_turn(turn) + dx)}" y="{tf.r2(y)}">{tf.half_up(value)}%</text>'

    svg.append(end_label(lo, fitted[round(lo + 1.0, 1)][1], True))
    svg.append(end_label(hi, fitted[round(hi - 1.0, 1)][1], False))
    step = tf.PW / (tf.TURNS[-1] - tf.TURNS[0])
    for turn in range(lo, hi + 1):
        rows_tip = [["lj", tf.fmt_pct(raw(lj, turn)), "LuckyJ"]]
        h = raw(humans, turn)
        if h is not None:
            rows_tip.append(["humans", tf.fmt_pct(h), t["humans"]])
        fit_pct = f"{tf.half_up(fitted[float(turn)][1])}%"
        foot = f'{t["turns"].format(n=f"{lj["n"][turn - 1]:,}")} · {t["tip_fit"].format(pct=fit_pct)}'
        payload = {"head": t["tip_turn"].format(turn=turn), "rows": rows_tip, "foot": foot}
        label = f'{t["tip_turn"].format(turn=turn)}: ' + ", ".join(f"{r[2]} {r[1]}" for r in rows_tip) + f", {foot}"
        svg.append(
            f'<rect class="timing-hit" x="{tf.r2(tf.x_turn(turn) - step / 2)}" y="{tf.M["t"]}" width="{tf.r2(step)}" '
            f'height="{tf.PH + 24}" tabindex="0" data-x="{tf.r2(tf.x_turn(turn))}" data-tip="{tf.tip_attr(payload)}" '
            f'aria-label="{html.escape(label, quote=True)}" />'
        )
    aria_points = ", ".join(t["aria_point"].format(pct=f"{tf.half_up(fitted[float(n)][1])}%", turn=n) for n in range(lo, hi + 1))
    aria = t["aria"].format(title=title, sub=sub, points=aria_points, cross=cross_aria)
    body = "\n            ".join(svg)
    return f'''        <div class="timing-panel" data-panel="fold-{block}-{count}">
          <p class="timing-panel-title"><b>{title}</b><span>{sub}</span></p>
          <div class="timing-plot">
            <svg viewBox="0 0 {tf.W} {tf.H}" role="img" aria-label="{html.escape(aria, quote=True)}">
            {body}
            </svg>
          </div>
        </div>'''


def table(lang: str, lines: dict) -> str:
    t = TEXT[lang]
    head = "".join(f'<th scope="col">{t["blocks"][block]}<br>{t["counts"][count]}</th>' for block, count in PANELS)
    body = []
    for turn in tf.TURNS:
        cells = []
        for block, count in PANELS:
            lj, humans = lines[count][block]["LuckyJ"], lines[count][block]["humans"]
            if not lj["n"][turn - 1]:
                cells.append("<td></td>")
                continue
            h = raw(humans, turn)
            cells.append(
                f'<td><b>{tf.fmt_pct(raw(lj, turn))}</b><span>{tf.fmt_pct(h) if h is not None else ""}</span>'
                f'<small>{t["turns"].format(n=f"{lj["n"][turn - 1]:,}")}</small></td>'
            )
        body.append(f'<tr><th scope="row">{turn}</th>{"".join(cells)}</tr>')
    rows = "\n              ".join(body)
    return f'''      <details class="timing-table">
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


def figure(lang: str, lines: dict, caption: str) -> str:
    t = TEXT[lang]
    drawn = "\n".join(panel(lang, block, count, lines[count][block]) for block, count in PANELS)
    return f'''  <figure class="timing-figure" id="oc-fold-line" aria-labelledby="oc-fold-line-caption">
    <div class="timing-plate">
      <p class="timing-title">{t["title"]}</p>
      <p class="timing-sub">{t["sub"]}</p>
      <p class="timing-legend"><span class="timing-key lj">{t["legend_lj"]}</span><span class="timing-key band">{t["legend_band"]}</span><span class="timing-key humans">{t["legend_humans"]}</span><span class="timing-key wash">{t["legend_wash"]}</span></p>
      <div class="timing-panels">
{drawn}
      </div>
    </div>
    <figcaption id="oc-fold-line-caption">{caption}</figcaption>
{table(lang, lines)}
  </figure>'''


def caption_of(text: str) -> str:
    """The caption is prose: kept in the page, with its correction mark, and carried over as it is."""
    tag = '<figcaption id="oc-fold-line-caption">'
    start = text.index(tag) + len(tag)
    return text[start:text.index("</figcaption>", start)]


def replace_block(text: str, block: str) -> str:
    start = "<!-- fold-figure:line -->"
    end = "<!-- /fold-figure:line -->"
    a = text.index(start) + len(start)
    b = text.index(end, a)
    return text[:a] + "\n" + block + "\n  " + text[b:]


def main() -> int:
    check = "--check" in sys.argv[1:]
    lines = load()["real_choices"]["lines"]["far"]
    stale = []
    for lang, path in PAGES.items():
        text = path.read_text(encoding="utf-8")
        new = replace_block(text, figure(lang, lines, caption_of(text)))
        if new != text:
            stale.append(path.name)
            if not check:
                path.write_text(new, encoding="utf-8")
    if check:
        if stale:
            print("stale:", ", ".join(stale))
            return 1
        print("the fold figure matches the artifact")
        return 0
    print("wrote:", ", ".join(stale) if stale else "nothing changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
