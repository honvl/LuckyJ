"""The "When LuckyJ starts keeping safe tiles" section cites only figures from its analysis artifact, in both editions."""

import html
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = json.loads((ROOT / "analysis/safe-tile-timing-2026-09-28.json").read_text(encoding="utf-8"))
SUMMARY = ARTIFACT["summary_bands"]
QUIET = SUMMARY["bands"]["quiet"]
THREAT = SUMMARY["bands"]["threat"]["any"]
GRID_BANDS = ("1-2", "3-5", "6-8", "9-12")
THREAT_BANDS = ("3-5", "6-8", "9-12", "13-18")
PAGES = ("points.html", "ja.html")


def page(name):
    return (ROOT / "site" / name).read_text(encoding="utf-8")


def section(name):
    text = page(name)
    start = text.index('<section class="section" id="safe-tile-timing">')
    return text[start:text.index("</section>", start)]


def plain(markup):
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


def pct(value):
    return f"{value:.1f}%"


def half_up(value):
    return int(value + 0.5)


class FigureTests(unittest.TestCase):
    def test_sample_is_child_kyoku_only(self):
        self.assertEqual(ARTIFACT["summary"]["child_kyoku"], 9745)
        self.assertEqual(ARTIFACT["summary"]["errors"], [])

    def expected(self):
        out = [f"{ARTIFACT['summary']['child_kyoku']:,}"]
        for kind in ("honor", "terminal", "middle"):
            out += [f"{QUIET[kind][band]['LuckyJ']['cuts']:,}" for band in GRID_BANDS]
        out += [pct(THREAT[band][who]["live_share_pct"]) for who in ("LuckyJ", "NAGA") for band in THREAT_BANDS]
        out += [f"{THREAT[band]['LuckyJ']['cuts']:,}" for band in THREAT_BANDS]
        share = SUMMARY["threat_share_by_turn"]
        out += [pct(share[turn]["threat_pct"]) for turn in ("4", "7", "10")]
        return out

    def test_every_figure_matches_the_artifact_in_both_editions(self):
        for name in PAGES:
            text = plain(section(name))
            for figure in self.expected():
                with self.subTest(page=name, figure=figure):
                    self.assertIn(figure, text)

    def test_the_grid_is_drawn_from_the_artifact(self):
        cell = re.compile(r'<td( class="is-hold")?><b class="fold-lj"><span class="visually-hidden">LuckyJ </span>(\d+)</b> '
                          r'<span class="fold-h"><span class="visually-hidden">NAGA </span>(\d+)</span></td>')
        expected = []
        for kind in ("honor", "terminal", "middle"):
            for band in GRID_BANDS:
                lj = half_up(QUIET[kind][band]["LuckyJ"]["live_share_pct"])
                naga = half_up(QUIET[kind][band]["NAGA"]["live_share_pct"])
                expected.append((' class="is-hold"' if lj < 50 else "", str(lj), str(naga)))
        for name in PAGES:
            with self.subTest(page=name):
                self.assertEqual(cell.findall(section(name)), expected)

    def test_the_prose_describes_the_grid(self):
        """The rounded claims in the prose follow the artifact."""
        guest_early = QUIET["honor"]["1-2"]["LuckyJ"]
        self.assertAlmostEqual(100 - guest_early["live_share_pct"], 75, delta=3)   # safe wind first, three in four
        terminal_early = QUIET["terminal"]["1-2"]["LuckyJ"]["live_share_pct"]
        self.assertAlmostEqual(terminal_early, 75, delta=3)                        # live terminal first, three in four
        self.assertGreater(QUIET["middle"]["1-2"]["LuckyJ"]["live_share_pct"], 80)  # more than four in five
        mid = [QUIET["honor"][band]["LuckyJ"] for band in ("3-5", "6-8")]
        self.assertAlmostEqual(100 * sum(b["live_cuts"] for b in mid) / sum(b["cuts"] for b in mid), 70, delta=2)
        self.assertAlmostEqual(QUIET["honor"]["1-2"]["NAGA"]["live_share_pct"], 60, delta=2)
        for band in ("1-2", "3-5"):
            self.assertAlmostEqual(QUIET["middle"][band]["NAGA"]["live_share_pct"], 50, delta=3)
        self.assertAlmostEqual(100 - QUIET["middle"]["9-12"]["LuckyJ"]["live_share_pct"], 60, delta=4)
        self.assertGreater(SUMMARY["threat_share_by_turn"]["10"]["threat_pct"], 50)


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

    def test_rule_exception_and_evidence(self):
        for name in PAGES:
            text = section(name)
            with self.subTest(page=name):
                self.assertEqual(text.count('<div class="rule">'), 1)
                self.assertEqual(text.count('<div class="exception">'), 1)
                self.assertEqual(text.count('class="evidence-note"'), 1)
                self.assertIn('href="#point-14"', text)


class VoiceTests(unittest.TestCase):
    def test_voice_rules(self):
        for name in PAGES:
            text = plain(section(name))
            with self.subTest(page=name):
                self.assertNotRegex(text, r"[—–]")
                self.assertNotRegex(text, r"(?i)\bof course\b|もちろん|のである")
                self.assertNotRegex(text, r"\bis not [^.;:]{1,40}[.;] It(?:'s| is)\b")


if __name__ == "__main__":
    unittest.main()
