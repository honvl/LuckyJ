# Saint 3 to Celestial (Jade) against 8-dan and 9-dan (Houou), on one Mortal scale

20 November 2026. Second version: the full Houou month, a 40,000-table Jade sample, and 9-dan added. Third
version, the same evening: the same games scored again on Mortal-S42.
Scripts: `scripts/mine_ladder_skill.py` (scores every seat), `scripts/compare_ladders.py` (everything below).
Outputs: `ladder-compare-2026-11-20.json` (all decisions) and `ladder-compare-discards-2026-11-20.json`
(discards only, same conclusions).

## Answer

Celestial is harder than 8-dan and harder than 9-dan. On Mortal-S42, the project's model since 20 November, a
player at the Houou average is about 86% to go from 7-dan to 8-dan, 51% to go from 8-dan to 9-dan, 75% to reach
9-dan starting at 7-dan, and 21% to go from Saint 3 to Celestial. On the earlier policy model the same four
figures were 86%, 50%, 70% and 31 to 40%, which read as "a little harder than 9-dan".

## Third version: the same games on Mortal-S42

Every game was scored again with Mortal-S42 (`mine_ladder_skill.py --qmodel`, the 361 Jade games and the first
2,000 Houou games on the Mac, the other 13,929 on GitHub runners through `.github/workflows/ladder-score.yml`;
6,304 seats scored on both agree exactly). Skill is the mean ln p of the action taken, with p the softmax of
S42's Q-values at temperature 0.6 (`compare_ladders.py --metric lp06`). Outputs:
`ladder-compare-s42-2026-11-20.json` and `ladder-compare-s42-discards-2026-11-20.json`.

| | Earlier policy model | Mortal-S42 |
|---|---|---|
| Jade Master 1 / 2 / 3 | -1.025 / -0.905 / -0.826 | -0.823 / -0.698 / -0.627 |
| Jade Saint 1 / 2 / 3 | -0.813 / -0.758 / -0.766 | -0.609 / -0.557 / -0.546 |
| Houou 七段 / 八段 / 九段 / 十段 / 天鳳 | -0.698 / -0.663 / -0.653 / -0.673 / -0.641 | -0.514 / -0.487 / -0.479 / -0.482 / -0.484 |
| Skill per Mahjong Soul rank step | 0.0621 ± 0.0046 | 0.0633 ± 0.0042 |
| Jade field, in rank steps (Master 1 = 0, Saint 3 = 5) | 1.35 | 1.35 |
| Houou field, in rank steps | 5.12 | 4.70 |
| The user, in rank steps | 5.27 | 3.99 |
| Beta, Jade (room sample per rank step) | 0.73 ± 0.07 | 0.71 ± 0.07 |
| Beta, Houou (986 repeat players) | 0.27 ± 0.08 | 0.19 ± 0.09 |
| Even-odds skill in rank steps: 7 to 8 / 8 to 9 / 7 to 9 / Celestial | 0.6 / 5.0 / 3.5 / 5.4 | -1.3 / 4.3 / 2.1 / 5.5 |
| Houou-average player: 7 to 8 / 8 to 9 / 7 to 9 / Celestial | 86 / 50 / 70 / 31% | 86 / 51 / 75 / 21% |
| The same, discards only | 86 / 50 / 78 / 40% | 86 / 51 / 75 / 22% |
| The user, skill from Mortal | 86 / 49 / 74 / 44% | 83 / 44 / 66 / 8% |
| The user, skill from Jade results | 91 / 68 / 87 / 88% | 90 / 65 / 85 / 86% |
| One shared beta (0.55 / 0.54), Houou-average player | 86 / 52 / 73 / 9% | 85 / 50 / 75 / 7% |
| Shared beta above which Celestial stops being harder: 7 to 8 / 8 to 9 / 7 to 9 | 1.09 / 0.81 / 0.92 | 1.18 / 0.86 / 0.99 |

What holds on both models: the Houou field plays about like a table of Saint 3s, the Jade field like Master 2
to 3, the Jade beta is about 0.7, and Celestial is the hardest of the four climbs for a Houou-average player.
On S42 the rank order is cleaner (Saint 3 is above Saint 2, which the earlier model had reversed) and the
Celestial gap over 9-dan is wider (5.5 rank steps against 4.3 for even odds).

What moves is the user. The earlier model put the user above the Houou field (5.27 rank steps); S42 puts the
user at Saint 3 (3.99), below the average Houou 7-dan. In match rate: 78.0% against Houou's 77.7% on the earlier
model, 80.2% against Houou's 81.3% on S42. The Mortal-based odds for Celestial fall from 44% to 8%. The
results-based odds do not move (86 to 88%), because they come from the user's Jade placement (2.324) and not
from either model. S42 predicts a Jade place of 2.411 for the user and the earlier model 2.367, so the earlier
model is closer to what happened. The guide's chapters were built on the earlier model, so the user's play may
simply follow that model's preferences more than S42's; this is not tested.

