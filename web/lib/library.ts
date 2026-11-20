// The Personal Guides library: the static guide (honver.html, read at build time into
// generated/honver-guide.json) and every guide the tutor wrote that its player keeps public.
import "server-only";
import guide from "./generated/honver-guide.json";
import { publicBooks, rankOf } from "./books";
import { rankLabel } from "./books-rules.mjs";
import type { Lang } from "./strings";

export type LibraryItem = {
  key: string;
  name: string;
  href: string;
  rank: string | null;
  tier: string | null;
  rankId: number | null;
  chapters: number;
  latest: string;
  date: string;
  time: number;
  topics: string[];
  /** Chapters per topic, so the library can offer the topics most chapters are about. */
  topicCounts: Record<string, number>;
};

function counts(topics: (string | null)[]): Record<string, number> {
  const out: Record<string, number> = {};
  for (const t of topics) if (t) out[t] = (out[t] || 0) + 1;
  return out;
}

function byCount(c: Record<string, number>): string[] {
  return Object.keys(c).sort((a, b) => c[b] - c[a] || a.localeCompare(b));
}

type GuideMeta = {
  chapters: { n: number; id: string | null; title: string; topic: string; date: string }[];
  news: { date: string; id: string | null; text: string }[];
};

export const STATIC_GUIDE_OWNER = "Honver";

export function staticGuide(lang: Lang): GuideMeta {
  return (guide as Record<Lang, GuideMeta>)[lang];
}

/** "18 November" (no year) as a time: this year, or last year if that would be in the future. */
function dayMonth(text: string): number {
  const now = new Date();
  const t = Date.parse(`${text} ${now.getUTCFullYear()} 12:00 UTC`);
  if (Number.isNaN(t)) return 0;
  return t > now.getTime() + 86400000 ? Date.parse(`${text} ${now.getUTCFullYear() - 1} 12:00 UTC`) : t;
}

export async function libraryItems(lang: Lang): Promise<LibraryItem[]> {
  const fmt = new Intl.DateTimeFormat(lang === "ja" ? "ja-JP" : "en-GB", { day: "numeric", month: "short", year: "numeric" });
  const en = staticGuide("en");
  const here = staticGuide(lang);
  const last = here.chapters[here.chapters.length - 1];
  const lastTime = dayMonth(en.chapters[en.chapters.length - 1]?.date || "");
  const ownerRank = await rankOf(STATIC_GUIDE_OWNER).catch(() => null);
  const ownerLabel = rankLabel(ownerRank, lang);
  const items: LibraryItem[] = [{
    key: "static-honver",
    name: STATIC_GUIDE_OWNER,
    href: lang === "ja" ? "/honver-ja.html" : "/honver.html",
    rank: ownerLabel?.label ?? null,
    tier: ownerLabel?.tier ?? null,
    rankId: ownerRank,
    chapters: here.chapters.length,
    latest: last?.title ?? "",
    date: lastTime ? fmt.format(new Date(lastTime)) : last?.date ?? "",
    time: lastTime,
    topics: byCount(counts(here.chapters.map((c) => c.topic))),
    topicCounts: counts(here.chapters.map((c) => c.topic)),
  }];
  for (const b of await publicBooks().catch(() => [])) {
    // The static guide's owner is listed once, by the guide above.
    if (b.player === STATIC_GUIDE_OWNER) continue;
    const label = rankLabel(b.rankId, lang);
    const time = Date.parse(b.updated);
    items.push({
      key: b.slug, name: b.name, href: `/books/${b.slug}`, rank: label?.label ?? null, tier: label?.tier ?? null,
      rankId: b.rankId, chapters: b.chapters, latest: b.latest, date: fmt.format(new Date(time)), time,
      topics: b.topics, topicCounts: Object.fromEntries(b.topics.map((t) => [t, 1])),
    });
  }
  return items.sort((a, b) => b.time - a.time);
}
