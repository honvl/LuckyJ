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

## Status

No Wind-Up Bird review is cached yet (the token is made by hand on the site). `compare` fills in its side once
reviews are there: its score, its match rate and its severity without importance, beside both Mortal models on the
same games, with the interval of the difference.
