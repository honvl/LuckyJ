#!/usr/bin/env python3
"""Draw the charts of the "Safe-tile timing" section from its analysis artifact.

The section in site/points.html and site/ja.html carries two figures, each written between
marker comments that this script fills:

  <!-- timing-figure:keep -->   four small charts: how often LuckyJ kept the safe leftover at each
                                of its own discards (one dot per discard, sized by its choices),
                                with a fitted curve and its 95% band, for guest winds, terminals and
                                middle tiles on a quiet table, and for any leftover once someone
                                threatens; NAGA's fitted curve in gray
  <!-- timing-figure:threat --> one area chart: how often a riichi or a two-call hand is on the
                                table, by LuckyJ's own discard

Each figure is static SVG (it reads without JavaScript), with a hover layer that app.js adds
from the data-tip attributes, and a folded table with every rate and its sample.

usage: build_safe_tile_timing_figures.py [--check]
  --check  exit 1 if the pages do not match what the script would write
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "analysis/safe-tile-timing-2026-09-28.json"
PAGES = {"en": ROOT / "site/points.html", "ja": ROOT / "site/ja.html"}

PANELS = (("quiet", "honor"), ("quiet", "terminal"), ("quiet", "middle"), ("threat", "any"))
TURNS = tuple(range(1, 19))
X_TICKS = (1, 3, 6, 9, 12, 15, 18)

# One panel's drawing box, in SVG user units. The panels render at roughly this width on a phone
# and a little wider on a desktop, so the text stays near its set size on both.
W, H = 340, 224
M = {"l": 40, "r": 14, "t": 16, "b": 48}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]

TEXT = {
    "en": {
        "keep_title": "How often LuckyJ kept the safe leftover",
        "keep_sub": "Two leftovers of the same kind, one already in an opponent&#8217;s river: the share of choices where LuckyJ kept that one and threw the other. Each dot is one discard, sized by its number of choices; the line is a fitted curve.",
        "legend_lj": "LuckyJ, per discard and fitted",
        "legend_band": "95% range of the fit",
        "legend_naga": "NAGA, fitted",
        "legend_wash": "below 50%, the safe tile goes first",
        "panels": {
            "honor": ("Guest winds", "Quiet table"),
            "terminal": ("Terminals", "Quiet table, 1s and 9s"),
            "middle": ("Middle tiles", "Quiet table, 2 to 8"),
            "any": ("Once someone threatens", "After a riichi or a second call, any kind"),
        },
        "axis_keep": "LuckyJ&#8217;s own discard",
        "cross": "50% between discards {a} and {b}",
        "keep_caption": "Terminals and middle tiles are saved from the first discard, guest winds from the third. From about the seventh discard the safe middle tile starts to go first, and once someone threatens, every safe leftover does.",
        "table_summary": "The numbers as a table",
        "table_keep_note": "Each cell: LuckyJ, then NAGA, then the number of choices. Discards with no choices are blank.",
        "table_discard": "Discard",
        "choices": "{n} choices",
        "tip_turn": "Discard {turn}",
        "tip_fit": "fitted {pct}",
        "threat_title": "When threats arrive",
        "threat_sub": "Share of LuckyJ&#8217;s decisions facing a riichi or a hand with two calls, by its own discard",
        "axis_threat": "LuckyJ&#8217;s own discard",
        "threat_caption": "At its fourth discard, 8% of LuckyJ&#8217;s decisions face a threat. By its tenth, more than half do.",
        "threat_table_share": "Facing a threat",
        "threat_table_states": "Decisions",
        "tip_threat": "faced a threat",
        "tip_states": "{n} decisions",
        "keep_aria": "{title}: LuckyJ&#8217;s fitted rate of keeping the safe leftover is {points}.{cross}",
        "keep_aria_point": "{pct} at discard {turn}",
        "keep_aria_cross": " It crosses 50% between discards {a} and {b}.",
        "threat_aria": "When threats arrive: {points}.",
        "threat_aria_point": "{pct} at discard {turn}",
    },
    "ja": {
        "keep_title": "LuckyJ が安全な浮き牌を残した割合",
        "keep_sub": "同じ種類の浮き牌が2枚あり、1枚はすでに相手の河にあるとき、LuckyJ がその牌を残してもう1枚を切った割合。点は1打ごとの値で、大きさは選択の回数を表す。線は当てはめた曲線。",
        "legend_lj": "LuckyJ（1打ごとの値と曲線）",
        "legend_band": "曲線の95%範囲",
        "legend_naga": "NAGA（曲線）",
        "legend_wash": "50%未満は安全な方が先に出る",
        "panels": {
            "honor": ("客風", "静かな場"),
            "terminal": ("端牌", "静かな場、1と9"),
            "middle": ("中張牌", "静かな場、2〜8"),
            "any": ("脅威が出た後", "リーチか2副露の後、すべての種類"),
        },
        "axis_keep": "LuckyJ 自身の打牌数",
        "cross": "{a}打目と{b}打目の間で50%",
        "keep_caption": "端牌と中張牌は1打目から、客風は3打目から取っておく。7打目ごろからは安全な中張牌が先に出始め、誰かが脅威になると、どの安全な浮き牌も先に出る。",
        "table_summary": "数字を表で見る",
        "table_keep_note": "各マスは LuckyJ、NAGA、選択の回数の順。選択がない打牌は空欄。",
        "table_discard": "打牌",
        "choices": "選択{n}回",
        "tip_turn": "{turn}打目",
        "tip_fit": "曲線 {pct}",
        "threat_title": "脅威が出てくる時期",
        "threat_sub": "リーチか2副露の相手に直面した LuckyJ の判断の割合（自身の打牌数別）",
        "axis_threat": "LuckyJ 自身の打牌数",
        "threat_caption": "4打目では LuckyJ の判断の8%が脅威に直面し、10打目では半分を超える。",
        "threat_table_share": "脅威あり",
        "threat_table_states": "判断の数",
        "tip_threat": "脅威に直面",
        "tip_states": "判断{n}回",
        "keep_aria": "{title}：LuckyJ が安全な浮き牌を残した割合の曲線は、{points}。{cross}",
        "keep_aria_point": "{turn}打目で{pct}",
        "keep_aria_cross": "{a}打目と{b}打目の間で50%を横切る。",
        "threat_aria": "脅威が出てくる時期：{points}。",
        "threat_aria_point": "{turn}打目で{pct}",
    },
}

THREAT_LABELED_TURNS = ("4", "7", "10")


def load() -> dict:
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def half_up(value: float) -> int:
    return int(value + 0.5)


def fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def x_turn(turn: float) -> float:
    return M["l"] + PW * (turn - TURNS[0]) / (TURNS[-1] - TURNS[0])


def dot_radius(n: int) -> float:
    """Dot area grows with the number of choices behind it."""
    return round(min(6.5, max(2.5, 1.6 + 0.3 * n ** 0.5)), 2)


def y_pct(value: float) -> float:
    return M["t"] + PH * (1 - value / 100)


def r2(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".")


def tip_attr(payload: dict) -> str:
    return html.escape(json.dumps(payload, ensure_ascii=False), quote=True)


def frame(axis_title: str, tick_x: list[tuple[float, str]]) -> list[str]:
    """Gridlines, the shaded half below 50%, y ticks, x labels and the axis title."""
    out = [f'<rect class="timing-wash" x="{M["l"]}" y="{r2(y_pct(50))}" width="{PW}" height="{r2(PH / 2)}" />']
    for tick in (0, 25, 50, 75, 100):
        cls = "timing-mid" if tick == 50 else "timing-grid"
        out.append(f'<line class="{cls}" x1="{M["l"]}" x2="{M["l"] + PW}" y1="{r2(y_pct(tick))}" y2="{r2(y_pct(tick))}" />')
        if tick in (0, 50, 100):
            out.append(f'<text class="timing-tick" x="{M["l"] - 8}" y="{r2(y_pct(tick) + 4)}">{tick}%</text>')
    for x, label in tick_x:
        out.append(f'<text class="timing-cat" x="{r2(x)}" y="{M["t"] + PH + 18}">{label}</text>')
    out.append(f'<text class="timing-axis" x="{r2(M["l"] + PW / 2)}" y="{H - 6}">{axis_title}</text>')
    return out


def crossing_pair(turn: float) -> tuple[int, int]:
    lower = int(turn)
    return lower, lower + 1


def keep_panel(lang: str, panel: dict, split: str, kind: str) -> str:
    t = TEXT[lang]
    title, sub = t["panels"][kind]
    lo, hi = panel["range"]
    rows = {r["turn"]: r for r in panel["turns"]}
    lj_fit, naga_fit = panel["fits"]["LuckyJ"], panel["fits"]["NAGA"]
    fitted = {round(g[0], 1): g for g in lj_fit["grid"]}
    svg = frame(t["axis_keep"], [(x_turn(n), str(n)) for n in X_TICKS])
    # the fit's 95% band, then NAGA's curve, then LuckyJ's curve and its dots on top
    upper = [f"{r2(x_turn(g[0]))},{r2(y_pct(g[3]))}" for g in lj_fit["grid"]]
    lower = [f"{r2(x_turn(g[0]))},{r2(y_pct(g[2]))}" for g in reversed(lj_fit["grid"])]
    svg.append(f'<polygon class="timing-band" points="{" ".join(upper + lower)}" />')
    svg.append(f'<line class="timing-cross" x1="0" x2="0" y1="{M["t"]}" y2="{M["t"] + PH}" />')
    for key, fit in (("naga", naga_fit), ("lj", lj_fit)):
        points = " ".join(f"{r2(x_turn(g[0]))},{r2(y_pct(g[1]))}" for g in fit["grid"])
        svg.append(f'<polyline class="timing-fit {key}" points="{points}" />')
    for turn in range(lo, hi + 1):
        r = rows[turn]
        pct = 100 * r["lj_k"] / r["lj_n"]
        svg.append(
            f'<circle class="timing-dot lj" cx="{r2(x_turn(turn))}" cy="{r2(y_pct(pct))}" r="{dot_radius(r["lj_n"])}" '
            f'data-turn="{turn}" data-pct="{pct:.1f}" data-n="{r["lj_n"]}" />'
        )
    # where LuckyJ's curve crosses 50%, and its value at each end
    cross_aria = ""
    for c in lj_fit["crossings_50"]:
        a, b = crossing_pair(c["turn"])
        x = x_turn(c["turn"])
        svg.append(f'<circle class="timing-switch" cx="{r2(x)}" cy="{r2(y_pct(50))}" r="4" data-turn="{c["turn"]:.2f}" />')
        # the curve leaves the crossing upward (note goes below, to the right) or downward (above, to the right,
        # high enough to clear the dots that scatter around 50%)
        y = y_pct(50) + 18 if c["direction"] == "up" else y_pct(50) - 26
        svg.append(f'<text class="timing-note is-start" x="{r2(x + 7)}" y="{r2(y)}">{t["cross"].format(a=a, b=b)}</text>')
        cross_aria += t["keep_aria_cross"].format(a=a, b=b)

    def end_label(turn: int, value: float, neighbour: float, at_start: bool) -> str:
        r = rows[turn]
        dot = 100 * r["lj_k"] / r["lj_n"]
        radius = dot_radius(r["lj_n"])
        # below the curve when it moves away upward from this end, above when it moves away downward
        below = neighbour > value
        top, bottom = min(y_pct(value), y_pct(dot)), max(y_pct(value), y_pct(dot))
        y = bottom + radius + 14 if below else top - radius - 6
        if y > M["t"] + PH - 4:
            y = top - radius - 6
        if y < M["t"] + 10:
            y = bottom + radius + 14
        if at_start:
            return f'<text class="timing-label is-start" x="{r2(x_turn(turn) + 6)}" y="{r2(y)}">{half_up(value)}%</text>'
        return f'<text class="timing-label is-end" x="{r2(x_turn(turn) - 6)}" y="{r2(y)}">{half_up(value)}%</text>'

    svg.append(end_label(lo, fitted[float(lo)][1], fitted[round(lo + 1.0, 1)][1], True))
    svg.append(end_label(hi, fitted[float(hi)][1], fitted[round(hi - 1.0, 1)][1], False))
    step = PW / (TURNS[-1] - TURNS[0])
    naga_rows = {r["turn"]: r for r in panel["turns"]}
    for turn in range(lo, hi + 1):
        r = naga_rows[turn]
        lj_pct = 100 * r["lj_k"] / r["lj_n"]
        naga_pct = 100 * r["naga_k"] / r["naga_n"] if r["naga_n"] else None
        rows_tip = [["lj", fmt_pct(lj_pct), "LuckyJ"]]
        if naga_pct is not None:
            rows_tip.append(["naga", fmt_pct(naga_pct), "NAGA"])
        fit_pct = f"{half_up(fitted[float(turn)][1])}%"
        foot = f'{t["choices"].format(n=f"{r["lj_n"]:,}")} · {t["tip_fit"].format(pct=fit_pct)}'
        payload = {"head": t["tip_turn"].format(turn=turn), "rows": rows_tip, "foot": foot}
        label = f'{t["tip_turn"].format(turn=turn)}: LuckyJ {fmt_pct(lj_pct)}' + (f", NAGA {fmt_pct(naga_pct)}" if naga_pct is not None else "") + f", {foot}"
        left = x_turn(turn) - step / 2
        svg.append(
            f'<rect class="timing-hit" x="{r2(left)}" y="{M["t"]}" width="{r2(step)}" height="{PH + 24}" '
            f'tabindex="0" data-x="{r2(x_turn(turn))}" data-tip="{tip_attr(payload)}" aria-label="{html.escape(label, quote=True)}" />'
        )
    aria_points = ", ".join(
        t["keep_aria_point"].format(pct=f"{half_up(fitted[float(n)][1])}%", turn=n) for n in range(lo, hi + 1)
    )
    aria = t["keep_aria"].format(title=title, points=aria_points, cross=cross_aria)
    body = "\n            ".join(svg)
    return f'''        <div class="timing-panel" data-panel="{split}-{kind}">
          <p class="timing-panel-title"><b>{title}</b><span>{sub}</span></p>
          <div class="timing-plot">
            <svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(aria, quote=True)}">
            {body}
            </svg>
          </div>
        </div>'''


def keep_table(lang: str, panels: dict) -> str:
    t = TEXT[lang]
    head = "".join(f'<th scope="col">{t["panels"][kind][0]}</th>' for _, kind in PANELS)
    body = []
    for turn in TURNS:
        cells = []
        for split, kind in PANELS:
            r = next(x for x in panels[f"{split}-{kind}"]["turns"] if x["turn"] == turn)
            if not r["lj_n"]:
                cells.append("<td></td>")
                continue
            naga = fmt_pct(100 * r["naga_k"] / r["naga_n"]) if r["naga_n"] else ""
            cells.append(
                f'<td><b>{fmt_pct(100 * r["lj_k"] / r["lj_n"])}</b><span>{naga}</span>'
                f'<small>{t["choices"].format(n=f"{r["lj_n"]:,}")}</small></td>'
            )
        body.append(f'<tr><th scope="row">{turn}</th>{"".join(cells)}</tr>')
    rows = "\n              ".join(body)
    return f'''      <details class="timing-table">
        <summary>{t["table_summary"]}</summary>
        <p>{t["table_keep_note"]}</p>
        <div class="timing-table-scroll">
          <table>
            <thead><tr><th scope="col">{t["table_discard"]}</th>{head}</tr></thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>
      </details>'''


def keep_figure(lang: str, panels: dict) -> str:
    t = TEXT[lang]
    drawn = "\n".join(keep_panel(lang, panels[f"{split}-{kind}"], split, kind) for split, kind in PANELS)
    return f'''  <figure class="timing-figure" id="timing-keep" aria-labelledby="timing-keep-caption">
    <div class="timing-plate">
      <p class="timing-title">{t["keep_title"]}</p>
      <p class="timing-sub">{t["keep_sub"]}</p>
      <p class="timing-legend"><span class="timing-key lj">{t["legend_lj"]}</span><span class="timing-key band">{t["legend_band"]}</span><span class="timing-key naga">{t["legend_naga"]}</span><span class="timing-key wash">{t["legend_wash"]}</span></p>
      <div class="timing-panels">
{drawn}
      </div>
    </div>
    <figcaption id="timing-keep-caption">{t["keep_caption"]}</figcaption>
{keep_table(lang, panels)}
  </figure>'''


def threat_figure(lang: str, share: dict) -> str:
    t = TEXT[lang]
    turns = [str(n) for n in range(1, 19)]
    step = PW / (len(turns) - 1)

    def x_turn(i: int) -> float:
        return M["l"] + step * i

    ticks = [(x_turn(int(n) - 1), n) for n in ("1", "3", "6", "9", "12", "15", "18")]
    svg = [line for line in frame(t["axis_threat"], ticks) if 'class="timing-wash"' not in line and 'class="timing-mid"' not in line]
    # the 50% line is only a gridline here: this chart has no "no preference" level
    svg.insert(0, f'<line class="timing-grid" x1="{M["l"]}" x2="{M["l"] + PW}" y1="{r2(y_pct(50))}" y2="{r2(y_pct(50))}" />')
    values = [share[n]["threat_pct"] for n in turns]
    line_points = " ".join(f"{r2(x_turn(i))},{r2(y_pct(v))}" for i, v in enumerate(values))
    area = f'M{r2(x_turn(0))},{r2(y_pct(0))} L' + " L".join(f"{r2(x_turn(i))},{r2(y_pct(v))}" for i, v in enumerate(values)) + f' L{r2(x_turn(len(turns) - 1))},{r2(y_pct(0))} Z'
    svg.append(f'<path class="timing-area" d="{area}" />')
    svg.append(f'<line class="timing-cross" x1="0" x2="0" y1="{M["t"]}" y2="{M["t"] + PH}" />')
    svg.append(f'<polyline class="timing-line threat" points="{line_points}" />')
    for n in THREAT_LABELED_TURNS:
        i = int(n) - 1
        v = share[n]["threat_pct"]
        svg.append(f'<circle class="timing-dot threat" cx="{r2(x_turn(i))}" cy="{r2(y_pct(v))}" r="4.5" data-turn="{n}" data-pct="{v:.1f}" />')
        svg.append(f'<text class="timing-label is-end" x="{r2(x_turn(i) - 6)}" y="{r2(y_pct(v) - 11)}">{half_up(v)}%</text>')
    for i, n in enumerate(turns):
        v = share[n]["threat_pct"]
        states = share[n]["states"]
        payload = {
            "head": t["tip_turn"].format(turn=n),
            "rows": [["threat", fmt_pct(v), t["tip_threat"]]],
            "foot": t["tip_states"].format(n=f"{states:,}"),
        }
        left = x_turn(i) - step / 2 if i else M["l"] - 8
        right = x_turn(i) + step / 2 if i < len(turns) - 1 else M["l"] + PW + 8
        label = f'{t["tip_turn"].format(turn=n)}: {fmt_pct(v)} {t["tip_threat"]}, {t["tip_states"].format(n=f"{states:,}")}'
        svg.append(
            f'<rect class="timing-hit" x="{r2(left)}" y="{M["t"]}" width="{r2(right - left)}" height="{PH + 24}" '
            f'tabindex="0" data-x="{r2(x_turn(i))}" data-tip="{tip_attr(payload)}" aria-label="{html.escape(label, quote=True)}" />'
        )
    aria_points = ", ".join(
        t["threat_aria_point"].format(pct=f"{half_up(share[n]['threat_pct'])}%", turn=n) for n in ("1",) + THREAT_LABELED_TURNS + ("18",)
    )
    aria = t["threat_aria"].format(points=aria_points)
    body = "\n            ".join(svg)
    table_rows = "\n              ".join(
        f'<tr><th scope="row">{n}</th><td>{fmt_pct(share[n]["threat_pct"])}</td><td>{share[n]["states"]:,}</td></tr>' for n in turns
    )
    return f'''  <figure class="timing-figure is-single" id="timing-threat" aria-labelledby="timing-threat-caption">
    <div class="timing-plate">
      <p class="timing-title">{t["threat_title"]}</p>
      <p class="timing-sub">{t["threat_sub"]}</p>
      <div class="timing-panels">
        <div class="timing-panel" data-panel="threat-share">
          <div class="timing-plot">
            <svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(aria, quote=True)}">
            {body}
            </svg>
          </div>
        </div>
      </div>
    </div>
    <figcaption id="timing-threat-caption">{t["threat_caption"]}</figcaption>
      <details class="timing-table">
        <summary>{t["table_summary"]}</summary>
        <div class="timing-table-scroll">
          <table class="is-narrow">
            <thead><tr><th scope="col">{t["table_discard"]}</th><th scope="col">{t["threat_table_share"]}</th><th scope="col">{t["threat_table_states"]}</th></tr></thead>
            <tbody>
              {table_rows}
            </tbody>
          </table>
        </div>
      </details>
  </figure>'''


def replace_block(text: str, name: str, block: str) -> str:
    start = f"<!-- timing-figure:{name} -->"
    end = f"<!-- /timing-figure:{name} -->"
    a = text.index(start) + len(start)
    b = text.index(end, a)
    return text[:a] + "\n" + block + "\n  " + text[b:]


def main() -> int:
    check = "--check" in sys.argv[1:]
    artifact = load()
    panels = artifact["summary_turns"]["panels"]
    share = artifact["summary_bands"]["threat_share_by_turn"]
    stale = []
    for lang, path in PAGES.items():
        text = path.read_text(encoding="utf-8")
        new = replace_block(text, "keep", keep_figure(lang, panels))
        new = replace_block(new, "threat", threat_figure(lang, share))
        if new != text:
            stale.append(path.name)
            if not check:
                path.write_text(new, encoding="utf-8")
    if check:
        if stale:
            print("stale:", ", ".join(stale))
            return 1
        print("figures match the artifact")
        return 0
    print("wrote:", ", ".join(stale) if stale else "nothing changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
