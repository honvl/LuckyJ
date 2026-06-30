# Point Validation - 2026-06-30

## Method

- Source artifacts: site/model-patterns.json, site/book-data.json.
- Qualitative review files scanned locally: 34; raw captions/transcripts stay ignored under `tmp/`.
- Model base: 134,988 eligible decisions and 36,193 LuckyJ/Nishiki mismatches.
- Book base: 1,256 hanchan, 13,059 hands, 147,378 discard decisions.
- A point is marked strong only when the proxy has a large sample, directionally useful lift, and a significant p-value. Mixed or aggregate-only points are marked qualified.

## Results

- Strong: 11.
- Qualified: 8.
- Review-only: 0.

| Point | Category | Verdict | Main statistical read | Caveat |
|---|---|---|---|---|
| point-01 | Value and Placement | Qualified | Placement framing is valid, but the statistics reject a blanket 'push because behind' rule. | Require concrete upside and a discard that keeps danger manageable. |
| point-02 | Shape and Routes | Strong | Pair/triplet anchors and dora/red material had materially lower bad rates than other mismatches. | The support is strongest for anchors with a job. |
| point-03 | Calls and Yaku Conditions | Qualified | Aggregate results support purposeful calling; a broad call-more rule still needs proof. | Demand a named purpose: tenpai, yaku creation, value, denial, or safe-tenpai equity. |
| point-04 | Calls and Defense | Strong | Threat-specific exit retention was strong, while generic safe-tile hoarding was worse than baseline. | This point is target-specific: name the threat before keeping the exit. |
| point-05 | Shape and Defense | Strong | Safer-than-Nishiki choices were one of the clearest support signals; danger pricing should be explicit. | Keep this targeted: early slimming works when the tile has little value or yaku route left. |
| point-06 | Value and Routes | Qualified | Dora/red retention is supported; broad risk-buying for value needs tighter proof. | The value seed should improve a real winning route. |
| point-07 | Calls and Tempo | Qualified | The outcome split supports active conversion; treat the call data as context evidence. | Use this as a review question for which speed tiles deserve calls. |
| point-08 | Value and Pressure | Qualified | Top-half games used more riichi; the point is conversion quality over raw reach volume. | Require value, pressure, or placement gain before turning the hand face-up. |
| point-09 | Defense and Push-Fold | Strong | The danger-delta split is highly significant in both directions. | Update the price after each draw, call, riichi, and new safe tile. |
| point-10 | Late Game | Qualified | Late positions are numerous enough to validate as a training category; every late LuckyJ split still needs context. | Cross-check third-row choices against points, safe tiles, and model disagreement. |
| point-11 | Late Game | Qualified | Draw-tenpai frequency makes the objective real, but each push still needs a danger price. | Chase keiten through multiple live threats only with safe exits. |
| point-12 | Review | Strong | The Nishiki mismatch base is large, and most mismatches stay below the severe-disagreement threshold. | A split marks a hand to study; proof comes from the purchase, risk, and table context. |
| point-13 | Calls and Yaku Conditions | Strong | Loose honor cleanup is one of the strongest support signals. | Split self-value yakuhai from opponent yaku-condition tiles before cutting. |
| point-14 | Defense | Strong | Threat-specific safety is strongly supported; generic safety retention needs a sharper target. | The point must stay narrow: who is the exit for, and when will it be spent? |
| point-15 | Defense and Shape | Strong | Spending a safe-looking tile that Nishiki kept was materially better than the mismatch baseline. | Spend it only after naming why it no longer defends the live danger. |
| point-16 | Shape and Defense | Strong | Cutting outside material while keeping inside shape had strong aggregate support. | Keep route preservation separate from vague safety. |
| point-17 | Defense | Strong | This is the cleanest correction to the original safe-tile language. | The same tile flips from good to bad once its live-threat target changes. |
| point-18 | Calls and Honors | Strong | Honor cleanup and pair-anchor stats support role labeling over a single honor rule. | Self yakuhai, opponent yaku condition, dead honor, and safe exit are different categories. |
| point-19 | Placement and Defense | Qualified | Leader low-risk choices were only mildly better than baseline; the stronger signal is controlled danger. | Lower ambition when the discard also keeps the next turn playable. |

