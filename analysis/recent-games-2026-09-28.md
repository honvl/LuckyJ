# Honver's games of 27 and 28 September: three calls, a once-cut West, counting callers (28 September 2026)

The user: "I feel like I'm losing it", about a three-call hand that "couldn't get tenpai or defend", a once-cut
West that dealt in when keeping the 7 of a 6-7-7 was more efficient, and trouble following a single caller past
turn 9 and their two tsumogiri. Later: "that dama was detectable because the dealer started auto-discarding
weirdly". The answer is chapter 14 of the personal guide (`site/honver.html#three-calls`).

## Data

7 new games (27 September 16:01 to 28 September 01:38, 68 hands, placements 2, 1, 4, 3, 4, 3, 1), 115 since
January. Compared with the 14 games of 24 to 27 September (152 hands), the 94 before (995) and LuckyJ (1,079 Tokujou
games, 11,272 hands). Scripts: `scripts/contrast/hands_all.py`, `scripts/mine_caller_tells.py`,
`scripts/contrast/vs_callers.py`, and for this chapter `scripts/contrast/report/third_calls.py`,
`three_call_push.py` and `dama_tell.py`.

| | 94 before | 14 games | 7 new games | LuckyJ |
|---|---|---|---|---|
| won | 21.8% | 25.7% | 17.6% | 22.9% |
| dealt in | 11.7% | 8.6% | 8.8% | 10.3% |
| into open hands, per 100 hands | 6.9 | 5.3 | 1.5 | 4.8 |
| into a riichi, per 100 hands | 3.8 | 2.0 | 5.9 | 3.8 |
| average deal-in | 4,687 | 3,685 | 7,183 | 5,308 |
| points per hand | +31 | +330 | -482 | +363 |

At 1-shanten against two or more tells, with a safe tile in hand: live cuts 40.0% (15) in the new games.

## The six deal-ins

| game, hand | into | points | verdict |
|---|---|---|---|
| 260928-7c1ee667 East 4-2 | dealer's dama | 18,600 | unlucky: tenpai since their 10th discard, then two tsumogiri (example) |
| 260928-5a0260b7 East 2-0 | riichi | 2,600 | 1-han open tenpai push at turn 6 |
| 260928-90620418 South 1-0 | open hand | 8,000 | lone chun cut on the 5th discard against an early pon |
| 260928-90620418 South 2-0 | riichi | 8,000 | slip: West kept on turn 9, cut on turn 10 with genbutsu 9s keeping the shanten (example) |
| 260928-90620418 South 4-0 | riichi | 3,900 | 4-han open tenpai push from fourth in the last hand |
| 260928-50d32e06 South 2-0 | riichi | 2,000 | closed tenpai with no yaku pushed with 12 tiles left |

The three-call hand is 260928-50d32e06 East 1-1: turn 9, tenpai on a dora tanki (7,700), [[7p]] suji kept it;
the player cut genbutsu [[3s]], then a live [[8s]] on turn 10 to stay 1-shanten. Kamicha waited on 6m-9m and
tsumoed a mangan.

## Figures

- Three calls, a riichi out, a tenpai available: LuckyJ kept it on 345 of 352 turns (198 of 198 when a safe tile
  kept it, 147 of 154 when only live tiles did); kept hands won 30%, dealt in 18%, +1,320. Honver 24 of 28, 9 of 10
  with a safe keep. First such turn per hand: LuckyJ 126 of 126.
- Third call that reaches tenpai: LuckyJ 94.3% with nobody in riichi (230). With a riichi out, by the tenpai's han:
  none 23.5% (17), 1 han 61.5% (13), 2 han 58.3% (12), 3+ han 93.0% (43).
- Three-call hands: LuckyJ won 39%, dealt in 13%, +1,814 a hand (350); Honver 33%, 14%, +322 (36). After a
  riichi: LuckyJ 30%, 19%, +1,265 (144); Honver 14%, 21%, -1,379 (14).
- Single caller tenpai by pond row, without and with two tsumogiri in a row: first row 6.5% / 9.5%, second row
  first half 22.4% / 27.7%, second half 35.6% / 47.3%, third row 43.9% / 68.7% (522,295 caller readings with one
  call). Late call adds little once the row is known: 23.2 vs 30.2, 38.3 vs 41.5, 52.0 vs 54.6.
- Silent closed opponent (no call, no riichi), dama tenpai by their discards and tsumogiri run 0/1/2/3+: 7 to 9:
  3.2 / 3.4 / 3.0 / 2.4%; 10 to 12: 7.4 / 8.9 / 9.8 / 8.8%; 13+: 12.6 / 18.8 / 23.2 / 22.5%. Dealer at 10 to 12:
  6.7% with no run, 8.5% after two. LuckyJ's live-cut rate against such a player from far hands, turn 10+: 54.2 /
  54.4 / 50.7 / 54.1% by run, so it does not answer the run. Deal-ins per 100 live cuts into that player, turn 10+:
  0.43 / 0.32 / 0.50 / 0.54.
