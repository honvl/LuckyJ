#!/usr/bin/env python3
"""Build a Chrome/Edge-compatible COLRv1 tile font from GL-MahjongTile SVG glyphs."""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont
from lxml import etree
from nanoemoji.extract_svgs import svg_glyphs
from nanoemoji.glyph import glyph_name
from picosvg.svg_meta import strip_ns


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FONT = ROOT / "site/fonts/GL-MahjongTile-Clr.woff2"
OUTPUT_FONT = ROOT / "site/fonts/GL-MahjongTile-COLRv1.woff2"
TILE_CODES = "qwertyuio8asdfghjklpzxcvbnm,0.1234567"


def extract_otsvg_glyphs(source_font: Path, svg_dir: Path) -> None:
    font = TTFont(source_font)
    ascender = font["OS/2"].sTypoAscender
    descender = font["OS/2"].sTypoDescender
    height = ascender - descender
    metrics = font["hmtx"].metrics
    cmap = font.getBestCmap()
    svg_by_gid = {gid: svg for gid, svg in svg_glyphs(font)}

    for code in TILE_CODES:
        glyph = cmap[ord(code)]
        gid = font.getGlyphID(glyph)
        svg = svg_by_gid[gid]

        defs = etree.Element("defs")
        group = etree.Element("g")
        group.attrib["transform"] = f"translate(0, {ascender})"
        for element in list(svg.svg_root):
            if strip_ns(element.tag) == "defs":
                defs.append(element)
            else:
                group.append(element)

        width, _ = metrics[glyph]
        svg.svg_root.append(defs)
        svg.svg_root.append(group)
        svg.svg_root.attrib["viewBox"] = f"0 0 {width} {height}"
        svg.svg_root.attrib["width"] = str(width)
        svg.svg_root.attrib["height"] = str(height)
        (svg_dir / f"emoji_u{ord(code):04x}.svg").write_text(
            svg.tostring(pretty_print=True),
            encoding="utf-8",
        )


def normalize_svgs(raw_dir: Path, normalized_dir: Path, env: dict[str, str]) -> None:
    picosvg = shutil.which("picosvg", path=env["PATH"])
    if not picosvg:
        raise SystemExit("picosvg was not found. Install nanoemoji in the active venv.")

    normalized_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(raw_dir.glob("*.svg")):
        subprocess.run(
            [
                picosvg,
                "--noclip_to_viewbox",
                "--output_file",
                str(normalized_dir / source.name),
                str(source),
            ],
            check=True,
            env=env,
        )


def write_glyphmap(svg_dir: Path, glyphmap_file: Path) -> None:
    with glyphmap_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        for svg_file in sorted(svg_dir.glob("*.svg")):
            codepoint = int(svg_file.stem.removeprefix("emoji_u"), 16)
            writer.writerow(
                [
                    str(svg_file),
                    "",
                    glyph_name((codepoint,)),
                    f"{codepoint:04x}",
                ]
            )


def write_config(config_file: Path, output_ttf: Path) -> None:
    config_file.write_text(
        f'''family = "mahjongtile-colr"
output_file = "{output_ttf.as_posix()}"
color_format = "glyf_colr_1"
upem = 1000
width = 666
ascender = 880
descender = -120
linegap = 0
reuse_tolerance = -1
ignore_reuse_error = true
keep_glyph_names = true
clip_to_viewbox = false
fea_file = ""

[axis.wght]
name = "Weight"
default = 400

[master.regular]
style_name = "Regular"
srcs = []

[master.regular.position]
wght = 400
''',
        encoding="utf-8",
    )


def build_colrv1_font() -> None:
    tool_dir = Path(sys.prefix) / "bin"
    env = os.environ.copy()
    env["PATH"] = f"{tool_dir}{os.pathsep}{env.get('PATH', '')}"

    with tempfile.TemporaryDirectory(prefix="luckyj-colrv1-") as tmp:
        build_dir = Path(tmp)
        raw_svg_dir = build_dir / "raw-svg"
        normalized_svg_dir = build_dir / "picosvg"
        raw_svg_dir.mkdir()

        extract_otsvg_glyphs(SOURCE_FONT, raw_svg_dir)
        normalize_svgs(raw_svg_dir, normalized_svg_dir, env)

        glyphmap_file = build_dir / "glyphmap.csv"
        config_file = build_dir / "config.toml"
        output_ttf = build_dir / "GL-MahjongTile-COLRv1.ttf"
        write_glyphmap(normalized_svg_dir, glyphmap_file)
        write_config(config_file, output_ttf)

        subprocess.run(
            [
                sys.executable,
                "-m",
                "nanoemoji.write_font",
                "--config_file",
                str(config_file),
                "--glyphmap_file",
                str(glyphmap_file),
            ],
            check=True,
            env=env,
        )

        font = TTFont(output_ttf)
        font.flavor = "woff2"
        OUTPUT_FONT.parent.mkdir(parents=True, exist_ok=True)
        font.save(OUTPUT_FONT)

    print(f"Wrote {OUTPUT_FONT.relative_to(ROOT)}")


if __name__ == "__main__":
    build_colrv1_font()
