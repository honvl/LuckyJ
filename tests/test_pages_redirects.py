import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import build_pages_redirects as redirects  # noqa: E402


def test_every_site_page_gets_a_redirect(tmp_path):
    names = redirects.build(tmp_path)
    for page in (ROOT / "site").glob("*.html"):
        assert page.name in names
    assert "404.html" in names
    honver = (tmp_path / "honver.html").read_text()
    assert 'url=https://ai.yui-life.com/honver.html"' in honver
    index = (tmp_path / "index.html").read_text()
    assert 'href="https://ai.yui-life.com/"' in index


def test_redirect_keeps_path_query_and_anchor(tmp_path):
    redirects.build(tmp_path)
    script = (tmp_path / "404.html").read_text().split("<script>")[1].split("</script>")[0]
    cases = {
        "/LuckyJ/honver.html": "https://ai.yui-life.com/honver.html?x=1#own-hand",
        "/LuckyJ/": "https://ai.yui-life.com/?x=1#own-hand",
        "/LuckyJ": "https://ai.yui-life.com/?x=1#own-hand",
    }
    for path, want in cases.items():
        js = (
            f"var location={{pathname:{path!r},search:'?x=1',hash:'#own-hand',"
            "replace:function(u){console.log(u)}};" + script
        )
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
        assert out.stdout.strip() == want
