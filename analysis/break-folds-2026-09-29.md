# Chapter 20: when LuckyJ breaks its hand to fold

The user's question (29 September): when does LuckyJ go back a shanten to fold? A safe tile drawn from
the wall and thrown straight back costs nothing and should not count.

## Definition

Corrected the same day at the user's objection ("passing up a step is similar"): the mark is the best hand
this draw allows (`best_sh` / `best`), not the hand before the draw. A safe tile (danger 1 or less:
genbutsu, full suji, an honor with two showing, against every caller or the riichi) that reaches the best
hand is a free fold; a safe draw that does nothing for the hand, thrown back, is one. When every safe tile
falls short, throwing one breaks the hand, in two forms that are the same choice on the table: back (every
safe tile is also worse than the hand before the draw, `prev_sh` / `prev`) and step (a safe tile keeps the
hand where it stood, only a live tile takes the step the draw offers). Turns are filed under the best hand
the draw allows. Turns that start with a call are left out. This is the mark chapter 18's "cost a shanten"
captions use.

In LuckyJ's Tokujou turns the two forms leave the same shape: the safe tile leaves 15 tiles of acceptance
after a step and 16 after going back with tenpai in reach (medians, one caller), 35 and 34 with 1-shanten in
reach, and the push offers 4 winning tiles in both (scratch join to `contrast/choices.py`). LuckyJ still
passes up a step more readily than it goes back; within open and within closed hands alike.

## Reproduce

```
.venv/bin/python scripts/contrast/vs_callers.py LJ_TOKUJOU.json lj OUT/lj --procs 12
.venv/bin/python scripts/contrast/vs_callers.py data/self_games/majsoul/index.json self OUT/you --procs 12
.venv/bin/python scripts/mine_riichi_folds.py compute LJ_TOKUJOU.json - OUT/rf_lj.json
.venv/bin/python scripts/mine_riichi_folds.py compute data/self_games/majsoul/index.json - OUT/rf_you.json
.venv/bin/python scripts/mine_break_folds.py OUT/lj.cuts.jsonl OUT/you.cuts.jsonl OUT/rf_lj.json OUT/rf_you.json analysis/break-folds-2026-09-29.json LJ_TOKUJOU.json
.venv/bin/python scripts/build_break_fold_figure.py
```

`LJ_TOKUJOU.json` is `data/local_sources/luckyj_tenhou/index.json` filtered to `mode == "tenhou-tokujou"`
(1,079 games). Run from the main checkout so the manifests' relative paths resolve. `vs_callers.py` now
also writes `drew`, `prev_sh`, `tsumogiri`, `call_turn` and `closed`, takes the group `self` (hero You,
others Jade), and writes every candidate tile for every caller (it used to write them only for the
caller with the most calls); the row count is unchanged (206,184). `mine_riichi_folds.py` rows gain
`prev` and `safe_best`.

## Break share when every safe tile would leave the hand a shanten short

Filed under the best hand the draw allows; back and step in brackets.

| Facing | Who | Tenpai | 1-shanten | 2-shanten or worse |
|---|---|---|---|---|
| One riichi | LuckyJ | 18.3% of 1,310 (13.9 / 30.8) | 53.4% of 1,583 (48.5 / 63.7) | 79.5% of 672 (75.9 / 85.8) |
| One riichi | You | 28.4% of 148 | 64.7% of 170 | 83.1% of 65 |
| One caller | LuckyJ | 3.3% of 1,300 (1.1 / 9.8) | 4.9% of 2,545 (4.5 / 6.0) | 4.1% of 1,643 (4.2 / 3.8) |
| One caller | You | 2.0% of 153 | 7.6% of 290 | 7.6% of 211 |
| Two or more callers | LuckyJ | 3.9% of 544 (2.6 / 8.5) | 11.2% of 956 (10.1 / 15.7) | 19.8% of 444 (18.1 / 23.9) |
| Two or more callers | You | 1.5% of 67 | 9.4% of 128 | 16.7% of 42 |

## Over the callers' square (chapter 18's grid; with two or more callers, 1 minus the product of 1 minus each)

Fitted with `fit_series`, one point per whole percent, between the 2nd and 98th percentiles.

| Square | 10% | 20% | 30% | 40% | 50% | 60% | 70% | 80% | 90% |
|---|---|---|---|---|---|---|---|---|---|
| Tenpai (1,797) | 1.8 | 2.0 | 2.4 | 2.7 | 3.1 | 3.6 | 4.2 | 4.8 | 5.5 |
| 1-shanten (3,457) | 1.4 | 2.4 | 4.0 | 6.1 | 8.6 | 11.3 | 13.9 | 16.4 | 18.9 |
| 2-shanten or worse (2,057) | 1.3 | 4.2 | 10.2 | 17.3 | 22.8 | 26.5 | 29.9 | 33.7 | 37.7 |

A regression on the square plus value (1-shanten in reach, log-odds): caller with 3+ dora in their calls
+1.28 ± 0.26, dealer caller +0.49 ± 0.17, each dora in LuckyJ's hand −0.26 ± 0.09, LuckyJ as dealer −0.44 ±
0.22, ten of LuckyJ's turns +1.61 ± 0.29. With 2-shanten or worse: +1.44 ± 0.37, +0.44 ± 0.23, −0.36 ±
0.13, −0.88 ± 0.33, +0.91 ± 0.41.

A ron cost the discarder, in LuckyJ's games: open hand 4,525 on average (2,944 wins), riichi 6,683
(2,186), closed dama 5,610 (820); honba included.

## Your games

Against LuckyJ's curve: 1-shanten in reach 33 breaks where it expects 25.5, 2-shanten or worse 23 where it
expects 16.8, tenpai in reach 4 where it expects 7.1; below a square of 40%, from 1-shanten or worse, 24
where it expects 12.5. Mortal's weight on the safe tiles on your costly turns (site replays): under 40%,
3.1% (tenpai, 68 turns), 2.5% (1-shanten, 250), 3.7% (2+, 212); 40% and over, 1.8% (132), 9.9% (162),
15.1% (40).

Examples in the chapter: 260927-33c90769 East 2-0 turn 13 (square 35%, broke with 1s; Mortal 3m or 8s),
260928-90620418 East 2-0 turn 8 (78%, broke with S holding two red fives; Mortal 6s 98.7%),
260928-697dfc0f East 2-0 turn 11 (two callers, 60%; broke with N; Mortal N 99.3%).
