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
 * A thread's new cap at a renewal: what it has spent so far plus one month's allowance, so an
 * unused allowance does not carry over and an overspent month does not eat into the next.
 * @param {number} spentCents @param {number} allowanceCents
 */
export function capAfterRenewal(spentCents, allowanceCents) {
  return Math.ceil(spentCents) + allowanceCents;
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
