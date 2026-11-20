# Player threads

Each paying player gets a long-lived thread: a Claude Opus 5.5 conversation (a Managed Agents
session) running in its own cloud sandbox. The sandbox holds this repository, the player's games,
LuckyJ's games and the Mortal policy. The player talks about their games there, and Claude builds
their guide chapters the way the Honver guide was built. Threads are kept, not deleted after a
chapter; they are removed only when a player closes their account.

- `agent/system.md`: the coach's instructions (method, chapter format, voice, limits).
- `sandbox/setup.sh`: prepares a sandbox: clones the repo, installs CPU torch, builds or reuses
  libriichi, links the Mortal weights, unpacks LuckyJ's and the player's games.
- `thread.py`: the operator's terminal client.

## Use

Needs an Anthropic API key, pasted as a single line into `service/.state/api_key` (gitignored;
`ANTHROPIC_API_KEY` in the environment also works, but keep it out of your shell profile so
Claude Code keeps its own login), the Mortal
policy in `~/Downloads/mortal_model_policy/`, and LuckyJ's logs in
`data/local_sources/luckyj_tenhou/` (from `scripts/naga_to_tenhou.py`).

```bash
.venv/bin/python service/thread.py setup
.venv/bin/python service/thread.py new Honver --games data/self_games/majsoul --budget 15
.venv/bin/python service/thread.py chat Honver
.venv/bin/python service/thread.py list
.venv/bin/python service/thread.py topup Honver 10
```

`setup` is safe to rerun: it uploads only files that changed and makes a new agent version only
when the prompt or tools changed. New threads pick up the latest version; running threads keep
theirs. The first thread compiles libriichi (a few minutes) and `chat` caches the wheel so later
threads install it directly. Anything the agent writes to `/mnt/session/outputs/` is copied to
`service/players/<player>/<thread>/` after each turn. The API lists outputs by bare file name
(no folders), so the agent names them uniquely and packs each chapter as
`chapter-<NN>-<slug>.tar.gz`, which `chat` unpacks into `chapters/<NN>-<slug>/`. IDs live in the site's database (table `service_state`, shared with the scheduled onboarding run); `service/.state/state.json` is a local copy.
Neither folder is committed.

A thread keeps the agent version it started with. After `setup` makes a new version, run
`.venv/bin/python service/thread.py refresh`: it replaces each older thread's tools at once
and queues the current instructions as system context for the player's next message (the
system prompt of a running thread cannot be replaced).

What a thread can reach (since 20 Nov 2026): open internet, web search and web fetch; the
player's whole ranked-game history (`amae-koromo-records.json`) and live rank and points
(`amae-koromo-stats.json`) from onboarding; a shared sample of recent Jade and Throne games
(`/mnt/session/uploads/room/recent-games.json`, refreshed by `setup` when a week old, from
`scripts/fetch_room_sample.py`); and the game-records API live. The API key sits in a vault
credential (`vlt_...` in the operator state) that the platform substitutes into requests to
`*.amae-koromo.com`; the sandbox only sees a placeholder in `$AMAE_KOROMO_TOKEN`. A vault can
be attached only when a thread starts, so threads older than the vault have everything except
the live API.

## Cost

First live run (15 Nov 2026, Honver's 303 games): sandbox build plus a placement and riichi-rate
answer $0.38; a tenpai split (riichi, dama, open) against LuckyJ $0.67.


Tokens are billed at Opus 5.5 rates and sandbox time at $0.08 per running hour (idle time is
free). Each thread is created with a hard spending cap (`--budget`, US dollars); at the cap it
pauses until `topup` raises it.
