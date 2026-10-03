# Recent games, 30 September to 3 October 2026: is the losing a leak?

The user asked how their recent games are going, having "lost a few lately". Twenty new games were fetched on
3 October (160 since January); with the five another session fetched on 1 October, 25 games follow the chapter
23 review (the last was 261001-8fda859e, 30 September 15:23). Replays with Mortal's ratings were built for all
of them (`build_replays.py --only`).

## Results

25 games: 7 firsts, 6 seconds, 8 thirds, 4 fourths, average place 2.36. Rank points (`review_recent_games.py
ranks`, the amae-koromo export, which lacks the newest game): +445 over the last 25, −173 over the last 11 with
three fourths where 1.9 were expected at the long-run 17.0%. Three or more fourths in 11 games happens about 28%
of the time at that rate.

## Hands (`contrast/hands_all.py`, the user's seat)

| | games | avg place | 4ths | won | avg win | dealt in | avg deal-in | net a hand |
|---|---|---|---|---|---|---|---|---|
| before 24 Sep | 94 | 2.46 | 22.3% | 21.8% | 6,150 | 11.7% | −4,687 | +31 |
| 24–30 Sep | 41 | 2.10 | 4.9% | 24.9% | 6,406 | 10.4% | −4,952 | +338 |
| last 25 | 25 | 2.36 | 16.0% | 21.7% | 7,733 | 9.6% | −4,939 | +453 |
| of which the last 11 | 11 | 2.55 | 27.3% | 20.4% | 7,536 | 13.0% | −4,064 | +321 |
| LuckyJ | | | | 22.9% | 7,317 | 10.3% | −5,308 | +363 |

## Decisions (Mortal's ratings in the site's replays)

Mortal's first choice: 76.6% of 14,189 decisions before 24 September, 76.7% of 6,098 on 24–30 September, 78.8%
of 1,850 in the first 14 of the last 25 games, 75.9% of 1,501 in the last 11. Turns Mortal rated under 5%: 7.8,
7.7, 7.0 and 7.3%. Calls: the user called 24.1% of 315 chances in the last 11 where Mortal's call probability
averaged 25.7%; called where Mortal passes 95%+ on 1.9%, passed where it calls 95%+ on 2.9% (before 24 September
1.9 and 2.0%).

## The four fourths

- 261001-d251c2a0 (30 Sep 18:46): no win, two tenpais in nine hands, points lost to others' wins and draws.
- 261002-b0ec9f2d (1 Oct 22:59): three deal-ins, each Mortal's choice: East 2-0 turn 19, a last-discard 2p into
  a houtei (99%); East 3-0 turn 8, a riichi (99%) declared with 6s (37%, 7s 63%) into a two-dragon open hand;
  East 4-1 turn 9, a riichi (100%) with 9p into a riichi.
- 261003-9f797d54 (2 Oct 14:37): East 4-1 turn 15, a three-call tenpai pushing 3s into a riichi (100%), ippatsu
  for 8,300; South 4-1 turn 10, 4m into an open hand (93%).
- 261003-3b706dd7 (2 Oct 21:23): no win and no deal-in; points lost to tsumo. In East 4-0, three-shanten and then
  two-shanten against a riichi, the user held the genbutsu 8m and cut W (turn 10), 8p, 2p and 1s (turn 13) where
  Mortal cut 8m at 95 to 100% each turn.

## Far hands against a riichi (`mine_riichi_folds.py`)

Live cuts while a safe tile was in hand, by best shanten (tenpai / 1 / 2 / 3+): before 24 September 35.4 / 13.6 /
2.9 / 3.0%; 24–30 September 30.3 / 12.8 / 4.9 / 4.0%; first 14 of the last 25 50.0 / 19.5 / 5.7 / 6.7%; last 11
40.0 / 13.5 / 10.5 / 11.8%; LuckyJ 38.3 / 16.6 / 6.2 / 2.9%. Of the ten far-hand live cuts in the last 11, seven
were Mortal's first choice (mostly early live honors, 93 to 100%); the three against it were the two turns of
261003-3b706dd7 East 4-0 above and 261003-5792c141 East 3-0 turn 12 (8m, Mortal 6s 98%). None dealt in.
