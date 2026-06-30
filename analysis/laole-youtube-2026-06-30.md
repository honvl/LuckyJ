# Laole YouTube LuckyJ Notes

Source: Laole / Oiraku, `老楽の麻雀AI考察`, YouTube channel `UCuwfKcSr1lY20EbUszJnHAQ`.

Method: I pulled metadata and Japanese auto-captions for the 14 LuckyJ-focused videos listed on the channel on 2026-06-30. The raw auto-captions are noisy and stay under ignored `tmp/laole-captions/`; this file keeps only derived review notes and source links.

## Videos Reviewed

| Date | Video | Main lead |
| --- | --- | --- |
| 2026-03-08 | [QJOF4PA2Jvg](https://www.youtube.com/watch?v=QJOF4PA2Jvg) | Channel launch LuckyJ hand review |
| 2026-03-15 | [HZ6vd4Q6E64](https://www.youtube.com/watch?v=HZ6vd4Q6E64) | Two riichi sticks, last-place context |
| 2026-03-22 | [iBnA-cbOnZQ](https://www.youtube.com/watch?v=iBnA-cbOnZQ) | Hard-to-copy shocking discard |
| 2026-03-29 | [E45S7sg_uKk](https://www.youtube.com/watch?v=E45S7sg_uKk) | Realist midgame and late-game hand building |
| 2026-04-19 | [_XLi_R-vj84](https://www.youtube.com/watch?v=_XLi_R-vj84) | Breaking common assumptions |
| 2026-04-26 | [_1x6QpiHc_4](https://www.youtube.com/watch?v=_1x6QpiHc_4) | Kansuuken and danger judgment |
| 2026-05-03 | [brwgZ6ovDNs](https://www.youtube.com/watch?v=brwgZ6ovDNs) | Multiple unusual LuckyJ decisions |
| 2026-05-10 | [uSsXAS90Q0g](https://www.youtube.com/watch?v=uSsXAS90Q0g) | One-chance skepticism |
| 2026-05-17 | [KlV2p_ucAgE](https://www.youtube.com/watch?v=KlV2p_ucAgE) | Three AI models disagree |
| 2026-05-31 | [EmR2o8T-_c4](https://www.youtube.com/watch?v=EmR2o8T-_c4) | Combo-count danger theory |
| 2026-06-07 | [tmrnbcOIEGA](https://www.youtube.com/watch?v=tmrnbcOIEGA) | Learning winning routes from LuckyJ |
| 2026-06-14 | [fQIU5EOsPfE](https://www.youtube.com/watch?v=fQIU5EOsPfE) | Sanshoku versus practical value routes |
| 2026-06-21 | [D8-IyhTRsS4](https://www.youtube.com/watch?v=D8-IyhTRsS4) | Dora-3 hand that rejects automatic ryanmen |
| 2026-06-28 | [paOEZ0Y4y-c](https://www.youtube.com/watch?v=paOEZ0Y4y-c) | Lowering deal-in rate |

## Additions To Carry Into The Book

1. Danger is partly combinatorial, not only label-based.
   The combo-theory video explicitly frames danger by counting the unseen tile combinations that can make a wait, then adjusting for bad-shape rates. This sharpens the current "read the river shape" point: a tile being suji, one-chance, or kansuuken-adjacent is not enough. Count how many plausible waits remain.

2. One-chance can increase bad-shape danger.
   The one-chance review is a useful warning against treating visible blockers as a binary safety signal. When several blocks in other suits are constrained, a one-chance tile can still be a common bad-shape hit. The book should keep one-chance under target-specific danger, not under generic safety.

3. High-value hands do not always want the best-looking wait.
   The dora-3 review highlights LuckyJ taking a yakuhai shanpon / triplet-value route rather than reflexively upgrading to ryanmen. The copyable idea is not "prefer shanpon"; it is that value, expected ron rate, and opponent reading can dominate raw wait shape.

4. Pair and triplet branches are real route material.
   Several reviews emphasize LuckyJ treating yakuhai, dora pairs, red-five blocks, and toitoi-like continuations as active routes rather than decorative upside. This supports the existing route-preservation points, but the source is more explicit about pair/triplet route value.

5. Open-hand isolated tiles are under active revision.
   The two-riichi-stick and last-place reviews call out post-call isolated-tile retention as an area where human heuristics may be changing. The book should avoid overconfident rules here: after opening, an isolated tile can be route material, a safety reserve, or a future liability depending on placement and how the next discard chain looks.

6. Realism gets stricter from middle row onward.
   Laole repeatedly characterizes LuckyJ as "realist" in the middle and late rows: enough-value hands stop chasing decorative upgrades, and hands that no longer reach tenpai should stop pretending. This reinforces the current late-precision point and should be stated in less abstract terms.

## Practical Changes Made

- Added a Laole/Oiraku source line to the README.
- Added a "Laole YouTube Addendum" block to the site synthesis sections.
- Added concrete English and Japanese source-example cards for:
  combo-count danger, one-chance skepticism, non-automatic ryanmen, and isolated tiles after opening.

No raw transcript text is committed. The auto-captions are useful for mining themes, but not reliable enough to quote as exact language.
