"""The replays under each chapter differ from one another, and each has its own written commentary."""

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_point_examples as points  # noqa: E402

EXAMPLES = json.loads((ROOT / "site/point-examples.json").read_text(encoding="utf-8"))
COMMENTARY = json.loads((ROOT / "data/replay_commentary.json").read_text(encoding="utf-8"))
FIELDS = ("prompt", "read", "whyNot")


def sentences(text):
    # tiles and numbers vary between replays; a template shows up once they are masked
    # a comma or point belongs to a number only between digits, so "against 9." still ends a sentence
    masked = re.sub(r"\d+(?:[,.]\d+)*", "#", re.sub(r"\[\[[^\]]+\]\]", "T", text))
    return [s.strip() for s in re.split(r"(?<=[.!?。])\s*", masked) if len(s.strip()) > 12]


class ReplaySelectionTests(unittest.TestCase):
    def test_each_point_shows_a_few_replays_from_different_games(self):
        for point, rows in EXAMPLES.items():
            with self.subTest(point=point):
                self.assertGreaterEqual(len(rows), points.MIN_EXAMPLES_PER_POINT)
                self.assertLessEqual(len(rows), points.EXAMPLES_PER_POINT)
                self.assertEqual(len({case["game"] for case in rows}), len(rows))
                self.assertEqual([case["example_index"] for case in rows], list(range(1, len(rows) + 1)))

    def test_replays_vary_the_seat_and_the_table(self):
        for point, rows in EXAMPLES.items():
            with self.subTest(point=point):
                self.assertGreaterEqual(len({case["current_rank"] for case in rows}), 3)
                situations = {(case["current_rank"], case["stage"], points.threat_kind(case)) for case in rows}
                self.assertEqual(len(situations), len(rows), "two replays show the same seat, stage and threat")

    def test_point_one_is_not_only_leads(self):
        rows = EXAMPLES["point-01"]
        self.assertGreaterEqual(len({case["current_rank"] for case in rows}), 3)
        self.assertGreaterEqual(len({case.get("placement_job") for case in rows}), 2)
        for case in rows:
            self.assertIsNotNone(points.placement_job(case))

    def test_every_replay_shows_a_real_difference(self):
        for point, rows in EXAMPLES.items():
            for case in rows:
                with self.subTest(point=point, game=case["game"]):
                    self.assertTrue(points.has_named_difference(point, case))


class ReplayCommentaryTests(unittest.TestCase):
    def test_every_replay_has_written_commentary_in_both_languages(self):
        for point, rows in EXAMPLES.items():
            for case in rows:
                with self.subTest(point=point, game=case["game"]):
                    self.assertIn(points.commentary_key(case), COMMENTARY)
                    for lang in ("guide", "guide_ja"):
                        self.assertEqual(set(case[lang]), set(FIELDS))
                        for field in FIELDS:
                            self.assertTrue(case[lang][field].strip(), f"{lang}.{field}")

    def test_no_sentence_repeats_within_a_chapter(self):
        for point, rows in EXAMPLES.items():
            with self.subTest(point=point):
                seen = {}
                for case in rows:
                    for lang in ("guide", "guide_ja"):
                        for field in FIELDS:
                            for sentence in sentences(case[lang][field]):
                                self.assertNotIn(sentence, seen, f"repeated in {point}: {sentence}")
                                seen[sentence] = case["game"]

    def test_voice_rules(self):
        text = " ".join(case[lang][field] for rows in EXAMPLES.values() for case in rows
                        for lang in ("guide", "guide_ja") for field in FIELDS)
        self.assertNotRegex(text, r"[—–]")
        self.assertNotRegex(text, r"(?i)\bof course\b|もちろん|のである")
        self.assertNotRegex(text, r"\bis not [^.;:]{1,40}[.;] It(?:'s| is)\b")

    def test_commentary_makes_no_unsupported_claims(self):
        for point, rows in EXAMPLES.items():
            for case in rows:
                text = " ".join(case[lang][field] for lang in ("guide", "guide_ja") for field in FIELDS)
                with self.subTest(point=point, game=case["game"]):
                    self.assertFalse(points.cached_guide_has_false_suji_claim(case, text))
                    self.assertFalse(points.cached_guide_treats_danger_proxy_as_probability(text))
                    self.assertFalse(points.cached_guide_uses_ambiguous_naga_threat_label(text))
                    self.assertFalse(points.cached_guide_has_discarded_route_claim(case, text))

    def test_commentary_file_has_no_orphans(self):
        keys = {points.commentary_key(case) for rows in EXAMPLES.values() for case in rows}
        self.assertEqual(set(COMMENTARY) - keys, set())


if __name__ == "__main__":
    unittest.main()
