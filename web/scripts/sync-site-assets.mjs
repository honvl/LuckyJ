// Copies what the chat page borrows from the static site: the tile fonts, and the games that have
// a replay page with the date the site shows for each (a game reference links to its replay only
// when one exists, and labels it with that date: the date in a Mahjong Soul id is often a day off).
import { copyFileSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const web = join(dirname(fileURLToPath(import.meta.url)), "..");
const site = join(web, "..", "site");

mkdirSync(join(web, "public", "fonts"), { recursive: true });
for (const name of readdirSync(join(site, "fonts"))) {
  if (name.startsWith("GL-MahjongTile")) copyFileSync(join(site, "fonts", name), join(web, "public", "fonts", name));
}
const index = JSON.parse(readFileSync(join(site, "replays", "index.json"), "utf8"));
const dates = Object.fromEntries(index.games.map((g) => [g.id, g.date]));
writeFileSync(join(web, "public", "replays.json"), JSON.stringify(dates));
console.log(`tile fonts copied; ${index.games.length} games have replays`);
