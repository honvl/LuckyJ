import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { accessFor, billingEnabled, portalUrl } from "@/lib/billing";

export async function POST() {
  const email = (await getServerSession(authOptions))?.user?.email;
  if (!email) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  if (!billingEnabled) return NextResponse.json({ error: "billing is not set up" }, { status: 503 });
  const customer = (await accessFor(email)).subscription?.customer_id;
  if (!customer) return NextResponse.json({ error: "no subscription" }, { status: 404 });
  return NextResponse.json({ url: await portalUrl(customer) });
}