## Evidence Lines

### point-01: Start with placement before hand shape.

- Leader low-risk choices: n=5,153, bad 29.6%, lift -1.7 pp, p=0.0157, danger delta -0.025.
- Behind-score risk buys: n=2,364, bad 34.5%, lift +3.7 pp, p=0.0001, danger delta 0.120.
- Outcome split: top-half games averaged 3.09 wins and 0.75 deal-ins; bottom-half games averaged 1.39 wins and 1.48 deal-ins.
- Example test: as leader, a low-danger discard that preserves the next safe turn can beat a thin value upgrade.
- Review-derived example: in a South-round placement hand, a low-risk tile that keeps a clean fold or cheap win can beat a thin value upgrade.

### point-02: Keep more than one route alive.

- Kept pair/triplet anchors: n=2,338, bad 21.9%, lift -9.8 pp, p=<0.0001, danger delta -0.019.
- Kept dora/red-five material: n=617, bad 24.6%, lift -6.5 pp, p=0.0005, danger delta -0.011.
- Breaking pairs early: n=4,318, bad 35.9%, lift +5.6 pp, p=8.93e-14, danger delta 0.021.
- Example test: keep a yakuhai pair or red-five branch when it creates value plus an open fallback.
- Review-derived example: when one hand can become yakuhai, honitsu/chanta, or riichi, keep the anchor that preserves those futures over the prettiest one-route shape.

### point-03: Call bad shapes when the call changes the hand's job.

- Call opportunities became calls 35.8% of hands, so call points need purpose filters.
- Winning-half volume was active: calls/game 5.79 compared with 5.44, riichi/game 2.11 compared with 1.67.
- Middle plus late decisions total 80,537; the defense points have evidence beyond opening-row cleanup.
- Example test: chi when it creates a real yaku route or a safe tenpai path from the weak block.
- Review-derived example: call a bad block only when it creates yaku, tenpai, denial, or safe draw equity; skip the call that merely exposes a fragile one-away hand.

### point-04: Open hands still need exits.

- Threat-specific exits: n=8,406, bad 24.4%, lift -8.7 pp, p=<0.0001, danger delta 0.012.
- Middle/late multi-threat exits: n=4,386, bad 23.5%, lift -8.6 pp, p=<0.0001, danger delta -0.001.
- Generic safe-tile retention: n=8,590, bad 35.1%, lift +5.4 pp, p=<0.0001, danger delta 0.036.
- Example test: after opening, keep one genbutsu to the live riichi if the hand still has a real tenpai path.
- Review-derived example: after opening, keep an exit to the live threat if the hand can still reach tenpai; commitment still needs one clean brake.

### point-05: Price the future danger of floaters.

- Lower-danger discards: n=3,741, bad 21.8%, lift -10.2 pp, p=<0.0001, danger delta -0.149.
- Higher-danger discards: n=5,033, bad 33.4%, lift +2.8 pp, p=6.23e-05, danger delta 0.134.
- Outside cuts preserving inner route: n=5,281, bad 23.1%, lift -9.2 pp, p=<0.0001, danger delta -0.030.
- Example test: cut the future-riichi liability before it becomes the only discard your hand can release.
- Review-derived example: if a loose middle tile will become the only discard after riichi, cut it while the hand still has blocks and replacement routes.

### point-06: Build value from the first discard.

- Dora/red material kept: n=617, bad 24.6%, lift -6.5 pp, p=0.0005, danger delta -0.011.
- Behind-score risk buys: n=2,364, bad 34.5%, lift +3.7 pp, p=0.0001, danger delta 0.120.
- Outcome split: top-half games averaged 3.09 wins and 0.75 deal-ins; bottom-half games averaged 1.39 wins and 1.48 deal-ins.
- Example test: keep red-five access when it also keeps tanyao or riichi value alive.
- Review-derived example: keep red or dora access when it improves a real winning route; release it when the extra value is decorative and the next danger is concrete.

### point-07: Tempo calls need a named purpose.

