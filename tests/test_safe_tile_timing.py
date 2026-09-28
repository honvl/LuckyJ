"""The "When LuckyJ starts keeping safe tiles" section draws its charts and tables from its analysis
artifact, in both editions: one dot per discard, a fitted curve through them, and prose whose claims
follow the fit rather than hand-picked turn bands."""

import html
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = json.loads((ROOT / "analysis/safe-tile-timing-2026-09-28.json").read_text(encoding="utf-8"))
TURNS_SUMMARY = ARTIFACT["summary_turns"]
PANELS = TURNS_SUMMARY["panels"]
SHARE = ARTIFACT["summary_bands"]["threat_share_by_turn"]
PANEL_KEYS = ("quiet-honor", "quiet-terminal", "quiet-middle", "threat-any")
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


def pct(value):
    return f"{value:.1f}%"


def fit(key, who="LuckyJ"):
    return PANELS[key]["fits"][who]


def fitted_at(key, turn, who="LuckyJ"):
    return next(g[1] for g in fit(key, who)["grid"] if g[0] == float(turn))


class ArtifactTests(unittest.TestCase):
    def test_sample_is_child_kyoku_only(self):
        self.assertEqual(ARTIFACT["summary"]["child_kyoku"], 9745)
        self.assertEqual(ARTIFACT["summary"]["errors"], [])

    def test_each_fit_runs_over_discards_with_enough_choices(self):
        for key in PANEL_KEYS:
            lo, hi = PANELS[key]["range"]
            rows = {r["turn"]: r for r in PANELS[key]["turns"]}
            with self.subTest(panel=key):
                self.assertTrue(all(rows[t]["lj_n"] >= TURNS_SUMMARY["min_choices"] for t in range(lo, hi + 1)))
                for who in ("LuckyJ", "NAGA"):
                    grid = fit(key, who)["grid"]
                    self.assertEqual((grid[0][0], grid[-1][0]), (float(lo), float(hi)))
                    self.assertIn(fit(key, who)["df"], (1, 2, 3))
                    self.assertTrue(all(g[2] <= g[1] <= g[3] for g in grid))

    def test_the_claims_follow_the_fits(self):
        """What the prose, captions and rule say in words, checked against the fitted curves."""
        # guest winds: the safe one goes first on the first two discards, kept from the third
        crossings = fit("quiet-honor")["crossings_50"]
        self.assertEqual(len(crossings), 1)
        self.assertEqual(crossings[0]["direction"], "up")
        self.assertTrue(2 < crossings[0]["turn"] < 3)
        # NAGA leans the other way on guest winds at the start
        self.assertGreater(fitted_at("quiet-honor", 1, "NAGA"), 50)
        self.assertGreater(fitted_at("quiet-honor", 2, "NAGA"), 50)
        # terminals and middle tiles: the safe one kept from the first discard
        self.assertGreater(fitted_at("quiet-terminal", 1), 60)
        self.assertGreater(fitted_at("quiet-middle", 1), 60)
        self.assertEqual(fit("quiet-terminal")["crossings_50"], [])
        # NAGA keeps the safe terminal a little less firmly
        self.assertLess(fitted_at("quiet-terminal", 1, "NAGA"), fitted_at("quiet-terminal", 1))
        self.assertGreater(fitted_at("quiet-terminal", 1, "NAGA"), 50)
        # middle tiles: LuckyJ lets the safe one go first from about the seventh discard, NAGA from about the fourth
        (middle,) = fit("quiet-middle")["crossings_50"]
        self.assertEqual(middle["direction"], "down")
        self.assertTrue(6 < middle["turn"] < 7)
        (naga_middle,) = fit("quiet-middle", "NAGA")["crossings_50"]
        self.assertEqual(naga_middle["direction"], "down")
        self.assertTrue(3 < naga_middle["turn"] < 4)
        self.assertAlmostEqual(fitted_at("quiet-middle", 1, "NAGA"), 50, delta=8)  # "starts near even"
        # once someone threatens, the safe leftover goes first all the way, for LuckyJ and NAGA
        for who in ("LuckyJ", "NAGA"):
            self.assertTrue(all(g[1] < 50 for g in fit("threat-any", who)["grid"]))
        # the threat chart's caption
        self.assertEqual(int(SHARE["4"]["threat_pct"] + 0.5), 8)
        self.assertGreater(SHARE["10"]["threat_pct"], 50)


