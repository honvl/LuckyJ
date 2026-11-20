// Subscriptions through Stripe Managed Payments (Stripe is merchant of record). Needs the database
// and STRIPE_SECRET_KEY, STRIPE_PRICE_ID, STRIPE_WEBHOOK_SECRET; without them the tutor runs
// without billing (local development: every linked login has access).
import "server-only";
import { neon } from "@neondatabase/serverless";
import Stripe from "stripe";
import { capAfterRenewal, hasAccess, invoiceSubscriptionId, isTutorSubscription, periodEnd } from "./billing-rules.mjs";
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
  current_period_end: string | null;
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

export async function checkoutUrl(email: string) {
  const base = env.NEXTAUTH_URL || "http://localhost:3100";
  const metadata = { email };
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

// The Stripe account also sells other products, and the portal's default settings are shared with
// them, so the tutor uses a portal configuration of its own (found by its metadata, created once):
// cancel at the end of the paid month, update the card, see invoices, and the tutor's own legal links.
let portalConfig: string | null = env.STRIPE_PORTAL_CONFIG || null;

async function tutorPortalConfig(base: string): Promise<string> {
  if (portalConfig) return portalConfig;
  for await (const c of stripe().billingPortal.configurations.list({ active: true, limit: 100 })) {
    if (c.metadata?.app === "luckyj-tutor") return (portalConfig = c.id);
  }
  const created = await stripe().billingPortal.configurations.create({
    name: "LuckyJ AI Mahjong Tutor",
    metadata: { app: "luckyj-tutor" },
    business_profile: {
      privacy_policy_url: `${base}/privacy.html`,
      terms_of_service_url: `${base}/terms.html`,
    },
    default_return_url: `${base}/account`,
    features: {
      invoice_history: { enabled: true },
      payment_method_update: { enabled: true },
      subscription_cancel: {
        enabled: true,
        mode: "at_period_end",
        cancellation_reason: { enabled: true, options: ["too_expensive", "missing_features", "unused", "other"] },
      },
    },
  });
  return (portalConfig = created.id);
}

export async function portalUrl(customerId: string) {
  const base = env.NEXTAUTH_URL || "http://localhost:3100";
  const configuration = await tutorPortalConfig(base);
  const session = await stripe().billingPortal.sessions.create({ customer: customerId, configuration, return_url: `${base}/account` });
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

async function upsertFromSubscription(sub: Stripe.Subscription, fallbackEmail?: string): Promise<boolean> {
  // Other products on the same Stripe account fire these events too.
  if (!isTutorSubscription(sub, env.STRIPE_PRICE_ID)) return false;
  const email = (sub.metadata?.email || fallbackEmail || "").toLowerCase();
  if (!email || !sql) return false;
  const end = periodEnd(sub);
  const customer = typeof sub.customer === "string" ? sub.customer : sub.customer?.id;
  await sql`
    insert into subscriptions (email, customer_id, subscription_id, status, current_period_end, majsoul_name, tenhou_name, publish, updated_at)
    values (${email}, ${customer}, ${sub.id}, ${sub.status}, ${end ? new Date(end * 1000) : null},
            ${sub.metadata?.majsoul_name || null}, ${sub.metadata?.tenhou_name || null}, ${sub.metadata?.publish !== "false"}, now())
    on conflict (email) do update set
      customer_id = excluded.customer_id, subscription_id = excluded.subscription_id, status = excluded.status,
      current_period_end = excluded.current_period_end,
      majsoul_name = coalesce(excluded.majsoul_name, subscriptions.majsoul_name),
      tenhou_name = coalesce(excluded.tenhou_name, subscriptions.tenhou_name),
      publish = excluded.publish, updated_at = now()`;
  return true;
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
        // Only the tutor's checkout sets metadata.email; client_reference_id alone may be another product's.
        const ours = session.metadata?.email ? await upsertFromSubscription(sub, session.metadata.email) : false;
        note = ours ? `subscribed ${sub.status}` : "another product's checkout";
      }
      break;
    }
    case "customer.subscription.created":
    case "customer.subscription.updated":
    case "customer.subscription.deleted": {
      const sub = event.data.object as Stripe.Subscription;
      note = (await upsertFromSubscription(sub)) ? `subscription ${sub.status}` : "another product's subscription";
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
