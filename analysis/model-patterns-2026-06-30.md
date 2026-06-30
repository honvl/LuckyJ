# Model-mined LuckyJ/NAGA patterns - 2026-06-30

## Method

Command:

```bash
.venv/bin/python scripts/mine_model_patterns.py --no-mortal --output site/model-patterns.json
```

The script mines cached model outputs for LuckyJ draw-discard decisions where LuckyJ's real discard differs from NAGA's top discard. It excludes reach-declaration decisions and tags each mismatch by tactical family: safety retention, stale safety spending, outside/inside shape, pair handling, score position, active threats, dora/red-five retention, and newer honor/yakuhai subfamilies.

This refreshed artifact is NAGA-side only. The static site still has the separate per-point `site/mortal-analysis.json` panels generated earlier from local Mortal/libriichi assets, but `site/model-patterns.json` now disables Mortal sampling so the expanded pattern scan can stay fast and reproducible.

The cached reports also preserve the three NAGA heads: Nishiki, Hibakari, and Kagashi. The existing `NAGA top` fields are kept as the first head, Nishiki, for continuity. A new `model_split` section in `site/model-patterns.json` compares LuckyJ against each head separately.

Definitions:

- `bad_rate`: share of mismatches where NAGA assigned LuckyJ's actual discard below 5%.
- `bad_lift`: percentage-point change in `bad_rate` compared with other LuckyJ/NAGA mismatches. Negative is better.
- `danger_delta`: LuckyJ discard danger minus NAGA discard danger. Negative means LuckyJ's discard is safer by the local danger proxy.

## Overall result

- Eligible LuckyJ draw-discard decisions: 135,038.
- LuckyJ/NAGA discard mismatches: 36,206, or 26.8%.
- Among all mismatches, NAGA's severe-disagreement proxy was 31.0%.
- Among all mismatches, the large probability-gap rate was 56.1%.

## NAGA head split

Tiny legacy/single-head reports account for 50 decisions; the split below uses the 134,988 decisions with Nishiki, Hibakari, and Kagashi present.

| Head | LuckyJ top-discard match | Mismatch rate | Severe disagreement among mismatches | Big-gap rate among mismatches |
|---|---:|---:|---:|---:|
| Nishiki | 73.2% | 26.8% | 31.0% | 56.1% |
| Hibakari | 72.2% | 27.8% | 26.9% | 51.6% |
| Kagashi | 71.5% | 28.5% | 34.1% | 58.1% |

Hibakari does not simply match LuckyJ more often than Nishiki. Its useful signal is narrower: when Nishiki disagrees with LuckyJ, Hibakari agrees with LuckyJ in 8,445 positions, or 23.3% of Nishiki mismatches. In those positions, Nishiki's severe-disagreement rate drops to 8.7%, far below the 31.0% baseline for all Nishiki mismatches.

| Slice | N | Share of Nishiki mismatches | Nishiki severe-disagreement rate | Avg danger delta vs Nishiki | Safer than Nishiki | Riskier than Nishiki |
|---|---:|---:|---:|---:|---:|---:|
| Hibakari matches LuckyJ, Nishiki splits | 8,445 | 23.3% | 8.7% | +0.012 | 6.5% | 14.3% |
| Hibakari only matches LuckyJ, Nishiki/Kagashi split | 5,234 | 14.5% | 13.0% | +0.011 | 6.8% | 13.7% |
| Kagashi matches LuckyJ, Nishiki splits | 6,151 | 17.0% | 2.8% | +0.013 | 7.9% | 15.6% |

This is not an immediate-danger story. The Hibakari-match slice is slightly riskier than Nishiki by the local danger proxy and is mostly early/middle: 63.5% early, 30.5% middle, 5.9% late. The insight is inventory defense: LuckyJ often cuts a tile Nishiki dislikes now because the tile Nishiki wants to cut is being kept as a future exit, value seed, or route anchor.

Hibakari alignment is most enriched in these Nishiki-mismatch families:

| Pattern | N | Hibakari matches LuckyJ | Lift vs all Nishiki mismatches |
|---|---:|---:|---:|
| Keep dora/red-five material through the clean NAGA cut | 617 | 33.2% | +9.9 pp |
| Keep genbutsu/suji exits while cutting elsewhere | 8,587 | 30.4% | +7.1 pp |
| Keep own yakuhai pair or triplet anchor while NAGA breaks it | 135 | 26.7% | +3.3 pp |
| Clean a singleton yakuhai before an unproven open hand can use it | 285 | 24.9% | +1.6 pp |

Hibakari alignment is weaker in the strongest immediate-defense buckets: `safer_than_naga` is 14.7% Hibakari-aligned, `honor_cleanup_vs_shape` is 14.6%, and `multi_threat_safe_tenpai` is 14.5%. Those remain LuckyJ/Nishiki-specific signals rather than Hibakari-confirmed ones.

Practical use: when a LuckyJ/Nishiki split is also a LuckyJ/Hibakari match, do not treat it as a pure anti-NAGA move. It is often a defensible alternate NAGA-family line. For public examples, that should be framed as "Nishiki wants the clean tile, while Hibakari also accepts LuckyJ's inventory plan," not as "LuckyJ ignores NAGA."

