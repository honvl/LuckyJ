// Shown for an address that matches no page. The app has two root layouts (app/(site) and
// app/(chat)), so Next.js has no layout to draw a 404 in and this file brings its own document
// (experimental.globalNotFound in next.config.mjs).
import type { Metadata } from "next";
import "./palette.css";
import "./globals.css";
import "./site.css";
import NotFoundBody from "@/components/NotFoundBody";
import { pageLang } from "@/lib/lang";

export const metadata: Metadata = { title: "Page not found: The LuckyJ Playbook" };

export default async function GlobalNotFound() {
  const lang = await pageLang();
  return (
    <html lang={lang}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..700;1,6..72,300..700&family=Schibsted+Grotesk:wght@400..800&family=Noto+Sans+JP:wght@400..700&display=swap"
        />
      </head>
      <body><NotFoundBody lang={lang} /></body>
    </html>
  );
}
