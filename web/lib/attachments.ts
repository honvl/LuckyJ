// Files a player attaches to a message: kept in the Files API and sent to the coach by reference
// (image and document blocks), so a long thread does not carry them inline. A small thumbnail of
// each image stays in the database so the thread can show it again.
import "server-only";
import { toFile } from "@anthropic-ai/sdk";
import { neon } from "@neondatabase/serverless";
import { anthropic } from "./server";

const sql = process.env.DATABASE_URL ? neon(process.env.DATABASE_URL) : null;

/** Under Vercel's 4.5 MB request limit, with room for the form around the file. */
export const MAX_BYTES = 4_000_000;
const IMAGE = new Set(["image/jpeg", "image/png", "image/gif", "image/webp"]);
const TEXT = /\.(txt|csv|tsv|json|md|log|xml|html?)$/i;

export type Attached = { fileId: string; kind: "image" | "document"; name: string; mime: string };

/** What a file is to the coach: an image, a PDF, a plain-text document, or nothing it can read. */
export function kindOf(name: string, mime: string): { kind: "image" | "document"; mime: string } | null {
  if (IMAGE.has(mime)) return { kind: "image", mime };
  if (mime === "application/pdf") return { kind: "document", mime };
  if (mime.startsWith("text/") || mime === "application/json" || TEXT.test(name)) return { kind: "document", mime: "text/plain" };
  return null;
}

export async function saveAttachment(player: string, file: File, thumb: string | null): Promise<Attached> {
  const kind = kindOf(file.name, file.type || "");
  if (!kind) throw new Error("unsupported file type");
  if (file.size > MAX_BYTES) throw new Error("file too large");
  const meta: any = await anthropic().beta.files.upload({
    file: await toFile(Buffer.from(await file.arrayBuffer()), file.name, { type: kind.mime }),
  } as any);
  const row: Attached = { fileId: meta.id, kind: kind.kind, name: file.name.slice(0, 200), mime: kind.mime };
  const smallThumb = thumb && thumb.startsWith("data:image/") && thumb.length < 120_000 ? thumb : null;
  if (sql) {
    await sql`insert into attachments (file_id, player, name, mime, kind, thumb)
              values (${row.fileId}, ${player}, ${row.name}, ${row.mime}, ${row.kind}, ${smallThumb})`;
  }
  return row;
}

/** The player's own attachments among these ids (others are dropped). */
export async function ownAttachments(player: string, ids: string[]): Promise<Attached[]> {
  if (!ids.length) return [];
  if (!sql) return [];
  const rows = await sql`select file_id, kind, name, mime from attachments where player = ${player} and file_id = any(${ids})`;
  const byId = new Map(rows.map((r) => [r.file_id as string, r]));
  return ids.flatMap((id) => {
    const r = byId.get(id);
    return r ? [{ fileId: id, kind: r.kind, name: r.name, mime: r.mime } as Attached] : [];
  });
}

/** Content blocks for a user message: the files first, then the text. */
export function messageContent(text: string, files: Attached[]): any[] {
  const blocks: any[] = files.map((f) =>
    f.kind === "image"
      ? { type: "image", source: { type: "file", file_id: f.fileId } }
      : { type: "document", source: { type: "file", file_id: f.fileId }, title: f.name },
  );
  if (text) blocks.push({ type: "text", text });
  return blocks;
}

export async function thumbnail(player: string, fileId: string): Promise<{ thumb: string | null; name: string } | null> {
  if (!sql) return null;
  const [row] = await sql`select thumb, name from attachments where player = ${player} and file_id = ${fileId}`;
  return row ? { thumb: row.thumb, name: row.name } : null;
}
