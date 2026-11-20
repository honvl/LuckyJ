import { NextResponse } from "next/server";
import { currentThread } from "@/lib/auth";
import { usedThisMonth } from "@/lib/budget";
import { ownChapters, syncChapters } from "@/lib/books";
import { threadHistory, threadSummary } from "@/lib/thread";

export const dynamic = "force-dynamic";

// ?thread=<id> picks the thread (the newest open one by default). ?sync=1 (sent when a turn ends)
// checks for new chapter archives now; otherwise at most once a minute.
export async function GET(request: Request) {
  const params = new URL(request.url).searchParams;
  const me = await currentThread(params.get("thread"));
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  await syncChapters(me.player, params.get("sync") === "1").catch((error) => console.error("chapter sync failed", error));
  const [summary, events, own, used] = await Promise.all([
    threadSummary(me.sessionId),
    threadHistory(me.sessionId),
    ownChapters(me.player),
    usedThisMonth(me.player),
  ]);
  const chapters = own.chapters.map(({ key, number, title, isPublic }) => ({ key, number, title, isPublic }));
  return NextResponse.json({ player: me.player, thread: me.sessionId, status: summary.status, usedPct: used, events, chapters, bookSlug: own.slug });
}
