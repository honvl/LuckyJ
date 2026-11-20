import { NextResponse } from "next/server";
import { currentPlayer } from "@/lib/auth";
import { accessFor } from "@/lib/billing";
import { createThread, listThreads } from "@/lib/threads";

export const dynamic = "force-dynamic";

/** The signed-in player's threads, newest first. */
export async function GET() {
  const me = await currentPlayer();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  return NextResponse.json({ threads: await listThreads(me.player) });
}

/** Start a new thread. */
export async function POST() {
  const me = await currentPlayer();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  if (!(await accessFor(me.email)).allowed) return NextResponse.json({ error: "subscription" }, { status: 402 });
  try {
    return NextResponse.json({ id: await createThread(me.player) });
  } catch (error) {
    console.error("new thread failed", error);
    return NextResponse.json({ error: "new thread failed" }, { status: 502 });
  }
}
