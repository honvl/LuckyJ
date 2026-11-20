// Turn the signed-in player's whole Personal Guide on or off the site.
import { NextResponse } from "next/server";
import { currentThread } from "@/lib/auth";
import { setBookPublic } from "@/lib/books";

export async function POST(request: Request) {
  const me = await currentThread();
  if (!me) return NextResponse.json({ error: "no guide yet" }, { status: 404 });
  const body = await request.json().catch(() => null);
  if (typeof body?.isPublic !== "boolean") return NextResponse.json({ error: "bad request" }, { status: 400 });
  await setBookPublic(me.player, body.isPublic);
  return NextResponse.json({ ok: true });
}
