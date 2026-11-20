// The hosted app serves the static site (../site: the playbook, the guide, the replays) from the
// same address as the chat, so the build copies it into public/. It also writes replays.json: the
// games that have a replay page, with the date the site shows for each (a game reference links to
// its replay only when one exists, and labels it with that date: the date in a Mahjong Soul id is
// often a day off).
import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseGuide } from "../lib/guide-meta.mjs";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const site = join(web, "..", "site");
const pub = join(web, "public");

rmSync(pub, { recursive: true, force: true });
mkdirSync(pub, { recursive: true });
cpSync(site, pub, { recursive: true, filter: (src) => !src.endsWith(".DS_Store") });

const index = JSON.parse(readFileSync(join(site, "replays", "index.json"), "utf8"));
const dates = Object.fromEntries(index.games.map((g) => [g.id, g.date]));
writeFileSync(join(pub, "replays.json"), JSON.stringify(dates));

// The static guide's chapters and news, for the library and the guide's card (lib/guide-meta.mjs).
const gen = join(web, "lib", "generated");
mkdirSync(gen, { recursive: true });
const guide = {
  en: parseGuide(readFileSync(join(site, "honver.html"), "utf8")),
  ja: parseGuide(readFileSync(join(site, "honver-ja.html"), "utf8")),
};
writeFileSync(join(gen, "honver-guide.json"), JSON.stringify(guide));
console.log(`site copied into public/; ${index.games.length} games have replays; the guide has ${guide.en.chapters.length} chapters`);
