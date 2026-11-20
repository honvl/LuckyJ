import type { Metadata } from "next";
import LibraryGrid from "@/components/LibraryGrid";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { libraryItems } from "@/lib/library";
import { pageLang } from "@/lib/lang";
import { SITE } from "@/lib/site-strings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Personal Guides: The LuckyJ Playbook", robots: { index: true } };

export default async function BooksPage() {
  const lang = await pageLang();
  const s = SITE[lang];
  const items = await libraryItems(lang);
  const chapters = items.reduce((sum, it) => sum + it.chapters, 0);
  return (
    <div className="s-page">
      <SiteHeader lang={lang} current="guides" path="/books" />
      <main className="s-main">
        <div className="s-intro">
          <div>
            <p className="s-kicker">{s.libraryKicker}</p>
            <h1 className="s-h1">{s.libraryTitle}</h1>
            <p className="s-lead">{s.libraryLead}</p>
          </div>
          <p className="s-muted">{s.libraryCount(items.length, chapters)}</p>
        </div>
        <LibraryGrid lang={lang} items={items} />
        <p className="s-note">{s.libraryNote} <a href="/tutor">{s.aboutTutor}</a></p>
      </main>
      <SiteFooter lang={lang} />
    </div>
  );
}
