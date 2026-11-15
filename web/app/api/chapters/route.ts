import { NextResponse } from "next/server";
import { currentThread } from "@/lib/auth";
import { setChapterPublic } from "@/lib/server";

export async function POST(request: Request) {
  const me = await currentThread();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  const body = await request.json().catch(() => null);
  const chapter = typeof body?.chapter === "string" ? body.chapter : "";
  if (!/^\d+-[\w-]+$/.test(chapter) || typeof body?.isPublic !== "boolean") {
    return NextResponse.json({ error: "bad request" }, { status: 400 });
  }
  setChapterPublic(me.player, chapter, body.isPublic);
  return NextResponse.json({ ok: true });
}
