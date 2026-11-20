import "server-only";
import { toChatEvent, type ChatEvent } from "./events";
import { anthropic } from "./server";
import { chainOf } from "./threads";

export async function threadSummary(sessionId: string) {
  const s: any = await anthropic().beta.sessions.retrieve(sessionId);
  const spent = Number(s.usage?.list_cost?.amount ?? 0);
  const cap = s.budget?.max_list_cost?.amount ? Number(s.budget.max_list_cost.amount) : null;
  return { status: s.status as string, spentCents: spent, capCents: cap };
}

async function sessionHistory(sessionId: string): Promise<ChatEvent[]> {
  const out: ChatEvent[] = [];
  for await (const ev of anthropic().beta.sessions.events.list(sessionId, { limit: 1000 } as any)) {
    const chat = toChatEvent(ev as any);
    if (chat) out.push(chat);
  }
  return out;
}

/** The thread's history: every session of its chain, oldest first, with a marker where a fresh
 * session took over (lib/rollover.ts). Status events of earlier sessions are left out. */
export async function threadHistory(player: string, sessionId: string): Promise<ChatEvent[]> {
  const chain = await chainOf(player, sessionId);
  const parts = await Promise.all(chain.map(sessionHistory));
  const out: ChatEvent[] = [];
  parts.forEach((events, i) => {
    if (i > 0) out.push({ id: `continued-${chain[i]}`, kind: "compacted" });
    const last = i === parts.length - 1;
    out.push(...(last ? events : events.filter((e) => e.kind !== "status" && e.kind !== "usage")));
  });
  return out;
}
