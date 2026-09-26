"""The "Against the humans" section cites only figures from its analysis artifact, in both editions."""

import html
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES = json.loads((ROOT / "analysis/table-contrast-2026-09-25.json").read_text(encoding="utf-8"))
PAGES = ("points.html", "ja.html")


def section(name):
    text = (ROOT / "site" / name).read_text(encoding="utf-8")
    start = text.index('<section class="section" id="table-contrast">')
    return text[start:text.index("</section>", start)]


def plain(markup):
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


def pct(value):
    return f"{value:.1f}%"


def points(value):
    sign = "+" if value > 0 else "−" if value < 0 else ""
    return f"{sign}{abs(value):,}"


def half_up(value):
    return int(value + 0.5)


class FigureTests(unittest.TestCase):
    def expected(self):
        f = FIGURES
        out = [str(f["ledger"]["net_gap_luckyj_over_tablemates"])]
        out += [f"{v:.1f}" for v in f["ledger"]["dealin_not_tenpai_per100"] + f["ledger"]["dealin_tenpai_per100"]]
        out += [pct(v) for v in f["ledger"]["win_rate_pct"][1:]]
        out += [f"{f['pairs']['human_into_luckyj_per100']:.2f}", f"{f['pairs']['human_into_human_per100']:.2f}"]
        out += [f"{f['pairs']['luckyj_ron_value']:,}", f"{f['pairs']['human_ron_value']:,}"]
        for group in FIGURES["groups"]:
            out += [pct(v) for v in f["callers"]["live_cut_2sh_no_dora"][group].values()]
        for table in ("Tokujou tables", "Houou tables"):
            out += [pct(f["callers"]["caller_tenpai_pct"][table][n]) for n in ("0", "2", "3")]
        out += [str(v) for v in f["ledger"]["points_lost_not_tenpai_into_open"] + f["ledger"]["points_lost_not_tenpai_into_riichi"]]
        out += [pct(v) for key in ("unsafe_2sh_pct", "unsafe_3sh_pct", "unsafe_far_by_turn8_pct") for v in f["far"][key]]
        out += [f"{v:.2f}" for v in f["far"]["dealin_3sh_per100"]]
        out += [pct(v) for band in f["riichi"]["declare_pct"].values() for v in band]
        out += [f"{gain:,}" for gain, _ in f["riichi"]["riichi_minus_dama"].values()]
        out.append(pct(f["riichi"]["mortal_prefers_riichi_pct"]))
        out += [pct(v) for band in f["dora"]["tanyao_call_pct"].values() for v in band]
        out += [pct(v) for v in f["dora"]["three_plus_dora_any_route_pct"].values()]
        out += [pct(v) for v in f["dora"]["value_pair_pon_2sh_pct"]]
        for gain, se in f["dora"]["humans_call_minus_pass"].values():
            out += [points(gain), f"±{se}"]
        out += [f"{v:.2f}" for v in f["flush"]["flush_wins_per100"]]
        out += [pct(v) for band in f["flush"]["fast_start_pct"].values() for v in band]
        for gain, se in f["flush"]["humans_fast_minus_slow"].values():
            out += [points(gain), f"±{se}"]
        return out

    def test_every_figure_matches_the_artifact_in_both_editions(self):
        for name in PAGES:
            text = plain(section(name))
            for figure in self.expected():
                with self.subTest(page=name, figure=figure):
                    self.assertIn(figure, text)

    def test_the_figure_is_drawn_to_the_artifact(self):
        f = FIGURES
        panels = [
            [(f["callers"]["live_cut_2sh_no_dora"][g]["no_tells"], f["callers"]["live_cut_2sh_no_dora"][g]["two_plus"]) for g in f["groups"]],
            list(zip(f["far"]["unsafe_tenpai_pct"], f["far"]["unsafe_3sh_pct"])),
            list(zip(*f["dora"]["tanyao_call_pct"].values())),
        ]
        for name in PAGES:
            rows = re.findall(r'<div class="dumbbell[^"]*">(.*?)</div>', section(name))
            self.assertEqual(len(rows), 9, name)
            for row, (start, end) in zip(rows, [pair for panel in panels for pair in panel]):
                with self.subTest(page=name, row=row[:60]):
                    dots = [float(x) for x in re.findall(r'dumbbell-dot[^"]*" style="left:([\d.]+)%', row)]
                    self.assertAlmostEqual(dots[0], start / 80 * 100, delta=0.06)
                    self.assertAlmostEqual(dots[1], end / 80 * 100, delta=0.06)
                    self.assertIn(f"{half_up(start)} &#8594; {half_up(end)}", row)


class StructureTests(unittest.TestCase):
    def test_five_cards_in_order_with_a_ledger(self):
        for name in PAGES:
            text = section(name)
            cards = re.findall(r'<div class="rx-card" id="(tc-\d)">', text)
            self.assertEqual(cards, [f"tc-{i}" for i in range(1, 6)], name)
            ledger = re.findall(r'<a href="#(tc-\d)">', text)
            self.assertEqual(ledger, cards, name)
            self.assertEqual(text.count('class="rx-basis"'), 5, name)

    def test_contents_list_the_section(self):
        index = (ROOT / "site/index.html").read_text(encoding="utf-8")
        ja = (ROOT / "site/ja.html").read_text(encoding="utf-8")
        self.assertIn('href="points.html#table-contrast"', index)
        self.assertIn('href="#table-contrast"', ja)


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
