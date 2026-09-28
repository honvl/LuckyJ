#!/usr/bin/env python3
"""Draw the charts of the "Safe-tile timing" section from its analysis artifact.

The section in site/points.html and site/ja.html carries two figures, each written between
marker comments that this script fills:

  <!-- timing-figure:keep -->   four small line charts: how often LuckyJ kept the safe leftover,
                                by its own discards, for guest winds, terminals and middle tiles on
                                a quiet table, and for any leftover once someone threatens
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

BANDS = ("1-2", "3-5", "6-8", "9-12", "13-18")
PANELS = (("quiet", "honor"), ("quiet", "terminal"), ("quiet", "middle"), ("threat", "any"))
MIN_PLOTTED = 30  # a band with fewer choices is left off the chart (it stays in the table)
MIN_SOLID = 50  # a plotted band with fewer choices gets a hollow point

# One panel's drawing box, in SVG user units. The panels render at roughly this width on a phone
# and a little wider on a desktop, so the text stays near its set size on both.
W, H = 340, 224
M = {"l": 40, "r": 14, "t": 16, "b": 48}
PW, PH = W - M["l"] - M["r"], H - M["t"] - M["b"]

TEXT = {
    "en": {
        "keep_title": "How often LuckyJ kept the safe leftover",
        "keep_sub": "Two leftovers of the same kind, one already in an opponent&#8217;s river: the share of choices where LuckyJ kept that one and threw the other.",
        "legend_lj": "LuckyJ",
        "legend_naga": "NAGA at the same spot",
        "legend_hollow": "fewer than 50 choices",
        "legend_wash": "below 50%, the safe tile goes first",
        "panels": {
            "honor": ("Guest winds", "Quiet table"),
            "terminal": ("Terminals", "Quiet table, 1s and 9s"),
            "middle": ("Middle tiles", "Quiet table, 2 to 8"),
            "any": ("Once someone threatens", "After a riichi or a second call, any kind"),
        },
        "bands": {b: b for b in BANDS},
        "axis_keep": "LuckyJ&#8217;s own discards",
        "keep_caption": "Terminals and middle tiles are saved from the first discard, guest winds from the third. From the ninth discard the safe middle tile starts to go first, and once someone threatens, every safe leftover does.",
        "table_summary": "The numbers as a table",
        "table_keep_note": "Each cell: LuckyJ, then NAGA, then the number of choices.",
        "table_leftover": "Leftover",
        "table_band_head": "Discards {band}",
        "choices": "{n} choices",
        "tip_band": "Discards {band}",
        "threat_title": "When threats arrive",
        "threat_sub": "Share of LuckyJ&#8217;s decisions facing a riichi or a hand with two calls, by its own discard",
        "axis_threat": "LuckyJ&#8217;s own discard",
        "threat_caption": "At its fourth discard, 8% of LuckyJ&#8217;s decisions face a threat. By its tenth, more than half do.",
        "threat_table_discard": "Discard",
        "threat_table_share": "Facing a threat",
        "threat_table_states": "Decisions",
        "tip_turn": "Discard {turn}",
        "tip_threat": "faced a threat",
        "tip_states": "{n} decisions",
        "keep_aria": "{title}: LuckyJ kept the safe leftover {points}.",
        "keep_aria_point": "{pct} on discards {band}",
        "threat_aria": "When threats arrive: {points}.",
        "threat_aria_point": "{pct} at discard {turn}",
    },
    "ja": {
        "keep_title": "LuckyJ が安全な浮き牌を残した割合",
        "keep_sub": "同じ種類の浮き牌が2枚あり、1枚はすでに相手の河にあるとき、LuckyJ がその牌を残してもう1枚を切った割合。",
        "legend_lj": "LuckyJ",
        "legend_naga": "同じ局面の NAGA",
        "legend_hollow": "選択が50回未満",
        "legend_wash": "50%未満は安全な方が先に出る",
        "panels": {
            "honor": ("客風", "静かな場"),
            "terminal": ("端牌", "静かな場、1と9"),
            "middle": ("中張牌", "静かな場、2〜8"),
            "any": ("脅威が出た後", "リーチか2副露の後、すべての種類"),
        },
        "bands": {b: b.replace("-", "〜") for b in BANDS},
        "axis_keep": "LuckyJ 自身の打牌数",
        "keep_caption": "端牌と中張牌は1打目から、客風は3打目から取っておく。9打目からは安全な中張牌が先に出始め、誰かが脅威になると、どの安全な浮き牌も先に出る。",
        "table_summary": "数字を表で見る",
        "table_keep_note": "各マスは LuckyJ、NAGA、選択の回数の順。",
        "table_leftover": "浮き牌",
        "table_band_head": "{band}打目",
        "choices": "選択{n}回",
        "tip_band": "{band}打目",
        "threat_title": "脅威が出てくる時期",
        "threat_sub": "リーチか2副露の相手に直面した LuckyJ の判断の割合（自身の打牌数別）",
        "axis_threat": "LuckyJ 自身の打牌数",
        "threat_caption": "4打目では LuckyJ の判断の8%が脅威に直面し、10打目では半分を超える。",
        "threat_table_discard": "打牌",
        "threat_table_share": "脅威あり",
        "threat_table_states": "判断の数",
        "tip_turn": "{turn}打目",
        "tip_threat": "脅威に直面",
        "tip_states": "判断{n}回",
        "keep_aria": "{title}：LuckyJ が安全な浮き牌を残した割合は{points}。",
        "keep_aria_point": "{band}打目で{pct}",
        "threat_aria": "脅威が出てくる時期：{points}。",
        "threat_aria_point": "{turn}打目で{pct}",
    },
}

THREAT_LABELED_TURNS = ("4", "7", "10")


def load() -> dict:
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    return artifact["summary_bands"]


def half_up(value: float) -> int:
    return int(value + 0.5)


def fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def x_band(i: int) -> float:
    return M["l"] + PW * (i + 0.5) / len(BANDS)


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


def keep_panel(lang: str, bands: dict, split: str, kind: str) -> str:
    t = TEXT[lang]
    title, sub = t["panels"][kind]
    data = bands[split][kind]
    rows = []
    for i, band in enumerate(BANDS):
        lj, naga = data[band]["LuckyJ"], data[band]["NAGA"]
        rows.append({
            "i": i,
            "band": band,
            "n": lj["cuts"],
            "lj": lj["live_share_pct"],
            "naga": naga["live_share_pct"],
            "plotted": lj["cuts"] >= MIN_PLOTTED,
            "solid": lj["cuts"] >= MIN_SOLID,
        })
    plotted = [r for r in rows if r["plotted"]]
    svg = frame(t["axis_keep"], [(x_band(r["i"]), t["bands"][r["band"]]) for r in rows])
    svg.append(f'<line class="timing-cross" x1="0" x2="0" y1="{M["t"]}" y2="{M["t"] + PH}" />')
    for key in ("naga", "lj"):
        points = " ".join(f'{r2(x_band(r["i"]))},{r2(y_pct(r[key]))}' for r in plotted)
        svg.append(f'<polyline class="timing-line {key}" points="{points}" />')
    for key in ("naga", "lj"):
        for r in plotted:
            radius = 4.5 if key == "lj" else 4
            hollow = "" if r["solid"] else " hollow"
            svg.append(
                f'<circle class="timing-dot {key}{hollow}" cx="{r2(x_band(r["i"]))}" cy="{r2(y_pct(r[key]))}" r="{radius}" '
                f'data-band="{r["band"]}" data-pct="{r[key]:.1f}" />'
            )
    # Direct labels on LuckyJ's first and last solid points only; the table and the tooltip carry the rest.
    solid = [r for r in plotted if r["solid"]]
    for r in {id(solid[0]): solid[0], id(solid[-1]): solid[-1]}.values():
        value = r["lj"]
        above = value >= r["naga"]
        if value > 88:
            above = False
        if value < 12:
            above = True
        y = y_pct(value) - 11 if above else y_pct(value) + 20
        svg.append(f'<text class="timing-label" x="{r2(x_band(r["i"]))}" y="{r2(y)}">{half_up(value)}%</text>')
    slot = PW / len(BANDS)
    for r in plotted:
        payload = {
            "head": t["tip_band"].format(band=t["bands"][r["band"]]),
            "rows": [["lj", fmt_pct(r["lj"]), "LuckyJ"], ["naga", fmt_pct(r["naga"]), "NAGA"]],
            "foot": t["choices"].format(n=f"{r['n']:,}"),
        }
        label = f'{t["tip_band"].format(band=t["bands"][r["band"]])}: LuckyJ {fmt_pct(r["lj"])}, NAGA {fmt_pct(r["naga"])}, {t["choices"].format(n=f"{r["n"]:,}")}'
        svg.append(
            f'<rect class="timing-hit" x="{r2(M["l"] + slot * r["i"])}" y="{M["t"]}" width="{r2(slot)}" height="{PH + 24}" '
            f'tabindex="0" data-x="{r2(x_band(r["i"]))}" data-tip="{tip_attr(payload)}" aria-label="{html.escape(label, quote=True)}" />'
        )
    aria_points = ", ".join(
        t["keep_aria_point"].format(pct=f"{half_up(r['lj'])}%", band=t["bands"][r["band"]]) for r in plotted
    )
    aria = t["keep_aria"].format(title=title, points=aria_points)
    body = "\n            ".join(svg)
    return f'''        <div class="timing-panel" data-panel="{split}-{kind}">
          <p class="timing-panel-title"><b>{title}</b><span>{sub}</span></p>
          <div class="timing-plot">
            <svg viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(aria, quote=True)}">
            {body}
            </svg>
          </div>
        </div>'''


def keep_table(lang: str, bands: dict) -> str:
    t = TEXT[lang]
    head = "".join(f'<th scope="col">{t["table_band_head"].format(band=t["bands"][b])}</th>' for b in BANDS)
    body = []
    for split, kind in PANELS:
        cells = []
        for band in BANDS:
            lj = bands[split][kind][band]["LuckyJ"]
            naga = bands[split][kind][band]["NAGA"]
            if lj["cuts"] == 0:
                cells.append("<td></td>")
                continue
            cells.append(
                f'<td><b>{fmt_pct(lj["live_share_pct"])}</b><span>{fmt_pct(naga["live_share_pct"])}</span>'
                f'<small>{t["choices"].format(n=f"{lj["cuts"]:,}")}</small></td>'
            )
        body.append(f'<tr><th scope="row">{t["panels"][kind][0]}</th>{"".join(cells)}</tr>')
    rows = "\n              ".join(body)
    return f'''      <details class="timing-table">
        <summary>{t["table_summary"]}</summary>
        <p>{t["table_keep_note"]}</p>
        <div class="timing-table-scroll">
          <table>
            <thead><tr><th scope="col">{t["table_leftover"]}</th>{head}</tr></thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </div>
      </details>'''


def keep_figure(lang: str, bands: dict) -> str:
    t = TEXT[lang]
    panels = "\n".join(keep_panel(lang, bands, split, kind) for split, kind in PANELS)
    return f'''  <figure class="timing-figure" id="timing-keep" aria-labelledby="timing-keep-caption">
    <div class="timing-plate">
      <p class="timing-title">{t["keep_title"]}</p>
      <p class="timing-sub">{t["keep_sub"]}</p>
      <p class="timing-legend"><span class="timing-key lj">{t["legend_lj"]}</span><span class="timing-key naga">{t["legend_naga"]}</span><span class="timing-key hollow">{t["legend_hollow"]}</span><span class="timing-key wash">{t["legend_wash"]}</span></p>
      <div class="timing-panels">
{panels}
      </div>
    </div>
    <figcaption id="timing-keep-caption">{t["keep_caption"]}</figcaption>
{keep_table(lang, bands)}
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
            <thead><tr><th scope="col">{t["threat_table_discard"]}</th><th scope="col">{t["threat_table_share"]}</th><th scope="col">{t["threat_table_states"]}</th></tr></thead>
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
    summary = load()
    stale = []
    for lang, path in PAGES.items():
        text = path.read_text(encoding="utf-8")
        new = replace_block(text, "keep", keep_figure(lang, summary["bands"]))
        new = replace_block(new, "threat", threat_figure(lang, summary["threat_share_by_turn"]))
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
