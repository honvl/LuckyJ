// Puts a chapter archive into a player's book without the coach: for chapters built by hand, or
// to try the book pages. The archive is what the coach packs (chapter-<NN>-<slug>.tar.gz).
//   node scripts/import-chapter.mjs <player> <path/to/chapter-NN-slug.tar.gz> [--private]
//   node scripts/import-chapter.mjs <player> --remove <NN-slug>
import { neon } from "@neondatabase/serverless";
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { bookSlug, chapterKey, readChapter, untarGz } from "../lib/books-rules.mjs";

const env = Object.fromEntries(
  readFileSync(new URL("../.env.local", import.meta.url), "utf8")
    .split("\n").filter((l) => l.includes("=")).map((l) => [l.slice(0, l.indexOf("=")), l.slice(l.indexOf("=") + 1)]),
);
const sql = neon(process.env.DATABASE_URL || env.DATABASE_URL);
const [player, arg, flag] = process.argv.slice(2);
if (!player || !arg) {
  console.error("usage: import-chapter.mjs <player> <archive.tar.gz> [--private] | <player> --remove <key>");
  process.exit(2);
}
const [p] = await sql`select name, slug from players where name = ${player}`;
if (!p) throw new Error(`no player ${player}; run thread.py db-sync`);

if (arg === "--remove") {
  await sql`delete from chapters where player = ${player} and key = ${flag}`;
  await sql`delete from private_chapters where player = ${player} and chapter = ${flag}`;
  console.log(`removed ${flag} from ${player}'s book`);
  process.exit(0);
}

const key = chapterKey(basename(arg));
if (!key) throw new Error("the file must be named chapter-<NN>-<slug>.tar.gz");
const chapter = readChapter(untarGz(readFileSync(arg)), key);
if (!chapter) throw new Error(`no ${key}/chapter.md in the archive`);
if (!p.slug) await sql`update players set slug = ${bookSlug(player)}, book_name = coalesce(book_name, ${player}) where name = ${player}`;
await sql`
  insert into chapters (player, key, number, title, markdown, spots, source_file_id)
  values (${player}, ${key}, ${chapter.number}, ${chapter.title}, ${chapter.markdown},
          ${chapter.spots ? JSON.stringify(chapter.spots) : null}, ${"local:" + basename(arg)})
  on conflict (player, key) do update set number = excluded.number, title = excluded.title,
    markdown = excluded.markdown, spots = excluded.spots, source_file_id = excluded.source_file_id, updated_at = now()`;
await sql`delete from chapter_files where player = ${player} and key = ${key}`;
for (const fig of chapter.figures) {
  await sql`insert into chapter_files (player, key, name, mime, data) values (${player}, ${key}, ${fig.name}, ${fig.mime}, ${fig.data.toString("base64")})`;
}
if (flag === "--private") await sql`insert into private_chapters (player, chapter) values (${player}, ${key}) on conflict do nothing`;
const [{ slug }] = await sql`select slug from players where name = ${player}`;
console.log(`${key}: "${chapter.title}", ${chapter.spots?.length ?? 0} cards, ${chapter.figures.length} figures -> /books/${slug}`);
