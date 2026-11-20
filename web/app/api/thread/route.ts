import { NextResponse } from "next/server";
import { currentThread } from "@/lib/auth";
import { ownChapters, syncChapters } from "@/lib/books";
import { threadHistory, threadSummary } from "@/lib/thread";

export const dynamic = "force-dynamic";

// ?sync=1 (sent when a turn ends) checks for new chapter archives now; otherwise at most once a minute.
export async function GET(request: Request) {
  const me = await currentThread();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  const force = new URL(request.url).searchParams.get("sync") === "1";
  await syncChapters(me.player, force).catch((error) => console.error("chapter sync failed", error));
  const [summary, events, own] = await Promise.all([
    threadSummary(me.sessionId),
    threadHistory(me.sessionId),
    ownChapters(me.player),
  ]);
  const chapters = own.chapters.map(({ key, number, title, isPublic }) => ({ key, number, title, isPublic }));
  return NextResponse.json({ player: me.player, ...summary, events, chapters, bookSlug: own.slug });
}
