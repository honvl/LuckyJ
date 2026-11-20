// The chat page's own root layout: assistant-ui's components need Tailwind, and keeping it here
// keeps Tailwind's reset away from the guide, books, login and account pages (app/(site)).
import type { Metadata } from "next";
import "../palette.css";
import "./chat.css";
import "../markdown.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { pageLang } from "@/lib/lang";
import { PRODUCT } from "@/lib/strings";

export const metadata: Metadata = { title: PRODUCT, robots: { index: false } };

export default async function ChatLayout({ children }: { children: React.ReactNode }) {
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
      <body>
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  );
}
