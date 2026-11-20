// Cloudflare R2 for attachments: the browser uploads straight to the bucket with a short-lived
// signed URL, so files skip Vercel's 4.5 MB request limit. The server then moves a file into the
// Files API (or, for big data files, hands the coach a signed download link) and the bucket's
// lifecycle rule deletes whatever is left after a few days.
// Env: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET. Without them, uploads go
// through the site as before (4 MB).
import "server-only";
import { AwsClient } from "aws4fetch";
import { createHash, randomUUID } from "node:crypto";

const env = process.env;
export const r2Enabled = Boolean(env.R2_ACCOUNT_ID && env.R2_ACCESS_KEY_ID && env.R2_SECRET_ACCESS_KEY && env.R2_BUCKET);

let client: AwsClient | null = null;
function r2(): AwsClient {
  client ??= new AwsClient({
    accessKeyId: env.R2_ACCESS_KEY_ID!,
    secretAccessKey: env.R2_SECRET_ACCESS_KEY!,
    service: "s3",
    region: "auto",
  });
  return client;
}

function objectUrl(key: string): string {
  const path = key.split("/").map(encodeURIComponent).join("/");
  return `https://${env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com/${env.R2_BUCKET}/${path}`;
}

/** Every key starts with a hash of the player, so a player can only finish their own uploads. */
export function playerPrefix(player: string): string {
  return createHash("sha256").update(`luckyj-attach:${player}`).digest("hex").slice(0, 20);
}

export function newKey(player: string, name: string): string {
  const safe = name.replace(/[^\w.-]+/g, "_").slice(-120) || "file";
  return `${playerPrefix(player)}/${randomUUID()}/${safe}`;
}

export function ownsKey(player: string, key: string): boolean {
  return key.startsWith(`${playerPrefix(player)}/`) && !key.includes("..");
}

async function presign(method: "PUT" | "GET", key: string, seconds: number): Promise<string> {
  const url = new URL(objectUrl(key));
  url.searchParams.set("X-Amz-Expires", String(seconds));
  const signed = await r2().sign(new Request(url, { method }), { aws: { signQuery: true } });
  return signed.url;
}

/** A URL the browser can PUT the file to for the next ten minutes. */
export const uploadUrl = (key: string) => presign("PUT", key, 600);

/** A URL the coach's sandbox can download the file from for 24 hours (the bucket deletes files after a day). */
export const downloadUrl = (key: string) => presign("GET", key, 24 * 3600);

export async function readObject(key: string): Promise<{ bytes: Buffer; size: number } | null> {
  const res = await r2().fetch(objectUrl(key));
  if (!res.ok) return null;
  const bytes = Buffer.from(await res.arrayBuffer());
  return { bytes, size: bytes.length };
}

export async function objectSize(key: string): Promise<number | null> {
  const res = await r2().fetch(objectUrl(key), { method: "HEAD" });
  return res.ok ? Number(res.headers.get("content-length") || 0) : null;
}

export async function deleteObject(key: string): Promise<void> {
  await r2().fetch(objectUrl(key), { method: "DELETE" }).catch(() => {});
}
