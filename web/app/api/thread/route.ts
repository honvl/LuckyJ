import { NextResponse } from "next/server";
import { currentThread } from "@/lib/auth";
import { threadChapters, threadHistory, threadSummary } from "@/lib/thread";

export const dynamic = "force-dynamic";

export async function GET() {
  const me = await currentThread();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  const [summary, events, chapters] = await Promise.all([
    threadSummary(me.sessionId),
    threadHistory(me.sessionId),
    threadChapters(me.player, me.sessionId),
  ]);
  return NextResponse.json({ player: me.player, ...summary, events, chapters });
}
