import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { bookSlug, chapterKey, readChapter, spotList, untarGz } from "./books-rules.mjs";

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
  assert.equal(chapter.title, "Riichi rates"); // the number shows on its own
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

test("cards come as a list or wrapped the way the guide's spots.json is", () => {
  const card = { id: "a" };
  assert.deepEqual(spotList([card]), [card]);
  assert.deepEqual(spotList({ spots: [card] }), [card]);
  assert.equal(spotList({}), null);
  assert.equal(spotList(null), null);
});

import { chapterLead, chapterTopic, rankLabel } from "./books-rules.mjs";
import { parseGuide, plain } from "./guide-meta.mjs";

test("a chapter's topic line is read and taken out of the prose", () => {
  const md = "# Chapter 3: Fold sooner\nTopic: Push or fold\n\nYou fold late.";
  const { topic, markdown } = chapterTopic(md);
  assert.equal(topic, "Push or fold");
  assert.equal(markdown, "# Chapter 3: Fold sooner\n\nYou fold late.");
  assert.equal(chapterTopic("# A\n\nNo topic here.").topic, null);
  assert.equal(chapterTopic("# A\n*Topic: Calls*\n").topic, "Calls");
});

test("titles lose their chapter prefix; the topic is kept", () => {
  const files = { "3-fold/chapter.md": Buffer.from("# Chapter 3: Fold sooner\nTopic: Folds\n\nText.") };
  const ch = readChapter(files, "3-fold");
  assert.equal(ch.title, "Fold sooner");
  assert.equal(ch.topic, "Folds");
  assert.ok(!ch.markdown.includes("Topic:"));
});

test("the lead is the first prose paragraph, plain and clipped", () => {
  const md = "# Title\n\n![fig](a.png)\n\nYou keep [[2m]] **dama** [[game:260101-abc East 1-0 t9]] when LuckyJ declares.\n\n| a | b |";
  assert.equal(chapterLead(md), "You keep 2m dama when LuckyJ declares.");
  assert.ok(chapterLead("# T\n\n" + "word ".repeat(200), 50).endsWith("…"));
});

test("rank ids read as tiers and steps", () => {
  assert.deepEqual(rankLabel(10503), { tier: "Saint", label: "Saint 3" });
  assert.deepEqual(rankLabel(10401, "ja"), { tier: "Master", label: "雀豪1" });
  assert.deepEqual(rankLabel(10701), { tier: "Celestial", label: "Celestial Lv1" });
  assert.equal(rankLabel(null), null);
});

test("the static guide's chapters and news are read from its markup", () => {
  const html = `<nav class="x" id="chapters"><ol>
    <li><a href="#value"><span class="contents-num">01</span><span class="contents-title">Count the dora</span><span class="contents-sub">Value &#183; added 22 September</span></a></li>
    <li><a href="#d"><span class="contents-num">02</span><span class="contents-title">手の方針</span><span class="contents-sub">打点 &#183; 9月22日追加</span></a></li>
  </ol></nav><aside id="whats-new"><ol><li class="is-latest"><span class="guide-news-date">18 Nov</span><p><span class="new-tag">Latest</span> <a href="#draw">Chapter 52 looks</a> at &#8220;games&#8221;.</p></li></ol></aside>`;
  const g = parseGuide(html);
  assert.deepEqual(g.chapters[0], { n: 1, id: "value", title: "Count the dora", topic: "Value", date: "22 September" });
  assert.equal(g.chapters[1].date, "9月22日");
  assert.deepEqual(g.news[0], { date: "18 Nov", id: "draw", text: "Chapter 52 looks at “games”." });
  assert.equal(plain("a&amp;b"), "a&b");
});

import { readReplay } from "./books-rules.mjs";

test("a chapter's packed replays are read; anything else in replays/ is skipped", () => {
  const id = "260616-f8041361-c866-473e-9584-c10aa47a0686";
  const game = JSON.stringify({ id, date: "2026-06-16", hands: [] });
  const files = {
    "4-x/chapter.md": Buffer.from("# Chapter 4: X\n\nText."),
    [`4-x/replays/${id}.json`]: Buffer.from(game),
    "4-x/replays/index.json": Buffer.from("{}"),
    "4-x/replays/260101-00000000-0000-0000-0000-000000000000.json": Buffer.from("not json"),
  };
  const ch = readChapter(files, "4-x");
  assert.deepEqual(ch.replays.map((r) => [r.id, r.date]), [[id, "2026-06-16"]]);
  assert.deepEqual(ch.figures, []);
  assert.equal(readReplay(`${id}.json`, Buffer.from(JSON.stringify({ id: "other", hands: [] }))), null);
});
