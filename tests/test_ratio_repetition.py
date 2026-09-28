"""Rates written out in words ("three times in four", "3回に1回") are fine now and then. The reader found
them confusing only when they came over and over, as in the first safe-tile timing section, where one
turned up every few sentences. This keeps every section of both editions below that density."""

import html
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NUMBER = r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|twenty-five|\d+)"
EN_RATIO = re.compile(
    rf"(?i)\b{NUMBER}\s+(?:times?\s+|chances?\s+|(?:first\s+)?tenpais\s+|thin\s+waits?\s+|hands?\s+)?in\s+{NUMBER}\b"
)
JA_RATIO = re.compile(r"\d+回に\d+回|\d+分の\d+")
MAX_PER_PARAGRAPH = 2
EN_WORDS_PER_RATIO = 150  # the first safe-tile section had one every 65 words; Prescriptions one every 75
JA_CHARS_PER_RATIO = 300  # the Japanese Prescriptions had one every 165 characters


def plain(markup):
    return html.unescape(re.sub(r"<[^>]+>", " ", markup))


def sections(name):
    text = (ROOT / "site" / name).read_text(encoding="utf-8")
    starts = [(m.start(), m.group(1)) for m in re.finditer(r'<section class="(?:section|point)[^"]*" id="([^"]+)"', text)]
    for i, (start, sid) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        yield sid, re.sub(r"<figure.*?</figure>", " ", text[start:end], flags=re.S)


class RatioRepetitionTests(unittest.TestCase):
    def check(self, name, pattern, size_of, per_ratio):
        for sid, markup in sections(name):
            paragraphs = re.findall(r"<(?:p|a|li)(?: [^>]*)?>(.*?)</(?:p|a|li)>", markup, flags=re.S)
            ratios = pattern.findall(plain(markup))
            with self.subTest(page=name, section=sid):
                for paragraph in paragraphs:
                    self.assertLessEqual(len(pattern.findall(plain(paragraph))), MAX_PER_PARAGRAPH, plain(paragraph)[:120])
                if ratios:
                    self.assertGreaterEqual(size_of(plain(markup)) / len(ratios), per_ratio, ratios)

    def test_english_sections_do_not_repeat_ratios_in_words(self):
        self.check("points.html", EN_RATIO, lambda text: len(text.split()), EN_WORDS_PER_RATIO)

    def test_japanese_sections_do_not_repeat_ratios_in_words(self):
        self.check("ja.html", JA_RATIO, lambda text: len(re.sub(r"\s", "", text)), JA_CHARS_PER_RATIO)

    def test_the_check_catches_the_old_wording(self):
        old = ("when it threw one of two leftover terminals it was the live one three times in four, and with two "
               "leftover middle tiles more than four times in five. Through its eighth it threw the live wind seven "
               "times in ten, and NAGA threw it first six times in ten.")
        self.assertEqual(len(EN_RATIO.findall(old)), 4)
        self.assertEqual(len(JA_RATIO.findall("4回に3回、5回に4回を超え、10回に7回、4分の3")), 4)


if __name__ == "__main__":
    unittest.main()
