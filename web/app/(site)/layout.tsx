import type { Metadata } from "next";
import "../palette.css";
import "../globals.css";
import "../markdown.css";
import "../site.css";
import { pageLang } from "@/lib/lang";
import { PRODUCT } from "@/lib/strings";

export const metadata: Metadata = { title: PRODUCT, robots: { index: false } };

export default async function RootLayout({ children }: { children: React.ReactNode }) {
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
      <body>{children}</body>
    </html>
  );
}
