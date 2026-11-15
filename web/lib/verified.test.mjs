import assert from "node:assert/strict";
import { test } from "node:test";
import { emailIsVerified } from "./verified.mjs";

test("only verified emails sign in", () => {
  assert.equal(emailIsVerified("google", { email: "a@b.c", email_verified: true }), true);
  assert.equal(emailIsVerified("google", { email: "a@b.c", email_verified: false }), false);
  assert.equal(emailIsVerified("google", { email: "a@b.c" }), false);
  assert.equal(emailIsVerified("discord", { email: "a@b.c", verified: true }), true);
  assert.equal(emailIsVerified("discord", { email: "a@b.c", verified: false }), false);
  assert.equal(emailIsVerified("discord", { email: null, verified: true }), false);
  assert.equal(emailIsVerified("line", { email: "a@b.c" }), false);
  assert.equal(emailIsVerified("google", undefined), false);
});
