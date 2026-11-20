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
      try { spots = JSON.parse(data.toString("utf8")); } catch { spots = null; }
    } else {
      const ext = rel.split(".").pop().toLowerCase();
      if (IMAGE_TYPES[ext] && !rel.includes("/")) figures.push({ name: rel, mime: IMAGE_TYPES[ext], data });
    }
  }
  if (!markdown) return null;
  const heading = markdown.match(/^#\s+(.+)$/m);
  const number = Number(key.split("-")[0]);
  return { key, number, title: heading ? heading[1].trim() : key.replace(/^\d+-/, "").replace(/-/g, " "), markdown, spots, figures };
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
