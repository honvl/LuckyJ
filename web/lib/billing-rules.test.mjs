import assert from "node:assert/strict";
import { test } from "node:test";
import { bookName, capAfterRenewal, hasAccess, invoiceSubscriptionId, isTutorSubscription, periodEnd, signupFields } from "./billing-rules.mjs";

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

test("sign-up fields: one Mahjong Soul name and one Tenhou name, at least one", () => {
  assert.deepEqual(signupFields({ majsoulName: "  Honver ", tenhouName: "", publish: false }), { majsoulName: "Honver", tenhouName: "", publish: false });
  assert.deepEqual(signupFields({ tenhouName: "ID-Honver" }), { majsoulName: "", tenhouName: "ID-Honver", publish: true });
  assert.deepEqual(signupFields({ majsoulName: "A", tenhouName: "B" }), { majsoulName: "A", tenhouName: "B", publish: true });
  assert.equal(signupFields({ majsoulName: " ", tenhouName: "" }), null);
  assert.equal(signupFields({}), null);
  assert.equal(signupFields({ majsoulName: "x".repeat(100) }).majsoulName.length, 64);
  assert.equal(bookName({ majsoulName: "A", tenhouName: "B" }), "A");
  assert.equal(bookName({ majsoulName: "", tenhouName: "B" }), "B");
});
