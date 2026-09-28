"""The "When LuckyJ starts keeping safe tiles" section draws its charts and tables from its analysis
artifact, in both editions, and keeps its numbers out of the prose."""

import html
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = json.loads((ROOT / "analysis/safe-tile-timing-2026-09-28.json").read_text(encoding="utf-8"))
SUMMARY = ARTIFACT["summary_bands"]
BANDS = SUMMARY["bands"]
SHARE = SUMMARY["threat_share_by_turn"]
QUIET = BANDS["quiet"]
THREAT = BANDS["threat"]["any"]
BAND_ORDER = ("1-2", "3-5", "6-8", "9-12", "13-18")
PANELS = (("quiet", "honor"), ("quiet", "terminal"), ("quiet", "middle"), ("threat", "any"))
MIN_PLOTTED = 30
MIN_SOLID = 50
PAGES = ("points.html", "ja.html")


def page(name):
    return (ROOT / "site" / name).read_text(encoding="utf-8")


def section(name):
    text = page(name)
    start = text.index('<section class="section" id="safe-tile-timing">')
    return text[start:text.index("</section>", start)]


def block(markup, start, end):
    a = markup.index(start)
    return markup[a:markup.index(end, a)]


def plain(markup):
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


def prose(name):
    """The section's own sentences: paragraphs, rule and exception, without the figures."""
    text = section(name)
    text = re.sub(r"<figure.*?</figure>", " ", text, flags=re.S)
    return plain(text)


def pct(value):
    return f"{value:.1f}%"


class ArtifactTests(unittest.TestCase):
    def test_sample_is_child_kyoku_only(self):
        self.assertEqual(ARTIFACT["summary"]["child_kyoku"], 9745)
        self.assertEqual(ARTIFACT["summary"]["errors"], [])

    def test_the_claims_follow_the_artifact(self):
        """What the prose, captions and rule say in words, checked against the numbers."""
        live = lambda kind, band: QUIET[kind][band]["LuckyJ"]["live_share_pct"]
        naga = lambda kind, band: QUIET[kind][band]["NAGA"]["live_share_pct"]
        # terminals and middle tiles: the safe one kept from the first discard
        self.assertGreater(live("terminal", "1-2"), 60)
        self.assertGreater(live("middle", "1-2"), 60)
        # guest winds: the safe one goes first on the first two discards, kept from the third
        self.assertLess(live("honor", "1-2"), 40)
        self.assertGreater(live("honor", "3-5"), 60)
        self.assertGreater(live("honor", "6-8"), 60)
        # NAGA: same way on terminals but less firmly, no preference on middle tiles through the fifth,
        # and the other way on guest winds at the start
        self.assertGreater(naga("terminal", "1-2"), 50)
        self.assertLess(naga("terminal", "1-2"), live("terminal", "1-2"))
        for band in ("1-2", "3-5"):
            self.assertAlmostEqual(naga("middle", band), 50, delta=3)
        self.assertGreater(naga("honor", "1-2"), 50)
        # from the ninth discard the safe middle tile goes first more often than not
        self.assertLess(live("middle", "9-12"), 50)
        # once someone threatens, the safe leftover goes first in every plotted band, and NAGA agrees
        for band in ("3-5", "6-8", "9-12", "13-18"):
            self.assertLess(THREAT[band]["LuckyJ"]["live_share_pct"], 30)
            self.assertLess(THREAT[band]["NAGA"]["live_share_pct"], 30)
        # the threat chart's caption
        self.assertEqual(int(SHARE["4"]["threat_pct"] + 0.5), 8)
        self.assertGreater(SHARE["10"]["threat_pct"], 50)


