#!/usr/bin/env python3
"""Draw chapter 54's figures and table from ``analysis/throne-shift-2026-11-21.json`` (``mine_throne_shift.py``).

Three pieces go into ``site/honver.html`` and, with Japanese labels, ``site/honver-ja.html``, each between its own
markers:

- ``throne-steps``: two vertical stacked bars, the first-to-fourth spread of a Saint 3's points and of a
  Celestial's, cut into its three steps with the higher place nearer the top.
- ``throne-swing``: what one deal-in costs in wins of the same size, by the place held when the hand starts, under
  Saint 3 points and under Celestial points, for mangan-size and 3,900 hands.
- ``throne-field``: play statistics of the Jade field, the Throne field and the user.

``--check`` exits non-zero when a page and the data disagree.

    .venv/bin/python scripts/build_throne_shift.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "throne-shift-2026-11-21.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
PARTS = ("throne-steps", "throne-swing", "throne-field")

WORDS = {
    "en": {
        "s3": "Saint 3, Jade room", "cel": "Celestial, Throne room",
        "steps_title": "What each place is worth: the first-to-fourth spread, step by step",
        "steps_sub": ("Each bar is all the rank points between a first and a fourth. A band is one step, with the higher "
                      "place nearer the top. At Saint 3 most of the bar is the step out of fourth."),
        "step": ["1st over 2nd", "2nd over 3rd", "3rd over 4th"], "points": "{v} points", "spread": "1st to 4th: {v} points",
        "aria_steps": "Share of the first-to-fourth spread taken by each step. ",
        "steps_caption": ("Saint 3: average rank points by place in the Jade room, the score part included ({n:,} seats). "
                          "Celestial: +50, +20, &#8722;20, &#8722;50 by place alone, doubled when all four seats are "
                          "Celestials."),
        "swing_title": "What one deal-in costs, in wins of the same size",
        "swing_sub": ("By your place when the hand starts. Above 1.00 a deal-in costs more than a win gains. Each pair "
                      "is the same {n:,} positions from your games, scored with Saint 3 points and with Celestial points."),
        "key_s3": "Saint 3 points", "key_cel": "Celestial points", "even": "1.00: a win and a deal-in weigh the same",
        "size_8000": "Mangan-size hands (8,000)", "size_3900": "3,900 hands", "place": ["1st", "2nd", "3rd", "4th"],
        "swing_axis": "Your place when the hand starts",
        "aria_swing": "Cost of a deal-in in wins of the same size, Saint 3 points then Celestial points. ",
        "swing_caption": ("Every hand of your Jade games since January: you win the amount from each other seat in turn, and "
                          "deal it into each, and the game is finished {sims:,} times from there."),
        "th_stat": "A hundred hands", "th_jade": "Jade field", "th_throne": "Throne field", "th_you": "You, in Jade",
        "stat": {"win": "Hands won", "deal_in": "Hands dealt into", "riichi": "Riichi declared", "call": "Hands with a call",
                 "tsumo_share": "Wins that were tsumo", "draw": "Hands ending in a draw", "tenpai_at_draw": "Tenpai at the draw",
                 "riichi_win": "Riichis that won"},
    },
    "ja": {
        "s3": "雀聖3・玉の間", "cel": "魂天・王座の間",
        "steps_title": "各順位の価値：1位から4位までの幅を一段ずつ",
        "steps_sub": "棒は1位と4位のあいだの段位ポイントの全体。帯は一段分で、上ほど高い順位である。雀聖3では棒の大半が4位から抜ける一段である。",
        "step": ["1位と2位の差", "2位と3位の差", "3位と4位の差"], "points": "{v}ポイント", "spread": "1位から4位：{v}ポイント",
        "aria_steps": "1位から4位までの幅に占める各段の割合。",
        "steps_caption": "雀聖3：玉の間での順位別の平均段位ポイント（素点分を含む、{n:,}席）。魂天：順位だけで+50、+20、&#8722;20、&#8722;50。四人とも魂天の卓では2倍になる。",
        "swing_title": "放銃1回は、同じ大きさの和了何回分か",
        "swing_sub": "局が始まるときのあなたの順位ごと。1.00より上なら、放銃で失う分が和了で得る分より大きい。各組は同じ{n:,}局面を雀聖3のポイントと魂天のポイントで採点したもの。",
        "key_s3": "雀聖3のポイント", "key_cel": "魂天のポイント", "even": "1.00：和了と放銃が同じ重さ",
        "size_8000": "満貫級（8,000）", "size_3900": "3,900の手", "place": ["1位", "2位", "3位", "4位"],
        "swing_axis": "局が始まるときのあなたの順位",
        "aria_swing": "放銃1回が同じ大きさの和了何回分か。雀聖3のポイント、魂天のポイントの順。",
        "swing_caption": "1月以降の玉の間の全局面。あなたが他の三席それぞれからその点数を和了した場合と、それぞれに放銃した場合を作り、そこから半荘を{sims:,}回最後まで進めた。",
        "th_stat": "100局あたり", "th_jade": "玉の間の平均", "th_throne": "王座の間の平均", "th_you": "あなた（玉の間）",
        "stat": {"win": "和了した局", "deal_in": "放銃した局", "riichi": "立直した局", "call": "副露した局",
                 "tsumo_share": "和了のうちツモ", "draw": "流局した局", "tenpai_at_draw": "流局時の聴牌",
                 "riichi_win": "立直の和了率"},
    },
}


def f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def steps(data: dict, lang: str) -> str:
    w = WORDS[lang]
    pts = data["points"]
    bars = [("s3", pts["saint3"]["average"], pts["saint3"]["step_share_pct"]),
            ("cel", [float(v) for v in pts["celestial"]["schedule"]], pts["celestial"]["step_share_pct"])]
    T, B = 46, 300
    xs = {"s3": (70, 210), "cel": (260, 400)}
    o, said = [], []
    for key, avg, share in bars:
        x0, x1 = xs[key]
        o.append(f'                <text class="timing-label" x="{(x0 + x1) // 2}" y="{T - 16}">{w[key]}</text>')
        y = T
        for n in range(3):
            h = (B - T) * share[n] / 100
            pts_step = round(avg[n] - avg[n + 1])
            tip = f"{w[key]}: {w['step'][n]}, {w['points'].format(v=pts_step)}, {f(share[n])}%"
            o.append(f'                <rect class="tier-rank ms{3 - n}" x="{x0}" y="{f(y + 1)}" width="{x1 - x0}" height="{f(h - 2)}"><title>{tip}</title></rect>')
            mid = y + h / 2
            o.append(f'                <text class="tier-rank-label ms{3 - n}" x="{(x0 + x1) // 2}" y="{f(mid - 3)}">{w["step"][n]}</text>')
            o.append(f'                <text class="tier-rank-label ms{3 - n} is-figure" x="{(x0 + x1) // 2}" y="{f(mid + 12)}">{round(share[n])}% &#183; {w["points"].format(v=pts_step)}</text>')
            said.append(f"{w[key]} {w['step'][n]} {round(share[n])}%")
            y += h
        o.append(f'                <text class="timing-axis" x="{(x0 + x1) // 2}" y="{B + 18}">{w["spread"].format(v=round(avg[0] - avg[3]))}</text>')
    head = f'              <svg viewBox="0 0 470 {B + 28}" role="img" aria-label="{w["aria_steps"]}{"; ".join(said)}.">'
    return "\n".join([
        '            <figure class="timing-figure is-single tier-figure" id="throne-steps-figure" aria-labelledby="throne-steps-caption">',
        '              <div class="timing-plate">',
        f'                <p class="timing-title">{w["steps_title"]}</p>',
        f'                <p class="timing-sub">{w["steps_sub"]}</p>',
        '                <div class="timing-plot">',
        head,
        *o,
        "              </svg>",
        "                </div>",
        "              </div>",
        f'              <figcaption id="throne-steps-caption">{w["steps_caption"].format(n=pts["saint3"]["seats"])}</figcaption>',
        "            </figure>",
    ])


def swing(data: dict, lang: str) -> str:
    w = WORDS[lang]
    sw = data["swings"]
    L, R, T, B = 46, 458, 40, 250
    lo, hi = 0.6, 1.6

    def y(v: float) -> float:
        return B - (v - lo) / (hi - lo) * (B - T)

    o, said = [], []
    for k in range(6):
        v = lo + 0.2 * k
        cls = "timing-mid" if abs(v - 1.0) < 1e-9 else "timing-grid"
        o.append(f'                <line class="{cls}" x1="{L}" x2="{R}" y1="{f(y(v))}" y2="{f(y(v))}" />')
        o.append(f'                <text class="timing-tick" x="{L - 8}" y="{f(y(v) + 4)}">{v:.2f}</text>')
    o.append(f'                <line class="timing-grid" x1="252" x2="252" y1="{T - 20}" y2="{B}" />')
    for size, x_first, centre in (("8000", 76, 152), ("3900", 282, 355)):
        o.append(f'                <text class="timing-label" x="{centre}" y="{T - 18}">{w["size_" + size]}</text>')
        for n in range(4):
            cell = sw[size][str(n + 1)]
            a, b = cell["saint3"]["ratio"], cell["celestial"]["ratio"]
            x = x_first + n * 50
            o.append(f'                <line class="throne-move" x1="{x}" x2="{x}" y1="{f(y(a))}" y2="{f(y(b))}" />')
            tip = f"{w['place'][n]}: {a:.2f} &#8594; {b:.2f}"
            o.append(f'                <circle class="tier-dot throne-s3" cx="{x}" cy="{f(y(a))}" r="4.5"><title>{tip}</title></circle>')
            o.append(f'                <circle class="tier-dot ms" cx="{x}" cy="{f(y(b))}" r="4.5"><title>{tip}</title></circle>')
            up, down = (a, b) if a >= b else (b, a)
            o.append(f'                <text class="timing-note" x="{x}" y="{f(y(up) - 9)}" text-anchor="middle">{up:.2f}</text>')
            o.append(f'                <text class="timing-note" x="{x}" y="{f(y(down) + 17)}" text-anchor="middle">{down:.2f}</text>')
            o.append(f'                <text class="timing-cat" x="{x}" y="{B + 18}">{w["place"][n]}</text>')
            said.append(f"{w['size_' + size]} {w['place'][n]} {a:.2f}, {b:.2f}")
    o.append(f'                <text class="timing-axis" x="{(L + R) // 2}" y="{B + 38}">{w["swing_axis"]}</text>')
    head = f'              <svg viewBox="0 0 470 {B + 46}" role="img" aria-label="{w["aria_swing"]}{"; ".join(said)}.">'
    return "\n".join([
        '            <figure class="timing-figure is-single tier-figure" id="throne-swing-figure" aria-labelledby="throne-swing-caption">',
        '              <div class="timing-plate">',
        f'                <p class="timing-title">{w["swing_title"]}</p>',
        f'                <p class="timing-sub">{w["swing_sub"].format(n=data["positions"])}</p>',
        f'                <p class="timing-legend"><span class="timing-key throne-s3key">{w["key_s3"]}</span><span class="timing-key tier-ms">{w["key_cel"]}</span><span class="timing-key throne-even">{w["even"]}</span></p>',
        '                <div class="timing-plot">',
        head,
        *o,
        "              </svg>",
        "                </div>",
        "              </div>",
        f'              <figcaption id="throne-swing-caption">{w["swing_caption"].format(sims=data["finishes_each"])}</figcaption>',
        "            </figure>",
    ])


def field(data: dict, lang: str) -> str:
    w = WORDS[lang]
    fd = data["field"]
    body = []
    for key, label in w["stat"].items():
        cells = [fd["jade"][key]["mean"], fd["throne"][key]["mean"], fd["you_in_jade"][key]]
        body.append(f'                  <tr><td>{label}</td>' + "".join(f"<td>{v * 100:.1f}%</td>" for v in cells) + "</tr>")
    return "\n".join([
        '            <div class="guide-data-scroll">',
        '              <table class="guide-data throne-field">',
        "                <thead>",
        f'                  <tr><th>{w["th_stat"]}</th><th>{w["th_jade"]}</th><th>{w["th_throne"]}</th><th>{w["th_you"]}</th></tr>',
        "                </thead>",
        "                <tbody>",
        *body,
        "                </tbody>",
        "              </table>",
        "            </div>",
    ])


RENDER = {"throne-steps": steps, "throne-swing": swing, "throne-field": field}


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
                sys.exit(f"{page.name}'s {part} does not match {DATA.name}; run scripts/build_throne_shift.py")
            html = head + start + new + end + tail
        if not check:
            page.write_text(html, encoding="utf-8")
    print("checked" if check else "written")


if __name__ == "__main__":
    main()
