"""The "When to fold to open callers" section cites only figures from its analysis artifact, in both editions."""

import html
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES = json.loads((ROOT / "analysis/open-callers-2026-09-27.json").read_text(encoding="utf-8"))
PAGES = ("points.html", "ja.html")
GROUPS = FIGURES["groups"]


def page(name):
    return (ROOT / "site" / name).read_text(encoding="utf-8")


def section(name):
    text = page(name)
    start = text.index('<section class="section" id="open-callers">')
    return text[start:text.index("</section>", start)]


def plain(markup):
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


def pct(value):
    return f"{value:.1f}%"


def half_up(value):
    return int(value + 0.5)


REAL = FIGURES["real_choices"]
FAR = REAL["lines"]["far"]
ORDINALS = {6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth"}


def crossing(curve):
    """The fitted curve's one downward crossing of 50%, as the two discards it falls between."""
    (c,) = curve["crossings_50"]
    assert c["direction"] == "down"
    return int(c["turn"]), int(c["turn"]) + 1


def fitted(curve, discard):
    return curve["fit"][str(discard)][0]


class FigureTests(unittest.TestCase):
    def expected(self):
        f = FIGURES
        out = [f"{sum(f['discards'].values()):,}"] + [f"{f['discards'][g]:,}" for g in GROUPS]
        line = f["fold_line"]
        out += [pct(v) for m in ("1", "2", "3") for v in line["caller_tenpai_pct"][m]]
        # the corrected fold line: real choices only, with ties and costly turns apart
        out += [f"{FAR[count][block]['LuckyJ']['spots']:,}" for count in ("real", "tie", "costly") for block in ("1", "2+")]
        kinds = REAL["kinds"]["far"]["LuckyJ"]
        out += [f"{kinds[k]['spots']:,}" for k in ("safe tile is the best tile", "only safe tiles keep shanten")]
        out += [f"{half_up(fitted(FAR['costly'][block]['LuckyJ'], 10))}%" for block in ("1", "2+")]
        mortal = REAL["mortal"]["far"]
        out += [pct(mortal[band][who]) for band in ("under 15%", "over 75%") for who in ("Mortal", "LuckyJ", "Tokujou")]
        dora = f["dora_pon"]
        out += [pct(v) for g in GROUPS for v in dora["live_cut_pct"][g] + dora["far_live_cut_pct"][g]]
        out += [pct(v) for v in dora["mortal_live_cut_pct"] + dora["caller_tenpai_pct"] + [dora["dora_pon_share_pct"]]]
        out += [f"{v:,}" for v in dora["caller_win_value"] + dora["deal_in_cost"][1:]]
        out += [f"{half_up(v)}%" for v in dora["live_cut_pct"]["LuckyJ"] + dora["far_live_cut_pct"]["LuckyJ"] + dora["caller_tenpai_pct"]]
        out += [f"{round(dora['deal_in_cost'][0], -3):,}", f"{round(dora['deal_in_cost'][1], -2):,}"]
        passed = f["passed"]
        out += [pct(passed["cut_pct"][g]) for g in GROUPS] + [f"{passed['n'][g]:,}" for g in GROUPS]
        out += [pct(passed["mortal_cut_pct"]), f"{passed['cuts']:,}"]
        wait = f["half_wait"]
        out += [f"{wait['dilemmas'][g]:,}" for g in GROUPS]
        out += [pct(v) for g in GROUPS for v in wait["safe_pct_by_row"][g]]
        out += [pct(v) for v in wait["mortal_safe_pct_by_row"] + wait["safe_pct_by_keep"]["LuckyJ"] + wait["live_tile_on_wait_pct_by_row"]]
        out += [pct(wait["safe_pct_by_value"]["LuckyJ"][0]), pct(wait["safe_pct_by_value"]["LuckyJ"][2])]
        out += [f"+{wait['humans_net_by_row']['wide'][2]:,}", f"+{wait['humans_net_by_row']['safe'][2]:,}"]
        out += [str(wait["closed_with_yaku_n_luckyj"]), pct(wait["closed_with_yaku_safe_pct_luckyj"]), pct(wait["mortal_closed_with_yaku_safe_pct"])]
        declare = f["riichi_open"]
        out += [str(declare["spots"][g]) for g in GROUPS]
        out += [pct(declare[key][g]) for key in ("declared_pct", "declared_wide_pct") for g in GROUPS]
        out += [pct(declare["mortal_declared_pct"]), pct(declare["mortal_declared_wide_pct"])]
        return out

    def test_every_figure_matches_the_artifact_in_both_editions(self):
        for name in PAGES:
            text = plain(section(name))
            for figure in self.expected():
                with self.subTest(page=name, figure=figure):
                    self.assertIn(figure, text)

    def test_the_lines_the_prose_names_are_the_fitted_lines(self):
        # Real choices: below half from a one-call caller's twelfth discard and a two-call caller's ninth.
        self.assertEqual(crossing(FAR["real"]["1"]["LuckyJ"]), (11, 12))
        self.assertEqual(crossing(FAR["real"]["2+"]["LuckyJ"]), (8, 9))
        # Ties alone: the tenth and the seventh, where the first version put the line, for LuckyJ and the humans.
        for who in ("LuckyJ", "humans"):
            with self.subTest(who=who):
                self.assertEqual(crossing(FAR["tie"]["1"][who]), (9, 10))
                self.assertEqual(crossing(FAR["tie"]["2+"][who]), (6, 7))
        # Costly turns: LuckyJ's fitted curve stays above half over its whole range.
        for block in ("1", "2+"):
            curve = FAR["costly"][block]["LuckyJ"]
            with self.subTest(block=block):
                self.assertEqual(curve["crossings_50"], [])
                self.assertGreater(min(v[0] for v in curve["fit"].values()), 50)
                self.assertEqual(curve["range"][1], 10)

    def test_the_prose_names_the_lines(self):
        en = plain(section("points.html"))
        ja = plain(section("ja.html"))
        self.assertIn("through the caller\u2019s eleventh discard and from the twelfth threw the safe tile first", en)
        self.assertIn("Against two or three calls it switched at the ninth", en)
        self.assertIn("11打目までは生牌を切り続け、12打目からは安全牌を先に切った", ja)
        self.assertIn("切り替えは9打目だった", ja)


def figure(name):
    text = section(name)
    start = text.index('<figure class="timing-figure" id="oc-fold-line"')
    return text[start:text.index("</figure>", start)]


class ChartTests(unittest.TestCase):
    dot = re.compile(r'<circle class="timing-dot lj" [^>]*data-turn="(\d+)" data-pct="([\d.]+)" data-n="(\d+)"')
    panels = (("1", "tie"), ("1", "costly"), ("2+", "tie"), ("2+", "costly"))

    def test_the_pages_match_the_generator(self):
        run = subprocess.run([sys.executable, str(ROOT / "scripts/build_open_callers_figure.py"), "--check"],
                             capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_one_dot_per_discard_and_both_fitted_curves(self):
        for name in PAGES:
            chart = figure(name)
            self.assertEqual(chart.count('<div class="timing-panel"'), 4, name)
            for block, count in self.panels:
                start = chart.index(f'data-panel="fold-{block}-{count}"')
                panel = chart[start:chart.index("</svg>", start)]
                curves = FAR[count][block]
                lj = curves["LuckyJ"]
                lo, hi = lj["range"]
                want = [(str(t), f"{100 * lj['k'][t - 1] / lj['n'][t - 1]:.1f}", str(lj["n"][t - 1])) for t in range(lo, hi + 1)]
                with self.subTest(page=name, panel=(block, count)):
                    self.assertEqual(self.dot.findall(panel), want)
                    for cls, who in (("lj", "LuckyJ"), ("humans", "humans")):
                        points = re.search(rf'<polyline class="timing-fit {cls}" points="([^"]+)"', panel).group(1).split()
                        self.assertEqual(len(points), len(curves[who]["grid"]))
                    self.assertEqual(panel.count('class="timing-switch"'), len(lj["crossings_50"]))

    def test_the_old_grid_is_gone(self):
        for name in PAGES:
            self.assertNotIn('class="fold-grid"', section(name), name)


class StructureTests(unittest.TestCase):
    def test_four_cards_in_order_with_a_ledger(self):
        for name in PAGES:
            text = section(name)
            cards = re.findall(r'<div class="rx-card" id="(oc-\d)">', text)
            self.assertEqual(cards, [f"oc-{i}" for i in range(1, 5)], name)
            ledger = re.findall(r'<a href="#(oc-\d)"><span class="rx-ledger-num">', text)
            self.assertEqual(ledger, cards, name)
            self.assertEqual(text.count('class="rx-basis"'), 4, name)

    def test_the_section_follows_against_the_humans(self):
        for name in PAGES:
            text = page(name)
            contrast = text.index('<section class="section" id="table-contrast">')
            callers = text.index('<section class="section" id="open-callers">')
            between = text[contrast:callers]
            self.assertEqual(between.count("<section"), 1, name)

    def test_contents_and_sources_list_the_section(self):
        self.assertIn('href="points.html#open-callers"', page("index.html"))
        self.assertIn('href="#open-callers"', page("ja.html"))
        for name in PAGES:
            self.assertIn("analysis/open-callers-2026-09-27.md", page(name))
        self.assertTrue((ROOT / "analysis/open-callers-2026-09-27.md").exists())


class CorrectionTests(unittest.TestCase):
    """Answer 4 first left out every discard that was itself a riichi declaration, and answer 1's fold line first
    counted turns where throwing the safe tile was shape, not defense; the corrected cards say so."""

    def card(self, name):
        text = section(name)
        start = text.index('<div class="rx-card" id="oc-4">')
        return text[start:text.index("</div>", start)]

    def test_answer_four_is_marked_and_the_old_rates_are_gone(self):
        for name, old in (("points.html", ("kept the wide wait five times in six", "about four times in ten", "one in three of its 21")),
                          ("ja.html", ("6回に5回広い待ちを残し", "約10回に4回", "21局面で3回に1回"))):
            card = self.card(name)
            with self.subTest(page=name):
                self.assertIn('<mark id="fix-oc4" class="guide-changed">', card)
                for phrase in old:
                    self.assertNotIn(phrase, card)

    def test_answer_one_is_marked_and_the_old_line_is_gone(self):
        old = {"points.html": ("through the caller\u2019s ninth discard and from the tenth", "76.7%", "57.7%", "38.4%", "17.6%", "69.3%", "23.2%", "67.1%", "35.6%"),
               "ja.html": ("9打目までは生牌を切り続け、10打目からは", "76.7%", "57.7%", "38.4%", "17.6%", "69.3%", "23.2%", "67.1%", "35.6%")}
        for name, phrases in old.items():
            text = section(name)
            start = text.index('<div class="rx-card" id="oc-1">')
            card = text[start:text.index('<div class="rx-card" id="oc-2">')]
            with self.subTest(page=name):
                self.assertIn('<mark id="fix-oc1" class="guide-changed">', card)
                self.assertIn('<mark id="fix-oc1-evidence" class="guide-changed">', card)
                self.assertIn('<mark id="fix-oc1-figure" class="guide-changed">', figure(name))
                ledger = text[text.index('<a href="#oc-1">'):]
                self.assertIn('<mark class="guide-changed">', ledger[:ledger.index("</a>")])
                for phrase in phrases:
                    self.assertNotIn(phrase, plain(card))

    def test_contents_flag_the_correction(self):
        for name, href in (("index.html", 'href="points.html#open-callers"'), ("ja.html", 'href="#open-callers"')):
            text = page(name)
            entry = text[text.index(href):]
            entry = entry[:entry.index("</li>")]
            with self.subTest(page=name):
                self.assertIn('<span class="changed-tag">Corrected</span>', entry)
                self.assertIn("27", entry)
                self.assertIn("29", entry)


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
