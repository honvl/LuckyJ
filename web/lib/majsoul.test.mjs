import assert from "node:assert/strict";
import { test } from "node:test";
import { accountServer, exactMatches, rankName } from "./majsoul.mjs";

test("server from account id", () => {
  assert.equal(accountServer(120182062), "international"); // Honver
  assert.equal(accountServer(73864018), "japan");
  assert.equal(accountServer(11761727), "china");
  assert.equal(accountServer(0), null);
});

test("ranks", () => {
  assert.equal(rankName(10503), "Saint 3");
  assert.equal(rankName(10301, "ja"), "雀傑1");
  assert.equal(rankName(10701), "");
});

test("only exact names on the chosen server", () => {
  const search = [
    { id: 120182062, nickname: "Honver", level: { id: 10503 }, latest_timestamp: 5 },
    { id: 73864018, nickname: "Honver", level: { id: 10401 }, latest_timestamp: 9 }, // same name, Japan
    { id: 120000001, nickname: "Honver2", level: { id: 10301 }, latest_timestamp: 9 },
    { id: 120000002, nickname: "honver", level: { id: 10301 }, latest_timestamp: 9 },
  ];
  assert.deepEqual(exactMatches(search, " Honver ", "international").map((p) => p.id), [120182062]);
  assert.deepEqual(exactMatches(search, "Honver", "japan").map((p) => p.id), [73864018]);
  assert.deepEqual(exactMatches(search, "Honver", "china"), []);
});
