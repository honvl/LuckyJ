import "server-only";
import { toChatEvent, type ChatEvent } from "./events";
import { MA_BETA, anthropic } from "./server";
import { privateChapters } from "./store";

export type Chapter = { file: string; number: number; slug: string; isPublic: boolean };

export async function threadSummary(sessionId: string) {
  const s: any = await anthropic().beta.sessions.retrieve(sessionId);
  const spent = Number(s.usage?.list_cost?.amount ?? 0);
  const cap = s.budget?.max_list_cost?.amount ? Number(s.budget.max_list_cost.amount) : null;
  return { status: s.status as string, spentCents: spent, capCents: cap };
}

export async function threadHistory(sessionId: string): Promise<ChatEvent[]> {
  const out: ChatEvent[] = [];
  for await (const ev of anthropic().beta.sessions.events.list(sessionId, { limit: 1000 } as any)) {
    const chat = toChatEvent(ev as any);
    if (chat) out.push(chat);
  }
  return out;
}

/** Chapters the coach packed as chapter-<NN>-<slug>.tar.gz; the newest file of each name wins. */
export async function threadChapters(player: string, sessionId: string): Promise<Chapter[]> {
  const hidden = new Set(await privateChapters(player));
  const seen = new Map<string, Chapter>();
  for await (const f of anthropic().beta.files.list({ scope_id: sessionId, betas: [MA_BETA] } as any)) {
    const m = (f as any).filename.match(/^chapter-(\d+)-([\w-]+)\.tar\.gz$/);
    if (!m || !(f as any).downloadable) continue;
    const key = `${m[1]}-${m[2]}`;
    seen.set(key, { file: key, number: Number(m[1]), slug: m[2], isPublic: !hidden.has(key) });
  }
  return [...seen.values()].sort((a, b) => a.number - b.number);
}
