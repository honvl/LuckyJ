import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { bookSlug, chapterKey, readChapter, untarGz } from "./books-rules.mjs";

function archive(files, key) {
  const dir = mkdtempSync(join(tmpdir(), "chapter-"));
  mkdirSync(join(dir, key));
  for (const [name, body] of Object.entries(files)) writeFileSync(join(dir, key, name), body);
  const out = join(dir, "out.tar.gz");
  execFileSync("tar", ["czf", out, "-C", dir, key]); // the same command the coach runs
  return readFileSync(out);
}

test("reads a chapter archive the way the coach packs it", () => {
  const key = "52-riichi-rates";
  const gz = archive({
    "chapter.md": "# Chapter 52: Riichi rates\n\nYou declare [[5m]] less.\n",
    "spots.json": JSON.stringify([{ id: "a", title: "One hand" }]),
    "fig-rates.png": Buffer.from([0x89, 0x50, 0x4e, 0x47]),
    "notes.txt": "not a figure",
  }, key);
  const chapter = readChapter(untarGz(gz), key);
  assert.equal(chapter.number, 52);
  assert.equal(chapter.title, "Chapter 52: Riichi rates");
  assert.match(chapter.markdown, /\[\[5m\]\]/);
  assert.deepEqual(chapter.spots, [{ id: "a", title: "One hand" }]);
  assert.deepEqual(chapter.figures.map((f) => [f.name, f.mime]), [["fig-rates.png", "image/png"]]);
});

test("a long file name survives (GNU long-name header)", () => {
  const key = "7-" + "x".repeat(120);
  const files = untarGz(archive({ "chapter.md": "# T\n" }, key));
  assert.ok(Object.keys(files).includes(`${key}/chapter.md`));
});

test("no chapter.md means no chapter", () => {
  assert.equal(readChapter(untarGz(archive({ "spots.json": "[]" }, "3-a")), "3-a"), null);
});

test("names", () => {
  assert.equal(chapterKey("chapter-52-riichi-rates.tar.gz"), "52-riichi-rates");
  assert.equal(chapterKey("analysis-02-x.json"), null);
  assert.equal(bookSlug("Honver"), "honver");
  assert.equal(bookSlug("Ms. Mahjong 2026"), "ms-mahjong-2026");
  assert.match(bookSlug("小茸茸"), /^p-[0-9a-f]{8}$/);
  assert.equal(bookSlug("小茸茸"), bookSlug("小茸茸"));
  assert.notEqual(bookSlug("小茸茸"), bookSlug("阿噗噜派丶"));
});
