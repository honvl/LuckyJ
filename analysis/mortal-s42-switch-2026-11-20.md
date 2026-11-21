# Mortal-S42 becomes the project's model

20 November 2026. From here on the scripts load Mortal-S42 (haor/Mortal-S42 on Hugging Face, Apache-2.0 weights,
`~/Downloads/mortal_q/s42-inference.pth`) through `scripts/mortal_engines.py` (`default_engine()`), in place of the
local policy model (`~/Downloads/mortal_model_policy`, a community fork with no licence file).

Why S42: in the three-way duel it was the strongest public checkpoint and about 0.04 places ahead of the earlier
model (`ladder-compare-2026-11-20.md`, `mortal-duel-2026-11-20.json`).

## From Q-values to percentages

The earlier model had a policy head, so a reaction carried probabilities. S42 has a value head: a reaction carries
Q-values in final-placement points (2 a place). Every script reads percentages, so `default_engine()` reports
softmax(Q / 0.6) over the legal actions. The move it plays is the highest Q whatever the temperature.

The temperature was set on 168 recent Jade games (all four seats, 103,678 decisions with two or more legal
actions), both models replaying the same decisions (`scripts/mortal_two_models.py`, then
`scripts/mortal_calibrate.py`).

| Temperature | Mean top probability | Mean entropy | Total variation from the earlier model | Played move under 10% | under 25% |
|---|---|---|---|---|---|
| Earlier policy model | 0.862 | 0.369 | | 13.2% | 19.2% |
| 0.10 | 0.974 | 0.063 | 0.180 | 19.2% | 20.7% |
| 0.30 | 0.923 | 0.188 | 0.151 | 13.9% | 18.0% |
| **0.60** | **0.854** | **0.363** | **0.132** | **8.8%** | **15.0%** |
| 1.00 | 0.773 | 0.579 | 0.153 | 5.2% | 12.7% |

At 0.6 S42's percentages are as spread out as the earlier model's (top probability and entropy both match) and the
two models' distributions are closest. A temperature of 0.6 means a move that costs 0.3 places gets about a third
of the best move's weight.

## What changes in the numbers

- The two models name the same first choice on 86.1% of decisions (83.3% of discards).
- S42 agrees with the players more often: the played move is its first choice 77.7% of the time against 74.1% for
  the earlier model (the user's own decisions: 80.8% against 78.4%).
- So at the matched temperature fewer played moves fall under a threshold: under 25%, 15.0% against 19.2% (the
  user: 12.1% against 15.2%); under 10%, 8.8% against 13.2%. A count such as chapter 51's "under 25%" cuts will
  come out lower with S42 for the same games. Thresholds in chapters up to 52 belong to the earlier model.
- The temperature that best predicts what Jade players do is higher, about 1.0 (mean ln p of the played move
  -0.586, against -0.845 for the earlier policy model). It is not used: the percentages are meant to read like
  the earlier ones.

## What stays on the earlier model

- Published replays. `build_replays.py` now leaves a game that already has a replay alone and records the model
  per game in `site/replays/index.json`; `--rebuild` redoes every game. All 361 published replays are unchanged.
- Chapters 1 to 52 and their data files.
- The ladder comparison's skill scale (`mine_ladder_skill.py` names its model explicitly).
- The tutor's sandbox, until its shared files and agent are updated. Without the S42 file `default_engine()` falls
  back to the earlier model and says so on stderr.

To use the earlier model in a script that takes `--model`, pass `~/Downloads/mortal_model_policy/model.py`.
