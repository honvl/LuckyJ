# Chapter 22: what your extra folds follow

The user's question (29 September), after the chat answer that LuckyJ's book reduces to one rule (pay only for a
hand that can pay you back, then pay in full or not at all) and that the user prices their own hand too low: "Tell me
more about me valuing my own hand too low in guide chapter 22, and whether that is a self esteem issue or a fear issue."

A game record cannot see feelings, but the two answers predict different things. Fear of the other player would follow
the size of their hand and a recent deal-in. Doubt about your own hand would follow what the hand is worth. This
measures what the user's extra folds follow, against LuckyJ's, with Mortal on the same turns as the benchmark.

## Definition

Costly turns are chapter 20's (`mine_break_folds.py`): draw turns facing exactly one riichi (or callers with nobody in
riichi) where every safe tile (genbutsu, dead, a full suji or nakasuji, an honor with two showing) leaves the hand a
shanten short of the best hand the draw allows. Folding is throwing a safe tile. Mortal's rate is Mortal's weight on the
safe tiles on the same turn: for the user from the site's replays (`site/replays`, the draw decision of that turn), for
LuckyJ from `scripts/contrast/mortal_run.py` over its Tokujou games (normalised over the discards and riichi). Extra folds
are folds beyond Mortal's rate, per 100 turns. A test splits the turns two ways; its contrast is the change in extra
folds from the first situation to the second, and its standard error comes from resampling whole games (2,000 draws,
seed 22). The counts reproduce chapter 20's exactly (LuckyJ one riichi 1,310 / 1,583 / 672; the user 148 / 170 / 65).
Mortal's record of the tile thrown matches the game on 99.9% of the user's turns and 100% of LuckyJ's.

## Reproduce

