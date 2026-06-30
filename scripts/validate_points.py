#!/usr/bin/env python3
"""Validate the numbered LuckyJ playbook points against supporting statistics."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "site" / "model-patterns.json"
BOOK_PATH = ROOT / "site" / "book-data.json"
OUT_JSON = ROOT / "site" / "point-validation.json"
OUT_MD = ROOT / "analysis" / "point-validation-2026-06-30.md"


REVIEW_EXAMPLES = {
    "point-01": (
        "Review example: in a South-round placement hand, a low-risk tile that keeps a clean fold or cheap win can beat a thin value upgrade.",
        "検討例: 南場の着順手では、薄い打点上昇より、きれいな撤退や安い和了を残す低危険牌が勝つことがある。",
    ),
    "point-02": (
        "Review example: when one hand can become yakuhai, honitsu/chanta, or riichi, keep the anchor that preserves those futures over the prettiest one-route shape.",
        "検討例: 役牌、混一/チャンタ、リーチの複数未来がある手では、見た目の良い一本道より、それらを残す支点を優先する。",
    ),
    "point-03": (
        "Review example: call a bad block only when it creates yaku, tenpai, denial, or safe draw equity; skip the call that merely exposes a fragile one-away hand.",
        "検討例: 悪いブロックは、役、テンパイ、阻止、安全なツモ番を作る時だけ鳴く。壊れやすい一向聴を晒すだけなら見送る。",
    ),
    "point-04": (
        "Review example: after opening, keep an exit to the live threat if the hand can still reach tenpai; commitment still needs one clean brake.",
        "検討例: 副露後でもテンパイが現実的なら、実脅威への出口を一枚残す。コミットした手にもきれいなブレーキを残す。",
    ),
    "point-05": (
        "Review example: if a loose middle tile will become the only discard after riichi, cut it while the hand still has blocks and replacement routes.",
        "検討例: リーチ後に唯一切らされる浮き中張牌は、ブロックと代替ルートがあるうちに処理する。",
    ),
    "point-06": (
        "Review example: keep red or dora access when it improves a real winning route; release it when the extra value is decorative and the next danger is concrete.",
        "検討例: 赤やドラ受けは本物の和了ルートを良くする時に残す。打点が飾りで次の危険が具体的なら手放す。",
    ),
    "point-07": (
        "Review example: a tempo call is valid when it creates tenpai, yaku certainty, denial, or an ippatsu break; raw speed needs an actual payoff.",
        "検討例: テンポ鳴きは、テンパイ、役確定、阻止、一発消しを作る時に有効。単なる速度には追加の目的が必要。",
    ),
    "point-08": (
        "Review example: declare when the hand's value and wait force opponents to react; stay flexible when riichi only exposes a bad route with little pressure.",
        "検討例: 打点と待ちが相手に対応を強制する時はリーチ。悪いルートを晒すだけで圧力が薄い時は柔軟に構える。",
    ),
    "point-09": (
        "Review example: a one-chance or suji label can flip after a second threat, new call, or suit-constrained river; reprice the tile before pushing.",
        "検討例: ワンチャンスや筋の評価は、二件目の脅威、新しい鳴き、色の制約で反転する。押す前に値付けし直す。",
    ),
    "point-10": (
        "Review example: third-row choices need exact tenpai, noten, deal-in, and placement arithmetic; copy a late push after the point swing is clear.",
        "検討例: 三段目はテンパイ、ノーテン、放銃、着順の点差計算が必要。点差変化を確認してから終盤の押しを真似する。",
    ),
    "point-11": (
        "Review example: preserve a harmless route to drawn-hand tenpai, but abandon it when the next discard must pass multiple live threats.",
        "検討例: 無害に流局テンパイへ戻る道は残す。ただし次打が複数脅威を通すなら捨てる。",
    ),
    "point-12": (
        "Review example: when models split, write the purchased value, safety, and route count before calling the move good or bad.",
        "検討例: モデルが割れた時は、打牌が買う打点、安全、ルート数を書いてから良し悪しを判断する。",
    ),
    "point-13": (
        "Review example: a lone dragon or seat wind changes price when an opponent's open hand still lacks a visible yaku.",
        "検討例: 相手の副露手に見える役がない時、孤立三元牌や自風牌の値段は大きく変わる。",
    ),
    "point-14": (
        "Review example: keep genbutsu or suji only after naming the target player and the next turn it protects.",
        "検討例: 現物や筋は、対象者と守る次巡を名付けてから残す。",
    ),
    "point-15": (
        "Review example: yesterday's safe tile loses value when a new riichi becomes the real threat and the old tile blocks your tenpai route.",
        "検討例: 新しいリーチが本当の脅威になり、古い安全牌がテンパイルートを邪魔するなら、その牌の価値は下がる。",
    ),
    "point-16": (
        "Review example: under pressure, an edge discard can reduce exposure while preserving the inner connector that actually wins the hand.",
        "検討例: 圧力下では、外側牌切りが露出を下げつつ、本当に和了する内側の接続を残すことがある。",
    ),
    "point-17": (
        "Review example: label the kept tile as safe against the dealer riichi, the open child, or no one; the last category should usually be spent.",
        "検討例: 残す牌を親リーチへの安全牌、子の副露への安全牌、誰にも効かない牌に分ける。最後の分類は基本的に使う。",
    ),
    "point-18": (
        "Review example: classify each honor as self value, opponent yaku condition, dead material, or defensive exit before cutting.",
        "検討例: 字牌は切る前に、自分の打点、相手の役条件、枯れ材料、守備出口へ分類する。",
    ),
    "point-19": (
        "Review example: as leader, lower ambition when the discard also keeps a clean next turn and fits the placement target.",
        "検討例: トップ目で目標を下げる時は、次巡がきれいに打てて着順目標にも合う牌を選ぶ。",
    ),
}


def pct(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    return f"{float(value) * 100:.1f}%"


def pp(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else ""
    return f"{sign}{float(value) * 100:.1f} pp"


def num(value: float | int | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def pval(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    value = float(value)
    if value == 0:
        return "<0.0001"
    if value < 0.0001:
        return f"{value:.2e}"
    return f"{value:.4f}"


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def local_review_file_count() -> int:
    count = 0
    for folder in ROOT.glob("tmp/*captions"):
        text_transcripts = list((folder / "transcripts").glob("*.txt"))
        if text_transcripts:
            count += len(text_transcripts)
        else:
            count += len(list(folder.glob("*.json3")))
    return count


def pattern(patterns: dict[str, Any], key: str, label: str, label_ja: str) -> dict[str, str]:
    item = patterns[key]
    text = (
        f"{label}: n={item['n']:,}, bad {pct(item['bad_rate'])}, "
        f"lift {pp(item['bad_lift_vs_other_mismatches'])}, "
        f"p={pval(item['bad_rate_p_value'])}, danger delta {num(item['avg_danger_delta'], 3)}."
    )
    text_ja = (
        f"{label_ja}: n={item['n']:,}, 悪手率 {pct(item['bad_rate'])}, "
        f"平均との差 {pp(item['bad_lift_vs_other_mismatches'])}, "
        f"p={pval(item['bad_rate_p_value'])}, 危険度差 {num(item['avg_danger_delta'], 3)}。"
    )
    return {"kind": "pattern", "key": key, "text": text, "text_ja": text_ja}


def aggregate(text: str, text_ja: str) -> dict[str, str]:
    return {"kind": "aggregate", "text": text, "text_ja": text_ja}


def point(
    id_: str,
    category: str,
    category_ja: str,
    title: str,
    title_ja: str,
    strength: str,
    verdict: str,
    verdict_ja: str,
    read: str,
    read_ja: str,
    caveat: str,
    caveat_ja: str,
    example: str,
    example_ja: str,
    stats: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "id": id_,
        "category": category,
        "category_ja": category_ja,
        "title": title,
        "title_ja": title_ja,
        "strength": strength,
        "verdict": verdict,
        "verdict_ja": verdict_ja,
        "read": read,
        "read_ja": read_ja,
        "caveat": caveat,
        "caveat_ja": caveat_ja,
        "example": example,
        "example_ja": example_ja,
        "stats": stats,
    }


def build() -> dict[str, Any]:
    model = load_json(MODEL_PATH)
    book = load_json(BOOK_PATH)
    patterns = model["summary"]["patterns"]
    overall = model["summary"]["overall"]
    nishiki = model.get("model_split", {}).get("models", {}).get("nishiki", {})
    review_decisions = nishiki.get("decisions", overall["decisions"])
    review_mismatches = nishiki.get("top_mismatches", overall["mismatches"])
    review_bad_rate = nishiki.get("severe_disagreement_rate", overall["bad_rate_among_mismatches"])
    summary = book["summary"]
    top = book["top_bottom"]["top_half"]
    bottom = book["top_bottom"]["bottom_half"]
    counters = book["decision_counters"]
    late = counters["stage"]["late"]
    middle = counters["stage"]["middle"]
    yakuhai = counters["yakuhai_pressure"]["self_yakuhai"]

    conversion = aggregate(
        "Outcome split: top-half games averaged 3.09 wins and 0.75 deal-ins; bottom-half games averaged 1.39 wins and 1.48 deal-ins.",
        "成績差: 上位半分は半荘あたり和了3.09回、放銃0.75回。下位半分は和了1.39回、放銃1.48回。",
    )
    call_riichi = aggregate(
        f"Winning-half volume was active: calls/game {num(top['calls_per_game'])} compared with {num(bottom['calls_per_game'])}, riichi/game {num(top['riichi_per_game'])} compared with {num(bottom['riichi_per_game'])}.",
        f"上位半分は能動的: 鳴きは半荘あたり {num(top['calls_per_game'])} 対 {num(bottom['calls_per_game'])}、リーチは {num(top['riichi_per_game'])} 対 {num(bottom['riichi_per_game'])}。",
    )
    call_rate = aggregate(
        f"Call opportunities became calls {pct(summary['call_round_rate'])} of hands, so call points need purpose filters.",
        f"局単位の鳴き率は {pct(summary['call_round_rate'])}。鳴きは可否より目的フィルターで見る必要がある。",
    )
    late_precision = aggregate(
        f"Late row remained dense enough to matter: {late['decisions']:,} decisions, mismatch {pct(late['mismatch'] / late['decisions'])}, bad {pct(late['bad'] / late['decisions'])}.",
        f"三段目も重要な母数がある: 判断 {late['decisions']:,} 件、不一致 {pct(late['mismatch'] / late['decisions'])}、悪手 {pct(late['bad'] / late['decisions'])}。",
    )
    middle_late = aggregate(
        f"Middle plus late decisions total {middle['decisions'] + late['decisions']:,}; the defense points have evidence beyond opening-row cleanup.",
        f"中盤と終盤の判断は合計 {middle['decisions'] + late['decisions']:,} 件。守備点は序盤整理に加えて中終盤にも根拠がある。",
    )
    drawn_hand = aggregate(
        f"Draw-tenpai-plus rounds occurred in {pct(summary['draw_tenpai_plus_rate'])} of hands, making noten-bappu a real objective.",
        f"流局テンパイ以上は {pct(summary['draw_tenpai_plus_rate'])} の局で発生。ノーテン罰符は本物の目的になる。",
    )
    mismatch = aggregate(
        f"Model review base: {review_mismatches:,} LuckyJ/Nishiki mismatches from {review_decisions:,} split-head decisions; only {pct(review_bad_rate)} hit the severe-disagreement proxy.",
        f"モデル復習の母数: split-head 判断 {review_decisions:,} 件中 LuckyJ/ニシキ不一致 {review_mismatches:,} 件。重い不一致 proxy は {pct(review_bad_rate)} に限られる。",
    )
    self_yakuhai = aggregate(
        f"Loose self-yakuhai timing split: no-open contexts cut singletons on median turn {num(yakuhai['no_open_hand']['median_cut_turn'], 1)}, while tanyao-shaped open contexts delayed to turn {num(yakuhai['tanyao_shaped_open']['median_cut_turn'], 1)}.",
        f"自分役牌の処理時期: 無副露文脈の中央値は {num(yakuhai['no_open_hand']['median_cut_turn'], 1)} 巡目、タンヤオ形副露文脈では {num(yakuhai['tanyao_shaped_open']['median_cut_turn'], 1)} 巡目まで遅れる。",
    )

    points = [
        point(
            "point-01",
            "Value and Placement",
            "打点と着順",
            "Start with placement before hand shape.",
            "着順から手牌問題を見る。",
            "qualified",
            "Qualified",
            "条件付き",
            "Placement framing is valid, but the statistics reject a blanket 'push because behind' rule.",
            "着順から読む方針は妥当。ただし「負けているから押す」という一般化は統計が否定する。",
            "Require concrete upside and a discard that keeps danger manageable.",
            "打点上昇や着順変化が具体的で、危険度が管理できる時だけ使う。",
            "Example: as leader, a low-danger discard that preserves the next safe turn can beat a thin value upgrade.",
            "例: トップ目では薄い打点上昇より、次巡の安全を残す低危険打牌が勝つことがある。",
            [
                pattern(patterns, "leader_low_risk", "Leader low-risk choices", "トップ目の低危険選択"),
                pattern(patterns, "behind_risk_buy", "Behind-score risk buys", "ビハインド時のリスク購入"),
                conversion,
            ],
        ),
        point(
            "point-02",
            "Shape and Routes",
            "形とルート",
            "Keep more than one route alive.",
            "複数ルートを残す。",
            "strong",
            "Strong",
            "強い",
            "Pair/triplet anchors and dora/red material had materially lower bad rates than other mismatches.",
            "対子/刻子の支点とドラ/赤の保持は、他の不一致より悪手率が明確に低い。",
            "The support is strongest for anchors with a job.",
            "仕事のある支点への支持が強い。",
            "Example: keep a yakuhai pair or red-five branch when it creates value plus an open fallback.",
            "例: 役牌対子や赤受けが打点と鳴き返しを同時に作るなら残す。",
            [
                pattern(patterns, "keep_pair_anchor", "Kept pair/triplet anchors", "対子/刻子支点の保持"),
                pattern(patterns, "keep_dora_or_red", "Kept dora/red-five material", "ドラ/赤の保持"),
                pattern(patterns, "break_pair_anchor", "Breaking pairs early", "対子早割り"),
            ],
        ),
        point(
            "point-03",
            "Calls and Yaku Conditions",
            "鳴きと役条件",
            "Call bad shapes when the call changes the hand's job.",
            "悪形は、手の仕事が変わる時だけ鳴く。",
            "qualified",
            "Qualified",
            "条件付き",
            "Aggregate results support purposeful calling; a broad call-more rule still needs proof.",
            "目的のある鳴きは成績面で支持される。単純な鳴き増やしは追加検証が必要。",
            "Demand a named purpose: tenpai, yaku creation, value, denial, or safe-tenpai equity.",
            "テンパイ、役作り、打点、阻止、形式テンパイなど目的を名付ける。",
            "Example: chi when it creates a real yaku route or a safe tenpai path from the weak block.",
            "例: 弱ブロックから役ルートや安全テンパイルートが生まれる時だけチーする。",
            [call_rate, call_riichi, middle_late],
        ),
        point(
            "point-04",
            "Calls and Defense",
            "鳴きと守備",
            "Open hands still need exits.",
            "副露手にも出口を残す。",
            "strong",
            "Strong",
            "強い",
            "Threat-specific exit retention was strong, while generic safe-tile hoarding was worse than baseline.",
            "脅威に対応する出口保持は強い一方、一般的な安全牌抱えは基準より悪い。",
            "This point is target-specific: name the threat before keeping the exit.",
            "対象特化のルール。出口を残す前に相手を名付ける。",
            "Example: after opening, keep one genbutsu to the live riichi if the hand still has a real tenpai path.",
            "例: 鳴いた後でも本物のテンパイルートがあるなら、現物を一枚だけリーチ者への出口として残す。",
            [
                pattern(patterns, "threat_keep_exit", "Threat-specific exits", "脅威対象の出口保持"),
                pattern(patterns, "multi_threat_safe_tenpai", "Middle/late multi-threat exits", "中終盤の多件脅威出口"),
                pattern(patterns, "keep_defensive_exit", "Generic safe-tile retention", "一般的な安全牌保持"),
            ],
        ),
        point(
            "point-05",
            "Shape and Defense",
            "形と守備",
            "Price the future danger of floaters.",
            "浮き牌の未来危険を値付けする。",
            "strong",
            "Strong",
            "強い",
            "Safer-than-Nishiki choices were one of the clearest support signals; danger pricing should be explicit.",
            "ニシキより安全な選択は最もきれいな信号の一つで、危険度の値付けを明示すべき。",
            "Keep this targeted: early slimming works when the tile has little value or yaku route left.",
            "早切りは、牌の価値や役ルートが薄い時に絞る。",
            "Example: cut the future-riichi liability before it becomes the only discard your hand can release.",
            "例: 後でリーチに切れなくなる浮き牌は、唯一の打牌になる前に処理する。",
            [
                pattern(patterns, "safer_than_naga", "Lower-danger discards", "低危険打牌"),
                pattern(patterns, "riskier_than_naga", "Higher-danger discards", "高危険打牌"),
                pattern(patterns, "cut_outside_keep_inside", "Outside cuts preserving inner route", "本線を残す外側切り"),
            ],
        ),
        point(
            "point-06",
            "Value and Routes",
            "打点とルート",
            "Build value from the first discard.",
            "第一打から打点を作る。",
            "qualified",
            "Qualified",
            "条件付き",
            "Dora/red retention is supported; broad risk-buying for value needs tighter proof.",
            "ドラ/赤の保持は支持される。打点のための広いリスク購入は追加確認が必要。",
            "The value seed should improve a real winning route.",
            "打点種は実際の和了ルートを良くする時だけ残す。",
            "Example: keep red-five access when it also keeps tanyao or riichi value alive.",
            "例: 赤受けがタンヤオやリーチ打点も同時に残すなら価値がある。",
            [
                pattern(patterns, "keep_dora_or_red", "Dora/red material kept", "ドラ/赤保持"),
                pattern(patterns, "behind_risk_buy", "Behind-score risk buys", "ビハインド時のリスク購入"),
                conversion,
            ],
        ),
        point(
            "point-07",
            "Calls and Tempo",
            "鳴きとテンポ",
            "Tempo calls need a named purpose.",
            "テンポ鳴きには目的を付ける。",
            "qualified",
            "Qualified",
            "条件付き",
            "The outcome split supports active conversion; treat the call data as context evidence.",
            "成績差は能動的な変換を支持する。鳴きデータは文脈証拠として扱う。",
            "Use this as a review question for which speed tiles deserve calls.",
            "どのスピード牌を鳴く価値があるかを復習時の問いにする。",
            "Example: call for tenpai, yaku certainty, ippatsu break, or denial; skip when the call only makes a fragile one-away hand.",
            "例: テンパイ、役確定、一発消し、阻止なら鳴く。壊れやすい一向聴になるだけなら見送る。",
            [call_rate, call_riichi, middle_late],
        ),
        point(
            "point-08",
            "Value and Pressure",
            "打点と圧力",
            "Riichi converts value into pressure.",
            "リーチは打点を圧力に変える。",
            "qualified",
            "Qualified",
            "条件付き",
            "Top-half games used more riichi; the point is conversion quality over raw reach volume.",
            "上位半分はリーチ回数も多い。要点は回数より変換品質。",
            "Require value, pressure, or placement gain before turning the hand face-up.",
            "打点、圧力、着順変化のいずれかがある時だけ手を公開する。",
            "Example: riichi the hand that forces opponents to react; dama or fold when the declaration only buys a bad wait with no table pressure.",
            "例: 相手に対応を強制する手はリーチ。悪形だけで圧力がないならダマや撤退も見る。",
            [call_riichi, conversion, mismatch],
        ),
        point(
            "point-09",
            "Defense and Push-Fold",
            "守備と押し引き",
            "Reprice push-fold after every draw.",
            "押し引きは毎巡更新する。",
            "strong",
            "Strong",
            "強い",
            "The danger-delta split is highly significant in both directions.",
            "危険度差の分岐は両方向で有意。",
            "Update the price after each draw, call, riichi, and new safe tile.",
            "ツモ、鳴き、リーチ、新しい安全牌ごとに価格を更新する。",
            "Example: a tile that was an acceptable push before the second threat may become a fold after another opponent opens.",
            "例: 二件目の脅威が出る前なら押せた牌も、別の相手が鳴いた後は撤退牌になる。",
            [
                pattern(patterns, "safer_than_naga", "Lower-danger choices", "低危険選択"),
                pattern(patterns, "riskier_than_naga", "Higher-danger choices", "高危険選択"),
                pattern(patterns, "multi_threat_safe_tenpai", "Multi-threat exits", "多件脅威出口"),
            ],
        ),
        point(
            "point-10",
            "Late Game",
            "終盤",
            "Third-row precision is a separate skill.",
            "三段目の精度は別技能。",
            "qualified",
            "Qualified",
            "条件付き",
            "Late positions are numerous enough to validate as a training category; every late LuckyJ split still needs context.",
            "終盤局面は訓練カテゴリにできる母数がある。終盤 LuckyJ 分岐は文脈確認が必要。",
            "Cross-check third-row choices against points, safe tiles, and model disagreement.",
            "三段目は点数、安全牌、モデル不一致で必ず確認する。",
            "Example: when both tenpai and noten-bappu are live, compute the exact point swing before copying the push.",
            "例: テンパイ料とノーテン罰符が絡む時は、押す前に点差変化を正確に計算する。",
            [late_precision, pattern(patterns, "multi_threat_safe_tenpai", "Late/middle multiple-threat exits", "中終盤の多件脅威出口"), mismatch],
        ),
        point(
            "point-11",
            "Late Game",
            "終盤",
            "Drawn-hand points are attack value.",
            "流局点も攻撃価値。",
            "qualified",
            "Qualified",
            "条件付き",
            "Draw-tenpai frequency makes the objective real, but each push still needs a danger price.",
            "流局テンパイの頻度から目的は本物だが、各押しには危険値付けが必要。",
            "Chase keiten through multiple live threats only with safe exits.",
            "複数脅威への形式テンパイは出口がある時だけ追う。",
            "Example: keep a harmless tenpai route when folding; abandon it if the next discard must pass two dangerous waits.",
            "例: 降りながら無害なテンパイルートを残す。次打が二つの危険待ちを通すなら捨てる。",
            [drawn_hand, pattern(patterns, "multi_threat_safe_tenpai", "Safe-tenpai style exits", "安全テンパイ型の出口"), late_precision],
        ),
        point(
            "point-12",
            "Review",
            "復習",
            "Use model disagreement as a study prompt.",
            "モデル不一致は復習の問い。",
            "strong",
            "Strong",
            "強い",
            "The Nishiki mismatch base is large, and most mismatches stay below the severe-disagreement threshold.",
            "ニシキ不一致の母数は大きく、重い不一致は少数にとどまる。",
            "A split marks a hand to study; proof comes from the purchase, risk, and table context.",
            "分岐は復習対象を示す。根拠は購入価値、危険、場況から作る。",
            "Example: if LuckyJ, Nishiki, Hibakari, and Mortal disagree, write the purchase and the risk before adopting the move.",
            "例: LuckyJ、ニシキ、ヒバカリ、Mortal が割れたら、その打牌が何を買い、何を危険にするかを書く。",
            [mismatch, pattern(patterns, "safer_than_naga", "Safer-than-Nishiki subset", "ニシキより安全な部分集合"), pattern(patterns, "riskier_than_naga", "Riskier-than-Nishiki subset", "ニシキより危険な部分集合")],
        ),
        point(
            "point-13",
            "Calls and Yaku Conditions",
            "鳴きと役条件",
            "Hold back uncertain open-hand yaku conditions.",
            "未確定副露の役条件牌を先に扱う。",
            "strong",
            "Strong",
            "強い",
            "Loose honor cleanup is one of the strongest support signals.",
            "浮き字牌整理は最も強い裏付けの一つ。",
            "Split self-value yakuhai from opponent yaku-condition tiles before cutting.",
            "切る前に、自分の役牌価値と相手の役条件牌を分ける。",
            "Example: clean a lone live dragon before an opponent's open hand turns it into their missing yaku.",
            "例: 相手副露の足りない役になる前に、生牌の孤立三元牌を整理する。",
            [
                pattern(patterns, "honor_cleanup_vs_shape", "Loose honor cleanup", "浮き字牌整理"),
                self_yakuhai,
                pattern(patterns, "keep_pair_anchor", "Yakuhai/pair anchors", "役牌/対子支点"),
            ],
        ),
        point(
            "point-14",
            "Defense",
            "守備",
            "Keep genbutsu and suji exits for a named target.",
            "現物と筋の出口は対象を名付けて残す。",
            "strong",
            "Strong",
            "強い",
            "Threat-specific safety is strongly supported; generic safety retention needs a sharper target.",
            "対象付き安全牌保持は強く支持される。一般的な安全牌保持には対象の明確化が必要。",
            "The point must stay narrow: who is the exit for, and when will it be spent?",
            "対象と使う時期を必ず決める狭いルールにする。",
            "Example: keep suji only if it defends the current riichi or open hand and the hand can still act next turn.",
            "例: 現在のリーチ者や副露者に通る筋で、次巡も手が動く時だけ残す。",
            [
                pattern(patterns, "threat_keep_exit", "Exit for active threat", "実脅威への出口"),
                pattern(patterns, "keep_defensive_exit", "Generic safe-tile keep", "一般的な安全牌保持"),
                pattern(patterns, "multi_threat_safe_tenpai", "Multi-threat exits", "多件脅威出口"),
            ],
        ),
        point(
            "point-15",
            "Defense and Shape",
            "守備と形",
            "Spend stale safe tiles when their job expires.",
            "古い安全牌は仕事が切れたら使う。",
            "strong",
            "Strong",
            "強い",
            "Spending a safe-looking tile that Nishiki kept was materially better than the mismatch baseline.",
            "ニシキが残す安全寄り牌を使う分岐は、不一致平均との差で明確に良い。",
            "Spend it only after naming why it no longer defends the live danger.",
            "今の脅威に効かなくなった理由を名付けてから使う。",
            "Example: discard yesterday's genbutsu when a new riichi makes it irrelevant and the tile blocks your tenpai route.",
            "例: 新しいリーチで古い現物の対象が消え、テンパイルートを邪魔するなら使う。",
            [
                pattern(patterns, "spend_defensive_exit", "Stale safety spent", "古い安全牌の使用"),
                pattern(patterns, "threat_keep_exit", "Threat-specific keeps", "対象付き保持"),
                pattern(patterns, "keep_defensive_exit", "Generic keeps as caution", "一般保持の警告"),
            ],
        ),
        point(
            "point-16",
            "Shape and Defense",
            "形と守備",
            "Outside cuts can preserve the real route.",
            "外側切りで本線を残す。",
            "strong",
            "Strong",
            "強い",
            "Cutting outside material while keeping inside shape had strong aggregate support.",
            "外側を切って内側形を残す分岐は集計上強く支持された。",
            "Keep route preservation separate from vague safety.",
            "本線維持と曖昧な守備を分けて読む。",
            "Example: in danger, cut the edge tile that lowers exposure while preserving the live inner wait route.",
            "例: 危険下では、露出を下げながら本命内側待ちを残す外側牌を切る。",
            [
                pattern(patterns, "cut_outside_keep_inside", "Outside cut, inside route kept", "外側切り・内側ルート保持"),
                pattern(patterns, "cut_inside_keep_outside", "Middle cut as caution", "中張牌切りの警告"),
                pattern(patterns, "safer_than_naga", "Lower-danger choices", "低危険選択"),
            ],
        ),
        point(
            "point-17",
            "Defense",
            "守備",
            "A kept safe tile needs a target.",
            "残す安全牌には対象が必要。",
            "strong",
            "Strong",
            "強い",
            "This is the cleanest correction to the original safe-tile language.",
            "元の安全牌表現への最も明確な修正。",
            "The same tile flips from good to bad once its live-threat target changes.",
            "実脅威の対象が変わると、同じ安全牌でも良し悪しが反転する。",
            "Example: label a kept 9m as genbutsu to the dealer riichi with a named target.",
            "例: 残す9萬を親リーチへの現物として具体的に名付ける。",
            [
                pattern(patterns, "threat_keep_exit", "Named threat exit", "対象付き出口"),
                pattern(patterns, "multi_threat_safe_tenpai", "Multiple-threat exit", "多件脅威出口"),
                pattern(patterns, "keep_defensive_exit", "Untargeted keep caution", "対象なし保持の警告"),
            ],
        ),
        point(
            "point-18",
            "Calls and Honors",
            "鳴きと字牌",
            "Give every honor tile a role label.",
            "字牌には役割名を付ける。",
            "strong",
            "Strong",
            "強い",
            "Honor cleanup and pair-anchor stats support role labeling over a single honor rule.",
            "字牌整理と対子支点の統計は、単一の字牌ルールより役割名付けを支持する。",
            "Self yakuhai, opponent yaku condition, dead honor, and safe exit are different categories.",
            "自分役牌、相手の役条件、枯れ字牌、安全出口は別カテゴリ。",
            "Example: a lone dragon can be value seed, opponent yaku-condition liability, or safe exit depending on calls and rivers.",
            "例: 孤立三元牌は、鳴きと河次第で打点種、相手役条件、安全出口のどれにもなる。",
            [
                pattern(patterns, "honor_cleanup_vs_shape", "Loose honor cleanup", "浮き字牌整理"),
                pattern(patterns, "keep_pair_anchor", "Pair/triplet anchors", "対子/刻子支点"),
                self_yakuhai,
            ],
        ),
        point(
            "point-19",
            "Placement and Defense",
            "着順と守備",
            "Leader safety qualifies the plan.",
            "トップ目安全は計画の条件。",
            "qualified",
            "Qualified",
            "条件付き",
            "Leader low-risk choices were only mildly better than baseline; the stronger signal is controlled danger.",
            "トップ目の低危険選択は平均との差が小さい。より強い信号は危険の管理。",
            "Lower ambition when the discard also keeps the next turn playable.",
            "次巡も打てる形を保つ時だけ目標を下げる。",
            "Example: choose the low-risk tile that keeps a clean fold or cheap win.",
            "例: 安い和了かきれいな撤退を残す低危険牌を選ぶ。",
            [
                pattern(patterns, "leader_low_risk", "Leader low-risk choices", "トップ目低危険選択"),
                pattern(patterns, "riskier_than_naga", "Riskier-than-Nishiki caution", "高危険選択の警告"),
                conversion,
            ],
        ),
    ]

    for item in points:
        item["review_example"], item["review_example_ja"] = REVIEW_EXAMPLES[item["id"]]

    counts = Counter(item["strength"] for item in points)
    review_files = local_review_file_count()
    return {
        "generated_at": date.today().isoformat(),
        "method": {
            "source_files": [str(MODEL_PATH.relative_to(ROOT)), str(BOOK_PATH.relative_to(ROOT))],
            "qualitative_review_files": review_files,
            "eligible_decisions": review_decisions,
            "mismatches": review_mismatches,
            "book_decisions": summary["decisions"],
            "hands": summary["hands"],
            "games": summary["games"],
            "baseline_mismatch_bad_rate": review_bad_rate,
            "note": "Qualitative review examples were kept as generalized prompts only; statistical validity comes from the model and book artifacts.",
            "note_ja": "定性的な検討例は一般化した問いとしてだけ使い、統計的な妥当性はモデルと書籍由来のデータで確認した。",
        },
        "summary": {
            "strong": counts["strong"],
            "qualified": counts["qualified"],
            "review": counts["review"],
            "total": len(points),
        },
        "points": points,
    }


def write_markdown(data: dict[str, Any]) -> None:
    lines = [
        "# Point Validation - 2026-06-30",
        "",
        "## Method",
        "",
        f"- Source artifacts: {', '.join(data['method']['source_files'])}.",
        f"- Qualitative review files scanned locally: {data['method'].get('qualitative_review_files', 0):,}; raw captions/transcripts stay ignored under `tmp/`.",
        f"- Model base: {data['method']['eligible_decisions']:,} eligible decisions and {data['method']['mismatches']:,} LuckyJ/Nishiki mismatches.",
        f"- Book base: {data['method']['games']:,} hanchan, {data['method']['hands']:,} hands, {data['method']['book_decisions']:,} discard decisions.",
        "- A point is marked strong only when the proxy has a large sample, directionally useful lift, and a significant p-value. Mixed or aggregate-only points are marked qualified.",
        "",
        "## Results",
        "",
        f"- Strong: {data['summary']['strong']}.",
        f"- Qualified: {data['summary']['qualified']}.",
        f"- Review-only: {data['summary']['review']}.",
        "",
        "| Point | Category | Verdict | Main statistical read | Caveat |",
        "|---|---|---|---|---|",
    ]
    for item in data["points"]:
        read = item["read"].replace("|", "/")
        caveat = item["caveat"].replace("|", "/")
        lines.append(
            f"| {item['id']} | {item['category']} | {item['verdict']} | {read} | {caveat} |"
        )
    lines.extend(
        [
            "",
            "## Evidence Lines",
            "",
        ]
    )
    for item in data["points"]:
        lines.append(f"### {item['id']}: {item['title']}")
        lines.append("")
        for stat in item["stats"]:
            lines.append(f"- {stat['text']}")
        example = item["example"].removeprefix("Example: ")
        lines.append(f"- Example test: {example}")
        review_example = item["review_example"].removeprefix("Review example: ")
        lines.append(f"- Review-derived example: {review_example}")
        lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    data = build()
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(data)
    print(
        f"Wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)} "
        f"({data['summary']['strong']} strong, {data['summary']['qualified']} qualified)."
    )


if __name__ == "__main__":
    main()
