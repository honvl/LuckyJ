#!/usr/bin/env python3
"""Render the site's bitmap icons from site/favicon.svg.

Browsers that read SVG icons use site/favicon.svg directly. This script draws the two fallbacks
the pages also link:

  site/favicon.ico           16, 32 and 48 px frames of the tile, on a transparent ground, for
                             browsers without SVG favicons
  site/apple-touch-icon.png  180 px, the tile standing on the cover's felt, for iOS home screens
                             (iOS fills a transparent icon with black, so this one is opaque)

On the felt the tile shows a pale bone back, as the running head's mark does over the cover.

Headless Chrome does the drawing so the bitmaps match what a browser renders. Set CHROME to its
path if it is not in the default macOS location.

usage: build_favicons.py
"""

from __future__ import annotations

import base64
import os
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "site/favicon.svg"
ICO = ROOT / "site/favicon.ico"
TOUCH = ROOT / "site/apple-touch-icon.png"
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

ICO_SIZES = (16, 32, 48)
TOUCH_SIZE = 180
FELT_BG = "radial-gradient(120% 95% at 38% 42%, #1a5842 0%, #134834 52%, #0f3c2b 100%)"
FELT_BACK = ("#134834", "#c3cbbf")


def data_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def screenshot(page: str, width: int, height: int) -> Image.Image:
    with tempfile.TemporaryDirectory() as tmp:
        html_file = Path(tmp) / "page.html"
        png_file = Path(tmp) / "shot.png"
        html_file.write_text(page)
        subprocess.run(
            [
                CHROME,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                "--default-background-color=00000000",
                f"--window-size={width},{height}",
                f"--screenshot={png_file}",
                html_file.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        return Image.open(png_file).convert("RGBA").copy()


def build_ico(svg: str) -> None:
    # Each frame sits in its own cell on one page, drawn at its own size rather than downscaled.
    cell = max(ICO_SIZES) + 8
    imgs = "".join(
        f'<img src="{data_uri(svg)}" width="{s}" height="{s}" style="position:absolute;left:{i * cell}px;top:0">'
        for i, s in enumerate(ICO_SIZES)
    )
    page = f'<!doctype html><body style="margin:0;background:transparent">{imgs}</body>'
    shot = screenshot(page, cell * len(ICO_SIZES) + 100, cell + 100)
    frames = [shot.crop((i * cell, 0, i * cell + s, s)) for i, s in enumerate(ICO_SIZES)]
    largest = frames[-1]
    largest.save(ICO, format="ICO", sizes=[(s, s) for s in ICO_SIZES], append_images=frames[:-1])


def build_touch_icon(svg: str) -> None:
    old, new = FELT_BACK
    assert svg.count(f'fill="{old}"') == 1, "expected one felt-green back in favicon.svg"
    tile = data_uri(svg.replace(f'fill="{old}"', f'fill="{new}"'))
    # The tile spans 48 x 64 of the SVG's 64-unit square; drawn at 168 px it stands 126 px tall,
    # inside the corners iOS rounds off.
    page = (
        '<!doctype html><body style="margin:0">'
        f'<div style="width:{TOUCH_SIZE}px;height:{TOUCH_SIZE}px;background:{FELT_BG};'
        'display:grid;place-items:center">'
        f'<img src="{tile}" width="168" height="168" style="margin-top:4px"></div></body>'
    )
    shot = screenshot(page, TOUCH_SIZE + 100, TOUCH_SIZE + 100)
    shot.crop((0, 0, TOUCH_SIZE, TOUCH_SIZE)).convert("RGB").save(TOUCH, optimize=True)


def main() -> None:
    svg = SVG.read_text()
    build_ico(svg)
    build_touch_icon(svg)
    for path in (ICO, TOUCH):
        print(f"wrote {path.relative_to(ROOT)} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
