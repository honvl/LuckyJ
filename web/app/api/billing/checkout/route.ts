import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { accessFor, billingEnabled, checkoutUrl } from "@/lib/billing";
import { signupFields } from "@/lib/billing-rules.mjs";
import { saveProfile } from "@/lib/profile";

export async function POST(request: Request) {
  const email = (await getServerSession(authOptions))?.user?.email;
  if (!email) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  if (!billingEnabled) return NextResponse.json({ error: "billing is not set up" }, { status: 503 });
  const fields = signupFields(await request.json().catch(() => null));
  if (!fields) return NextResponse.json({ error: "missing fields" }, { status: 400 });
  const access = await accessFor(email);
  if (access.allowed || (access.subscription && ["active", "trialing", "past_due"].includes(access.subscription.status))) {
    return NextResponse.json({ error: "already subscribed" }, { status: 409 });
  }
  // Who they play as is kept with the login, not in Stripe.
  await saveProfile(access.email, fields);
  return NextResponse.json({ url: await checkoutUrl(access.email) });
}
