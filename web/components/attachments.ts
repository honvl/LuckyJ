"use client";
// Attachments for the chat composer (assistant-ui AttachmentAdapter). A file uploads as soon as it
// is picked, like Claude Desktop: photos are shrunk first (longest side 1568 px, the size the model
// reads best) and get a small thumbnail for the thread. The site keeps the file in the Files API;
// the message then refers to it by id (see /api/attachments and lib/attachments.ts).
import type { AttachmentAdapter, CompleteAttachment, PendingAttachment } from "@assistant-ui/react";

const ACCEPT = "image/jpeg,image/png,image/gif,image/webp,application/pdf,text/plain,text/csv,.csv,.tsv,.json,.md,.log,.txt";
const MAX_BYTES = 4_000_000;
const MODEL_EDGE = 1568;
const THUMB_EDGE = 320;

/** The upload's file id and thumbnail for each attachment the composer holds (keyed by its id). */
export const uploaded = new Map<string, { fileId: string; thumb: string | null; kind: "image" | "document" }>();

async function scaled(file: File, edge: number, type = "image/jpeg", quality = 0.86): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  const ratio = Math.min(1, edge / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(bitmap.width * ratio));
  canvas.height = Math.max(1, Math.round(bitmap.height * ratio));
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("could not read the image"))), type, quality));
}

function dataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

function isImage(file: File) {
  return /^image\/(jpeg|png|gif|webp)$/.test(file.type);
}

export function attachmentAdapter(messages: { tooLarge: string; failed: string }): AttachmentAdapter {
  return {
    accept: ACCEPT,
    async *add({ file }) {
      const id = `att-${crypto.randomUUID()}`;
      const image = isImage(file);
      const base: Omit<PendingAttachment, "status"> = { id, type: image ? "image" : "document", name: file.name, contentType: file.type, file };
      yield { ...base, status: { type: "running", reason: "uploading", progress: 0 } };
      try {
        let body: Blob = file;
        let name = file.name;
        let thumb: string | null = null;
        if (image && file.type !== "image/gif") {
          body = await scaled(file, MODEL_EDGE);
          name = name.replace(/\.(png|webp|jpe?g)$/i, "") + ".jpg";
        }
        if (image) thumb = await dataUrl(await scaled(file, THUMB_EDGE, "image/jpeg", 0.8));
        if (body.size > MAX_BYTES) throw new Error(messages.tooLarge);
        const form = new FormData();
        form.append("file", new File([body], name, { type: image && file.type !== "image/gif" ? "image/jpeg" : file.type || "text/plain" }));
        if (thumb) form.append("thumb", thumb);
        const res = await fetch("/api/attachments", { method: "POST", body: form });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.error === "file too large" ? messages.tooLarge : messages.failed);
        }
        const saved = await res.json();
        uploaded.set(id, { fileId: saved.fileId, thumb, kind: saved.kind });
        yield { ...base, status: { type: "requires-action", reason: "composer-send" } };
      } catch (error: any) {
        yield { ...base, status: { type: "incomplete", reason: "error", message: String(error?.message || messages.failed) } };
      }
    },
    async remove(attachment) {
      uploaded.delete(attachment.id);
    },
    async send(attachment): Promise<CompleteAttachment> {
      const up = uploaded.get(attachment.id);
      const content: CompleteAttachment["content"] = up?.thumb
        ? [{ type: "image", image: up.thumb }]
        : [{ type: "file", data: "", mimeType: attachment.contentType || "text/plain", filename: attachment.name }];
      return { ...attachment, status: { type: "complete" }, content };
    },
  };
}
