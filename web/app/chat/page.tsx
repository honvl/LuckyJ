import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { accessFor, billingEnabled } from "@/lib/billing";
import { STRINGS, pageLang } from "@/lib/lang";
import { PRODUCT } from "@/lib/strings";
import Chat from "@/components/Chat";
import ManageButton from "@/components/ManageButton";
import SignOutButton from "@/components/SignOutButton";
import Subscribe from "@/components/Subscribe";

export const dynamic = "force-dynamic";

const PAYING = ["active", "trialing", "past_due"];

export default async function ChatPage() {
  const lang = await pageLang();
  const t = STRINGS[lang];
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) redirect("/login");
  const access = await accessFor(email);
  const paying = PAYING.includes(access.subscription?.status || "");

  if (access.thread && access.allowed) {
    return (
      <Chat
        lang={lang}
        player={access.thread.player}
        siteUrl={process.env.SITE_URL || ""}
        canManage={Boolean(access.subscription?.customer_id)}
      />
    );
  }

  let body: React.ReactNode;
  let title: string = t.title;
  if (access.thread || !paying) {
    // No thread and no subscription, or a thread whose subscription ended.
    title = t.subscribeTitle;
    body = billingEnabled ? <Subscribe lang={lang} ended={Boolean(access.thread)} /> : <p className="login-lead">{t.notLinked}</p>;
  } else {
    // Paid, thread not created yet: the operator fetches the games and starts it.
    title = t.waitingTitle;
    body = <p className="login-lead">{t.waitingLead}</p>;
  }
  return (
    <main className="login">
      <p className="login-kicker">{PRODUCT}</p>
      <h1>{title}</h1>
      {body}
      <p className="login-actions">
        {access.subscription?.customer_id && <ManageButton label={t.manage} />}
        <SignOutButton label={t.signOut} />
      </p>
      <p className="login-note">
        {t.notAffiliated} <a href={t.privacyHref}>{t.privacy}</a>
      </p>
    </main>
  );
}
