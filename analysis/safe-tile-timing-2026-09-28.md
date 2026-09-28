# When LuckyJ starts keeping safe tiles (28 September 2026)

The question, from a reader: on what turn does LuckyJ start collecting defensive tiles? The book
section `#safe-tile-timing` in `site/points.html` and `site/ja.html` answers it from the figures
here. Figures: `analysis/safe-tile-timing-2026-09-28.json`, written by
`scripts/mine_safe_tile_timing.py` from the cached NAGA reports of the 1,255 reviewed games. The
charts are drawn from its `summary_turns` block by `scripts/build_safe_tile_timing_figures.py`.

## Data and definitions

- **Sample.** Every kyoku where LuckyJ is not dealer: 9,745 kyoku
  (3,309 dealer kyoku skipped). LuckyJ's own discards 1 to 18,
  counted in its own discard order (a discard after a call counts). Decisions after its own riichi
  are left out.
- **Safe** means the tile is already in at least one opponent's river (genbutsu against at least one
  opponent). **Live** means it is in no opponent's river. This is not safety against a specific
  threat; Point 13 covers that.
- **Leftover (floater).** A single tile in hand (no pair) with no tile of its suit within two ranks.
  Honors count only when they are guest winds: dragons, LuckyJ's seat wind and the round wind are
  excluded, because LuckyJ keeps those for yaku and they would look like defensive retention.
  Terminals are 1 and 9; middle tiles are 2 to 8.
- **Quiet** means no opponent in riichi and no opponent with two or more calls. Otherwise the table is
  a **threat** table.
- **The choice.** A discard counts when the hand holds a safe and a live leftover of the same kind
  (any kind for the threat panel) and LuckyJ throws one of them. The rate is the share of those
  choices where it threw the live one and kept the safe one. **NAGA** is the Nishiki head's top pick
  (`dahai_pred[0]`) at the same decision.

## Why same kind

On the first discards the safe leftovers are mostly guest winds, which LuckyJ throws early anyway,
while the live leftovers include terminals and middle tiles. Pooling the kinds put the start of
collecting at the fourth discard; split by kind, terminals and middle tiles are kept from the first.

## Why a fitted curve instead of bands

The first version of the chart pooled discards into bands (1-2, 3-5, 6-8, 9-12, 13-18). A reader
pointed out that the bands were arbitrary. The chart now shows one point per discard and a fitted
curve: a binomial logistic regression of the choice on a natural cubic spline of the discard number,
with 1, 2 or 3 degrees of freedom chosen by AIC, fitted over the longest run of discards that each
have at least 10 choices. The 95% band uses the fit's covariance, scaled by the
Pearson dispersion where it exceeds 1. The fit moved one conclusion: the safe middle tile starts to
go first from about the seventh discard (the curve crosses 50% at 6.7), where the bands had put it at
the ninth.

## Per discard, with the fits

### Guest winds, quiet table

Fitted over discards 1 to 8. LuckyJ: 2 degree(s) of freedom (AIC by df {'1': 37.434, '2': 11.163, '3': 12.201}), dispersion 1.065; NAGA: 2 (AIC {'1': 14.976, '2': 14.605, '3': 16.207}), dispersion 1.523.
LuckyJ's curve crosses 50%: at discard 2.46, going up. NAGA's: never in the fitted range.

| discard | LuckyJ kept safe (choices) | LuckyJ fit [95% range] | NAGA kept safe (choices) | NAGA fit |
|---|---|---|---|---|
| 1 | 17.0% (282) | 17.9% [14.1-22.6] | 61.1% (334) | 60.0% |
| 2 | 42.5% (113) | 38.9% [33.7-44.4] | 54.2% (144) | 59.7% |
| 3 | 59.6% (52) | 62.2% [54.0-69.7] | 64.6% (65) | 60.4% |
| 4 | 81.2% (32) | 76.9% [68.3-83.8] | 72.7% (33) | 62.6% |
| 5 | 81.2% (16) | 82.5% [74.8-88.2] | 71.4% (21) | 67.3% |
| 6 | 68.0% (25) | 81.1% [73.0-87.2] | 62.1% (29) | 74.1% |
| 7 | 86.7% (15) | 73.9% [60.6-83.9] | 80.0% (15) | 81.5% |
| 8 | 61.5% (13) | 61.4% [38.7-80.0] | 100.0% (9) | 87.6% |
| 9 | 50.0% (6) |  | 40.0% (5) |  |
| 10 | 50.0% (4) |  | 66.7% (3) |  |
| 11 | 100.0% (3) |  | 75.0% (4) |  |
| 12 | 0.0% (3) |  | 0.0% (2) |  |
| 13 | 0.0% (1) |  |  (0) |  |
| 15 | 0.0% (1) |  | 0.0% (1) |  |

