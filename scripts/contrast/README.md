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
