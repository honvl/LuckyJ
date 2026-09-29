# Chapter 19: LuckyJ's fold line on the caller grid, and how to count a caller's run

Three follow-up questions on chapter 18's grid (29 September): where LuckyJ starts folding instead of
pushing, what a caller who alternates tiles from hand and tiles from the wall means, and whether the
guest winds and terminals a caller draws and throws count toward the run.

## Reproduce

```
.venv/bin/python scripts/contrast/vs_callers.py LJ_TOKUJOU.json lj OUT/vc_lj --procs 8
.venv/bin/python scripts/mine_caller_fold_line.py OUT/vc_lj.cuts.jsonl analysis/caller-fold-line-2026-09-29.json
.venv/bin/python scripts/mine_caller_surface.py compute data/local_sources/luckyj_tenhou/index.json - OUT/cs_lj.json
.venv/bin/python scripts/mine_caller_surface.py compute data/self_games/majsoul/index.json 2026-01-01 OUT/cs_you.json
.venv/bin/python scripts/mine_caller_surface.py patterns analysis/caller-patterns-2026-09-29.json analysis/caller-surface-2026-09-29.json OUT/cs_lj.json
.venv/bin/python scripts/mine_caller_surface.py patterns analysis/caller-patterns-honver-2026-09-29.json analysis/caller-surface-2026-09-29.json OUT/cs_you.json --opponents
.venv/bin/python scripts/build_caller_surface.py
```

`LJ_TOKUJOU.json` is `data/local_sources/luckyj_tenhou/index.json` filtered to `mode == "tenhou-tokujou"`
(1,079 games), the main book's set. `vs_callers.py` now also writes each caller's H/T pattern since their
last call (`q_pattern`) and the tiles of their current run (`run_tiles`); nothing else in its output
changed (206,184 cut rows before and after). `compute` now keeps the same pattern, with one letter per
tile for its kind, on every reading; the grid built from the new rows is identical to
`caller-surface-2026-09-29.json`.

## 1. The fold line

The main book's fold-line spots ("Open callers"): LuckyJ's own discards against a single caller, nobody
in riichi, two-shanten or worse, holding a safe tile (danger 1 or less: genbutsu, full suji, an honor with
two or more showing) that keeps its best shanten. A live cut has danger 2 or more. Fitted with
`fit_series` over the caller's discards with at least 40 spots each.

| Caller's discard | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| One call (7,821 spots) | 79 | 80 | 79 | 78 | 76 | 72 | 65 | 57 | **48** | 40 | 34 | 29 | 25 | 22 |
| Two or more (2,812 spots) | | | 86 | 78 | 67 | 56 | **47** | 40 | 36 | 33 | 30 | 28 | 25 | 23 |

The fitted curves cross 50% at 8.82 (one call) and 6.60 (two or more), so the grid's line sits before the
9th and the 7th discard. The book and chapters 13 and 14 put the one-call line at the tenth, from bands
of three discards (7 to 9: 57.7%, 10 to 12: 38.4%); per discard, the ninth is 48% (95% band 44 to 53%),
a coin flip, and the tenth 40% (36 to 45%). Three calls on their own are too few to place (328 spots);
they share the line with two calls, as in the book.

Does the run move it? Logistic regression of the live cut on a three-knot natural spline of the
caller's discard plus the run (0 to 3+), per block and per LuckyJ shanten:

| LuckyJ | One call | Two or more |
|---|---|---|
| Two-shanten or worse | +0.027 ± 0.031 (7,821) | −0.064 ± 0.044 (2,812) |
| One-shanten | +0.055 ± 0.030 (4,838) | +0.029 ± 0.041 (2,454) |
| Tenpai | **−0.356 ± 0.111** (939) | +0.030 ± 0.125 (660) |

Log-odds per tile of run. Only the tenpai choice against one call reacts: with a safe tile that keeps
its tenpai, LuckyJ cut a live tile 17.4% of the time against a run of 0 (420 spots), 10.9% against 1
(230), 5.4% against 2 (129) and 6.9% against 3 or more (160).

