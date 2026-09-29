#!/usr/bin/env python3
"""Draw the personal guide's caller grid (chapter 18) from ``analysis/caller-surface-2026-09-29.json``.

The grid is a heat table: one row per number of calls and run of tiles drawn and thrown, one column per
discard the caller has made, each cell the fitted share of those callers who could win off a discard
(tenpai with a yaku). It is written into ``site/honver.html`` between the ``caller-surface`` markers;
``--check`` exits non-zero when the page and the data disagree.

usage: build_caller_surface.py [--check]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "analysis" / "caller-surface-2026-09-29.json"
PAGE = ROOT / "site" / "honver.html"
START = "<!-- caller-surface -->"
END = "<!-- /caller-surface -->"
MAX_DISCARD = 18
ROW_START = ' class="cs-row-start"'
CALL_LABELS = {1: "One call", 2: "Two calls", 3: "Three or four calls"}
RUN_LABELS = {0: "last tile from hand", 1: "last one from the wall", 2: "two in a row from the wall", 3: "three or more from the wall"}
# paper to deep vermilion, the site's tokens
LOW = (0xF4, 0xF0, 0xE6)
MID = (0xF5, 0xA5, 0x83)
HIGH = (0x8E, 0x2A, 0x15)


def shade(pct: float) -> str:
    """Background colour for a share: paper at 0, the vermilion felt at 50, deep vermilion at 100."""
    x = max(0.0, min(1.0, pct / 100))
    a, b, t = (LOW, MID, x / 0.5) if x <= 0.5 else (MID, HIGH, (x - 0.5) / 0.5)
    rgb = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return "#%02x%02x%02x" % rgb


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def text_for(background: str) -> str:
    """White or the page ink, whichever reads better on this square."""
    bg = _luminance(background)
    white = 1.05 / (bg + 0.05)
    ink = (bg + 0.05) / (_luminance("#1e1a14") + 0.05)
    return "#fff" if white > ink else "var(--ink)"


def value(cell: dict, minimum: int) -> float | None:
    if "fit" in cell:
        return cell["fit"]
    if cell["n"] >= minimum and cell["raw"] is not None:
        return cell["raw"]
    return None


def render(data: dict) -> str:
    grid = data["grid"]["can_win"]
    minimum = data["min_readings"]
    head_rows = (
        '<tr><th class="cs-corner" rowspan="2" scope="col">Calls, and their latest discards</th>'
        '<th class="cs-group" colspan="6" scope="colgroup">First row</th>'
        '<th class="cs-group" colspan="6" scope="colgroup">Second row</th>'
        '<th class="cs-group" colspan="6" scope="colgroup">Third row</th></tr>'
        "<tr>" + "".join(f'<th scope="col"{ROW_START if d in (7, 13) else ""}>{d}</th>' for d in range(1, MAX_DISCARD + 1)) + "</tr>"
    )
    body = []
    for calls in (1, 2, 3):
        body.append(f'<tr class="cs-calls"><th scope="rowgroup" colspan="{MAX_DISCARD + 1}">{CALL_LABELS[calls]}</th></tr>')
        for run in (0, 1, 2, 3):
            cells = grid[f"{calls}-{run}"]["cells"]
            tds = []
            for d in range(1, MAX_DISCARD + 1):
                v = value(cells[str(d)], minimum)
                classes = (["cs-row-start"] if d in (7, 13) else []) + (["cs-empty"] if v is None else [])
                attr = f' class="{" ".join(classes)}"' if classes else ""
                if v is None:
                    tds.append(f"<td{attr}></td>")
                    continue
                tds.append(f'<td{attr} style="background:{shade(v)};color:{text_for(shade(v))}">{round(v)}</td>')
            body.append(f'<tr><th scope="row">{RUN_LABELS[run]}</th>{"".join(tds)}</tr>')
    legend = "".join(f'<span style="background:{shade(p)};color:{text_for(shade(p))}">{p}%</span>' for p in (0, 10, 25, 50, 75, 90))
    return (
        f"{START}\n"
        '            <figure class="caller-surface">\n'
        '              <div class="guide-data-scroll">\n'
        f'                <table class="cs-grid"><thead>{head_rows}</thead><tbody>{"".join(body)}</tbody></table>\n'
        "              </div>\n"
        f'              <figcaption><span class="cs-legend">{legend}</span> Share of callers who could win off your '
        "discard (tenpai with a yaku), after their discard number at the top, in LuckyJ&#8217;s games. A blank "
        f"square has fewer than {minimum} readings.</figcaption>\n"
        "            </figure>\n"
        f"            {END}"
    )


def main() -> None:
    data = json.loads(DATA.read_text())
    page = PAGE.read_text(encoding="utf-8")
    start, end = page.index(START), page.index(END) + len(END)
    new = page[:start] + render(data) + page[end:]
    if "--check" in sys.argv:
        if new != page:
            sys.exit("site/honver.html's caller grid does not match analysis/caller-surface-2026-09-29.json; run build_caller_surface.py")
        print("caller grid matches")
        return
    PAGE.write_text(new, encoding="utf-8")
    print("wrote the caller grid into site/honver.html")


if __name__ == "__main__":
    main()
