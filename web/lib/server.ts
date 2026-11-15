// Server-only helpers: the API client, the operator's thread state, and per-player web settings.
// Locally these live in service/.state/ (gitignored), the same files service/thread.py uses.
// A hosted deployment needs a database instead; that comes with the billing step.
import "server-only";
import Anthropic from "@anthropic-ai/sdk";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const REPO = resolve(process.env.REPO_ROOT || join(process.cwd(), ".."));
const STATE_DIR = join(REPO, "service", ".state");
const STATE = join(STATE_DIR, "state.json");
const WEB_STATE = join(STATE_DIR, "web.json");
export const MA_BETA = "managed-agents-2026-04-01";

let client: Anthropic | null = null;

export function anthropic(): Anthropic {
  if (client) return client;
  let key = process.env.ANTHROPIC_API_KEY?.trim();
  const keyFile = join(STATE_DIR, "api_key");
  if (!key && existsSync(keyFile)) key = readFileSync(keyFile, "utf8").trim();
  if (!key) throw new Error("No API key: put it in service/.state/api_key");
  client = new Anthropic({ apiKey: key });
  return client;
}

type Thread = { session_id: string; intro?: string };
type Player = { threads: Thread[]; emails?: string[] };
type State = { players: Record<string, Player> };

function readJson<T>(path: string, fallback: T): T {
  return existsSync(path) ? (JSON.parse(readFileSync(path, "utf8")) as T) : fallback;
}

function writeJson(path: string, value: unknown) {
  const tmp = `${path}.tmp`;
  writeFileSync(tmp, JSON.stringify(value, null, 2) + "\n");
  renameSync(tmp, path);
}

export type PlayerThread = { player: string; sessionId: string };

/** The signed-in person's player and latest thread, from the emails `thread.py link` recorded. */
export function threadForEmail(email: string | null | undefined): PlayerThread | null {
  if (!email) return null;
  const state = readJson<State>(STATE, { players: {} });
  const wanted = email.trim().toLowerCase();
  for (const [player, info] of Object.entries(state.players)) {
    if ((info.emails || []).some((e) => e.toLowerCase() === wanted) && info.threads.length) {
      return { player, sessionId: info.threads[info.threads.length - 1].session_id };
    }
  }
  return null;
}

/** System context queued for a thread's next message (thread.py sets it), taken once. */
export function takeIntro(player: string, sessionId: string): string | null {
  const state = readJson<State>(STATE, { players: {} });
  const thread = state.players[player]?.threads.find((t) => t.session_id === sessionId);
  if (!thread?.intro) return null;
  const intro = thread.intro;
  delete thread.intro;
  writeJson(STATE, state);
  return intro;
}

type WebState = { private_chapters: Record<string, string[]> };

export function privateChapters(player: string): string[] {
  return readJson<WebState>(WEB_STATE, { private_chapters: {} }).private_chapters[player] || [];
}

export function setChapterPublic(player: string, chapter: string, isPublic: boolean) {
  const web = readJson<WebState>(WEB_STATE, { private_chapters: {} });
  const set = new Set(web.private_chapters[player] || []);
  if (isPublic) set.delete(chapter);
  else set.add(chapter);
  web.private_chapters[player] = [...set].sort();
  writeJson(WEB_STATE, web);
}
