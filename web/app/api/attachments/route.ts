import { NextResponse } from "next/server";
import { currentPlayer } from "@/lib/auth";
import { saveFromR2, saveUpload } from "@/lib/attachments";
import { accessFor } from "@/lib/billing";

export const maxDuration = 60; // moving a 32 MB PDF from R2 to the Files API takes a few seconds

const KNOWN = new Set(["unsupported file type", "file too large", "unknown upload"]);

/**
 * Finish one attachment. JSON {key, name, type, thumb}: a file the browser already put in R2
 * (see ./upload). Multipart {file, thumb}: a small file posted here directly (no R2 configured).
 */
export async function POST(request: Request) {
  const me = await currentPlayer();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  if (!(await accessFor(me.email)).allowed) return NextResponse.json({ error: "subscription" }, { status: 402 });
  try {
    if ((request.headers.get("content-type") || "").includes("application/json")) {
      const body = await request.json();
      const thumb = typeof body?.thumb === "string" ? body.thumb : null;
      const declared = Number(body?.size);
      return NextResponse.json(await saveFromR2(me.player, String(body?.key || ""), String(body?.name || "file"), String(body?.type || ""), thumb, Number.isFinite(declared) && declared > 0 ? declared : null));
    }
    const form = await request.formData().catch(() => null);
    const file = form?.get("file");
    if (!(file instanceof File)) return NextResponse.json({ error: "no file" }, { status: 400 });
    const thumb = form?.get("thumb");
    return NextResponse.json(await saveUpload(me.player, file, typeof thumb === "string" ? thumb : null));
  } catch (error: any) {
    const message = String(error?.message || "");
    if (!KNOWN.has(message)) console.error("attachment failed", error);
    return NextResponse.json({ error: KNOWN.has(message) ? message : "upload failed" }, { status: KNOWN.has(message) ? 400 : 502 });
  }
}
