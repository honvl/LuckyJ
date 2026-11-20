// The /start screen's three states: the subscribe form, the wait while a new subscriber's games
// are fetched, and the note for a login with no tutor when billing is off.
import AutoRefresh from "@/components/AutoRefresh";
import SignOutButton from "@/components/SignOutButton";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import Subscribe from "@/components/Subscribe";
import { SITE } from "@/lib/site-strings";
import { STRINGS, type Lang } from "@/lib/strings";

export default function StartBody({ lang, waiting, canSubscribe, ended }: { lang: Lang; waiting: boolean; canSubscribe: boolean; ended: boolean }) {
  const t = STRINGS[lang];
  const s = SITE[lang];
  return (
    <div className="s-page s-page-fill">
      <SiteHeader lang={lang} current="tutor" path="/start" />
      <main className={`s-gate${canSubscribe ? " s-gate-wide" : ""}`}>
        <div className="s-gate-text">
          <p className="s-kicker">{s.tutor}</p>
          <h1 className="s-h1 s-gate-h1">{waiting ? t.waitingTitle : t.subscribeTitle}</h1>
          <p className="s-lead">{waiting ? t.waitingLead : canSubscribe ? t.subscribeLead : t.notLinked}</p>
          {waiting && <p className="s-note"><AutoRefresh seconds={60} />{t.waitingChecks}</p>}
          {canSubscribe && (
            <div className="s-gate-plan">
              <p className="s-price"><span>{s.price}</span> {s.perMonth}</p>
              <p className="s-side-label">{t.included}</p>
              <ul>{s.planItems.map((item) => <li key={item}>{item}</li>)}</ul>
              <p className="s-note">{t.priceNote}</p>
            </div>
          )}
          <p className="s-gate-links">
            <a href="/account">{t.accountLink}</a>
            <SignOutButton label={t.signOut} />
          </p>
        </div>
        {canSubscribe && (
          <div className="s-card s-gate-form">
            <Subscribe lang={lang} ended={ended} />
          </div>
        )}
      </main>
      <SiteFooter lang={lang} />
    </div>
  );
}
