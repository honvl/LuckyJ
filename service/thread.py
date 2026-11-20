#!/usr/bin/env python3
"""Run player threads: a long-lived Claude Opus 5.5 conversation per player, in a cloud sandbox.

Each thread is a Managed Agents session. The sandbox holds the site repository, the player's
games, LuckyJ's games and the Mortal policy, so the player can ask about their games and have
chapters built the way the Honver guide was. Threads are never deleted after a chapter; a
player can keep talking in one for months.

    .venv/bin/python service/thread.py setup
    .venv/bin/python service/thread.py new Honver --games data/self_games/majsoul
    .venv/bin/python service/thread.py chat Honver
    .venv/bin/python service/thread.py list
    .venv/bin/python service/thread.py topup Honver 10

Credentials come from the environment (ANTHROPIC_API_KEY, or an `ant auth login` profile).
IDs of everything created live in service/.state/state.json, which is not committed.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "service"
STATE = SERVICE / ".state" / "state.json"
KEY_FILE = SERVICE / ".state" / "api_key"  # one line, the key; gitignored with .state/
DB_URL_FILE = SERVICE / ".state" / "database_url"  # the hosted site's Postgres, one line
SCHEMA = SERVICE / "db" / "schema.sql"
WEB_STATE = SERVICE / ".state" / "web.json"
PLAYERS = SERVICE / "players"
SYSTEM = SERVICE / "agent" / "system.md"
SETUP_SH = SERVICE / "sandbox" / "setup.sh"
MORTAL_DIR = Path.home() / "Downloads" / "mortal_model_policy"
LUCKYJ_LOGS = ROOT / "data" / "local_sources" / "luckyj_tenhou"

MODEL = {"id": "claude-opus-5-5", "effort": "high"}
AGENT_NAME = "Mahjong coach"
AGENT_DESCRIPTION = ("Riichi mahjong coach for one player. A copy can be handed one chapter of the "
                     "player's Personal Guide to build end to end from a self-contained brief.")
# Chapters are built in a copy of the coach, in its own session thread. A chapter build reads
# ~170k tokens of code, tables and figures; in the chat thread all of it stayed in the context,
# so every later reply re-read it (and paid to rewrite it after a 5-minute pause). The copy keeps
# that in its own thread and the chat thread gets only its report. Workflows stay off: one
# chapter is one piece of work, and runs would bill extra agents.
MULTIAGENT = {
    "type": "multiagent_20261001",
    "subagents": {"type": "enabled", "predefined_agents": [{"type": "self"}],
                  "inline_agents": {"type": "disabled"}},
    "workflows": {"type": "disabled"},
}
ENV_NAME = "mahjong-coach"
MA_BETA = "managed-agents-2026-04-01"
DEFAULT_BUDGET_USD = 15

ENV_CONFIG = {
    "type": "cloud",
    # Open internet, as the operator's own sessions have: the coach downloads data, reads rule
    # pages and calls the game-records API. No secrets live in the sandbox (see VAULT below).
    "networking": {"type": "unrestricted"},
}

TOOLS = [{
    "type": "agent_toolset_20260401",
    # Every call approved, as in the operator's own sessions: the "auto" policy's risk check
    # denied ordinary work (starting setup.sh in the background) and the coach then gave up on
    # the shell. No secrets live in the sandbox; the records key is a vault placeholder.
    "default_config": {"enabled": True, "permission_policy": {"type": "always_allow"}},
    "configs": [
        {"name": "web_fetch", "enabled": True},
        {"name": "web_search", "enabled": True},
    ],
}]

# The game-records API key reaches the sandbox only as a placeholder in $AMAE_KOROMO_TOKEN; the
# platform swaps in the real key on requests to these hosts, so the coach can query the API
# without ever seeing the key.
VAULT_NAME = "mahjong-coach"
AMAE_SECRET = "AMAE_KOROMO_TOKEN"
AMAE_HOSTS = ["*.amae-koromo.com"]
ROOM_SAMPLE = SERVICE / ".state" / "room-sample.json"
ROOM_SAMPLE_MAX_AGE_DAYS = 7


# ------------------------------------------------------------------ state

STATE_KEY = "operator"  # the row in service_state that holds this file's contents
STATE_TABLE = ("create table if not exists service_state (key text primary key, value jsonb not null,"
               " updated_at timestamptz not null default now())")


def in_ci() -> bool:
    """A GitHub Actions run, whose logs are public: print no emails, names or account ids."""
    return os.environ.get("GITHUB_ACTIONS") == "true"


def load_state() -> dict:
    """The operator's records: agent, environment, shared files, players and their threads.

    With a database they live there (so the scheduled cloud run and this Mac share them) and
    state.json is a local copy; the first run copies an existing state.json up.
    """
    local = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else None
    url = database_url()
    if not url:
        return local or {"shared_files": {}, "players": {}}
    import psycopg
    from psycopg.types.json import Jsonb
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(STATE_TABLE)
        row = conn.execute("select value from service_state where key = %s", (STATE_KEY,)).fetchone()
        if row is None and local is not None:
            conn.execute("insert into service_state (key, value) values (%s, %s) on conflict do nothing",
                         (STATE_KEY, Jsonb(local)))
            return local
    state = row[0] if row else {"shared_files": {}, "players": {}}
    if not in_ci():
        write_local_state(state)
    return state


def merge_state(ours: dict, theirs: dict) -> dict:
    """Combine two copies of the records so a run never drops what another run added.

    Ours wins where both have a value; players, shared files, emails and threads are unions
    (threads by session id, in the order they were made).
    """
    merged = {**theirs, **ours}
    merged["shared_files"] = {**theirs.get("shared_files", {}), **ours.get("shared_files", {})}
    players = {}
    for name in [*theirs.get("players", {}), *[n for n in ours.get("players", {}) if n not in theirs.get("players", {})]]:
        a, b = ours.get("players", {}).get(name), theirs.get("players", {}).get(name)
        if a is None or b is None:
            players[name] = a if a is not None else b
            continue
        p = {**b, **a}
        p["emails"] = list(dict.fromkeys([*b.get("emails", []), *a.get("emails", [])]))
        if not p["emails"]:
            del p["emails"]
        mine = {t["session_id"]: t for t in a.get("threads", [])}
        threads = [mine.pop(t["session_id"], t) for t in b.get("threads", [])]
        p["threads"] = threads + list(mine.values())
        players[name] = p
    merged["players"] = players
    return merged


def database_url() -> str | None:
    """The hosted site's database, from DATABASE_URL or service/.state/database_url."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url and DB_URL_FILE.exists():
        url = DB_URL_FILE.read_text(encoding="utf-8").strip()
    return url or None


