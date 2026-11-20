import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ChapterIndex from "@/components/ChapterIndex";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { bookBySlug } from "@/lib/books";
import { chapterLead, rankLabel } from "@/lib/books-rules.mjs";
import { STATIC_GUIDE_OWNER, libraryItems } from "@/lib/library";
import { STRINGS, pageLang } from "@/lib/lang";
import { SITE } from "@/lib/site-strings";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const book = await bookBySlug((await params).slug);
  return { title: book ? `Personal Guide: ${book.name}` : "Personal Guides", robots: { index: true } };
}

export default async function BookPage({ params }: Params) {
  const book = await bookBySlug((await params).slug);
  if (!book) notFound();
  const lang = await pageLang();
  const s = SITE[lang];
  const day = new Intl.DateTimeFormat(lang === "ja" ? "ja-JP" : "en-GB", { day: "numeric", month: "long" });
  const short = new Intl.DateTimeFormat(lang === "ja" ? "ja-JP" : "en-GB", { day: "numeric", month: "short" });
  const chapters = [...book.chapters].sort((a, b) => a.number - b.number);
  const newest = chapters[chapters.length - 1];
  const updated = chapters.reduce((t, c) => Math.max(t, Date.parse(c.updatedAt)), 0);
  const rank = rankLabel(book.rankId, lang)?.label;
  const href = (key: string) => `/books/${book.slug}/${encodeURIComponent(key)}`;
  const news = [...chapters].reverse().slice(0, 2);
  const library = await libraryItems(lang);
  const others = library.filter((it) => it.key !== book.slug && it.name !== book.name).slice(0, 3);
  // The static guide's owner also has the long guide: point to it from the tutor's chapters.
  const mainGuide = book.player === STATIC_GUIDE_OWNER ? library.find((it) => it.key === "static-honver") : undefined;
  const path = `/books/${book.slug}`;
  return (
    <div className="s-page">
      <SiteHeader lang={lang} current="guides" path={path} />
      <section className="s-cover-band">
        <div className="s-band-inner">
          <nav aria-label="Breadcrumb" className="s-crumb"><a href="/books">{s.guides}</a> <span aria-hidden="true">/</span> {book.name}</nav>
          <div className="s-band-row">
            <div className="s-band-text">
              <span className="s-band-kicker">{s.personalGuide}</span>
              <h1 className="s-band-title">{book.name}</h1>
              <p className="s-band-sub">{s.tutorSub(book.name)}</p>
              <p className="s-band-meta">{[rank && s.onMajsoul(rank), s.chapters(chapters.length), updated && s.updated(day.format(new Date(updated)))].filter(Boolean).join(" · ")}</p>
            </div>
            <div className="s-band-actions">
              <a className="s-btn s-btn-paper" href={href(newest.key)}>{s.readNewest(newest.number)}</a>
              {chapters.length > 1 && <a className="s-btn s-btn-line" href={href(chapters[0].key)}>{s.startAtOne}</a>}
            </div>
          </div>
        </div>
      </section>
      <div className="s-columns">
        <div className="s-col-main">
          <aside className="s-news" aria-labelledby="news-title">
            <h2 id="news-title" className="s-h2">{s.whatsNew}</h2>
            <ol>
              {news.map((c) => (
                <li key={c.key}>
                  <a href={href(c.key)}>
                    <span className="s-news-date">{short.format(new Date(c.addedAt))}</span>
                    <span className="s-news-text"><strong>{STRINGS[lang].chapter(c.number)}</strong>: {c.title}. {chapterLead(c.markdown, 260)}</span>
                  </a>
                </li>
              ))}
            </ol>
          </aside>
          <ChapterIndex
            lang={lang}
            entries={chapters.map((c) => ({ n: c.number, title: c.title, topic: c.topic, date: day.format(new Date(c.addedAt)), href: href(c.key) }))}
          />
        </div>
        <aside className="s-col-side">
          {mainGuide && (
            <a className="s-book s-book-small" href={mainGuide.href}>
              <span className="s-cover"><span className="s-cover-kicker">{s.personalGuide}</span><span className="s-cover-name">{s.mainGuide(mainGuide.name, mainGuide.chapters)}</span></span>
              <span className="s-book-body"><span className="s-book-when">{s.newest} · {mainGuide.date}</span><span className="s-book-latest">{mainGuide.latest}</span></span>
            </a>
          )}
          <div className="s-panel">
            <h2 className="s-side-label">{s.howToRead}</h2>
            <p>{s.howToReadText}</p>
          </div>
          {others.length > 0 && (
            <div>
              <h2 className="s-side-label">{s.otherGuides}</h2>
              <ul className="s-side-list">
                {others.map((o) => (
                  <li key={o.key}><a href={o.href}><span className="s-muted s-small">{[o.name, o.rank].filter(Boolean).join(" · ")}</span><span className="s-side-title">{o.latest}</span></a></li>
                ))}
              </ul>
              <a className="s-strong-link" href="/books">{s.browseAll}</a>
            </div>
          )}
          <p className="s-note">{s.writtenWithTutor} <a href="/tutor">{s.aboutTutor}</a></p>
        </aside>
      </div>
      <SiteFooter lang={lang} note={s.publishedBy(book.name)} />
    </div>
  );
}
