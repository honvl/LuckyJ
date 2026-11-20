"use client";
// A player's book: chapter prose (the coach's chapter.md) and its cards (spots.json), drawn with
// the chat's renderer so tiles, tables and game references look the same.
import { useEffect, useMemo, useState } from "react";
import type { BookChapter } from "@/lib/books";
import { STRINGS, type Lang } from "@/lib/strings";
import Markdown from "./Markdown";

type Spot = {
  id?: string; game?: string; round?: string; frames?: { turn?: number; kind?: string }[];
  title?: string; situation?: string; did?: string; luckyj?: string; fix?: string; verdict?: string;
  ja?: Partial<Record<"title" | "situation" | "did" | "luckyj" | "fix", string>>;
};

function gameMarkup(spot: Spot, replays: Record<string, string>): string {
  const turn = spot.frames?.[0]?.turn;
  if (!spot.game || !spot.round || !turn) return "";
  // Cards name a game by its short id; a replay is keyed by the full one.
  const uuid = Object.keys(replays).find((id) => id.startsWith(spot.game!)) || spot.game;
  if (!/^\d{6}-[0-9a-f-]{8,40}$/.test(uuid)) return "";
  return `[[game:${uuid} ${spot.round} t${turn}${spot.frames?.[0]?.kind === "call" ? " call" : ""}]]`;
}

function Card({ spot, lang, ctx }: { spot: Spot; lang: Lang; ctx: any }) {
  const t = STRINGS[lang];
  const text = (k: "title" | "situation" | "did" | "luckyj" | "fix") => (lang === "ja" && spot.ja?.[k]) || spot[k] || "";
  const rows: [string, string][] = [
    [t.cardSituation, text("situation")],
    [t.cardDid, text("did")],
    [t.cardLuckyj, text("luckyj")],
    [spot.verdict ? t.cardVerdict : t.cardFix, spot.verdict ? (t.verdicts as any)[spot.verdict] || spot.verdict : text("fix")],
  ];
  const ref = gameMarkup(spot, ctx.replays);
  return (
    <article className="book-card" id={spot.id ? `card-${spot.id}` : undefined}>
      <h4>{text("title")}</h4>
      {ref && <Markdown text={ref} ctx={ctx} />}
      <dl>
        {rows.filter(([, v]) => v).map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd><Markdown text={v} ctx={ctx} /></dd>
          </div>
        ))}
      </dl>
    </article>
  );
}

export default function BookChapters({ lang, slug, chapters }: { lang: Lang; slug: string; chapters: BookChapter[] }) {
  const t = STRINGS[lang];
  const [replays, setReplays] = useState<Record<string, string>>({});
  useEffect(() => {
    fetch("/replays.json").then((r) => (r.ok ? r.json() : {})).then(setReplays).catch(() => {});
  }, []);
  const base = useMemo(() => ({ lang, siteUrl: "", replays }), [lang, replays]);
  return (
    <>
      <nav className="book-toc" aria-label={t.contents}>
        <h2>{t.contents}</h2>
        <ol>
          {chapters.map((c) => (
            <li key={c.key}><a href={`#ch-${c.key}`}>{c.title}</a></li>
          ))}
        </ol>
      </nav>
      {chapters.map((c) => {
        const ctx = { ...base, assetBase: `/books/${slug}/files/${encodeURIComponent(c.key)}` };
        const spots = Array.isArray(c.spots) ? (c.spots as Spot[]) : [];
        return (
          <section key={c.key} className="book-chapter" id={`ch-${c.key}`}>
            <Markdown text={c.markdown} ctx={ctx} />
            {spots.length > 0 && (
              <div className="book-cards">
                <h3>{t.cards}</h3>
                {spots.map((s, i) => <Card key={s.id || i} spot={s} lang={lang} ctx={ctx} />)}
              </div>
            )}
          </section>
        );
      })}
    </>
  );
}
