#!/usr/bin/env python3
"""Draw the personal guide's chapter 22 figure from ``analysis/fold-motives-2026-09-29.json``.

Five small panels in the book's dumbbell style (the "Against the humans" figure in points.html): each
splits the costly turns against one riichi two ways and shows, for you and for LuckyJ, the extra folds
beyond Mortal's rate on the same turns in the first situation (hollow dot) and the second (filled dot).
A thin mark shows zero, folding exactly as often as Mortal. A folded table gives the numbers with one
standard error of each change. The figure is plain HTML, written into ``site/honver.html`` and, with
Japanese words, ``site/honver-ja.html`` between the ``fold-motives-figure`` markers. ``--check`` exits
non-zero when a page and the data disagree.

usage: build_fold_motives_figure.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "fold-motives-2026-09-29.json"
PAGES = {"en": ROOT / "site" / "honver.html", "ja": ROOT / "site" / "honver-ja.html"}
START = "<!-- fold-motives-figure -->"
END = "<!-- /fold-motives-figure -->"
TESTS = ("threat_dealer", "prev_dealt", "south", "dora", "me_dealer")
SCALE = (-8.0, 14.0)  # extra folds per 100 turns, the track's left and right ends
MINUS = "&#8722;"
ARROW = "&#8594;"

TEXT = {
    "en": {
        "title": "What moves your extra folds against a riichi",
        "panels": {
            "threat_dealer": ("Their hand", f"a child&#8217;s riichi {ARROW} a dealer&#8217;s"),
            "prev_dealt": ("Your last hand", f"no deal-in {ARROW} a deal-in"),
            "south": ("The round", f"East {ARROW} South"),
            "dora": ("Your dora", f"none {ARROW} two or more"),
            "me_dealer": ("Your seat", f"child {ARROW} dealer"),
        },
        "you": "You",
        "lj": "LuckyJ",
        "read_title": "How to read it",
        "read": "Each row runs from the hollow dot, the first situation, to the filled one, the second. The thin mark "
                "is zero: folding exactly as often as Mortal on the same turns. Right of it, more folds than Mortal.",
        "key_first": "first situation",
        "key_second": "second situation",
        "caption": "Extra folds: on costly turns against one riichi, where every safe tile leaves the hand a shanten short "
                   "of the best hand the draw allows, how many more times in 100 the player threw the safe tile than "
                   "Mortal would have on the same turns. Your {you:,} turns in {you_games} games since January; LuckyJ&#8217;s "
                   "{lj:,} in its {lj_games:,} Tokujou games. The scale runs from {lo} to +{hi}.",
        "table_summary": "The numbers, with one standard error of each change",
        "table_split": "Split",
        "table_first": "First",
        "table_second": "Second",
        "table_change": "Change",
    },
    "ja": {
        "title": "リーチに対するあなたの余分なオリを動かすもの",
        "panels": {
            "threat_dealer": ("相手の手", f"子のリーチ {ARROW} 親のリーチ"),
            "prev_dealt": ("直前の局", f"放銃なし {ARROW} 放銃あり"),
            "south": ("場", f"東場 {ARROW} 南場"),
            "dora": ("自分のドラ", f"なし {ARROW} 2枚以上"),
            "me_dealer": ("自分の席", f"子 {ARROW} 親"),
        },
        "you": "あなた",
        "lj": "LuckyJ",
        "read_title": "読み方",
        "read": "各行は、白抜きの点（前の状況）から塗りつぶした点（後の状況）へ動く。細い線は0で、同じ巡目のMortalと"
                "同じだけオリていることを表す。右ほど、Mortalより多くオリている。",
        "key_first": "前の状況",
        "key_second": "後の状況",
        "caption": "余分なオリ：リーチ1人を相手にした損な巡目（どの安全牌を切っても、このツモで届く最良の手より1シャンテン遠くなる"
                   "巡目）で、同じ巡目のMortalより何回多く安全牌を切ったか（100巡目あたり）。あなたは2026年1月以降の"
                   "{you_games}半荘で{you:,}巡目、LuckyJは特上卓{lj_games:,}半荘で{lj:,}巡目。目盛りは{lo}から+{hi}まで。",
        "table_summary": "数値と、各変化の標準誤差",
        "table_split": "分け方",
        "table_first": "前",
        "table_second": "後",
        "table_change": "変化",
    },
}


def whole(v: float) -> str:
    """A signed whole number, rounded half away from zero, with a real minus sign."""
    n = int(abs(v) + 0.5)
    if n == 0:
        return "0"
    return f"+{n}" if v > 0 else f"{MINUS}{n}"


def signed(v: float) -> str:
    return f"+{v:.1f}" if v > 0 else f"{MINUS}{abs(v):.1f}" if v < 0 else "0.0"


def plain(v: float) -> str:
    return f"{MINUS}{abs(v):.1f}" if v < 0 else f"{v:.1f}"


def left(v: float) -> str:
    lo, hi = SCALE
    if not lo <= v <= hi:
        raise ValueError(f"{v} is off the figure's scale {SCALE}")
    return f"{100 * (v - lo) / (hi - lo):.1f}%"


def dumbbell(who: str, cls: str, first: float, second: float) -> str:
    a, b = sorted((first, second))
    lo = SCALE[0]
    width = 100 * (b - a) / (SCALE[1] - lo)
    return (f'<div class="dumbbell is-{cls}"><span class="dumbbell-who">{who}</span><span class="dumbbell-track">'
            f'<span class="dumbbell-zero" style="left:{left(0.0)}"></span>'
            f'<span class="dumbbell-bar is-{cls}" style="left:{left(a)};width:{width:.1f}%"></span>'
            f'<span class="dumbbell-dot is-{cls}" style="left:{left(first)}"></span>'
            f'<span class="dumbbell-dot is-{cls} is-end" style="left:{left(second)}"></span></span>'
            f'<span class="dumbbell-change">{whole(first)} {ARROW} {whole(second)}</span></div>')


def panels(data: dict, lang: str) -> list[str]:
    t = TEXT[lang]
    out = []
    for key in TESTS:
        test = data["tests"]["riichi"][key]
        title, sub = t["panels"][key]
        rows = [dumbbell(t["you"], "you", test["You"]["b"]["extra"], test["You"]["a"]["extra"]),
                dumbbell(t["lj"], "lj", test["LuckyJ"]["b"]["extra"], test["LuckyJ"]["a"]["extra"])]
        body = "\n                ".join(rows)
        out.append(f'''<div class="contrast-panel">
                <p class="contrast-panel-title">{title}</p>
                <p class="contrast-panel-sub">{sub}</p>
                {body}
              </div>''')
    out.append(f'''<div class="contrast-panel motive-read">
                <p class="contrast-panel-title">{t["read_title"]}</p>
                <p class="contrast-panel-sub">{t["read"]}</p>
                <p class="contrast-panel-key"><span class="key-open"></span>{t["key_first"]} <span class="key-filled"></span>{t["key_second"]}</p>
              </div>''')
    return out


def table(data: dict, lang: str) -> str:
    t = TEXT[lang]
    rows = []
    for key in TESTS:
        test = data["tests"]["riichi"][key]
        cells = []
        for who in ("You", "LuckyJ"):
            e = test[who]
            cells.append(f'<td>{plain(e["b"]["extra"])}</td><td>{plain(e["a"]["extra"])}</td>'
                         f'<td>{signed(e["contrast"])} &#177; {e["se"]:.1f}</td>')
        title, sub = t["panels"][key]
        rows.append(f'<tr><th scope="row">{title}: {sub}</th>{"".join(cells)}</tr>')
    body = "\n                      ".join(rows)
    head_who = f'<th scope="col" colspan="3">{t["you"]}</th><th scope="col" colspan="3">{t["lj"]}</th>'
    head_cols = "".join(f'<th scope="col">{t[k]}</th>' for k in ("table_first", "table_second", "table_change")) * 2
    return f'''<details class="timing-table">
                <summary>{t["table_summary"]}</summary>
                <div class="timing-table-scroll">
                  <table>
                    <thead>
                      <tr><th scope="col" rowspan="2">{t["table_split"]}</th>{head_who}</tr>
                      <tr>{head_cols}</tr>
                    </thead>
                    <tbody>
                      {body}
                    </tbody>
                  </table>
                </div>
              </details>'''


def render(data: dict, lang: str) -> str:
    t = TEXT[lang]
    overall = data["overall"]["riichi"]
    caption = t["caption"].format(you=overall["You"]["turns"], you_games=data["games"]["You"], lj=overall["LuckyJ"]["turns"],
                                  lj_games=data["games"]["LuckyJ"], lo=f"{MINUS}{abs(SCALE[0]):.0f}", hi=f"{SCALE[1]:.0f}")
    body = "\n              ".join(panels(data, lang))
    return (
        f"{START}\n"
        '            <figure class="contrast-figure motive-figure" id="motive-figure" aria-labelledby="motive-figure-caption">\n'
        f'              <p class="motive-title">{t["title"]}</p>\n'
        '              <div class="contrast-panels">\n'
        f"              {body}\n"
        "              </div>\n"
        f'              <figcaption id="motive-figure-caption">{caption}</figcaption>\n'
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
                sys.exit(f"{name}'s chapter 22 figure does not match {DATA.relative_to(ROOT)}; run build_fold_motives_figure.py")
            print(f"{name}: chapter 22 figure matches")
            continue
        path.write_text(new, encoding="utf-8")
        print(f"wrote the chapter 22 figure into {name}")


if __name__ == "__main__":
    main()
