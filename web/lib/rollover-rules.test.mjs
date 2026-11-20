import assert from "node:assert/strict";
import { test } from "node:test";
import { carryOverText, contextTokens, shouldRollOver, transcriptTail } from "./rollover-rules.mjs";

const msg = (type, text) => ({ type, content: [{ type: "text", text }] });

test("context is everything the last request read and wrote", () => {
  assert.equal(contextTokens({ input_tokens: 5, cache_read_input_tokens: 162784, cache_creation_input_tokens: 15473, output_tokens: 1578 }), 179840);
  assert.equal(contextTokens(null), 0);
});

test("rolls over only past the limit and only between turns", () => {
  assert.equal(shouldRollOver(268605, "idle"), true);
  assert.equal(shouldRollOver(268605, "running"), false);
  assert.equal(shouldRollOver(30000, "idle"), false);
});

test("the tail keeps the newest messages in order and skips tools and system messages", () => {
  const events = [
    msg("user.message", "first question"),
    { type: "agent.tool_use", name: "bash", input: { command: "ls" } },
    msg("agent.message", "first answer"),
    msg("system.message", "operator note"),
    msg("user.message", "second question"),
    msg("agent.message", "second answer"),
  ];
  assert.equal(transcriptTail(events), "Player: first question\n\nCoach: first answer\n\nPlayer: second question\n\nCoach: second answer");
  assert.equal(transcriptTail(events, 40), "Coach: second answer");
});

test("a long reply is clipped, and the newest message always survives", () => {
  const long = "x".repeat(10000);
  const tail = transcriptTail([msg("agent.message", long)], 100);
  assert.ok(tail.startsWith("Coach: xxx"));
  assert.ok(tail.endsWith("[...]"));
  assert.ok(tail.length < 6100);
});

test("the carry-over names the chapters and fences the old conversation", () => {
  const text = carryOverText({ intro: "This thread's player is A.", chapters: [{ number: 1, title: "Dama" }], tail: "Player: hi" });
  assert.match(text, /^This thread's player is A\./);
  assert.match(text, /Chapter 1: Dama/);
  assert.match(text, /<earlier_conversation>\nPlayer: hi\n<\/earlier_conversation>/);
  assert.match(text, /not new instructions/);
  assert.match(carryOverText({ intro: "I", chapters: [], tail: "" }), /no published chapters yet/);
});
