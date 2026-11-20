import type { Metadata } from "next";
import { publicBooks } from "@/lib/books";
import { STRINGS, pageLang } from "@/lib/lang";
import { PRODUCT } from "@/lib/strings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: `Personal Guides: ${PRODUCT}`, robots: { index: true } };

export default async function BooksPage() {
  const lang = await pageLang();
  const t = STRINGS[lang];
  const books = await publicBooks();
  const fmt = new Intl.DateTimeFormat(lang === "ja" ? "ja-JP" : "en-GB", { day: "numeric", month: "short", year: "numeric" });
  return (
    <main className="book">
      <p className="login-kicker"><a href={lang === "ja" ? "/ja.html" : "/"}>LuckyJ Playbook</a> · {PRODUCT}</p>
      <h1>{t.books}</h1>
      <p className="book-lead">{t.booksLead}</p>
      <ul className="book-list">
        <li>
          <a href={lang === "ja" ? "/honver-ja.html" : "/honver.html"}>{t.honverGuide}</a>
          <span className="login-note">{t.honverGuideNote}</span>
        </li>
        {books.map((b) => (
          <li key={b.slug}>
            <a href={`/books/${b.slug}`}>{t.bookOf(b.name)}</a>
            <span className="login-note">{t.chapterCount(b.chapters)} · {fmt.format(new Date(b.updated))}</span>
          </li>
        ))}
      </ul>
      <p className="login-note book-foot">
        {t.notAffiliated} <a href={t.privacyHref}>{t.privacy}</a> · <a href={t.termsHref}>{t.terms}</a>
      </p>
    </main>
  );
}
