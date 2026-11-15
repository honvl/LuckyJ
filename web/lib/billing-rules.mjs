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

/** The sign-up form's fields, cleaned; null when something required is missing. */
export function signupFields(body) {
  const platform = body?.platform === "tenhou" ? "tenhou" : body?.platform === "majsoul" ? "majsoul" : null;
  const gameName = typeof body?.gameName === "string" ? body.gameName.trim().slice(0, 64) : "";
  if (!platform || !gameName) return null;
  return { platform, gameName, publish: body?.publish !== false };
}
