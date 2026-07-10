import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import analyze_luckyj as analysis  # noqa: E402
import build_mortal_analysis as mortal  # noqa: E402


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class AccuracyRegressionTests(unittest.TestCase):
    def test_clean_corpus_invariants(self):
        data = read_json("data/luckyj_analysis.json")
        self.assertEqual(data["games_analyzed"], 1255)
        self.assertEqual(data["totals"]["rounds"], 13054)
        self.assertEqual(data["totals"]["decision_count"], 147337)
        self.assertEqual(data["totals"]["exhaustive_draws"], 1761)
        self.assertEqual(data["totals"]["draw_tenpai"], 823)
        self.assertEqual(data["source_scope"]["room_counts"], {
            "General": 49,
            "Tokujou": 1079,
            "Upper": 127,
        })
        self.assertEqual(data["source_scope"]["duplicates_removed"], 1)
        duplicate = data["source_scope"]["duplicate_report_groups"][0]
        self.assertEqual(duplicate["kept_idx"], 1101)
        self.assertEqual(duplicate["dropped"][0]["idx"], 1100)
        self.assertEqual(data["errors"], [])

    def test_source_correction_is_auditable(self):
        corrections = read_json("data/source_corrections.json")
        row = corrections["paifu_overrides"]["107"]
        self.assertIn("2023042215gm-0089-0000-934864ab", row["paifu"])

    def test_abortive_draw_is_not_counted_as_exhaustive(self):
        end = [{"tenpais": [True, False, False, False]}]
        self.assertTrue(analysis.exhaustive_draw_tenpai(end, 0, 0))
        self.assertIsNone(analysis.exhaustive_draw_tenpai(end, 0, 66))

    def test_showcases_are_tokujou_and_model_aligned(self):
        examples = read_json("site/point-examples.json")
        mortal_rows = mortal.existing_mortal_cache(ROOT / "site/mortal-analysis.json")
        self.assertEqual(sum(len(rows) for rows in examples.values()), 160)
        for point, rows in examples.items():
            for case in rows:
                self.assertEqual(case["room"], "Tokujou")
                self.assertEqual(case["room_code"], "0029")
                self.assertIn(mortal.example_signature(point, case), mortal_rows)
                if point != "point-12":
                    self.assertNotIn(case["evidence_tier"], {"unsupported", "unverified"})

        cases = read_json("site/case-studies.json")
        for rows in cases.values():
            for case in rows:
                self.assertEqual(case["room"], "Tokujou")
                self.assertEqual(case["room_code"], "0029")

        prescriptions = read_json("site/rx-prescription-examples.json")
        for rows in prescriptions.values():
            for case in rows:
                self.assertEqual(case["room"], "Tokujou")
                self.assertEqual(case["room_code"], "0029")

    def test_point_specific_guards(self):
        examples = read_json("site/point-examples.json")
        for case in examples["point-04"]:
            post_call = case["post_call_eval"]
            self.assertTrue(post_call["targeted_reserve_tiles"])
            primary_seat = post_call["primary_threat"]["seat"]
            for reserve in post_call["primary_threat_reserve_reads"]:
                self.assertTrue(reserve["safe_against_threat"])
                self.assertTrue(any(
                    opponent["seat_label"] == primary_seat
                    and opponent["kind"] in {"genbutsu", "suji"}
                    for opponent in reserve["against"]
                ))
            if case["game"] == 229:
                self.assertEqual(post_call["targeted_reserve_tiles"][0], "9s")
            if case["game"] == 534:
                self.assertEqual(post_call["targeted_reserve_tiles"][0], "6s")
        for case in examples["point-13"]:
            self.assertEqual(analysis.tile_class(case["actual"]), "honor")
            self.assertNotEqual(analysis.tile_class(case["naga"]), "honor")
            text = f"{case['guide']['read']} {case['guide_ja']['read']}"
            self.assertRegex(text, r"pon risk|ポンリスク")
            self.assertNotRegex(text, r"still incomplete|still looks incomplete|まだ未完成|まだ遠い")
            self.assertNotIn("場風/自風", text)

    def test_reader_guides_do_not_overstate_danger_proxy(self):
        examples = read_json("site/point-examples.json")
        text = " ".join(
            str(case.get(lang, {}).get(field, ""))
            for rows in examples.values()
            for case in rows
            for lang in ("guide", "guide_ja")
            for field in ("read", "whyNot", "copy", "limit", "prompt", "answer")
        )
        self.assertNotRegex(text, r"(?<![\d.])0\.\d{2,4}(?!\d)")
        self.assertNotRegex(text, r"\bdeal[- ]?in (?:probability|chance|rate|risk)\b")
        self.assertNotRegex(text, r"放銃(?:率|確率|リスク)")
        self.assertNotRegex(text, r"\bdanger[TSK]\b")
        self.assertNotRegex(text, r"\bNAGA threat\b|NAGA脅威")

        strategy_text = " ".join(
            json.dumps(read_json(path), ensure_ascii=False)
            for path in ("site/strategy-guides.json", "site/strategy-guides.ja.json")
        )
        self.assertNotRegex(strategy_text, r"still looks incomplete|相手がまだ遠い")

        app = (ROOT / "site/app.js").read_text(encoding="utf-8")
        self.assertIn('nagaThreat: "NAGA danger proxy"', app)
        self.assertIn('nagaThreat: "NAGA危険度指標"', app)
        self.assertNotIn('nagaThreat: "NAGA threat"', app)
        self.assertNotIn('immediateDanger: "Immediate danger"', app)

    def test_reader_copy_matches_current_prescription_artifacts(self):
        points = (ROOT / "site/points.html").read_text(encoding="utf-8")
        ja = (ROOT / "site/ja.html").read_text(encoding="utf-8")
        for text in (points, ja):
            self.assertIn("76.6%", text)
            self.assertIn("63.4%", text)
            self.assertIn("Δ-10.8pp", text)
            self.assertNotIn("still looks incomplete", text)
            self.assertNotIn("相手がまだ遠い", text)
        self.assertIn("字牌整理が4,135件", ja)
        self.assertIn("対象外になった安全牌を使うケースが4,005件", ja)


if __name__ == "__main__":
    unittest.main()
