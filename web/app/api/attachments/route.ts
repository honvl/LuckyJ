import { NextResponse } from "next/server";
import { currentPlayer } from "@/lib/auth";
import { saveAttachment } from "@/lib/attachments";
import { accessFor } from "@/lib/billing";

/** Upload one attachment (form fields: file, and thumb for images). Returns its file id. */
export async function POST(request: Request) {
  const me = await currentPlayer();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  if (!(await accessFor(me.email)).allowed) return NextResponse.json({ error: "subscription" }, { status: 402 });
  const form = await request.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) return NextResponse.json({ error: "no file" }, { status: 400 });
  const thumb = form?.get("thumb");
  try {
    return NextResponse.json(await saveAttachment(me.player, file, typeof thumb === "string" ? thumb : null));
  } catch (error: any) {
    const message = String(error?.message || "");
    const known = message === "unsupported file type" || message === "file too large";
    if (!known) console.error("attachment upload failed", error);
    return NextResponse.json({ error: known ? message : "upload failed" }, { status: known ? 400 : 502 });
  }
}
