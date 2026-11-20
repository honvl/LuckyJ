import assert from "node:assert/strict";
import { test } from "node:test";
import { R2_LIMITS, planFor, r2Quota } from "./attachment-rules.mjs";

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

test("R2 caps stay inside the free tier", () => {
  const none = { playerFiles: 0, playerBytes: 0, allBytes: 0, monthFiles: 0 };
  assert.equal(r2Quota(none, 50 * MB), null);
  assert.equal(r2Quota({ ...none, playerFiles: 50 }, 1), "daily file limit");
  assert.equal(r2Quota({ ...none, playerBytes: 990 * MB }, 20 * MB), "daily size limit");
  assert.equal(r2Quota({ ...none, allBytes: 1_990 * MB }, 20 * MB), "service upload limit");
  assert.equal(r2Quota({ ...none, monthFiles: 100_000 }, 1), "service upload limit");
  // Two days of the daily cap stored, and the monthly uploads, against the free tier.
  assert.ok((2 * R2_LIMITS.allBytesPerDay) / 1e9 <= 10);
  assert.ok(R2_LIMITS.allFilesPerMonth <= 1_000_000 / 5);
});
