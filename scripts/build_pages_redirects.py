"""Build the GitHub Pages copy as redirects to the site's new home.

The site moved from honvl.github.io/LuckyJ to ai.yui-life.com (20 Nov 2026).
Every old page name gets a stub that sends the reader to the same page there,
keeping the query string and #anchor; 404.html catches every other path.

    python scripts/build_pages_redirects.py --out _pages
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

NEW_ORIGIN = "https://ai.yui-life.com"
OLD_PREFIX = "/LuckyJ"
ROOT = Path(__file__).resolve().parent.parent

STUB = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Moved to ai.yui-life.com</title>
<meta name="robots" content="noindex">
<link rel="canonical" href="{url}">
<meta http-equiv="refresh" content="0; url={url}">
<script>
  var path = location.pathname.replace(/^{prefix}(?=\\/|$)/, "") || "/";
  location.replace("{origin}" + path + location.search + location.hash);
</script>
</head>
<body>
<p>This site moved to <a href="{url}">{url}</a>.</p>
</body>
</html>
"""


def stub(page: str) -> str:
    url = html.escape(f"{NEW_ORIGIN}/{page}")
    return STUB.format(url=url, origin=NEW_ORIGIN, prefix=OLD_PREFIX.replace("/", "\\/"))


def build(out: Path, site: Path = ROOT / "site") -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    pages = sorted(p.name for p in site.glob("*.html"))
    for name in pages:
        target = "" if name == "index.html" else name
        (out / name).write_text(stub(target), encoding="utf-8")
    (out / "404.html").write_text(stub(""), encoding="utf-8")
    return pages + ["404.html"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "_pages")
    args = parser.parse_args()
    for name in build(args.out):
        print(name)


if __name__ == "__main__":
    main()
