# An importance weighting of our own for Mortal-S42's rating (21 Nov 2026)

Question: can we weight decisions by importance ourselves, so that a game's Mortal rating says more about rank?
The starting guess was that later moves matter more than earlier ones.

Scripts: `scripts/mine_importance.py` (every decision scored by Mortal-S42 and kept apart by situation),
`scripts/fit_importance.py` (`describe`, `score`, `all`). Rows: `data/ladder_skill/jade_importance.jsonl`,
`houou_importance.jsonl` (local).

## What Wind-Up Bird's importance is made of

Its importance weight was fitted on its own reviews (7,839 discards of 63 of your games). ln(weight) is explained

| by | R² |
| --- | --- |
| the discard number alone | 0.65 |
| the hand's shanten alone | 0.75 |
| its tenpai read of the opponents alone | 0.48 |
| discard number + shanten | 0.89 |
| all three | 0.94 |

Mean weight by discard number: 5.4 (discards 1-3), 12, 20, 27, 31, 35 (16 and later). By shanten: 44 at tenpai, 24
one away, 12 two away, 5 three or more away. By the top opponent's tenpai chance: 9 under 10%, 30 at 90% or more.
The game's stage does not enter (East 17.5, South 17.4, South 4 17.8).

So the guess is right about their weights, and shanten is the larger half of it. The formula
`ln w = 0.040 * discard + (1.57 tenpai, 1.11 one away, 0.59 two away) + 0.82 * tenpai chance` reproduces it, with a
declared riichi standing in for the tenpai chance on our side.

## Does it make S42's rating track the place? Jade, every seat (1,443 seat-games)

Spearman correlation of the rating with the place in the same game; gain is against the flat rating.

| Weighting | Q loss | ln p | Miss rate |
| --- | --- | --- | --- |
| flat | -0.153 | -0.146 | -0.126 |
| later turns only (w = discard number) | -0.162 | -0.157 | -0.138 |
| Wind-Up Bird's formula | -0.191 | -0.194 | -0.183 |
| fitted to the place, scored on held-out games | -0.210 | -0.238 | -0.242 |

Wind-Up Bird's formula adds 0.04 to 0.06 (every interval excludes zero); the turn alone adds about 0.01 (not
separable from zero). On the first 74 of your games Wind-Up Bird reviewed, its own score reached -0.24 and our
S42 rating under its formula -0.22 to -0.26: the reproduction tracks the place as well as the original. On all
361 its score settles at -0.197, level with flat S42 at -0.185 (`analysis/neji-placement-2026-11-21.md`).

## Where the gain comes from

Each rating was split into the situations the seat was in (what those situations usually cost, with no decision
in it) and the player's own part (loss beyond the usual for the situation).

| Part of the rating (ln p) | flat | Wind-Up Bird's formula | gain |
| --- | --- | --- | --- |
| whole rating | -0.146 | -0.194 | -0.049 [-0.073, -0.023] |
| situations only | -0.282 | -0.331 | -0.049 [-0.076, -0.022] |
| the player's own part | -0.082 | -0.092 | -0.010 [-0.036, +0.016] |

The whole gain sits in the situations. Tenpai decisions are easy (93% match Mortal against 70% three or more
away), so a seat that was tenpai often rates well under any weighting that leans on tenpai, and it places well
because of those same hands. The mix of situations alone tracks the place at -0.28 to -0.33, better than any
rating of decisions. On the player's own part no weighting helps, the fitted one included (-0.005
[-0.013, +0.004] held out).

Mortal-S42's raw Q loss runs the other way from importance: it is largest on the first discards (0.35 a decision
at discards 1-2, 0.22 at 17 and later) and far from tenpai (0.37 at three or more away, 0.09 at tenpai).

## The same in Houou, every seat (63,675 seat-games)

| Part of the rating (Q loss) | flat | Wind-Up Bird's formula | fitted, held out |
| --- | --- | --- | --- |
| whole rating | -0.038 | -0.077 | -0.133 |
| situations only | -0.215 | -0.286 | |
| the player's own part | +0.008 | +0.001 | +0.002 |

The formula doubles the whole rating's link to the same game's place and a fitted weighting more than triples
it. The situations alone reach -0.22 to -0.29. The player's own part is at zero under every weighting.

## Across games: Houou regulars (715 players with 20 or more games)

The same-game place cannot tell a better measure of play from a better detector of lucky hands. Across games
it can: a player's rating in half of their games against their mean place in the other half (`skill` in
`fit_importance.py`, 20 random splits, intervals from resampling players).

| Weighting | Q loss | ln p | Miss rate |
| --- | --- | --- | --- |
| flat | -0.074 | -0.070 | -0.058 |
| later turns only | -0.081 | -0.076 | -0.064 |
| Wind-Up Bird's formula | -0.089 | -0.087 | -0.075 |
| gain of the formula over flat | -0.015 [-0.058, +0.017] | -0.017 [-0.060, +0.016] | -0.017 [-0.072, +0.023] |

| Part of the rating (Q loss) | flat | Wind-Up Bird's formula | gain |
| --- | --- | --- | --- |
| situations only | +0.029 | +0.026 | -0.003 [-0.056, +0.049] |
| the player's own part | -0.078 | -0.094 | -0.016 [-0.058, +0.017] |

## Reading

- The situation mix, which carries the whole same-game gain, says nothing about the player across games
  (+0.03, the wrong sign). It is the hands dealt, not skill.
- Across games every weighting points the same way, a gain of 0.006 to 0.022, and every interval spans zero.
  715 players cannot confirm a gain that small; the later-turns guess alone is worth about 0.007.
- The player's own part is the cleanest rating across games, slightly ahead of the whole rating under each
  weighting (-0.078 against -0.074 flat, -0.094 against -0.089 with the formula).
- For rank analysis: keep the flat rating as the measure of a player. An importance-weighted rating is fair to
  use for ordering one game's mistakes for review. It should not be read as a better estimate of strength, and
  its better fit to one game's place is not evidence of that.
