# LuckyJ against the humans at its tables (25 September 2026)

The question: what does LuckyJ do that strong humans do not, and which of those differences are worth
points? LuckyJ's 1,079 Tokujou hanchan (19 April to 30 May 2023, 11,272 hands) were replayed with all
four hands visible. The baselines are the 3,237 human seats at the same tables (mostly 5 to 7 dan,
median rating 1,926) and 2,714 Houou hanchan from 2023 (10,856 human seats, 28,826 hands) from the
local Tenhou archive. NAGA's three heads (read from the reports for every seat) and a local Mortal
policy model (run on every seat) serve as independent checks. Scripts: `scripts/contrast/`.

Groups below are always in the order Tokujou humans / Houou humans / LuckyJ.

## 1. The ledger

| per hand | Tokujou | Houou | LuckyJ |
|---|---|---|---|
| net points | -122 | -1 | +363 |
| won | 21.0% | 21.0% | 22.9% |
| dealt in | 13.9% | 12.2% | 10.3% |
| dealt in while tenpai | 6.5% | 6.2% | 6.0% |
| dealt in at 1-shanten | 4.5% | 3.8% | 2.7% |
| dealt in at 2-shanten or worse | 2.9% | 2.2% | 1.6% |
| riichi | 18.6% | 18.2% | 19.3% |
| opened | 32.3% | 33.7% | 36.5% |

"State" is the shanten after the tile that dealt in. Points lost per hand to deal-ins:

| state, winner | Tokujou | Houou | LuckyJ |
|---|---|---|---|
| tenpai, into riichi | 193 | 179 | 179 |
| tenpai, into an open hand | 155 | 132 | 121 |
| tenpai, into dama | 44 | 39 | 45 |
| 1-shanten, into riichi | 89 | 64 | 40 |
| 1-shanten, into an open hand | 111 | 81 | 59 |
| 1-shanten, into dama | 35 | 38 | 29 |
| 2+-shanten, into riichi | 67 | 45 | 26 |
| 2+-shanten, into an open hand | 62 | 44 | 31 |
| 2+-shanten, into dama | 25 | 18 | 16 |
| **total, tenpai** | **392** | **350** | **345** |
| **total, not tenpai** | **388** | **291** | **201** |

The Houou players close about half of the not-tenpai gap (7.4 -> 6.0 -> 4.3 deal-ins per 100 hands)
and none of the win-rate gap.

### Win rate and the opponent pool

LuckyJ always sits with three Tokujou humans; each human sits with two humans and LuckyJ. Rons per
ordered pair of players, per 100 hands (`pairs.py`):

| winner <- dealer-in | rons per 100 hands | average ron |
|---|---|---|
| LuckyJ <- human | 4.77 | 6,592 |
| human <- human | 4.67 | 6,147 |
| human <- LuckyJ | 3.49 | 6,037 |

Tsumo wins per 100 hands: LuckyJ 8.61, humans 8.20. About 1.2 of LuckyJ's 1.9 point win-rate edge
over its tablemates is the opponent pool (LuckyJ feeds them less); the rest is a slightly higher
tsumo rate. LuckyJ's offensive edge is mainly value: its rons are 7% larger.

The same confound explains LuckyJ's higher riichi win rate (51.8% against 47.7% Tokujou and 48.0%
Houou). A human dealt into LuckyJ's riichi 9.43% of the time (n 5,481 responder-riichis) and into
another human's 9.36% (n 10,052). LuckyJ's riichis face three human defenders.

## 2. The pattern: switches, not hedges

| decision | condition | Tokujou | Houou | LuckyJ |
|---|---|---|---|---|
| live cut against a caller, 2+-shanten, no dora, safe tile held | no tells | 70.7% | 70.4% | 74.5% |
| | two or more tells | 42.8% | 37.3% | 33.1% |
| unsafe cut against a riichi | tenpai | 41.0% | 39.4% | 42.4% |
| | three-shanten or worse | 13.0% | 9.4% | 6.4% |
| tanyao call from two-shanten | no dora | 24.3% | 27.6% | 22.9% |
| | two or more dora | 48.7% | 50.1% | 59.2% |

LuckyJ's rates move further on the deciding variable at both ends. The Houou players move toward
LuckyJ at one end of each scale and not at the other.

## 3. Prescriptions and their evidence

### 3.1 Answer the caller's tells, not the call

Tells (as in `mine_caller_tells.py`): the latest call on the caller's 9th turn or later; a second
call; the last two discards since the call both tsumogiri.

Caller tenpai rate by tells (0/1/2/3): LuckyJ's tables 13.5 / 39.2 / 66.1 / 85.4%; Houou tables
14.3 / 41.8 / 70.2 / 87.1%.

Live-cut rate while holding a safe tile (no dora in hand), by tells 0 / 1 / 2+ / 3:

