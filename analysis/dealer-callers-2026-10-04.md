# The dealer's one call, the run from the wall, and the suit a river avoids (4 October 2026)

Guide chapter 28 (`#dealer-call`). The question: in the 3 October 23:38 game (261004-663f0de9, fourth on −3,200 after
three deal-ins) the user pushed against the East 4 dealer's one call, expecting to fold by the dealer's 10th discard,
and missed that the dealer's last three tiles came from the wall.

Data: `analysis/dealer-callers-2026-10-04.json` from

    .venv/bin/python scripts/contrast/vs_callers.py MAN/lj_all.json lj vc_lj
    .venv/bin/python scripts/contrast/vs_callers.py MAN/self.json self vc_you
    .venv/bin/python scripts/contrast/choices.py MAN/lj_all.json choices_lj.jsonl --callers
    .venv/bin/python scripts/contrast/choices.py MAN/self.json choices_you.jsonl --callers
    .venv/bin/python scripts/mine_dealer_callers.py vc_lj.cuts.jsonl choices_lj.jsonl vc_you.cuts.jsonl choices_you.jsonl analysis/dealer-callers-2026-10-04.json

`lj_all.json` is the 1,079 Tokujou games of `data/local_sources/luckyj_tenhou/index.json`; `self.json` the user's 165
games since 1 January. `vs_callers.py` now also writes `q_river` (the caller's discards per suit and honors) and
`q_meld_suits`. The regenerated rows reproduce chapter 19's fold lines exactly (12/9, ties 10/7, 4,500 and 1,591 turns).

## Findings

Real choices only (a safe tile keeps the best shanten and so does a live tile with at least as much acceptance),
single caller with one call, nobody in riichi; curves fitted per discard over the discards with 25+ turns.

| LuckyJ's live cuts | against the dealer | against anyone else |
|---|---|---|
| far hand (2-shanten+), 50% at | 10th (crossing 10.05) | 13th (50.2% there; 65% at the 10th) |
| far hand, ties | 9th (8.44) | 56% at the 11th |
| one-shanten, below half from | 12th (11.91) | 64% at the 14th |
| one-shanten, ties | 10th (9.22); 62% at the 5th, 53% at the 8th | 54% at the 13th |

- Early discards: LuckyJ pushes against the dealer as hard as against others (one-shanten even harder at the 4th-5th);
  the dealer curve falls below from about the 6th. From the 9th discard on the dealer effect is about −0.55 log-odds.
- A ron into a dealer's one call paid 5,949 on average (144 rons) against 3,759 (409).
- The run (tiles in a row from the wall since the last call) does not move LuckyJ's live cuts: +0.01 ± 0.06 far,
  +0.09 ± 0.05 one-shanten per tile, dealer × run −0.08 ± 0.09 and −0.05 ± 0.09, and the same from the 9th discard.
  Chapter 18's squares do move with it: one call at the 8th discard 21% (last tile from hand) vs 24% (three from the
  wall), 30% vs 41% at the 10th, 34% vs 55% at the 12th.
- The user's live share against LuckyJ's curves at the same discards: far 74 vs 77 (dealer), 77 vs 82 (others);
  one-shanten 67 vs 66, 72 vs 71.
- Rivers that avoid a suit (none of it in 6+ discards, calls in it or honors), every seat's live cuts from the 6th
  discard, fitted hit rate at the caller's 8th discard: other suits 1.0 per 100, honors 0.7, the avoided suit 1.4,
  a live number tile against a river showing every suit 2.2. Avoided vs other suits: ×2.1 (0.76 ± 0.19 log-odds);
  avoided suit vs every suit shown: ×0.7. LuckyJ does not act on it: with two equally good live number tiles, one in
  the avoided suit, it threw the other suit's tile 45% (216 turns through the 8th discard) and 55% (64 after).
- Tenpai against a single caller: when only safe tiles keep the tenpai LuckyJ throws one 98.8% (1,089); when every
  safe tile breaks it, it breaks 3.5% (1,521).

## The three deal-ins (Mortal from the site's replays)

- East 4-1, turn 7, [[3p]] into the dealer's 12,300 (pinzu half flush, haku, double East, ready from their 5th
  discard on a 1p-2p penchan). One-shanten tie with the genbutsu [[1m]] on the user's turns 4-7 (dealer discards
  5-8); LuckyJ's fitted live share 62% → 53%; Mortal threw the live tile each time (96-99%). Verdict: close.
- East 3-0, turn 13: tenpai on a 7m kanchan (tanyao, dora 8p, 2,900 as dealer); the user threw genbutsu [[3s]] where
  [[8p]] was suji and kept the tenpai (Mortal 8p 100%, 3s 0%). Three turns later [[6m]] back into tenpai dealt into
  kamicha's manzu half flush, 5,200 (Mortal 6m 100% by then).
- South 1-0, turn 13: riichi with [[7s]] from 2,000 in last (pinfu dora 1, 5s-8s) over the genbutsu [[6s]] shanpon;
  Mortal 100%. Shimocha's toitoi (7s/F) took it, 5,200, and the user went below zero.