def db_sync(state: dict) -> bool:
    """Copy players, threads, login emails and private chapters into the site's database.

    Rows already there are kept as they are (a thread's queued intro may have been taken by the
    site since), so this only adds. Returns False when no database is configured.
    """
    url = database_url()
    if not url:
        return False
    import psycopg
    web = json.loads(WEB_STATE.read_text(encoding="utf-8")) if WEB_STATE.exists() else {}
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        for name, info in state["players"].items():
            conn.execute("insert into players (name) values (%s) on conflict do nothing", (name,))
            threads = info.get("threads", [])
            for i, t in enumerate(threads):
                # Oldest first, a second apart, so "latest thread" keeps the file's order.
                conn.execute(
                    "insert into threads (session_id, player, created_at, intro)"
                    " values (%s, %s, now() - make_interval(secs => %s), %s) on conflict do nothing",
                    (t["session_id"], name, len(threads) - i, t.get("intro")))
            for email in info.get("emails", []):
                row = conn.execute("insert into logins (email, player) values (%s, %s)"
                                   " on conflict (email) do nothing returning player",
                                   (email, name)).fetchone()
                if row is None:
                    owner = conn.execute("select player from logins where email = %s", (email,)).fetchone()
                    if owner and owner[0] != name:
                        print("  ! a login email belongs to another player in the database" if in_ci()
                              else f"  ! {email} belongs to {owner[0]} in the database, not {name}")
            for chapter in web.get("private_chapters", {}).get(name, []):
                conn.execute("insert into private_chapters (player, chapter) values (%s, %s)"
                             " on conflict do nothing", (name, chapter))
    return True


def take_intro(state: dict, player: str, session_id: str) -> str | None:
    """A thread's queued system context, taken once (from the database when there is one)."""
    thread = next(t for t in state["players"][player]["threads"] if t["session_id"] == session_id)
    local = thread.pop("intro", None)
    save_state(state)
    url = database_url()
    if not url:
        return local
    import psycopg
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute(
            "update threads t set intro = null from (select session_id, intro from threads"
            " where session_id = %s for update) old where t.session_id = old.session_id"
            " and old.intro is not null returning old.intro", (session_id,)).fetchone()
    return row[0] if row else None


UPDATE_MARKER = "Your operator has updated your instructions"


def queue_intro(state: dict, player: str, session_id: str, text: str) -> None:
    """Add to a thread's queued system context, which goes out with the player's next message.

    An instructions update not yet delivered is replaced, not stacked: it always comes last.
    """
    def keep(intro: str | None) -> str | None:
        return (intro or "").split(UPDATE_MARKER)[0].rstrip() or None
    thread = next(t for t in state["players"][player]["threads"] if t["session_id"] == session_id)
    thread["intro"] = "\n\n".join(x for x in (keep(thread.get("intro")), text) if x)
    save_state(state)
    url = database_url()
    if not url:
        return
    import psycopg
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            "update threads set intro = concat_ws(E'\\n\\n',"
            " nullif(rtrim(split_part(coalesce(intro, ''), %s, 1)), ''), %s::text) where session_id = %s",
            (UPDATE_MARKER, text, session_id))


