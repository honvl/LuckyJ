# Saint 3 to Celestial (Jade) against 7-dan to 8-dan (Houou), on one Mortal scale

20 November 2026. Scripts: `scripts/mine_ladder_skill.py` (scores every seat), `scripts/compare_ladders.py`
(everything below). Outputs: `ladder-compare-2026-11-20.json` (all decisions) and
`ladder-compare-discards-2026-11-20.json` (discards only, same conclusions).

## Data

- Houou: 3,000 four-player hanchan drawn at random from the 15,929 played 6 Oct to 5 Nov 2026 (Tenhou's
  public `scc` index, logs from `mjlog2json.cgi`, stored in the gitignored `data/tenhou_houou_2026/`).
  11,996 seats: 7,251 七段, 3,424 八段, 1,130 九段, 178 十段, 13 天鳳.
- Jade: the 361 Jade South games in `data/self_games/majsoul/` (Jan to Nov 2026), all four seats: 1,082
  opponent seats and the user.

## Skill scale

Skill = mean ln p of the action the player took, under the local Mortal policy, over every decision with two or
more legal actions (about 150 a game). Higher is closer to Mortal.

| Group | Skill | Mahjong Soul rank steps (Master 1 = 0, Saint 3 = 5) |
|---|---|---|
| Jade Master 1 / 2 / 3 | -1.025 / -0.905 / -0.826 | |
| Jade Saint 1 / 2 / 3 | -0.813 / -0.758 / -0.766 | |
| Jade field (the user's opponents) | -0.918 | 1.35 |
| Houou 七段 / 八段 / 九段 / 十段 | -0.699 / -0.662 / -0.651 / -0.671 | |
| Houou field | -0.683 | 5.12 |
| The user | -0.675 | 5.27 |

The Houou field plays like a table of Saint 3s; the user's Jade tables average Master 2 to 3.

## Places per unit of skill (beta)

| Method | beta |
|---|---|
| Mahjong Soul: Saints place 0.144 better than Masters at mixed tables, over a 0.178 skill gap | 0.81 ± 0.23 |
| Mahjong Soul: 0.0527 places per rank step, over 0.0621 skill per step | 0.85 |
| Houou players seen 4+ times: place against skill from their other games, shrunk, clustered SE | 0.78 ± 0.17 |
| Houou dan tiers: 0.066 places per dan over 0.024 skill per dan | 2.74 (outlier) |

Three independent estimates agree on about 0.8. Dans differ in placement more than in Mortal agreement, so the
dan ratio is not used. Check: with beta 0.81 the user's skill predicts a Jade mean place of 2.352; the
measured place in these games is 2.324.

## Climbs

Thurstone placement model (performance = k * skill + normal noise, k set by beta), three opponents at the room's
field skill, one attempt from the start of the level until promotion or demotion.

- Houou 7-dan: 1,400 to 2,800, +90/+45/0/-120. Break-even mean place 2.554 (4th 26.6%).
- Jade Saint 3: 4,500 to 9,000, +144/+65/-9/-272. Break-even mean place 2.363 (4th 21.1%).

The stronger Houou field costs about 0.75 * 0.81 * 0.235 = 0.14 places; Houou's kinder payouts allow 0.19 places
more. Skill for a 50% chance of promotion:

| beta | Houou 7 to 8 | Jade S3 to Celestial |
|---|---|---|
| 0.66 | -0.795 | -0.634 |
| 0.80 | -0.772 (about Saint 1-2) | -0.687 (about Saint 3, the Houou average) |
| 1.00 | -0.757 | -0.732 |
| 1.20 | -0.747 | -0.762 |

The answer flips only near beta 1.1, about 1.5 standard errors above the estimates.

The user (beta 0.81):

| | Mean place | Pts/game | P(promote per attempt) | Median games |
|---|---|---|---|---|
| Houou 7-dan, skill from Mortal | 2.491 | +4.3 | 88% | 199 |
| Jade Saint 3, skill from Mortal | 2.353 | +1.2 | 62% | 690 |
| Houou 7-dan, skill from Jade results | 2.466 | +6.0 | 94% | 168 |
| Jade Saint 3, skill from Jade results | 2.325 | +4.6 | 87% | 561 |

The results-based Jade pace (+4.6) matches the measured climb pace (+4.9/game, ch51).

## Conclusion

On the last step, 7-dan to 8-dan in Houou is somewhat easier than Saint 3 to Celestial in Jade: it needs about
1.4 fewer Mahjong Soul rank steps of skill for even odds, and a third of the games. A player who plays like an
average Houou regular is a coin flip for Celestial and an 85-90% favourite for 8-dan.

## Limits

- Mortal agreement is one view of skill; the dan anomaly shows it misses some of what separates dans.
- The same policy scores both sites, but the rules and interfaces differ a little, and that could move the
  cross-site field gap (0.235).
- Only the last step is compared. Getting into Houou (7-dan with R2000) and reaching Saint 3 are not modelled.
- The Jade field is the user's own opponents, which is the room as a Saint 3 player meets it.