Run from the main checkout (the LuckyJ manifest's log paths are relative to it). `LJ_TOKUJOU.json` is
`data/local_sources/luckyj_tenhou/index.json` filtered to `mode == "tenhou-tokujou"` (1,079 games).

```
.venv/bin/python scripts/contrast/choices.py data/self_games/majsoul/index.json OUT/choices_you.jsonl
.venv/bin/python scripts/contrast/vs_callers.py data/self_games/majsoul/index.json self OUT/you
.venv/bin/python scripts/contrast/tenpai.py data/self_games/majsoul/index.json OUT/tenpai_you.jsonl
.venv/bin/python scripts/contrast/choices.py LJ_TOKUJOU.json OUT/choices_lj.jsonl
.venv/bin/python scripts/contrast/vs_callers.py LJ_TOKUJOU.json lj OUT/lj
.venv/bin/python scripts/contrast/tenpai.py LJ_TOKUJOU.json OUT/tenpai_lj.jsonl
.venv/bin/python scripts/contrast/mortal_run.py LJ_TOKUJOU.json OUT/mortal_lj.jsonl
.venv/bin/python scripts/mine_fold_motives.py OUT/choices_you.jsonl OUT/you.cuts.jsonl OUT/tenpai_you.jsonl \
    OUT/choices_lj.jsonl OUT/lj.cuts.jsonl OUT/tenpai_lj.jsonl OUT/mortal_lj.jsonl LJ_TOKUJOU.json analysis/fold-motives-2026-09-29.json
.venv/bin/python scripts/build_fold_motives_figure.py
```

## How much

Folded vs Mortal's rate on the same turns (extra per 100, turns).

| Costly turns | Who | Tenpai | 1-shanten | 2-shanten or worse | All |
|---|---|---|---|---|---|
| One riichi | You | 28.4% vs 19.0% (+9.4, 148) | 64.7% vs 58.1% (+6.6, 170) | 83.1% vs 74.9% (+8.1, 65) | 53.8% vs 45.9% (+7.9, 383) |
| One riichi | LuckyJ | 18.3% vs 20.1% (-1.8, 1,310) | 53.4% vs 57.7% (-4.3, 1,583) | 79.5% vs 75.3% (+4.1, 672) | 45.4% vs 47.2% (-1.8, 3,565) |
| Callers | You | 1.8% vs 2.1% (-0.3, 220) | 8.2% vs 5.4% (+2.8, 417) | 9.1% vs 5.5% (+3.6, 253) | 6.9% vs 4.6% (+2.2, 890) |
| Callers | LuckyJ | 3.5% vs 3.2% (+0.3, 1,844) | 6.6% vs 6.4% (+0.2, 3,501) | 7.4% vs 7.1% (+0.3, 2,087) | 6.1% vs 5.8% (+0.3, 7,432) |

## The tests

Change in extra folds per 100 from the first situation to the second, ± one standard error.

| Threat | Split | You | LuckyJ | Difference |
|---|---|---|---|---|
| riichi | the other hand is the dealer's | +7.5 → +9.6 (+2.2 ± 4.0) | -3.6 → +2.3 (+5.9 ± 1.3) | -3.7 ± 4.2 |
| riichi | you dealt in on the hand before | +8.0 → +7.2 (-0.8 ± 7.4) | -2.2 → +2.6 (+4.8 ± 1.9) | -5.6 ± 7.6 |
| riichi | the South round | +5.1 → +11.3 (+6.3 ± 4.0) | -0.1 → -4.0 (-3.9 ± 1.3) | +10.2 ± 4.2 |
| riichi | two or more dora in your hand, against none | +4.8 → +11.1 (+6.4 ± 4.5) | -1.4 → -2.3 (-0.9 ± 1.4) | +7.3 ± 4.7 |
| riichi | you are the dealer | +7.9 → +8.0 (+0.0 ± 4.2) | -0.4 → -5.7 (-5.4 ± 1.4) | +5.4 ± 4.4 |
| callers | the other hand is the dealer's | +2.1 → +2.4 (+0.3 ± 1.5) | -0.6 → +1.9 (+2.5 ± 0.5) | -2.2 ± 1.6 |
| callers | you dealt in on the hand before | +2.2 → +2.9 (+0.8 ± 1.7) | +0.3 → +0.1 (-0.2 ± 0.7) | +1.0 ± 1.8 |
| callers | the South round | +2.4 → +2.1 (-0.2 ± 1.5) | +0.1 → +0.5 (+0.4 ± 0.5) | -0.6 ± 1.6 |
| callers | two or more dora in your hand, against none | +1.3 → +3.6 (+2.3 ± 1.6) | +0.2 → +0.8 (+0.6 ± 0.6) | +1.7 ± 1.7 |
| callers | you are the dealer | +2.6 → +1.0 (-1.6 ± 1.6) | +0.6 → -0.7 (-1.3 ± 0.4) | -0.3 ± 1.6 |

Before and since the reviews began (20 September), one riichi: +11.1 per 100 on 160 turns, then +5.7 on 223 (change -5.4 ± 4.4).

Riichi or dama, first closed tenpai kept with riichi available (4+ tiles left, 1,000 points, not furiten); declared vs Mortal's weight on riichi:

| Who | All | East | South |
|---|---|---|---|
| You | 72.0% vs 69.7% (321) | 80.9% vs 74.5% (173) | 61.5% vs 64.0% (148) |
| LuckyJ | 73.4% vs 70.8% (2,661) | 78.2% vs 75.9% (1,513) | 67.2% vs 64.0% (1,148) |

South against East, declared beyond Mortal: you -8.9 ± 4.0, LuckyJ +0.9 ± 1.4, difference -9.8 ± 4.2.

## Your own hand

One-shanten against one riichi, by dora in hand (folded vs Mortal):

| Who | No dora | One | Two or more |
|---|---|---|---|
| You | 65.1% vs 61.4% (+3.7, 43) | 66.7% vs 62.8% (+3.9, 54) | 63.0% vs 52.7% (+10.3, 73) |
| LuckyJ | 56.5% vs 59.8% (-3.2, 527) | 56.7% vs 60.0% (-3.3, 651) | 44.2% vs 51.4% (-7.2, 405) |

Two or more dora, by turn:

| Who | Turns 1-9 | 10-12 | 13+ |
|---|---|---|---|
| You | 40.0% vs 21.1% (+18.9, 20) | 58.6% vs 54.0% (+4.6, 29) | 87.5% vs 77.4% (+10.1, 24) |
| LuckyJ | 32.7% vs 43.0% (-10.4, 150) | 40.0% vs 46.2% (-6.2, 115) | 60.0% vs 64.6% (-4.6, 140) |

## The round by place (one riichi, extra per 100, turns)

| Who | Place | East | South |
|---|---|---|---|
| You | 1 | -0.1 (66) | +8.3 (32) |
| You | 2 | +7.2 (46) | +10.0 (47) |
| You | 3 | +8.1 (59) | +15.3 (65) |
| You | 4 | +6.8 (36) | +8.3 (32) |
| LuckyJ | 1 | -4.0 (613) | -10.6 (515) |
| LuckyJ | 2 | -2.1 (474) | -5.3 (396) |
| LuckyJ | 3 | +1.1 (532) | -2.6 (360) |
| LuckyJ | 4 | +6.4 (402) | +8.6 (273) |

## Reading

- Not fear of the other hand: a dealer's riichi adds less to your extra folds than to LuckyJ's, and a deal-in on the
  hand before changes nothing (only 41 turns).
- The round: in the South your folds climb further above Mortal's and your declarations fall below it; LuckyJ does
  the opposite on folds and holds steady on declarations. Two independent decisions, each more than two standard errors
  from LuckyJ's pattern.
- Your hand: the extra grows with dora (the one-shanten does not fold less with two dora, LuckyJ's does) and does not
  shrink as dealer (LuckyJ's does); between one and one and a half standard errors, and it repeats chapter 16.
- In fourth place your extra folds match LuckyJ's, which also folds more than Mortal there.
- Riichi or dama overall matches LuckyJ: both declare 2 to 3 points above Mortal.
- Caveats: Mortal does not know Mahjong Soul's rank points; the user's splits are small (41 to 299 turns); the
  answer is about decisions, not feelings.

## Examples (chapter 22's table)

- 2026-09-22 17:38 260923-275bb855-c2db-43a4-b555-b1c52a836ccd South 3-0 turn 4: place 1, dealer False, toimen riichi on discard 3; one, 3 dora; threw 8s; Mortal 3s 88.5%, safe tiles 10.2%.
- 2026-09-19 18:11 260920-9d667586-3125-40f9-9989-9b14743d5967 South 3-2 turn 7: place 2, dealer True, toimen riichi on discard 6; one, 2 dora; threw 3p; Mortal 9s 79.3%, safe tiles 18.6%.
- 2026-09-20 22:43 260921-7b8a8c7c-94f0-47c6-84ba-1638af253b8d South 2-0 turn 13: place 2, dealer True, toimen riichi on discard 11; tenpai, 2 dora; threw 2p; Mortal 3m 98.2%, safe tiles 0.2%.
