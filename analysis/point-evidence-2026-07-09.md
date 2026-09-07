# Point Evidence Audit - 2026-09-07

## Method

- Source artifacts: site/model-patterns.json, site/book-data.json.
- Qualitative review files scanned locally: 34; raw captions/transcripts stay ignored under `tmp/`.
- Model base: 134,951 eligible decisions and 36,184 LuckyJ/Nishiki mismatches.
- Book base: 1,255 hanchan, 13,054 hands, 147,337 discard decisions.
- Scope warning: These cards measure Nishiki acceptance patterns, not winning EV or causal performance. Decisions within a hanchan are clustered, patterns overlap, and displayed p-values are unadjusted.

## Results

- Proxy-supported: 9.
- Context-qualified: 6.
- Contested showcase: 0.
- Review-only: 1.

| Point | Category | Verdict | Main statistical read | Caveat |
|---|---|---|---|---|
| point-01 | Value and Placement | Context-qualified | Placement framing is valid, but it is only useful when it changes concrete danger, value, or next-turn safety. | Leader safety is a qualifier, not a standalone excuse to kill shape. |
| point-02 | Shape and Routes | Proxy-supported | Pair/triplet anchors and dora/red material had materially lower Nishiki severe-disagreement rates than other mismatches. | The support is strongest for anchors with a job. |
| point-03 | Calls and Yaku Conditions | Context-qualified | Aggregate results support purposeful calling; bad-shape repair and tempo belong under the same named-purpose rule. | Demand a named purpose: tenpai, yaku creation, value, denial, or safe-tenpai equity. |
| point-04 | Calls and Defense | Proxy-supported | Threat-specific safe-tile retention was strong, while generic safe-tile hoarding was worse than baseline. | This point is target-specific: name the threat before keeping the tile. |
| point-05 | Shape and Defense | Proxy-supported | Safer-than-Nishiki choices were one of the clearest support signals; danger pricing should be explicit. | Keep this targeted: early slimming works when the tile has little value or yaku route left. |
| point-06 | Value and Routes | Context-qualified | Dora/red retention is supported; broad risk-buying for value needs tighter proof. | The value seed should improve a real winning route. |
| point-08 | Value and Pressure | Context-qualified | Top-half games used more riichi; the point is conversion quality over raw reach volume. | Require value, pressure, or placement gain before turning the hand face-up. |
| point-09 | Defense and Push-Fold | Proxy-supported | The danger-delta split is highly significant in both directions. | Update the price after each draw, call, riichi, and new safe tile. |
| point-10 | Late Game | Context-qualified | Late positions are numerous enough to validate as a training category; every late LuckyJ split still needs context. | Cross-check third-row choices against points, safe tiles, and model disagreement. |
| point-11 | Late Game | Context-qualified | Draw-tenpai frequency makes the objective real, but each push still needs a danger price. | Chase keiten through multiple live threats only with safe tiles. |
| point-12 | Review | Review-only | The Nishiki mismatch base is large, and most mismatches stay below the severe-disagreement threshold. | A split marks a hand to study; proof comes from the purchase, risk, and table context. |
| point-13 | Calls and Yaku Conditions | Proxy-supported | Broad honor cleanup is proxy-supported, but the selected open-hand examples are contested by Mortal. | Discarding offers the pon. Treat this as a timing study, early release versus later choke, not as denial. |
| point-14 | Defense | Proxy-supported | Threat-specific safety is strongly supported; generic safety retention only works after naming the target. | The point must stay narrow: who is the tile for, when will it be spent, and what shape cost does it impose? |
| point-15 | Defense and Shape | Proxy-supported | Spending a safe-looking tile that Nishiki kept was materially better than the mismatch baseline. | Spend it only after naming why it no longer defends the live danger. |
| point-16 | Shape and Defense | Proxy-supported | Cutting outside material while keeping inside shape had strong aggregate support. | Keep route preservation separate from vague safety. |
| point-18 | Calls and Honors | Proxy-supported | Honor cleanup and pair-anchor stats support role labeling over a single honor rule. | Self yakuhai, opponent yaku condition, dead honor, and safe tile are different categories. |

## Evidence Lines

### point-01: Start with placement before hand shape.

