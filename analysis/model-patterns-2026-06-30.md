# Model-mined LuckyJ/NAGA/Mortal patterns - 2026-06-30

## Method

Command:

```bash
.venv/bin/python scripts/mine_model_patterns.py --mortal-per-pattern 10 --mortal-total 140 --output site/model-patterns.json
```

The script mines cached NAGA reports for LuckyJ draw-discard decisions where LuckyJ's real discard differs from NAGA's top discard. It excludes reach-declaration decisions and then tags each mismatch by coarse tactical pattern: safety retention, stale safety spend, outside-vs-inside shape, pair handling, score position, active threats, and dora/red-five retention.

The Mortal pass is a deterministic replay sample from local Mjai logs and the local Mortal/libriichi policy. It is a cross-check, not a source of broad frequencies.

Definitions:

- `bad_rate`: share of mismatches where NAGA assigned LuckyJ's actual discard below 5%.
- `bad_lift`: percentage-point change in `bad_rate` compared with other LuckyJ/NAGA mismatches. Negative is better.
- `danger_delta`: LuckyJ discard danger minus NAGA discard danger. Negative means LuckyJ's discard is safer by the local danger proxy.
- Mortal agreement columns count sampled positions where Mortal's top discard matched LuckyJ or NAGA.

## Overall result

- Eligible LuckyJ draw-discard decisions: 135,038.
- LuckyJ/NAGA discard mismatches: 36,206, or 26.8%.
- Among all mismatches, NAGA's severe-disagreement proxy was 31.0%.
- Among all mismatches, the large probability-gap rate was 56.1%.
- Mortal replay sample: 140 matched positions, 0 missing.

The main caution: Mortal mostly sided with NAGA on the sampled high-gap positions. That means these are discovery signals for candidate points, not proof that a broad LuckyJ rule is correct.

## Pattern ranking

| Pattern | N | Bad rate | Bad lift | Danger delta | Mortal LuckyJ | Mortal NAGA |
|---|---:|---:|---:|---:|---:|---:|
| Cut loose honor while NAGA keeps shape | 2,348 | 20.9% | -10.9 pp | -0.037 | 2/19 | 17/19 |
| Choose a lower-danger discard than NAGA | 3,741 | 21.8% | -10.2 pp | -0.149 | 10/59 | 47/59 |
| Keep pair/triplet anchor NAGA wants to break | 2,338 | 21.9% | -9.8 pp | -0.019 | 1/28 | 24/28 |
| Cut outside material while keeping inside shape | 5,281 | 23.1% | -9.2 pp | -0.030 | 8/52 | 42/52 |
| Keep a defensive exit against an active threat | 8,406 | 24.4% | -8.7 pp | +0.012 | 14/130 | 107/130 |
| Middle/late exits with multiple threats | 4,386 | 23.5% | -8.6 pp | -0.001 | 10/81 | 64/81 |
| Spend a safe-looking tile while NAGA keeps it | 4,057 | 23.9% | -8.0 pp | -0.035 | 3/10 | 6/10 |
| Keep dora/red-five material | 617 | 24.6% | -6.5 pp | -0.011 | 2/10 | 8/10 |
| Leader choices that do not add danger | 5,153 | 29.6% | -1.7 pp | -0.025 | 3/15 | 11/15 |
| Riskier than NAGA | 5,033 | 33.4% | +2.8 pp | +0.134 | 7/81 | 66/81 |
| Behind-score risk buy | 2,364 | 34.5% | +3.7 pp | +0.120 | 3/40 | 32/40 |
| Generic keep genbutsu/suji exit | 8,590 | 35.1% | +5.4 pp | +0.036 | 1/34 | 32/34 |
| Break pair earlier than NAGA | 4,318 | 35.9% | +5.6 pp | +0.021 | 5/39 | 31/39 |
| Cut middle tile while keeping outside/safety/yaku | 10,926 | 38.6% | +10.9 pp | +0.029 | 2/17 | 13/17 |

## Additional points worth drafting