### Terminals, quiet table

Fitted over discards 1 to 9. LuckyJ: 1 degree(s) of freedom (AIC by df {'1': 8.543, '2': 10.537, '3': 12.511}), dispersion 1.0; NAGA: 1 (AIC {'1': 11.832, '2': 12.611, '3': 14.059}), dispersion 1.074.
LuckyJ's curve crosses 50%: never in the fitted range. NAGA's: never in the fitted range.

| discard | LuckyJ kept safe (choices) | LuckyJ fit [95% range] | NAGA kept safe (choices) | NAGA fit |
|---|---|---|---|---|
| 1 | 75.2% (222) | 74.5% [70.1-78.4] | 62.0% (150) | 63.5% |
| 2 | 72.7% (227) | 72.9% [69.3-76.3] | 63.7% (201) | 63.7% |
| 3 | 64.8% (88) | 71.3% [67.9-74.5] | 60.0% (95) | 63.9% |
| 4 | 75.8% (66) | 69.7% [65.6-73.5] | 76.6% (77) | 64.0% |
| 5 | 75.0% (36) | 68.0% [62.7-72.9] | 64.1% (39) | 64.2% |
| 6 | 63.3% (30) | 66.3% [59.3-72.6] | 62.1% (29) | 64.3% |
| 7 | 58.8% (17) | 64.5% [55.7-72.4] | 52.6% (19) | 64.5% |
| 8 | 59.1% (22) | 62.6% [51.9-72.2] | 60.0% (20) | 64.7% |
| 9 | 66.7% (12) | 60.8% [48.1-72.2] | 66.7% (12) | 64.8% |
| 10 | 71.4% (7) |  | 62.5% (8) |  |
| 11 | 40.0% (5) |  | 40.0% (5) |  |
| 12 | 20.0% (5) |  | 20.0% (5) |  |
| 13 | 50.0% (2) |  | 50.0% (2) |  |
| 15 | 0.0% (1) |  | 0.0% (1) |  |
| 16 | 0.0% (2) |  | 0.0% (2) |  |

### Middle tiles, quiet table

Fitted over discards 1 to 13. LuckyJ: 1 degree(s) of freedom (AIC by df {'1': 17.538, '2': 18.895, '3': 18.734}), dispersion 1.193; NAGA: 1 (AIC {'1': 15.923, '2': 17.116, '3': 18.796}), dispersion 1.06.
LuckyJ's curve crosses 50%: at discard 6.73, going down. NAGA's: at discard 3.32, going down.

| discard | LuckyJ kept safe (choices) | LuckyJ fit [95% range] | NAGA kept safe (choices) | NAGA fit |
|---|---|---|---|---|
| 1 | 80.0% (20) | 78.0% [71.5-83.3] | 42.9% (14) | 55.4% |
| 2 | 87.2% (39) | 74.0% [68.0-79.1] | 50.0% (34) | 53.1% |
| 3 | 67.4% (95) | 69.5% [64.3-74.2] | 56.0% (84) | 50.7% |
| 4 | 65.3% (147) | 64.6% [60.1-68.9] | 47.4% (137) | 48.4% |
| 5 | 53.1% (130) | 59.4% [55.5-63.2] | 43.4% (122) | 46.0% |
| 6 | 50.8% (120) | 54.0% [50.1-57.8] | 40.7% (108) | 43.7% |
| 7 | 56.4% (110) | 48.5% [44.2-52.8] | 50.0% (112) | 41.4% |
| 8 | 35.9% (64) | 43.0% [37.9-48.2] | 33.8% (65) | 39.2% |
| 9 | 43.9% (41) | 37.7% [31.8-44.0] | 42.9% (42) | 37.0% |
| 10 | 34.5% (29) | 32.7% [26.2-39.9] | 39.3% (28) | 34.8% |
| 11 | 26.3% (19) | 28.0% [21.2-36.1] | 17.4% (23) | 32.7% |
| 12 | 40.0% (10) | 23.8% [16.9-32.5] | 41.7% (12) | 30.6% |
| 13 | 13.3% (15) | 20.0% [13.3-29.0] | 18.8% (16) | 28.7% |
| 14 | 16.7% (6) |  | 16.7% (6) |  |
| 15 | 0.0% (5) |  | 14.3% (7) |  |
| 16 | 0.0% (8) |  | 0.0% (8) |  |
| 17 | 0.0% (3) |  | 0.0% (1) |  |
| 18 | 0.0% (3) |  | 0.0% (2) |  |

