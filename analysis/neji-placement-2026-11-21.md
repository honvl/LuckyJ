# Does a game's review grade say where you finished? (21 Nov 2026)

Question: Wind-Up Bird (Nejimakidori) grades a game by severity times importance. Is that grade much more
suggestive of the place in the game than the ratings the two Mortal models give the same game?

Scripts: `scripts/fetch_neji_reviews.py` (reviews into `data/neji_reviews/`), `scripts/neji_placement_check.py`
(`baseline`, `compare`, `power`). Numbers: `analysis/neji-placement-2026-11-21.json`.

## What the Mortal ratings do today

Spearman correlation of one seat's rating in a game with that seat's place in the same game (negative = a better
rating goes with a better place).

| Games | Mortal policy, best statistic | Mortal-S42, match rate | Mortal-S42, mean Q loss |
| --- | --- | --- | --- |
| Jade, every seat (1,443 seat-games) | -0.119 | -0.126 | -0.153 |
| Jade, your seat (361) | -0.099 | -0.156 | -0.185 |
| Houou, every seat (63,675) | +0.004 | -0.018 | -0.038 |

A game's rating explains 2 to 3% of the spread in its place in the Jade room and almost none in Houou. The deal
decides most of one game.

## What weighting by stakes adds inside one model

Mean Q loss is already weighted by what each decision is worth; match rate counts every decision the same. Same
model, same games:

- Jade, every seat: -0.028 [-0.054, -0.002]
- Houou, every seat: -0.020 [-0.024, -0.015]

So stakes add about 0.02 to 0.03 of correlation. That is the size to expect from importance weighting unless
Wind-Up Bird's weights carry something Q-values do not.

## What it takes to answer for Wind-Up Bird

Reviews needed to tell its grade from Mortal-S42's -0.15 on the same games (80% power):

| Its correlation with place | Reviews, if the two grades correlate 0.5 | if 0.7 |
| --- | --- | --- |
| -0.40 | 111 | 68 |
| -0.30 | 325 | 195 |
| -0.25 | 744 | 445 |
| -0.20 | 3,009 | 1,797 |

A token covers 24 reviews. One token can only show a very large gap; a gap worth calling "much better" (-0.30 or
beyond) needs 200 to 330 reviews, which is most of the 361 rated Jade games.

## The answer: all 361 rated Jade games, your seat

Every game was reviewed by Wind-Up Bird and both Mortal models. Same Spearman correlation with the place.

| Rating | Correlation with place |
| --- | --- |
| Wind-Up Bird: score (severity × importance) | -0.197 [-0.297, -0.093] |
| Wind-Up Bird: severity without importance | -0.198 [-0.301, -0.094] |
| Wind-Up Bird: match rate | -0.135 [-0.237, -0.032] |
| Wind-Up Bird: total EV loss | -0.017 [-0.118, +0.086] |
| Mortal-S42: mean Q loss | -0.185 [-0.290, -0.079] |
| Mortal-S42: mean ln p | -0.184 [-0.290, -0.076] |
| Mortal-S42: match rate | -0.156 [-0.261, -0.051] |
| Mortal policy: match rate | -0.099 [-0.203, +0.004] |

| Difference | Size |
| --- | --- |
| Wind-Up Bird's score minus Mortal-S42's mean Q loss | -0.012 [-0.104, +0.085] |
| Wind-Up Bird's score minus its own severity without importance | +0.001 [-0.069, +0.073] |
| Wind-Up Bird's score minus its own match rate | -0.062 [-0.145, +0.026] |

- The importance grade is not more suggestive of the place than Mortal-S42's rating: -0.197 against -0.185.
  With 361 games a gap of 0.10 or more would have shown; "much better" is ruled out.
- Importance adds nothing to Wind-Up Bird's own grade on these games (+0.001). What lifts its score above its
  match rate is severity, the same step as S42's Q loss over S42's match rate.
- The two reviewers correlate +0.55 and each keeps a little once the other is known (Wind-Up Bird given S42
  -0.115 [-0.213, -0.013]; S42 given Wind-Up Bird -0.093 [-0.200, +0.010]). Two models' opinions together say
  slightly more than either alone.
- The interim reading on the first 63 games (-0.245) was sampling: the interval then was [-0.455, -0.012].

`analysis/importance-2026-11-21.md` has the follow-up: an importance weighting of our own on S42, and the
across-games test of whether it measures the player.
