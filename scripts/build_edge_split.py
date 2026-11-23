#!/usr/bin/env python3
"""Draw chapter 56's figures and table from ``analysis/edge-split-2026-11-23.json`` (``mine_edge_split.py``).

Three pieces go into ``site/honver.html`` and, with Japanese labels, ``site/honver-ja.html``, each between its own
markers:

- ``edge-split``: where 0.10 places of strength lands among the four places, in the Jade, Throne and Houou rooms.
- ``edge-pace``: Saint 3 points a game by strength, with the Jade room's split and with Houou's even split.
- ``edge-lines``: the strength each rank takes on chapter 53's scale, with each split.

``--check`` exits non-zero when a page and the data disagree.

    .venv/bin/python scripts/build_edge_split.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "edge-split-2026-11-23.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
PARTS = ("edge-split", "edge-pace", "edge-lines")

WORDS = {
    "en": {
        "split_title": "Where 0.10 places of strength lands",
        "split_sub": ("Change in the share of each place for a player 0.10 places a game stronger than their table. In the "
                      "Jade room fourths fall twice as fast as firsts rise; in the Houou room they move together."),
        "jade": "Jade room", "throne": "Throne room", "houou": "Houou room",
        "places": ["1st", "2nd", "3rd", "4th"],
        "split_axis": "Change in share, percentage points",
        "aria_split": "Change in the share of 1st to 4th per 0.10 places of strength. ",
        "split_caption": ("Chapter 53&#8217;s fits: 100,000 Jade tables, {throne:,} Throne tables and 15,929 Houou "
                          "hanchan, each seat&#8217;s place against its strength over the other three."),
        "pace_title": "Saint 3 points a game, by strength",
        "pace_sub": ("At Saint 3&#8217;s Jade tables. The same strength earns less when its edge splits evenly, and the "
                     "line where it starts to climb moves from 2.49 to 2.47."),
        "j_line": "Jade split", "h_line": "Even split, as in Houou",
        "pace_axis": "Strength on chapter 53&#8217;s scale (average placement against three average Saint 3s)",
        "per_game": "points a game", "stronger": "stronger",
        "eight": "Average 8-dan", "you": "You, results",
        "aria_pace": "Saint 3 points a game by strength. ",
        "pace_caption": ("Saint 3&#8217;s average points by place in the Jade room ({pts}), its tables&#8217; field, and "
                         "each split&#8217;s share slopes. One game swings by about 160 points either way."),
        "th": ["To reach", "Jade split", "Even split", "Moves by"],
        "ranks": {"Saint 1": "Saint 2", "Saint 2": "Saint 3", "Saint 3": "Celestial", "七段": "8-dan", "八段": "9-dan",
                  "九段": "10-dan", "十段": "Tenhou-i"},
        "own": "own room",
    },
    "ja": {
        "split_title": "0.10順位分の強さはどの順位に出るか",
        "split_sub": "卓の相手より1半荘あたり0.10順位強い打ち手で、各順位の割合がどれだけ動くか。玉の間では4位が減る速さが1位が増える速さの2倍で、鳳凰卓では同じ速さで動く。",
        "jade": "玉の間", "throne": "王座の間", "houou": "鳳凰卓",
        "places": ["1位", "2位", "3位", "4位"],
        "split_axis": "割合の変化（ポイント）",
        "aria_split": "強さ0.10順位あたりの1位から4位の割合の変化。",
        "split_caption": "第53章の当てはめ。玉の間10万卓、王座の間{throne:,}卓、鳳凰卓15,929半荘で、各席の順位を他の三人に対する強さで見た。",
        "pace_title": "雀聖3の1半荘あたりのポイント（強さ別）",
        "pace_sub": "雀聖3の玉の間の卓で。同じ強さでも差が均等に出ると稼ぎが減り、上がり始める線は2.49から2.47に動く。",
        "j_line": "玉の間の出方", "h_line": "均等な出方（鳳凰卓）",
        "pace_axis": "第53章の目盛りでの強さ（平均的な雀聖3三人との平均順位）",
        "per_game": "1半荘のポイント", "stronger": "強い",
        "eight": "平均的な八段", "you": "あなた（成績）",
        "aria_pace": "強さ別の雀聖3の1半荘あたりのポイント。",
        "pace_caption": "雀聖3の玉の間での順位別平均ポイント（{pts}）、その卓の相手、それぞれの出方の割合の傾きから。1半荘で上下に約160ポイント振れる。",
        "th": ["届く段位", "玉の間の出方", "均等な出方", "差"],
        "ranks": {"Saint 1": "雀聖2", "Saint 2": "雀聖3", "Saint 3": "魂天", "七段": "八段", "八段": "九段", "九段": "十段", "十段": "天鳳位"},
        "own": "自分の卓",
    },
}


def f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def pct(v: float) -> str:
    s = f"{abs(v):.1f}"
    return ("+" if v > 0 else "&#8722;" if v < 0 else "") + s


def split(data: dict, lang: str) -> str:
    w = WORDS[lang]
    sp = data["splits"]
    rooms = [("jade", sp["jade"]), ("throne", sp["throne"]), ("houou", sp["houou"])]
    L, R, T, B = 58, 458, 30, 250
    v0, v1 = -4.5, 3.5

    def y(v: float) -> float:
        return B - (v - v0) / (v1 - v0) * (B - T)

    o = []
    said = []
    for v in range(-4, 4):
        cls = "timing-mid" if v == 0 else "timing-grid"
        o.append(f'                <line class="{cls}" x1="{L}" x2="{R}" y1="{f(y(v))}" y2="{f(y(v))}" />')
        o.append(f'                <text class="timing-tick" x="{L - 8}" y="{f(y(v) + 4)}">{pct(v) if v else "0"}</text>')
    group = (R - L) / 4
    bw, gap = 24, 5
    for k in range(4):
        cx = L + group * (k + 0.5)
        o.append(f'                <text class="timing-cat" x="{f(cx)}" y="{B + 18}">{w["places"][k]}</text>')
        for n, (room, c) in enumerate(rooms):
            v = c[k] * 10
            x = cx + (n - 1) * (bw + gap) - bw / 2
            top, bot = (y(v), y(0)) if v >= 0 else (y(0), y(v))
            o.append(f'                <rect class="split-bar {room}" x="{f(x)}" y="{f(top)}" width="{bw}" height="{f(bot - top)}">'
                     f'<title>{w[room]}, {w["places"][k]}: {pct(v)}</title></rect>')
            ty = top - 5 if v >= 0 else bot + 12
            o.append(f'                <text class="timing-note" x="{f(x + bw / 2)}" y="{f(ty)}" text-anchor="middle">{pct(v)}</text>')
            said.append(f"{w[room]} {w['places'][k]} {pct(v).replace('&#8722;', '-')}")
    o.append(f'                <text class="timing-axis" x="{(L + R) // 2}" y="{B + 40}">{w["split_axis"]}</text>')
    return "\n".join([
        '            <figure class="timing-figure is-single tier-figure" id="edge-split-figure" aria-labelledby="edge-split-caption">',
        '              <div class="timing-plate">',
        f'                <p class="timing-title">{w["split_title"]}</p>',
        f'                <p class="timing-sub">{w["split_sub"]}</p>',
        f'                <p class="timing-legend"><span class="timing-key tier-ms">{w["jade"]}</span>'
        f'<span class="timing-key split-throne">{w["throne"]}</span><span class="timing-key tier-th">{w["houou"]}</span></p>',
        '                <div class="timing-plot">',
        f'              <svg viewBox="0 0 470 {B + 50}" role="img" aria-label="{w["aria_split"]}{"; ".join(said)}.">',
        *o,
        "              </svg>",
        "                </div>",
        "              </div>",
        f'              <figcaption id="edge-split-caption">{w["split_caption"].format(throne=sp["throne_tables"])}</figcaption>',
        "            </figure>",
    ])


def pace(data: dict, lang: str) -> str:
    w = WORDS[lang]
    rows = data["saint3_pace"]
    L, R, T, B = 58, 446, 30, 260
    s0, s1 = 2.50, 2.40
    p0, p1 = -4, 14

    def x(s: float) -> float:
        return L + (s0 - s) / (s0 - s1) * (R - L)

    def y(p: float) -> float:
        return B - (p - p0) / (p1 - p0) * (B - T)

    o = []
    for p in range(p0, p1 + 1, 2):
        cls = "timing-mid" if p == 0 else "timing-grid"
        o.append(f'                <line class="{cls}" x1="{L}" x2="{R}" y1="{f(y(p))}" y2="{f(y(p))}" />')
        o.append(f'                <text class="timing-tick" x="{L - 8}" y="{f(y(p) + 4)}">{pct(p) if p else "0"}</text>')
    for s in (2.50, 2.48, 2.46, 2.44, 2.42, 2.40):
        o.append(f'                <text class="timing-axis" x="{f(x(s))}" y="{B + 16}">{s:.2f}</text>')
    o.append(f'                <text class="timing-note is-end" x="{R}" y="{B + 32}">{w["stronger"]} &#8594;</text>')
    o.append(f'                <text class="timing-note is-start" x="{L - 50}" y="{T - 14}">{w["per_game"]}</text>')
    # the average 8-dan and the user, as vertical guides
    eight = 2.5 - data["eight_dan_holder_a"]
    you = data["you_scale"]["results"]
    for s, label in ((eight, w["eight"]), (you, w["you"])):
        o.append(f'                <line class="split-guide" x1="{f(x(s))}" x2="{f(x(s))}" y1="{T}" y2="{B}" />')
        o.append(f'                <text class="timing-note" x="{f(x(s))}" y="{T - 4}" text-anchor="middle">{label} {s:.2f}</text>')
    said = []
    for key, cls in (("jade_split", "jade"), ("houou_split", "houou")):
        pts = " ".join(f"{f(x(r['scale']))},{f(y(r[key]))}" for r in rows)
        o.append(f'                <polyline class="split-line {cls}" points="{pts}" />')
        # where the line crosses zero: the strength that starts to climb
        a, b = rows[0], rows[-1]
        slope = (b[key] - a[key]) / (b["scale"] - a["scale"])
        cross = a["scale"] - a[key] / slope
        o.append(f'                <circle class="split-cross {cls}" cx="{f(x(cross))}" cy="{f(y(0))}" r="4"><title>{cross:.3f}</title></circle>')
        at = next(r for r in rows if abs(r["scale"] - 2.40) < 1e-9)
        label = w["j_line"] if cls == "jade" else w["h_line"]
        o.append(f'                <text class="split-label {cls}" x="{R + 4}" y="{f(y(at[key]) + 4)}">{pct(at[key])}</text>')
        said.append(f"{label}: zero at {cross:.3f}, {at[key]:+.1f} at 2.40")
    o.append(f'                <text class="timing-axis" x="{(L + R) // 2}" y="{B + 50}">{w["pace_axis"]}</text>')
    pts = " / ".join(f"{p:+.0f}".replace("-", "&#8722;") for p in data["lines"]["Saint 3"]["points"])
    return "\n".join([
        '            <figure class="timing-figure is-single tier-figure" id="edge-pace-figure" aria-labelledby="edge-pace-caption">',
        '              <div class="timing-plate">',
        f'                <p class="timing-title">{w["pace_title"]}</p>',
        f'                <p class="timing-sub">{w["pace_sub"]}</p>',
        f'                <p class="timing-legend"><span class="timing-key tier-ms">{w["j_line"]}</span><span class="timing-key tier-th">{w["h_line"]}</span></p>',
        '                <div class="timing-plot">',
        f'              <svg viewBox="0 0 470 {B + 60}" role="img" aria-label="{w["aria_pace"]}{"; ".join(said)}.">',
        *o,
        "              </svg>",
        "                </div>",
        "              </div>",
        f'              <figcaption id="edge-pace-caption">{w["pace_caption"].format(pts=pts)}</figcaption>',
        "            </figure>",
    ])


def lines(data: dict, lang: str) -> str:
    w = WORDS[lang]
    body = []
    for key in ("Saint 1", "Saint 2", "Saint 3", "七段", "八段", "九段", "十段"):
        ln = data["lines"][key]
        j, h = 2.5 - ln["jade_split"]["a"], 2.5 - ln["houou_split"]["a"]
        cells = [f"{j:.3f}", f"{h:.3f}"]
        own = 0 if key.startswith("Saint") else 1  # the split the rank's own room really has
        cells[own] = f"<b>{cells[own]}</b>"
        move = h - j
        body.append(f'                  <tr><td>{w["ranks"][key]}</td><td>{cells[0]}</td><td>{cells[1]}</td>'
                    f'<td>{"0.000" if abs(move) < 5e-4 else f"{move:+.3f}".replace("-", "&#8722;")}</td></tr>')
    return "\n".join([
        '            <div class="guide-data-scroll">',
        '              <table class="guide-data edge-lines-table">',
        "                <thead>",
        "                  <tr>" + "".join(f"<th>{h}</th>" for h in w["th"]) + "</tr>",
        "                </thead>",
        "                <tbody>",
        *body,
        "                </tbody>",
        "              </table>",
        "            </div>",
    ])


RENDER = {"edge-split": split, "edge-pace": pace, "edge-lines": lines}


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
                sys.exit(f"{page.name}'s {part} does not match {DATA.name}; run scripts/build_edge_split.py")
            html = head + start + new + end + tail
        if not check:
            page.write_text(html, encoding="utf-8")
    print("checked" if check else "written")


if __name__ == "__main__":
    main()
