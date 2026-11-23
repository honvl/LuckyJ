#!/usr/bin/env python3
"""Draw chapter 53's figures and table from ``analysis/tier-ranking-2026-11-20.json`` (``mine_tier_ranking.py``).

Three pieces go into ``site/honver.html`` and, with Japanese labels, ``site/honver-ja.html``, each between its own
markers:

- ``tier-ladder``: Saint 2, Saint 3 and Celestial beside the Houou dans on one scale, the average placement against
  three average Saint 3s. Mahjong Soul tiers are dots with their 95% range. The Houou average is placed by Mortal
  (its range is the link's), each dan is a dot sized by its seats, and the line through the dans carries a 95% band.
- ``tier-table``: the same numbers as a table.
- ``tier-shares``: the finishing places each tier really took in its own room, as stacked bars.

``--check`` exits non-zero when a page and the data disagree.

    .venv/bin/python scripts/build_tier_ranking.py [--check]
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "tier-ranking-2026-11-20.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
PARTS = ("tier-bands", "tier-table", "tier-ladder")
DANS = ["七段", "八段", "九段", "十段", "天鳳"]
Z = 1.96

WORDS = {
    "en": {
        "ms": "Mahjong Soul", "th": "Tenhou, Houou room",
        "Saint 2": "Saint 2", "Saint 3": "Saint 3", "Celestial": "Celestial", "field": "Houou|average",
        "七段": "7-dan", "八段": "8-dan", "九段": "9-dan", "十段": "10-dan", "天鳳": "Tenhou-i",
        "bands_title": "What it takes to reach each rank",
        "bands_sub": ("Each bar is one site&#8217;s ladder. A band is the strength that gains rank points at the rank below "
                      "and stops gaining at this one, so it reaches the rank and goes no further. The scale is the average "
                      "placement that strength would take against three average Jade-room Saint 3s."),
        "below_ms": "Saint 1 and below", "below_th": "7-dan and below",
        "slide": "The Tenhou bar can slide this far as one piece",
        "aria_bands": "Strength needed to reach each rank, as average placement against three average Saint 3s. ",
        "reach": "{rank} from {v}",
        "caption_bands": ("Thresholds from each rank&#8217;s point schedule: Saint 1, 2 and 3 in the Jade room, 7-dan to "
                          "10-dan in the Houou room. The lines carry the Mahjong Soul thresholds across to the Tenhou bar."),
        "th_reach": "To reach it", "th_holder": "Average holder today", "none": "other room", "you": "You",
        "you_key": "You, by how often you play Mortal&#8217;s move",
        "lj": "LuckyJ", "lj_key": "LuckyJ, from its Tokujou results, with its 95% range",
        "split_title": "Where the edge lands (chapter 56)",
        "split_left": "Fewer fourths, as in Jade", "split_right": "Even, as in Houou",
        "split_own": "Each room&#8217;s own split",
        "split_own_text": "Each room&#8217;s own split: fewer fourths on the Mahjong Soul bar, even on the Tenhou bar.",
        "split_mix_text": "Both bars at one split, {pct}% of the way from Jade&#8217;s to Houou&#8217;s.",
        "split_where": "You, {you}: {ms} and {th}. LuckyJ, {lj}: {lj_th}.",
        "split_hint": "The dots are measured average places and do not depend on the split; the bands around them move.",
        "ladder_title": "Where the average holder of each rank sits today",
        "ladder_sub": ("The players who hold each rank now, on the same scale: their average placement against three "
                       "average Jade-room Saint 3s. Saint 3 itself is 2.50."),
        "key_ms": "Mahjong Soul tier, with its 95% range",
        "key_field": "Houou average, placed by Mortal, with the link&#8217;s 95% range",
        "key_dan": "One dan&#8217;s own results, sized by its games",
        "key_fit": "Line through the dans, with its 95% range",
        "axis": "Average placement against three average Saint 3s",
        "stronger": "stronger", "zero": "Saint 3 level",
        "aria_ladder": "Average placement against three average Saint 3s. ",
        "th_tier": "Tier", "th_place": "Average placement", "th_range": "95% range",
        "th_from": "Measured from",
        "from_ms": "{seats:,} {room} seats", "from_field": "Mortal, {seats:,} seats",
        "from_dan": "{seats:,} seats and the line", "jade": "Jade", "throne": "Throne",
        "shares_title": "The places each tier really took, in its own room",
        "shares_sub": ("Shares of first to fourth place. The rooms have different fields, so a bar only compares with "
                       "the bars of its own room: Saint 3 takes 28% firsts among Masters and 24% among Celestials."),
        "p1": "1st", "p2": "2nd", "p3": "3rd", "p4": "4th", "avg": "avg",
        "room_jade": "Jade room (Masters and Saints)", "room_throne": "Throne room (Saints and Celestials)",
        "room_houou": "Houou room (7-dan and up)",
        "aria_shares": "Shares of first and fourth place by tier in its own room. ",
        "caption_ladder": ("Mahjong Soul: {jade:,} Jade and {throne:,} Throne tables. Tenhou: {houou:,} Houou hanchan. "
                           "The Tenhou points as a group can move up or down by the Houou average&#8217;s range."),
    },
    "ja": {
        "ms": "雀魂", "th": "天鳳 鳳凰卓",
        "Saint 2": "雀聖2", "Saint 3": "雀聖3", "Celestial": "魂天", "field": "鳳凰卓|平均",
        "七段": "七段", "八段": "八段", "九段": "九段", "十段": "十段", "天鳳": "天鳳位",
        "bands_title": "各段位に届くのに必要な強さ",
        "bands_sub": "棒はそれぞれのサイトの段位の並び。帯は、一つ下の段位ではポイントが増え、その段位では増えなくなる強さの範囲で、その段位まで届いて止まる。目盛りは、その強さが玉の間の平均的な雀聖3三人と打ったときの平均順位。",
        "below_ms": "雀聖1以下", "below_th": "七段以下",
        "slide": "天鳳の棒は全体としてこの幅だけ上下しうる",
        "aria_bands": "各段位に届くのに必要な強さ（平均的な雀聖3三人との平均順位）。",
        "reach": "{rank}は{v}から",
        "caption_bands": "境目は各段位のポイント配分から求めた。雀聖1、2、3は玉の間、七段から十段は鳳凰卓。線は雀魂の境目を天鳳の棒まで延ばしたもの。",
        "th_reach": "届くには", "th_holder": "今の平均的な在籍者", "none": "別の卓", "you": "あなた",
        "you_key": "あなた（Mortalとの一致度から）",
        "lj": "LuckyJ", "lj_key": "LuckyJ（特上卓の成績から、95%範囲つき）",
        "split_title": "強さがどの順位に出るか（第56章）",
        "split_left": "4位を減らす（玉の間）", "split_right": "均等（鳳凰卓）",
        "split_own": "部屋ごとの出方",
        "split_own_text": "部屋ごとの出方：雀魂の棒は4位を減らす出方、天鳳の棒は均等な出方。",
        "split_mix_text": "両方の棒を一つの出方で。玉の間の出方から鳳凰卓の出方まで{pct}%の位置。",
        "split_where": "あなた（{you}）：{ms}、{th}。LuckyJ（{lj}）：{lj_th}。",
        "split_hint": "点は実際の平均順位なので出方では動かない。動くのはまわりの帯である。",
        "ladder_title": "各段位の今の平均的な在籍者の位置",
        "ladder_sub": "今その段位にいる人たちを同じ目盛りに置いた。玉の間の平均的な雀聖3三人との平均順位で、雀聖3自身は2.50である。",
        "key_ms": "雀魂の段位と95%範囲",
        "key_field": "鳳凰卓平均（Mortalで位置づけ）と接続の95%範囲",
        "key_dan": "各段位の実際の成績（点の大きさは対局数）",
        "key_fit": "段位を通る直線と95%範囲",
        "axis": "平均的な雀聖3三人との平均順位",
        "stronger": "強い", "zero": "雀聖3の水準",
        "aria_ladder": "平均的な雀聖3三人との平均順位。",
        "th_tier": "段位", "th_place": "平均順位", "th_range": "95%範囲", "th_from": "根拠",
        "from_ms": "{room}の間 {seats:,}席", "from_field": "Mortal、鳳凰卓 {seats:,}席",
        "from_dan": "{seats:,}席と直線", "jade": "玉", "throne": "王座",
        "shares_title": "各段位が自分の卓で実際に取った順位",
        "shares_sub": "1位から4位の割合。部屋ごとに相手が違うので、棒は同じ部屋の棒とだけ比べられる。雀聖3は雀豪相手なら1位28%、魂天相手なら24%である。",
        "p1": "1位", "p2": "2位", "p3": "3位", "p4": "4位", "avg": "平均",
        "room_jade": "玉の間（雀豪と雀聖）", "room_throne": "王座の間（雀聖と魂天）", "room_houou": "鳳凰卓（七段以上）",
        "aria_shares": "各段位の自分の卓での1位率と4位率。",
        "caption_ladder": "雀魂は玉の間{jade:,}卓と王座の間{throne:,}卓、天鳳は鳳凰卓{houou:,}半荘。天鳳側の点は全体として、鳳凰卓平均の範囲だけ上下に動きうる。",
    },
}


def name(w: dict, key: str) -> str:
    return w[key].replace("|", " ") if w is WORDS["en"] else w[key].replace("|", "")


def f(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def place(a: float) -> str:
    return f"{2.5 - a:.2f}"


def rows(data: dict) -> list[dict]:
    """The nine things on the chart, in order, on the common scale."""
    ms, th, link = data["mahjong_soul"], data["tenhou_on_the_scale"], data["link"]["policy"]
    out = []
    for name in ("Saint 2", "Saint 3", "Celestial"):
        t = ms["tiers"][name]
        out.append({"key": name, "side": "ms", "a": t["a"], "lo": t["a"] - Z * t["se"], "hi": t["a"] + Z * t["se"],
                    "seats": t["seats"], "room": "throne" if name == "Celestial" else "jade"})
    seats = sum(th[d]["seats"] for d in DANS)
    out.append({"key": "field", "side": "th", "a": link["field_a"], "lo": link["field_a"] - Z * link["field_a_se"],
                "hi": link["field_a"] + Z * link["field_a_se"], "seats": seats})
    for d in DANS:
        t = th[d]
        out.append({"key": d, "side": "th", "a": t["a_fit"], "lo": t["a_fit"] - Z * t["se_fit"],
                    "hi": t["a_fit"] + Z * t["se_fit"], "raw": t["a"], "seats": t["seats"]})
    return out


def ladder(data: dict, lang: str) -> str:
    w = WORDS[lang]
    rs = rows(data)
    L, R, T, B = 58, 458, 46, 300
    lo = min(min(r["lo"], r.get("raw", r["lo"])) for r in rs if r["key"] != "天鳳")
    hi = max(r["hi"] for r in rs)
    a0, a1 = (int(lo / 0.04) - 1) * 0.04, (int(hi / 0.04) + 1) * 0.04
    xs = dict(zip([r["key"] for r in rs], [88, 136, 184, 252, 296, 331, 366, 402, 446]))

    def y(a: float) -> str:
        return f(B - (a - a0) / (a1 - a0) * (B - T))

    said = "; ".join(f"{name(w, r['key'])} {place(r['a'])}" for r in rs)
    o = [f'              <svg viewBox="0 0 470 356" role="img" aria-label="{w["aria_ladder"]}{said}.">']
    k = round(a0 / 0.04)
    while k * 0.04 <= a1 + 1e-9:
        a = k * 0.04
        cls = "timing-mid" if k == 0 else "timing-grid"
        o.append(f'                <line class="{cls}" x1="{L}" x2="{R}" y1="{y(a)}" y2="{y(a)}" />')
        o.append(f'                <text class="timing-tick" x="{L - 8}" y="{f(float(y(a)) + 4)}">{place(a)}</text>')
        k += 1
    o.append(f'                <line class="timing-grid" x1="220" x2="220" y1="{T - 22}" y2="{B}" />')
    o.append(f'                <text class="timing-label" x="136" y="{T - 22}">{w["ms"]}</text>')
    o.append(f'                <text class="timing-label" x="352" y="{T - 22}">{w["th"]}</text>')
    o.append(f'                <text class="timing-note is-end" x="{R}" y="{f(float(y(0)) + 13)}">{w["zero"]}</text>')
    o.append(f'                <text class="timing-note is-end" x="{L - 8}" y="{T - 22}">&#8593; {w["stronger"]}</text>')
    for r in rs:
        x, lines = xs[r["key"]], w[r["key"]].split("|")
        if len(lines) == 1:
            o.append(f'                <text class="timing-cat" x="{x}" y="{B + 18}">{lines[0]}</text>')
        else:
            o.append(f'                <text class="timing-cat" x="{x}" y="{B + 18}"><tspan x="{x}">{lines[0]}</tspan><tspan x="{x}" dy="13">{lines[1]}</tspan></text>')
    o.append(f'                <text class="timing-axis" x="{(L + R) // 2}" y="{B + 50}">{w["axis"]}</text>')
    dans = [r for r in rs if r["key"] in DANS]
    band = " ".join(f"{xs[r['key']]},{y(r['hi'])}" for r in dans) + " " + \
        " ".join(f"{xs[r['key']]},{y(r['lo'])}" for r in reversed(dans))
    o.append(f'                <polygon class="tier-band" points="{band}" />')
    o.append('                <polyline class="tier-fit" points="' + " ".join(f"{xs[r['key']]},{y(r['a'])}" for r in dans) + '" />')
    for r in rs:
        x = xs[r["key"]]
        tip = f"{name(w, r['key'])}: {place(r['a'])} ({place(r['hi'])} to {place(r['lo'])})" if lang == "en" else \
            f"{name(w, r['key'])}: {place(r['a'])}（{place(r['hi'])}〜{place(r['lo'])}）"
        if r["key"] in DANS:
            if r["key"] != "天鳳":  # 74 seats: its own point is off the chart and says nothing alone
                radius = max(2.0, min(6.5, (r["seats"] / 38000) ** 0.5 * 6.5))
                o.append(f'                <circle class="tier-dot th" cx="{x}" cy="{y(r["raw"])}" r="{f(radius)}"><title>{tip}</title></circle>')
            o.append(f'                <text class="timing-note" x="{x}" y="{f(float(y(r["hi"])) - 6)}" text-anchor="middle">{place(r["a"])}</text>')
            continue
        side = r["side"] if r["key"] != "field" else "field"
        if r["hi"] - r["lo"] > 1e-9:
            o.append(f'                <line class="tier-whisker {side}" x1="{x}" x2="{x}" y1="{y(r["lo"])}" y2="{y(r["hi"])}" />')
            for end in ("lo", "hi"):
                o.append(f'                <line class="tier-whisker {side}" x1="{x - 4}" x2="{x + 4}" y1="{y(r[end])}" y2="{y(r[end])}" />')
        o.append(f'                <circle class="tier-dot {side}" cx="{x}" cy="{y(r["a"])}" r="5"><title>{tip}</title></circle>')
        o.append(f'                <text class="timing-note" x="{x}" y="{f(float(y(r["hi"])) - 6)}" text-anchor="middle">{place(r["a"])}</text>')
    o.append("              </svg>")
    t = data["mahjong_soul"]["tables"]
    cap = w["caption_ladder"].format(jade=t["jade"], throne=t["throne"], houou=data["houou"]["tables"])
    return "\n".join([
        '            <figure class="timing-figure is-single tier-figure" id="tier-ladder-figure" aria-labelledby="tier-ladder-caption">',
        '              <div class="timing-plate">',
        f'                <p class="timing-title">{w["ladder_title"]}</p>',
        f'                <p class="timing-sub">{w["ladder_sub"]}</p>',
        f'                <p class="timing-legend"><span class="timing-key tier-ms">{w["key_ms"]}</span><span class="timing-key tier-field">{w["key_field"]}</span>'
        f'<span class="timing-key tier-th">{w["key_dan"]}</span><span class="timing-key tier-fitkey">{w["key_fit"]}</span></p>',
        '                <div class="timing-plot">',
        *o,
        "                </div>",
        "              </div>",
        f'              <figcaption id="tier-ladder-caption">{cap}</figcaption>',
        "            </figure>",
    ])


def bands(data: dict, lang: str) -> str:
    w = WORDS[lang]
    b = data["bands"]
    link = data["link"]["policy"]
    L, R, T, B = 58, 458, 44, 374
    a0, a1 = -0.08, 0.24
    cols = {"ms": (100, 200), "th": (262, 362)}

    def y(a: float) -> float:
        return B - (a - a0) / (a1 - a0) * (B - T)

    said = []
    o = []
    k = round(a0 / 0.04)
    while k * 0.04 <= a1 + 1e-9:
        a = k * 0.04
        o.append(f'                <line class="timing-grid" x1="{L}" x2="{R}" y1="{f(y(a))}" y2="{f(y(a))}" />')
        o.append(f'                <text class="timing-tick" x="{L - 8}" y="{f(y(a) + 4)}">{place(a)}</text>')
        k += 1
    o.append(f'                <text class="timing-note is-end" x="{L - 8}" y="{T - 22}">&#8593; {w["stronger"]}</text>')
    o.append(f'                <text class="timing-label" x="150" y="{T - 22}">{w["ms"]}</text>')
    o.append(f'                <text class="timing-label" x="312" y="{T - 22}">{w["th"].split(",")[0].split(" ")[0]}</text>')
    bounds = {"ms": [None, "Saint 1", "Saint 2", "Saint 3", None], "th": [None, "七段", "八段", "九段", "十段", None]}
    band_names = {}
    for side, key in (("ms", "mahjong_soul"), ("th", "tenhou")):
        x0, x1 = cols[side]
        segs = list(b[key])
        if side == "ms":
            segs = [{"rank": "below_ms", "from": None, "to": segs[0]["from"]}] + segs
        else:
            segs[0] = {**segs[0], "rank": "below_th"}
        for n, seg in enumerate(segs):
            lo = a0 if seg["from"] is None else seg["from"]
            hi = a1 if seg["to"] is None else seg["to"]
            top, bot = y(hi), y(lo)
            label = name(w, seg["rank"]) if seg["rank"] in w else seg["rank"]
            band_names.setdefault(side, []).append(label)
            tip = label if seg["from"] is None else w["reach"].format(rank=label, v=place(seg["from"]))
            lo_key, hi_key = bounds[side][n] or "", bounds[side][n + 1] or ""
            keys = f'data-side="{side}" data-lo="{lo_key}" data-hi="{hi_key}"'
            o.append(f'                <rect class="tier-rank {side}{n}" {keys} x="{x0}" y="{f(top + 1)}" width="{x1 - x0}" height="{f(bot - top - 2)}"><title>{tip}</title></rect>')
            hidden = "" if bot - top >= 15 else ' visibility="hidden"'
            o.append(f'                <text class="tier-rank-label {side}{n}" {keys} x="{(x0 + x1) // 2}" y="{f((top + bot) / 2 + 4)}"{hidden}>{label}</text>')
            if seg["from"] is not None:
                edge, anchor = (x0 - 6, "is-end") if side == "ms" else (x1 + 6, "is-start")
                o.append(f'                <text class="timing-note {anchor}" data-line="{lo_key}" x="{edge}" y="{f(bot + 4)}">{place(seg["from"])}</text>')
                said.append(w["reach"].format(rank=label, v=place(seg["from"])))
                if side == "ms":
                    o.append(f'                <line class="tier-cross" data-line="{lo_key}" x1="{x1}" x2="{cols["th"][0]}" y1="{f(bot)}" y2="{f(bot)}" />')
    # the user, by Mortal agreement on the same line that places the Houou average
    you = data["you"]["a_from_mortal"]
    x0, x1 = cols["ms"]
    o.append(f'                <circle class="tier-you" cx="{x1 - 12}" cy="{f(y(you))}" r="4"><title>{w["you"]}: {place(you)}</title></circle>')
    o.append(f'                <text class="tier-you-label" x="{x1 - 21}" y="{f(y(you) + 4)}">{w["you"]} {place(you)}</text>')
    # LuckyJ, from its own Tokujou results against opponents Mortal places, on the Tenhou bar
    lj = data.get("luckyj")
    if lj:
        x0, x1 = cols["th"]
        xl = x1 - 14
        lo, hi = lj["a"] - Z * lj["se"], lj["a"] + Z * lj["se"]
        o.append(f'                <line class="tier-whisker lj" x1="{xl}" x2="{xl}" y1="{f(y(lo))}" y2="{f(y(hi))}" />')
        for v in (lo, hi):
            o.append(f'                <line class="tier-whisker lj" x1="{xl - 4}" x2="{xl + 4}" y1="{f(y(v))}" y2="{f(y(v))}" />')
        o.append(f'                <circle class="tier-lj" cx="{xl}" cy="{f(y(lj["a"]))}" r="4.5"><title>{w["lj"]}: {place(lj["a"])} ({place(hi)}&#8211;{place(lo)})</title></circle>')
        o.append(f'                <text class="tier-you-label" x="{xl - 9}" y="{f(y(lj["a"]) + 4)}">{w["lj"]} {place(lj["a"])}</text>')
    # how far the Tenhou bar can slide: the link's 95% range, drawn at the Houou average
    xb = 414
    lo, hi = link["field_a"] - Z * link["field_a_se"], link["field_a"] + Z * link["field_a_se"]
    o.append(f'                <line class="tier-whisker field" x1="{xb}" x2="{xb}" y1="{f(y(lo))}" y2="{f(y(hi))}" />')
    for v in (lo, hi):
        o.append(f'                <line class="tier-whisker field" x1="{xb - 4}" x2="{xb + 4}" y1="{f(y(v))}" y2="{f(y(v))}" />')
    o.append(f'                <circle class="tier-dot field" cx="{xb}" cy="{f(y(link["field_a"]))}" r="4"><title>{name(w, "field")}: {place(link["field_a"])}</title></circle>')
    lines = w["field"].split("|")
    o.append(f'                <text class="timing-note" x="{xb}" y="{f(y(hi) - 20)}" text-anchor="middle"><tspan x="{xb}">{lines[0]}</tspan><tspan x="{xb}" dy="12">{lines[1]}</tspan></text>')
    o.append(f'                <text class="timing-axis" x="{(L + R) // 2}" y="{B + 22}">{w["axis"]}</text>')
    head = f'              <svg viewBox="0 0 470 {B + 30}" role="img" aria-label="{w["aria_bands"]}{"; ".join(said)}.">'
    control = split_control(data, w, bounds, band_names, (a0, a1, T, B))
    return "\n".join([
        '            <figure class="timing-figure is-single tier-figure" id="tier-bands-figure" aria-labelledby="tier-bands-caption">',
        '              <div class="timing-plate">',
        f'                <p class="timing-title">{w["bands_title"]}</p>',
        f'                <p class="timing-sub">{w["bands_sub"]}</p>',
        f'                <p class="timing-legend"><span class="timing-key tier-ms">{w["ms"]}</span><span class="timing-key tier-th">{w["th"].split(",")[0].split(" ")[0]}</span>'
        f'<span class="timing-key tier-field">{w["slide"]}</span><span class="timing-key tier-youkey">{w["you_key"]}</span>'
        + (f'<span class="timing-key tier-ljkey">{w["lj_key"]}</span>' if data.get("luckyj") else "") + '</p>',
        '                <div class="timing-plot">',
        head,
        *o,
        "              </svg>",
        "                </div>",
        *control,
        "              </div>",
        f'              <figcaption id="tier-bands-caption">{w["caption_bands"]}</figcaption>',
        "            </figure>",
    ])


def split_lines(data: dict, lam: dict) -> dict:
    """Each rank's line on the scale when an edge splits as ``(1 - lam) * Jade + lam * Houou`` (chapter 56)."""
    ms, th, link = data["mahjong_soul"], data["houou"], data["link"]["policy"]
    J, H = ms["share_slopes"]["jade"], th["share_slopes"]
    out = {}
    for key, side, base, pts in ([(n, "ms", ms["to_pass"][n]["jade"]["opponents"], ms["rank_points"]["12"][n]) for n in ("Saint 1", "Saint 2", "Saint 3")]
                                 + [(d, "th", link["field_a"] + th["opponents_vs_field"][d], th["rank_points"][d]) for d in DANS[:4]]):
        c = [(1 - lam[side]) * j + lam[side] * h for j, h in zip(J, H)]
        out[key] = {"side": side, "base": base, "points": pts, "a": base - 0.25 * sum(pts) / sum(x * p for x, p in zip(c, pts))}
    return out


