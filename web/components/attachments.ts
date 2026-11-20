"use client";
// Attachments for the chat composer (assistant-ui AttachmentAdapter). A file uploads as soon as it
// is picked, like Claude Desktop: photos are shrunk first (longest side 1568 px, the size the model
// reads best) and get a small thumbnail for the thread. The browser puts the file straight into R2
// with a signed URL (no size limit from the site's host), then /api/attachments moves it to the
// Files API or keeps it as a download for big data files (lib/attachments.ts). Without R2 the file
// is posted to the site itself, up to 4 MB.
import type { AttachmentAdapter, CompleteAttachment, PendingAttachment } from "@assistant-ui/react";

const MAX_BYTES = 100_000_000;
const MODEL_EDGE = 1568;
const THUMB_EDGE = 320;

/** The upload's file id and thumbnail for each attachment the composer holds (keyed by its id). */
export const uploaded = new Map<string, { fileId: string; thumb: string | null; kind: "image" | "document" | "download" }>();

/** PUT to a signed R2 URL, reporting progress (fetch cannot report upload progress). */
function put(url: string, body: Blob, onProgress: (fraction: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`upload ${xhr.status}`)));
    xhr.onerror = () => reject(new Error("upload failed"));
    xhr.send(body);
  });
}

async function errorOf(res: Response, messages: { tooLarge: string; failed: string; limit: string }): Promise<Error> {
  const err = await res.json().catch(() => ({}));
  if (res.status === 429) return new Error(messages.limit);
  return new Error(err.error === "file too large" ? messages.tooLarge : messages.failed);
}

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

export function attachmentAdapter(messages: { tooLarge: string; failed: string; limit: string }): AttachmentAdapter {
  return {
    accept: "*/*",
    async *add({ file }) {
      const id = `att-${crypto.randomUUID()}`;
      const image = isImage(file);
      const base: Omit<PendingAttachment, "status"> = { id, type: image ? "image" : "document", name: file.name, contentType: file.type, file };
      yield { ...base, status: { type: "running", reason: "uploading", progress: 0 } };
      try {
        let body: Blob = file;
        let name = file.name;
        let type = file.type || "application/octet-stream";
        let thumb: string | null = null;
        if (image && file.type !== "image/gif") {
          body = await scaled(file, MODEL_EDGE);
          name = name.replace(/\.(png|webp|jpe?g)$/i, "") + ".jpg";
          type = "image/jpeg";
        }
        if (image) thumb = await dataUrl(await scaled(file, THUMB_EDGE, "image/jpeg", 0.8));
        if (body.size > MAX_BYTES) throw new Error(messages.tooLarge);

        let saved: { fileId: string; kind: "image" | "document" | "download" };
        const ticket = await fetch("/api/attachments/upload", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, type, size: body.size }),
        });
        if (ticket.status === 501) {
          // No R2: post the file to the site (Vercel takes up to about 4.5 MB per request).
          const form = new FormData();
          form.append("file", new File([body], name, { type }));
          if (thumb) form.append("thumb", thumb);
          const res = await fetch("/api/attachments", { method: "POST", body: form });
          if (!res.ok) throw await errorOf(res, messages);
          saved = await res.json();
        } else {
          if (!ticket.ok) throw await errorOf(ticket, messages);
          const { key, url } = await ticket.json();
          // Progress comes from the upload's own events; queue them for this generator.
          const updates: number[] = [];
          let wake: (() => void) | null = null;
          let done = false;
          let failure: unknown = null;
          put(url, body, (f) => { updates.push(f); wake?.(); })
            .catch((e) => { failure = e; })
            .finally(() => { done = true; wake?.(); });
          while (!done || updates.length) {
            if (!updates.length) await new Promise<void>((r) => (wake = r));
            wake = null;
            const latest = updates.splice(0).pop();
            if (latest != null) yield { ...base, status: { type: "running", reason: "uploading", progress: Math.min(0.95, latest) } };
          }
          if (failure) throw new Error(messages.failed);
          const res = await fetch("/api/attachments", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ key, name, type, thumb, size: body.size }),
          });
          if (!res.ok) throw await errorOf(res, messages);
          saved = await res.json();
        }
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
