# Chapter 20: when LuckyJ breaks its hand to fold

The user's question (29 September): when does LuckyJ go back a shanten to fold? A safe tile drawn from
the wall and thrown straight back costs nothing and should not count.

## Definition

The mark is the hand before the draw: on a draw turn, throwing the drawn tile back leaves the hand as it
stood, so its shanten (`prev_sh` in the cut rows, `prev` in the riichi rows) is the reference. Safe is
danger 1 or less (genbutsu, full suji, an honor with two showing) against every caller, or against the
riichi. Each draw turn facing a threat is one of four kinds: free (a safe tile keeps the hand where it
stood and reaches the best shanten), step (a safe tile keeps the hand where it stood, only a live tile
takes the step the draw offers), break (every safe tile leaves the hand further back), none (no safe
tile). Turns that start with a call are left out. Chapter 18's fold views measured cost against the best
shanten, which folds "step" turns into their costly set; this separates them.

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

## Break share when every safe tile would break the hand

| Facing | Who | Tenpai | 1-shanten | 2-shanten or worse |
|---|---|---|---|---|
| One riichi | LuckyJ | 13.9% of 966 | 48.5% of 1,070 | 75.9% of 432 |
| One riichi | You | 23.4% of 107 | 55.3% of 103 | 85.7% of 49 |
| One caller | LuckyJ | 1.1% of 975 | 4.5% of 1,830 | 4.2% of 1,085 |
| One caller | You | 0.0% of 124 | 6.3% of 207 | 7.5% of 134 |
| Two or more callers | LuckyJ | 2.6% of 427 | 10.1% of 771 | 18.1% of 310 |
| Two or more callers | You | 0.0% of 49 | 8.2% of 97 | 16.1% of 31 |

Passing up a step: LuckyJ 9.8% (1-shanten) and 5.0% (2+) against one caller, 30.8% and 70.8% against one
riichi.

## Over the callers' square (chapter 18's grid; with two or more callers, 1 minus the product of 1 minus each)

Fitted with `fit_series`, one point per whole percent, between the 2nd and 98th percentiles.

| Square | 10% | 20% | 30% | 40% | 50% | 60% | 70% | 80% | 90% |
|---|---|---|---|---|---|---|---|---|---|
| Tenpai (1,362) | 0.0 | 0.0 | 0.1 | 0.4 | 1.2 | 2.5 | 3.1 | 2.7 | 1.9 |
| 1-shanten (2,572) | 1.2 | 2.0 | 3.2 | 4.9 | 7.1 | 9.5 | 12.2 | 15.0 | 18.1 |
| 2-shanten or worse (1,380) | 1.3 | 3.3 | 7.6 | 14.4 | 21.7 | 27.2 | 30.1 | 31.1 | |

A regression on the square plus value (1-shanten, log-odds): caller with 3+ dora in their calls +1.40 ±
0.30, dealer caller +0.61 ± 0.21, each dora in LuckyJ's hand −0.30 ± 0.11, LuckyJ as dealer −0.29 ± 0.27,
ten of LuckyJ's turns +1.07 ± 0.35. From 2-shanten or worse: +1.29 ± 0.43, +0.35 ± 0.27, −0.30 ± 0.15,
−0.95 ± 0.38, +0.46 ± 0.50.

A ron cost the discarder, in LuckyJ's games: open hand 4,525 on average (2,944 wins), riichi 6,683
(2,186), closed dama 5,610 (820); honba included.

## Your games

Against LuckyJ's curve: 1-shanten 20 breaks where it expects 16.6, 2-shanten or worse 15 where it
expects 11.2, tenpai 0 where it expects 2.5; below a square of 40%, 12 where it expects 7.6. Mortal's
weight on the safe tiles at your break turns (site replays): under 40%, 2.1% (tenpai, 50 turns), 1.2%
(1-shanten, 173), 3.7% (2+, 134); 40% and over, 0.6% (113), 8.7% (125), 15.8% (30).

Examples in the chapter: 260927-33c90769 East 2-0 turn 13 (square 35%, broke with 1s; Mortal 3m or 8s),
260928-90620418 East 2-0 turn 8 (78%, broke with S holding two red fives; Mortal 6s 98.7%),
260928-697dfc0f East 2-0 turn 11 (two callers, 60%; broke with N; Mortal N 99.3%).
