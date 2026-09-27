# LuckyJ against the humans at its tables

Scripts behind `analysis/table-contrast-2026-09-25.md`: LuckyJ's 1,079 Tokujou hanchan compared with
the 3,237 human seats at the same tables and with 2,714 Houou hanchan from 2023, decision by decision.

The extractors run in the project venv (`.venv`, which has `mahjong`, `torch` and `libriichi`). The
report scripts under `report/` use pandas and numpy; they ran in a separate scratch venv
(`uv venv` with `pandas pyarrow numpy mahjong==2.0.0`), since the project venv has no pandas. They
read their inputs from the working directory they are run in.

## Inputs

- `data/local_sources/luckyj_tenhou/index.json` (from `scripts/naga_to_tenhou.py`): LuckyJ's games as
  tenhou.net/6 logs with all four hands. Filter to `mode == "tenhou-tokujou"` for the comparison.
- `data/report_cache/*.json.gz`: the NAGA reports, which also carry NAGA's discard predictions for
  every seat (`naga_align.py`).
- `~/Downloads/mjlog_combined_local_mjai/*.json.gz`: the local Tenhou mjai archive. The 2023 Houou
  hanchan (`2023*gm-00a9-*`) are the Houou baseline, and 1,254 of LuckyJ's 1,255 games are in it too,
  which is what `mortal_run.py` replays.

Each extractor takes a manifest in the `fetch_majsoul_games.py` shape (`file`, `hero_seat`, `uuid`,
`start_time`). For the tablemate baseline, list every LuckyJ game three more times with
`hero_seat` set to each human seat (`uuid` suffixed `#s<seat>`), and give the existing miners that
manifest; they then measure the humans with the same code that measured LuckyJ.

## Pipeline

1. `mjai2tenhou.py OUTDIR MANIFEST FILES...` converts the Houou mjai logs to tenhou.net/6 games,
   reconciling scores hand to hand (2,714 of 2,715 passed), and writes a four-seat manifest.
2. `hands_all.py MANIFEST GROUP OUT.json`: one record per hand and seat (state at a deal-in, win,
   riichi, calls, net points). Feeds the ledger and the deal-in split.
3. `discards.py MANIFEST OUT.jsonl [--early]`: one row per discard with shanten, acceptance of every
   candidate, isolated-tile classes, threats, and safety labels against riichi or callers.
4. `calls.py`, `tenpai.py`: every chi/pon chance with the block it completes, and every closed
   decision where a tenpai is available with the dama and riichi value of each wait.
5. `riichi_level.py`, `riichi_response.py`, `riichi_wall.py`: one row per riichi (wait, table state,
   where the winning tiles really were, result) and one row per other seat at each riichi (safe tiles
   held, shanten, result).
6. `naga_align.py` and `mortal_run.py`: NAGA's three heads and a local Mortal policy model for every
   seat's decisions, keyed so they join to the discard rows on `(g, li, s, t)`.
7. The existing miners (`mine_riichi_folds.py`, `mine_vs_open.py`, `mine_caller_tells.py`,
   `mine_call_chances.py`, `mine_dora_hands.py`, `mine_shape_plans.py`, `mine_tenpai_push.py`) run on
   the LuckyJ, tablemate and Houou manifests; `runjobs.py` runs a job list in parallel.
8. `report/*.py` reads those outputs and prints every figure the write-up cites.

`pairs.py` counts rons per ordered pair of players (human into LuckyJ, human into human), which is how
the opponent-pool effect on win rates was separated from LuckyJ's own play. `flushwins.py` counts
half and full flush wins from the winners' final hands, since the Houou mjai logs carry no yaku list.

## Open callers (27 September 2026)

`analysis/open-callers-2026-09-27.md` (the book's "When to fold to open callers" section) comes from
one more extractor and one exporter:

1. `vs_callers.py MANIFEST GROUP PREFIX` writes `PREFIX.cuts.jsonl`, one row per discard and caller
   while nobody is in riichi (the tile's safety label, whether it was on the caller's real wait, the
   caller's calls, discards so far, tsumogiri run, visible dora and the tiles they passed since their
   last discard), and `PREFIX.tenpai.jsonl`, every tenpai decision against callers with the
   half-wait dilemmas marked. Run it as `vs_callers.py man/lj_all.json lj callers_lj` and
   `vs_callers.py man/houou_games.json houou callers_hou` (about 7 and 20 seconds on 14 processes).
2. `riichi_danger.py MANIFEST GROUP OUT.jsonl` writes every closed tenpai decision made under a threat
   (an opponent in riichi or with an open meld): each tenpai discard's live tiles, furiten, han with and
   without riichi, and danger against the riichi players and the callers. Run it on the same two
   manifests as `riichi_open_lj.jsonl` and `riichi_open_hou.jsonl`.
3. `mortal_spots.py SPOTS.json OUT.jsonl` asks the local Mortal policy about chosen spots. It replays the
   seat's mjai log up to the draw or call, records the action probabilities (riichi included), and when
   riichi is legal injects a declaration to record the tile Mortal would declare with. Run it on the
   half-wait dilemmas of LuckyJ's games (`mortal_halfwait.jsonl`) and on the riichi dilemmas of both
   corpora (`mortal_riichi_open.jsonl`).
4. `report/export_open_callers.py OUT.json`, run in the same directory with those files and
   `mortal_disc.parquet` beside it, writes `analysis/open-callers-2026-09-27.json`, which
   `tests/test_open_callers.py` pins.

The first run of `vs_callers.py` dropped every discard that was itself a riichi declaration, which left
closed hands that declared out of the half-wait dilemmas. The cut rows still leave declarations out (they
describe discards made with nobody in riichi, and a declaration is always made from tenpai); the tenpai
rows keep them and record `riichi`.
