# When LuckyJ folds to open callers (27 September 2026)

The question: against an open hand, when does LuckyJ stop cutting live tiles, what makes it stop
sooner, and what does it do when its own tenpai needs a live tile? This extends section 3 of
`analysis/table-contrast-2026-09-25.md` (the caller's tells) with the same games: LuckyJ's 1,079
Tokujou hanchan (its seats against the 3,237 human seats at the same tables) and 2,714 Houou hanchan
from 2023, replayed with all four hands visible. A local Mortal policy model, run on every seat of
LuckyJ's games, is the independent check. Figures: `analysis/open-callers-2026-09-27.json`, written by
`scripts/contrast/report/export_open_callers.py` from the output of `scripts/contrast/vs_callers.py`.

Groups are listed Tokujou humans / Houou humans / LuckyJ. "Humans" pools Tokujou and Houou.

## Data and definitions

`vs_callers.py` writes one row for every discard made while at least one opponent has an open meld and
nobody is in riichi, once per caller: 577,879 discards (122,582 by the Tokujou humans, 416,744 by Houou
players, 38,553 by LuckyJ) and 747,381 rows (156,902, 541,197 and 49,282). The fold-line, dora-pon and
passed-tile rates use only discards made against a single caller.

- **The caller's discards so far** count every discard the caller has made, the one right after each
  call included, whether or not another player later called the tile away. A call adds no discard of
  its own. This is the clock the section uses; bands are 1 to 6, 7 to 9, 10 to 12 and 13 or more.
- **Safe** means the caller's genbutsu (any tile in their river, called-away tiles included), a dead
  honor, a full suji or nakasuji, or an honor with two copies visible. **Live** is everything else:
  live honors and terminals, virtual nakasuji, half suji and unsupported 2 to 8. These are the
  `build_personal_guide.safety` labels against that caller.
- **Free hold**: a discard against a single caller where a safe tile keeps the hand's best shanten.
  Cutting a live tile there was a choice, not a necessity. The rates below are the share of live cuts.
- **Tenpai** and **on the wait** come from the caller's real hand.
- **Passed tile**: a tile another player discarded after the caller's last discard, which the caller
  did not ron. Until the caller's next discard it cannot deal into them (temporary furiten).
- **Dora pon**: the caller's melds show three or more dora, counting red fives and the first
  indicator only.
- **Half-wait dilemma**: a tenpai decision against callers where every discard that keeps the widest
  wait is a live tile and a safe discard keeps a narrower tenpai. Rows are the discarder's own rows of
  six (turns 1 to 6, 7 to 12, 13 on).

## 1. The caller's clock

How often the caller was tenpai, by calls and their discards so far (all groups pooled):

| calls | 1 to 6 | 7 to 9 | 10 to 12 | 13+ |
|---|---|---|---|---|
| one | 6.7% | 23.5% | 39.5% | 53.6% |
| two | 23.8% | 45.9% | 62.1% | 71.8% |
| three | 63.7% | 79.9% | 88.2% | 89.8% |

Each tsumogiri in a row since the call adds a little: for a single caller in their first nine discards,
11.0% with none, 15.9% after one, 20.5% after two and 25.3% after three or more.

## 2. The fold line (free hold)

Live cuts from two-shanten or worse, single caller, LuckyJ against the humans (n in brackets):

| calls | 1 to 6 | 7 to 9 | 10 to 12 | 13+ |
|---|---|---|---|---|
| one, LuckyJ | 76.7% (4,871) | 57.7% (2,018) | 38.4% (711) | 17.6% (222) |
| one, humans | 66.5% (63,924) | 57.8% (25,590) | 41.8% (8,048) | 26.0% (2,564) |
| two, LuckyJ | 67.7% (992) | 44.4% (914) | 31.1% (408) | 22.4% (170) |
| two, humans | 63.5% (11,780) | 48.8% (11,001) | 34.4% (5,109) | 21.6% (2,580) |
| three, LuckyJ | 53.6% (69) | 30.4% (125) | 24.2% (91) | 4.9% (41) |
| three, humans | 47.0% (972) | 37.9% (1,812) | 34.3% (1,090) | 21.1% (870) |

LuckyJ's rate falls below half at the caller's tenth discard against one call and at the seventh
against two or three. The humans cross in nearly the same places (with three calls, one band earlier)
but move less: they spend more safe tiles before the line and more live tiles after it. Early against
one call, most of LuckyJ's extra live cuts are live honors and terminals (46.2% of its discards against
39.4%); number tiles differ by about three points.

From one-shanten LuckyJ runs close to the humans:

| calls | 1 to 6 | 7 to 9 | 10 to 12 | 13+ |
|---|---|---|---|---|
| one, LuckyJ | 59.4% | 49.1% | 39.9% | 25.8% |
| one, humans | 55.7% | 50.8% | 42.0% | 28.6% |
| two, LuckyJ | 52.9% | 41.2% | 36.5% | 22.0% |
| two, humans | 53.8% | 46.8% | 37.1% | 24.5% |

Mortal on the free-hold spots of LuckyJ's games (every seat), share of top choices that were live:

| hand | caller under 15% tenpai | caller over 75% tenpai |
|---|---|---|
| two-shanten or worse | Mortal 69.3%, LuckyJ 76.7%, Tokujou 67.1% | Mortal 23.2%, LuckyJ 23.9%, Tokujou 35.6% |
| one-shanten | Mortal 59.8%, LuckyJ 59.4%, Tokujou 56.4% | Mortal 24.9%, LuckyJ 27.7%, Tokujou 33.3% |

Breaking the hand for safety (every shanten-keeping tile live, a safe tile only at the cost of
shanten) is rare for everyone against callers and shows no clear LuckyJ difference: from two-shanten
or worse, 0.6% to 1.8% against callers under 15% likely to be tenpai and 27% to 32% against callers
over 75%.

What barely moved LuckyJ, or moved it no more than the humans: its own dora, either player being
dealer, a yakuhai pon, and a tsumogiri streak on its own (live cuts 67.6% with no tsumogiri since the
call, 58.9% after three, against 61 to 62% and 54 to 55% for the humans).

## 3. The dora pon

Free hold, single caller in their first nine discards, one-shanten or further. Live cuts against a
caller showing three or more dora and against the rest:

| | Tokujou | Houou | LuckyJ | Mortal |
|---|---|---|---|---|
| three dora showing | 55.7% (709) | 49.3% (2,964) | 44.1% (245) | 48.8% |
| the rest | 59.2% (39,138) | 58.5% (127,306) | 62.2% (13,131) | 59.7% |
| two-shanten or worse, three dora | 56.4% | 53.4% | 45.5% | |
| two-shanten or worse, the rest | 62.7% | 61.9% | 67.7% | |

98.4% of the callers who came to show three dora did it with a pon or kan of the dora. At that stage
they were tenpai 27.2% of the time against 20.1% for the rest. They won 10,377 points on average
against 4,716 for other callers, and a deal-in into them cost 9,653 against 3,988. The effect is
concentrated in the caller's first nine discards; later, LuckyJ's rates against dora pons and other
callers converge.

## 4. The passed tile

Single caller more than 30% likely to be tenpai by the clock, one-shanten or further, and a
live-looking tile that another player discarded since the caller's last discard keeps the best
shanten. Share of discards that were that tile: Tokujou 34.3% (1,270 spots), Houou 37.9% (3,896),
LuckyJ 59.2% (397). Mortal, on the same spots of LuckyJ's games (1,667), 50.3%. Of 24,095 passed
tiles cut against a caller in all three groups, none dealt in, as the furiten rule requires.

## 5. Tenpai: the narrower safe wait

Half-wait dilemmas: 622 Tokujou, 1,907 Houou, 160 LuckyJ, about 3% of the tenpai decisions made
against callers. Share taking the safe, narrower tenpai:

| row | Tokujou | Houou | LuckyJ | Mortal (LuckyJ's games) |
|---|---|---|---|---|
| first (1 to 6) | 9.5% (21) | 26.5% (68) | 16.7% (6) | 14.8% (27) |
| second (7 to 12) | 27.8% (334) | 26.6% (927) | 41.9% (86) | 32.1% (420) |
| third (13+) | 37.5% (267) | 39.7% (912) | 50.0% (68) | 42.1% (335) |

Second and third rows together:

| | Tokujou | Houou | LuckyJ |
|---|---|---|---|
| safe discard keeps a third of the wait or less | 19.1% | 18.5% | 24.2% |
| keeps about half | 30.3% | 32.2% | 48.3% |
| keeps two thirds or more | 50.8% | 50.8% | 59.4% |
| wide wait worth three han or more | 22.5% | 19.9% | 33.8% (71) |
| one or two han | 30.3% | 30.7% | 49.1% (55) |
| no yaku for a ron on the wide wait | 55.9% | 63.2% | 67.9% (28) |
| closed hand (dama) | 28.7% | 28.1% | 33.3% (21) |

In the second and third rows LuckyJ went safe 47.4% of the time from an open hand, and in the third row
54.8% of the time against a caller with two or more tells. In the third row with about half the wait kept, it went safe 63.9% of the time (36
spots); Mortal 46%. In a closed dama hand with a yaku, Mortal preferred the safe tenpai only 21.4% of
the time in the second and third rows (126 spots). Mortal and LuckyJ agreed on 81.2% of LuckyJ's
dilemmas.

How often the live tile was really on a caller's wait: 3.2%, 5.0% and 10.5% by row; 13.6% in the third
row against a caller with two tells.

The humans' own outcomes favour the wide wait in every row (net per hand, wide against safe: +2,709
and +500, +1,959 and +911, +1,216 and +684; third-row win rate 29.0% against 14.9%, deal-in rate 12.5%
against 6.9%). That comparison is confounded: in the third row the players who went safe faced a caller
with two tells 55.0% of the time, those who kept the wide wait 47.5%.

## Caveats

- LuckyJ's half-wait sample is small (160 spots, 6 in the first row, 21 closed), so the row pattern
  leans on Mortal's 782 spots from the same games for support.
- The clock uses the caller's tenpai rate pooled over all groups. LuckyJ's own callers are humans,
  and the Tokujou humans' callers include LuckyJ.
- Safety labels come from the caller's river and suji only; kabe, the passed tile and reads of the
  caller's yaku are not in the label, so "live" is a floor on what a strong player would call safe.