1. Spend stale safety before it steals shape.

   The `spend_defensive_exit` pattern is one of the cleaner signals: 4,057 cases, 23.9% bad rate, -8.0 pp lift, and -0.035 average danger delta. Mortal only backed LuckyJ in 3 of 10 sampled cases, so this needs hand-picked examples, but it is a real point: a genbutsu/suji tile is not valuable just because it is safe. Its value depends on whether it protects against the current target and whether holding it damages the hand's next decision.

2. Late outside cuts can be route-preserving, not just timid.

   `cut_outside_keep_inside` had 5,281 cases, 23.1% bad rate, -9.2 pp lift, and -0.030 danger delta. The Mortal-agreeing examples include late 1s-vs-2s, 1p-vs-3p, and 9m-vs-6m decisions. This is a good new point if written narrowly: when the hand is already real and the table is dangerous, cutting the edge tile can preserve a live inner route while reducing immediate exposure.

3. Multi-threat defense is target-specific, not generic tile hoarding.

   `multi_threat_safe_tenpai` and `threat_keep_exit` both look better than the mismatch baseline, while generic `keep_defensive_exit` is worse than baseline. This directly changes the defense framing: LuckyJ keeping suji/genbutsu is only interesting when the tile is an exit against a live riichi/open threat and the timing is middle or late. Early, generic safety retention is not supported by this analysis.

4. Loose honor cleanup deserves a separate branch from open-hand contract cleanup.

   `honor_cleanup_vs_shape` was the best NAGA-side statistical pattern: 2,348 cases, 20.9% bad rate, -10.9 pp lift, and -0.037 danger delta. Mortal mostly sided with NAGA in the sample, so this should not become a blanket rule. It is still worth mining for examples that split loose self-yakuhai, opponent contract tiles, and dead honors.

5. Score-position safety is probably a drill, not a headline principle.

   `leader_low_risk` is mildly better than baseline and safer on average, but Mortal did not strongly back it. It should become a qualifier inside defense points: when leading, LuckyJ can accept lower route ambition only if the discard also does not increase danger.

## Do not promote yet

- Generic "keep genbutsu/suji because it is safe" is not supported. It had 8,590 cases but a 35.1% bad rate, +5.4 pp worse than other mismatches, and Mortal sided with NAGA in 32 of 34 sampled cases.
- Pair-anchor rules are unstable. Keeping pair anchors looks good by NAGA aggregate, but Mortal heavily rejected the sampled high-gap cases. Breaking pairs early is worse by both NAGA aggregate and Mortal sample. This needs hand-shape-specific subcategories before becoming a point.
- Behind-score risk buying is not strong enough as a broad point. It increases danger and is worse than baseline by NAGA's severe-disagreement proxy. Keep only sharply curated examples where the upside is concrete.

## Mortal-agreeing examples to review next

- `2023042214gm-0089-0000-ad521d37`, game 107, kyoku 7, left 16: LuckyJ/Mortal discard 1s, NAGA discard 2s.
- `2023042723gm-0029-0000-969cebce`, game 280, kyoku 8, left 22: LuckyJ/Mortal discard 1p, NAGA discard 3p.
- `2023042810gm-0029-0000-6cf0f648`, game 286, kyoku 8, left 7: LuckyJ/Mortal discard 5p, NAGA discard 4p.
- `2023043013gm-0029-0000-bbd6fa72`, game 352, kyoku 0, left 43: LuckyJ/Mortal discard 5m, NAGA discard P.
- `2023050217gm-0029-0000-bd0f6f3f`, game 427, kyoku 9, left 31: LuckyJ/Mortal discard 9s, NAGA discard 5p.
- `2023050323gm-0029-0000-a95fb42e`, game 472, kyoku 13, left 12: LuckyJ/Mortal discard 9m, NAGA discard 6m.
- `2023050714gm-0029-0000-542d2dff`, game 584, kyoku 6, left 27: LuckyJ/Mortal discard N, NAGA discard 1s.

## Next book edits

Use this analysis to add or refine points in this order:

1. Add a stale-safety point: "Safe tiles expire when they no longer defend the current danger."
2. Add a late outside-cut point: "Edge cuts can preserve the winning route under pressure."
3. Revise the existing defense language so suji/genbutsu retention is tied to specific threats and timing.
4. Extend the yakuhai cleanup point with subcases for self value, opponent contract tiles, and dead honors.
