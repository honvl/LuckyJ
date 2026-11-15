// Server-sent events: the thread's live events, reduced for the page. The browser reconnects on
// its own when this closes, and refetches history to fill any gap.
import { currentThread } from "@/lib/auth";
import { toChatEvent } from "@/lib/events";
import { anthropic } from "@/lib/server";

export const dynamic = "force-dynamic";
export const maxDuration = 300;

export async function GET(request: Request) {
  const me = await currentThread();
  if (!me) return new Response("not signed in", { status: 401 });
  const upstream = await anthropic().beta.sessions.events.stream(me.sessionId);
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    async start(controller) {
      const stop = () => {
        upstream.controller.abort();
        try { controller.close(); } catch {}
      };
      request.signal.addEventListener("abort", stop);
      controller.enqueue(encoder.encode(": open\n\n"));
      try {
        for await (const ev of upstream) {
          const chat = toChatEvent(ev as any);
          if (chat) controller.enqueue(encoder.encode(`data: ${JSON.stringify(chat)}\n\n`));
        }
      } catch {
        // aborted or dropped: the browser reconnects
      }
      stop();
    },
  });
  return new Response(body, {
    headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache, no-transform", Connection: "keep-alive" },
  });
}