Which statistic predicts placement better, among the 986 Houou repeat players over the full month (place
against the player's statistic in their other games, shrunk, clustered by player):

| Statistic | Places per SD of skill | t |
|---|---|---|
| Earlier policy model: mean ln p | 0.0162 ± 0.0051 | 3.2 |
| Earlier policy model: match rate | 0.0138 ± 0.0051 | 2.7 |
| S42: mean ln p at temperature 0.6 | 0.0111 ± 0.0052 | 2.1 |
| S42: RMS loss per move | 0.0149 ± 0.0051 | 2.9 |
| S42: match rate | 0.0079 ± 0.0051 | 1.6 |

The two models' statistics correlate 0.93 across players. S42's is the weaker predictor by about one standard
error, so the difference is not established; used together neither adds to the other (t 1.1 and 0.0). Everything
below this section is the second version, on the earlier policy model.

## Data

- Houou: all 15,929 four-player hanchan played 6 Oct to 5 Nov 2026 (Tenhou's public `scc` index, logs from
  `mjlog2json.cgi`, stored in the gitignored `data/tenhou_houou_2026/`). 63,675 seats scored: 38,448 七段,
  18,244 八段, 6,042 九段, 867 十段, 74 天鳳. 41 seats from abandoned games are left out.
- Jade, with logs: the 361 Jade South games in `data/self_games/majsoul/` (Jan to Nov 2026), all four seats.
- Jade, results only: 40,000 Jade South tables from 23 Oct to 20 Nov 2026 (amae-koromo), rank and place of
  every seat.

## Skill scale

Skill = mean ln p of the action the player took, under the local Mortal policy model, over every decision with
two or more legal actions (about 156 a game). Higher is closer to Mortal.

| Group | Skill | Mahjong Soul rank steps (Master 1 = 0, Saint 3 = 5) |
|---|---|---|
| Jade Master 1 / 2 / 3 | -1.025 / -0.905 / -0.826 | |
| Jade Saint 1 / 2 / 3 | -0.813 / -0.758 / -0.766 | |
| Jade field (the user's opponents) | -0.918 | 1.35 |
| Houou 七段 / 八段 / 九段 / 十段 / 天鳳 | -0.698 / -0.663 / -0.653 / -0.673 / -0.641 | |
| Houou field | -0.6835 ± 0.0007 | 5.12 |
| The user | -0.675 | 5.27 |

The Houou field plays like a table of Saint 3s; the user's Jade tables average Master 2 to 3.

## Places per unit of skill (beta)

| Method | beta |
|---|---|
| Jade room sample: 0.0452 places per rank step, over 0.0621 skill per step | 0.73 ± 0.07 |
| Jade room sample: Saints place 0.127 better than Masters at 24,071 mixed tables, over a 0.178 skill gap | 0.71 ± 0.08 |
| Houou, 986 players seen 4+ times: place against skill in their other games, shrunk, clustered SE | 0.27 ± 0.08 |
| Houou dan tiers: 0.033 places per dan over 0.023 skill per dan | 1.43 (not used) |

The two rooms differ by 0.46 ± 0.11. Mortal agreement separates Masters from Saints well; among Houou regulars
the same gap in agreement is worth about a third as many places. The first version of this note had 0.78 ± 0.17
for Houou from 3,000 games, which was a high draw: four random quarters of the full month give 0.13 to 0.36.

So each climb uses its own room's beta. Check on the Jade figure: it predicts a Jade mean place of 2.367 for the
user's skill; the measured place is 2.324. One shared beta (0.55, the inverse-variance mean) predicts 2.400.

## Climbs

Thurstone placement model (performance = k * skill + normal noise, k set by the room's beta), three opponents
at the room's field skill, one attempt from the start of the level until promotion or demotion. The 7-to-9
chain drops an 8-dan who falls below 0 back to 7-dan at 1,400 and ends when a 7-dan is demoted.

- Houou 7-dan: 1,400 to 2,800, +90/+45/0/-120. Break-even mean place 2.556 (4th 26.8%).
- Houou 8-dan: 1,600 to 3,200, +90/+45/0/-135. Break-even mean place 2.500 (4th 25.1%).
- Jade Saint 3: 4,500 to 9,000, +144/+65/-9/-272. Break-even mean place 2.359 (4th 20.9%).

An average Houou player earns points at 7-dan and breaks even at 8-dan, whatever beta is. For Celestial the
same player has to place 0.14 better than the Jade average; the field gap (0.2345 skill) times the Jade beta
gives 0.12 to 0.13.

| Climb | Skill for even odds (rank steps) | Houou-average player | The user, skill from Mortal | The user, skill from Jade results | Median games |
|---|---|---|---|---|---|
| Houou 7 to 8 | 0.6 | 86% | 86% | 91% | 205 |
| Houou 8 to 9 | 5.0 | 50% | 49% | 68% | 290 |
| Houou 7 to 9 | 3.5 | 70% | 74% | 87% | 700 to 900 |
| Jade Saint 3 to Celestial | 5.4 | 31% | 44% | 88% | 550 to 700 |

The 0.6 for 7 to 8 extrapolates the Houou beta far below the Houou range; read it as "anyone who belongs in
Houou". Discards only: 1.1 / 4.8 / 3.2 / 5.4 rank steps, and the Houou-average player is 86 / 50 / 78 / 40%.

The user's two readings differ most for Celestial (44% against 88%) because the measured Jade place (2.324) is
better than Mortal agreement predicts (2.367). The results-based pace, +5.0 a game, matches the measured climb
pace (+4.9, ch51).

### With one shared beta (0.55)

| Climb | Skill for even odds (rank steps) | Houou-average player | The user, skill from Mortal |
|---|---|---|---|
| Houou 7 to 8 | 3.1 | 86% | 86% |
| Houou 8 to 9 | 5.3 | 52% | 53% |
| Houou 7 to 9 | 4.2 | 73% | 78% |
| Jade Saint 3 to Celestial | 6.8 | 9% | 14% |

Celestial is then much the hardest. With one shared beta, Celestial stops being harder than 7 to 8 only above
1.09, than 7 to 9 above 0.92, and than 8 to 9 above 0.81. Both rooms measure below those.

## Would a different Mortal measure skill better?

The local model has a policy head and no value head, so the skill statistic is agreement with its policy. Three
public Mortal v4 checkpoints carry a value head (Q-values in final-placement points): `mortal_298k` (VoidShine),
`mortal_582500` (Yuchen1457) and `s42-inference` (haor/Mortal-S42), all 40 blocks by 192 channels, all trained
offline with a penalty on rare moves.

**Q statistics against the current one.** 3,000 Houou games (11,996 seats) scored with the 298k model
(`mine_ladder_skill.py --qmodel`), then each statistic raced on the same seats: place regressed on a player's
statistic in their other games, 711 players with 4+ games.

| Statistic | Places per SD of skill | t |
|---|---|---|
| Current: mean ln p, policy model | 0.047 ± 0.010 | 4.7 |
| Current model: match rate | 0.051 ± 0.010 | 4.9 |
| Q model: mean loss per move | 0.035 ± 0.010 | 3.6 |
| Q model: RMS loss | 0.037 ± 0.010 | 3.8 |
| Q model: match rate | 0.037 ± 0.011 | 3.6 |
| Q model: share of moves losing over 1 point | 0.035 ± 0.010 | 3.5 |

Mean Q loss correlates 0.93 with the current statistic across 449 players with ten or more games. With both in
one regression the current statistic keeps its effect (t 2.2) and the best Q statistic adds nothing (t -0.7).

**Strength by play.** `scripts/mortal_duel.py`: each checkpoint takes one seat against three copies of the local
policy model, 2,000 seeds dealt four times each (8,000 hanchan per checkpoint, the same deals for all three).
Seeds 10000 to 10839 and 11400 to 11439 were played on the Mac, the rest on GitHub runners
(`.github/workflows/duel.yml`). Result file: `mortal-duel-2026-11-20.json`. An average rank of 2.5 is level with
the local model.

| Checkpoint | Average rank | 95% interval | 1st / 2nd / 3rd / 4th |
|---|---|---|---|
| s42-inference | 2.458 | 2.436 to 2.480 | 27.5 / 24.6 / 22.6 / 25.3% |
| mortal_582500 | 2.477 | 2.456 to 2.497 | 26.6 / 23.8 / 24.9 / 24.7% |
| mortal_298k | 2.489 | 2.467 to 2.511 | 26.2 / 23.9 / 24.8 / 25.1% |

Paired on the same deals, S42 is ahead of the 298k model by 0.031 places (0.002 to 0.061) and of the 582,500-step
model by 0.019 (-0.005 to 0.043); the two older checkpoints differ by 0.012 (-0.016 to 0.039). S42 is the
strongest of the three by a small margin and about 0.04 places ahead of the local model. None is a clear step
up, and the one Q model tested as a yardstick predicts placement worse than the current statistic, so the skill
scale stays on the local policy model.

## Limits

- Mortal agreement is one view of skill. Among Houou regulars it explains little of who places well, and
  Tenhou's own rating adds to it (correlation 0.29 across players, both predict placement together).
- The same policy scores both sites, but rules and interfaces differ a little, and that could move the
  cross-site field gap (0.2345), which the Celestial row rests on.
- Each row is one attempt at one level. Getting into Houou (7-dan with R2000) and reaching Saint 3 are not
  modelled.
- The Jade field is the user's own opponents, which is the room as a Saint 3 player meets it.
