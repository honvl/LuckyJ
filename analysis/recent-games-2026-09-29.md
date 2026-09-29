# Honver's games of 28 September evening, and keeping safe tiles early (29 September 2026)

The user: "I played more games, review my latest ones. I feel like I'm doing better now, winning more and losing
less. However I'm concerned that I'm not keeping the safe tiles correctly at the beginning." Then: "So I would
prioritize already-discarded guest wind over live guest wind, or also live value honor?" The answer is chapter 17
of the personal guide (`site/honver.html#early-safe-tiles`).

## Data

8 new games (28 September 17:00 to 23:30, 80 hands, places 3, 1, 2, 2, 2, 1, 2, 1, +683 rank points), 123 since
January. Scripts: `scripts/contrast/hands_all.py` (hand ledger), `scripts/review_recent_games.py ranks`,
`scripts/mine_early_safe_tiles.py` (leftovers, riichi, report), Mortal's ratings from `site/replays/`.

| | 94 before 24 Sep | 21 games 24-28 Sep | 8 new games | 29 since 24 Sep | LuckyJ (1,079 Tokujou) |
|---|---|---|---|---|---|
| won | 21.8% | 23.2% | 26.2% | 24.0% | 22.9% |
| average win | 6,150 | 5,322 | 7,967 | 6,093 | 7,317 |
| dealt in | 11.7% | 8.6% | 12.5% | 9.7% | 10.3% |
| lost to deal-ins, per hand | 546 | 414 | 528 | 444 | 546 |
| points per hand | +31 | +79 | +846 | +284 | +363 |

Rank points: 94 before, places 24/28/26/22%, -10.3 a game, average place 2.46; 29 since 24 September, 28/34/31/7%,
+39.4 a game, 2.17. LuckyJ Tokujou: 31.7/27.5/23.9/16.9%, 2.26.

## The ten deal-ins of the 8 new games, with Mortal

Mortal's probability for the tile cut: 7p 100%, 5s 100%, S 70%, 4s 100%, 8m 98%, 3m 98%, 4s 99% (seven of its own
choices); two forced after the player's riichi (declarations: Mortal riichi 100%, and 35% against 64% for 9m); one
mistake: 260929-8e871836 East 1-0 turn 4, East cut into kamicha's riichi from their third discard (Mortal 7s 67%,
chun 30%, East 1%).

## Safe tiles early (`analysis/early-safe-tiles-honver-2026-09-29.txt`)

- Same-kind leftovers, nobody threatening, against LuckyJ's fitted rate at the same discard: terminals 57/80
  (71.3%), middle tiles 28/71 (48.2%), two guest winds on discards 1-2 14/32 (23.2%), from discard 3 6/13 (67.9%).
- A live value honor against a guest wind already out: 29/203 value honor first (LuckyJ 25.3%, -4.5 SD). LuckyJ by
  discard 2/11/35/60/71/72%, fitted crossing 3.54; the player 0/3/14/35/54/66%, crossing 4.77.
- Mortal on the player's same turns (weight on the live tile of the two): value honor 13.2% overall
  (5/10/15/20/32/36% by discard 1-6); two guest winds 46.0% on discards 1-2 and 38.8% from 3; terminals 53.6/69.0%;
  middles 35.1/31.6%. So on honors the player plays Mortal's way and LuckyJ is the outlier: style, not a leak.
- Riichi faced while not tenpai (490 of the player's, LuckyJ's 6,668 at the same declarer discard): genbutsu held
  1.84 vs 1.90, none 17.8% vs 18.1%, first reply live 20.2% vs 20.2%, dealt in to it 7.6% vs 6.0%. By the declarer's
  fourth discard: none 42.9% vs 42.6%.
- LuckyJ's cuts against one riichi within its first six discards (`mine_riichi_folds.py` rows, 1,079 Tokujou games):
  live honor with no other copy showing 3.81 per 100 (105 cuts), with one copy showing 1.11 (180).

## Correction: the honor order on the third discard (`analysis/honor-order-2026-09-29.txt`)

The user asked what to throw on the third discard, since chapter 17's exception said to keep the guest wind that
is out "from the third" and to let a live value honor go "from your fourth". LuckyJ, by the lone honors held
(quiet, non-dealer, `mine_early_safe_tiles.py honors`): on the third discard a live guest wind goes first against
one already out 59.1% (22), against a live value honor 78.9% (327), with all three 54.5% (33); with only a guest
wind already out and a live value honor, the guest wind goes first 63.2% (285) on the third and 40.0% (225) on
the fourth. From the fourth both live honors go before the guest wind that is out (all three held: it goes first
11.1% on the fourth, 0% on the fifth). Chapter 17's exception and evidence note were corrected and marked
(`mark#fix-17-honors`, `mark#fix-17-honor-evidence`).