| | Tokujou | Houou | LuckyJ |
|---|---|---|---|
| 2+-shanten | 70.7 / 58.7 / 42.8 / 38.9 | 70.4 / 56.1 / 37.3 / 30.7 | 74.5 / 53.5 / 33.1 / 23.7 |
| 1-shanten | 68.5 / 61.5 / 48.3 / 42.5 | 69.4 / 59.0 / 45.5 / 36.7 | 67.6 / 52.5 / 39.3 / 31.6 |
| tenpai | 65.4 / 58.6 / 53.0 / 51.2 | 65.7 / 59.0 / 50.9 / 45.4 | 60.2 / 55.7 / 48.4 / 44.6 |

Standard errors: LuckyJ cells 1 to 4 points, human cells under 1. With dora in hand the gap at two
or more tells is smaller (2+-shanten: 41.5 / 39.1 / 36.1).

Deal-ins per 100 discards against callers with no riichi out, LuckyJ vs Tokujou (Houou):
vs 2 melds at 1-shanten 0.79 vs 1.67 (1.42); vs 3+ melds at 1-shanten 0.74 vs 2.42 (1.07).
Hits per 100 live cuts, no dora: 1.03 LuckyJ, 1.52 Tokujou, 1.50 Houou.

### 3.2 Fold a far hand on the first discard after a riichi

From `mine_riichi_folds.py` (safe = genbutsu incl. riichi furiten, suji, nakasuji, honor with two
seen). Unsafe-cut rate and deal-ins per 100 discards facing a riichi, by the best shanten reachable:

| shanten | Tokujou | Houou | LuckyJ |
|---|---|---|---|
| tenpai | 41.0% ±0.5, 5.73 | 39.4% ±0.3, 5.25 | 42.4% ±0.8, 5.48 |
| 1 | 24.8% ±0.3, 2.48 | 21.2% ±0.1, 1.90 | 20.5% ±0.5, 1.32 |
| 2 | 16.2% ±0.3, 1.30 | 13.0% ±0.1, 0.86 | 10.3% ±0.4, 0.72 |
| 3+ | 13.0% ±0.4, 1.11 ±0.12 | 9.4% ±0.2, 0.47 ±0.04 | 6.4% ±0.4, 0.21 ±0.08 |

From 2+-shanten on the seat's turn 8 or earlier: 25.4 / 21.5 / 16.1%. With a safe tile that kept the
same shanten: 8.4 / 5.5 / 3.7%. Closed hands when a riichi came, LuckyJ's tables: 2-shanten won
4.7% (humans) and 3.5% (LuckyJ); 3+-shanten 1.9% and 1.8%.

Safe tiles held at the moment of a riichi were the same for LuckyJ and the humans (1-shanten: 1.90
vs 1.89 genbutsu), but at equal genbutsu counts the humans dealt in more (1-shanten with 2
genbutsu: 9.2% vs 6.9%). The gap is in play after the declaration, not in preparation before it.

### 3.3 Riichi the cheap tenpai

First closed tenpai, nobody in riichi, not furiten, non-dealer (`tenpai.py`). Declare rate by the
hand's best value without riichi (han incl. dora):

| han | Tokujou | Houou | LuckyJ |
|---|---|---|---|
| 0 (no yaku) | 71.5 (n 1,796) | 74.1 (5,976) | 82.3 (548) |
| 1 | 60.3 (622) | 63.5 (2,076) | 81.6 (174) |
| 2 | 66.5 (1,085) | 70.9 (3,462) | 81.4 (307) |
| 3 | 58.0 (697) | 63.5 (2,401) | 68.2 (242) |
| 4 | 47.0 (417) | 42.5 (1,323) | 55.1 (156) |
| 5+ | 33.0 (267) | 32.1 (801) | 41.2 (97) |

1-2 han with a yaku on every wait, by live tiles: 3 or fewer 34.0 / 41.5 / 52.9; 4 to 6 62.3 / 64.5
/ 82.6; 7 or more 78.9 / 82.9 / 95.8. From turn 13: 44.9 / 54.2 / 76.4. Dealer, 1 han: 69.2 / 78.9
/ 87.2.

Humans' own results for those hands (Tokujou and Houou pooled), riichi minus dama, net per hand:
3 or fewer live +1,094 ±265 (riichi n 583, dama n 888); 4 to 6 +895 ±178 (1,722 and 969); 7 or more
+1,730 ±196 (1,844 and 405). Win rates: Tokujou riichi 55.4% vs dama 47.2%, Houou 53.2% vs 50.6%.

LuckyJ's dama: 3 han on 3 or fewer live tiles declared 26.9% (n 52), 4 han 20.8% (53), 5+ 12.5% (32);
4 han on 4 to 6 live 47.6% (42).

### 3.4 Let dora decide a two-shanten call

`mine_call_chances.py`, 2-shanten to 1-shanten with a yaku route, tanyao, no riichi out:
call rate by dora held 0 / 1 / 2+: Tokujou 24.3 / 27.6 / 48.7; Houou 27.6 / 31.3 / 50.1; LuckyJ 22.9
/ 28.0 / 59.2. Any route with 3+ dora: Tokujou 54.5% (n 222), LuckyJ 86.4% (59).

