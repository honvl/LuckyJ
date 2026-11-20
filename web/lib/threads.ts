// A player's chat threads, as in Claude Desktop: several per player, each its own coach session
// (sandbox, tools, data) sharing the player's notes and allowance. Threads started here reuse what
// the operator set up (service/thread.py): the agent, environment, shared files, the player's
// memory store and their newest games upload.
import "server-only";
import { neon } from "@neondatabase/serverless";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { anthropic, STATE_DIR } from "./server";
import { allowanceCapForNewThread } from "./budget";

const url = process.env.DATABASE_URL;
const sql = url ? neon(url) : null;
const STATE = join(STATE_DIR, "state.json");

export type ThreadRow = { id: string; title: string | null; createdAt: string; archived: boolean };

type OperatorThread = { session_id: string; games_file_id?: string; intro?: string; [k: string]: unknown };
type OperatorPlayer = { memory_store_id?: string; hero_names?: string[]; threads: OperatorThread[]; emails?: string[] };
type OperatorState = {
  agent_id?: string;
  environment_id?: string;
  vault_id?: string;
  shared_files?: Record<string, { file_id: string }>;
  players: Record<string, OperatorPlayer>;
};

function readLocal(): OperatorState {
  return existsSync(STATE) ? JSON.parse(readFileSync(STATE, "utf8")) : { players: {} };
}

function writeLocal(state: OperatorState) {
  const tmp = `${STATE}.tmp`;
  writeFileSync(tmp, JSON.stringify(state, null, 1) + "\n");
  renameSync(tmp, STATE);
}

async function operatorState(): Promise<OperatorState> {
  if (!sql) return readLocal();
  const [row] = await sql`select value from service_state where key = 'operator'`;
  return (row?.value as OperatorState) ?? { players: {} };
}

/** The player a login belongs to, or null. */
export async function playerForEmail(email: string | null | undefined): Promise<string | null> {
  if (!email) return null;
  const wanted = email.trim().toLowerCase();
  if (sql) {
    const [row] = await sql`select player from logins where email = ${wanted}`;
    return row?.player ?? null;
  }
  for (const [player, info] of Object.entries(readLocal().players)) {
    if ((info.emails || []).some((e) => e.toLowerCase() === wanted)) return player;
  }
  return null;
}

/** A player's threads, newest first. */
export async function listThreads(player: string): Promise<ThreadRow[]> {
  if (sql) {
    const rows = await sql`
      select session_id, title, created_at, archived from threads
      where player = ${player} order by created_at desc`;
    return rows.map((r) => ({ id: r.session_id, title: r.title, createdAt: new Date(r.created_at).toISOString(), archived: r.archived }));
  }
  const threads = readLocal().players[player]?.threads || [];
  return threads
    .map((t, i) => ({ id: t.session_id, title: (t.title as string) ?? null, createdAt: new Date(i * 1000).toISOString(), archived: Boolean(t.archived) }))
    .reverse();
}

/** The thread a request asks for if it is the player's, else their newest open thread. */
export async function pickThread(player: string, wanted?: string | null): Promise<string | null> {
  const threads = await listThreads(player);
  if (wanted && threads.some((t) => t.id === wanted)) return wanted;
  return (threads.find((t) => !t.archived) ?? threads[0])?.id ?? null;
}

function introFor(player: string, names: string[]): string {
  // Same words as service/thread.py intro().
  const shown = names.join(", ") || "unknown";
  return (`This thread's player is ${player}. In their games they play as: ${shown} ` +
    "(the hero_name in index.json). These games are theirs; analyse them as theirs.");
}

/** Start a new coach thread for the player, set up like their newest one. Returns its id. */
export async function createThread(player: string): Promise<string> {
  const state = await operatorState();
  const me = state.players[player];
  if (!state.agent_id || !state.environment_id || !me?.memory_store_id) throw new Error("the operator has not set up this player");
  const games = [...me.threads].reverse().find((t) => t.games_file_id)?.games_file_id;
  if (!games) throw new Error("no games upload for this player");
  const resources: any[] = Object.entries(state.shared_files || {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([mount, f]) => ({ type: "file", file_id: f.file_id, mount_path: mount }));
  resources.push(
    { type: "file", file_id: games, mount_path: "/player/games.tar.gz" },
    {
      type: "memory_store", memory_store_id: me.memory_store_id, access: "read_write",
      instructions: "This player's notes. Read them before you start; add to them as you go.",
    },
  );
  const cap = await allowanceCapForNewThread(player);
  const session: any = await anthropic().beta.sessions.create({
    agent: state.agent_id,
    environment_id: state.environment_id,
    title: `${player}, thread ${me.threads.length + 1}`,
    metadata: { player },
    budget: { type: "limit", max_list_cost: { amount: String(cap), currency: "USD" } },
    resources,
    vault_ids: state.vault_id ? [state.vault_id] : [],
  } as any);
  const intro = introFor(player, me.hero_names || [player]);
  const record: OperatorThread = { session_id: session.id, games_file_id: games, downloaded: [], from_site: true };
  if (sql) {
    await sql`insert into threads (session_id, player, intro) values (${session.id}, ${player}, ${intro})`;
    // The operator's records keep every thread too (thread.py refresh, list and chapter copies).
    await sql`
      update service_state set value = jsonb_set(value, array['players', ${player}, 'threads'],
        coalesce(value #> array['players', ${player}, 'threads'], '[]'::jsonb) || ${JSON.stringify([record])}::jsonb),
        updated_at = now()
      where key = 'operator'`;
  } else {
    const local = readLocal();
    local.players[player].threads.push({ ...record, intro });
    writeLocal(local);
  }
  return session.id;
}

/** Rename or archive one of the player's threads. */
export async function updateThread(player: string, id: string, change: { title?: string; archived?: boolean }) {
  const title = change.title?.trim().slice(0, 80);
  if (sql) {
    if (title !== undefined) await sql`update threads set title = ${title || null} where session_id = ${id} and player = ${player}`;
    if (change.archived !== undefined) await sql`update threads set archived = ${change.archived} where session_id = ${id} and player = ${player}`;
    return;
  }
  const local = readLocal();
  const t = local.players[player]?.threads.find((x) => x.session_id === id);
  if (!t) return;
  if (title !== undefined) t.title = title || null;
  if (change.archived !== undefined) t.archived = change.archived;
  writeLocal(local);
}

/** Name a thread after its first message, the way Claude Desktop does, unless it has a name. */
export async function titleFromFirstMessage(player: string, id: string, text: string) {
  const title = text.replace(/\s+/g, " ").trim().slice(0, 60);
  if (!title) return;
  if (sql) {
    await sql`update threads set title = ${title} where session_id = ${id} and player = ${player} and title is null`;
    return;
  }
  const local = readLocal();
  const t = local.players[player]?.threads.find((x) => x.session_id === id);
  if (t && !t.title) {
    t.title = title;
    writeLocal(local);
  }
}
