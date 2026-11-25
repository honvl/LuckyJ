"use client";
// The chat page: assistant-ui's thread and thread list (components/assistant-ui) fed from the
// coach's sessions. Each thread is a coach session; the sidebar lists them like Claude Desktop.
import {
  AssistantRuntimeProvider,
  type AppendMessage,
  type ThreadMessageLike,
  useExternalStoreRuntime,
  WebSpeechDictationAdapter,
} from "@assistant-ui/react";
import { BookOpenIcon, LibraryIcon, MenuIcon, NotebookTextIcon, XIcon } from "lucide-react";
import { signOut } from "next-auth/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { attachmentAdapter, uploaded } from "@/components/attachments";
import { MahjongContext } from "@/components/assistant-ui/elements/markdown-text";
import { Thread } from "@/components/assistant-ui/elements/thread.aui";
import { ThreadList } from "@/components/assistant-ui/elements/thread-list.aui";
import { AuiLabelsContext } from "@/components/assistant-ui/labels";
import type { ChatEvent } from "@/lib/events";
import { SITE } from "@/lib/site-strings";
import { STRINGS, type Lang } from "@/lib/strings";

type ThreadRow = { id: string; title: string | null; createdAt: string; archived: boolean };
type Chapter = { key: string; number: number; title: string; isPublic: boolean };
type File_ = { fileId: string; kind: "image" | "document" | "download"; name?: string; thumb?: string | null };
type Local = { id: string; kind: "user"; text: string; local: true; files?: File_[] };
// serverId: a message sent from this page keeps the id it was drawn with when the server's copy
// arrives, so the thread does not read the swap as an edit (a "2/2" branch).
type Item = (Extract<ChatEvent, { kind: "user" | "agent" | "tool" | "compacted" | "error" }> & { serverId?: string }) | Local;

/** The coach's events as chat messages: each reply gathers its text and tool steps. */
function toMessages(items: Item[], running: boolean, t: (typeof STRINGS)[Lang]): ThreadMessageLike[] {
  const out: ThreadMessageLike[] = [];
  let reply: { id: string; parts: any[] } | null = null;
  const flush = () => {
    if (reply) out.push({ id: reply.id, role: "assistant", content: reply.parts, status: { type: "complete", reason: "unknown" } });
    reply = null;
  };
  for (const ev of items) {
    if (ev.kind === "user") {
      flush();
      const files = ((ev as any).files || []) as File_[];
      out.push({
        id: ev.id,
        role: "user",
        content: ev.text ? [{ type: "text", text: ev.text }] : [],
        attachments: files.map((f) => ({
          id: f.fileId || `${ev.id}-${f.name}`,
          type: f.kind === "image" ? "image" : "document",
          name: f.name || (f.kind === "image" ? "image" : "document"),
          status: { type: "complete" as const },
          content: f.kind === "image"
            ? [{ type: "image" as const, image: f.thumb || `/api/attachments/${encodeURIComponent(f.fileId)}` }]
            : [{ type: "file" as const, data: "", mimeType: "application/octet-stream", filename: f.name || "document" }],
        })),
      });
      continue;
    }
    reply ??= { id: `reply-${ev.id}`, parts: [] };
    if (ev.kind === "agent") reply.parts.push({ type: "text", text: ev.text });
    else if (ev.kind === "tool")
      reply.parts.push({
        type: "tool-call", toolCallId: ev.id, toolName: ev.label, args: { detail: ev.detail }, argsText: ev.detail,
        result: ev.failed ? "failed" : "done", isError: Boolean(ev.failed),
      });
    else if (ev.kind === "compacted") reply.parts.push({ type: "text", text: `*${t.compacted}*` });
    else if (ev.kind === "error") reply.parts.push({ type: "text", text: `**${ev.message}**` });
  }
  flush();
  const last = out[out.length - 1];
  if (running && last?.role === "assistant") {
    const parts = [...(last.content as any[])];
    const tool = parts[parts.length - 1];
    // The step the coach is on has no result yet.
    if (tool?.type === "tool-call") parts[parts.length - 1] = { ...tool, result: undefined, isError: false };
    out[out.length - 1] = { ...last, content: parts, status: { type: "running" } };
  }
  return out;
}

function textOf(message: AppendMessage): string {
  return message.content.map((p) => (p.type === "text" ? p.text : "")).join("").trim();
}

/** The uploaded files a composed message carries. */
function filesOf(message: AppendMessage): File_[] {
  return (message.attachments || []).flatMap((a) => {
    const up = uploaded.get(a.id);
    return up ? [{ fileId: up.fileId, kind: up.kind, name: a.name, thumb: up.thumb }] : [];
  });
}

