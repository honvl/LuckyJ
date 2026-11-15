import { NextResponse } from "next/server";
import { currentThread } from "@/lib/auth";
import { anthropic, takeIntro } from "@/lib/server";

const MAX_CHARS = 8000;

export async function POST(request: Request) {
  const me = await currentThread();
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  const body = await request.json().catch(() => null);
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  if (!text) return NextResponse.json({ error: "empty message" }, { status: 400 });
  if (text.length > MAX_CHARS) return NextResponse.json({ error: "message too long" }, { status: 400 });

  const events: any[] = [{ type: "user.message", content: [{ type: "text", text }] }];
  const intro = takeIntro(me.player, me.sessionId);
  // The API takes a system message only as the last event of a request.
  if (intro) events.push({ type: "system.message", content: [{ type: "text", text: intro }] });
  try {
    await anthropic().beta.sessions.events.send(me.sessionId, { events } as any);
  } catch (error: any) {
    const budget = /budget/i.test(String(error?.message));
    return NextResponse.json(
      { error: budget ? "budget" : "send failed" },
      { status: budget ? 402 : 502 },
    );
  }
  return NextResponse.json({ ok: true });
}
