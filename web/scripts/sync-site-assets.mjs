// The hosted app serves the static site (../site: the playbook, the guide, the replays) from the
// same address as the chat, so the build copies it into public/. It also writes replays.json: the
// games that have a replay page, with the date the site shows for each (a game reference links to
// its replay only when one exists, and labels it with that date: the date in a Mahjong Soul id is
// often a day off).
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { parseGuide } from "../lib/guide-meta.mjs";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const site = join(web, "..", "site");
const pub = join(web, "public");

// Only files whose bytes differ are written, and only files gone from ../site are removed. The copy
// used to wipe and rewrite all of public/ on every start; `next dev` then reloaded every page a few
// times a second for as long as it ran (it stopped only when the server restarted without a sync).
function files(dir, base = dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? files(join(dir, e.name), base) : e.name === ".DS_Store" ? [] : [relative(base, join(dir, e.name))]);
}
function writeIfChanged(file, bytes) {
  if (existsSync(file) && statSync(file).size === bytes.length && readFileSync(file).equals(bytes)) return false;
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, bytes);
  return true;
}
const GENERATED = new Set(["replays.json"]);
mkdirSync(pub, { recursive: true });
const wanted = new Set(files(site));
let copied = 0;
for (const rel of wanted) copied += writeIfChanged(join(pub, rel), readFileSync(join(site, rel)));
let removed = 0;
for (const rel of files(pub)) {
  if (wanted.has(rel) || GENERATED.has(rel)) continue;
  rmSync(join(pub, rel));
  removed += 1;
}

const index = JSON.parse(readFileSync(join(site, "replays", "index.json"), "utf8"));
const dates = Object.fromEntries(index.games.map((g) => [g.id, g.date]));
writeIfChanged(join(pub, "replays.json"), Buffer.from(JSON.stringify(dates)));

// The static guide's chapters and news, for the library and the guide's card (lib/guide-meta.mjs).
const gen = join(web, "lib", "generated");
mkdirSync(gen, { recursive: true });
const guide = {
  en: parseGuide(readFileSync(join(site, "honver.html"), "utf8")),
  ja: parseGuide(readFileSync(join(site, "honver-ja.html"), "utf8")),
};
writeIfChanged(join(gen, "honver-guide.json"), Buffer.from(JSON.stringify(guide)));
console.log(`site synced into public/ (${copied} files written, ${removed} removed); ${index.games.length} games have replays; the guide has ${guide.en.chapters.length} chapters`);
