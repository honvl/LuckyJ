# When LuckyJ starts keeping safe tiles (28 September 2026)

The question, from a reader: on what turn does LuckyJ start collecting defensive tiles? The book
section `#safe-tile-timing` in `site/points.html` and `site/ja.html` answers it from the figures
here. Figures: `analysis/safe-tile-timing-2026-09-28.json` (block `summary_bands`), written by
`scripts/mine_safe_tile_timing.py` from the cached NAGA reports of the 1,255 reviewed games.

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
- **The choice.** A turn counts when the hand holds a safe and a live leftover of the same kind. The
  figure is the share of LuckyJ's cuts of either tile that went to the live one: live / (safe + live).
  Above 50% the safe tile was kept; below 50% it went first. **NAGA** is the Nishiki head's top
  pick (`dahai_pred[0]`) at the same decision.

## Why same kind

The first pass (20 September) pooled all kinds and put the start of collecting at the fourth discard.
That was partly tile mix. On the first discards the safe leftovers are mostly guest winds, which
LuckyJ throws early anyway, while the live leftovers include terminals and middle tiles. Pooled, the
live share was:

| leftover | discards 1-2 | discards 3-5 | discards 6-8 | discards 9-12 | discards 13-18 |
|---|---|---|---|---|---|
| any leftover (mixed kinds) | 49.3% / 44.0% (3,304) | 60.6% / 47.3% (2,949) | 60.7% / 53.6% (1,507) | 50.6% / 49.0% (555) | 20.2% / 23.4% (163) |

Split by kind, the early turns reverse for terminals and middle tiles.

## Quiet tables, same kind (LuckyJ / NAGA, cuts in brackets)

| leftover | discards 1-2 | discards 3-5 | discards 6-8 | discards 9-12 | discards 13-18 |
|---|---|---|---|---|---|
| guest winds | 24.3% / 59.0% (395) | 70.0% / 68.1% (100) | 71.7% / 73.6% (53) | 50.0% / 50.0% (16) | 0.0% / 0.0% (2) |
| terminals | 73.9% / 63.0% (449) | 70.5% / 66.8% (190) | 60.9% / 58.8% (69) | 55.2% / 53.3% (29) | 20.0% / 20.0% (5) |
| middle tiles | 84.7% / 47.9% (59) | 61.6% / 48.1% (372) | 49.7% / 42.8% (294) | 37.4% / 36.2% (99) | 7.5% / 12.5% (40) |

- Terminals: the live one goes first from the first discard, fading toward even by the ninth.
- Middle tiles: the live one goes first strongly on the first two discards (a small sample of 59
  cuts) and still on the third to fifth; about even on the sixth to eighth; from the ninth the safe
  one goes first. NAGA is indifferent through the fifth discard.
- Guest winds: on the first two discards LuckyJ throws the wind someone already discarded; NAGA does
  the opposite. From the third to the eighth, LuckyJ throws the live wind about seven times in ten.
- The late bands (9 to 12 for guest winds and terminals, and every 13 to 18 cell) are small.

## Threat tables, same kind

| leftover | discards 1-2 | discards 3-5 | discards 6-8 | discards 9-12 | discards 13-18 |
|---|---|---|---|---|---|
| guest winds | 40.0% / 20.0% (5) | 20.0% / 0.0% (10) | 17.6% / 14.3% (17) | 16.7% / 21.1% (18) | 0.0% / 0.0% (13) |
| terminals | 100.0% / 100.0% (2) | 31.8% / 25.0% (22) | 20.0% / 28.6% (45) | 15.4% / 12.1% (52) | 7.7% / 9.3% (39) |
| middle tiles | 0.0% / 0.0% (2) | 23.3% / 23.8% (43) | 16.4% / 16.8% (146) | 7.0% / 6.9% (228) | 3.6% / 3.0% (253) |
| any leftover (mixed kinds) | 44.8% / 21.2% (29) | 27.9% / 21.4% (233) | 19.3% / 19.9% (555) | 10.6% / 11.0% (915) | 4.5% / 4.7% (800) |

Once someone is in riichi or has two calls, the safe leftover goes first in every kind, and LuckyJ
and NAGA agree to within a few points from the third discard on.

## When the threat arrives

Share of LuckyJ's decisions facing a riichi or a two-call opponent, by its own discard: 1: 0.2%, 2: 1.3%, 3: 3.9%, 4: 8.1%, 5: 13.9%, 6: 21.4%, 7: 29.8%, 8: 37.6%, 9: 45.0%, 10: 52.4%, 11: 59.9%, 12: 63.9%, 13: 69.0%, 14: 73.2%, 15: 76.5%, 16: 78.8%, 17: 81.2%, 18: 79.1%.

On quiet tables the hand holds 1.65 tile types that are already in some opponent's river at
the third discard, 3.03 at the sixth and 4.04 at the ninth.

## Charts

The book section draws these figures as charts with `scripts/build_safe_tile_timing_figures.py`:
four small line charts (the three quiet-table kinds and "once someone threatens") on the share of
choices where LuckyJ kept the safe leftover, with NAGA as a gray line, and an area chart of the share
of decisions facing a threat by discard. A band with fewer than 30 choices is left off the charts
and stays in the tables under them; a plotted band with fewer than 50 choices gets a hollow point.

## Limits

- Child kyoku only; LuckyJ's dealer hands are not in the sample.
- "Safe" is genbutsu against any opponent, so on a quiet table it is insurance against whoever
  attacks later, not against a named player.
- The comparison is NAGA only. The human corpus of the table-contrast sections was not replayed for
  this question.
- The guest-wind reason in the book (one copy fewer to pair, and a live wind stays cheap to cut) is an
  interpretation, not something the data tests.

## Rebuild

```bash
.venv/bin/python scripts/mine_safe_tile_timing.py            # full replay, writes today's file
.venv/bin/python scripts/mine_safe_tile_timing.py --summarize analysis/safe-tile-timing-2026-09-28.json
```
