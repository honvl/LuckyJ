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

/** One in-game name, trimmed to what the games allow; "" when absent. */
function cleanName(value) {
  return typeof value === "string" ? value.trim().slice(0, 64) : "";
}

/**
 * The sign-up form's fields, cleaned: one Mahjong Soul name and one Tenhou name, at least one of
 * them. Null when both are missing.
 */
export function signupFields(body) {
  const majsoulName = cleanName(body?.majsoulName);
  const tenhouName = cleanName(body?.tenhouName);
  if (!majsoulName && !tenhouName) return null;
  return { majsoulName, tenhouName, publish: body?.publish !== false };
}

/** The name a player's book is published under: their Mahjong Soul name, else their Tenhou name. */
export function bookName(fields) {
  return fields.majsoulName || fields.tenhouName || "";
}
