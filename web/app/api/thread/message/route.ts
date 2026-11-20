import { NextResponse } from "next/server";
import { currentThread } from "@/lib/auth";
import { messageContent, ownAttachments } from "@/lib/attachments";
import { accessFor } from "@/lib/billing";
import { prepareSend } from "@/lib/budget";
import { anthropic } from "@/lib/server";
import { takeIntro } from "@/lib/store";
import { titleFromFirstMessage } from "@/lib/threads";

const MAX_CHARS = 8000;

export async function POST(request: Request) {
  const body = await request.json().catch(() => null);
  const me = await currentThread(typeof body?.thread === "string" ? body.thread : null);
  if (!me) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  if (!(await accessFor(me.email)).allowed) return NextResponse.json({ error: "subscription" }, { status: 402 });
  const text = typeof body?.text === "string" ? body.text.trim() : "";
  const ids = Array.isArray(body?.attachments) ? body.attachments.filter((x: unknown) => typeof x === "string").slice(0, 10) : [];
  const files = await ownAttachments(me.player, ids);
  if (!text && !files.length) return NextResponse.json({ error: "empty message" }, { status: 400 });
  if (text.length > MAX_CHARS) return NextResponse.json({ error: "message too long" }, { status: 400 });
  // All of the player's threads share one allowance; give this thread what the others are not holding.
  if (!(await prepareSend(me.player, me.sessionId))) return NextResponse.json({ error: "budget" }, { status: 402 });

  const events: any[] = [{ type: "user.message", content: await messageContent(text, files) }];
  const intro = await takeIntro(me.player, me.sessionId);
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
  await titleFromFirstMessage(me.player, me.sessionId, text || files.map((f) => f.name).join(", ")).catch(() => {});
  return NextResponse.json({ ok: true, thread: me.sessionId });
}
