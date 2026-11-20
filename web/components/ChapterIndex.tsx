"use client";
// A guide's chapter list with topic filters (the guide's front page).
import { useMemo, useState } from "react";
import type { Lang } from "@/lib/strings";
import { SITE } from "@/lib/site-strings";

export type IndexEntry = { n: number; title: string; topic: string | null; date: string; href: string };

export default function ChapterIndex({ lang, entries }: { lang: Lang; entries: IndexEntry[] }) {
  const s = SITE[lang];
  const [topic, setTopic] = useState("All");
  const topics = useMemo(() => {
    const count = new Map<string, number>();
    for (const e of entries) if (e.topic) count.set(e.topic, (count.get(e.topic) || 0) + 1);
    return [...count.entries()].sort((a, b) => b[1] - a[1]).slice(0, 10).map(([t]) => t);
  }, [entries]);
  const shown = topic === "All" ? entries : entries.filter((e) => e.topic === topic);
  return (
    <section id="chapters" className="s-index" aria-labelledby="chapters-title">
      <div className="s-index-head">
        <h2 id="chapters-title" className="s-h2">{s.allChapters}</h2>
        <span className="s-muted">{s.shownChapters(shown.length, entries.length)}</span>
      </div>
      {topics.length > 1 && (
        <div className="s-chips" role="group" aria-label={s.topic}>
          {[s.all, ...topics].map((label, i) => {
            const value = i === 0 ? "All" : label;
            return (
              <button key={value} type="button" className={`s-chip${topic === value ? " is-on" : ""}`} aria-pressed={topic === value} onClick={() => setTopic(value)}>
                {label}
              </button>
            );
          })}
        </div>
      )}
      <ol className="s-chapter-list">
        {shown.map((e) => (
          <li key={e.n}>
            <a href={e.href}>
              <span className="s-num">{String(e.n).padStart(2, "0")}</span>
              <span className="s-chapter-text">
                <span className="s-chapter-title">{e.title}</span>
                <span className="s-muted s-small">{[e.topic, e.date].filter(Boolean).join(" · ")}</span>
              </span>
            </a>
          </li>
        ))}
      </ol>
    </section>
  );
}
