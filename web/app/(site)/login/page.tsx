import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { STRINGS, pageLang } from "@/lib/lang";
import { SITE } from "@/lib/site-strings";
import { PRODUCT } from "@/lib/strings";
import LoginButtons from "@/components/LoginButtons";
import { SiteFooter, SiteHeader } from "@/components/SiteChrome";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: `Sign in: ${PRODUCT}`, robots: { index: false } };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  // Already signed in: the chat, or the subscribe screen it forwards to.
  if ((await getServerSession(authOptions))?.user?.email) redirect("/chat");
  const lang = await pageLang();
  const t = STRINGS[lang];
  const s = SITE[lang];
  // A provider's own id and name sit in `options` until next-auth initialises it.
  const providers = authOptions.providers.map((p: any) => ({ id: p.options?.id ?? p.id, name: p.options?.name ?? p.name }));
  return (
    <div className="s-page s-page-fill">
      <SiteHeader lang={lang} current="tutor" path="/login" />
      <main className="s-gate">
        <div className="s-card s-gate-card">
          <p className="s-kicker">{s.tutor}</p>
          <h1 className="s-h1 s-gate-h1">{t.signIn}</h1>
          <p className="s-gate-lead">{t.signInLead}</p>
          {(await searchParams).error && <p className="login-error" role="alert">{t.signInFailed}</p>}
          <LoginButtons providers={providers} lang={lang} />
          <p className="s-note s-gate-new">{t.newHere} <a href="/tutor">{t.seeTutor}</a></p>
        </div>
      </main>
      <SiteFooter lang={lang} />
    </div>
  );
}
