// Subscriptions through Stripe Managed Payments (Stripe is merchant of record). Needs the database
// and STRIPE_SECRET_KEY, STRIPE_PRICE_ID, STRIPE_WEBHOOK_SECRET; without them the tutor runs
// without billing (local development: every linked login has access).
import "server-only";
import { neon } from "@neondatabase/serverless";
import Stripe from "stripe";
import { capAfterRenewal, hasAccess, invoiceSubscriptionId, periodEnd } from "./billing-rules.mjs";
import { anthropic } from "./server";
import { threadForEmail } from "./store";

const env = process.env;
const sql = env.DATABASE_URL ? neon(env.DATABASE_URL) : null;
export const billingEnabled = Boolean(sql && env.STRIPE_SECRET_KEY && env.STRIPE_PRICE_ID);
export const ALLOWANCE_CENTS = Number(env.MONTHLY_ALLOWANCE_CENTS || 1500);

let client: Stripe | null = null;
export function stripe(): Stripe {
  if (!env.STRIPE_SECRET_KEY) throw new Error("STRIPE_SECRET_KEY is not set");
  client ??= new Stripe(env.STRIPE_SECRET_KEY);
  return client;
}

export type Subscription = {
  email: string;
  customer_id: string | null;
  subscription_id: string | null;
  status: string;
  platform: string | null;
  game_name: string | null;
};

export type Access = {
  email: string;
  thread: { player: string; sessionId: string } | null;
  comp: boolean;
  subscription: Subscription | null;
  allowed: boolean;
};

/** Everything the page needs to know about a login: its thread, and whether it may use it. */
export async function accessFor(email: string): Promise<Access> {
  const wanted = email.trim().toLowerCase();
  const thread = await threadForEmail(wanted);
  if (!sql) return { email: wanted, thread, comp: true, subscription: null, allowed: Boolean(thread) };
  const [comp] = thread ? await sql`select comp from players where name = ${thread.player}` : [];
  // A player can have several logins; any of them paying gives the thread access.
  const subs = (await sql`
    select s.* from subscriptions s
    where s.email = ${wanted}
       or s.email in (select l2.email from logins l1 join logins l2 on l2.player = l1.player where l1.email = ${wanted})
    order by (s.status in ('active','trialing','past_due')) desc, s.updated_at desc`) as Subscription[];
  const subscription = subs[0] ?? null;
  const isComp = Boolean(comp?.comp);
  return {
    email: wanted,
    thread,
    comp: isComp,
    subscription,
    allowed: Boolean(thread) && hasAccess({ comp: isComp, status: subscription?.status }),
  };
}

export async function checkoutUrl(email: string, fields: { platform: string; gameName: string; publish: boolean }) {
  const base = env.NEXTAUTH_URL || "http://localhost:3100";
  const metadata = { email, platform: fields.platform, game_name: fields.gameName, publish: String(fields.publish) };
  const session = await stripe().checkout.sessions.create({
    mode: "subscription",
    line_items: [{ price: env.STRIPE_PRICE_ID!, quantity: 1 }],
    managed_payments: { enabled: true },
    customer_email: email,
    client_reference_id: email,
    metadata,
    subscription_data: { metadata },
    success_url: `${base}/chat?subscribed=1`,
    cancel_url: `${base}/chat`,
  } as Stripe.Checkout.SessionCreateParams);
  return session.url;
}

export async function portalUrl(customerId: string) {
  const base = env.NEXTAUTH_URL || "http://localhost:3100";
  const session = await stripe().billingPortal.sessions.create({ customer: customerId, return_url: `${base}/chat` });
  return session.url;
}

/** Raise a thread's cap to what it has spent plus one month's allowance. */
async function renewThreadCap(sessionId: string) {
  const s: any = await anthropic().beta.sessions.retrieve(sessionId);
  const spent = Number(s.usage?.list_cost?.amount ?? 0);
  const cap = capAfterRenewal(spent, ALLOWANCE_CENTS);
  await anthropic().beta.sessions.update(sessionId, {
    budget: { type: "limit", max_list_cost: { amount: String(cap), currency: "USD" } },
  } as any);
  return cap;
}

async function upsertFromSubscription(sub: Stripe.Subscription, fallbackEmail?: string) {
  const email = (sub.metadata?.email || fallbackEmail || "").toLowerCase();
  if (!email || !sql) return;
  const end = periodEnd(sub);
  const customer = typeof sub.customer === "string" ? sub.customer : sub.customer?.id;
  await sql`
    insert into subscriptions (email, customer_id, subscription_id, status, current_period_end, platform, game_name, publish, updated_at)
    values (${email}, ${customer}, ${sub.id}, ${sub.status}, ${end ? new Date(end * 1000) : null},
            ${sub.metadata?.platform || null}, ${sub.metadata?.game_name || null}, ${sub.metadata?.publish !== "false"}, now())
    on conflict (email) do update set
      customer_id = excluded.customer_id, subscription_id = excluded.subscription_id, status = excluded.status,
      current_period_end = excluded.current_period_end,
      platform = coalesce(excluded.platform, subscriptions.platform),
      game_name = coalesce(excluded.game_name, subscriptions.game_name),
      publish = excluded.publish, updated_at = now()`;
}

/** Handle one verified Stripe event. Returns a short note for the log. */
export async function handleEvent(event: Stripe.Event): Promise<string> {
  if (!sql) return "no database";
  const seen = await sql`select 1 from billing_events where event_id = ${event.id}`;
  if (seen.length) return "already handled";
  let note = "ignored";
  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      if (session.mode === "subscription" && session.subscription) {
        const subId = typeof session.subscription === "string" ? session.subscription : session.subscription.id;
        const sub = await stripe().subscriptions.retrieve(subId);
        await upsertFromSubscription(sub, session.metadata?.email || session.client_reference_id || undefined);
        note = `subscribed ${sub.status}`;
      }
      break;
    }
    case "customer.subscription.created":
    case "customer.subscription.updated":
    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;
      await upsertFromSubscription(sub);
      note = `subscription ${sub.status}`;
      break;
    }
    case "invoice.paid": {
      const invoice = event.data.object as Stripe.Invoice;
      const subId = invoiceSubscriptionId(invoice);
      // The first invoice is covered by the thread's starting cap (thread.py new); later ones renew it.
      if (subId && invoice.billing_reason === "subscription_cycle") {
        const [row] = await sql`select email from subscriptions where subscription_id = ${subId}`;
        const thread = row ? await threadForEmail(row.email) : null;
        note = thread ? `renewed cap to ${await renewThreadCap(thread.sessionId)}` : "renewal without a thread yet";
      }
      break;
    }
  }
  // Recorded only after success, so a failure is retried by Stripe.
  await sql`insert into billing_events (event_id, type) values (${event.id}, ${event.type}) on conflict do nothing`;
  return note;
}