Humans' own results, first chance, call minus pass (net per hand): no dora -91 ±136 (called n 994, passed n 2,521);
one dora -185 ±141 (1,185 and 2,587); two or more +1,047 ±219 (1,103 and 1,030).

Value-pair pon from 2-shanten: 83.3 / 87.3 / 93.4%. Hands dealt 2+ dora: reached tenpai 52.7 / 53.3 /
55.8%; tenpai given up and not won back 4.0 / 4.6 / 1.7%.

From one-shanten, a call to a tenpai with a yaku: 52.9 / 58.6 / 57.6% taken; the humans' results for
calling were better than passing at every acceptance level (+532 to +618 a hand, selection-prone),
so LuckyJ's lower rate from very wide closed hands (18.8% vs 26.6 / 29.8% with 20+ tiles of
acceptance) is not supported as a lesson.

### 3.5 Start the flush on the first discard

Half and full flush wins per 100 hands (winner's final hand in one suit plus honors, `flushwins.py`):
1.17 / 1.08 / 2.09.

`mine_shape_plans.py`, "fit" = tiles of the best suit plus honors in the deal. Share that cut two or
more off-suit tiles in the first three discards:

| deal | Tokujou | Houou | LuckyJ |
|---|---|---|---|
| 9 fitting, value pair | 39.1 | 37.9 | 52.2 |
| 10+ fitting, value pair | 55.8 | 52.0 | 63.3 |
| 9 fitting, no pair | 25.9 | 24.2 | 38.5 |
| 10+ fitting, no pair | 43.7 | 39.0 | 57.3 |

In one suit by the sixth discard with exactly 10 fitting: 18.9 / 17.5 / 28.4%. Humans' own results,
fast start minus slow start (win value minus deal-in cost per hand): 9 + pair +372 ±98; 10+ + pair
+413 ±138; 9, no pair +41 ±77; 10+, no pair +225 ±127.

## 4. What does not carry over

- First-row honor order. Turns 1 to 6, quiet table, an isolated honor and an isolated number tile
  that both keep the best shanten: the share cutting the honor is 61.0 / 62.1 / 48.1% (guest wind vs
  lone terminal 58.2 / 60.5 / 46.7; value honor vs lone 2 or 8 68.9 / 71.8 / 45.2). NAGA's top
  choice is the honor 55.4 to 55.8%, Mortal's 51.0 to 51.7%. In the humans' own hands the choice made
  no measurable difference: honor-first minus number-first, stratified by shanten and dora,
  -14 ±36 points per hand.
- Tenpai pushes against a riichi: 41.0 / 39.4 / 42.4% unsafe cuts; when every tenpai-keeping tile is
  unsafe, pushed 78.6 / 76.7 / 82.0%. LuckyJ is slightly more aggressive with a tenpai, not less.
- 1-shanten pushes by dora: Houou and LuckyJ match (turn 8 or earlier, 0 dora 32.9 vs 33.5%).

## 5. Engine checks

NAGA's three heads are read from the reports (`naga_align.py`, 539,235 discard decisions over all
four seats). A local Mortal policy model (`mortal_run.py`, `~/Downloads/mortal_model_policy`) was run
on every seat of all 1,079 games; its outputs are action probabilities, not values, so it serves as a
second strong policy, trained apart from LuckyJ. Mortal figures are in the humans' own spots unless
marked.

| spot | humans did | LuckyJ did | NAGA | Mortal |
|---|---|---|---|---|
| first row, isolated honor vs isolated number tile, share choosing the honor | 61.0% | 48.1% | 55.8% top choice | 51.7% top choice |
| cheap first tenpai (1-2 han, yaku on every wait, quiet, dealer or not), share declared | 63.3% (n 2,051) | 81.0% (625) | | 77.8% prefer riichi |
| the same, where the humans stayed dama | | | | 51.4% prefer riichi (n 753) |
| two-shanten call, any non-yakuhai route, two or more dora | 41.9% (n 927) | 57.4% (296) | | 55.4% mean call probability |
| two-shanten call, any non-yakuhai route, no dora | 25.0% (1,964) | 30.3% (666) | | 33.3% |
| value-pair pon from two-shanten | 83.6% (1,419) | 94.0% (434) | | 93.6% |
| value-pair pon from three-shanten | 75.9% (1,997) | 89.8% (630) | | 93.2% |

Mortal agrees with LuckyJ against the humans on riichi, on dora calls and on value-pair pons, and
sits with LuckyJ on the first-row honor order. It calls more than the humans at every dora count,
so it supports "call more with two dora" and does not by itself support "pass without dora"; the
humans' own results do (section 3.4).

## Files

- `scripts/contrast/`: extractors and `report/` analysis scripts; see its README for the order.
- Intermediate outputs (not committed, regenerate with the scripts): per-hand records, the discard,
  call and tenpai tables, riichi-level rows, NAGA and Mortal predictions, and the miner rows for the
  LuckyJ, tablemate and Houou manifests.
