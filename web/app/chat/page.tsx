import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions, currentThread } from "@/lib/auth";
import { STRINGS, pageLang } from "@/lib/lang";
import Chat from "@/components/Chat";

export const dynamic = "force-dynamic";

export default async function ChatPage() {
  const lang = await pageLang();
  const session = await getServerSession(authOptions);
  if (!session) redirect("/login");
  const me = await currentThread();
  if (!me) {
    return (
      <main className="login">
        <h1>{STRINGS[lang].title}</h1>
        <p className="login-lead">{STRINGS[lang].notLinked}</p>
      </main>
    );
  }
  return <Chat lang={lang} player={me.player} siteUrl={process.env.SITE_URL || ""} />;
}
