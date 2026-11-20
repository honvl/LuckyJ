import assert from "node:assert/strict";
import { test } from "node:test";
import { capAfterRenewal, hasAccess, initialAllowance, planCaps, usedPercent, invoiceSubscriptionId, isTutorSubscription, periodEnd, signupFields } from "./billing-rules.mjs";

test("access", () => {
  assert.equal(hasAccess({ comp: true }), true);
  assert.equal(hasAccess({ status: "active" }), true);
  assert.equal(hasAccess({ status: "past_due" }), true);
  assert.equal(hasAccess({ status: "canceled" }), false);
  assert.equal(hasAccess({ status: null }), false);
  assert.equal(hasAccess({}), false);
});

test("renewal cap is spent plus one allowance", () => {
  assert.equal(capAfterRenewal(1234, 1500), 2734);
  assert.equal(capAfterRenewal(1612, 1500), 3112); // overspent by one request: next month still gets 1500
  assert.equal(capAfterRenewal(0, 1500), 1500);
});

test("invoice and subscription shapes", () => {
  assert.equal(invoiceSubscriptionId({ parent: { subscription_details: { subscription: "sub_1" } } }), "sub_1");
  assert.equal(invoiceSubscriptionId({ parent: { subscription_details: { subscription: { id: "sub_2" } } } }), "sub_2");
  assert.equal(invoiceSubscriptionId({ subscription: "sub_3" }), "sub_3");
  assert.equal(invoiceSubscriptionId({}), null);
  assert.equal(periodEnd({ items: { data: [{ current_period_end: 100 }, { current_period_end: 200 }] } }), 200);
  assert.equal(periodEnd({ items: { data: [] } }), null);
});

test("only the tutor's price counts", () => {
  const tutor = { items: { data: [{ price: { id: "price_tutor" } }] } };
  const other = { items: { data: [{ price: { id: "price_lambent" } }] } };
  assert.equal(isTutorSubscription(tutor, "price_tutor"), true);
  assert.equal(isTutorSubscription(other, "price_tutor"), false);
  assert.equal(isTutorSubscription({ items: { data: [] } }, "price_tutor"), false);
  assert.equal(isTutorSubscription(tutor, undefined), false);
});

test("sign-up fields: a Mahjong Soul account picked on the player's server", () => {
  const ok = { majsoulServer: "international", majsoulName: " Honver ", majsoulAccountId: 120182062, publish: false };
  assert.deepEqual(signupFields(ok), { majsoulServer: "international", majsoulName: "Honver", majsoulAccountId: 120182062, publish: false });
  assert.equal(signupFields({ ...ok, majsoulServer: "japan" }), null, "account is not on that server");
  assert.equal(signupFields({ ...ok, majsoulServer: "mars" }), null);
  assert.equal(signupFields({ ...ok, majsoulName: " " }), null);
  assert.equal(signupFields({ ...ok, majsoulAccountId: "abc" }), null);
  assert.equal(signupFields({ ...ok, publish: undefined }).publish, true);
});

test("threads share one allowance", () => {
  const threads = [
    { id: "a", spentCents: 400.2, capCents: 1500, running: false },
    { id: "b", spentCents: 100, capCents: null, running: false },
    { id: "c", spentCents: 0, capCents: 1, running: false },
  ];
  const plan = planCaps(1500, threads, "c");
  // a and b give back their headroom; c gets the rest
  assert.deepEqual(plan.updates, [
    { id: "a", capCents: 402 },
    { id: "b", capCents: 101 },
    { id: "c", capCents: 1500 - 402 - 101 },
  ]);
  assert.equal(plan.canSend, true);
  const total = 402 + 101 + plan.activeCap;
  assert.ok(total <= 1500);
});

test("a running thread keeps its cap", () => {
  const plan = planCaps(1500, [
    { id: "a", spentCents: 300, capCents: 1000, running: true },
    { id: "b", spentCents: 0, capCents: 500, running: false },
  ], "b");
  assert.deepEqual(plan.updates, []);
  assert.equal(plan.activeCap, 500);
});

test("no allowance left blocks the message", () => {
  const plan = planCaps(1500, [
    { id: "a", spentCents: 1490, capCents: 1491, running: false },
    { id: "b", spentCents: 9, capCents: 9, running: false },
  ], "b");
  assert.equal(plan.canSend, false);
  assert.deepEqual(plan.updates, []); // never lower a cap to or below what was spent
});

test("allowance from old caps, and the bar", () => {
  assert.equal(initialAllowance([{ id: "a", spentCents: 120, capCents: 1500, running: false }, { id: "b", spentCents: 3.4, capCents: null, running: false }]), 1504);
  assert.equal(usedPercent(1500, 0, 1500), 0);
  assert.equal(usedPercent(1500, 750, 1500), 50);
  assert.equal(usedPercent(3000, 1600, 1500), 7); // renewed at 1,500 spent, 100 spent since: 7% of the month
  assert.equal(usedPercent(1500, 1600, 1500), 100);
  assert.equal(usedPercent(5000, 100, 1500), 0);
});