- Leader low-risk choices: n=5,153, Nishiki severe-disagreement rate 29.6%, difference vs other mismatches -1.7 pp, unadjusted p=0.0155, danger delta -0.025.
- Riskier-than-Nishiki caution: n=5,032, Nishiki severe-disagreement rate 33.4%, difference vs other mismatches +2.8 pp, unadjusted p=6.95e-05, danger delta 0.134.
- Behind-score risk buys: n=2,363, Nishiki severe-disagreement rate 34.5%, difference vs other mismatches +3.7 pp, unadjusted p=0.0002, danger delta 0.120.
- Outcome split: top-half games averaged 3.09 wins and 0.75 deal-ins; bottom-half games averaged 1.39 wins and 1.48 deal-ins.
- Selected-example Mortal check: 6/10 support LuckyJ.
- Example test: as leader, a low-danger discard that preserves the next safe turn can beat a thin value upgrade when it still fits the hand's placement job.
- Review-derived example: in a South-round placement hand, a low-risk tile that keeps a clean fold or cheap win can beat a thin value upgrade, but only when it still answers real danger.

### point-02: Keep more than one route alive.

- Kept pair/triplet anchors: n=2,338, Nishiki severe-disagreement rate 21.9%, difference vs other mismatches -9.8 pp, unadjusted p=<0.0001, danger delta -0.019.
- Kept dora/red-five material: n=617, Nishiki severe-disagreement rate 24.6%, difference vs other mismatches -6.5 pp, unadjusted p=0.0005, danger delta -0.011.
- Breaking pairs early: n=4,315, Nishiki severe-disagreement rate 35.9%, difference vs other mismatches +5.6 pp, unadjusted p=9.15e-14, danger delta 0.021.
- Selected-example Mortal check: 4/10 support LuckyJ.
- Example test: keep a yakuhai pair or red-five branch when it creates value plus an open fallback.
- Review-derived example: when one hand can become yakuhai, honitsu/chanta, or riichi, keep the anchor that preserves those futures over the prettiest one-route shape.

### point-03: Call bad shapes when the call changes the hand's job.

- Call opportunities became calls 35.8% of hands, so call points need purpose filters.
- Winning-half volume was active: calls/game 5.80 compared with 5.44, riichi/game 2.11 compared with 1.67.
- Middle plus late decisions total 80,521; the defense points have evidence beyond opening-row cleanup.
- Selected-example Mortal check: 10/10 support LuckyJ.
- Example test: call when it creates a real yaku route, changes the round clock, or gives a safe tenpai path from the weak block.
- Review-derived example: call a bad block only when it creates yaku, tenpai, denial, tempo pressure, or safe draw equity; skip the call that merely exposes a fragile one-away hand.

### point-04: Open hands still need safe tiles.

- Actual open-hand scope: 6,021 LuckyJ/Nishiki discard splits; LuckyJ retained a classified defensive tile in 3,536, including 1,723 tied to a live threat.
- Threat-specific safe tiles: n=7,618, Nishiki severe-disagreement rate 24.3%, difference vs other mismatches -8.6 pp, unadjusted p=<0.0001, danger delta 0.018.
- Middle/late multi-threat tiles: n=4,185, Nishiki severe-disagreement rate 23.6%, difference vs other mismatches -8.4 pp, unadjusted p=<0.0001, danger delta 0.003.
- Generic safe-tile retention: n=8,547, Nishiki severe-disagreement rate 35.4%, difference vs other mismatches +5.7 pp, unadjusted p=<0.0001, danger delta 0.045.
- Selected-example Mortal check: 2/10 support LuckyJ.
- Example test: after opening, keep one genbutsu to the live riichi if the hand still has a real tenpai path.
- Review-derived example: after opening, keep a safe tile for the live threat if the hand can still reach tenpai; commitment still needs one clean brake.

### point-05: Price the future danger of floaters.

- Lower-danger discards: n=3,740, Nishiki severe-disagreement rate 21.8%, difference vs other mismatches -10.2 pp, unadjusted p=<0.0001, danger delta -0.149.
- Higher-danger discards: n=5,032, Nishiki severe-disagreement rate 33.4%, difference vs other mismatches +2.8 pp, unadjusted p=6.95e-05, danger delta 0.134.
- Outside cuts preserving inner route: n=5,276, Nishiki severe-disagreement rate 23.1%, difference vs other mismatches -9.2 pp, unadjusted p=<0.0001, danger delta -0.030.
- Selected-example Mortal check: 8/10 support LuckyJ.
- Example test: cut the future-riichi liability before it becomes the only discard your hand can release.
- Review-derived example: if a loose middle tile will become the only discard after riichi, cut it while the hand still has blocks and replacement routes.

### point-06: Build value from the first discard.

