# When to keep a big hand dama (guide chapter 24, 1 October 2026)

The user felt they had been declaring riichi too much lately and asked when to keep a big hand dama "to avoid
losing the point stick", then whether LuckyJ does not want the riichi's boost from 4 or 5 han to a 12,000
haneman. Five new games (30 September 18:46 to 1 October 11:57; places 4, 1, 3, 2, 3) were fetched with
`fetch_majsoul_games.py --since 2026-01-01` (140 games since January) and their replays built (87ea89a).

Inputs: `scripts/contrast/tenpai.py` on the user's 140 games and on LuckyJ's 1,079 Tokujou games
(`data/local_sources/luckyj_tenhou/index.json`, mode `tenhou-tokujou`). `scripts/mine_dama_value.py` writes
`analysis/dama-value-2026-10-01.json`; `scripts/build_dama_value_figure.py` draws the chart into both editions;
`tests/test_dama_value.py` pins every figure the chapter cites.

## Your riichis

| | before 29 Sep 16:00 | 17 games since | 5 newest | LuckyJ |
|---|---|---|---|---|
| Riichis per 100 hands | 19.0 | 23.2 | 30.4 | 19.3 |
| First closed tenpais per 100 hands | 24.8 | 26.8 | 28.3 | 23.6 |
| First tenpais declared | 72.0% | 80.0% | 92.3% (12 of 13) | 73.4% |
| Mortal's riichi weight on the same turns | | 72.0% | 87.0% | |

First tenpais worth 3 han or more on every winning tile, nobody in riichi: before, 25 of 53 declared against
27.0 expected from LuckyJ's rates; since 29 September, 5 of 7 against 2.9 (Mortal 1.9). The five newest
games' 14 riichis won 4, dealt in 3 (two of them riichis Mortal makes at 99%+) and lost the stick 7 times.

## LuckyJ's riichi share (first closed tenpai, nobody in riichi, value on every winning tile)

No yaku 85% (780); yaku on only some winning tiles 91% (139); 1-2 han 83% (727); other waits: 3 han 26% (109),
4 han 27% (93), 5+ han 12% (43).

Correction the same day, after the user said to tell pinfu 4 han from other 4 han: a closed ron scores 30 fu
with pinfu and 40 or more without it (seven pairs, 25 fu, aside), so two-sided hands are now sorted by the points
of their cheapest ron (`dama_han`/`dama_fu` from `contrast/tenpai.py`):

| two-sided, cheapest ron pays | hands | declared |
|---|---|---|
| 3,900 (3 han pinfu) | 160 | 88% |
| 5,200 or 6,400 (3 han, 40-50 fu) | 25 | 56% |
| 7,700 (4 han pinfu) | 60 | 58%, by turn below |
| a mangan or more (5 han, or 4 han at 40+ fu) | 41 | 32%, by turn below |

Of the 71 two-sided 4-han hands, 60 are pinfu and 11 at 40 fu. On other waits, 57 of the 93 four-han hands are
seven pairs at 25 fu (6,400), so those rows stay counted by han.

By turn (`fit_series`; series under 100 hands fitted as a straight logit line): 3,900 stays at 80% or more
through turn 13 and crosses half at 15.4; 7,700 is 86% at turn 4, crosses half at 10.75, 42% at 12; a mangan is
79% at turn 6, crosses half at 8.59, 23% at 11. The first version, by han alone, had 4 han crossing at 10.65 and
5+ han at 8.11. The chart now runs to turn 18.

## The riichi's boost at turn 11 (two-sided, non-dealer, six live tiles)

Fitted over all four seats of LuckyJ's games: 2,289 declared two-sided tenpais with a yaku against 208
two-sided tenpais worth 4+ han kept dama, with the turn as a spline and live tiles and dealer as terms.

| | dama | riichi |
|---|---|---|
| ron | 46.2% | 27.7% |
| tsumo | 16.3% | 20.9% |
| hand not won, average | -2,177 | -2,632 |
| 5 han, all told | 4,832 | 5,018 (+186; 95% -958 to +1,562) |
| 4 han at 40 fu, all told | 4,180 | 4,002 (-178; 95% -1,244 to +1,072) |
| 4 han pinfu, all told | 4,041 | 4,002 (-40; 95% -1,097 to +1,197) |

Win values use the non-dealer table, with the ura dora and ippatsu spread of 4,126 riichi wins (rons: no extra
han 55.9%, one 31.8%, two 8.9%, three or more 3.4%). With 3-han dama hands in the comparison the riichi leads
by up to 745 points, and the range still crosses zero.

Not robust, and not in the chapter: the turn where the riichi's price changes sign. With the dama group
limited to 4+ han it sits near turn 6-7; with 2+ or 3+ han it moves to about 12.8. The chat answer's
"riichi ahead by 1,200-1,500 by turn 9, dama ahead from turn 10" came from banded, cell-matched rates and
did not survive the fitted model. The chapter's rule therefore follows LuckyJ's fitted choices by turn.

## Chasing a riichi with three live tiles or fewer (LuckyJ, first tenpai)

No yaku 56% (54), 1-2 han 26% (34), 3 han 2 of 23, 4+ han 4 of 36.

## Chapter 23's "about a third"

Chapter 23 counted a hand by its best winning tile. Against callers from turn 10 with nobody in riichi, LuckyJ
declared 13 of 39 such 5+ han hands; counted on every winning tile, 2 of 23.