def band_of(a: float, side: str, lines: dict, bounds: dict, names: dict) -> str:
    ks = bounds[side]
    for n in range(len(ks) - 1):
        lo = -1e9 if ks[n] is None else lines[ks[n]]["a"]
        hi = 1e9 if ks[n + 1] is None else lines[ks[n + 1]]["a"]
        if lo <= a < hi:
            return names[side][n]
    return names[side][-1]


def split_control(data: dict, w: dict, bounds: dict, names: dict, frame: tuple) -> list[str]:
    """A slider that redraws the bands for one split on both bars (site/honver.js), with the numbers it needs."""
    own = split_lines(data, {"ms": 0.0, "th": 1.0})
    you, lj = data["you"]["a_from_mortal"], data["luckyj"]["a"]
    where = w["split_where"].format(you=place(you), ms=band_of(you, "ms", own, bounds, names), th=band_of(you, "th", own, bounds, names),
                                    lj=place(lj), lj_th=band_of(lj, "th", own, bounds, names))
    ms, th = data["mahjong_soul"], data["houou"]
    payload = {"J": ms["share_slopes"]["jade"], "H": th["share_slopes"], "own": {"ms": 0, "th": 1},
               "lines": {k: {"side": v["side"], "base": round(v["base"], 5), "points": v["points"]} for k, v in own.items()},
               "bounds": bounds, "names": names, "frame": dict(zip(("a0", "a1", "T", "B"), frame)),
               "you": you, "lj": lj, "reach": w["reach"],
               "words": {k: w[k] for k in ("split_own_text", "split_mix_text", "split_where")}}
    payload["words"] = {k: html.unescape(v) for k, v in payload["words"].items()}  # the script sets textContent
    payload["names"] = {k: [html.unescape(n) for n in v] for k, v in payload["names"].items()}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return [
        '                <div class="tier-split">',
        f'                  <p class="tier-split-title">{w["split_title"]}</p>',
        f'                  <div class="tier-split-row"><span class="tier-split-end">{w["split_left"]}</span>'
        f'<input class="tier-split-range" type="range" min="0" max="100" step="5" value="0" aria-label="{w["split_title"]}" />'
        f'<span class="tier-split-end">{w["split_right"]}</span></div>',
        f'                  <div class="tier-split-row"><button type="button" class="tier-split-own" aria-pressed="true">{w["split_own"]}</button>'
        f'<output class="tier-split-readout" aria-live="polite">{w["split_own_text"]} {where}</output></div>',
        f'                  <p class="tier-split-hint">{w["split_hint"]}</p>',
        f'                  <script type="application/json" class="tier-split-data">{text}</script>',
        "                </div>",
    ]


