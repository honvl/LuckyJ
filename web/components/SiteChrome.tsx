// The running head and colophon of the site's app pages (/books, a guide, /tutor). The head copies
// the static Playbook's (site/index.html, .running-head in site/styles.css): the same tile mark,
// italic title, links in the same order on the right and the boxed language link, so moving
// between the two feels like one book.
import type { Lang } from "@/lib/strings";
import { SITE } from "@/lib/site-strings";

type Current = "guides" | "tutor" | null;

function BookMark() {
  return (
    <svg viewBox="8 0 48 64" aria-hidden="true" focusable="false" className="s-mark">
      <rect className="s-mark-back" x="8" width="48" height="64" rx="10" />
      <rect className="s-mark-face" x="12" y="4" width="40" height="49" rx="7" />
      <g className="s-mark-letter">
        <path d="M24 10H47V15H45Q42 15.4 42 18.5V35.5C42 44 36.6 48.6 29.5 48.6C23.6 48.6 18.6 45.4 18.6 40.6L27.6 41.4C31.2 42 33 39.8 33 35.5V18.5Q33 15.4 30 15H24Z" />
        <circle cx="23.6" cy="40.4" r="5.8" />
      </g>
    </svg>
  );
}

export function SiteHeader({ lang, current, path }: { lang: Lang; current: Current; path: string }) {
  const s = SITE[lang];
  const here = (which: Current) => (current === which ? { "aria-current": "page" as const } : {});
  return (
    <header className="s-head">
      <a className="s-brand" href={s.playbookHref}><BookMark /><span>{s.bookTitle}</span></a>
      <nav className="s-nav" aria-label={s.navLabel}>
        <a href={s.contentsHref}>{s.contents}</a>
        <a className="s-nav-2" href={s.prescriptionsHref}>{s.prescriptions}</a>
        <a className="s-nav-2" href={s.drillsHref}>{s.drills}</a>
        <a href="/books" {...here("guides")}>{s.guides}</a>
        <a className="s-quiet" href="/tutor" {...here("tutor")}>{s.tutor}</a>
      </nav>
      <a className="s-lang" href={`/lang?to=${s.otherLangCode}&back=${encodeURIComponent(path)}`} lang={s.otherLangCode} hrefLang={s.otherLangCode}>{s.otherLang}</a>
    </header>
  );
}

export function SiteFooter({ lang, note }: { lang: Lang; note?: string }) {
  const s = SITE[lang];
  return (
    <footer className="s-foot">
      <div className="s-foot-inner">
        <span className="s-foot-note">{note ? `${note} ` : ""}{s.notAffiliated}</span>
        <a href="/tutor">{s.tutor}</a>
        <a href={s.privacyHref}>{s.privacy}</a>
        <a href={s.termsHref}>{s.terms}</a>
        <a href={`mailto:${s.contact}`}>{s.contact}</a>
      </div>
    </footer>
  );
}
