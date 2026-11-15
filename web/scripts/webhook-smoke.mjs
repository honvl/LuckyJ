// Sends signed Stripe events to a running chat page and checks what the database records.
// Uses test rows only and removes them; the renewal check raises a thread's cap and puts it back.
//   node scripts/webhook-smoke.mjs [baseUrl] [renewSessionEmail]
// Needs STRIPE_WEBHOOK_SECRET and DATABASE_URL (read from .env.local) and the API key file.
import Anthropic from "@anthropic-ai/sdk";
import { neon } from "@neondatabase/serverless";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Stripe from "stripe";

const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split("\n").filter((l) => l.includes("=")).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const base = process.argv[2] || "http://localhost:3100";
const renewEmail = process.argv[3] || null;
const sql = neon(env.DATABASE_URL);
const stripe = new Stripe("sk_test_unused");
const EMAIL = "webhook-smoke@example.test";
const SUB = "sub_smoke_" + Date.now();
const ids = [];

async function send(type, object, id = `evt_smoke_${type}_${Date.now()}_${ids.length}`) {
  ids.push(id);
  const payload = JSON.stringify({ id, object: "event", type, data: { object }, api_version: "2026-10-28.endive", created: Math.floor(Date.now() / 1000) });
  const header = stripe.webhooks.generateTestHeaderString({ payload, secret: env.STRIPE_WEBHOOK_SECRET });
  const res = await fetch(`${base}/api/billing/webhook`, { method: "POST", body: payload, headers: { "stripe-signature": header, "content-type": "application/json" } });
  return { status: res.status, id };
}

const subscription = (status) => ({
  id: SUB, object: "subscription", customer: "cus_smoke", status,
  metadata: { email: EMAIL, platform: "majsoul", game_name: "SmokeTest", publish: "false" },
  items: { data: [{ current_period_end: 1800000000 }] },
});

try {
  // A forged signature is refused.
  const bad = await fetch(`${base}/api/billing/webhook`, { method: "POST", body: "{}", headers: { "stripe-signature": "t=1,v1=bad" } });
  assert.equal(bad.status, 400, "forged signature refused");

  assert.equal((await send("customer.subscription.created", subscription("active"))).status, 200);
  let [row] = await sql`select * from subscriptions where email = ${EMAIL}`;
  assert.equal(row.status, "active");
  assert.equal(row.game_name, "SmokeTest");
  assert.equal(row.publish, false);
  assert.equal(new Date(row.current_period_end).getTime(), 1800000000 * 1000);

  // The same event again is a no-op; a cancellation flips the status.
  const again = await send("customer.subscription.updated", subscription("past_due"));
  await send("customer.subscription.updated", subscription("canceled"), again.id);
  [row] = await sql`select status from subscriptions where email = ${EMAIL}`;
  assert.equal(row.status, "past_due", "a repeated event id is not applied twice");
  await send("customer.subscription.deleted", subscription("canceled"));
  [row] = await sql`select status from subscriptions where email = ${EMAIL}`;
  assert.equal(row.status, "canceled");

  // A renewal for a login without a thread changes nothing.
  assert.equal((await send("invoice.paid", { object: "invoice", billing_reason: "subscription_cycle", parent: { subscription_details: { subscription: SUB } } })).status, 200);
  console.log("subscription events: ok");

  if (renewEmail) {
    // A renewal raises the linked thread's cap to spent + allowance; the old cap is restored after.
    const anthropic = new Anthropic({ apiKey: readFileSync(new URL("../../service/.state/api_key", import.meta.url), "utf8").trim() });
    const [link] = await sql`select t.session_id from logins l join threads t on t.player = l.player where l.email = ${renewEmail} order by t.created_at desc limit 1`;
    const before = await anthropic.beta.sessions.retrieve(link.session_id);
    const oldCap = before.budget.max_list_cost.amount;
    const subId = SUB + "_renew";
    await sql`insert into subscriptions (email, subscription_id, status) values (${renewEmail}, ${subId}, 'active')`;
    try {
      assert.equal((await send("invoice.paid", { object: "invoice", billing_reason: "subscription_cycle", parent: { subscription_details: { subscription: subId } } })).status, 200);
      const after = await anthropic.beta.sessions.retrieve(link.session_id);
      const spent = Number(after.usage.list_cost.amount);
      assert.equal(Number(after.budget.max_list_cost.amount), spent + Number(env.MONTHLY_ALLOWANCE_CENTS || 1500));
      console.log(`renewal: cap ${oldCap} -> ${after.budget.max_list_cost.amount} (spent ${spent}): ok`);
    } finally {
      await anthropic.beta.sessions.update(link.session_id, { budget: { type: "limit", max_list_cost: { amount: oldCap, currency: "USD" } } });
      await sql`delete from subscriptions where subscription_id = ${subId}`;
      console.log(`renewal: cap restored to ${oldCap}`);
    }
  }
} finally {
  await sql`delete from subscriptions where email = ${EMAIL}`;
  await sql`delete from billing_events where event_id = any(${ids})`;
}