def instructions_update(version: int, system: str) -> str:
    """The note that brings an older thread's instructions up to the current agent version."""
    return (f"{UPDATE_MARKER} (agent version {version}). The full current "
            "instructions follow. Where they differ from the ones you started with, follow these. "
            "Do not mention this update to the player.\n\n" + system)


def write_local_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")


def save_state(state: dict) -> None:
    url = database_url()
    if url:
        import psycopg
        from psycopg.types.json import Jsonb
        with psycopg.connect(url) as conn:  # one transaction: the row stays locked until written
            conn.execute(STATE_TABLE)
            row = conn.execute("select value from service_state where key = %s for update",
                               (STATE_KEY,)).fetchone()
            merged = merge_state(state, row[0]) if row else state
            conn.execute("insert into service_state (key, value, updated_at) values (%s, %s, now())"
                         " on conflict (key) do update set value = excluded.value, updated_at = now()",
                         (STATE_KEY, Jsonb(merged)))
        state.clear()
        state.update(merged)
    if not in_ci():
        write_local_state(state)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return s or "player-" + sha256(name.encode())[:8]


def need_player(state: dict, player: str) -> dict:
    if player not in state["players"]:
        sys.exit(f"no player {player!r}; start one with: thread.py new {player} --games DIR")
    return state["players"][player]


def latest_thread(state: dict, player: str) -> str:
    threads = need_player(state, player)["threads"]
    if not threads:
        sys.exit(f"{player} has no thread yet")
    return threads[-1]["session_id"]


# ------------------------------------------------------------------ uploads

def tar_gz(members: list[tuple[str, Path]]) -> bytes:
    """A reproducible tar.gz (fixed mtimes) so unchanged inputs hash the same."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for arcname, path in sorted(members):
            info = tar.gettarinfo(str(path), arcname)
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, "", ""
            with path.open("rb") as fh:
                tar.addfile(info, fh)
    # gzip stamps the current time in its header unless told otherwise.
    return gzip.compress(buf.getvalue(), compresslevel=6, mtime=0)


def upload(client: anthropic.Anthropic, name: str, data: bytes) -> str:
    # The file name carries the player's key (ms-<account id>), which a public log must not show.
    print(f"  uploading {'a file' if in_ci() else name} ({len(data) / 1e6:.1f} MB)")
    meta = client.files.upload(file=(name, data), timeout=1800)
    return meta.id


def sync_shared(client: anthropic.Anthropic, state: dict, mount: str, name: str, data: bytes) -> None:
    """Upload a file every thread mounts, unless the same bytes are already uploaded."""
    have = state["shared_files"].get(mount)
    digest = sha256(data)
    if have and have["sha256"] == digest:
        return
    state["shared_files"][mount] = {"file_id": upload(client, name, data), "sha256": digest}
    save_state(state)


def shared_resources(state: dict) -> list[dict]:
    return [{"type": "file", "file_id": f["file_id"], "mount_path": mount}
            for mount, f in sorted(state["shared_files"].items())]


# ------------------------------------------------------------------ setup

def cmd_setup(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    state = load_state()

    print("environment")
    if state.get("environment_id"):
        client.beta.environments.update(state["environment_id"], config=ENV_CONFIG)
    else:
        env = client.beta.environments.create(name=ENV_NAME, config=ENV_CONFIG)
        state["environment_id"] = env.id
        save_state(state)
    print(f"  {state['environment_id']}")

    print("shared files")
    for f in ("model.py", "mortal.pth"):
        if not (MORTAL_DIR / f).exists():
            sys.exit(f"missing {MORTAL_DIR / f}")
    sync_shared(client, state, "/setup.sh", "setup.sh", SETUP_SH.read_bytes())
    sync_shared(client, state, "/mortal/model.py", "model.py", (MORTAL_DIR / "model.py").read_bytes())
    sync_shared(client, state, "/mortal/mortal.pth", "mortal.pth", (MORTAL_DIR / "mortal.pth").read_bytes())
    logs = sorted(LUCKYJ_LOGS.glob("*.json"))
    if not logs:
        sys.exit(f"no LuckyJ logs in {LUCKYJ_LOGS}; run scripts/naga_to_tenhou.py first")
    sync_shared(client, state, "/luckyj/luckyj_tenhou.tar.gz", "luckyj_tenhou.tar.gz",
                tar_gz([(f"luckyj_tenhou/{p.name}", p) for p in logs]))

    if not ROOM_SAMPLE.exists() or time.time() - ROOM_SAMPLE.stat().st_mtime > ROOM_SAMPLE_MAX_AGE_DAYS * 86400:
        print("  refreshing the room sample (a few minutes)")
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_room_sample.py"), str(ROOM_SAMPLE)],
                       check=True)
    sync_shared(client, state, "/room/recent-games.json", "recent-games.json", ROOM_SAMPLE.read_bytes())

    print("vault")
    setup_vault(client, state)
    print(f"  {state['vault_id']}")

    print("agent")
    system = SYSTEM.read_text(encoding="utf-8")
    config = dict(model=MODEL, system=system, tools=TOOLS, description=AGENT_DESCRIPTION,
                  multiagent=MULTIAGENT)
    config_hash = sha256(json.dumps(config, sort_keys=True).encode())
    if not state.get("agent_id"):
        agent = client.beta.agents.create(name=AGENT_NAME, **config)
        state["agent_id"] = agent.id
    elif state.get("agent_hash") != config_hash:
        current = client.beta.agents.retrieve(state["agent_id"])
        agent = client.beta.agents.update(state["agent_id"], version=current.version, **config)
    else:
        agent = client.beta.agents.retrieve(state["agent_id"])
    state["agent_hash"] = config_hash
    save_state(state)
    print(f"  {agent.id} version {agent.version}")
    print("New threads use this setup. Existing threads keep the files they started with;"
          " `thread.py refresh` brings their tools and instructions up to date.")


# ------------------------------------------------------------------ threads

def setup_vault(client: anthropic.Anthropic, state: dict) -> None:
    """The vault whose credential puts the game-records key on the coach's API requests."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import fetch_majsoul_games as fms
    token = fms.amae_token()
    if not token:
        sys.exit("no AMAE_KOROMO_TOKEN in the environment or tmp/tensoul/.env")
    if not state.get("vault_id"):
        state["vault_id"] = client.beta.vaults.create(display_name=VAULT_NAME).id
        save_state(state)
    auth = {"type": "environment_variable", "secret_name": AMAE_SECRET, "secret_value": token,
            "networking": {"type": "limited", "allowed_hosts": AMAE_HOSTS},
            "injection_location": {"header": True, "body": False}}
    digest = sha256(json.dumps(auth, sort_keys=True).encode())
    if state.get("vault_credential_id") and state.get("vault_credential_hash") == digest:
        return
    if state.get("vault_credential_id"):
        update = {k: v for k, v in auth.items() if k != "secret_name"}  # the name is immutable
        client.beta.vaults.credentials.update(state["vault_credential_id"], vault_id=state["vault_id"],
                                              auth=update)
    else:
        cred = client.beta.vaults.credentials.create(state["vault_id"], auth=auth,
                                                     display_name="game records API")
        state["vault_credential_id"] = cred.id
    state["vault_credential_hash"] = digest
    save_state(state)


