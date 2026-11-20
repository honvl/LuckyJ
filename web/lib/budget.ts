// One allowance per player, shared by all their threads (lib/billing-rules.mjs has the rules).
// Managed Agents caps spending per session, so before each message the caps are moved to where
// the player is writing. Without a database (local development) nothing is capped here.
import "server-only";
import { neon } from "@neondatabase/serverless";
import { capAfterRenewal, initialAllowance, planCaps, usedPercent } from "./billing-rules.mjs";
import { anthropic } from "./server";

const sql = process.env.DATABASE_URL ? neon(process.env.DATABASE_URL) : null;
export const ALLOWANCE_CENTS = Number(process.env.MONTHLY_ALLOWANCE_CENTS || 1500);

type Spend = { id: string; spentCents: number; capCents: number | null; running: boolean };

async function spends(player: string): Promise<Spend[]> {
  if (!sql) return [];
  const rows = await sql`select session_id from threads where player = ${player}`;
  return Promise.all(rows.map(async (r) => {
    const s: any = await anthropic().beta.sessions.retrieve(r.session_id);
    return {
      id: r.session_id as string,
      spentCents: Number(s.usage?.list_cost?.amount ?? 0),
      capCents: s.budget?.max_list_cost?.amount ? Number(s.budget.max_list_cost.amount) : null,
      running: s.status === "running",
    };
  }));
}

async function allowance(player: string, threads: Spend[]): Promise<number> {
  const [row] = await sql!`select allowance_cents from players where name = ${player}`;
  if (row?.allowance_cents != null) return Number(row.allowance_cents);
  const start = initialAllowance(threads);
  await sql!`update players set allowance_cents = ${start} where name = ${player} and allowance_cents is null`;
  return start;
}

async function setCap(id: string, cents: number) {
  await anthropic().beta.sessions.update(id, {
    budget: { type: "limit", max_list_cost: { amount: String(cents), currency: "USD" } },
  } as any);
}

/** Move the player's caps to the thread they are writing in. False when the allowance is used up. */
export async function prepareSend(player: string, sessionId: string): Promise<boolean> {
  if (!sql) return true;
  const threads = await spends(player);
  const plan = planCaps(await allowance(player, threads), threads, sessionId);
  if (!plan.canSend) return false;
  // Lower the others first, so the caps never add up to more than the allowance.
  const active = plan.updates.filter((u) => u.id === sessionId);
  for (const u of plan.updates.filter((x) => x.id !== sessionId)) await setCap(u.id, u.capCents);
  for (const u of active) await setCap(u.id, u.capCents);
  return true;
}

/** A new thread's starting cap: what the others are not holding (at least a cent). */
export async function allowanceCapForNewThread(player: string): Promise<number> {
  if (!sql) return ALLOWANCE_CENTS;
  const threads = await spends(player);
  const plan = planCaps(await allowance(player, threads), [...threads, { id: "new", spentCents: 0, capCents: null, running: false }], "new");
  for (const u of plan.updates.filter((x) => x.id !== "new")) await setCap(u.id, u.capCents);
  return Math.max(1, plan.activeCap);
}

/** How much of this month's allowance the player has used, 0 to 100 (null without a database). */
export async function usedThisMonth(player: string): Promise<number | null> {
  if (!sql) return null;
  const threads = await spends(player);
  const spent = threads.reduce((sum, t) => sum + t.spentCents, 0);
  return usedPercent(await allowance(player, threads), spent, ALLOWANCE_CENTS);
}

/** At a renewal: the allowance becomes everything spent so far plus one month. */
export async function renewAllowance(player: string): Promise<number> {
  const threads = await spends(player);
  const spent = threads.reduce((sum, t) => sum + t.spentCents, 0);
  const next = capAfterRenewal(spent, ALLOWANCE_CENTS);
  await sql!`update players set allowance_cents = ${next} where name = ${player}`;
  return next;
}