class ChartTests(unittest.TestCase):
    dot = re.compile(r'<circle class="timing-dot (lj|naga)( hollow)?" [^>]*data-band="([\d-]+)" data-pct="([\d.]+)"')

    def test_the_pages_match_the_generator(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_safe_tile_timing_figures.py"), "--check"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_every_point_of_the_four_panels_comes_from_the_artifact(self):
        for name in PAGES:
            keep = block(section(name), '<figure class="timing-figure" id="timing-keep"', "</figure>")
            for split, kind in PANELS:
                panel = block(keep, f'data-panel="{split}-{kind}"', "</svg>")
                found = self.dot.findall(panel)
                expected = []
                for who, key in (("naga", "NAGA"), ("lj", "LuckyJ")):
                    for band in BAND_ORDER:
                        cell = BANDS[split][kind][band]
                        if cell["LuckyJ"]["cuts"] < MIN_PLOTTED:
                            continue
                        hollow = " hollow" if cell["LuckyJ"]["cuts"] < MIN_SOLID else ""
                        expected.append((who, hollow, band, f"{cell[key]['live_share_pct']:.1f}"))
                with self.subTest(page=name, panel=f"{split}-{kind}"):
                    self.assertEqual(found, expected)

    def test_the_threat_chart_comes_from_the_artifact(self):
        for name in PAGES:
            threat = block(section(name), '<figure class="timing-figure is-single" id="timing-threat"', "</figure>")
            labeled = re.findall(r'<circle class="timing-dot threat" [^>]*data-turn="(\d+)" data-pct="([\d.]+)"', threat)
            with self.subTest(page=name):
                self.assertEqual(labeled, [(t, f"{SHARE[t]['threat_pct']:.1f}") for t in ("4", "7", "10")])
                self.assertEqual(threat.count('class="timing-hit"'), 18)
                points = re.search(r'<polyline class="timing-line threat" points="([^"]+)"', threat).group(1).split()
                self.assertEqual(len(points), 18)

    def test_the_tables_hold_every_rate_and_sample(self):
        for name in PAGES:
            keep = plain(block(section(name), '<figure class="timing-figure" id="timing-keep"', "</figure>"))
            threat = plain(block(section(name), '<figure class="timing-figure is-single" id="timing-threat"', "</figure>"))
            for split, kind in PANELS:
                for band in BAND_ORDER:
                    cell = BANDS[split][kind][band]
                    if cell["LuckyJ"]["cuts"] == 0:
                        continue
                    for figure in (pct(cell["LuckyJ"]["live_share_pct"]), pct(cell["NAGA"]["live_share_pct"]), f"{cell['LuckyJ']['cuts']:,}"):
                        with self.subTest(page=name, panel=f"{split}-{kind}", band=band, figure=figure):
                            self.assertIn(figure, keep)
            for turn in range(1, 19):
                for figure in (pct(SHARE[str(turn)]["threat_pct"]), f"{SHARE[str(turn)]['states']:,}"):
                    with self.subTest(page=name, turn=turn, figure=figure):
                        self.assertIn(figure, threat)

    def test_charts_are_readable_without_the_tooltip(self):
        """Every plotted panel names itself for screen readers, and the hover layer is wired up."""
        for name in PAGES:
            text = section(name)
            with self.subTest(page=name):
                self.assertEqual(text.count('role="img" aria-label="'), 5)
                self.assertEqual(text.count('<details class="timing-table">'), 2)
        app = (ROOT / "site/app.js").read_text(encoding="utf-8")
        self.assertIn("function setupTimingCharts()", app)
        self.assertIn("  setupTimingCharts();\n", app)


class PlacementTests(unittest.TestCase):
    def test_the_section_follows_open_callers(self):
        for name in PAGES:
            text = page(name)
            callers = text.index('<section class="section" id="open-callers">')
            timing = text.index('<section class="section" id="safe-tile-timing">')
            self.assertGreater(timing, callers, name)
            self.assertEqual(text[callers:timing].count("<section"), 1, name)

    def test_contents_and_sources_list_the_section(self):
        for name, href in (("index.html", 'href="points.html#safe-tile-timing"'), ("ja.html", 'href="#safe-tile-timing"')):
            text = page(name)
            entry = text[text.index(href):]
            entry = entry[:entry.index("</li>")]
            with self.subTest(page=name):
                self.assertIn('<span class="new-tag">New</span>', entry)
        for name in PAGES:
            self.assertIn("analysis/safe-tile-timing-2026-09-28.md", page(name))
        self.assertTrue((ROOT / "analysis/safe-tile-timing-2026-09-28.md").exists())

    def test_rule_exception_evidence_and_tiles(self):
        for name in PAGES:
            text = section(name)
            with self.subTest(page=name):
                self.assertEqual(text.count('<div class="rule">'), 1)
                self.assertEqual(text.count('<div class="exception">'), 1)
                self.assertEqual(text.count('class="evidence-note"'), 1)
                self.assertIn('href="#point-14"', text)
                self.assertIn("9,745", plain(text))
                for tile in ("[[9p]]", "[[1s]]", "[[W]]", "[[N]]"):
                    self.assertIn(tile, text)


class VoiceTests(unittest.TestCase):
    def test_voice_rules(self):
        for name in PAGES:
            text = plain(section(name))
            with self.subTest(page=name):
                self.assertNotRegex(text, r"[—–]")
                self.assertNotRegex(text, r"(?i)\bof course\b|もちろん|のである")
                self.assertNotRegex(text, r"\bis not [^.;:]{1,40}[.;] It(?:'s| is)\b")

    def test_no_ratios_written_out_in_words(self):
        """The reader found "three times in four" hard to follow: rates live in the charts and tables."""
        number = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        for name in PAGES:
            text = prose(name)
            with self.subTest(page=name):
                self.assertNotRegex(text, rf"(?i)\b{number}\s+(?:times?\s+)?in\s+{number}\b")
                self.assertNotRegex(text, r"(?i)\bthree quarters\b|\bin every \w+ hands\b")
                self.assertNotRegex(text, r"\d+回に\d+回|\d+分の\d+")

    def test_the_prose_keeps_numbers_to_the_evidence(self):
        """Outside the evidence note, the paragraphs name turns, not rates."""
        for name in PAGES:
            text = section(name)
            text = re.sub(r"<figure.*?</figure>", " ", text, flags=re.S)
            text = re.sub(r'<p class="evidence-note">.*?</p>', " ", text, flags=re.S)
            with self.subTest(page=name):
                self.assertNotRegex(plain(text), r"\d+(?:\.\d+)?\s*%")


if __name__ == "__main__":
    unittest.main()
