import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import AccountPanel from "@/components/AccountPanel";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";
import { authOptions } from "@/lib/auth";
import { accessFor, billingEnabled } from "@/lib/billing";
import { ownChapters } from "@/lib/books";
import { STRINGS, pageLang } from "@/lib/lang";
import { getProfile } from "@/lib/profile";
import { SITE } from "@/lib/site-strings";
import { PRODUCT } from "@/lib/strings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: `Account: ${PRODUCT}`, robots: { index: false } };

export default async function AccountPage() {
  const email = (await getServerSession(authOptions))?.user?.email;
  if (!email) redirect("/login?callbackUrl=/account");
  const lang = await pageLang();
  const t = STRINGS[lang];
  const [access, profile] = await Promise.all([accessFor(email), getProfile(email)]);
  const own = access.thread ? await ownChapters(access.thread.player) : null;
  const sub = access.subscription;
  return (
    <div className="s-page s-page-fill">
      <SiteHeader lang={lang} current="tutor" path="/account" />
      <main className="s-main s-account">
        <div className="s-account-head">
          <div>
            <p className="s-kicker">{SITE[lang].tutor}</p>
            <h1 className="s-h1 s-gate-h1">{t.account}</h1>
          </div>
          <a className="s-btn s-btn-line-ink" href="/chat">{t.backToTutor}</a>
        </div>
        <AccountPanel
          lang={lang}
          email={access.email}
          billing={billingEnabled}
          subscription={{
            comp: access.comp && !!access.thread,
            status: sub?.status ?? null,
            renews: sub?.current_period_end ? new Date(sub.current_period_end).toISOString().slice(0, 10) : null,
            ends: sub?.cancel_at ? new Date(sub.cancel_at).toISOString().slice(0, 10) : null,
            canManage: Boolean(sub?.customer_id),
          }}
          profile={profile}
          guide={own ? {
            slug: own.slug,
            isPublic: own.bookPublic,
            chapters: own.chapters.map(({ key, number, title, isPublic }) => ({ key, number, title, isPublic })),
          } : null}
        />
      </main>
      <SiteFooter lang={lang} />
    </div>
  );
}
