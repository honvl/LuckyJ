import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import AccountPanel from "@/components/AccountPanel";
import { authOptions } from "@/lib/auth";
import { accessFor, billingEnabled } from "@/lib/billing";
import { ownChapters } from "@/lib/books";
import { STRINGS, pageLang } from "@/lib/lang";
import { getProfile } from "@/lib/profile";
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
    <main className="book account">
      <p className="login-kicker"><a href="/chat">{t.title}</a> · {PRODUCT}</p>
      <h1>{t.account}</h1>
      <AccountPanel
        lang={lang}
        email={access.email}
        billing={billingEnabled}
        subscription={{
          comp: access.comp && !!access.thread,
          status: sub?.status ?? null,
          renews: sub?.current_period_end ? new Date(sub.current_period_end).toISOString().slice(0, 10) : null,
          canManage: Boolean(sub?.customer_id),
        }}
        profile={profile}
        guide={own ? {
          slug: own.slug,
          isPublic: own.bookPublic,
          chapters: own.chapters.map(({ key, number, title, isPublic }) => ({ key, number, title, isPublic })),
        } : null}
      />
      <p className="login-note book-foot">
        {t.notAffiliated} <a href={t.privacyHref}>{t.privacy}</a> · <a href={t.termsHref}>{t.terms}</a>
      </p>
    </main>
  );
}
