import assert from "node:assert/strict";
import { test } from "node:test";
import { capAfterRenewal, hasAccess, invoiceSubscriptionId, isTutorSubscription, periodEnd, signupFields } from "./billing-rules.mjs";

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

test("sign-up fields", () => {
  assert.deepEqual(signupFields({ platform: "majsoul", gameName: "  Honver ", publish: false }), { platform: "majsoul", gameName: "Honver", publish: false });
  assert.deepEqual(signupFields({ platform: "tenhou", gameName: "ID12345" }), { platform: "tenhou", gameName: "ID12345", publish: true });
  assert.equal(signupFields({ platform: "riichi city", gameName: "x" }), null);
  assert.equal(signupFields({ platform: "majsoul", gameName: "  " }), null);
});
