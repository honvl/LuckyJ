// Change the Mahjong Soul account a login plays as, or the default for new chapters.
import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { signupFields } from "@/lib/billing-rules.mjs";
import { getProfile, saveProfile } from "@/lib/profile";

export async function POST(request: Request) {
  const email = (await getServerSession(authOptions))?.user?.email;
  if (!email) return NextResponse.json({ error: "not signed in" }, { status: 401 });
  const body = await request.json().catch(() => null);
  if (typeof body?.publish === "boolean" && !body.majsoulServer) {
    const current = await getProfile(email);
    if (!current?.majsoulAccountId) return NextResponse.json({ error: "no account yet" }, { status: 400 });
    await saveProfile(email, { majsoulServer: current.majsoulServer!, majsoulName: current.majsoulName!, majsoulAccountId: current.majsoulAccountId, publish: body.publish });
    return NextResponse.json({ ok: true });
  }
  const fields = signupFields(body);
  if (!fields) return NextResponse.json({ error: "bad request" }, { status: 400 });
  const { publish: _ignored, ...account } = fields;
  await saveProfile(email, account);
  return NextResponse.json({ ok: true });
}
