// A player's chat threads, as in Claude Desktop: several per player, each its own coach session
// (sandbox, tools, data) sharing the player's notes and allowance. Threads started here reuse what
// the operator set up (service/thread.py): the agent, environment, shared files, the player's
// memory store and their newest games upload.
import { gamesFiles, gamesResources } from "./games-rules.mjs";
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
type OperatorPlayer = {
  memory_store_id?: string; hero_names?: string[]; threads: OperatorThread[]; emails?: string[];
  /** What the player has been given (service/thread.py): game ids and the archives that hold them. */
  games?: { uuids: string[]; archives: { file_id: string }[] };
};
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

/** A player's threads, newest first. A thread that went on in a fresh session (lib/rollover.ts)
 * is listed once, as its newest session. */
export async function listThreads(player: string): Promise<ThreadRow[]> {
  if (sql) {
    const rows = await sql`
      select session_id, title, created_at, archived from threads
      where player = ${player} and continued_by is null order by created_at desc`;
    return rows.map((r) => ({ id: r.session_id, title: r.title, createdAt: new Date(r.created_at).toISOString(), archived: r.archived }));
  }
  const threads = readLocal().players[player]?.threads || [];
  return threads
    .map((t, i) => ({ t, row: { id: t.session_id, title: (t.title as string) ?? null, createdAt: new Date(i * 1000).toISOString(), archived: Boolean(t.archived) } }))
    .filter(({ t }) => !t.continued_by)
    .map(({ row }) => row)
    .reverse();
}

type Link = { continues: string | null; continuedBy: string | null };

async function linkOf(player: string, id: string): Promise<Link | null> {
  if (sql) {
    const [r] = await sql`select continues, continued_by from threads where session_id = ${id} and player = ${player}`;
    return r ? { continues: r.continues ?? null, continuedBy: r.continued_by ?? null } : null;
  }
  const t = readLocal().players[player]?.threads.find((x) => x.session_id === id);
  return t ? { continues: (t.continues as string) ?? null, continuedBy: (t.continued_by as string) ?? null } : null;
}

/** The newest session of the chain `id` belongs to, or null when it is not the player's. */
async function newestOf(player: string, id: string): Promise<string | null> {
  let current = id;
  for (let hops = 0; hops < 100; hops++) {
    const link = await linkOf(player, current);
    if (!link) return null;
    if (!link.continuedBy) return current;
    current = link.continuedBy;
  }
  return current;
}

/** Every session of the thread that ends in `id`, oldest first. */
export async function chainOf(player: string, id: string): Promise<string[]> {
  const chain = [id];
  for (let hops = 0; hops < 100; hops++) {
    const link = await linkOf(player, chain[0]);
    if (!link?.continues) break;
    chain.unshift(link.continues);
  }
  return chain;
}

/** The thread a request asks for if it is the player's (its newest session), else their newest
 * open thread. */
export async function pickThread(player: string, wanted?: string | null): Promise<string | null> {
  if (wanted) {
    const newest = await newestOf(player, wanted);
    if (newest) return newest;
  }
  const threads = await listThreads(player);
  return (threads.find((t) => !t.archived) ?? threads[0])?.id ?? null;
}

export function introFor(player: string, names: string[]): string {
  // Same words as service/thread.py intro().
  const shown = names.join(", ") || "unknown";
  return (`This thread's player is ${player}. In their games they play as: ${shown} ` +
    "(the hero_name in index.json). These games are theirs; analyse them as theirs.");
}

/** The player's in-game names, for the intro. */
export async function heroNames(player: string): Promise<string[]> {
  const me = (await operatorState()).players[player];
  return me?.hero_names || [player];
}

type Continuation = { continues: string; intro: string; title: string | null };

/** Start a new coach thread for the player, set up like their newest one. Returns its id.
 * With `cont`, the new session carries on an existing thread (lib/rollover.ts). */
export async function createThread(player: string, cont?: Continuation): Promise<string> {
  const state = await operatorState();
  const me = state.players[player];
  if (!state.agent_id || !state.environment_id || !me?.memory_store_id) throw new Error("the operator has not set up this player");
  // Every games archive, the sign-up one and each top-up since (lib/games-rules.mjs).
  const archives = gamesFiles(me);
  if (!archives.length) throw new Error("no games upload for this player");
  const resources: any[] = Object.entries(state.shared_files || {})
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([mount, f]) => ({ type: "file", file_id: f.file_id, mount_path: mount }));
  resources.push(
    ...gamesResources(me),
    {
      type: "memory_store", memory_store_id: me.memory_store_id, access: "read_write",
      instructions: "This player's notes. Read index.md and player.md first; keep the notes current (see Keeping notes).",
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
  const intro = cont?.intro ?? introFor(player, me.hero_names || [player]);
  // games_archives: the top-up archives this thread started with, so thread.py games adds only later ones.
  const record: OperatorThread = { session_id: session.id, games_file_id: archives[0], games_archives: archives.slice(1), downloaded: [], from_site: true };
  if (cont) record.continues = cont.continues;
  if (sql) {
    await sql`
      insert into threads (session_id, player, intro, title, continues)
      values (${session.id}, ${player}, ${intro}, ${cont?.title ?? null}, ${cont?.continues ?? null})`;
    if (cont) await sql`update threads set continued_by = ${session.id} where session_id = ${cont.continues} and player = ${player}`;
    // The operator's records keep every thread too (thread.py refresh, list and chapter copies).
    await sql`
      update service_state set value = jsonb_set(value, array['players', ${player}, 'threads'],
        coalesce(value #> array['players', ${player}, 'threads'], '[]'::jsonb) || ${JSON.stringify([record])}::jsonb),
        updated_at = now()
      where key = 'operator'`;
  } else {
    const local = readLocal();
    local.players[player].threads.push({ ...record, intro, title: cont?.title ?? undefined });
    if (cont) {
      const old = local.players[player].threads.find((t) => t.session_id === cont.continues);
      if (old) old.continued_by = session.id;
    }
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
