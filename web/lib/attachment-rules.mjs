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