### Any leftover, after a riichi or a second call

Fitted over discards 2 to 18. LuckyJ: 1 degree(s) of freedom (AIC by df {'1': 16.252, '2': 18.252, '3': 20.18}), dispersion 1.0; NAGA: 2 (AIC {'1': 22.75, '2': 20.056, '3': 21.317}), dispersion 1.0.
LuckyJ's curve crosses 50%: never in the fitted range. NAGA's: never in the fitted range.

| discard | LuckyJ kept safe (choices) | LuckyJ fit [95% range] | NAGA kept safe (choices) | NAGA fit |
|---|---|---|---|---|
| 1 | 50.0% (4) |  | 0.0% (5) |  |
| 2 | 44.0% (25) | 39.1% [33.1-45.4] | 25.0% (28) | 26.4% |
| 3 | 39.5% (38) | 34.4% [29.4-39.7] | 26.5% (49) | 24.9% |
| 4 | 27.0% (89) | 30.0% [26.0-34.3] | 22.1% (95) | 23.3% |
| 5 | 24.5% (106) | 25.9% [22.7-29.4] | 18.6% (118) | 21.7% |
| 6 | 19.7% (157) | 22.2% [19.7-24.9] | 21.0% (167) | 20.1% |
| 7 | 21.3% (188) | 18.9% [17.0-21.1] | 20.2% (208) | 18.3% |
| 8 | 17.1% (210) | 16.0% [14.4-17.7] | 18.9% (238) | 16.4% |
| 9 | 12.1% (247) | 13.5% [12.1-15.0] | 12.4% (283) | 14.4% |
| 10 | 11.5% (217) | 11.3% [10.0-12.7] | 12.9% (256) | 12.4% |
| 11 | 10.4% (241) | 9.4% [8.2-10.8] | 10.9% (266) | 10.4% |
| 12 | 8.1% (210) | 7.8% [6.7-9.2] | 6.9% (216) | 8.6% |
| 13 | 4.4% (203) | 6.5% [5.4-7.8] | 4.6% (218) | 6.8% |
| 14 | 6.0% (183) | 5.4% [4.3-6.7] | 5.7% (193) | 5.4% |
| 15 | 5.3% (152) | 4.4% [3.5-5.7] | 6.3% (143) | 4.2% |
| 16 | 5.7% (105) | 3.6% [2.8-4.8] | 6.7% (105) | 3.2% |
| 17 | 0.0% (95) | 3.0% [2.2-4.1] | 1.0% (97) | 2.4% |
| 18 | 3.2% (62) | 2.5% [1.7-3.5] | 0.0% (57) | 1.8% |

## When the threat arrives

Share of LuckyJ's decisions facing a riichi or a two-call opponent, by its own discard: 1: 0.2%, 2: 1.3%, 3: 3.9%, 4: 8.1%, 5: 13.9%, 6: 21.4%, 7: 29.8%, 8: 37.6%, 9: 45.0%, 10: 52.4%, 11: 59.9%, 12: 63.9%, 13: 69.0%, 14: 73.2%, 15: 76.5%, 16: 78.8%, 17: 81.2%, 18: 79.1%.

## Limits

- Child kyoku only; LuckyJ's dealer hands are not in the sample.
- "Safe" is genbutsu against any opponent, so on a quiet table it is insurance against whoever
  attacks later, not against a named player.
- A hand can contribute choices at more than one discard. The dispersion scaling widens the band when
  the points scatter more than a binomial would, but the fit does not model hands as clusters.
- The comparison is NAGA only. The human corpus of the table-contrast sections was not replayed for
  this question.
- The guest-wind reason in the book (one copy fewer to pair, and a live wind stays cheap to cut) is an
  interpretation, not something the data tests.

## Rebuild

```bash
.venv/bin/python scripts/mine_safe_tile_timing.py            # full replay, writes today's file
.venv/bin/python scripts/mine_safe_tile_timing.py --summarize analysis/safe-tile-timing-2026-09-28.json
.venv/bin/python scripts/build_safe_tile_timing_figures.py   # redraws the charts in both editions
```
