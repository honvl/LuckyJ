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
`service/players/<player>/<thread>/` after each turn. IDs live in `service/.state/state.json`.
Neither folder is committed.

## Cost

Tokens are billed at Opus 5.5 rates and sandbox time at $0.08 per running hour (idle time is
free). Each thread is created with a hard spending cap (`--budget`, US dollars); at the cap it
pauses until `topup` raises it.
