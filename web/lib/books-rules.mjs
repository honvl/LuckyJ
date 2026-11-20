// Player books: archive reading and naming, kept free of I/O so they can be tested.
import { createHash } from "node:crypto";
import { gunzipSync } from "node:zlib";

const MAX_ARCHIVE = 20 * 1024 * 1024; // bytes, compressed
const MAX_FILE = 5 * 1024 * 1024;     // bytes, any one file inside

/**
 * The files in a .tar.gz, as {name: Buffer}. Reads POSIX ustar and GNU long names; skips
 * directories, links and anything over MAX_FILE. Names are kept as written ("01-x/chapter.md").
 * @param {Uint8Array} gz
 */
export function untarGz(gz) {
  if (gz.byteLength > MAX_ARCHIVE) throw new Error("archive too large");
  const tar = gunzipSync(gz, { maxOutputLength: 4 * MAX_ARCHIVE });
  /** @type {Record<string, Buffer>} */
  const files = {};
  let pos = 0;
  let longName = null;
  while (pos + 512 <= tar.length) {
    const header = tar.subarray(pos, pos + 512);
    if (header.every((b) => b === 0)) break;
    const field = (start, len) => header.subarray(start, start + len).toString("utf8").replace(/\0.*$/s, "");
    const size = parseInt(field(124, 12).trim() || "0", 8);
    const type = String.fromCharCode(header[156] || 48);
    const prefix = field(345, 155);
    let name = longName ?? (prefix ? `${prefix}/${field(0, 100)}` : field(0, 100));
    longName = null;
    const start = pos + 512;
    const data = tar.subarray(start, start + size);
    pos = start + Math.ceil(size / 512) * 512;
    if (type === "L") {
      longName = data.toString("utf8").replace(/\0.*$/s, "");
      continue;
    }
    if (type !== "0" && type !== "\0") continue; // directories, links, pax headers
    if (size > MAX_FILE) continue;
    name = name.replace(/^\.\//, "");
    if (name.split("/").some((part) => part === ".." || part === "")) continue;
    if (name.split("/").pop().startsWith("._")) continue; // macOS metadata files
    files[name] = Buffer.from(data);
  }
  return files;
}

const IMAGE_TYPES = { png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg", webp: "image/webp", svg: "image/svg+xml", gif: "image/gif" };

/**
 * A chapter archive's contents: chapter.md (required), spots.json and figures, from the files
 * under "<NN>-<slug>/". Null when there is no chapter.md.
 * @param {Record<string, Buffer>} files @param {string} key  e.g. "52-riichi-rates"
 */
/** A chapter's cards: spots.json is either a list or {"spots": [...]}, as the site's own guide writes it. */
export function spotList(value) {
  if (Array.isArray(value)) return value;
  if (value && Array.isArray(value.spots)) return value.spots;
  return null;
}

export function readChapter(files, key) {
  const inside = (name) => name.startsWith(`${key}/`) ? name.slice(key.length + 1) : null;
  let markdown = null;
  let spots = null;
  const figures = [];
  for (const [name, data] of Object.entries(files)) {
    const rel = inside(name);
    if (!rel) continue;
    if (rel === "chapter.md") markdown = data.toString("utf8");
    else if (rel === "spots.json") {
      try { spots = spotList(JSON.parse(data.toString("utf8"))); } catch { spots = null; }
    } else {
      const ext = rel.split(".").pop().toLowerCase();
      if (IMAGE_TYPES[ext] && !rel.includes("/")) figures.push({ name: rel, mime: IMAGE_TYPES[ext], data });
    }
  }
  if (!markdown) return null;
  const { topic, markdown: body } = chapterTopic(markdown);
  const heading = body.match(/^#\s+(.+)$/m);
  const number = Number(key.split("-")[0]);
  const title = heading ? heading[1].trim().replace(/^Chapter\s+\d+:\s*/i, "").replace(/^第\d+章[：:]\s*/, "") : key.replace(/^\d+-/, "").replace(/-/g, " ");
  return { key, number, title, topic, markdown: body, spots, figures };
}

/**
 * A chapter's topic: the coach writes "Topic: Riichi or dama" on its own line just under the
 * heading (service/agent/system.md). Returns it and the markdown without that line.
 * @param {string} markdown
 */
export function chapterTopic(markdown) {
  const lines = String(markdown).split("\n");
  const limit = Math.min(lines.length, 6);
  for (let i = 0; i < limit; i++) {
    const m = lines[i].match(/^\s*\*?(?:Topic|トピック)\s*[:：]\s*(.+?)\*?\s*$/i);
    if (m) {
      lines.splice(i, 1);
      return { topic: m[1].trim().slice(0, 40), markdown: lines.join("\n") };
    }
  }
  return { topic: null, markdown: String(markdown) };
}

/** The first paragraph of a chapter's prose, as plain text, for What's new (at most `limit` characters). */
export function chapterLead(markdown, limit = 320) {
  const blocks = String(markdown).split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const para = blocks.find((b) => !/^(#|!\[|\||[-*] |>|```|\d+\. )/.test(b)) || "";
  const text = para
    .replace(/\[\[game:[^\]]*\]\]/g, "")
    .replace(/\[\[([^\]]+)\]\]/g, "$1")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return text.length <= limit ? text : `${text.slice(0, limit).replace(/\s+\S*$/, "")}…`;
}

const TIERS = {
  1: { en: "Novice", ja: "初心" }, 2: { en: "Adept", ja: "雀士" }, 3: { en: "Expert", ja: "雀傑" },
  4: { en: "Master", ja: "雀豪" }, 5: { en: "Saint", ja: "雀聖" }, 6: { en: "Celestial", ja: "魂天" },
  7: { en: "Celestial", ja: "魂天" },
};

/**
 * A Mahjong Soul rank id (10xyz: x the tier, z the step) as words: {tier, label}, or null.
 * 10503 -> Saint 3 (雀聖3); 10701 -> Celestial Lv1 (魂天Lv1).
 * @param {number|null|undefined} id @param {"en"|"ja"} lang
 */
export function rankLabel(id, lang = "en") {
  const n = Number(id);
  if (!Number.isFinite(n) || n < 10000) return null;
  const tier = Math.floor(n / 100) % 10;
  const step = n % 100;
  const names = TIERS[tier];
  if (!names) return null;
  const celestial = tier >= 6;
  const label = celestial ? `${names[lang]} Lv${step}` : lang === "ja" ? `${names.ja}${step}` : `${names.en} ${step}`;
  return { tier: names.en, label };
}

/** "chapter-52-riichi-rates.tar.gz" -> "52-riichi-rates", else null. */
export function chapterKey(filename) {
  const m = String(filename).match(/^chapter-(\d+-[\w-]+)\.tar\.gz$/);
  return m ? m[1] : null;
}

/**
 * The URL name of a book: the name in lowercase ASCII words joined by "-", or, for names with no
 * ASCII letters or digits (小茸茸), "p-" and a short stable hash.
 * @param {string} name
 */
export function bookSlug(name) {
  const ascii = String(name).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
  if (ascii.length >= 2) return ascii;
  return "p-" + createHash("sha1").update(String(name)).digest("hex").slice(0, 8);
}
