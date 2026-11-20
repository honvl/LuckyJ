"use client";
import { signOut } from "next-auth/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ChatEvent } from "@/lib/events";
import { STRINGS, type Lang } from "@/lib/strings";
import Markdown from "./Markdown";

type Chapter = { key: string; number: number; title: string; isPublic: boolean };
type Local = { id: string; kind: "user"; text: string; local: true };
type Item = ChatEvent | Local;

type Block =
  | { type: "user"; id: string; text: string }
  | { type: "agent"; id: string; text: string }
  | { type: "work"; id: string; steps: Extract<ChatEvent, { kind: "tool" }>[] }
  | { type: "note"; id: string; text: string };

function toBlocks(items: Item[], t: (typeof STRINGS)[Lang]): Block[] {
  const blocks: Block[] = [];
  for (const ev of items) {
    if (ev.kind === "user") blocks.push({ type: "user", id: ev.id, text: ev.text });
    else if (ev.kind === "agent") blocks.push({ type: "agent", id: ev.id, text: ev.text });
    else if (ev.kind === "tool") {
      const last = blocks[blocks.length - 1];
      if (last?.type === "work") last.steps.push(ev);
      else blocks.push({ type: "work", id: ev.id, steps: [ev] });
    } else if (ev.kind === "compacted") blocks.push({ type: "note", id: ev.id, text: t.compacted });
    else if (ev.kind === "error") blocks.push({ type: "note", id: ev.id, text: ev.message });
  }
  return blocks;
}

