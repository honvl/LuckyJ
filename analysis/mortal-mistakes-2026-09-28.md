# Mortal across 115 games: the mistakes LuckyJ does not make (28 September 2026)

The user: "Look at some more of my games with mortal and aggregate any common mistakes to write me a new chapter (but
not ones that LuckyJ would think are fine moves)". The answer is chapter 16 of the personal guide
(`site/honver.html#fold-later`).

## Method

- `scripts/contrast/choices.py MANIFEST OUT.jsonl` writes one row per discard of the manifest's hero, with every tile
  it could cut: shanten and acceptance left, tile class, dora and red flags, isolation, and safety against the riichi
  players (worst label) or the opponents with the most calls, plus `pond`, the discards of the most advanced threat.
  Run over Honver's 115 games since January and LuckyJ's 1,079 Tokujou games (LuckyJ's seat).
- Mortal's probabilities: Honver's from the site's replay files (`scripts/build_replays.py` stores them for every
  decision), LuckyJ's from `mortal_lj.jsonl` (`scripts/contrast/mortal_run.py`). Joined on (game, hand, turn): 13,101
  of Honver's discards and 124,887 of LuckyJ's, riichi declarations aside; every cut and riichi flag lines up.
- The filter for "LuckyJ would think it fine": a kind of disagreement counts only when Honver makes it more often
  than LuckyJ in the same kind of spot. Two measures, which agree: Mortal-conditioned (where Mortal puts 60% or more on
  one tile, how often each player picks something it gives under 10%) and behavior only (LuckyJ's own choice in spots
  defined by the hand features, with no Mortal in the definition).
- `scripts/contrast/report/fold_later.py REPLAYS LJ_MANIFEST SELF_MANIFEST` prints every figure below.

## What is shared

| on the table | Honver, discards Mortal gives <10% | LuckyJ |
|---|---|---|
| nobody threatening | 11.5% (6,926) | 11.4% (64,770) |
| one call | 11.9% (2,632) | 12.7% (24,776) |
| a riichi | 12.5% (2,171) | 10.7% (21,564) |
| two calls or more | 19.2% (1,372) | 12.4% (13,777) |

Mortal's first choice: Honver 71.8%, LuckyJ 72.6%. Efficiency (lost acceptance with nobody threatening 4.55 vs 4.81 per
100), honor order (Mortal-conditioned ties 3-8% either way), pushes into a riichi where Mortal folds (3.6 vs 4.1 per
100 discards facing a riichi) and calls (against a confident Mortal: called 2.6% vs 2.2% of sure passes, passed
16.6% vs 13.2% of sure calls) are shared or close. Folding then pushing within three turns after paying for safety:
24% vs 24% against a riichi, 58% vs 61% against two calls, so not a habit of Honver's.

## What is Honver's

Mortal-conditioned, took a safer tile Mortal gives under 10%: against a riichi 75/408 (18.4%) vs 385/4,137 (9.3%),
z 4.6; against two calls or more 108/711 (15.2%) vs 589/6,869 (8.6%), z 4.8; against one call 7.8% vs 8.0%. Against
two calls, Honver's rate went from 12.9% (559) before 24 September to 23.7% (152) since.

1. Two calls, first row (caller has discarded 6 or fewer): a safe tile that costs acceptance or a shanten is taken
   47/170 (27.6%) vs 203/1,391 (14.6%), z 3.7; 21.8% before 24 September, 43.5% since. On a tie (same shanten,
   acceptance within one, a genbutsu or 2-seen honor against a live tile) the safe tile is cut 39/64 (60.9%) vs
   234/638 (36.7%), z 3.8. From the seventh discard on: 27.8% vs 25.6% and 70.0% vs 63.5%.
2. A riichi, 1-shanten, the safest tile breaks the shanten, before turn 13, two dora or more: LuckyJ breaks 37%, keeps
   it with a suji or 2-seen honor 15% and with a live tile 48% (451); Honver 55%, 10%, 35% (69). With 0-1 dora: LuckyJ
   51/12/37 (1,414), Honver 58/16/25 (118). From turn 13: LuckyJ breaks 70% (0-1 dora) and 61% (2+), Honver 85% and
   79%. Mortal-conditioned with two dora or more: paid shape for the safer tile 32/172 (18.6%) vs 87/1,400 (6.2%).
3. Rare: dama where Mortal declares 90%+ with nobody in riichi, 21/176 (11.9%) vs 86/1,482 (5.8%); by behavior alone
   the narrow first-tenpai riichi rate is 60.4% vs 61.4%, so it stays a note.

## Examples

`first-row-genbutsu` (260928-95743bf4 South 2-0 T5), `first-row-west-pair` (260928-e154b24e East 2-0 T7),
`first-row-tie` (260923-275bb855 South 2-1 T6), `three-triplets-folded` (260920-900a1166 East 4-0 T12),
`three-red-fives` (260620-c57a2076 East 3-1 T9). In the first and last, Honver declared riichi within three turns of
paying for the safe tile.