function threadFromUrl(): string | null {
  return new URL(window.location.href).searchParams.get("thread");
}

function showThreadInUrl(id: string) {
  const url = new URL(window.location.href);
  url.searchParams.set("thread", id);
  window.history.replaceState(null, "", url);
}

export default function Chat({ lang, player, siteUrl }: { lang: Lang; player: string; siteUrl: string }) {
  const t = STRINGS[lang];
  const [threads, setThreads] = useState<ThreadRow[]>([]);
  const [current, setCurrent] = useState<string | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("idle");
  const [stop, setStop] = useState<string | undefined>();
  const [usedPct, setUsedPct] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [bookSlug, setBookSlug] = useState<string | null>(null);
  const [replays, setReplays] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [sidebar, setSidebar] = useState(false);
  const [showChapters, setShowChapters] = useState(false);
  const currentRef = useRef<string | null>(null);
  currentRef.current = current;
  // True while a message is on its way: a history load answered before the server has it reads
  // "idle", which must not end the turn this page just started (and close its live stream).
  const sending = useRef(false);
  // Whether the page is on screen. A hidden tab keeps no live stream open.
  const [visible, setVisible] = useState(() => typeof document === "undefined" || document.visibilityState === "visible");
  useEffect(() => {
    const onChange = () => setVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);

  const merge = useCallback((incoming: ChatEvent[]) => {
    setItems((prev) => {
      const seen = new Set(prev.flatMap((e) => ("serverId" in e && e.serverId ? [e.id, e.serverId] : [e.id])));
      let next = prev;
      for (const ev of incoming) {
        if (seen.has(ev.id)) continue;
        seen.add(ev.id);
        if (ev.kind === "user") {
          // The server's copy of a message sent from this page replaces the local one.
          const i = next.findIndex((e) => "local" in e && e.text === ev.text);
          const localFiles = i >= 0 ? ((next[i] as Local).files || []) : [];
          if (i >= 0) {
            // Keep this page's thumbnails for files the server copy only names by id.
            const files = (ev.files || []).map((f) => ({ ...f, thumb: localFiles.find((l) => l.fileId === f.fileId)?.thumb }));
            next = [...next.slice(0, i), { ...ev, files, id: next[i].id, serverId: ev.id }, ...next.slice(i + 1)];
            continue;
          }
        }
        if (ev.kind === "user" || ev.kind === "agent" || ev.kind === "tool" || ev.kind === "compacted" || ev.kind === "error") {
          next = [...next, ev];
        }
      }
      return next;
    });
    for (const ev of incoming) {
      if (ev.kind === "status") {
        setStatus(ev.state);
        setStop(ev.stop);
      }
    }
  }, []);

  const listThreads = useCallback(async () => {
    const res = await fetch("/api/threads", { cache: "no-store" });
    if (!res.ok) return [] as ThreadRow[];
    const rows = ((await res.json()).threads || []) as ThreadRow[];
    setThreads(rows);
    return rows;
  }, []);

  const load = useCallback(async (id: string, sync = false) => {
    const res = await fetch(`/api/thread?thread=${encodeURIComponent(id)}${sync ? "&sync=1" : ""}`, { cache: "no-store" });
    if (!res.ok || currentRef.current !== id) return;
    const data = await res.json();
    merge(data.events);
    if (!(sending.current && data.status === "idle")) setStatus(data.status);
    setUsedPct(data.usedPct ?? null);
    setChapters(data.chapters);
    setBookSlug(data.bookSlug ?? null);
    setLoading(false);
  }, [merge]);

  const open = useCallback((id: string) => {
    if (id === currentRef.current) return;
    currentRef.current = id;
    setCurrent(id);
    setItems([]);
    setStatus("idle");
    setStop(undefined);
    setNotice(null);
    setLoading(true);
    setSidebar(false);
    showThreadInUrl(id);
  }, []);

  // First load: the thread list, then the thread the address names (or the newest open one).
  useEffect(() => {
    fetch("/replays.json").then((r) => (r.ok ? r.json() : {})).then(setReplays).catch(() => {});
    listThreads().then((rows) => {
      const wanted = threadFromUrl();
      const pick = rows.find((r) => r.id === wanted) ?? rows.find((r) => !r.archived) ?? rows[0];
      if (pick) open(pick.id);
    });
  }, [listThreads, open]);

  // The open thread's history.
  useEffect(() => {
    if (current) load(current, true);
  }, [current, load]);

  // Back on screen: reload, which also shows a turn that started or ended while the tab was hidden.
  const wasVisible = useRef(visible);
  useEffect(() => {
    if (visible && !wasVisible.current && currentRef.current) load(currentRef.current);
    wasVisible.current = visible;
  }, [visible, load]);

  // Live events only while the coach is working and the page is on screen. An open stream holds a
  // server function (2 GB on Vercel) for up to five minutes whether or not anything arrives, so an
  // idle or background tab must not keep one. The coach's idle event closes it.
  // "rescheduling" is the session retrying mid-turn.
  const live = Boolean(current) && visible && (status === "running" || status === "rescheduling");
  useEffect(() => {
    if (!live || !current) return;
    const source = new EventSource(`/api/thread/stream?thread=${encodeURIComponent(current)}`);
    // Each (re)connection: fill whatever arrived before it, and learn whether the turn already ended.
    source.onopen = () => load(current);
    source.onmessage = (msg) => {
      if (currentRef.current !== current) return;
      const ev = JSON.parse(msg.data) as ChatEvent;
      merge([ev]);
      // Chapters show up in the outputs a moment after the turn ends; the title after the first message.
      if (ev.kind === "status" && ev.state === "idle") {
        setTimeout(() => load(current, true), 3000);
        listThreads();
      }
    };
    return () => source.close();
  }, [live, current, load, merge, listThreads]);

  const send = useCallback(async (text: string, files: File_[] = []) => {
    const id = currentRef.current;
    if ((!text && !files.length) || !id) return;
    setNotice(null);
    setItems((prev) => [...prev, { id: `local-${Date.now()}`, kind: "user", text, local: true, files }]);
    sending.current = true;
    setStatus("running");
    const res = await fetch("/api/thread/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, thread: id, attachments: files.map((f) => f.fileId) }),
    }).finally(() => {
      sending.current = false;
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      if (body.error === "budget") setStop("budget_reached");
      else if (body.error === "subscription") window.location.reload();
      else setNotice(t.error);
      setStatus("idle");
      return;
    }
    // A long thread goes on in a fresh session (lib/rollover.ts): follow it without clearing the
    // page; its history load brings the earlier messages back above the marker.
    const body = await res.json().catch(() => ({}));
    if (typeof body.thread === "string" && body.thread !== id && currentRef.current === id) {
      const marker = { id: `continued-${body.thread}`, kind: "compacted" as const };
      setItems((prev) => {
        // The marker goes above the message just sent, which now lives in the fresh session.
        const i = prev.findLastIndex((e) => "local" in e);
        return i < 0 ? [...prev, marker] : [...prev.slice(0, i), marker, ...prev.slice(i)];
      });
      currentRef.current = body.thread;
      setCurrent(body.thread);
      showThreadInUrl(body.thread);
      listThreads();
      return;
    }
    // The first message names the thread.
    setTimeout(listThreads, 1500);
  }, [listThreads, t.error]);

  const newThread = useCallback(async () => {
    setCreating(true);
    setNotice(null);
    try {
      const res = await fetch("/api/threads", { method: "POST" });
      if (!res.ok) throw new Error(String(res.status));
      const { id } = await res.json();
      await listThreads();
      open(id);
    } catch {
      setNotice(t.newThreadFailed);
    } finally {
      setCreating(false);
    }
  }, [listThreads, open, t.newThreadFailed]);

  const patchThread = useCallback(async (id: string, change: { title?: string; archived?: boolean }) => {
    setThreads((prev) => prev.map((r) => (r.id === id ? { ...r, ...change } : r)));
    await fetch(`/api/threads/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(change),
    });
    if (change.archived && id === currentRef.current) {
      const rows = await listThreads();
      const next = rows.find((r) => !r.archived && r.id !== id);
      if (next) open(next.id);
    }
  }, [listThreads, open]);

  const running = status === "running";
  const outOfBudget = stop === "budget_reached";
  const messages = useMemo(() => toMessages(items, running, t), [items, running, t]);
  const attachments = useMemo(() => attachmentAdapter({ tooLarge: t.fileTooLarge, failed: t.uploadFailed, limit: t.uploadLimit }), [t]);
  // Browser speech input, made after the first render so the server's HTML matches.
  const [dictation, setDictation] = useState<WebSpeechDictationAdapter | undefined>();
  useEffect(() => {
    if (WebSpeechDictationAdapter.isSupported?.()) setDictation(new WebSpeechDictationAdapter({ language: lang === "ja" ? "ja-JP" : "en-US" }));
  }, [lang]);

  // First questions, for an empty thread only (with messages in it they would sit above the
  // composer as follow-ups). A click writes one into the composer; the player sends it.
  const empty = messages.length === 0 && !loading;
  const suggestions = useMemo(() => (empty ? t.starters.map((prompt) => ({ prompt })) : []), [empty, t]);

  const runtime = useExternalStoreRuntime<ThreadMessageLike>({
    messages,
    convertMessage: (m) => m,
    isRunning: running,
    isLoading: loading,
    isDisabled: outOfBudget || creating || !current,
    suggestions,
    onNew: async (message) => send(textOf(message), filesOf(message)),
    adapters: {
      dictation,
      attachments,
      threadList: {
        threadId: current ?? undefined,
        isLoading: !current && threads.length === 0,
        threads: threads.filter((r) => !r.archived).map((r) => ({ status: "regular" as const, id: r.id, title: r.title ?? undefined })),
        archivedThreads: threads.filter((r) => r.archived).map((r) => ({ status: "archived" as const, id: r.id, title: r.title ?? undefined })),
        onSwitchToThread: (id) => open(id),
        onSwitchToNewThread: () => newThread(),
        onRename: (id, title) => patchThread(id, { title }),
        onArchive: (id) => patchThread(id, { archived: true }),
        onUnarchive: (id) => patchThread(id, { archived: false }),
      },
    },
  });

  const toggleChapter = async (chapter: Chapter) => {
    const isPublic = !chapter.isPublic;
    setChapters((prev) => prev.map((c) => (c.key === chapter.key ? { ...c, isPublic } : c)));
    await fetch("/api/chapters", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapter: chapter.key, isPublic }),
    });
  };

  const ctx = useMemo(() => ({ lang, siteUrl, replays }), [lang, siteUrl, replays]);
  const site = SITE[lang];
  const siteLink = "flex min-h-9 items-center gap-2.5 rounded-md px-2 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground";
  const Welcome = useMemo(
    () =>
      function Welcome() {
        return (
          <div className="mx-auto flex w-full max-w-(--thread-max-width) flex-col gap-2 px-2 pb-6">
            <p className="font-serif text-2xl">{player}</p>
            <p className="font-sans text-muted-foreground">{t.emptyThread}</p>
          </div>
        );
      },
    [player, t.emptyThread],
  );
  const labels = useMemo(
    () => ({
      placeholder: t.placeholder, newThread: t.newThread, untitled: t.untitled, search: t.threads,
      rename: t.rename, archive: t.archive, archived: t.archived, unarchive: t.unarchive,
    }),
    [t],
  );

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AuiLabelsContext.Provider value={labels}>
        <MahjongContext.Provider value={ctx}>
          <div className="flex h-dvh overflow-hidden bg-background">
            {/* Sidebar: threads, as in Claude Desktop. A drawer on phones. */}
            <aside
              className={`fixed inset-y-0 left-0 z-30 flex w-72 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-transform md:static md:translate-x-0 ${sidebar ? "translate-x-0" : "-translate-x-full"}`}
              aria-label={t.threads}
            >
              <div className="flex items-center justify-between gap-3 px-4 pt-4 pb-2">
                <div className="flex min-w-0 items-center gap-3">
                  <a href={site.playbookHref} aria-label={site.bookTitle} title={site.bookTitle} className="shrink-0 rounded-sm">
                    <svg viewBox="8 0 48 64" aria-hidden="true" focusable="false" className="h-8 w-6">
                      <rect x="8" width="48" height="64" rx="10" fill="var(--felt)" />
                      <rect x="12" y="4" width="40" height="49" rx="7" fill="var(--plate)" />
                      <g fill="var(--verm)">
                        <path d="M24 10H47V15H45Q42 15.4 42 18.5V35.5C42 44 36.6 48.6 29.5 48.6C23.6 48.6 18.6 45.4 18.6 40.6L27.6 41.4C31.2 42 33 39.8 33 35.5V18.5Q33 15.4 30 15H24Z" />
                        <circle cx="23.6" cy="40.4" r="5.8" />
                      </g>
                    </svg>
                  </a>
                  <div className="grid min-w-0 leading-tight">
                    <span className="font-sans text-[11px] font-bold tracking-[0.14em] text-muted-foreground uppercase">{t.title}</span>
                    <span className="truncate font-serif text-lg">{player}</span>
                  </div>
                </div>
                <button type="button" className="rounded-md p-1.5 hover:bg-sidebar-accent md:hidden" onClick={() => setSidebar(false)} aria-label="Close">
                  <XIcon className="size-4" />
                </button>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
                <ThreadList />
              </div>
              <nav className="grid border-t border-sidebar-border px-2 py-2 font-sans text-sm" aria-label={t.siteLinks}>
                {bookSlug && chapters.length > 0 && (
                  <a className={siteLink} href={`/books/${bookSlug}`}><NotebookTextIcon className="size-4 shrink-0" />{t.yourGuide}</a>
                )}
                <a className={siteLink} href="/books"><LibraryIcon className="size-4 shrink-0" />{site.guides}</a>
                <a className={siteLink} href={site.playbookHref}><BookOpenIcon className="size-4 shrink-0" />{site.bookTitle}</a>
              </nav>
              <div className="grid gap-2 border-t border-sidebar-border px-4 py-3 font-sans text-sm">
                {usedPct != null && (
                  <div className="grid gap-1" title={t.used(usedPct)}>
                    <div className="h-1.5 overflow-hidden rounded-full bg-secondary" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={usedPct} aria-label={t.used(usedPct)}>
                      <span className="block h-full bg-primary" style={{ width: `${usedPct}%` }} />
                    </div>
                    <span className="text-xs text-muted-foreground">{t.used(usedPct)}</span>
                  </div>
                )}
                <div className="flex gap-3">
                  <a className="text-muted-foreground hover:text-foreground" href="/account">{t.accountLink}</a>
                  <button type="button" className="text-muted-foreground hover:text-foreground" onClick={() => signOut({ callbackUrl: "/login" })}>
                    {t.signOut}
                  </button>
                </div>
              </div>
            </aside>
            {sidebar && <div className="fixed inset-0 z-20 bg-black/20 md:hidden" onClick={() => setSidebar(false)} />}

            <main className="flex min-w-0 flex-1 flex-col">
              <header className="flex items-center gap-2 border-b border-border px-3 py-2 font-sans text-sm">
                <button type="button" className="rounded-md p-1.5 hover:bg-muted md:hidden" onClick={() => setSidebar(true)} aria-label={t.showThreads}>
                  <MenuIcon className="size-5" />
                </button>
                <span className="min-w-0 flex-1 truncate font-medium">
                  {threads.find((r) => r.id === current)?.title || t.untitled}
                </span>
                {chapters.length > 0 && (
                  <button
                    type="button"
                    className={`rounded-full border border-border px-3 py-1 text-xs ${showChapters ? "bg-accent text-accent-foreground" : "hover:bg-muted"}`}
                    aria-expanded={showChapters}
                    onClick={() => setShowChapters((v) => !v)}
                  >
                    {t.chapters} · {chapters.length}
                  </button>
                )}
              </header>

              {showChapters && chapters.length > 0 && (
                <section className="max-h-[40vh] overflow-y-auto border-b border-border bg-card px-4 py-3" aria-label={t.chapters}>
                  <ul className="mx-auto grid max-w-176 gap-2">
                    {chapters.map((c) => (
                      <li key={c.key} className="flex items-baseline gap-3 rounded-lg border border-border bg-background px-3 py-2">
                        <span className="font-sans text-xs font-bold whitespace-nowrap text-destructive">{t.chapter(c.number)}</span>
                        <span className="min-w-0 flex-1 font-serif">
                          {c.isPublic && bookSlug ? <a className="underline underline-offset-2" href={`/books/${bookSlug}/${encodeURIComponent(c.key)}`}>{c.title}</a> : c.title}
                        </span>
                        <button
                          type="button"
                          className={`rounded-full border px-2.5 py-0.5 font-sans text-xs ${c.isPublic ? "border-primary bg-accent text-primary" : "border-border text-muted-foreground"}`}
                          aria-pressed={c.isPublic}
                          onClick={() => toggleChapter(c)}
                        >
                          {c.isPublic ? t.public : t.private}
                        </button>
                      </li>
                    ))}
                  </ul>
                  <p className="mx-auto mt-2 max-w-176 font-sans text-xs text-muted-foreground">{t.publicNote}</p>
                </section>
              )}

              {(notice || outOfBudget || creating) && (
                <p className={`px-4 py-2 text-center font-sans text-sm ${creating ? "text-muted-foreground" : "text-destructive"}`} role="status">
                  {creating ? t.startingThread : outOfBudget ? t.budgetReached : notice}
                </p>
              )}

              <div className="min-h-0 flex-1">
                <Thread components={{ Welcome }} />
              </div>
            </main>
          </div>
        </MahjongContext.Provider>
      </AuiLabelsContext.Provider>
    </AssistantRuntimeProvider>
  );
}
