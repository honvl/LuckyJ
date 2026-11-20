// Files a player attaches to a message. What the coach gets depends on the file:
// - images (shrunk in the browser) and PDFs up to the model's limits, and text files up to 1 MB,
//   go to the Files API and into the message as image and document blocks;
// - anything bigger (a long CSV, a zip of game logs) stays in R2, and the message carries a
//   48-hour download link the coach's sandbox fetches with curl.
// A small thumbnail of each image stays in the database so the thread can show it again.
import "server-only";
import { toFile } from "@anthropic-ai/sdk";
import { neon } from "@neondatabase/serverless";
import { deleteObject, downloadUrl, objectSize, ownsKey, r2Enabled, readObject } from "./r2";
import { anthropic } from "./server";

const sql = process.env.DATABASE_URL ? neon(process.env.DATABASE_URL) : null;

import { MAX_VIA_SITE, planFor } from "./attachment-rules.mjs";

export { MAX_VIA_SITE, planFor };
export type Kind = "image" | "document" | "download";
export type Attached = { fileId: string; kind: Kind; name: string; mime: string; size?: number };

async function record(player: string, row: Attached, thumb: string | null) {
  const smallThumb = thumb && thumb.startsWith("data:image/") && thumb.length < 120_000 ? thumb : null;
  if (!sql) return;
  await sql`insert into attachments (file_id, player, name, mime, kind, thumb)
            values (${row.fileId}, ${player}, ${row.name}, ${row.mime}, ${row.kind}, ${smallThumb})`;
}

async function toFilesApi(player: string, bytes: Buffer, name: string, kind: Kind, mime: string, thumb: string | null): Promise<Attached> {
  const meta: any = await anthropic().beta.files.upload({ file: await toFile(bytes, name, { type: mime }) } as any);
  const row: Attached = { fileId: meta.id, kind, name: name.slice(0, 200), mime, size: bytes.length };
  await record(player, row, thumb);
  return row;
}

/** A file posted to the site itself (no R2, up to 4 MB). */
export async function saveUpload(player: string, file: File, thumb: string | null): Promise<Attached> {
  const plan = planFor(file.name, file.type || "", file.size, false);
  if ("error" in plan) throw new Error(plan.error);
  return toFilesApi(player, Buffer.from(await file.arrayBuffer()), file.name, plan.kind, plan.mime, thumb);
}

/** A file the browser put in R2: into the Files API (then out of R2), or kept there for download. */
export async function saveFromR2(player: string, key: string, name: string, mime: string, thumb: string | null): Promise<Attached> {
  if (!r2Enabled || !ownsKey(player, key)) throw new Error("unknown upload");
  const size = await objectSize(key);
  if (size == null) throw new Error("unknown upload");
  const plan = planFor(name, mime, size, true);
  if ("error" in plan) {
    await deleteObject(key);
    throw new Error(plan.error);
  }
  if (plan.kind === "download") {
    const row: Attached = { fileId: `r2:${key}`, kind: "download", name: name.slice(0, 200), mime: plan.mime, size };
    await record(player, row, null);
    return row;
  }
  const object = await readObject(key);
  if (!object) throw new Error("unknown upload");
  const row = await toFilesApi(player, object.bytes, name, plan.kind, plan.mime, thumb);
  await deleteObject(key);
  return row;
}

/** The player's own attachments among these ids (others are dropped). */
export async function ownAttachments(player: string, ids: string[]): Promise<Attached[]> {
  if (!ids.length || !sql) return [];
  const rows = await sql`select file_id, kind, name, mime from attachments where player = ${player} and file_id = any(${ids})`;
  const byId = new Map(rows.map((r) => [r.file_id as string, r]));
  return ids.flatMap((id) => {
    const r = byId.get(id);
    return r ? [{ fileId: id, kind: r.kind, name: r.name, mime: r.mime } as Attached] : [];
  });
}

/** The line that hands the coach a big file; lib/events.ts reads it back as an attachment. */
export const DOWNLOAD_MARKER = "[attached file] ";

/** Content blocks for a user message: the files first, then the text. */
export async function messageContent(text: string, files: Attached[]): Promise<any[]> {
  const blocks: any[] = [];
  for (const f of files) {
    if (f.kind === "image") blocks.push({ type: "image", source: { type: "file", file_id: f.fileId } });
    else if (f.kind === "document") blocks.push({ type: "document", source: { type: "file", file_id: f.fileId }, title: f.name });
    else {
      const url = await downloadUrl(f.fileId.replace(/^r2:/, ""));
      const target = `/workspace/uploads/${f.name.replace(/[^\w.-]+/g, "_")}`;
      blocks.push({
        type: "text",
        text: `${DOWNLOAD_MARKER}${f.name} (too big to read in one go; the link works for 48 hours). ` +
          `Fetch it before you use it: mkdir -p /workspace/uploads && curl -fsSL -o "${target}" "${url}"`,
      });
    }
  }
  if (text) blocks.push({ type: "text", text });
  return blocks;
}

export async function thumbnail(player: string, fileId: string): Promise<{ thumb: string | null; name: string } | null> {
  if (!sql) return null;
  const [row] = await sql`select thumb, name from attachments where player = ${player} and file_id = ${fileId}`;
  return row ? { thumb: row.thumb, name: row.name } : null;
}