- Call opportunities became calls 35.8% of hands, so call points need purpose filters.
- Winning-half volume was active: calls/game 5.79 compared with 5.44, riichi/game 2.11 compared with 1.67.
- Middle plus late decisions total 80,537; the defense points have evidence beyond opening-row cleanup.
- Example test: call for tenpai, yaku certainty, ippatsu break, or denial; skip when the call only makes a fragile one-away hand.
- Review-derived example: a tempo call is valid when it creates tenpai, yaku certainty, denial, or an ippatsu break; raw speed needs an actual payoff.

### point-08: Riichi converts value into pressure.

- Winning-half volume was active: calls/game 5.79 compared with 5.44, riichi/game 2.11 compared with 1.67.
- Outcome split: top-half games averaged 3.09 wins and 0.75 deal-ins; bottom-half games averaged 1.39 wins and 1.48 deal-ins.
- Model review base: 36,193 LuckyJ/Nishiki mismatches from 134,988 split-head decisions; only 31.0% hit the severe-disagreement proxy.
- Example test: riichi the hand that forces opponents to react; dama or fold when the declaration only buys a bad wait with no table pressure.
- Review-derived example: declare when the hand's value and wait force opponents to react; stay flexible when riichi only exposes a bad route with little pressure.

### point-09: Reprice push-fold after every draw.

- Lower-danger choices: n=3,741, bad 21.8%, lift -10.2 pp, p=<0.0001, danger delta -0.149.
- Higher-danger choices: n=5,033, bad 33.4%, lift +2.8 pp, p=6.23e-05, danger delta 0.134.
- Multi-threat exits: n=4,386, bad 23.5%, lift -8.6 pp, p=<0.0001, danger delta -0.001.
- Example test: a tile that was an acceptable push before the second threat may become a fold after another opponent opens.
- Review-derived example: a one-chance or suji label can flip after a second threat, new call, or suit-constrained river; reprice the tile before pushing.

### point-10: Third-row precision is a separate skill.

- Late row remained dense enough to matter: 19,978 decisions, mismatch 27.9%, bad 6.6%.
- Late/middle multiple-threat exits: n=4,386, bad 23.5%, lift -8.6 pp, p=<0.0001, danger delta -0.001.
- Model review base: 36,193 LuckyJ/Nishiki mismatches from 134,988 split-head decisions; only 31.0% hit the severe-disagreement proxy.
- Example test: when both tenpai and noten-bappu are live, compute the exact point swing before copying the push.
- Review-derived example: third-row choices need exact tenpai, noten, deal-in, and placement arithmetic; copy a late push after the point swing is clear.

### point-11: Drawn-hand points are attack value.

- Draw-tenpai-plus rounds occurred in 40.6% of hands, making noten-bappu a real objective.
- Safe-tenpai style exits: n=4,386, bad 23.5%, lift -8.6 pp, p=<0.0001, danger delta -0.001.
- Late row remained dense enough to matter: 19,978 decisions, mismatch 27.9%, bad 6.6%.
- Example test: keep a harmless tenpai route when folding; abandon it if the next discard must pass two dangerous waits.
- Review-derived example: preserve a harmless route to drawn-hand tenpai, but abandon it when the next discard must pass multiple live threats.

### point-12: Use model disagreement as a study prompt.

- Model review base: 36,193 LuckyJ/Nishiki mismatches from 134,988 split-head decisions; only 31.0% hit the severe-disagreement proxy.
- Safer-than-Nishiki subset: n=3,741, bad 21.8%, lift -10.2 pp, p=<0.0001, danger delta -0.149.
- Riskier-than-Nishiki subset: n=5,033, bad 33.4%, lift +2.8 pp, p=6.23e-05, danger delta 0.134.
- Example test: if LuckyJ, Nishiki, Hibakari, and Mortal disagree, write the purchase and the risk before adopting the move.
- Review-derived example: when models split, write the purchased value, safety, and route count before calling the move good or bad.

### point-13: Hold back uncertain open-hand yaku conditions.

- Loose honor cleanup: n=2,348, bad 20.9%, lift -10.9 pp, p=<0.0001, danger delta -0.037.
- Loose self-yakuhai timing split: no-open contexts cut singletons on median turn 3.0, while tanyao-shaped open contexts delayed to turn 9.0.
- Yakuhai/pair anchors: n=2,338, bad 21.9%, lift -9.8 pp, p=<0.0001, danger delta -0.019.
- Example test: clean a lone live dragon before an opponent's open hand turns it into their missing yaku.
- Review-derived example: a lone dragon or seat wind changes price when an opponent's open hand still lacks a visible yaku.

