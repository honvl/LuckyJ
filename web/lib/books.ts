// Player books: chapters the coach packs are copied from Anthropic into the database, and the
// book pages read them from there. A chapter in private_chapters is never shown.
import "server-only";
import { neon } from "@neondatabase/serverless";
import { bookSlug, chapterKey, readChapter, spotList, untarGz } from "./books-rules.mjs";
import { MA_BETA, anthropic } from "./server";

const sql = process.env.DATABASE_URL ? neon(process.env.DATABASE_URL) : null;
export const booksEnabled = Boolean(sql);
const SYNC_EVERY_MS = 60_000;

export type BookChapter = {
  key: string;
  number: number;
  title: string;
  topic: string | null;
  addedAt: string;
  markdown: string;
  spots: any[] | null;
  figures: string[];
  isPublic: boolean;
  updatedAt: string;
};

export type Book = {
  player: string; name: string; slug: string; rankId: number | null; chapters: BookChapter[];
  /** Games with a replay on the site, by id, with the date the replay shows. */
  replays: Record<string, string>;
};

/** Titles stored before the prefix was dropped still read "Chapter 1: …"; the number shows on its own. */
function bareTitle(title: string): string {
  return String(title).replace(/^Chapter\s+\d+:\s*/i, "").replace(/^第\d+章[：:]\s*/, "");
}

/** The name a book is published under, and its URL name (set once, kept stable). */
async function ensureBookName(player: string): Promise<{ name: string; slug: string }> {
  const [row] = await sql!`select book_name, slug from players where name = ${player}`;
  const [prof] = await sql!`
    select pr.majsoul_name from profiles pr join logins l on l.email = pr.email
    where l.player = ${player} and pr.majsoul_name is not null order by pr.updated_at desc limit 1`;
  const name = prof?.majsoul_name || row?.book_name || player;
  if (row?.slug) {
    if (row.book_name !== name) await sql!`update players set book_name = ${name} where name = ${player}`;
    return { name, slug: row.slug };
  }
  const base = bookSlug(name);
  for (let i = 1; i < 50; i++) {
    const slug = i === 1 ? base : `${base}-${i}`;
    const taken = await sql!`select 1 from players where slug = ${slug} and name <> ${player}`;
    if (taken.length) continue;
    await sql!`update players set book_name = ${name}, slug = ${slug} where name = ${player}`;
    return { name, slug };
  }
  throw new Error(`no free book URL for ${player}`);
}

/** Whether a player's new chapters start public (their sign-up choice; free players: yes). */
async function publishByDefault(player: string): Promise<boolean> {
  const [prof] = await sql!`
    select pr.publish from profiles pr join logins l on l.email = pr.email
    where l.player = ${player} order by pr.updated_at desc limit 1`;
  return prof ? Boolean(prof.publish) : true;
}

/**
 * Copy chapter archives the coach wrote into the database. Checks each of the player's threads
 * at most once a minute unless forced. Returns the keys of chapters added or replaced.
 */
export async function syncChapters(player: string, force = false): Promise<string[]> {
  if (!sql) return [];
  const [p] = await sql`select synced_at from players where name = ${player}`;
  if (!p) return [];
  if (!force && p.synced_at && Date.now() - new Date(p.synced_at).getTime() < SYNC_EVERY_MS) return [];
  await sql`update players set synced_at = now() where name = ${player}`;
  await ensureBookName(player);

  const known = new Map<string, string>();
  for (const r of await sql`select key, source_file_id from chapters where player = ${player}`) known.set(r.key, r.source_file_id);
  const latest = new Map<string, { id: string; created: number }>();
  for (const t of await sql`select session_id from threads where player = ${player}`) {
    for await (const f of anthropic().beta.files.list({ scope_id: t.session_id, betas: [MA_BETA] } as any)) {
      const file = f as any;
      const key = chapterKey(file.filename);
      if (!key || !file.downloadable) continue;
      const created = new Date(file.created_at).getTime();
      if (!latest.has(key) || latest.get(key)!.created < created) latest.set(key, { id: file.id, created });
    }
  }

  const changed: string[] = [];
  const startPublic = await publishByDefault(player);
  for (const [key, { id }] of latest) {
    if (known.get(key) === id) continue;
    const res: any = await anthropic().beta.files.download(id, { betas: [MA_BETA] } as any);
    const chapter = readChapter(untarGz(new Uint8Array(await res.arrayBuffer())), key);
    if (!chapter) continue;
    await sql`
      insert into chapters (player, key, number, title, topic, markdown, spots, source_file_id)
      values (${player}, ${key}, ${chapter.number}, ${chapter.title}, ${chapter.topic}, ${chapter.markdown},
              ${chapter.spots ? JSON.stringify(chapter.spots) : null}, ${id})
      on conflict (player, key) do update set number = excluded.number, title = excluded.title,
        topic = excluded.topic, markdown = excluded.markdown, spots = excluded.spots,
        source_file_id = excluded.source_file_id, updated_at = now()`;
    await sql`delete from chapter_files where player = ${player} and key = ${key}`;
    await sql`delete from chapter_replays where player = ${player} and key = ${key}`;
    for (const r of chapter.replays) {
      await sql`insert into chapter_replays (player, key, game_id, date, data)
                values (${player}, ${key}, ${r.id}, ${r.date}, ${r.json})`;
    }
    for (const fig of chapter.figures) {
      await sql`insert into chapter_files (player, key, name, mime, data)
                values (${player}, ${key}, ${fig.name}, ${fig.mime}, ${fig.data.toString("base64")})`;
    }
    if (!known.has(key) && !startPublic) {
      await sql`insert into private_chapters (player, chapter) values (${player}, ${key}) on conflict do nothing`;
    }
    changed.push(key);
  }
  return changed;
}

