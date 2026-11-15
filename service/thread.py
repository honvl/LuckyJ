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
import hashlib
import io
import json
import os
import re
import sys
import tarfile
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "service"
STATE = SERVICE / ".state" / "state.json"
KEY_FILE = SERVICE / ".state" / "api_key"  # one line, the key; gitignored with .state/
PLAYERS = SERVICE / "players"
SYSTEM = SERVICE / "agent" / "system.md"
SETUP_SH = SERVICE / "sandbox" / "setup.sh"
MORTAL_DIR = Path.home() / "Downloads" / "mortal_model_policy"
LUCKYJ_LOGS = ROOT / "data" / "local_sources" / "luckyj_tenhou"

MODEL = {"id": "claude-opus-5-5", "effort": "high"}
AGENT_NAME = "Mahjong coach"
ENV_NAME = "mahjong-coach"
MA_BETA = "managed-agents-2026-04-01"
DEFAULT_BUDGET_USD = 15

ENV_CONFIG = {
    "type": "cloud",
    "networking": {
        "type": "limited",
        # Package managers cover PyPI, crates.io and github.com (the site repo and Mortal).
        "allow_package_managers": True,
        # CPU-only torch wheels; PyPI's default torch pulls gigabytes of CUDA libraries.
        "allowed_hosts": ["download.pytorch.org", "download-r2.pytorch.org"],
    },
}

TOOLS = [{
    "type": "agent_toolset_20260401",
    "default_config": {"enabled": True, "permission_policy": {"type": "auto"}},
    "configs": [
        {"name": "web_fetch", "enabled": False},
        {"name": "web_search", "enabled": False},
    ],
}]


# ------------------------------------------------------------------ state

def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"shared_files": {}, "players": {}}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")


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
    with tarfile.open(fileobj=buf, mode="w:gz", compresslevel=6) as tar:
        for arcname, path in sorted(members):
            info = tar.gettarinfo(str(path), arcname)
            info.mtime, info.uid, info.gid, info.uname, info.gname = 0, 0, 0, "", ""
            with path.open("rb") as fh:
                tar.addfile(info, fh)
    return buf.getvalue()


def upload(client: anthropic.Anthropic, name: str, data: bytes) -> str:
    print(f"  uploading {name} ({len(data) / 1e6:.1f} MB)")
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

    print("agent")
    system = SYSTEM.read_text(encoding="utf-8")
    config_hash = sha256(json.dumps([MODEL, TOOLS, system], sort_keys=True).encode())
    if not state.get("agent_id"):
        agent = client.beta.agents.create(name=AGENT_NAME, model=MODEL, system=system, tools=TOOLS)
        state["agent_id"] = agent.id
    elif state.get("agent_hash") != config_hash:
        current = client.beta.agents.retrieve(state["agent_id"])
        agent = client.beta.agents.update(state["agent_id"], version=current.version,
                                          model=MODEL, system=system, tools=TOOLS)
    else:
        agent = client.beta.agents.retrieve(state["agent_id"])
    state["agent_hash"] = config_hash
    save_state(state)
    print(f"  {agent.id} version {agent.version}")
    print("New threads use this setup. Existing threads keep the files they started with.")


# ------------------------------------------------------------------ threads

def cmd_new(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    state = load_state()
    if not state.get("agent_id"):
        sys.exit("run `thread.py setup` first")
    games_dir = Path(args.games).resolve()
    if not (games_dir / "index.json").exists():
        sys.exit(f"{games_dir} has no index.json (the manifest fetch_majsoul_games.py writes)")
    games = sorted(games_dir.glob("*.json"))
    archive = tar_gz([(p.name, p) for p in games])
    print(f"{args.player}: {len(games) - 1} game files")

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
         "instructions": "This player's notes. Read them before you start; add to them as you go."},
    ]
    cents = int(round(args.budget * 100))
    session = client.beta.sessions.create(
        agent=state["agent_id"],
        environment_id=state["environment_id"],
        title=f"{args.player}, thread {len(player['threads']) + 1}",
        metadata={"player": args.player},
        budget={"type": "limit", "max_list_cost": {"amount": str(cents), "currency": "USD"}},
        resources=resources,
    )
    player["threads"].append({"session_id": session.id, "games_file_id": games_file,
                              "downloaded": []})
    save_state(state)
    print(f"thread {session.id} with a ${args.budget:.2f} cap")
    print(f"talk to it: .venv/bin/python service/thread.py chat {args.player}")


def short(value: object, limit: int = 140) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def run_turn(client: anthropic.Anthropic, session_id: str, text: str) -> str:
    """Send one message and print the thread's work until it waits for the player again."""
    last_cost = None
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        client.beta.sessions.events.send(
            session_id=session_id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": text}]}],
        )
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
    files = client.beta.files.list(scope_id=session_id, betas=[MA_BETA])
    for f in files:
        if f.id in done:
            continue
        rel = Path(*[p for p in Path(f.filename).parts if p not in ("", "/", "..")])
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        client.beta.files.download(f.id, betas=[MA_BETA]).write_to_file(target)
        done.add(f.id)
        print(f"  saved {target.relative_to(ROOT)}")
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
            run_turn(client, session_id, text)
        except anthropic.BadRequestError as e:
            print(f"  ! {e.message}")
            continue
        pull_outputs(client, state, args.player, session_id)


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


def cmd_topup(client: anthropic.Anthropic, args: argparse.Namespace) -> None:
    state = load_state()
    session_id = args.thread or latest_thread(state, args.player)
    s = client.beta.sessions.retrieve(session_id)
    spent = int(s.usage.list_cost.amount) if s.usage and s.usage.list_cost else 0
    new_cap = spent + int(round(args.usd * 100))
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="create or update the environment, shared files and agent")
    p = sub.add_parser("new", help="start a new thread for a player")
    p.add_argument("player")
    p.add_argument("--games", required=True, help="folder with the player's games and index.json")
    p.add_argument("--budget", type=float, default=DEFAULT_BUDGET_USD, help="spending cap in USD")
    p = sub.add_parser("chat", help="talk in a player's thread (the latest one by default)")
    p.add_argument("player")
    p.add_argument("--thread", help="a specific session id")
    sub.add_parser("list", help="every thread with its status and spend")
    p = sub.add_parser("topup", help="let a thread spend this many more USD")
    p.add_argument("player")
    p.add_argument("usd", type=float)
    p.add_argument("--thread", help="a specific session id")
    args = ap.parse_args()

    client = anthropic.Anthropic(api_key=api_key())
    {"setup": cmd_setup, "new": cmd_new, "chat": cmd_chat, "list": cmd_list,
     "topup": cmd_topup}[args.cmd](client, args)


if __name__ == "__main__":
    main()
