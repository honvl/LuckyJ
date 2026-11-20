// The thread's events, reduced to what the chat page shows. History (events.list) and the live
// stream go through the same function, so a reconnect that refetches history dedupes by id.

export type ChatEvent =
  | { id: string; kind: "user"; text: string; files?: { fileId: string; kind: "image" | "document" | "download"; name?: string }[] }
  | { id: string; kind: "agent"; text: string }
  | { id: string; kind: "tool"; label: string; detail: string; failed?: boolean }
  | { id: string; kind: "status"; state: "running" | "idle"; stop?: string }
  | { id: string; kind: "usage"; spentCents: number }
  | { id: string; kind: "compacted" }
  | { id: string; kind: "error"; message: string };

type Raw = { id: string; type: string; [key: string]: any };

/** Same as lib/attachments.ts (kept here because this file also runs in the browser). */
const DOWNLOAD_MARKER = "[attached file] ";

function textOf(content: any[] | undefined): string {
  return (content || []).filter((b) => b?.type === "text").map((b) => b.text).join("");
}

function oneLine(value: unknown, limit = 160): string {
  const text = (typeof value === "string" ? value : JSON.stringify(value ?? "")).replace(/\s+/g, " ").trim();
  return text.length <= limit ? text : `${text.slice(0, limit - 1)}…`;
}

function base(path: unknown): string {
  return String(path || "").split("/").filter(Boolean).pop() || "";
}

/** What a tool call did, in words a player can read; `detail` keeps the raw call. */
function describeTool(name: string, input: any): { label: string; detail: string } {
  switch (name) {
    case "bash": {
      const cmd = String(input?.command || "");
      const script = cmd.match(/scripts\/([\w-]+\.py)/)?.[1];
      return { label: script ? `Ran ${script}` : "Ran a command", detail: oneLine(cmd, 400) };
    }
    case "read":
      return { label: `Read ${base(input?.file_path)}`, detail: String(input?.file_path || "") };
    case "write":
      return { label: `Wrote ${base(input?.file_path)}`, detail: String(input?.file_path || "") };
    case "edit":
      return { label: `Edited ${base(input?.file_path)}`, detail: String(input?.file_path || "") };
    case "grep":
    case "glob":
      return { label: "Searched the code", detail: oneLine(input) };
    default:
      return { label: `Used ${name}`, detail: oneLine(input) };
  }
}

export function toChatEvent(ev: Raw): ChatEvent | null {
  switch (ev.type) {
    case "user.message": {
      // Attached files travel as image and document blocks that point at the Files API.
      // Big files arrive as a download line (lib/attachments.ts DOWNLOAD_MARKER), not as text.
      const blocks: any[] = ev.content || [];
      const isDownload = (b: any) => b?.type === "text" && String(b.text).startsWith(DOWNLOAD_MARKER);
      type Attached = { fileId: string; kind: "image" | "document" | "download"; name?: string };
      const files = blocks.flatMap((b: any): Attached[] => {
        if ((b?.type === "image" || b?.type === "document") && b?.source?.file_id)
          return [{ fileId: b.source.file_id as string, kind: b.type as "image" | "document", name: b.title ?? undefined }];
        if (isDownload(b)) {
          const name = String(b.text).slice(DOWNLOAD_MARKER.length).split(" (too big")[0];
          return [{ fileId: "", kind: "download", name }];
        }
        return [];
      });
      const text = textOf(blocks.filter((b) => !isDownload(b)));
      return files.length ? { id: ev.id, kind: "user", text, files } : { id: ev.id, kind: "user", text };
    }
    case "agent.message":
      return { id: ev.id, kind: "agent", text: textOf(ev.content) };
    case "agent.tool_use":
      return { id: ev.id, kind: "tool", ...describeTool(ev.name, ev.input) };
    case "session.status_running":
      return { id: ev.id, kind: "status", state: "running" };
    case "session.status_idle":
      return { id: ev.id, kind: "status", state: "idle", stop: ev.stop_reason?.type };
    case "session.usage": {
      const amount = ev.usage?.list_cost?.amount;
      return amount == null ? null : { id: ev.id, kind: "usage", spentCents: Number(amount) };
    }
    // Chapters are built by a copy of the coach in its own thread; the chat shows the handoff
    // and the report, not the copy's own tool calls.
    case "agent.thread_message_sent":
      return { id: ev.id, kind: "tool", label: "Handed work to the chapter builder", detail: oneLine(textOf(ev.content), 400) };
    case "agent.thread_message_received":
      return { id: ev.id, kind: "tool", label: "Chapter builder reported back", detail: oneLine(textOf(ev.content), 400) };
    case "agent.thread_context_compacted":
      return { id: ev.id, kind: "compacted" };
    case "session.error":
      return { id: ev.id, kind: "error", message: oneLine(ev.error?.message || ev.error || "error") };
    default:
      return null; // system.message (the operator's context), tool results, spans
  }
}
