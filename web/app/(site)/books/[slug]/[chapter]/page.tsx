import type { Metadata } from "next";
import { notFound } from "next/navigation";
import ChapterBody from "@/components/ChapterBody";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { bookBySlug } from "@/lib/books";
import { pageLang } from "@/lib/lang";
import { SITE } from "@/lib/site-strings";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ slug: string; chapter: string }> };

async function find(params: Params["params"]) {
  const { slug, chapter } = await params;
  const book = await bookBySlug(slug);
  const key = decodeURIComponent(chapter);
  const chapters = book ? [...book.chapters].sort((a, b) => a.number - b.number) : [];
  const i = chapters.findIndex((c) => c.key === key);
  return book && i >= 0 ? { book, chapters, i } : null;
}

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const found = await find(params);
  return { title: found ? `${found.chapters[found.i].title}: Personal Guide: ${found.book.name}` : "Personal Guides", robots: { index: true } };
}

export default async function ChapterPage({ params }: Params) {
  const found = await find(params);
  if (!found) notFound();
  const { book, chapters, i } = found;
  const chapter = chapters[i];
  const lang = await pageLang();
  const s = SITE[lang];
  const day = new Intl.DateTimeFormat(lang === "ja" ? "ja-JP" : "en-GB", { day: "numeric", month: "long" });
  const href = (key: string) => `/books/${book.slug}/${encodeURIComponent(key)}`;
  const prev = chapters[i - 1];
  const next = chapters[i + 1];
  const same = chapter.topic ? chapters.filter((c) => c.topic === chapter.topic && c.key !== chapter.key).slice(-3).reverse() : [];
  const path = href(chapter.key);
  return (
    <div className="s-page">
      <SiteHeader lang={lang} current="guides" path={path} />
      <div className="s-subbar">
        <div className="s-subbar-inner">
          <nav aria-label="Breadcrumb" className="s-crumb-dark">
            <a href="/books">{s.guides}</a> <span aria-hidden="true">/</span> <a href={`/books/${book.slug}`}>{book.name}</a> <span aria-hidden="true">/</span> {chapter.number}
          </nav>
          <a className="s-strong-link" href={`/books/${book.slug}#chapters`}>{s.backToContents}</a>
        </div>
      </div>
      <div className="s-columns">
        <article className="s-col-main s-reading">
          <p className="s-kicker">{s.chapterKicker(chapter.number, chapter.topic, day.format(new Date(chapter.addedAt)))}</p>
          <h1 className="s-chapter-h1">{chapter.title}</h1>
          <ChapterBody lang={lang} slug={book.slug} chapter={chapter} />
          <nav className="s-pager" aria-label={s.allChapters}>
            {prev ? <a href={href(prev.key)}><span className="s-muted s-small">{s.previous(prev.number)}</span><span className="s-side-title">{prev.title}</span></a> : <span />}
            {next ? <a className="s-pager-next" href={href(next.key)}><span className="s-muted s-small">{s.next(next.number)}</span><span className="s-side-title">{next.title}</span></a>
              : <a className="s-pager-next" href={`/books/${book.slug}#chapters`}><span className="s-muted s-small">{s.allChapters}</span><span className="s-side-title">{s.backToContents}</span></a>}
          </nav>
        </article>
        <aside className="s-col-side">
          {same.length > 0 && (
            <div>
              <h2 className="s-side-label">{s.sameTopic}</h2>
              <ul className="s-side-list">
                {same.map((c) => (
                  <li key={c.key}><a href={href(c.key)}><span className="s-muted s-small">{s.chapterKicker(c.number, null, day.format(new Date(c.addedAt)))}</span><span className="s-side-title">{c.title}</span></a></li>
                ))}
              </ul>
            </div>
          )}
          <p className="s-note">{s.writtenWithTutor} <a href="/tutor">{s.aboutTutor}</a></p>
        </aside>
      </div>
      <SiteFooter lang={lang} note={s.publishedBy(book.name)} />
    </div>
  );
}
