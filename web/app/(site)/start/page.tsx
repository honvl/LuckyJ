// Where a signed-in player lands until the chat is theirs to use: the subscribe form, the wait
// while their games are fetched, or a note that this login has no tutor. /chat sends people here.
// It lives under app/(site) because these screens need the site's stylesheet, which the chat
// page's own layout (Tailwind) does not load.
import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import StartBody from "@/components/StartBody";
import { authOptions } from "@/lib/auth";
import { accessFor, billingEnabled } from "@/lib/billing";
import { pageLang } from "@/lib/lang";
import { PRODUCT } from "@/lib/strings";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: PRODUCT, robots: { index: false } };

const PAYING = ["active", "trialing", "past_due"];

export default async function StartPage() {
  const email = (await getServerSession(authOptions))?.user?.email;
  if (!email) redirect("/login");
  const access = await accessFor(email);
  if (access.thread && access.allowed) redirect("/chat");
  const paying = PAYING.includes(access.subscription?.status || "");
  // Paid with no thread yet: the games are being fetched and the tutor set up.
  const waiting = !access.thread && paying;
  const canSubscribe = !waiting && billingEnabled;
  return <StartBody lang={await pageLang()} waiting={waiting} canSubscribe={canSubscribe} ended={Boolean(access.thread)} />;
}
