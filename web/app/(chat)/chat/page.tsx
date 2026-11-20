import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { accessFor } from "@/lib/billing";
import { pageLang } from "@/lib/lang";
import Chat from "@/components/Chat";

export const dynamic = "force-dynamic";

export default async function ChatPage() {
  const lang = await pageLang();
  const session = await getServerSession(authOptions);
  const email = session?.user?.email;
  if (!email) redirect("/login");
  const access = await accessFor(email);
  // No tutor to open yet (not subscribed, subscription ended, or games still being fetched): the
  // subscribe and waiting screens are at /start, under the site's layout and stylesheet.
  if (!access.thread || !access.allowed) redirect("/start");
  return <Chat lang={lang} player={access.thread.player} siteUrl={process.env.SITE_URL || ""} />;
}