- Dora/red material kept: n=617, Nishiki severe-disagreement rate 24.6%, difference vs other mismatches -6.5 pp, unadjusted p=0.0005, danger delta -0.011.
- Behind-score risk buys: n=2,363, Nishiki severe-disagreement rate 34.5%, difference vs other mismatches +3.7 pp, unadjusted p=0.0002, danger delta 0.120.
- Outcome split: top-half games averaged 3.09 wins and 0.75 deal-ins; bottom-half games averaged 1.39 wins and 1.48 deal-ins.
- Selected-example Mortal check: 6/10 support LuckyJ.
- Example test: keep red-five access when it also keeps tanyao or riichi value alive.
- Review-derived example: keep red or dora access when it improves a real winning route; release it when the extra value is decorative and the next danger is concrete.

### point-08: Riichi converts value into pressure.

- Winning-half volume was active: calls/game 5.80 compared with 5.44, riichi/game 2.11 compared with 1.67.
- Outcome split: top-half games averaged 3.09 wins and 0.75 deal-ins; bottom-half games averaged 1.39 wins and 1.48 deal-ins.
- Model review base: 36,184 LuckyJ/Nishiki mismatches from 134,951 split-head decisions; only 31.0% hit the severe-disagreement proxy.
- Selected-example Mortal check: 9/10 support LuckyJ. Declaration support only for riichi examples.
- Example test: riichi the hand that forces opponents to react; dama or fold when the declaration only buys a bad wait with no table pressure.
- Review-derived example: declare when the hand's value and wait force opponents to react; stay flexible when riichi only exposes a bad route with little pressure.

### point-09: Reprice push-fold after every draw.

- Lower-danger choices: n=3,740, Nishiki severe-disagreement rate 21.8%, difference vs other mismatches -10.2 pp, unadjusted p=<0.0001, danger delta -0.149.
- Higher-danger choices: n=5,032, Nishiki severe-disagreement rate 33.4%, difference vs other mismatches +2.8 pp, unadjusted p=6.95e-05, danger delta 0.134.
- Multi-threat tiles: n=4,185, Nishiki severe-disagreement rate 23.6%, difference vs other mismatches -8.4 pp, unadjusted p=<0.0001, danger delta 0.003.
- Selected-example Mortal check: 8/10 support LuckyJ.
- Example test: a tile that was an acceptable push before the second threat may become a fold after another opponent opens.
- Review-derived example: a one-chance or suji label can flip after a second threat, new call, or suit-constrained river; reprice the tile before pushing.

### point-10: Third-row precision is a separate skill.

- Late row remained dense enough to matter: 19,978 decisions, mismatch 27.9%, Nishiki severe disagreement 6.6%.
- Late/middle multiple-threat tiles: n=4,185, Nishiki severe-disagreement rate 23.6%, difference vs other mismatches -8.4 pp, unadjusted p=<0.0001, danger delta 0.003.
- Model review base: 36,184 LuckyJ/Nishiki mismatches from 134,951 split-head decisions; only 31.0% hit the severe-disagreement proxy.
- Selected-example Mortal check: 10/10 support LuckyJ.
- Example test: when both tenpai and noten-bappu are live, compute the exact point swing before copying the push.
- Review-derived example: third-row choices need exact tenpai, noten, deal-in, and placement arithmetic; copy a late push after the point swing is clear.

### point-11: Drawn-hand points are attack value.

- LuckyJ was tenpai in 823 of 1,761 recorded wall-exhausted draws (46.7%), making noten-bappu a real objective.
- Safe-tenpai style tiles: n=4,185, Nishiki severe-disagreement rate 23.6%, difference vs other mismatches -8.4 pp, unadjusted p=<0.0001, danger delta 0.003.
- Late row remained dense enough to matter: 19,978 decisions, mismatch 27.9%, Nishiki severe disagreement 6.6%.
- Selected-example Mortal check: 4/10 support LuckyJ.
- Example test: keep a harmless tenpai route when folding; abandon it if the next discard must pass two dangerous waits.
- Review-derived example: preserve a harmless route to drawn-hand tenpai, but abandon it when the next discard must pass multiple live threats.

### point-12: Use model disagreement as a study prompt.

- Model review base: 36,184 LuckyJ/Nishiki mismatches from 134,951 split-head decisions; only 31.0% hit the severe-disagreement proxy.
- Safer-than-Nishiki subset: n=3,740, Nishiki severe-disagreement rate 21.8%, difference vs other mismatches -10.2 pp, unadjusted p=<0.0001, danger delta -0.149.
- Riskier-than-Nishiki subset: n=5,032, Nishiki severe-disagreement rate 33.4%, difference vs other mismatches +2.8 pp, unadjusted p=6.95e-05, danger delta 0.134.
- Selected-example Mortal check: 2/10 support LuckyJ.
- Example test: if LuckyJ, Nishiki, Hibakari, and Mortal disagree, write the purchase and the risk before adopting the move.
- Review-derived example: when models split, write the purchased value, safety, and route count before calling the move good or bad.

