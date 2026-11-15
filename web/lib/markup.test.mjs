import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  TILE_GLYPHS, gameLabel, isNumericCell, parseGameRef, replayHref, splitError, splitMarkup, tileName,
} from "./markup.mjs";

const UUID = "260616-f8041361-1d2b-4c5e-9f00-123456789abc";

test("tile glyphs match the site's table", () => {
  const appJs = readFileSync(new URL("../../site/app.js", import.meta.url), "utf8");
  const block = appJs.match(/const tileCodes = \{([\s\S]*?)\};/)[1];
  const site = Object.fromEntries([...block.matchAll(/"?(\w+)"?: "(.)"/g)].map((m) => [m[1], m[2]]));
  assert.deepEqual(TILE_GLYPHS, site);
});

test("splits tiles and game references out of prose", () => {
  const parts = splitMarkup(`A [[2m]] kanchan, see [[game:${UUID} East 1-0 t9]]. [[nope]] stays.`);
  assert.deepEqual(parts, [
    "A ", { tiles: ["2m"] }, " kanchan, see ",
    { game: { uuid: UUID, round: "East 1-0", turn: 9, call: false } },
    ". [[nope]] stays.",
  ]);
  assert.deepEqual(splitMarkup("[[2m 3m 4m]]"), [{ tiles: ["2m", "3m", "4m"] }]);
});

test("game references need the full form", () => {
  assert.equal(parseGameRef("game:260616-f8041361"), null);
  assert.equal(parseGameRef(`game:${UUID}|East 1-0|9`), null);
  assert.deepEqual(parseGameRef(`game:${UUID} South 2-1 t12 call`), { uuid: UUID, round: "South 2-1", turn: 12, call: true });
});

test("labels and replay links", () => {
  const ref = parseGameRef(`game:${UUID} South 2-1 t12 call`);
  assert.equal(gameLabel(ref), "16 Jun · South 2-1 · turn 12, call");
  assert.equal(gameLabel(ref, "ja"), "6/16 南2局 1本場 12巡目（鳴き）");
  assert.equal(gameLabel(ref, "en", "2026-06-15 23:44"), "15 Jun · South 2-1 · turn 12, call");
  assert.equal(replayHref(ref), `/replay.html?g=${UUID}&r=South+2-1&t=12&at=call`);
  assert.equal(tileName("5pr", "ja"), "赤五筒");
  assert.equal(tileName("C"), "Red dragon");
});

test("table cells", () => {
  assert.deepEqual(splitError("72.6% ± 1.6"), { value: "72.6%", error: "± 1.6" });
  assert.equal(splitError("Riichi"), null);
  for (const cell of ["72.6% ± 1.6", "572 of 788", "572 of 788 = 72.6% ± 1.6", "-1,200", "2.9 SE", "87"]) {
    assert.ok(isNumericCell(cell), cell);
  }
  for (const cell of ["Riichi", "No riichi out yet", "1.1 SE, a maybe"]) assert.ok(!isNumericCell(cell), cell);
});
