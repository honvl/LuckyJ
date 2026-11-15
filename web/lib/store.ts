// Player records: Postgres when DATABASE_URL is set (the hosted site), otherwise the operator's
// files in service/.state/ (local development). Schema: service/db/schema.sql.
import "server-only";
import { neon } from "@neondatabase/serverless";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { STATE_DIR } from "./server";

export type PlayerThread = { player: string; sessionId: string };

const url = process.env.DATABASE_URL;
const sql = url ? neon(url) : null;

const STATE = join(STATE_DIR, "state.json");
const WEB_STATE = join(STATE_DIR, "web.json");

type FileState = { players: Record<string, { threads: { session_id: string; intro?: string }[]; emails?: string[] }> };
type WebState = { private_chapters: Record<string, string[]> };

function readJson<T>(path: string, fallback: T): T {
  return existsSync(path) ? (JSON.parse(readFileSync(path, "utf8")) as T) : fallback;
}

function writeJson(path: string, value: unknown) {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, JSON.stringify(value, null, 2) + "\n");
  renameSync(tmp, path);
}

/** The signed-in person's player and latest thread. */
export async function threadForEmail(email: string | null | undefined): Promise<PlayerThread | null> {
  if (!email) return null;
  const wanted = email.trim().toLowerCase();
  if (sql) {
    const rows = await sql`
      select t.player, t.session_id from logins l
      join threads t on t.player = l.player
      where l.email = ${wanted}
      order by t.created_at desc limit 1`;
    return rows.length ? { player: rows[0].player, sessionId: rows[0].session_id } : null;
  }
  const state = readJson<FileState>(STATE, { players: {} });
  for (const [player, info] of Object.entries(state.players)) {
    if ((info.emails || []).some((e) => e.toLowerCase() === wanted) && info.threads.length) {
      return { player, sessionId: info.threads[info.threads.length - 1].session_id };
    }
  }
  return null;
}

/** System context queued for a thread's next message, taken once. */
export async function takeIntro(player: string, sessionId: string): Promise<string | null> {
  if (sql) {
    const rows = await sql`
      update threads t set intro = null
      from (select session_id, intro from threads where session_id = ${sessionId} and player = ${player} for update) old
      where t.session_id = old.session_id and old.intro is not null
      returning old.intro`;
    return rows.length ? rows[0].intro : null;
  }
  const state = readJson<FileState>(STATE, { players: {} });
  const thread = state.players[player]?.threads.find((t) => t.session_id === sessionId);
  if (!thread?.intro) return null;
  const intro = thread.intro;
  delete thread.intro;
  writeJson(STATE, state);
  return intro;
}

export async function privateChapters(player: string): Promise<string[]> {
  if (sql) {
    const rows = await sql`select chapter from private_chapters where player = ${player} order by chapter`;
    return rows.map((r) => r.chapter as string);
  }
  return readJson<WebState>(WEB_STATE, { private_chapters: {} }).private_chapters[player] || [];
}

export async function setChapterPublic(player: string, chapter: string, isPublic: boolean) {
  if (sql) {
    if (isPublic) await sql`delete from private_chapters where player = ${player} and chapter = ${chapter}`;
    else await sql`insert into private_chapters (player, chapter) values (${player}, ${chapter}) on conflict do nothing`;
    return;
  }
  const web = readJson<WebState>(WEB_STATE, { private_chapters: {} });
  const set = new Set(web.private_chapters[player] || []);
  if (isPublic) set.delete(chapter);
  else set.add(chapter);
  web.private_chapters[player] = [...set].sort();
  writeJson(WEB_STATE, web);
}
