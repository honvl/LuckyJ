import assert from "node:assert/strict";
import { test } from "node:test";
import { planFor } from "./attachment-rules.mjs";

const MB = 1_000_000;

test("images and PDFs the model reads directly", () => {
  assert.deepEqual(planFor("hand.jpg", "image/jpeg", 0.4 * MB, true), { kind: "image", mime: "image/jpeg" });
  assert.deepEqual(planFor("big.png", "image/png", 6 * MB, true), { error: "file too large" });
  assert.deepEqual(planFor("book.pdf", "application/pdf", 20 * MB, true), { kind: "document", mime: "application/pdf" });
});

test("text: small files are read, big ones become downloads", () => {
  assert.deepEqual(planFor("log.csv", "text/csv", 0.3 * MB, true), { kind: "document", mime: "text/plain" });
  assert.deepEqual(planFor("games.json", "", 0.3 * MB, true), { kind: "document", mime: "text/plain" });
  assert.equal(planFor("all-games.csv", "text/csv", 40 * MB, true).kind, "download");
  assert.equal(planFor("logs.zip", "application/zip", 60 * MB, true).kind, "download");
  assert.equal(planFor("huge.pdf", "application/pdf", 50 * MB, true).kind, "download");
});

test("limits", () => {
  assert.deepEqual(planFor("x.zip", "application/zip", 101 * MB, true), { error: "file too large" });
  // Without R2 everything goes through the site: 4 MB, and no downloads.
  assert.deepEqual(planFor("x.pdf", "application/pdf", 5 * MB, false), { error: "file too large" });
  assert.deepEqual(planFor("x.zip", "application/zip", 1 * MB, false), { error: "unsupported file type" });
  assert.deepEqual(planFor("log.csv", "text/csv", 2 * MB, false), { error: "file too large" });
});