def table(data: dict, lang: str) -> str:
    w = WORDS[lang]
    reach = {seg["rank"]: seg["from"] for key in ("mahjong_soul", "tenhou") for seg in data["bands"][key]}
    body = []
    for r in rows(data):
        if r["key"] == "field":
            continue
        need = w["none"] if reach.get(r["key"]) is None else place(reach[r["key"]])
        rng = "2.50" if r["key"] == "Saint 3" else f"{place(r['hi'])} to {place(r['lo'])}" if lang == "en" else f"{place(r['hi'])}〜{place(r['lo'])}"
        body.append(f'                  <tr><td>{name(w, r["key"])}</td><td>{need}</td><td>{place(r["a"])}</td><td>{rng}</td></tr>')
    return "\n".join([
        '            <div class="guide-data-scroll">',
        '              <table class="guide-data tier-table">',
        "                <thead>",
        f'                  <tr><th>{w["th_tier"]}</th><th>{w["th_reach"]}</th><th>{w["th_holder"]}</th><th>{w["th_range"]}</th></tr>',
        "                </thead>",
        "                <tbody>",
        *body,
        "                </tbody>",
        "              </table>",
        "            </div>",
    ])


RENDER = {"tier-bands": bands, "tier-table": table, "tier-ladder": ladder}


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
                sys.exit(f"{page.name}'s {part} does not match {DATA.name}; run scripts/build_tier_ranking.py")
            html = head + start + new + end + tail
        if not check:
            page.write_text(html, encoding="utf-8")
    print("checked" if check else "written")


if __name__ == "__main__":
    main()
