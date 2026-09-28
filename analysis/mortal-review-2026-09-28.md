# Mortal's replay of the 27 and 28 September deal-ins (28 September 2026)

The user: "Track mortal to see where I fked up on those deal in hands", about the six deal-ins and the three-call
hand of chapter 14. The answer is chapter 15 of the personal guide (`site/honver.html#mortal-review`), plus three
marked corrections to chapter 14.

## Method

`scripts/tenhou6_to_mjai.py` converts the tensoul (tenhou.net/6) records of the Mahjong Soul games to mjai, with
draws, calls, kan draws and dora flips, riichi declarations and results; it reproduced 300 of 300 Houou games exactly
and every discard of the latest 7 games (`MjaiConversionTests`). Later on 28 September it became a wrapper around
`build_replays`' conversion (the site replays); its events for all 115 games, and the review below, stayed the same.
`scripts/mortal_hand_review.py GAME [HANDS]
[--json OUT]` feeds those events to the local Mortal policy (`scripts/contrast/mortal_run.py`) as Honver's seat and
records Mortal's three most likely actions at every discard and call chance, with the probability it gave the play.
`scripts/contrast/report/mortal_review.py` turns the per-game JSON into the figures below, alongside baselines from
the contrast extractors (`mortal_lj.jsonl`, `calls.py`, `tenpai.py`).

## Agreement

| | decisions | Mortal's first choice | under 10% |
|---|---|---|---|
| Honver, discards, 7 games | 762 | 73.0% | 99 |
| Honver, discards in the six deal-in hands | 60 | 63.3% | 13 |
| Honver, call chances | 201 | 93.0% | 9 |
| LuckyJ, discards, 1,079 Tokujou games | 127,059 | 72.6% | |
| Humans at LuckyJ's tables | 382,042 | 68.3% | |

Red and plain fives count as one tile.

## The six deal-ins

| game, hand | paid | Mortal | verdict |
|---|---|---|---|
| 260928-7c1ee667 East 4-2 | 18,600 | 7p 2%, 2m 97% | mistake: 2m kept 34 tiles (7p 33) and was not in the dealer's 4p-7p wait |
| 260928-90620418 South 2-0 | 8,000 | W 93% at turn 10 | mistake a turn earlier: W 97% at turn 9 (7p 2%); kamicha was 1-shanten then |
| 260928-50d32e06 South 2-0 | 2,000 + stick | riichi 8%, 7p 68%, 4s 21% | mistake: yakuless 6s kanchan riichi into the dealer's riichi while 13,400 ahead |
| 260928-5a0260b7 East 2-0 | 2,600 | 96 to 99% every turn | Mortal's play |
| 260928-90620418 South 1-0 | 8,000 | C 92% | Mortal's play |
| 260928-90620418 South 4-0 | 3,900 | 99 to 100% from the chi on | Mortal's play |

In 50d32e06 South 2 Mortal steered for tanyao: chi the dealer's 4s after the 8th discard (83%), and in the actual line
2m at turn 9 (98%) and 1m at turn 10 (59%). The second riichi was shimocha's; the forced 9s on turn 15 dealt in.

The three-call hand (50d32e06 East 1-1): the 9m pon at turn 6 (Mortal pass 99%) left an open 1-shanten with no pair;
Mortal kept the dora tanki at turn 9 (7p 100%), as chapter 14 said, and preferred 2s (55%) to 8s (30%) at turn 10.

## Baselines

- Pons of a number tile, nobody in riichi, that would not lower the shanten of a hand with a call already: LuckyJ
  pons 53 of 378 (14.0%); those hands won 26 and dealt in 2, +2,732 a hand. Honver 7 of 36 (19.4%): won 1, dealt in 2,
  -1,757. With a dora tile LuckyJ pons 9 of 15. In closed hands the rates match (9.1% and 8.7%). Of the three such
  pons in these games Mortal passed the 9m (99%) and the 4m of cc7d275a East 1-0 (100%) and made the 4p of 90620418
  East 4-1.
- First tenpai with no yaku, 4 or fewer live tiles, against one riichi: LuckyJ declared 58 of 141, and the declared
  hands won 13, dealt in 17, -584 a hand (the others -916). Without an 8,000 lead 49 of 121; leading by 8,000 or more
  in the South 3 of 9. So LuckyJ treats the spot as close; the case against the riichi rests on the lead, which
  Mortal weighs.

## Corrections to chapter 14

- It called the 50d32e06 South 2 deal-in "a closed tenpai with no yaku" pushed with 12 tiles left. It was a riichi
  declared into the dealer's riichi, and the tile that dealt in was forced.
- The dealer's haneman example (7c1ee667 East 4-2) was marked bad luck. 2m was the better cut (Mortal 97%).
- The once-cut West example gave genbutsu 9s as better on turn 10. Mortal pushed the West there (93%); the mistake
  was turn 9 only.

`analysis/recent-games-2026-09-28.md` carries the same corrections.

## Correction (28 September): the 9m pon

The user said they ponned the 9m to aim for a tanki on the dora. The chapter had said the pon left "fewer ways to
finish" and only tanki waits. `scripts/contrast/report/idle_pons.py` counts the tiles that give tenpai on each side:
10 without the pon and 28 with it, and 10 of the 28 lead to a 7,700 wait (a drawn 6p makes a dora pair with a 3s-6s
wait). Every tenpai without the pon was worth 3,900. Kamicha held one 6p, so the dora tanki had only two tiles left.

LuckyJ, at 1-shanten with one call and nobody in riichi, where a pon of a number tile keeps the shanten but adds 10 or
more tenpai tiles: pons 21 of 74; with two or more dora in hand 3 of 19; when the pon multiplies the tenpai tiles by
2.5 or more, 14 of 26. Pons won 38% and dealt in 10% (+557 a hand), passes 36% and 8% (+966). Honver's own such
chances: 4, ponned 2. The pon is a close call that Mortal (99% pass) and LuckyJ lean against, and the costly turn in
the hand was the broken tenpai on turn 9. Chapter 15's paragraph, rule, evidence and first example are corrected.