## Pattern ranking

| Pattern | N | Bad rate | Bad lift | Danger delta | Read |
|---|---:|---:|---:|---:|---|
| Cut a loose non-self honor before shape cleanup in the first row | 278 | 19.4% | -11.7 pp | -0.024 | Good narrow version of early honor cleanup: the honor lacks a self-value job and LuckyJ removes it before prettifying shape. |
| Late keep of a named exit over NAGA's shape-cleaning discard | 931 | 20.2% | -11.1 pp | +0.014 | Late safe tiles work best when they answer a live target; generic comfort stays weak. |
| Clean a singleton yakuhai before an unproven open hand can use it | 285 | 24.6% | -6.5 pp | +0.013 | This is the measured version of the manually noticed yakuhai-cleaning idea. Sample is smaller but directionally useful. |
| Keep own yakuhai pair or triplet anchor while NAGA breaks it | 135 | 20.0% | -11.1 pp | +0.049 | Small but strong subcase: own yakuhai pairs can be real route anchors. |
| Spend a safe-looking tile after its target changes | 2,992 | 22.1% | -9.7 pp | -0.026 | Refines stale safety: the safe label matters less than whether it names the current target. |
| Cut a loose honor while NAGA prefers shape cleanup | 2,348 | 20.9% | -10.9 pp | -0.037 | Broad honor cleanup remains one of the strongest NAGA-side signals. |
| Choose a lower immediate-danger discard than NAGA | 3,741 | 21.8% | -10.2 pp | -0.149 | The cleanest defensive pricing signal. |
| Keep a pair or triplet anchor that NAGA wants to break | 2,338 | 21.9% | -9.8 pp | -0.019 | Supported when the anchor has a job: yaku, value, route fork, or defense. |
| Cut outside material while keeping middle-tile shape | 5,281 | 23.1% | -9.2 pp | -0.030 | Outside cuts can preserve the route under pressure. |
| Keep a defensive exit against an active riichi/open threat | 8,406 | 24.4% | -8.7 pp | +0.012 | Strong only because the exit is tied to a live opponent. |
| Middle/late choices preserving exits with multiple threats | 4,386 | 23.5% | -8.6 pp | -0.001 | Multi-threat defense is an inventory problem: which exit survives the next draw. |
| Spend a safe-looking tile while NAGA keeps it | 4,057 | 23.9% | -8.0 pp | -0.035 | Safe tiles expire when their target or route value expires. |
| Keep dora/red-five material | 617 | 24.6% | -6.5 pp | -0.011 | Value seeds are worth preserving when they improve a real route. |
| Leader choices with controlled danger | 5,153 | 29.6% | -1.7 pp | -0.025 | Leader safety qualifies the plan. |
| Behind-score choices that buy route/value with extra danger | 2,364 | 34.5% | +3.7 pp | +0.120 | Broad behind-score risk buying needs tight concrete-upside filters. |
| Generic keep genbutsu/suji exit | 8,590 | 35.1% | +5.4 pp | +0.036 | Generic safety hoarding stays weak. |
| Break pair earlier than NAGA | 4,318 | 35.9% | +5.6 pp | +0.021 | Pair breaks need subcategories; the broad action is risky by this proxy. |
| Cut middle tile while keeping outside/safety/yaku | 10,926 | 38.6% | +10.9 pp | +0.029 | The broad "keep outside material" story is too loose and often bad. |

## New mineable points

1. Yakuhai cleaning is real but narrow.

   The open-hand yaku-condition subset has 285 cases and a 24.6% bad rate, 6.5 pp better than other mismatches. It should stay tied to visible context: a singleton yakuhai, an open opponent with unclear yaku, and a hand with another self-value route.

2. Guest-honor cleanup is stronger than generic honor cleanup.

   The first-row non-self honor subset has 278 cases, a 19.4% bad rate, and an 11.7 pp improvement compared with other mismatches. This is a useful split: LuckyJ often removes honors that lack a self job before NAGA's preferred shape cleanup.

3. Self yakuhai pairs are route anchors.

   The self-yakuhai pair/triplet anchor subset is small at 135 cases, but its bad rate is 20.0%, 11.1 pp better than baseline. Treat this as a drill category while more examples are reviewed.

4. Stale safety should be target-checked.

   The off-target safety-spend subset has 2,992 cases and a 22.1% bad rate, 9.7 pp better than baseline. This explains why "safe tile" language must name the target opponent; otherwise the tile can become route clutter.

5. Late exits need names.

   The late named-exit subset has 931 cases and a 20.2% bad rate, 11.1 pp better than baseline. This supports late safety only when the kept tile defends an actual live threat.

## Keep Narrow

- Generic "keep genbutsu/suji because it is safe" remains weak.
- Broad "break pairs early" remains too noisy.
- Broad behind-score danger buying remains too expensive unless the upside is concrete.
- Broad middle-tile cuts to keep outside material are often bad; the route-preserving outside-cut point is the supported opposite subcase.
