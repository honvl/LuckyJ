// What the library and the home page need to know about the static Personal Guide (honver.html,
// honver-ja.html): its chapters and its newest updates, read from the page's own markup at build
// time (scripts/sync-site-assets.mjs), so a new chapter in the guide shows up without a second edit.

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " " };

/** Markup to plain text: tags dropped, entities decoded, spaces collapsed. */
export function plain(html) {
  return String(html)
    .replace(/<[^>]+>/g, " ")
    .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(Number(n)))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&([a-z]+);/gi, (m, name) => ENTITIES[name.toLowerCase()] ?? m)
    .replace(/\s+/g, " ")
    .trim();
}

function section(html, pattern) {
  const m = html.match(pattern);
  return m ? m[0] : "";
}

/**
 * The guide's chapters ({n, id, title, topic, date}) and What's new entries ({date, id, text}).
 * A contents-sub reads "Topic · added 22 September" (or "打点 · 9月22日追加").
 * @param {string} html
 */
export function parseGuide(html) {
  const nav = section(html, /<nav[^>]*id="chapters"[\s\S]*?<\/nav>/);
  const chapters = [];
  for (const li of nav.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/g)) {
    const href = li[1].match(/href="#([^"]+)"/)?.[1] ?? null;
    const num = plain(li[1].match(/class="contents-num">([\s\S]*?)<\/span>/)?.[1] ?? "");
    const title = plain(li[1].match(/class="contents-title">([\s\S]*?)<\/span>/)?.[1] ?? "");
    // The sub may hold a "New" tag of its own: read to the link's end, then drop the tag.
    const subHtml = li[1].match(/class="contents-sub">([\s\S]*?)<\/span>\s*<\/a>/)?.[1] ?? "";
    const sub = plain(subHtml.replace(/<span class="new-tag">[\s\S]*?<\/span>/g, ""));
    if (!num || !title) continue;
    const [topic, added] = sub.split(" · ");
    const date = (added || "").replace(/^added\s+/i, "").replace(/追加$/, "").trim();
    chapters.push({ n: Number(num), id: href, title, topic: topic || "", date });
  }
  const aside = section(html, /<aside[^>]*id="whats-new"[\s\S]*?<\/aside>/);
  const news = [];
  for (const li of aside.matchAll(/<li[^>]*>([\s\S]*?)<\/li>/g)) {
    const date = plain(li[1].match(/class="guide-news-date">([\s\S]*?)<\/span>/)?.[1] ?? "");
    const body = li[1].match(/<p>([\s\S]*?)<\/p>/)?.[1] ?? "";
    const id = body.match(/href="#([^"]+)"/)?.[1] ?? null;
    const text = plain(body.replace(/<span class="new-tag">[\s\S]*?<\/span>/, ""));
    if (date && text) news.push({ date, id, text });
  }
  return { chapters, news };
}
