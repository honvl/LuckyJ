"use client";
// A chapter of a player's book: its prose (the coach's chapter.md) and its cards (spots.json),
// drawn with the chat's renderer so tiles, tables and game references look the same.
import { useMemo } from "react";
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

/** One chapter's prose and its cards. The page draws the kicker and the title itself. */
export default function ChapterBody({ lang, slug, chapter, replays }: {
  lang: Lang; slug: string; chapter: BookChapter; replays: Record<string, string>;
}) {
  const t = STRINGS[lang];
  // The guide's own replays (packed with its chapters): a game reference links to one of them.
  const ctx = useMemo(
    () => ({ lang, siteUrl: "", replays, book: slug, assetBase: `/books/${slug}/files/${encodeURIComponent(chapter.key)}` }),
    [lang, replays, slug, chapter.key],
  );
  const spots = Array.isArray(chapter.spots) ? (chapter.spots as Spot[]) : [];
  // The page shows the title as its own heading.
  const prose = chapter.markdown.replace(/^\s*#\s+.*\n?/, "");
  return (
    <div className="book-chapter">
      <Markdown text={prose} ctx={ctx} />
      {spots.length > 0 && (
        <div className="book-cards">
          <h3>{t.cards}</h3>
          {spots.map((s, i) => <Card key={s.id || i} spot={s} lang={lang} ctx={ctx} />)}
        </div>
      )}
    </div>
  );
}
