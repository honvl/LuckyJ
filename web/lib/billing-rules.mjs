import { SERVERS, accountServer } from "./majsoul.mjs";
// Billing rules, kept free of I/O so they can be tested. Stripe API version 2026-10-28.endive:
// an invoice names its subscription under parent.subscription_details, and a subscription's
// period lives on its items.

/** Statuses that let a player use the tutor. past_due keeps access while Stripe retries the card. */
export const ACTIVE = new Set(["active", "trialing", "past_due"]);

/** @param {{ comp?: boolean, status?: string | null }} who */
export function hasAccess(who) {
  return Boolean(who.comp) || ACTIVE.has(String(who.status || ""));
}

/**
 * A player's new allowance at a renewal: what all their threads have spent so far plus one
 * month's allowance, so an unused allowance does not carry over and an overspent month does not
 * eat into the next.
 * @param {number} spentCents @param {number} allowanceCents
 */
export function capAfterRenewal(spentCents, allowanceCents) {
  return Math.ceil(spentCents) + allowanceCents;
}

/**
 * @typedef {{ id: string, spentCents: number, capCents: number | null, running: boolean }} ThreadSpend
 */

/**
 * A player's allowance before the database held one: what their threads' own caps added up to.
 * @param {ThreadSpend[]} threads
 */
export function initialAllowance(threads) {
  return threads.reduce((sum, t) => sum + (t.capCents ?? Math.ceil(t.spentCents)), 0);
}

/**
 * Spending caps for a message in one thread. All of a player's threads share one allowance:
 * an idle thread gives back what it has not spent (its cap drops to what it has spent plus one
 * cent, the lowest the API accepts), a running thread keeps its cap, and the thread the player is
 * writing in gets the rest. The caps never add up to more than the allowance.
 * @param {number} allowanceCents @param {ThreadSpend[]} threads @param {string} activeId
 * @returns {{ updates: { id: string, capCents: number }[], activeCap: number, canSend: boolean }}
 */
export function planCaps(allowanceCents, threads, activeId) {
  const updates = [];
  let held = 0;
  for (const t of threads) {
    if (t.id === activeId) continue;
    const floor = Math.ceil(t.spentCents) + 1;
    if (t.running) {
      held += Math.max(t.capCents ?? floor, floor);
      continue;
    }
    if (t.capCents == null || t.capCents > floor) updates.push({ id: t.id, capCents: floor });
    held += Math.max(Math.min(t.capCents ?? floor, floor), Math.ceil(t.spentCents));
  }
  const active = threads.find((t) => t.id === activeId);
  const activeCap = allowanceCents - held;
  const canSend = Boolean(active) && activeCap > Math.ceil(active.spentCents);
  if (canSend && active.capCents !== activeCap) updates.push({ id: activeId, capCents: activeCap });
  return { updates, activeCap, canSend };
}

/**
 * How much of this month's allowance is used, 0 to 100, for the page's bar. A top-up that leaves
 * more than a month's allowance shows as unused.
 * @param {number} allowanceCents @param {number} spentCents @param {number} monthlyCents
 */
export function usedPercent(allowanceCents, spentCents, monthlyCents) {
  const remaining = allowanceCents - spentCents;
  const base = Math.max(monthlyCents, remaining);
  if (base <= 0) return 100;
  return Math.min(100, Math.max(0, Math.round(100 * (1 - remaining / base))));
}

/** @param {any} invoice */
export function invoiceSubscriptionId(invoice) {
  const sub = invoice?.parent?.subscription_details?.subscription ?? invoice?.subscription ?? null;
  return typeof sub === "string" ? sub : sub?.id ?? null;
}

/** @param {any} subscription  Unix seconds of the current period's end, or null. */
export function periodEnd(subscription) {
  const ends = (subscription?.items?.data || []).map((i) => i.current_period_end).filter(Boolean);
  if (ends.length) return Math.max(...ends);
  return subscription?.current_period_end ?? null;
}

/**
 * Whether a subscription is for the tutor. The Stripe account sells other products too, and the
 * webhook hears every event on the account, so anything without the tutor's price is ignored.
 * @param {any} subscription @param {string | undefined} priceId
 */
export function isTutorSubscription(subscription, priceId) {
  if (!priceId) return false;
  return (subscription?.items?.data || []).some((item) => (item?.price?.id ?? item?.price) === priceId);
}

/**
 * The sign-up form's fields, cleaned: the player's Mahjong Soul server, their in-game name and
 * the account they picked from the exact-name matches on that server. Null when anything is
 * missing or the account is not on the chosen server.
 */
export function signupFields(body) {
  const server = SERVERS.includes(body?.majsoulServer) ? body.majsoulServer : null;
  const name = typeof body?.majsoulName === "string" ? body.majsoulName.trim().slice(0, 64) : "";
  const accountId = Number(body?.majsoulAccountId);
  if (!server || !name || !Number.isSafeInteger(accountId) || accountId <= 0) return null;
  if (accountServer(accountId) !== server) return null;
  return { majsoulServer: server, majsoulName: name, majsoulAccountId: accountId, publish: body?.publish !== false };
}