### point-13: Price the missing yakuhai.

- Loose honor cleanup: n=2,346, Nishiki severe-disagreement rate 20.8%, difference vs other mismatches -10.9 pp, unadjusted p=<0.0001, danger delta -0.037.
- Loose self-yakuhai timing split: no-open contexts cut singletons on median turn 4.0, while tanyao-shaped open contexts delayed to turn 10.0.
- Yakuhai/pair anchors: n=2,338, Nishiki severe-disagreement rate 21.9%, difference vs other mismatches -9.8 pp, unadjusted p=<0.0001, danger delta -0.019.
- Selected-example Mortal check: 2/10 support LuckyJ.
- Example test: release a lone live dragon only while no yaku or clear advancement is visible; choke it once advancement becomes visible unless placement favors feeding.
- Review-derived example: a lone dragon or seat wind changes price when an opponent's open hand still lacks a visible yaku.

### point-14: Keep genbutsu and suji tiles for a named target.

- Tile for active threat: n=7,618, Nishiki severe-disagreement rate 24.3%, difference vs other mismatches -8.6 pp, unadjusted p=<0.0001, danger delta 0.018.
- Generic safe-tile keep: n=8,547, Nishiki severe-disagreement rate 35.4%, difference vs other mismatches +5.7 pp, unadjusted p=<0.0001, danger delta 0.045.
- Multi-threat tiles: n=4,185, Nishiki severe-disagreement rate 23.6%, difference vs other mismatches -8.4 pp, unadjusted p=<0.0001, danger delta 0.003.
- Selected-example Mortal check: 3/10 support LuckyJ.
- Example test: keep suji only if it defends the current riichi or open hand, and spend it when its live-threat target expires.
- Review-derived example: keep genbutsu or suji only after naming the target player and the next turn it protects; untargeted safety is just clutter.

### point-15: Spend stale safe tiles when their job expires.

- Stale safety spent: n=4,353, Nishiki severe-disagreement rate 22.6%, difference vs other mismatches -9.6 pp, unadjusted p=<0.0001, danger delta -0.050.
- Threat-specific keeps: n=7,618, Nishiki severe-disagreement rate 24.3%, difference vs other mismatches -8.6 pp, unadjusted p=<0.0001, danger delta 0.018.
- Generic keeps as caution: n=8,547, Nishiki severe-disagreement rate 35.4%, difference vs other mismatches +5.7 pp, unadjusted p=<0.0001, danger delta 0.045.
- Selected-example Mortal check: 1/10 support LuckyJ.
- Example test: discard yesterday's genbutsu when a new riichi makes it irrelevant and the tile blocks your tenpai route.
- Review-derived example: yesterday's safe tile loses value when a new riichi becomes the real threat and the old tile blocks your tenpai route.

### point-16: Outside cuts can preserve the real route.

- Outside cut, inside route kept: n=5,276, Nishiki severe-disagreement rate 23.1%, difference vs other mismatches -9.2 pp, unadjusted p=<0.0001, danger delta -0.030.
- Middle cut as caution: n=10,925, Nishiki severe-disagreement rate 38.6%, difference vs other mismatches +10.9 pp, unadjusted p=<0.0001, danger delta 0.029.
- Lower-danger choices: n=3,740, Nishiki severe-disagreement rate 21.8%, difference vs other mismatches -10.2 pp, unadjusted p=<0.0001, danger delta -0.149.
- Selected-example Mortal check: 7/10 support LuckyJ.
- Example test: in danger, cut the edge tile that lowers exposure while preserving the live inner wait route.
- Review-derived example: under pressure, an edge discard can reduce exposure while preserving the inner connector that actually wins the hand.

### point-18: Give every honor tile a role label.

- Loose honor cleanup: n=2,346, Nishiki severe-disagreement rate 20.8%, difference vs other mismatches -10.9 pp, unadjusted p=<0.0001, danger delta -0.037.
- Pair/triplet anchors: n=2,338, Nishiki severe-disagreement rate 21.9%, difference vs other mismatches -9.8 pp, unadjusted p=<0.0001, danger delta -0.019.
- Loose self-yakuhai timing split: no-open contexts cut singletons on median turn 4.0, while tanyao-shaped open contexts delayed to turn 10.0.
- Selected-example Mortal check: 6/10 support LuckyJ.
- Example test: a lone dragon can be value seed, opponent yaku-condition liability, or safe tile depending on calls and rivers.
- Review-derived example: classify each honor as self value, opponent yaku condition, dead material, or defensive tile before cutting.
