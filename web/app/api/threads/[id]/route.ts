import { NextResponse } from "next/server";
import { currentPlayer } from "@/lib/auth";
import { updateThread } from "@/lib/threads";

/** Rename ({title}) or archive ({archived}) one of the player's threads. */
export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const me = await currentPlayer();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  const { id } = await params;
  const body = await request.json().catch(() => ({}));
  await updateThread(me.player, id, {
    title: typeof body?.title === "string" ? body.title : undefined,
    archived: typeof body?.archived === "boolean" ? body.archived : undefined,
  });
  return NextResponse.json({ ok: true });
}
