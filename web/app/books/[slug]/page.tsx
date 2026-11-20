import type { Metadata } from "next";
import { notFound } from "next/navigation";
import BookChapters from "@/components/BookChapters";
import { bookBySlug } from "@/lib/books";
import { STRINGS, pageLang } from "@/lib/lang";
import { PRODUCT } from "@/lib/strings";

export const dynamic = "force-dynamic";

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const book = await bookBySlug((await params).slug);
  return { title: book ? `${book.name}: ${PRODUCT}` : PRODUCT, robots: { index: true } };
}

export default async function BookPage({ params }: Params) {
  const book = await bookBySlug((await params).slug);
  if (!book) notFound();
  const lang = await pageLang();
  const t = STRINGS[lang];
  return (
    <main className="book">
      <p className="login-kicker"><a href="/books">{t.books}</a> · {PRODUCT}</p>
      <h1>{t.bookOf(book.name)}</h1>
      <p className="book-lead">{t.bookLead}</p>
      <BookChapters lang={lang} slug={book.slug} chapters={book.chapters} />
      <p className="login-note book-foot">
        {t.notAffiliated} <a href={t.privacyHref}>{t.privacy}</a>
      </p>
    </main>
  );
}