def cmd_new(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    state = load_state()
    if not state.get("agent_id"):
        sys.exit("run `thread.py setup` first")
    games_dir = Path(args.games).resolve()
    if not (games_dir / "index.json").exists():
        sys.exit(f"{games_dir} has no index.json (the manifest fetch_majsoul_games.py writes)")
    games = sorted(games_dir.glob("*.json"))
    archive = tar_gz([(p.name, p) for p in games])
    print(f"{'player' if in_ci() else args.player}: {len(games) - 1} game files")

    player = state["players"].setdefault(args.player, {"threads": []})
    if not player.get("memory_store_id"):
        store = client.beta.memory_stores.create(
            name=f"notes-{slug(args.player)}",
            description=(f"Notes on the mahjong player {args.player}: findings with their numbers, "
                         "sample sizes and the scripts behind them, the chapters already "
                         "delivered, and what the player asked for."),
        )
        player["memory_store_id"] = store.id
        save_state(state)

    games_file = upload(client, f"games-{slug(args.player)}.tar.gz", archive)
    resources = shared_resources(state) + [
        {"type": "file", "file_id": games_file, "mount_path": "/player/games.tar.gz"},
        {"type": "memory_store", "memory_store_id": player["memory_store_id"], "access": "read_write",
         "instructions": "This player's notes. Read index.md and player.md first; keep the notes current (see Keeping notes)."},
    ]
    cents = int(round(args.budget * 100))
    # All of a player's threads share one allowance (web/lib/budget.ts moves it to the thread the
    # player writes in). The first thread sets it; a later one starts at a cent and gets its share
    # with the player's first message on the site.
    first = not player["threads"]
    if not first:
        cents = 1
    session = client.beta.sessions.create(
        agent=state["agent_id"],
        environment_id=state["environment_id"],
        title=f"{args.player}, thread {len(player['threads']) + 1}",
        metadata={"player": args.player},
        budget={"type": "limit", "max_list_cost": {"amount": str(cents), "currency": "USD"}},
        resources=resources,
        vault_ids=[state["vault_id"]] if state.get("vault_id") else [],
    )
    index = json.loads((games_dir / "index.json").read_text(encoding="utf-8"))
    names = sorted({row.get("hero_name") for row in index if row.get("hero_name")})
    player["hero_names"] = names  # the site's "new thread" writes the same intro
    player["threads"].append({"session_id": session.id, "games_file_id": games_file,
                              "downloaded": [], "intro": intro(args.player, names)})
    if args.email:
        emails = player.setdefault("emails", [])
        if args.email.strip().lower() not in emails:
            emails.append(args.email.strip().lower())
    save_state(state)
    if db_sync(state):
        print("  recorded in the site's database")
        if first:
            set_allowance(args.player, cents, only_if_unset=True)
    if in_ci():
        print(f"  thread started with a ${args.budget:.2f} cap")
        return
    print(f"thread {session.id} with a ${args.budget:.2f} cap")
    if args.email:
        print(f"  {args.email} opens it on the site")
    print(f"talk to it: .venv/bin/python service/thread.py chat {args.player}")


def intro(player: str, names: list[str]) -> str:
    """System context sent with a thread's first message: who the player is."""
    shown = ", ".join(names) or "unknown"
    return (f"This thread's player is {player}. In their games they play as: {shown} "
            "(the hero_name in index.json). These games are theirs; analyse them as theirs.")


def short(value: object, limit: int = 140) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def run_turn(client: anthropic.Anthropic, session_id: str, text: str,
             context: str | None = None) -> str:
    """Send one message and print the thread's work until it waits for the player again.

    `context`, when given, goes with it as a system message (it stays for every later turn).
    """
    last_cost = None
    events = [{"type": "user.message", "content": [{"type": "text", "text": text}]}]
    if context:
        # The API takes a system message only as the last event of a request.
        events.append({"type": "system.message", "content": [{"type": "text", "text": context}]})
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        client.beta.sessions.events.send(session_id=session_id, events=events)
        for ev in stream:
            if ev.type == "agent.message":
                for block in ev.content:
                    if block.type == "text":
                        print(block.text, end="", flush=True)
                print()
            elif ev.type == "agent.tool_use":
                cmd = ev.input.get("command") or ev.input.get("file_path") or ev.input
                print(f"  · {ev.name}: {short(cmd)}", flush=True)
                if ev.evaluated_permission == "ask":
                    answer = input("    allow this call? [y/N] ").strip().lower()
                    client.beta.sessions.events.send(
                        session_id=session_id,
                        events=[{"type": "user.tool_confirmation", "tool_use_id": ev.id,
                                 "result": "allow" if answer == "y" else "deny"}],
                    )
            elif ev.type == "agent.tool_result" and ev.is_error:
                print("    (tool error)", flush=True)
            elif ev.type == "agent.thread_context_compacted":
                print("  · earlier conversation summarized to fit the context", flush=True)
            elif ev.type == "session.usage":
                cost = getattr(getattr(ev, "usage", None), "list_cost", None)
                if cost is not None:
                    last_cost = cost
            elif ev.type == "session.error":
                print(f"  ! error: {short(ev.error.model_dump() if hasattr(ev.error, 'model_dump') else ev.error)}")
            elif ev.type == "session.status_idle":
                reason = ev.stop_reason.type
                if reason == "requires_action":
                    continue
                if reason == "budget_reached":
                    print("  ! this thread reached its spending cap; raise it with `thread.py topup`")
                elif reason == "refusal":
                    print("  ! the model declined this request")
                break
            elif ev.type == "session.status_terminated":
                print("  ! the thread has ended and cannot continue")
                break
    if last_cost is not None:
        print(f"  [spent so far: ${int(last_cost.amount) / 100:.2f}]")
    return session_id


def pull_outputs(client: anthropic.Anthropic, state: dict, player: str, session_id: str) -> None:
    """Copy new files from the sandbox's outputs to service/players/<player>/<session>/."""
    thread = next(t for t in state["players"][player]["threads"] if t["session_id"] == session_id)
    done = set(thread.get("downloaded", []))
    dest = PLAYERS / slug(player) / session_id
    # The listing also holds the files we mounted (not downloadable) and gives each output
    # only its bare filename, so the agent names outputs uniquely and packs each chapter
    # as chapter-<NN>-<slug>.tar.gz. Oldest first, so a rewritten file ends up newest.
    files = sorted(client.beta.files.list(scope_id=session_id, betas=[MA_BETA]),
                   key=lambda f: f.created_at)
    for f in files:
        if f.id in done or not f.downloadable:
            continue
        rel = Path(Path(f.filename).name)
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        client.beta.files.download(f.id, betas=[MA_BETA]).write_to_file(target)
        done.add(f.id)
        print(f"  saved {target.relative_to(ROOT)}")
        m = re.fullmatch(r"chapter-(\d+-[\w-]+)\.tar\.gz", rel.name)
        if m:
            folder = dest / "chapters" / m.group(1)
            folder.mkdir(parents=True, exist_ok=True)
            with tarfile.open(target) as tar:
                tar.extractall(folder, filter="data")
            print(f"  unpacked {folder.relative_to(ROOT)}")
        if f.filename.endswith(".whl") and "libriichi" in f.filename:
            cached = [m for m in state["shared_files"] if m.startswith("/cache/")]
            if not cached:
                # Later threads install this wheel instead of compiling libriichi again.
                sync_shared(client, state, f"/cache/{rel.name}", rel.name, target.read_bytes())
                print("  cached the libriichi wheel for new threads")
    thread["downloaded"] = sorted(done)
    save_state(state)


def cmd_chat(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    state = load_state()
    session_id = args.thread or latest_thread(state, args.player)
    print(f"{args.player} · {session_id}. Empty line or Ctrl-D to leave.\n")
    while True:
        try:
            text = input("you> ").strip()
        except EOFError:
            print()
            break
        if not text:
            break
        try:
            run_turn(client, session_id, text, context=take_intro(state, args.player, session_id))
        except anthropic.BadRequestError as e:
            print(f"  ! {e.message}")
            continue
        pull_outputs(client, state, args.player, session_id)


def cmd_link(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    """Let a login email open this player's thread on the web page."""
    state = load_state()
    if args.player not in state["players"]:
        sys.exit(f"no player {args.player}; create a thread with `new` first")
    email = args.email.strip().lower()
    for name, info in state["players"].items():
        if name != args.player and email in info.get("emails", []):
            sys.exit(f"{email} already belongs to {name}")
    emails = state["players"][args.player].setdefault("emails", [])
    if email not in emails:
        emails.append(email)
    save_state(state)
    db_sync(state)
    print(f"{email} opens {args.player}'s latest thread")


def _db():
    url = database_url()
    if not url:
        sys.exit(f"no database: set DATABASE_URL or write it to {DB_URL_FILE.relative_to(ROOT)}")
    import psycopg
    return psycopg.connect(url, autocommit=True)


def cmd_pending(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    """Paying players whose games still need fetching and whose thread does not exist yet."""
    with _db() as conn:
        rows = conn.execute(
            "select s.email, p.majsoul_name, p.majsoul_server, p.majsoul_account_id, p.publish, s.status, s.created_at"
            " from subscriptions s left join profiles p on p.email = s.email"
            " left join logins l on l.email = s.email"
            " where l.email is null and s.status in ('active', 'trialing', 'past_due')"
            " order by s.created_at").fetchall()
    if not rows:
        print("nobody is waiting")
    for email, name, server, account_id, publish, status, created in rows:
        who = f"{name} ({server}, {account_id})" if account_id else "no Mahjong Soul account yet"
        print(f"{created:%Y-%m-%d %H:%M}  {email}  {who}  {'public' if publish else 'private'}  {status}")
    if rows:
        print("\n`thread.py onboard` fetches their games and starts their threads.")


MIN_GAMES = 10  # a thread needs enough games to say anything


def cmd_onboard(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    """Start a thread for every paying player still waiting: fetch their games, create, link.

    The player is keyed by Mahjong Soul account id (ms-<id>), so two players with the same
    nickname on different servers never share a thread. Safe to run on a schedule.
    """
    with _db() as conn:
        rows = conn.execute(
            "select s.email, p.majsoul_account_id, p.majsoul_name, p.majsoul_server"
            " from subscriptions s join profiles p on p.email = s.email"
            " left join logins l on l.email = s.email"
            " where l.email is null and s.status in ('active', 'trialing') and p.majsoul_account_id is not null"
            " order by s.created_at").fetchall()
    if not rows:
        print("nobody is waiting")
        return
    ci = in_ci()
    failed = 0
    for n, (email, account_id, name, server) in enumerate(rows, 1):
        player = f"ms-{account_id}"
        games_dir = PLAYERS / player / "games"
        print(f"player {n} of {len(rows)} ({server})" if ci else f"{email}: {name} ({server}, {account_id})", flush=True)
        if args.dry_run:
            continue
        # The fetch's progress goes to the log as it happens (scrubbed in CI). A job killed for time
        # used to leave no line at all, because the output was held until the fetch returned.
        fetch = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "scripts" / "fetch_player_games.py"), "--account", str(account_id),
             "--out", str(games_dir)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in fetch.stdout:
            line = line.rstrip()
            if line:
                print("  " + (scrub(line, email, name, account_id) if ci else line)[:300], flush=True)
        fetch_failed = fetch.wait() != 0
        index = json.loads((games_dir / "index.json").read_text(encoding="utf-8")) if (games_dir / "index.json").exists() else []
        if fetch_failed:
            # A failed run is red in the workflow list, which is how the operator learns the fetch
            # account needs attention. Games fetched before a refusal still count toward MIN_GAMES.
            print("  ! fetch failed", flush=True)
            failed += 1
            if not index:
                continue
        if len(index) < MIN_GAMES:
            print(f"  waiting: {len(index)} ranked games found, a thread starts at {MIN_GAMES}", flush=True)
            continue
        cmd_new(client, argparse.Namespace(player=player, games=str(games_dir), budget=DEFAULT_BUDGET_USD, email=email))
    if failed:
        # A failed run is what tells the operator the fetch account's login needs attention.
        sys.exit(f"{failed} of {len(rows)} fetches failed")


def scrub(text: str, *private: object) -> str:
    """Text for a public log: the player's email, name and account id, game ids and paths removed."""
    for value in private:
        if value:
            text = text.replace(str(value), "…")
    text = re.sub(r"\b[0-9a-f]{6}-[0-9a-f]{8}-[0-9a-f-]{20,}\b", "<game>", text)  # Mahjong Soul uuids
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", "<id>", text)
    text = re.sub(r"\S+@\S+", "<email>", text)
    text = re.sub(r"\d{6,}", "<n>", text)
    return re.sub(r"(/[^\s/]+)+/", "", text)


def cmd_comp(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    """Let a player use the tutor without a subscription (or take that away with --off)."""
    with _db() as conn:
        n = conn.execute("update players set comp = %s where name = %s", (not args.off, args.player)).rowcount
    if not n:
        sys.exit(f"no player {args.player} in the database; run db-sync")
    print(f"{args.player} {'needs a subscription again' if args.off else 'uses the tutor free'}")


RANK_REFRESH_HOURS = 6


def cmd_ranks(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    """Store each player's Mahjong Soul rank for the library (players.rank_id, rank_points).

    The account id comes from the player's sign-up profile, or from a key like ms-<id>; `--player`
    with `--account` sets one by hand. Ranks younger than RANK_REFRESH_HOURS are left alone.
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import fetch_majsoul_games as fms
    token = fms.amae_token()
    if not token:
        sys.exit("no AMAE_KOROMO_TOKEN in the environment or tmp/tensoul/.env")
    with _db() as conn:
        conn.execute(SCHEMA.read_text(encoding="utf-8"))
        if args.player:
            if not args.account:
                sys.exit("--player needs --account")
            todo = [(args.player, args.account)]
        else:
            rows = conn.execute(
                "select p.name, max(pr.majsoul_account_id) from players p"
                " left join logins l on l.player = p.name"
                " left join profiles pr on pr.email = l.email"
                " where p.rank_at is null or p.rank_at < now() - make_interval(hours => %s)"
                " group by p.name", (RANK_REFRESH_HOURS,)).fetchall()
            todo = []
            for name, account in rows:
                m = re.fullmatch(r"ms-(\d+)", name)
                account = account or (int(m.group(1)) if m else None)
                if account:
                    todo.append((name, account))
        done = 0
        for name, account in todo:
            try:
                level = (fms.amae_stats(int(account), token).get("player_stats") or {}).get("level") or {}
            except Exception as e:  # one player's lookup failing leaves the others
                print(f"  ! rank lookup failed: {type(e).__name__}")
                continue
            if not level.get("id"):
                continue
            points = (level.get("score") or 0) + (level.get("delta") or 0)
            conn.execute("update players set rank_id = %s, rank_points = %s, rank_at = now() where name = %s",
                         (int(level["id"]), int(points), name))
            done += 1
    print(f"ranks stored for {done} of {len(todo)} players")


def cmd_db_sync(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    """Create the site's tables and copy every player into them."""
    if not db_sync(load_state()):
        sys.exit(f"no database: set DATABASE_URL or write it to {DB_URL_FILE.relative_to(ROOT)}")
    print("the site's database has every player, thread and login")


def cmd_list(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    state = load_state()
    for player, info in state["players"].items():
        print(player)
        for t in info["threads"]:
            s = client.beta.sessions.retrieve(t["session_id"])
            cost = s.usage.list_cost.amount if s.usage and s.usage.list_cost else "0"
            cap = s.budget.max_list_cost.amount if s.budget else None
            cap_txt = f" of ${int(cap) / 100:.2f}" if cap else ""
            print(f"  {s.id}  {s.status:<11} ${int(cost) / 100:.2f}{cap_txt}  {s.title or ''}")


def set_allowance(player: str, cents: int, only_if_unset: bool = False, add: bool = False) -> int | None:
    """The player's shared allowance in the site's database (US cents, lifetime). None without one."""
    url = database_url()
    if not url:
        return None
    import psycopg
    with psycopg.connect(url, autocommit=True) as conn:
        if add:
            row = conn.execute("update players set allowance_cents = coalesce(allowance_cents, 0) + %s"
                               " where name = %s returning allowance_cents", (cents, player)).fetchone()
        elif only_if_unset:
            row = conn.execute("update players set allowance_cents = coalesce(allowance_cents, %s)"
                               " where name = %s returning allowance_cents", (cents, player)).fetchone()
        else:
            row = conn.execute("update players set allowance_cents = %s where name = %s returning allowance_cents",
                               (cents, player)).fetchone()
    return row[0] if row else None


def cmd_topup(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    """Add to the player's shared allowance (every thread draws on it); without the site's
    database, raise one thread's cap as before."""
    state = load_state()
    cents = int(round(args.usd * 100))
    total = None if args.thread else set_allowance(args.player, cents, add=True)
    if total is not None:
        print(f"{args.player}: allowance now ${total / 100:.2f}, shared by all threads"
              " (the site gives it to the thread they write in)")
        return
    session_id = args.thread or latest_thread(state, args.player)
    s = client.beta.sessions.retrieve(session_id)
    spent = int(s.usage.list_cost.amount) if s.usage and s.usage.list_cost else 0
    new_cap = spent + cents
    client.beta.sessions.update(
        session_id, budget={"type": "limit", "max_list_cost": {"amount": str(new_cap), "currency": "USD"}})
    print(f"{session_id}: spent ${spent / 100:.2f}, cap now ${new_cap / 100:.2f}")


def api_key() -> str:
    """The service's key, from ANTHROPIC_API_KEY or service/.state/api_key.

    The key stays out of the shell profile so Claude Code keeps its own login.
    """
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key or "..." in key:
        sys.exit(f"No API key. Paste one into {KEY_FILE.relative_to(ROOT)} "
                 "(a single line, sk-ant-...) and rerun.")
    return key


def cmd_refresh(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    """Bring threads started on an older agent version up to date.

    A thread keeps the agent version it was created with. Its tools can be replaced while it is
    not running; its system prompt cannot, so the current instructions are queued as system
    context for the player's next message instead.
    """
    state = load_state()
    if not state.get("agent_id"):
        sys.exit("run `thread.py setup` first")
    agent = client.beta.agents.retrieve(state["agent_id"])
    system = SYSTEM.read_text(encoding="utf-8")
    for name, info in state["players"].items():
        if args.player and name != args.player:
            continue
        for t in info.get("threads", []):
            sid = t["session_id"]
            s = client.beta.sessions.retrieve(sid)
            have = t.get("agent_version") or getattr(s.agent, "version", 0)
            label = "thread" if in_ci() else f"{name} {sid}"
            if have >= agent.version:
                print(f"  {label}: up to date (version {have})")
                continue
            if s.status in ("running", "terminated"):
                print(f"  {label}: {s.status}, left for the next refresh")
                continue
            if not args.dry_run:
                # Vaults can only be attached when a thread starts (the API refuses vault_ids
                # updates), so a thread started before the vault has no live records API.
                client.beta.sessions.update(sid, agent={"tools": TOOLS})
                queue_intro(state, name, sid, instructions_update(agent.version, system))
                t["agent_version"] = agent.version
                save_state(state)
            no_api = "" if state.get("vault_id") in (getattr(s, "vault_ids", None) or []) else \
                "; no live records API (needs a new thread)"
            print(f"  {label}: version {have} -> {agent.version} (tools now, instructions with the next message{no_api})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="create or update the environment, shared files and agent")
    p = sub.add_parser("new", help="start a new thread for a player")
    p.add_argument("player")
    p.add_argument("--games", required=True, help="folder with the player's games and index.json")
    p.add_argument("--budget", type=float, default=DEFAULT_BUDGET_USD, help="spending cap in USD")
    p.add_argument("--email", help="the login email that opens this thread on the site")
    p = sub.add_parser("chat", help="talk in a player's thread (the latest one by default)")
    p.add_argument("player")
    p.add_argument("--thread", help="a specific session id")
    p = sub.add_parser("link", help="let a login email open this player's thread on the web page")
    p.add_argument("player")
    p.add_argument("email")
    sub.add_parser("db-sync", help="create the site's tables and copy every player into them")
    p = sub.add_parser("ranks", help="store every player's Mahjong Soul rank for the library")
    p.add_argument("--player", help="set one player's rank (with --account)")
    p.add_argument("--account", type=int, help="that player's Mahjong Soul account id")
    sub.add_parser("pending", help="paying players still waiting for their thread")
    p = sub.add_parser("onboard", help="fetch games and start a thread for every paying player waiting")
    p.add_argument("--dry-run", action="store_true", help="list who would be started and stop")
    p = sub.add_parser("comp", help="let a player use the tutor without paying")
    p.add_argument("player")
    p.add_argument("--off", action="store_true", help="require a subscription again")
    sub.add_parser("list", help="every thread with its status and spend")
    p = sub.add_parser("refresh", help="bring threads on an older agent version up to date")
    p.add_argument("player", nargs="?", help="only this player's threads")
    p.add_argument("--dry-run", action="store_true", help="list what would change and stop")
    p = sub.add_parser("topup", help="let a thread spend this many more USD")
    p.add_argument("player")
    p.add_argument("usd", type=float)
    p.add_argument("--thread", help="a specific session id")
    args = ap.parse_args()

    client = anthropic.Anthropic(api_key=api_key())
    {"setup": cmd_setup, "new": cmd_new, "chat": cmd_chat, "link": cmd_link, "db-sync": cmd_db_sync, "ranks": cmd_ranks, "pending": cmd_pending, "onboard": cmd_onboard, "comp": cmd_comp, "list": cmd_list,
     "refresh": cmd_refresh, "topup": cmd_topup}[args.cmd](client, args)


if __name__ == "__main__":
    main()
