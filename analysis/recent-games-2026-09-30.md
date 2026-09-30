# Recent games, 29 and 30 September 2026: pushes against riichis and late riichis against callers

The user felt they keep doing well, pushing cheap, narrow open tenpais into riichis and answering open
tenpais with late riichis, and that it pays. Twelve new Jade South games (29 September 16:39 to 30
September 15:23) were fetched with `fetch_majsoul_games.py --since 2026-01-01`, their replays built with
`build_replays.py`, and the amae-koromo export refreshed.

## Results

Places 2 3 3 1 2 1 1 1 2 3 3 1: five firsts, no fourth, average place 1.92, +847 rank points
(`review_recent_games.py ranks`). At the long-run fourth rate, 17.0% since January, twelve games expect two
fourths. Since 1 January: 135 games, +1,025, places 26.7 / 28.9 / 27.4 / 17.0%.

## Tenpai against a riichi, every tenpai-keeping tile unsafe

`mine_tenpai_push.py compute data/self_games/majsoul/index.json 2026-01-01`, split into the 12 new games and
the 123 before; LuckyJ from `analysis/tenpai-push-luckyj-2026-09-24.txt`.

| | spots | pushed | pushes won | pushes dealt in | net a push |
|---|---|---|---|---|---|
| you, 12 new games | 23 | 87.0% | 40.0% | 15.0% | +2,475 |
| you, 123 before | 166 | 77.7% | 24.0% | 23.3% | −574 |
| LuckyJ, 1,255 games | 1,505 | 82.3% | 30.9% | 20.8% | +518 |

With 1–2 han the new games pushed 7 of 8 (before 56.0%, LuckyJ 73.4%). Mortal's first choice (the site's
replay ratings) matched the user's tile on 17 of the 23 spots, and on every cheap open push:
260930-22b377c9 East 4-1 turn 13 (2 han, 3 live, 7m, Mortal 99%), 261001-8fda859e East 3-1 (9p 100%),
260930-af991ffc East 4-0 (kan 93%) and South 2-0 (3p 100%), 260930-f21e479a East 2-0 (C 100%). The one cheap
open fold, 260930-22b377c9 East 2-0 turn 14, was a push for Mortal (4p 99%). The other disagreements:
260930-e1e10294 East 4-1 turn 7, a closed 4-han tenpai against the dealer's riichi, declared with 2m (Mortal
dama 2m 83%, riichi 12%); the 2m dealt in for 18,300 with ippatsu, so the tile was Mortal's too and only the
declaration was not. 260930-af991ffc South 3-0 turn 14 stayed dama where Mortal chased (riichi 97%).
260930-3f714fda South 3-0 turn 17 pushed 1p (Mortal 18%, 6s 72%). 260930-ce150fc2 South 3-0 turn 11 cut 5mr
where Mortal would kan (98%). 261001-8fda859e East 2-0 turn 12 pushed 6p where Mortal pushed 3p (84%).

The pushes won more and dealt in less than LuckyJ's do, 20 pushes against about 1,240: within about one
standard error each way.

## Closed tenpai against callers, nobody in riichi, from turn 10: declare or dama

`contrast/riichi_danger.py` on the user's 135 games and LuckyJ's 1,079 Tokujou games, the first decision of
each hand with riichi legal.

| | turn 10–12, one call | turn 10–12, two+ calls | turn 13+, one call | turn 13+, two+ calls |
|---|---|---|---|---|
| LuckyJ declared | 70% of 237 | 69% of 165 | 61% of 112 | 49% of 129 |
| you, 123 before | 68% of 28 | 74% of 19 | 38% of 13 | 22% of 9 |
| you, 12 new | 3 of 4 | 2 of 2 | 1 of 2 | none |

By the hand's value before riichi (turn 10+, callers only): LuckyJ declared 69% of yakuless tenpais, 74% at
1–2 han, 55% at 3–4 han and 32% at 5 han or more; the user over all 135 games 71%, 68%, 44% and 17%.

The eight new spots: the four yakuless tenpais were declared and Mortal agreed (94 to 100%). Two dama
tenpais that already had a yaku were declared where Mortal kept dama: 260930-ce150fc2 South 4-0 turn 12
(3 han dama, riichi 5%) and 260930-f5119e21 South 2-0 turn 11 (5 han dama, riichi 2%); both paid (+500 and
+12,000). 260930-f5119e21 East 4-0 (5 han) stayed dama with Mortal (riichi 4%), and 260930-22b377c9 South 4-0
(2 han) stayed dama where Mortal was even (50%).

## Added for chapter 23

Declare rates by turn band, first decision of each hand, callers only (turn 10–12 / 13+): LuckyJ 280 of 402
(70%) and 131 of 241 (54%); the user before these games 33 of 47 (70%) and 7 of 22 (32%); the 12 new games
5 of 6 and 1 of 2.

Chasing a riichi with a closed tenpai (`mine_tenpai_push.py` rows, closed pushes, han counted with the
riichi): LuckyJ by its 9th turn declared 76% of 98 pushes at 3 han or less and 43% of 61 at 4 han or more;
from its 10th turn 54% of 130 and 31% of 144. The 260930-e1e10294 East 4-1 chase was a 4-han push at turn 7.
