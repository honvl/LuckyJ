"use client";
// The library's search, sort and rank and topic filters over the guides the page was given.
import { useMemo, useState } from "react";
import type { LibraryItem } from "@/lib/library";
import type { Lang } from "@/lib/strings";
import { SITE } from "@/lib/site-strings";

const TIERS = ["Celestial", "Saint", "Master", "Expert"];
const TIER_JA: Record<string, string> = { Celestial: "魂天", Saint: "雀聖", Master: "雀豪", Expert: "雀傑" };
const COVERS = ["#134834", "#2d3a55", "#5a3a2a", "#006243", "#3f4a3c", "#4a2d45"];

export default function LibraryGrid({ lang, items }: { lang: Lang; items: LibraryItem[] }) {
  const s = SITE[lang];
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<"newest" | "most" | "rank">("newest");
  const [tier, setTier] = useState("All");
  const [topic, setTopic] = useState("All");

  // The topics most chapters in the library are about.
  const topics = useMemo(() => {
    const count = new Map<string, number>();
    for (const it of items) for (const [t, n] of Object.entries(it.topicCounts)) count.set(t, (count.get(t) || 0) + n);
    return [...count.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 10).map(([t]) => t);
  }, [items]);
  const tiers = TIERS.filter((t) => items.some((it) => it.tier === t));

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = items.filter((it) =>
      (tier === "All" || it.tier === tier) &&
      (topic === "All" || it.topics.includes(topic)) &&
      (!q || [it.name, it.latest, ...it.topics].some((x) => x.toLowerCase().includes(q))));
    const by = {
      newest: (a: LibraryItem, b: LibraryItem) => b.time - a.time,
      most: (a: LibraryItem, b: LibraryItem) => b.chapters - a.chapters,
      rank: (a: LibraryItem, b: LibraryItem) => (b.rankId ?? 0) - (a.rankId ?? 0),
    }[sort];
    return [...list].sort(by);
  }, [items, query, sort, tier, topic]);

  const chip = (label: string, value: string, current: string, set: (v: string) => void) => (
    <button key={value} type="button" className={`s-chip${current === value ? " is-on" : ""}`} aria-pressed={current === value} onClick={() => set(value)}>
      {label}
    </button>
  );

  return (
    <>
      <div className="s-filters">
        <div className="s-filter-row">
          <div className="s-field s-field-grow">
            <label htmlFor="lib-q">{s.search}</label>
            <input id="lib-q" type="search" value={query} placeholder={s.searchPlaceholder} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <div className="s-field">
            <label htmlFor="lib-sort">{s.sort}</label>
            <select id="lib-sort" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
              <option value="newest">{s.sortNewest}</option>
              <option value="most">{s.sortMost}</option>
              <option value="rank">{s.sortRank}</option>
            </select>
          </div>
        </div>
        {tiers.length > 0 && (
          <div className="s-chips" role="group" aria-label={s.rank}>
            <span className="s-chips-label">{s.rank}</span>
            {chip(s.all, "All", tier, setTier)}
            {tiers.map((t) => chip(lang === "ja" ? TIER_JA[t] : t, t, tier, setTier))}
          </div>
        )}
        {topics.length > 0 && (
          <div className="s-chips" role="group" aria-label={s.topic}>
            <span className="s-chips-label">{s.topic}</span>
            {chip(s.all, "All", topic, setTopic)}
            {topics.map((t) => chip(t, t, topic, setTopic))}
          </div>
        )}
      </div>
      <p className="s-count" aria-live="polite">{shown.length ? s.shown(shown.length) : s.none}</p>
      <ul className="s-shelf">
        {shown.map((it) => (
          <li key={it.key}>
            <a className="s-book" href={it.href}>
              <span className="s-cover" style={{ background: COVERS[Math.max(0, items.indexOf(it)) % COVERS.length] }}>
                <span className="s-cover-kicker">{s.personalGuide}</span>
                <span className="s-cover-name">{it.name}</span>
                <span className="s-cover-meta">{[it.rank, s.chapters(it.chapters)].filter(Boolean).join(" · ")}</span>
              </span>
              <span className="s-book-body">
                <span className="s-book-when">{s.newest} · {it.date}</span>
                <span className="s-book-latest">{it.latest}</span>
                {it.topics.length > 0 && (
                  <span className="s-tags">{it.topics.slice(0, 3).map((t) => <span key={t} className="s-tag">{t}</span>)}</span>
                )}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </>
  );
}