async function chaptersOf(player: string, publicOnly: boolean): Promise<BookChapter[]> {
  const rows = await sql!`
    select c.key, c.number, c.title, c.topic, c.markdown, c.spots, c.created_at, c.updated_at,
           (pc.chapter is null) as is_public,
           coalesce((select array_agg(f.name order by f.name) from chapter_files f
                     where f.player = c.player and f.key = c.key), '{}') as figures
    from chapters c
    left join private_chapters pc on pc.player = c.player and pc.chapter = c.key
    where c.player = ${player}
    order by c.number, c.key`;
  const [p] = await sql!`select book_public from players where name = ${player}`;
  const bookPublic = p ? Boolean(p.book_public) : false;
  return rows
    .filter((r) => !publicOnly || (bookPublic && r.is_public))
    .map((r) => ({
      key: r.key, number: r.number, title: bareTitle(r.title), topic: r.topic ?? null,
      addedAt: new Date(r.created_at).toISOString(), markdown: r.markdown, spots: spotList(r.spots),
      figures: r.figures, isPublic: r.is_public, updatedAt: new Date(r.updated_at).toISOString(),
    }));
}

/** A player's own chapters, public and private (for their chat page). */
export async function ownChapters(player: string): Promise<{ slug: string | null; bookPublic: boolean; chapters: BookChapter[] }> {
  if (!sql) return { slug: null, bookPublic: false, chapters: [] };
  const [p] = await sql`select slug, book_public from players where name = ${player}`;
  return { slug: p?.slug ?? null, bookPublic: Boolean(p?.book_public), chapters: await chaptersOf(player, false) };
}

/** Turn a player's whole Personal Guide on or off the site. */
export async function setBookPublic(player: string, isPublic: boolean) {
  if (!sql) return;
  await sql`update players set book_public = ${isPublic} where name = ${player}`;
}

/** The public book at /books/<slug>, or null. */
export async function bookBySlug(slug: string): Promise<Book | null> {
  if (!sql) return null;
  const [p] = await sql`select name, book_name, slug, rank_id from players where slug = ${slug}`;
  if (!p) return null;
  await syncChapters(p.name).catch(() => []); // throttled; a failure leaves what is stored
  const chapters = await chaptersOf(p.name, true);
  if (!chapters.length) return null;
  const shown = new Set(chapters.map((c) => c.key));
  const replays: Record<string, string> = {};
  for (const r of await sql`select key, game_id, date from chapter_replays where player = ${p.name}`) {
    if (shown.has(r.key)) replays[r.game_id] = r.date || "";
  }
  return { player: p.name, name: p.book_name || p.name, slug: p.slug, rankId: p.rank_id ?? null, chapters, replays };
}

/** A replay a public chapter of a public book carries, as its JSON text, or null. */
export async function bookReplay(slug: string, game: string): Promise<string | null> {
  if (!sql) return null;
  const [row] = await sql`
    select r.data from chapter_replays r join players p on p.name = r.player
    left join private_chapters pc on pc.player = r.player and pc.chapter = r.key
    where p.slug = ${slug} and r.game_id = ${game} and pc.chapter is null and p.book_public
    limit 1`;
  return row ? (row.data as string) : null;
}

export type BookSummary = {
  player: string; name: string; slug: string; rankId: number | null; chapters: number; updated: string;
  latest: string; topics: string[];
};

/** Every book with at least one public chapter, newest first, for /books and the home page. */
export async function publicBooks(): Promise<BookSummary[]> {
  if (!sql) return [];
  const rows = await sql`
    select p.name, p.book_name, p.slug, p.rank_id, count(*)::int as chapters, max(c.updated_at) as updated,
           (array_agg(c.title order by c.number desc))[1] as latest,
           array_remove(array_agg(distinct c.topic), null) as topics
    from players p join chapters c on c.player = p.name
    left join private_chapters pc on pc.player = c.player and pc.chapter = c.key
    where pc.chapter is null and p.slug is not null and p.book_public
    group by p.name order by max(c.updated_at) desc`;
  return rows.map((r) => ({
    player: r.name, name: r.book_name || r.name, slug: r.slug, rankId: r.rank_id ?? null,
    chapters: r.chapters, updated: new Date(r.updated).toISOString(), latest: bareTitle(r.latest),
    topics: r.topics || [],
  }));
}

/** A player's rank id (the static guide's owner has no book row of their own to carry it). */
export async function rankOf(player: string): Promise<number | null> {
  if (!sql) return null;
  const [r] = await sql`select rank_id from players where name = ${player}`;
  return r?.rank_id ?? null;
}

/** A figure of a public chapter, or null. */
export async function figure(slug: string, key: string, name: string) {
  if (!sql) return null;
  const [row] = await sql`
    select f.mime, f.data from chapter_files f join players p on p.name = f.player
    left join private_chapters pc on pc.player = f.player and pc.chapter = f.key
    where p.slug = ${slug} and f.key = ${key} and f.name = ${name} and pc.chapter is null and p.book_public`;
  return row ? { mime: row.mime as string, data: Buffer.from(row.data, "base64") } : null;
}
