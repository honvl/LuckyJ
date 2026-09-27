# Honver's games of 24 to 27 September: defense against callers (27 September 2026)

The question, from the user: "I feel like I'm doing better now with the open hand defense." The answer is chapter
13 of the personal guide (`site/honver.html#caller-defense`). This note keeps its figures and how they were made.

## Data

- 108 of Honver's Jade South games since 1 January 2026 (`data/self_games/majsoul/index.json`, fetched with
  `scripts/fetch_majsoul_games.py --since 2026-01-01`): the 94 before 24 September and the 14 new games from 24
  September 19:36 to 27 September. The new games: three firsts, five seconds, six thirds, no fourth (2.21 against
  2.46 before). At the earlier fourth rate (21 of 94) a 14-game run without a fourth has probability 0.029.
- LuckyJ: its 1,079 Tokujou games, measured with the same code.
- Extractors, run on a manifest per period: `scripts/contrast/hands_all.py` (hand ledger),
  `scripts/mine_caller_tells.py compute` (chapter 8's tells table), `scripts/contrast/vs_callers.py` (the fold line
  and deal-ins at the cut), `scripts/contrast/riichi_danger.py` (riichi at a first tenpai against callers),
  `scripts/contrast/report/early_ties.py` and `scripts/contrast/report/both_threats.py`.

## Figures in the chapter

| | 94 games before | 14 new games | LuckyJ |
|---|---|---|---|
| hands | 995 | 152 | 11,272 |
| deal-ins to an open hand, per 100 hands | 6.93 | 5.26 (8) | 4.76 |
| points lost to open hands, per hand | 269 | 191 | 211 |
| deal-ins to a riichi, per 100 hands | 3.82 | 1.97 | 3.83 |
| net points per hand | +31 | +330 | +363 |
| average win | 6,150 | 5,331 | 7,317 |
| live cuts at 1-shanten with a safe tile in hand, 2+ tells | 50.2% (237) | 42.2% (45) | 41.7% (3,266) |
| the same, all three tells | 51.0% (51) | 30.8% (13) | 32.1% (548) |
| live cuts from 2-shanten or worse, caller 30-60% likely tenpai, a safe tile kept the shanten | 39.0% (154) | 17.4% (23) | 38.9% (1,847) |
| live cuts that dealt in to a caller, per 100 | 2.25 (2,264 live cuts) | 1.04 (383) | 1.26 |
| live tile on the caller's wait when the caller was tenpai | 7.7% | 3.6% | 5.2% |

The tells rows use `mine_caller_tells` (all hands, shanten after the cut, any safe tile in hand); the 30-60% row
uses the book's free-hold definition and caller odds (`analysis/open-callers-2026-09-27.json`).

Before the line (caller under 30% likely to be tenpai), when a safe tile and a live tile tie for the best
acceptance, from 2-shanten or worse: LuckyJ cut the safe tile 25.5% of the time and the live one 55.1% (1,978
spots); 18 to 26% safe when the tied live tile was a terminal or an honor. Honver: 31.1% (151) before, 12 of 24 in
the new games. When the caller was later 30%+ likely to be tenpai (1-shanten or further), turns with no safe tile
that kept the shanten: LuckyJ 17.0% (7,976), Honver 19.7% (690) before and 23.3% (103) in the new games.

With a riichi and a caller out at once, when a tile safe against both kept the best shanten and a tile safe
against only one did too: LuckyJ cut a tile safe against both 68.4% of the time (3,461), Honver 75.3% (287).

At a first closed tenpai against callers with nobody in riichi, when the widest wait needed a live tile: LuckyJ
declared 70.0% (1,001), Honver 67.0% (88) before and 14 of 16 in the new games.

At 1-shanten against a single caller in their 10th to 12th discard, when only a shanten-losing tile was safe,
LuckyJ broke the hand 8.1% of the time (235), 9.0% against a dealer (78).

## The 13 deal-ins of the new games

| game, hand | into | verdict |
|---|---|---|
| 260925-01f573ba South 3-1 | open hand | suji [[7s]] from a dama tenpai hit |
| 260925-ab37b976 East 2-0 | open hand | riichi declared with a live [[5s]] against one early call |
| 260925-0d8e7a00 East 2-0 | open hand | slip: live [[7p]] against three calls; [[3p]] kept the shanten (example) |
| 260925-0d8e7a00 East 3-3 | riichi | 1-shanten push of a live terminal, close |
| 260925-0d8e7a00 East 4-0 | open hand | 11,600 push from 1-shanten against the dealer's double east, close (example) |
| 260925-97b9cfb4 East 1-1 | open hand | live [[2s]] from 3-shanten before the line |
| 260925-97b9cfb4 South 2-0 | dama | open tenpai push at turn 16 |
| 260927-33c90769 South 1-0 | riichi | slip: drawn [[9m]] from 4-shanten; [[N]] genbutsu against both (example) |
| 260927-1a030971 East 4-1 | open hand | riichi declared with suji [[2p]] |
| 260927-04d7d3c9 East 2-0 | riichi | 3-han tenpai push |
| 260928-95743bf4 South 2-0 | open hand | tile forced after a riichi declared against a two-call caller |
| 260928-e4fb5c17 East 4-0 | dama | open tenpai push |
| 260928-e154b24e South 2-3 | open hand | slip: [[9m]] suji against the riichi, live against the pon; [[9p]] safe against both (example) |

## Chapter 3 correction

Chapter 3's rule said to cut the safe tile whenever two tiles are equal. Its own evidence had LuckyJ taking a free
safe tile 56% of the time, and before the line from far hands the tie numbers above show the opposite choice three
times in four. The rule now says to cut the safe tile on a tie once the caller could be ready, and before that to
cut an equal live honor or terminal and keep the safe tile.
