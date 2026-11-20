// Attachment rules, kept free of I/O so they can be tested (lib/attachments.ts uses them).
// How a file reaches the coach: an image or a document block it reads directly, or, for files too
// big to read in one go, a download its sandbox fetches.

const MB = 1_000_000;
/** Through the site itself (no R2): under Vercel's 4.5 MB request limit. */
export const MAX_VIA_SITE = 4 * MB;
/** Straight to R2. */
export const MAX_VIA_R2 = 100 * MB;
const MAX_IMAGE = 5 * MB; // the API's limit per image
const MAX_PDF = 32 * MB; // the API's limit per PDF document
const MAX_TEXT_IN_CONTEXT = 1 * MB; // larger text is for code, not for reading

const IMAGE = new Set(["image/jpeg", "image/png", "image/gif", "image/webp"]);
const TEXT = /\.(txt|csv|tsv|json|md|log|xml|html?)$/i;

/**
 * @param {string} name @param {string} mime @param {number} size @param {boolean} viaR2
 * @returns {{ kind: "image" | "document" | "download", mime: string } | { error: string }}
 */
export function planFor(name, mime, size, viaR2) {
  const max = viaR2 ? MAX_VIA_R2 : MAX_VIA_SITE;
  if (size > max) return { error: "file too large" };
  if (IMAGE.has(mime)) return size <= MAX_IMAGE ? { kind: "image", mime } : { error: "file too large" };
  const isText = mime.startsWith("text/") || mime === "application/json" || TEXT.test(name);
  if (mime === "application/pdf" && size <= MAX_PDF) return { kind: "document", mime };
  if (isText && size <= MAX_TEXT_IN_CONTEXT) return { kind: "document", mime: "text/plain" };
  if (viaR2) return { kind: "download", mime: mime || "application/octet-stream" };
  return { error: isText || mime === "application/pdf" ? "file too large" : "unsupported file type" };
}

/**
 * Caps that keep R2 inside Cloudflare's free tier (10 GB-month stored, 1 million uploads and 10
 * million reads a month). Files expire after a day (bucket lifecycle rule), so what is stored is
 * at most about two days of uploads.
 */
export const R2_LIMITS = {
  playerFilesPerDay: 50,
  playerBytesPerDay: 1_000 * MB,
  allBytesPerDay: 2_000 * MB, // two days of this stored stays well under 10 GB
  allFilesPerMonth: 100_000, // a tenth of the free uploads
};

/**
 * Whether one more upload of `size` bytes fits. `usage`: today's totals for the player and for
 * everyone, and this month's file count for everyone.
 * @param {{ playerFiles: number, playerBytes: number, allBytes: number, monthFiles: number }} usage
 * @param {number} size
 * @returns {string | null} the reason it does not fit, or null
 */
export function r2Quota(usage, size, limits = R2_LIMITS) {
  if (usage.playerFiles + 1 > limits.playerFilesPerDay) return "daily file limit";
  if (usage.playerBytes + size > limits.playerBytesPerDay) return "daily size limit";
  if (usage.allBytes + size > limits.allBytesPerDay || usage.monthFiles + 1 > limits.allFilesPerMonth) return "service upload limit";
  return null;
}