class ChartTests(unittest.TestCase):
    dot = re.compile(r'<circle class="timing-dot lj" [^>]*data-turn="(\d+)" data-pct="([\d.]+)" data-n="(\d+)"')

    def test_the_pages_match_the_generator(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build_safe_tile_timing_figures.py"), "--check"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_one_dot_per_discard_from_the_artifact(self):
        for name in PAGES:
            keep = block(section(name), '<figure class="timing-figure" id="timing-keep"', "</figure>")
            for key in PANEL_KEYS:
                panel = block(keep, f'data-panel="{key}"', "</svg>")
                lo, hi = PANELS[key]["range"]
                rows = {r["turn"]: r for r in PANELS[key]["turns"]}
                expected = [(str(t), f"{100 * rows[t]['lj_k'] / rows[t]['lj_n']:.1f}", str(rows[t]["lj_n"])) for t in range(lo, hi + 1)]
                with self.subTest(page=name, panel=key):
                    self.assertEqual(self.dot.findall(panel), expected)
                    self.assertEqual(panel.count('class="timing-hit"'), hi - lo + 1)

    def test_fitted_curves_band_and_crossings_are_drawn(self):
        for name in PAGES:
            keep = block(section(name), '<figure class="timing-figure" id="timing-keep"', "</figure>")
            for key in PANEL_KEYS:
                panel = block(keep, f'data-panel="{key}"', "</svg>")
                with self.subTest(page=name, panel=key):
                    for who, cls in (("LuckyJ", "lj"), ("NAGA", "naga")):
                        points = re.search(rf'<polyline class="timing-fit {cls}" points="([^"]+)"', panel).group(1).split()
                        self.assertEqual(len(points), len(fit(key, who)["grid"]))
                    band = re.search(r'<polygon class="timing-band" points="([^"]+)"', panel).group(1).split()
                    self.assertEqual(len(band), 2 * len(fit(key)["grid"]))
                    crossings = re.findall(r'<circle class="timing-switch" [^>]*data-turn="([\d.]+)"', panel)
                    self.assertEqual(crossings, [f"{c['turn']:.2f}" for c in fit(key)["crossings_50"]])
                    for c in fit(key)["crossings_50"]:
                        a = int(c["turn"])
                        note = f"between discards {a} and {a + 1}" if name == "points.html" else f"{a}打目と{a + 1}打目の間"
                        self.assertIn(note, plain(panel))

    def test_the_threat_chart_comes_from_the_artifact(self):
        for name in PAGES:
            threat = block(section(name), '<figure class="timing-figure is-single" id="timing-threat"', "</figure>")
            labeled = re.findall(r'<circle class="timing-dot threat" [^>]*data-turn="(\d+)" data-pct="([\d.]+)"', threat)
            with self.subTest(page=name):
                self.assertEqual(labeled, [(t, f"{SHARE[t]['threat_pct']:.1f}") for t in ("4", "7", "10")])
                self.assertEqual(threat.count('class="timing-hit"'), 18)
                points = re.search(r'<polyline class="timing-line threat" points="([^"]+)"', threat).group(1).split()
                self.assertEqual(len(points), 18)

    def test_the_tables_hold_every_discard(self):
        for name in PAGES:
            keep = plain(block(section(name), '<figure class="timing-figure" id="timing-keep"', "</figure>"))
            threat = plain(block(section(name), '<figure class="timing-figure is-single" id="timing-threat"', "</figure>"))
            for key in PANEL_KEYS:
                for r in PANELS[key]["turns"]:
                    if not r["lj_n"]:
                        continue
                    figures = [pct(100 * r["lj_k"] / r["lj_n"]), f"{r['lj_n']:,}"]
                    if r["naga_n"]:
                        figures.append(pct(100 * r["naga_k"] / r["naga_n"]))
                    for figure in figures:
                        with self.subTest(page=name, panel=key, turn=r["turn"], figure=figure):
                            self.assertIn(figure, keep)
            for turn in range(1, 19):
                for figure in (pct(SHARE[str(turn)]["threat_pct"]), f"{SHARE[str(turn)]['states']:,}"):
                    with self.subTest(page=name, turn=turn, figure=figure):
                        self.assertIn(figure, threat)

    def test_charts_are_readable_without_the_tooltip(self):
        for name in PAGES:
            text = section(name)
            with self.subTest(page=name):
                self.assertEqual(text.count('role="img" aria-label="'), 5)
                self.assertEqual(text.count('<details class="timing-table">'), 2)
        app = (ROOT / "site/app.js").read_text(encoding="utf-8")
        self.assertIn("function setupTimingCharts()", app)
        self.assertIn("  setupTimingCharts();\n", app)


class ProseTests(unittest.TestCase):
    def test_the_turns_named_in_the_prose_are_the_fitted_ones(self):
        en = plain(section("points.html"))
        ja = plain(section("ja.html"))
        self.assertIn("From about the seventh discard LuckyJ throws the safe middle tile first", en)
        self.assertIn("From about your seventh discard, start throwing a safe middle tile first", en)
        self.assertIn("throws the safe one first from about the fourth discard", en)
        self.assertIn("From the third discard LuckyJ keeps the safe wind", en)
        self.assertIn("7打目ごろからは、LuckyJ は河にある中張牌を先に切る", ja)
        self.assertIn("4打目ごろから安全な方を先に切る", ja)
        for text in (en, ja):
            self.assertNotRegex(text, r"ninth discard|9打目から")


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


if __name__ == "__main__":
    unittest.main()
