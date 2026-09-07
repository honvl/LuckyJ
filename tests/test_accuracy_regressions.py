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

    def test_open_hand_brake_exhaustion_is_explicit(self):
        strategy = read_json("site/strategy-guides.json")["point-04"]
        strategy_ja = read_json("site/strategy-guides.ja.json")["point-04"]
        strategy_text = " ".join(strategy.values()).lower()
        strategy_ja_text = " ".join(strategy_ja.values())
        points = (ROOT / "site/points.html").read_text(encoding="utf-8").lower()
        ja = (ROOT / "site/ja.html").read_text(encoding="utf-8")

        self.assertIn("one turn, not a permanent fold", strategy_text)
        self.assertIn("mawashi has ended", strategy_text)
        self.assertIn("fourth against the third-place dealer", strategy_text)
        self.assertIn("一巡", strategy_ja_text)
        self.assertIn("回し打ちは終わ", strategy_ja_text)
        self.assertIn("4着", strategy_ja_text)
        self.assertIn("one saved genbutsu buys one turn", points)
        self.assertIn("fourth and the riichi dealer is third", points)
        self.assertIn("残した現物が買うのは一巡", ja)
        self.assertIn("自分が4着で、立直した親が3着", ja)

    def test_extreme_danger_audit_is_nondealer_only(self):
        audit = read_json("data/nondealer_high_danger_pushes.json")
        methodology = audit["methodology"]
        summary = audit["summary"]

        self.assertEqual(methodology["luckyj_dealer_states"], "excluded")
        self.assertEqual(methodology["post_luckyj_riichi_locked_discards"], "excluded")
        self.assertEqual(summary["decisions"], 46)
        self.assertEqual(summary["capped_at_99_99"], 25)
        self.assertEqual(summary["shanten"], {
            "tenpai": 33,
            "one_shanten": 12,
            "two_or_more_shanten": 1,
        })
        self.assertEqual(summary["hand_state"]["open"], 20)
        self.assertEqual(summary["against_at_least_one_riichi"], 46)
        self.assertEqual(summary["supported_by_at_least_two_naga_heads"], 30)
        self.assertEqual(summary["outcomes"], {
            "self_win": 12,
            "direct_deal_in": 11,
            "other_player_win": 14,
            "draw": 9,
        })
        self.assertTrue(all(not row["dealer"] for row in audit["decisions"]))
        self.assertTrue(all(row["danger_proxy"] >= 0.90 for row in audit["decisions"]))
        self.assertTrue(all(row["opponent_riichi_count"] >= 1 for row in audit["decisions"]))
        self.assertEqual(
            {row["example_category"] for row in audit["examples"]},
            {
                "high_value_tenpai",
                "fourth_place_one_shanten",
                "riichi_declaration",
                "valuable_open_tenpai",
                "three_call_inventory_trap",
                "engine_rejected_overpush",
            },
        )

        strategy = " ".join(read_json("site/strategy-guides.json")["point-09"].values())
        strategy_ja = " ".join(read_json("site/strategy-guides.ja.json")["point-09"].values())
        points = (ROOT / "site/points.html").read_text(encoding="utf-8")
        ja = (ROOT / "site/ja.html").read_text(encoding="utf-8")
        self.assertIn("nondealer Tokujou sample", strategy)
        self.assertIn("46 chosen discards", strategy)
        self.assertIn("These counts describe nondealer decisions only", strategy)
        self.assertIn("特上卓の子のサンプル", strategy_ja)
        self.assertIn("選択打牌は46件", strategy_ja)
        self.assertIn("nondealer-only", points)
        self.assertIn("最大NAGA危険度指標90%以上の選択打牌が46件", ja)
        self.assertNotIn("Game 401", points)
        self.assertNotIn("Game 401", ja)

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

    def test_point14_pre_threat_target_is_explicit(self):
        mined = read_json("analysis/pre-threat-safety-2026-09-07.json")
        threat = mined["threat_source"]
        self.assertEqual(mined["summary"]["dealer_kyoku_skipped"], 3309)
        self.assertEqual(threat["riichi_rate_per_opponent_kyoku"]["dealer"]["rate_pct"], 21.0)
        self.assertEqual(threat["riichi_rate_per_opponent_kyoku"]["child"]["rate_pct"], 17.7)
        self.assertEqual(mined["deal_in_price"]["loss_points"]["dealer"]["mean"], 6712.1)
        self.assertEqual(mined["deal_in_price"]["loss_points"]["child"]["mean"], 4724.4)
        pre = mined["pre_declaration_genbutsu"]
        self.assertEqual(pre["holds_at_least_one"]["all"]["n"], 5504)
        self.assertEqual(pre["holds_at_least_one"]["all"]["rate_pct"], 74.5)
        retention = mined["quiet_table_retention"]["discard_rate_by_owner_role_and_tile_kind"]
        self.assertEqual(retention["dealer"]["all"]["rate_pct"], 13.3)
        self.assertEqual(retention["child"]["all"]["rate_pct"], 12.4)

        strategy = " ".join(read_json("site/strategy-guides.json")["point-14"].values())
        strategy_ja = " ".join(read_json("site/strategy-guides.ja.json")["point-14"].values())
        points = (ROOT / "site/points.html").read_text(encoding="utf-8")
        ja = (ROOT / "site/ja.html").read_text(encoding="utf-8")
        for text in (strategy, points):
            self.assertIn("74.5% of 5,504", text)
            self.assertIn("21.0% of child kyoku against 17.7%", text)
            self.assertIn("13.3%", text)
            self.assertIn("price rule", text)
            self.assertIn("replaces the dealer as the name", text)
        for text in (strategy_ja, ja):
            self.assertIn("5,504回のうち74.5%", text)
            self.assertIn("21.0%でリーチし、各子は17.7%", text)
            self.assertIn("13.3%", text)
            self.assertIn("値段の規則", text)
            self.assertIn("宣言者が親に代わって名前になる", text)


if __name__ == "__main__":
    unittest.main()
