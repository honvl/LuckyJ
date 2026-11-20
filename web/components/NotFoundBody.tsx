// The 404 page's body, shared by a missing guide or chapter (app/(site)/not-found.tsx) and an
// address that matches no page at all (app/global-not-found.tsx).
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { SITE } from "@/lib/site-strings";
import type { Lang } from "@/lib/strings";

export default function NotFoundBody({ lang }: { lang: Lang }) {
  const s = SITE[lang];
  return (
    <div className="s-page s-page-fill">
      <SiteHeader lang={lang} current={null} path="/" />
      <main className="s-main s-lost">
        <p className="s-kicker">{s.lostKicker}</p>
        <h1 className="s-h1">{s.lostTitle}</h1>
        <p className="s-lead">{s.lostLead}</p>
        <ul className="s-lost-links">
          <li><a href={s.playbookHref}><strong>{s.bookTitle}</strong><span>{s.lostPlaybook}</span></a></li>
          <li><a href="/books"><strong>{s.guides}</strong><span>{s.lostGuides}</span></a></li>
          <li><a href="/tutor"><strong>{s.tutor}</strong><span>{s.lostTutor}</span></a></li>
        </ul>
      </main>
      <SiteFooter lang={lang} />
    </div>
  );
}