### point-14: Keep genbutsu and suji exits for a named target.

- Exit for active threat: n=8,406, bad 24.4%, lift -8.7 pp, p=<0.0001, danger delta 0.012.
- Generic safe-tile keep: n=8,590, bad 35.1%, lift +5.4 pp, p=<0.0001, danger delta 0.036.
- Multi-threat exits: n=4,386, bad 23.5%, lift -8.6 pp, p=<0.0001, danger delta -0.001.
- Example test: keep suji only if it defends the current riichi or open hand and the hand can still act next turn.
- Review-derived example: keep genbutsu or suji only after naming the target player and the next turn it protects.

### point-15: Spend stale safe tiles when their job expires.

- Stale safety spent: n=4,057, bad 23.9%, lift -8.0 pp, p=<0.0001, danger delta -0.035.
- Threat-specific keeps: n=8,406, bad 24.4%, lift -8.7 pp, p=<0.0001, danger delta 0.012.
- Generic keeps as caution: n=8,590, bad 35.1%, lift +5.4 pp, p=<0.0001, danger delta 0.036.
- Example test: discard yesterday's genbutsu when a new riichi makes it irrelevant and the tile blocks your tenpai route.
- Review-derived example: yesterday's safe tile loses value when a new riichi becomes the real threat and the old tile blocks your tenpai route.

### point-16: Outside cuts can preserve the real route.

- Outside cut, inside route kept: n=5,281, bad 23.1%, lift -9.2 pp, p=<0.0001, danger delta -0.030.
- Middle cut as caution: n=10,926, bad 38.6%, lift +10.9 pp, p=<0.0001, danger delta 0.029.
- Lower-danger choices: n=3,741, bad 21.8%, lift -10.2 pp, p=<0.0001, danger delta -0.149.
- Example test: in danger, cut the edge tile that lowers exposure while preserving the live inner wait route.
- Review-derived example: under pressure, an edge discard can reduce exposure while preserving the inner connector that actually wins the hand.

### point-17: A kept safe tile needs a target.

- Named threat exit: n=8,406, bad 24.4%, lift -8.7 pp, p=<0.0001, danger delta 0.012.
- Multiple-threat exit: n=4,386, bad 23.5%, lift -8.6 pp, p=<0.0001, danger delta -0.001.
- Untargeted keep caution: n=8,590, bad 35.1%, lift +5.4 pp, p=<0.0001, danger delta 0.036.
- Example test: label a kept 9m as genbutsu to the dealer riichi with a named target.
- Review-derived example: label the kept tile as safe against the dealer riichi, the open child, or no one; the last category should usually be spent.

### point-18: Give every honor tile a role label.

- Loose honor cleanup: n=2,348, bad 20.9%, lift -10.9 pp, p=<0.0001, danger delta -0.037.
- Pair/triplet anchors: n=2,338, bad 21.9%, lift -9.8 pp, p=<0.0001, danger delta -0.019.
- Loose self-yakuhai timing split: no-open contexts cut singletons on median turn 3.0, while tanyao-shaped open contexts delayed to turn 9.0.
- Example test: a lone dragon can be value seed, opponent yaku-condition liability, or safe exit depending on calls and rivers.
- Review-derived example: classify each honor as self value, opponent yaku condition, dead material, or defensive exit before cutting.

### point-19: Leader safety qualifies the plan.

- Leader low-risk choices: n=5,153, bad 29.6%, lift -1.7 pp, p=0.0157, danger delta -0.025.
- Riskier-than-Nishiki caution: n=5,033, bad 33.4%, lift +2.8 pp, p=6.23e-05, danger delta 0.134.
- Outcome split: top-half games averaged 3.09 wins and 0.75 deal-ins; bottom-half games averaged 1.39 wins and 1.48 deal-ins.
- Example test: choose the low-risk tile that keeps a clean fold or cheap win.
- Review-derived example: as leader, lower ambition when the discard also keeps a clean next turn and fits the placement target.