What the run was made of, from two-shanten or worse, against the discard curve: against one call, runs
of honors and terminals only 66.2% live (curve 64.4%, 903 spots), runs with a number tile 59.4% (60.0%,
1,795); against two or more, 51.2% (45.6%, 322) and 38.9% (41.1%, 939). A hint that LuckyJ pushes a
little more against runs of honors and terminals; too small to teach.

## 2. Patterns of hand and wall discards

The grid's 88,588 readings (LuckyJ's 1,255 games, every seat), each set against its own square ("own");
where a pattern is set against other rows, only squares where every run row of the block can be read
("rows").

| Pattern since the last call | own n | could win | its squares | rows n | could win | first / second / third / fourth row |
|---|---|---|---|---|---|---|
| right after the call (nothing since) | 21,913 | 24.5 | 21.9 | 14,033 | 32.7 | 29.0 / 32.8 / 34.6 / 36.0 |
| hand after hand, or the call's discard | 15,575 | 16.7 | 20.3 | 11,874 | 20.3 | 24.8 / 29.2 / 31.6 / 33.5 |
| hand after exactly one from the wall | 5,296 | 23.8 | 25.5 | 4,793 | 25.3 | 27.1 / 31.8 / 34.5 / 36.7 |
| hand after exactly two | 2,159 | 30.8 | 30.7 | 2,120 | 30.9 | 30.9 / 36.5 / 40.0 / 42.8 |
| hand after three or more | 1,734 | 41.3 | 36.9 | 1,722 | 41.2 | 36.6 / 44.5 / 50.3 / 55.2 |
| last four alternated, last from hand | 935 | 28.9 | 31.2 | 931 | 28.7 | 31.0 / 37.5 / 42.0 / 45.6 |
| last four alternated, last from the wall | 1,233 | 34.7 | 36.4 | 1,232 | 34.7 | 30.3 / 36.3 / 40.3 / 43.4 |

Right after a call the caller reads like the second row. With the grid as drawn, a tile from the wall
straight after the call reads like the third row (35.7% against 34.5%) and two like the fourth (47.0%
against 46.2%), so "count the call as one tile from the wall" holds on the published squares too.

## 3. Honors and terminals from the wall

| Run from the wall | own n | could win | its squares |
|---|---|---|---|
| one, a value honor | 2,801 | 35.5 | 33.6 |
| one, a guest wind | 1,637 | 32.6 | 31.2 |
| one, a terminal | 4,350 | 29.8 | 31.5 |
| one, a 2 or 8 | 3,860 | 29.9 | 31.8 |
| one, a 3 to 7 | 7,511 | 34.9 | 33.9 |
| two, both honors or terminals | 1,921 | 39.6 | 40.3 |
| two, with a 2 to 8 | 7,909 | 42.6 | 42.4 |
| three or more, all honors or terminals | 572 | 40.0 | 49.6 |
| three or more, all guest winds or terminals | 150 | 30.7 | 46.1 |
| three or more, with a 2 to 8 | 10,807 | 60.1 | 59.6 |

5.0% of runs of three or more are made only of honors and terminals. Against the rows, those runs read
39.9% where the second row says 41.1% and the fourth 49.5%.

## 4. Ways to count the run

Each count refits the twelve grid rows and scores every reading (log-likelihood, can-win):

| Count | log-likelihood | vs the grid |
|---|---|---|
| every tile from the wall since the last call, in a row (the grid) | −43,948.4 | 0 |
| the same, passing over guest winds and terminals | −43,973.2 | −24.8 |
| tiles from the wall among the last four since the call | −44,125.0 | −176.6 |
| the call itself counted as one tile from the wall | −43,795.3 | +153.1 |
| that, and a hand discard ending three or more from the wall read as one | −43,749.8 | +198.6 |

## 5. At the user's tables

Opponents' readings in the user's 123 games since 1 January (6,472): right after a call 35.3% could win
where the first row said 28.6% and the second 32.4% (978 readings where all rows read); after a hand
discard that ended three or more from the wall 42.1% where the first row said 37.9% and the second
45.3% (121); hand after hand 19.4% where the first row said 23.4% (855); runs of three or more all
honors or terminals 39.0% where the fourth row said 45.6% (41).