export default function Chat({ lang, player, siteUrl }: { lang: Lang; player: string; siteUrl: string }) {
  const t = STRINGS[lang];
  const [items, setItems] = useState<Item[]>([]);
  const [status, setStatus] = useState<string>("idle");
  const [stop, setStop] = useState<string | undefined>();
  const [spent, setSpent] = useState(0);
  const [cap, setCap] = useState<number | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [bookSlug, setBookSlug] = useState<string | null>(null);
  const [replays, setReplays] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState("");
  const [failed, setFailed] = useState(false);
  const stuck = useRef(true);

  const merge = useCallback((incoming: ChatEvent[]) => {
    setItems((prev) => {
      const seen = new Set(prev.map((e) => e.id));
      let next = prev;
      for (const ev of incoming) {
        if (seen.has(ev.id)) continue;
        seen.add(ev.id);
        if (ev.kind === "user") {
          // The server's copy of a message sent from this page replaces the local one.
          const i = next.findIndex((e) => "local" in e && e.text === ev.text);
          if (i >= 0) {
            next = [...next.slice(0, i), ev, ...next.slice(i + 1)];
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
      if (ev.kind === "usage") setSpent(ev.spentCents);
      if (ev.kind === "status") {
        setStatus(ev.state);
        setStop(ev.stop);
      }
    }
  }, []);

  const load = useCallback(async (sync = false) => {
    const res = await fetch(sync ? "/api/thread?sync=1" : "/api/thread", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    merge(data.events);
    setStatus(data.status);
    setSpent(data.spentCents);
    setCap(data.capCents);
    setChapters(data.chapters);
    setBookSlug(data.bookSlug ?? null);
  }, [merge]);

  useEffect(() => {
    load(true);
    fetch("/replays.json").then((r) => (r.ok ? r.json() : {})).then(setReplays).catch(() => {});
    const source = new EventSource("/api/thread/stream");
    let dropped = false;
    source.onopen = () => {
      if (dropped) load(); // fill whatever arrived while disconnected
      dropped = false;
    };
    source.onerror = () => {
      dropped = true;
    };
    source.onmessage = (msg) => {
      const ev = JSON.parse(msg.data) as ChatEvent;
      merge([ev]);
      // Chapters show up in the outputs a moment after the turn ends.
      if (ev.kind === "status" && ev.state === "idle") setTimeout(() => load(true), 3000);
    };
    return () => source.close();
  }, [load, merge]);

  useEffect(() => {
    const onScroll = () => {
      stuck.current = window.innerHeight + window.scrollY >= document.body.scrollHeight - 120;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    // To the very bottom: the composer is fixed over the last ~100px of the window.
    if (stuck.current) window.scrollTo({ top: document.body.scrollHeight });
  }, [items, status]);

  const send = async () => {
    const text = draft.trim();
    if (!text) return;
    setFailed(false);
    setDraft("");
    stuck.current = true;
    setItems((prev) => [...prev, { id: `local-${Date.now()}`, kind: "user", text, local: true }]);
    setStatus("running");
    const res = await fetch("/api/thread/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      if (body.error === "budget") setStop("budget_reached");
      else if (body.error === "subscription") window.location.reload();
      else setFailed(true);
      setStatus("idle");
    }
  };

  const toggleChapter = async (chapter: Chapter) => {
    const isPublic = !chapter.isPublic;
    setChapters((prev) => prev.map((c) => (c.key === chapter.key ? { ...c, isPublic } : c)));
    await fetch("/api/chapters", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chapter: chapter.key, isPublic }),
    });
  };

  const blocks = useMemo(() => toBlocks(items, t), [items, t]);
  const ctx = useMemo(() => ({ lang, siteUrl, replays }), [lang, siteUrl, replays]);
  const pct = cap ? Math.min(100, Math.round((spent / cap) * 100)) : null;
  const running = status === "running";
  const outOfBudget = stop === "budget_reached";

  return (
    <div className="chat">
      <header className="chat-head">
        <div className="chat-title">
          <span className="chat-kicker">{t.title}</span>
          <span className="chat-player">{player}</span>
        </div>
        {pct != null && (
          <div className="spend" title={t.used(pct)}>
            <div className="spend-bar" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} aria-label={t.used(pct)}>
              <span style={{ width: `${pct}%` }} />
            </div>
            <span className="spend-text">{t.used(pct)}</span>
          </div>
        )}
        <a className="link-button" href="/account">{t.accountLink}</a>
        <button type="button" className="link-button" onClick={() => signOut({ callbackUrl: "/login" })}>
          {t.signOut}
        </button>
      </header>

      {chapters.length > 0 && (
        <section className="chapters" aria-label={t.chapters}>
          <h2>{t.chapters}</h2>
          <ul>
            {chapters.map((c) => (
              <li key={c.key} className="chapter-card">
                <span className="chapter-num">{t.chapter(c.number)}</span>
                <span className="chapter-slug">
                  {c.isPublic && bookSlug ? <a href={`/books/${bookSlug}#ch-${c.key}`}>{c.title}</a> : c.title}
                </span>
                <button type="button" className={`pill ${c.isPublic ? "is-on" : ""}`} aria-pressed={c.isPublic} onClick={() => toggleChapter(c)}>
                  {c.isPublic ? t.public : t.private}
                </button>
              </li>
            ))}
          </ul>
          <p className="chapters-note">{t.publicNote}</p>
        </section>
      )}

      <main className="thread">
        {blocks.map((b, i) => {
          if (b.type === "user") return <div key={b.id} className="msg msg-user">{b.text}</div>;
          if (b.type === "agent") return <div key={b.id} className="msg msg-agent"><Markdown text={b.text} ctx={ctx} /></div>;
          if (b.type === "note") return <p key={b.id} className="msg-note">{b.text}</p>;
          const live = running && i === blocks.length - 1;
          return (
            <details key={b.id} className={`work ${live ? "is-live" : ""}`}>
              <summary>
                {live ? t.working : b.steps[b.steps.length - 1].label} · {t.steps(b.steps.length)}
              </summary>
              <ol>
                {b.steps.map((s) => (
                  <li key={s.id}>
                    <span className="work-label">{s.label}</span>
                    <code className="work-detail">{s.detail}</code>
                  </li>
                ))}
              </ol>
            </details>
          );
        })}
        {running && blocks[blocks.length - 1]?.type !== "work" && <p className="msg-note is-live">{t.working}…</p>}
        {failed && <p className="msg-note is-error">{t.error}</p>}
        {outOfBudget && <p className="msg-note is-error">{t.budgetReached}</p>}
      </main>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }}
          placeholder={t.placeholder}
          rows={2}
          maxLength={8000}
          disabled={outOfBudget}
        />
        <button className="button" type="submit" disabled={outOfBudget || !draft.trim()}>
          {t.send}
        </button>
      </form>
    </div>
  );
}
