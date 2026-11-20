import "server-only";
import { toChatEvent, type ChatEvent } from "./events";
import { anthropic } from "./server";

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
