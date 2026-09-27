"""The "When to fold to open callers" section cites only figures from its analysis artifact, in both editions."""

import html
import json
import re
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


class FigureTests(unittest.TestCase):
    def expected(self):
        f = FIGURES
        out = [f"{sum(f['discards'].values()):,}"] + [f"{f['discards'][g]:,}" for g in GROUPS]
        line = f["fold_line"]
        out += [pct(v) for key in ("LuckyJ", "humans") for v in line["far"]["1"][key]]
        out += [pct(v) for m in ("1", "2", "3") for v in line["caller_tenpai_pct"][m]]
        far = f["mortal_fold_line"]["far"]
        out += [pct(far[band][who]) for band in ("under 15%", "over 75%") for who in ("Mortal", "Tokujou")]
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

    def test_the_fold_grid_is_drawn_from_the_artifact(self):
        line = FIGURES["fold_line"]["far"]
        cell = re.compile(r'<td( class="is-hold")?><b class="fold-lj"><span class="visually-hidden">LuckyJ </span>(\d+)</b> '
                          r'<span class="fold-h"><span class="visually-hidden">[^<]+</span>(\d+)</span></td>')
        for name in PAGES:
            cells = cell.findall(section(name))
            self.assertEqual(len(cells), 12, name)
            want = [(lj, hu) for m in ("1", "2", "3") for lj, hu in zip(line[m]["LuckyJ"], line[m]["humans"])]
            for (hold, lj, hu), (lj_want, hu_want) in zip(cells, want):
                with self.subTest(page=name, cell=(lj, hu)):
                    self.assertEqual(int(lj), half_up(lj_want))
                    self.assertEqual(int(hu), half_up(hu_want))
                    self.assertEqual(bool(hold), lj_want < 50)

    def test_the_line_the_prose_names_is_the_line_in_the_grid(self):
        # One call: still above half through the ninth discard, below from the tenth. Two or three: below from the seventh.
        far = FIGURES["fold_line"]["far"]
        self.assertTrue(far["1"]["LuckyJ"][1] > 50 > far["1"]["LuckyJ"][2])
        for m in ("2", "3"):
            self.assertTrue(far[m]["LuckyJ"][0] > 50 > far[m]["LuckyJ"][1])


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
    """Answer 4 first left out every discard that was itself a riichi declaration; the corrected card says so."""

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

    def test_contents_flag_the_correction(self):
        for name, href in (("index.html", 'href="points.html#open-callers"'), ("ja.html", 'href="#open-callers"')):
            text = page(name)
            entry = text[text.index(href):]
            entry = entry[:entry.index("</li>")]
            with self.subTest(page=name):
                self.assertIn('<span class="changed-tag">Corrected</span>', entry)
                self.assertIn("27", entry)


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
